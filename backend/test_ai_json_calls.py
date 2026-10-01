"""
Tests for the JSON-call failure modes that produced
"Video strategy did not return valid JSON" in production.

The bug: generate_video_strategy asked for the largest JSON schema in the
codebase (~45 values across five nested objects) with a 4000-token budget on
Gemini 2.5 Flash — a thinking model whose thought tokens are drawn from the
same completion budget. The reply was cut off mid-object, and the truncated
JSON failed the parser in exactly the same way as a model that wrapped its
answer in prose, so the only clue was "did not return valid JSON" and the real
cause — a too-small budget — went unquestioned.

These pin: truncation is detected and named as such, the retry actually grows
the budget, a formatting slip is retried with a stricter instruction, and a
truncation is never reported as a JSON-formatting problem.
"""
import asyncio
import importlib
import json
import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))


class _Response:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status
        self.text = json.dumps(payload)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _Recorder:
    """Stands in for httpx.AsyncClient and records the payloads it is given."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.payloads = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        self.payloads.append(json)
        payload = self.responses[min(len(self.payloads) - 1, len(self.responses) - 1)]
        if isinstance(payload, _Response):
            return payload
        return _Response(payload)


def _completion(content, finish_reason="stop"):
    return {"choices": [{"finish_reason": finish_reason,
                         "message": {"content": content}}]}


def _patch_client(monkeypatch, responses):
    import ai_service
    rec = _Recorder(responses)
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", lambda *a, **k: rec)
    monkeypatch.setattr(ai_service, "OPENROUTER_API_KEY", "test")
    return rec


class TestChatJson:
    def test_a_clean_object_parses_on_the_first_attempt(self, monkeypatch):
        import ai_service
        rec = _patch_client(monkeypatch, [_completion('{"hook_line": "Hi"}')])
        result = _run(ai_service._chat_json("sys", "prompt", "Ctx"))
        assert result == {"hook_line": "Hi"}
        assert len(rec.payloads) == 1, "a good reply must not cost a retry"

    def test_fences_and_trailing_prose_are_tolerated(self, monkeypatch):
        import ai_service
        body = 'Sure!\n```json\n{"a": 1, "b": {"c": 2}}\n```\nHope that helps.'
        _patch_client(monkeypatch, [_completion(body)])
        assert _run(ai_service._chat_json("sys", "prompt", "Ctx")) == {"a": 1, "b": {"c": 2}}

    def test_truncation_raises_truncated_not_a_json_error(self, monkeypatch):
        """
        The distinction that was missing. A cut-off reply is a length problem;
        reporting it as "did not return valid JSON" sends you hunting for a
        formatting bug that does not exist.
        """
        import ai_service
        half = '{"hook_line": "It was always this one tap", "character": {"appearance": "a n'
        # Both attempts truncated: the budget is genuinely too small.
        _patch_client(monkeypatch, [_completion(half, finish_reason="length")])
        with pytest.raises(ai_service.TruncatedResponse) as err:
            _run(ai_service._chat_json("sys", "prompt", "Ctx", max_tokens=8192))
        assert "cut off" in str(err.value)
        assert "valid JSON" not in str(err.value)

    def test_the_retry_actually_grows_the_budget(self, monkeypatch):
        """
        Repeating a truncated request at the same size truncates identically,
        so the retry must differ. This asserts the number, not just the count.
        """
        import ai_service
        half = '{"hook_line": "abc'
        rec = _patch_client(
            monkeypatch, [_completion(half, finish_reason="length")])
        with pytest.raises(ai_service.TruncatedResponse):
            _run(ai_service._chat_json("sys", "prompt", "Ctx", max_tokens=8000))
        assert len(rec.payloads) == 2
        first, second = rec.payloads[0]["max_tokens"], rec.payloads[1]["max_tokens"]
        assert first == 8000
        assert second > first, f"retry budget {second} did not grow from {first}"
        # And the retry also asks for shorter values, since a bigger budget
        # alone is not a fix for an over-long schema.
        assert "under 25 words" in rec.payloads[1]["messages"][1]["content"]

    def test_truncation_recovers_when_the_bigger_budget_is_enough(self, monkeypatch):
        """The happy path for the fix: one retry turns a failure into a result."""
        import ai_service
        half = '{"hook_line": "It was always this one tap", "character": {"appear'
        rec = _patch_client(monkeypatch, [
            _completion(half, finish_reason="length"),
            _completion('{"hook_line": "It was always this one tap"}'),
        ])
        result = _run(ai_service._chat_json("sys", "prompt", "Ctx", max_tokens=8000))
        assert result["hook_line"] == "It was always this one tap"
        assert len(rec.payloads) == 2

    def test_a_prose_refusal_is_named_not_a_json_error(self, monkeypatch):
        """
        "I cannot help with that." has no braces at all — it is a refusal,
        not a formatting slip. Reporting it as "did not return valid JSON"
        used to send everyone hunting for a parser or budget problem while
        the model had simply declined the prompt.
        """
        import ai_service
        rec = _patch_client(monkeypatch, [_completion("I cannot help with that.")])
        with pytest.raises(ai_service.ModelRefusal) as err:
            _run(ai_service._chat_json("sys", "prompt", "Ctx"))
        # Retried once (temperature sometimes works), then named as a refusal.
        assert len(rec.payloads) == 2
        assert "prose" in str(err.value) or "declined" in str(err.value)
        assert "valid JSON" not in str(err.value)
        assert not isinstance(err.value, ai_service.TruncatedResponse)

    def test_malformed_json_with_braces_is_still_a_json_error(self, monkeypatch):
        """
        The counterpart: braces present but unparseable is genuinely a format
        problem, and must keep the JSON error rather than being renamed.
        """
        import ai_service
        rec = _patch_client(monkeypatch, [_completion('{"a": 1,')])
        with pytest.raises(RuntimeError) as err:
            _run(ai_service._chat_json("sys", "prompt", "Ctx", attempts=1))
        assert "valid JSON" in str(err.value)
        assert not isinstance(err.value, ai_service.ModelRefusal)

    def test_a_filtered_reply_names_the_finish_reason(self, monkeypatch):
        import ai_service
        rec = _patch_client(monkeypatch, [
            _completion("I can't help with that topic.", finish_reason="content_filter")])
        with pytest.raises(ai_service.ModelRefusal) as err:
            _run(ai_service._chat_json("sys", "prompt", "Ctx", attempts=1))
        assert "content_filter" in str(err.value)

    def test_literal_newlines_inside_strings_are_salvaged(self, monkeypatch):
        """
        The most common model formatting slip: a raw newline inside a string
        value. strict=False accepts it with zero semantic change, so this
        parses on the first attempt instead of costing a retry.
        """
        import ai_service
        rec = _patch_client(monkeypatch, [_completion('{"a": "line one\nline two"}')])
        assert _run(ai_service._chat_json("sys", "prompt", "Ctx")) == {"a": "line one\nline two"}
        assert len(rec.payloads) == 1

    def test_a_formatting_slip_recovers_on_retry(self, monkeypatch):
        import ai_service
        rec = _patch_client(monkeypatch, [
            _completion("Here you go:\n```json\n{'single': 'quotes'}\n```"),
            _completion('{"ok": true}'),
        ])
        assert _run(ai_service._chat_json("sys", "prompt", "Ctx")) == {"ok": True}
        assert len(rec.payloads) == 2
        assert "ONE complete JSON object" in rec.payloads[1]["messages"][1]["content"]

    def test_no_choices_is_its_own_error(self, monkeypatch):
        import ai_service
        _patch_client(monkeypatch, [{"id": "x"}])
        with pytest.raises(RuntimeError) as err:
            _run(ai_service._chat_json("sys", "prompt", "Ctx"))
        assert "no response" in str(err.value)

    def test_empty_content_names_the_finish_reason(self, monkeypatch):
        import ai_service
        _patch_client(monkeypatch, [
            _completion("", finish_reason="content_filter")])
        with pytest.raises(RuntimeError) as err:
            _run(ai_service._chat_json("sys", "prompt", "Ctx", attempts=1))
        assert "content_filter" in str(err.value)


class TestStrategyBudget:
    def test_strategy_uses_a_budget_that_fits_its_schema(self):
        """
        Guard the number itself. The strategy object is the largest in the
        codebase, and 4000 tokens is what produced the production failure.
        """
        import re
        src = (BACKEND_DIR / "ai_service.py").read_text(encoding="utf-8")
        match = re.search(
            r"raw = await _chat_json\((?:[^)]*?)max_tokens=(\d+)", src, re.S)
        assert match, "generate_video_strategy should route through _chat_json"
        assert int(match.group(1)) >= 8192, (
            f"strategy max_tokens is {match.group(1)}; the schema needs headroom "
            f"for Gemini's thinking tokens on top of ~45 JSON values"
        )

    def test_the_prompt_bounds_value_length(self):
        """
        A budget is a backstop, not the fix. The prompt also has to ask for
        concise values, or every strategy costs a retry.
        """
        src = (BACKEND_DIR / "ai_service.py").read_text(encoding="utf-8")
        assert "Keep EVERY string value under 25 words" in src
        assert "no markdown fence" in src


class TestStrategyEndpointError:
    """The endpoint must name truncation rather than leaking a JSON message."""

    @pytest.fixture(scope="class")
    def api(self):
        tmpdir = importlib.import_module("tempfile").mkdtemp(prefix="tiktok-strategy-err-")
        os.environ["TURSO_DATABASE_URL"] = ""
        os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
        os.environ["CLERK_JWKS_URL"] = ""
        os.environ.pop("VIDEO_MODEL_DEFAULT", None)
        os.environ.pop("VIDEO_MODEL_ALLOWLIST", None)
        if "server" in sys.modules:
            del sys.modules["server"]
        server = importlib.import_module("server")
        server.DB_PATH = Path(tmpdir) / "test.db"
        server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        original = (server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR)
        server.pipeline.VIDEOS_DIR = Path(tmpdir) / "videos"
        server.pipeline.GENERATED_DIR = Path(tmpdir) / "generated"
        server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
        asyncio.run(server.init_db())
        yield server
        server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR = original

    def _project(self, api):
        from models import (
            ApproveAppProfileRequest, BrandProfileCreateRequest,
            CreateStudioProjectRequest,
        )
        profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name="Truncation", app_category="Productivity"), user_id="anonymous"))
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(),
            user_id="anonymous"))
        template = _run(api.list_templates(user_id="anonymous"))["templates"][0]
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"], template_id=template["id"]),
            user_id="anonymous"))
        return project["id"]

    def test_truncation_is_reported_as_a_length_problem(self, api, monkeypatch):
        from fastapi import HTTPException
        from models import GenerateStrategyRequest
        from ai_service import TruncatedResponse

        async def boom(**kwargs):
            raise TruncatedResponse(
                "Video strategy was cut off after 8192 tokens (finish_reason=length) "
                "before the JSON closed"
            )

        monkeypatch.setattr(api, "generate_video_strategy", boom)
        project_id = self._project(api)
        with pytest.raises(HTTPException) as err:
            _run(api.generate_project_strategy(
                project_id=project_id, payload=GenerateStrategyRequest(),
                user_id="anonymous"))
        assert err.value.status_code == 502
        message = str(err.value.detail)
        assert "cut off" in message
        assert "valid JSON" not in message
        assert "length problem" in message

    def test_refusal_is_reported_as_a_refusal(self, api, monkeypatch):
        """
        A model that declines the prompt must not surface as a JSON error:
        the founder would retry a request that fails the same way every
        time, instead of reporting it.
        """
        from fastapi import HTTPException
        from models import GenerateStrategyRequest
        from ai_service import ModelRefusal

        async def boom(**kwargs):
            raise ModelRefusal("Video strategy returned no JSON object")

        monkeypatch.setattr(api, "generate_video_strategy", boom)
        project_id = self._project(api)
        with pytest.raises(HTTPException) as err:
            _run(api.generate_project_strategy(
                project_id=project_id, payload=GenerateStrategyRequest(),
                user_id="anonymous"))
        assert err.value.status_code == 502
        message = str(err.value.detail)
        assert "declined" in message
        assert "valid JSON" not in message

    def test_any_other_failure_still_reports_itself(self, api, monkeypatch):
        from fastapi import HTTPException
        from models import GenerateStrategyRequest

        async def boom(**kwargs):
            raise RuntimeError("Video strategy missing required fields: {'character'}")

        monkeypatch.setattr(api, "generate_video_strategy", boom)
        project_id = self._project(api)
        with pytest.raises(HTTPException) as err:
            _run(api.generate_project_strategy(
                project_id=project_id, payload=GenerateStrategyRequest(),
                user_id="anonymous"))
        assert "missing required fields" in str(err.value.detail)


def _run(coro):
    return asyncio.run(coro)
