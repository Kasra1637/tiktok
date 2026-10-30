"""
Tests for the JSON-call failure modes that produced
"Video strategy did not return valid JSON" in production.

The bug: generate_video_strategy asked for the largest JSON schema in the
codebase (~45 values across five nested objects) with a 4000-token budget on
a thinking model whose thought tokens are drawn from the same completion
budget. The reply was cut off mid-object, and the truncated
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


class _GetRecorder:
    """Stands in for httpx.AsyncClient for the capability lookup (GET only)."""

    def __init__(self, payload, status=200):
        self._payload = payload
        self._status = status
        self.urls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url):
        self.urls.append(url)
        return _Response(self._payload, status=self._status)


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


class TestModelConfiguration:
    """
    The chat slugs are env-overridable so a model swap is a config change, the
    same way VIDEO_MODEL_DEFAULT already works for the video provider.
    """

    def test_a_missing_or_blank_var_falls_back_to_the_shipped_default(self, monkeypatch):
        import ai_service
        monkeypatch.delenv("AI_TEXT_MODEL", raising=False)
        assert ai_service._model_from_env("AI_TEXT_MODEL", "fallback/model") == "fallback/model"
        monkeypatch.setenv("AI_TEXT_MODEL", "   ")
        assert ai_service._model_from_env("AI_TEXT_MODEL", "fallback/model") == "fallback/model"

    def test_a_set_var_wins_over_the_default(self, monkeypatch):
        import ai_service
        monkeypatch.setenv("AI_VISION_MODEL", "vendor/other-model")
        assert ai_service._model_from_env("AI_VISION_MODEL", "fallback/model") == "vendor/other-model"


class TestTemperatureIsDataDriven:
    """
    Whether a model accepts a `temperature` field is read from OpenRouter's
    per-endpoint supported_parameters rather than guessed from the model family,
    so pointing the service at a new model needs no code change and no
    discovery-by-400. The prefix list is only the offline fallback.
    """

    def test_the_declaration_beats_the_offline_fallback(self, monkeypatch):
        import ai_service
        monkeypatch.setattr(ai_service, "_TEMPERATURE_SUPPORT", {})
        # A family the fallback omits, declared as accepting it.
        monkeypatch.setitem(
            ai_service._TEMPERATURE_SUPPORT, "anthropic/claude-haiku-5.5", True)
        assert ai_service._temperature_param(
            "anthropic/claude-haiku-5.5", 0.4) == {"temperature": 0.4}
        # A family the fallback sends to, declared as refusing it.
        monkeypatch.setitem(ai_service._TEMPERATURE_SUPPORT, "z-ai/glm-5.3-flash", False)
        assert ai_service._temperature_param("z-ai/glm-5.3-flash", 0.4) == {}

    def test_an_unknown_model_falls_back_to_the_prefix_list(self, monkeypatch):
        import ai_service
        monkeypatch.setattr(ai_service, "_TEMPERATURE_SUPPORT", {})
        assert ai_service.temperature_support("anthropic/claude-haiku-5.5") is None
        assert ai_service._temperature_param("anthropic/claude-haiku-5.5", 0.4) == {}
        assert ai_service._temperature_param("z-ai/glm-5.3-flash", 0.4) == {"temperature": 0.4}

    def test_the_lookup_reads_the_declared_parameters(self, monkeypatch):
        import ai_service
        monkeypatch.setattr(ai_service, "_TEMPERATURE_SUPPORT", {})
        rec = _GetRecorder({"data": {"endpoints": [
            {"supported_parameters": ["reasoning", "temperature"]},
            {"supported_parameters": ["reasoning", "temperature"]},
        ]}})
        monkeypatch.setattr(ai_service.httpx, "AsyncClient", lambda *a, **k: rec)
        out = _run(ai_service.refresh_temperature_support(["vendor/takes-temp"]))
        assert out["vendor/takes-temp"] is True
        assert rec.urls == [
            "https://openrouter.ai/api/v1/models/vendor/takes-temp/endpoints"]

    def test_one_endpoint_without_it_is_enough_to_omit(self, monkeypatch):
        """
        OpenRouter routes to one endpoint, so a partial listing is a coin flip.
        The conservative reading is the one that cannot 400.
        """
        import ai_service
        monkeypatch.setattr(ai_service, "_TEMPERATURE_SUPPORT", {})
        rec = _GetRecorder({"data": {"endpoints": [
            {"supported_parameters": ["temperature"]},
            {"supported_parameters": ["reasoning"]},
        ]}})
        monkeypatch.setattr(ai_service.httpx, "AsyncClient", lambda *a, **k: rec)
        out = _run(ai_service.refresh_temperature_support(["vendor/mixed"]))
        assert out["vendor/mixed"] is False

    def test_a_failed_lookup_keeps_the_fallback(self, monkeypatch):
        import ai_service
        monkeypatch.setattr(ai_service, "_TEMPERATURE_SUPPORT", {})
        rec = _GetRecorder({"error": "nope"}, status=500)
        monkeypatch.setattr(ai_service.httpx, "AsyncClient", lambda *a, **k: rec)
        out = _run(ai_service.refresh_temperature_support(["vendor/down"]))
        assert "vendor/down" not in out
        # ...and the offline fallback still answers.
        assert ai_service._temperature_param("vendor/down", 0.4) == {"temperature": 0.4}

    def test_a_lookup_that_raises_is_swallowed(self, monkeypatch):
        """The boot path must never be taken down by this lookup."""
        import ai_service
        monkeypatch.setattr(ai_service, "_TEMPERATURE_SUPPORT", {})

        def boom(*a, **k):
            raise RuntimeError("network down")

        monkeypatch.setattr(ai_service.httpx, "AsyncClient", boom)
        out = _run(ai_service.refresh_temperature_support(["vendor/boom"]))
        assert "vendor/boom" not in out


class TestChatModelRequestShape:
    """
    Claude Haiku 5.5 replaces GPT-5 Mini on every chat flow. The consequences
    that travel with the family are pinned here rather than re-discovered as
    production 400s:

    - temperature is sent ONLY where the endpoint declares it. Haiku 5.5
      declares none on any of its endpoints, so the field is omitted for it and
      nothing is spent finding that out; _post_chat's retry stays as the net
      under both the declared data and the offline fallback;
    - max_tokens stays (OpenRouter maps it), and thinking tokens are billed
      against the same budget, which the truncation retry already covers.
    """

    def test_chat_models_point_at_haiku_5_5(self):
        import ai_service
        assert ai_service.TEXT_MODEL == "anthropic/claude-haiku-5.5"
        assert ai_service.VISION_MODEL == "anthropic/claude-haiku-5.5"

    def test_the_shipped_default_gets_no_temperature(self, monkeypatch):
        """
        Claude Haiku 5.5 declares no temperature on any of its endpoints, so the
        field is omitted and nothing is spent discovering that by 400.
        """
        import ai_service
        rec = _patch_client(monkeypatch, [_completion('{"a": 1}')])
        assert _run(ai_service._chat_json("sys", "prompt", "Ctx")) == {"a": 1}
        assert rec.payloads[0]["model"] == "anthropic/claude-haiku-5.5"
        assert "temperature" not in rec.payloads[0]

    def test_an_explicit_temperature_reaches_a_model_that_takes_it(self, monkeypatch):
        import ai_service
        monkeypatch.setitem(
            ai_service._TEMPERATURE_SUPPORT, "anthropic/claude-haiku-5.5", True)
        rec = _patch_client(monkeypatch, [_completion('{"a": 1}')])
        assert _run(ai_service._chat_json("sys", "prompt", "Ctx", temperature=0.5)) == {"a": 1}
        assert rec.payloads[0]["temperature"] == 0.5

    def test_chat_temperature_is_the_documented_default(self):
        import ai_service
        assert ai_service.CHAT_TEMPERATURE == 0.4

    def test_the_offline_fallback_omits_for_the_known_families(self, monkeypatch):
        import ai_service
        monkeypatch.setattr(ai_service, "_TEMPERATURE_SUPPORT", {})
        for slug in ("openai/gpt-5-mini", "openai/gpt-6-sol", "o3-mini",
                     "anthropic/claude-haiku-5.5", "anthropic/claude-opus-5.5"):
            assert ai_service._temperature_param(slug, 0.4) == {}, slug
        assert ai_service._temperature_param(
            "z-ai/glm-5.3-flash", 0.4) == {"temperature": 0.4}

    def test_a_refused_temperature_is_retried_without_it(self, monkeypatch):
        """
        The net under both the declared data and the offline fallback. If the
        provider refuses the field, the identical request goes again without it,
        so a wrong answer costs the field and never the call.
        """
        import ai_service
        monkeypatch.setitem(
            ai_service._TEMPERATURE_SUPPORT, "anthropic/claude-haiku-5.5", True)
        refusal = _Response(
            {"error": {"message": "Unsupported value: temperature"}}, status=400)
        rec = _patch_client(monkeypatch, [refusal, _completion('{"a": 1}')])
        assert _run(ai_service._chat_json("sys", "prompt", "Ctx", temperature=0.4)) == {"a": 1}
        assert len(rec.payloads) == 2
        assert rec.payloads[0]["temperature"] == 0.4
        assert "temperature" not in rec.payloads[1]
        assert rec.payloads[1]["model"] == rec.payloads[0]["model"]

    def test_an_unrelated_400_is_not_retried(self, monkeypatch):
        """Only a refusal that NAMES temperature is worth a second request."""
        import ai_service
        refusal = _Response({"error": {"message": "bad request"}}, status=400)
        rec = _patch_client(monkeypatch, [refusal])
        with pytest.raises(RuntimeError):
            _run(ai_service._chat_json("sys", "prompt", "Ctx", temperature=0.4, attempts=1))
        assert len(rec.payloads) == 1

    def test_no_response_format_without_a_schema(self, monkeypatch):
        import ai_service
        rec = _patch_client(monkeypatch, [_completion('{"a": 1}')])
        _run(ai_service._chat_json("sys", "prompt", "Ctx"))
        assert "response_format" not in rec.payloads[0]

    def test_response_format_carries_a_strict_schema(self, monkeypatch):
        import ai_service
        schema = {
            "type": "object",
            "properties": {"a": {"type": "string"}},
            "required": ["a"],
            "additionalProperties": False,
        }
        rec = _patch_client(monkeypatch, [_completion('{"a": "1"}')])
        _run(ai_service._chat_json("sys", "prompt", "Ctx", json_schema=schema))
        rf = rec.payloads[0]["response_format"]
        assert rf["type"] == "json_schema"
        assert rf["json_schema"]["strict"] is True
        assert rf["json_schema"]["schema"] == schema
        assert rf["json_schema"]["name"] == "ctx"

    def test_every_shipped_schema_is_strict(self):
        """
        Strict mode rejects any object whose properties are not all required
        with nothing else admitted. A helper walks every shipped schema the
        way the provider validates it, so a loose object cannot slip in with
        a new field and fail every call at request time.
        """
        import ai_service

        def check(node, path):
            if isinstance(node, dict) and node.get("type") == "object":
                props = node.get("properties", {})
                assert sorted(node.get("required", [])) == sorted(props), (
                    f"{path}: required must list every property"
                )
                assert node.get("additionalProperties") is False, (
                    f"{path}: additionalProperties must be false"
                )
                for key, sub in props.items():
                    check(sub, f"{path}.{key}")
            elif isinstance(node, dict) and node.get("type") == "array":
                check(node.get("items", {}), f"{path}[]")

        for name in (
            "APP_PROFILE_JSON_SCHEMA",
            "ANGLES_JSON_SCHEMA", "PLAN_JSON_SCHEMA", "STRATEGY_JSON_SCHEMA",
        ):
            check(getattr(ai_service, name), name)

    def test_direct_flows_send_response_format(self, monkeypatch):
        """
        The flows that post httpx directly (not through _chat_json) must
        still carry the envelope: app research, angles, plan.
        """
        import ai_service

        profile_keys = ai_service.REQUIRED_APP_PROFILE_KEYS
        list_keys = set(ai_service.APP_PROFILE_LIST_KEYS) | {
            "outcome_statements", "viewer_objections"}
        profile = {
            k: ([] if k in list_keys else "") for k in profile_keys}
        angle = {
            "kind": "problem_solution", "label": "L",
            "target_audience": "a", "user_problem": "p",
            "hook_promise": "h", "app_feature": "f",
            "desired_emotion": "e", "claims_to_respect": [],
        }
        plan = {
            "hook_line": "I couldn't get started.", "script": "One prompt helped me start writing.",
            "beat_timeline": [
                {"start": 0, "end": 3, "label": "hook", "text": "t"},
                {"start": 3, "end": 20, "label": "middle", "text": "t"},
            ],
            "visual_direction": "v", "demo_brief": "d",
            "voice_direction": "vd", "sound_direction": "sd",
            "claims_used": [],
        }
        rec = _patch_client(monkeypatch, [
            _completion(json.dumps(profile)),
            _completion(json.dumps({"angles": [angle]})),
            _completion(json.dumps(plan)),
        ])
        _run(ai_service.analyze_app_profile({"app_store": "text"}))
        _run(ai_service.generate_content_angles({"brand_name": "B"}))
        _run(ai_service.generate_creative_plan(
            profile={"brand_name": "B"}, template={"name": "T"}))
        assert len(rec.payloads) == 3
        for payload in rec.payloads:
            assert payload["response_format"]["type"] == "json_schema"
            assert "temperature" not in payload


class TestAngleFeedbackPromptWiring:
    ANGLE = {
        "kind": "problem_solution", "label": "Too many lists",
        "target_audience": "Busy professionals", "user_problem": "Nothing gets finished",
        "hook_promise": "Finish one thing", "app_feature": "Task timer",
        "desired_emotion": "Relief", "claims_to_respect": [],
    }

    def _capture(self, monkeypatch):
        import ai_service
        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return [dict(self.ANGLE)]

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        return captured

    def test_verdicts_reach_the_angle_prompt(self, monkeypatch):
        import ai_service
        import feedback as feedback_mod
        captured = self._capture(monkeypatch)
        summary = feedback_mod.summarize_angle_feedback([
            {"kind": "problem_solution", "objective": "demonstrate_feature",
             "event": "thumb_up", "step": "goal"},
        ])
        _run(ai_service.generate_content_angles(
            {"brand_name": "Taskly"}, angle_feedback=summary))
        assert "problem_solution (1 win(s), 0 flop(s))" in captured["prompt"]

    def test_no_record_reads_as_no_evidence_not_silence(self, monkeypatch):
        import ai_service
        import feedback as feedback_mod
        captured = self._capture(monkeypatch)
        _run(ai_service.generate_content_angles(
            {"brand_name": "Taskly"},
            angle_feedback=feedback_mod.summarize_angle_feedback([])))
        assert "PAST VERDICTS: none recorded" in captured["prompt"]

    def test_omitted_feedback_leaves_the_prompt_untouched(self, monkeypatch):
        import ai_service
        captured = self._capture(monkeypatch)
        _run(ai_service.generate_content_angles({"brand_name": "Taskly"}))
        assert "PAST VERDICTS" not in captured["prompt"]

    def test_generation_caps_at_six_angles(self, monkeypatch):
        """The audience step shows exactly six suggestions: the prompt asks
        for exactly six and the cap holds even when the model overshoots."""
        import ai_service

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            assert "exactly 6" in prompt
            return [dict(self.ANGLE) for _ in range(9)]

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        out = _run(ai_service.generate_content_angles({"brand_name": "Taskly"}))
        assert len(out) == 6


class TestAnglePromptGrounding:
    """
    Angles were the thinnest prompt in the studio. The profile already carries
    the moment the app is reached for, the reason a viewer would refuse it, and
    what must never be shown — and none of it reached generation, so the model
    generalised from a feature list and produced copy that read like a category
    description instead of something filmable. These pin the material, the
    craft bar that turns it into a scene, and the one field that stays out.
    """

    ANGLE = {
        "kind": "problem_solution", "label": "Log the shift",
        "target_audience": "Shift workers", "user_problem": "Timesheets go missing",
        "hook_promise": "One tap at the door", "app_feature": "Shift log",
        "desired_emotion": "Relief", "claims_to_respect": [],
    }

    PROFILE = {
        "brand_name": "Shiftly",
        "app_category": "scheduling",
        "core_features": ["One-tap shift log"],
        "problems_solved": ["Paper timesheets go missing"],
        "target_audience": "Shift workers",
        "usage_moments": ["End of a night shift", "Handover at 7am"],
        "viewer_objections": [
            {"objection": "Another app to keep updated",
             "what_they_do_now": "Screenshots of the rota",
             "honest_answer": "One tap logs it"},
        ],
        "must_not_show": ["managers approving shifts"],
        # Recorded decision: the demo the founder films later, never a
        # generation input. Passed here so its absence is an assertion.
        "proof_moment": "One tap and the shift is on the log",
    }

    def _capture(self, monkeypatch):
        import ai_service
        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            captured["kwargs"] = kwargs
            return [dict(self.ANGLE)]

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        return captured

    def test_the_usage_moment_reaches_the_prompt(self, monkeypatch):
        import ai_service
        captured = self._capture(monkeypatch)
        _run(ai_service.generate_content_angles(dict(self.PROFILE)))
        assert "End of a night shift" in captured["prompt"]
        assert "Handover at 7am" in captured["prompt"]

    def test_the_objection_reaches_the_prompt(self, monkeypatch):
        import ai_service
        captured = self._capture(monkeypatch)
        _run(ai_service.generate_content_angles(dict(self.PROFILE)))
        assert "Another app to keep updated" in captured["prompt"]
        assert "Screenshots of the rota" in captured["prompt"]

    def test_must_not_show_reaches_the_prompt(self, monkeypatch):
        import ai_service
        captured = self._capture(monkeypatch)
        _run(ai_service.generate_content_angles(dict(self.PROFILE)))
        assert "managers approving shifts" in captured["prompt"]

    def test_proof_moment_stays_out(self, monkeypatch):
        """
        proof_moment is the product demo the founder records separately. It was
        excluded from the strategy prompt because supplying it was the route by
        which "show this happening" reached a prompt that may not show the app.
        The same rule has to hold now that angles get the other rich fields.
        """
        import ai_service
        captured = self._capture(monkeypatch)
        _run(ai_service.generate_content_angles(dict(self.PROFILE)))
        assert '\"proof_moment\"' not in captured["prompt"]
        assert "One tap and the shift is on the log" not in captured["prompt"]

    def test_the_craft_bar_is_stated(self, monkeypatch):
        """Rich input alone still produced benefit-speak. These are the rules
        that turn a field into a scene, and the filler they exist to stop."""
        import ai_service
        captured = self._capture(monkeypatch)
        _run(ai_service.generate_content_angles(dict(self.PROFILE)))
        prompt = captured["prompt"]
        assert "a camera can SEE" in prompt
        assert "differ in ARGUMENT" in prompt
        for filler in ("seamless", "effortless", "game-changing", "unlock"):
            assert filler in prompt, filler

    def test_angles_request_the_dedicated_model(self, monkeypatch):
        import ai_service
        captured = self._capture(monkeypatch)
        monkeypatch.setattr(ai_service, "ANGLE_MODEL", "vendor/strong-model")
        _run(ai_service.generate_content_angles(dict(self.PROFILE)))
        assert captured["kwargs"]["model"] == "vendor/strong-model"

    def test_the_angle_model_falls_back_to_the_text_model(self):
        """Unset is the shipped behavior: same model as every other text flow.
        A stronger default is a paid product decision, not a code change."""
        import ai_service
        override = (os.environ.get("AI_ANGLE_MODEL") or "").strip()
        assert ai_service.ANGLE_MODEL == (override or ai_service.TEXT_MODEL)

    def test_chat_json_sends_the_model_it_is_given(self, monkeypatch):
        import ai_service
        rec = _patch_client(monkeypatch, [_completion('{"ok": true}')])
        _run(ai_service._chat_json("sys", "prompt", "Ctx", model="vendor/strong-model"))
        assert rec.payloads[0]["model"] == "vendor/strong-model"

    def test_chat_json_still_defaults_to_the_text_model(self, monkeypatch):
        import ai_service
        rec = _patch_client(monkeypatch, [_completion('{"ok": true}')])
        _run(ai_service._chat_json("sys", "prompt", "Ctx"))
        assert rec.payloads[0]["model"] == ai_service.TEXT_MODEL


class TestAngleGoalPromptWiring:
    @pytest.mark.parametrize("flow", ["plan", "strategy"])
    def test_an_override_advances_the_goal_without_replacing_the_angle(self, monkeypatch, flow):
        import ai_service

        captured = {}
        plan = {
            "hook_line": "Too many lists?", "script": "Too many lists? Start with one task.",
            "beat_timeline": [{"start": 0, "end": 3, "label": "hook", "text": "Too many lists?"},
                              {"start": 3, "end": 15, "label": "middle", "text": "Start with one task."}],
            "visual_direction": "Desk", "demo_brief": "Record the timer afterwards.",
            "voice_direction": "Calm", "sound_direction": "Room tone", "claims_used": [],
        }
        strategy = {key: "x" for key in ai_service.REQUIRED_STRATEGY_KEYS}
        strategy.update({"scene": {}, "performance": {}, "segments": [],
                         "messaging_pillars": [], "emotional_triggers": []})

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return plan if flow == "plan" else strategy

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        args = {
            "profile": {"id": "profile-1", "brand_name": "Taskly", "core_features": ["Task timer"]},
            "template": {"id": "template-1", "name": "Name the misdiagnosis", "hook_seconds": 3},
            "angle": {"id": "angle-1", "kind": "problem_solution", "label": "Too many lists",
                      "user_problem": "Nothing gets finished", "target_audience": "Busy professionals"},
            "objective": "demonstrate_feature",
        }
        if flow == "plan":
            _run(ai_service.generate_creative_plan(**args, duration_seconds=15))
        else:
            result = _run(ai_service.generate_video_strategy(**args, hook_seconds=3, total_duration=15))
            assert result["objective"] == "demonstrate_feature"
            assert result["content_angle_id"] == "angle-1"

        prompt = captured["prompt"]
        for required in ("ANGLE + GOAL RULE", "Busy professionals", "Nothing gets finished",
                         "demonstrate_feature", "founder's later demo/CTA"):
            assert required in prompt
        assert "NEVER" in prompt and "product demonstration" in prompt


class TestTruncatedResearchRetriesDoubled:
    """
    Production failure, 2026-10-10: app-profile research at max_tokens=4000
    truncated mid-object under GPT-5 Mini (reasoning tokens share the
    budget) and surfaced as "App profile did not return valid JSON" — a
    formatting error for what was a length problem, with no retry. These
    flows now route through _chat_json, so truncation is detected, retried
    doubled, and named as truncation when it persists.
    """

    def _full_profile(self):
        import ai_service
        list_keys = set(ai_service.APP_PROFILE_LIST_KEYS) | {
            "outcome_statements", "viewer_objections"}
        profile = {
            k: ([] if k in list_keys else "x")
            for k in ai_service.REQUIRED_APP_PROFILE_KEYS}
        profile["brand_name"] = "Vocolens"
        return profile

    def test_truncated_research_recovers_on_the_doubled_retry(self, monkeypatch):
        import ai_service
        half = '{"brand_name": "Vocolens", "brand_description": "Voice-first AI journal'
        rec = _patch_client(monkeypatch, [
            _completion(half, finish_reason="length"),
            _completion(json.dumps(self._full_profile())),
        ])
        result = _run(ai_service.analyze_app_profile({"website": "text"}))
        assert result["brand_name"] == "Vocolens"
        assert len(rec.payloads) == 2
        assert rec.payloads[0]["max_tokens"] == 8000
        assert rec.payloads[1]["max_tokens"] == 16000
        for payload in rec.payloads:
            assert payload["response_format"]["type"] == "json_schema"

    def test_persistently_truncated_research_names_truncation(self, monkeypatch):
        import ai_service
        half = '{"brand_name": "Vocolens", "brand_description": "Voice-first AI journal'
        _patch_client(monkeypatch, [_completion(half, finish_reason="length")])
        with pytest.raises(ai_service.TruncatedResponse) as err:
            _run(ai_service.analyze_app_profile({"website": "text"}))
        assert "cut off" in str(err.value)
        assert "valid JSON" not in str(err.value)


class TestResearchedDescriptionIsOneLine:
    """
    The App Profile description is the page subtitle, read at a glance.

    The research schema used to ask for 1-3 sentences, so a 196-character
    three-sentence blurb rendered as three lines under the page title while the
    editor labelled the same field "a one-line description". The schema now asks
    for one sentence of 80 characters or fewer, and the reply is clipped to that
    budget rather than trusted, because this model has already ignored the
    length instruction once.
    """

    LONG = (
        "Vocolens is an AI voice journal and mood tracker. Users speak their "
        "thoughts instead of typing, and the app transcribes them, analyzes "
        "emotions, and offers personalized reflections and mood trends over time."
    )

    def _profile(self, description):
        import ai_service
        list_keys = set(ai_service.APP_PROFILE_LIST_KEYS) | {
            "outcome_statements", "viewer_objections"}
        profile = {
            k: ([] if k in list_keys else "x")
            for k in ai_service.REQUIRED_APP_PROFILE_KEYS}
        profile["brand_name"] = "Vocolens"
        profile["brand_description"] = description
        return profile

    def test_the_prompt_asks_for_one_short_sentence(self, monkeypatch):
        import ai_service
        rec = _patch_client(monkeypatch, [_completion(json.dumps(self._profile("x")))])
        _run(ai_service.analyze_app_profile({"website": "text"}))
        prompt = rec.payloads[0]["messages"][1]["content"]
        assert "one sentence, 80 characters or fewer" in prompt
        assert "1-3 sentence" not in prompt

    def test_an_overshooting_reply_is_cut_to_the_first_sentence(self, monkeypatch):
        import ai_service
        _patch_client(monkeypatch, [_completion(json.dumps(self._profile(self.LONG)))])
        result = _run(ai_service.analyze_app_profile({"website": "text"}))
        description = result["brand_description"]
        assert len(description) <= ai_service.APP_DESCRIPTION_MAX_CHARS
        # The whole point: the app is still identifiable, and the restatement
        # that used to run to three lines is gone.
        assert description.startswith("Vocolens is an AI voice journal and mood tracker.")
        assert "transcribes" not in description
        assert description.endswith(".")

    def test_a_long_single_sentence_ends_on_a_word_boundary(self):
        import ai_service
        source = (
            "A shared household list that replaces the eleven separate chat "
            "threads every family ends up maintaining across the week."
        )
        clipped = ai_service.clip_app_description(source)
        assert len(clipped) <= ai_service.APP_DESCRIPTION_MAX_CHARS
        assert clipped.endswith("…")
        assert not clipped.endswith(" …")
        # No half words: the last visible token is a whole word of the source,
        # so the cut fell on a space rather than inside "maintaining".
        last_word = clipped[:-1].rstrip().split()[-1]
        assert f"{last_word} " in source

    def test_a_description_inside_the_budget_is_untouched(self):
        import ai_service
        short = "One shared list for the whole household."
        assert ai_service.clip_app_description(short) == short


class TestScriptVoiceAndTarget:
    """
    The script generation rules: a natural-delivery target rather than a hard
    model ceiling, no padding to reach it, a customer's voice rather than the
    founder's, and a rewrite-to-fit before the video model is called.
    """

    def test_the_spoken_pace_is_150_characters_over_10_seconds(self):
        import ai_service
        assert ai_service.SPOKEN_CHARS_PER_SECOND == 15
        assert ai_service.spoken_budget(10) == 150

    def test_the_prompts_write_from_the_customer_perspective(self):
        src = (BACKEND_DIR / "ai_service.py").read_text(encoding="utf-8")
        assert "CUSTOMER PERSPECTIVE" in src
        assert "satisfied customer" in src
        assert "never the app's founder, owner, developer or marketer" in src

    def test_the_budget_is_a_natural_delivery_target_not_a_hard_ceiling(self):
        src = (BACKEND_DIR / "ai_service.py").read_text(encoding="utf-8")
        assert "natural delivery, not an arbitrary maximum" in src
        assert "NEVER pad with filler words" in src

    def test_an_over_length_script_is_rewritten_by_the_one_rule(self):
        """One arithmetic does the rewriting, not a second one beside it.

        `partition_spoken_words` sizes both spoken lines: the plan arrival clamp
        calls it before the row is written, and the render path calls it (as
        `repair_spoken_story`) before the prompt is built. A separate condensing
        helper existed for a moment and cut the script's TAIL, which is where
        the payoff sentence lives; it is gone.
        """
        src = (BACKEND_DIR / "ai_service.py").read_text(encoding="utf-8")
        assert "def partition_spoken_words" in src
        assert "def repair_spoken_story" in src
        assert "condense_script_to_target" not in src
        server_src = (BACKEND_DIR / "server.py").read_text(encoding="utf-8")
        assert "partition_spoken_words(" in server_src
        assert "repair_spoken_story(" in server_src


class TestCreativePlanBudget:
    """
    Production failure, 2026-10-13: the creative plan at max_tokens=3500
    truncated mid-object under GPT-5 Mini (reasoning tokens share the
    budget) on both the first attempt and the doubled retry, surfacing as
    "AI plan generation failed ... cut off after 7000 tokens". Same fix as
    the research and strategy budgets before it: start with headroom.
    """

    def test_plan_uses_a_budget_that_fits_its_schema(self):
        """Guard the number itself, scoped to this caller."""
        import re
        src = (BACKEND_DIR / "ai_service.py").read_text(encoding="utf-8")
        match = re.search(
            r"async def generate_creative_plan\(.*?max_tokens=(\d+)", src, re.S)
        assert match, "generate_creative_plan should route through _chat_json"
        assert int(match.group(1)) >= 8000, (
            f"plan max_tokens is {match.group(1)}; the schema needs headroom "
            f"for thinking tokens on top of its paragraph values"
        )

    def test_truncated_plan_recovers_on_the_doubled_retry(self, monkeypatch):
        """The user-visible failure becomes a result: one retry is enough."""
        import ai_service
        plan = {
            "hook_line": "I couldn't name what I was feeling.",
            "script": ("The suggestions helped me find the words. "
                       "I understood myself better after writing the entry."),
            "beat_timeline": [
                {"start": 0, "end": 3, "label": "hook",
                 "text": "I couldn't name what I was feeling."},
                {"start": 3, "end": 15, "label": "middle", "text": "script"},
            ],
            "visual_direction": "A person reflecting at their desk.",
            "demo_brief": "Record the emotion suggestions.",
            "voice_direction": "Conversational.",
            "sound_direction": "Voice only.",
            "claims_used": [],
        }
        half = '{"hook_line": "I couldn\'t name what I was feeling.', \
            '"script": "The sugg'
        rec = _patch_client(monkeypatch, [
            _completion(half, finish_reason="length"),
            _completion(json.dumps(plan)),
        ])
        result = _run(ai_service.generate_creative_plan(
            profile={}, template={"hook_seconds": 3}, duration_seconds=15,
        ))
        assert result["hook_line"] == plan["hook_line"]
        assert result["script"] == plan["script"]
        assert [p["max_tokens"] for p in rec.payloads] == [8000, 16000]


class TestStrategyBudget:
    def test_strategy_requests_selfie_orbit_and_visible_final_phone(self, monkeypatch):
        import ai_service

        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [
                    {"index": 0, "role": "hook", "seconds": 3,
                     "goal": "g", "script": "s", "action": "a"},
                    {"index": 1, "role": "middle", "seconds": 17,
                     "goal": "g", "script": "s", "action": "a"},
                ],
            }

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        asyncio.run(ai_service.generate_video_strategy(
            profile={"brand_name": "Test"},
            template={"name": "T", "hook_seconds": 3},
            hook_seconds=3,
        ))
        prompt = captured["prompt"]
        from generation_planning import SELFIE_STARTING_SHOT
        assert SELFIE_STARTING_SHOT in prompt
        assert "1.1 metres" not in prompt
        assert '"direction": "left or right"' in prompt
        assert "when the story begins" in prompt.lower()
        assert "same distance from the face" in prompt
        assert "Do not push in, pull back, or zoom" in prompt
        assert '"at":' not in prompt
        assert "Final 1-2s" in prompt
        assert "raise the phone into view" in prompt
        assert "back to camera" in prompt
        assert "whole phone" in prompt
        assert "uncropped" in prompt
        assert "through the last frame" in prompt
        assert "clear margins" in prompt
        assert "never hidden" in prompt
        assert "screen to her" in prompt
        assert "eyes on it" in prompt
        assert "never glancing away" in prompt
        assert "excited" in prompt
        assert "about a metre away (loose hint)" in prompt
        assert "do not show a screen" in prompt
        assert "NEVER write a call to action" in prompt

    def test_camera_beat_keeps_only_direction_and_a_short_gesture(self):
        import ai_service

        strategy = ai_service.normalize_strategy({
            "camera_beat": {"at": 99, "direction": " LEFT ",
                            "gesture": "a small puzzled head tilt", "arc": 0.09},
        })
        assert strategy["camera_beat"] == {
            "direction": "left", "gesture": "a small puzzled head tilt",
        }
        assert set(ai_service.STRATEGY_CAMERA_BEAT_JSON_SCHEMA["properties"]) == {"direction", "gesture"}
        assert ai_service.STRATEGY_CAMERA_BEAT_JSON_SCHEMA["properties"]["direction"]["enum"] == ["left", "right"]

    def test_camera_gesture_is_short_without_splitting_a_word(self):
        import ai_service

        gesture = ai_service.normalize_strategy({
            "camera_beat": {"direction": "right", "gesture": "a slight head tilt " * 20},
        })["camera_beat"]["gesture"]
        assert len(gesture) <= 90
        assert ("a slight head tilt " * 20).startswith(gesture)
        assert not gesture.endswith("ti")

    @pytest.mark.parametrize("direction", ["left", "right"])
    def test_normalization_preserves_each_orbit_direction(self, direction):
        import ai_service

        beat = ai_service.normalize_strategy({"camera_beat": {
            "direction": direction, "gesture": "a small relieved smile",
        }})["camera_beat"]
        assert beat == {"direction": direction, "gesture": "a small relieved smile"}

    def test_invalid_orbit_direction_names_the_next_step(self):
        import ai_service

        with pytest.raises(ValueError, match="regenerate the strategy"):
            ai_service.normalize_strategy({"camera_beat": {
                "direction": "up", "gesture": "a small relieved smile",
            }})

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
            f"for thinking tokens on top of ~45 JSON values"
        )

    def test_the_prompt_bounds_value_length(self):
        """
        A budget is a backstop, not the fix. The prompt also has to ask for
        concise values, or every strategy costs a retry.

        The opening's physical performance is the one deliberate exemption: it is
        written as ordered timed beats, and a 25-word cap would cut it back to
        the generic gesture this change exists to replace.
        """
        src = (BACKEND_DIR / "ai_service.py").read_text(encoding="utf-8")
        assert "Keep every string value under 25 words" in src
        assert "no markdown fence" in src
        assert "may run to about 45 words" in src

    def test_the_prompt_demands_a_physical_pattern_interrupt_opening(self, monkeypatch):
        """
        The render cannot invent an opening: it films the beats the strategy
        writes. So the strategy prompt has to ask for them by body part, timed,
        with the expression treated as an action rather than as a description of
        the face, which the founder's photograph owns.
        """
        import ai_service

        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [{"index": 0, "role": "hook", "seconds": 3,
                              "goal": "g", "script": "s", "action": "a"},
                             {"index": 1, "role": "middle", "seconds": 17,
                              "goal": "g", "script": "s", "action": "a"}],
            }

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        asyncio.run(ai_service.generate_video_strategy(
            profile={
                "brand_name": "ShiftLog",
                "brand_description": "Shift logging for healthcare workers.",
                "app_category": "Productivity",
                "usage_moments": ["the end of a night shift"],
            },
            template={"name": "T", "hook_seconds": 3},
            hook_seconds=3,
        ))
        prompt = captured["prompt"]

        assert "PATTERN INTERRUPT" in prompt
        for requirement in (
            "first frame must already be moving",
            "first half-second",
            "Never a neutral pose",
            "escalate",
            "posture and shoulders",
            "brows",
            "aimed at the lens",
            "own situation",
            "only the middle closes",
        ):
            assert requirement in prompt, f"opening rule missing: {requirement}"
        # The appearance prohibition still governs: expression is an action, and
        # the photograph is the only authority on who the person is.
        assert "Say what the face does, never what the face is" in prompt
        assert "may run to about 45 words" in prompt

    def test_the_prompt_frames_the_pitch_as_outcomes_not_features(self, monkeypatch):
        """
        The middle earns the download by describing what changes for the
        viewer, not what the app contains. The prompt has to demand the
        translation explicitly -- "focus on benefits" alone kept the feature
        list and appended adjectives -- and it has to scope the outcome
        language to the mechanism and payoff moments, never the hook.
        """
        import ai_service

        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [{"index": 0, "role": "hook", "seconds": 3,
                              "goal": "g", "script": "s", "action": "a"},
                             {"index": 1, "role": "middle", "seconds": 17,
                              "goal": "g", "script": "s", "action": "a"}],
            }

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        asyncio.run(ai_service.generate_video_strategy(
            profile={
                "brand_name": "Sleeply",
                "brand_description": "A sleep app.",
                "app_category": "Health & Fitness",
                "core_features": ["sleep timer"],
                "desired_outcomes": ["Falling asleep faster"],
                "outcome_statements": [{
                    "outcome": "fall asleep without checking your phone",
                    "who_feels_it": "night-time scrollers",
                    "from_feature": "sleep timer",
                    "how_it_helps": "the wind-down starts itself",
                }],
            },
            template={"name": "T", "hook_seconds": 3},
            hook_seconds=3,
        ))
        prompt = captured["prompt"]

        for requirement in (
            # The translate step, with the worked example.
            "Translate every feature",
            "helps you fall asleep",
            "without checking your phone",
            # The two pitch moments, in order, scoped to the middle.
            "MECHANISM moment",
            "PAYOFF moment",
            "the hook has neither",
            "The hook stays attention-only",
            # Source precedence: linked statements first, derivation last.
            "outcome_statements first",
            "Never invent an outcome",
            # Benefits, not promises: the existing guarantee rule governs.
            "Benefits, not promises",
        ):
            assert requirement in prompt, f"pitch rule missing: {requirement}"
        # The schema asks for the moments, so the model must write them back.
        assert '"mechanism_beat"' in prompt
        assert '"payoff_beat"' in prompt
        # primary_feature stays the feature: it grounds the video, it does
        # not pitch it.
        assert '"primary_feature": "the ONE feature this video shows' in prompt

    def test_the_strategy_schema_defaults_to_energetic_delivery(self, monkeypatch):
        """
        Delivery has no numeric knob on any provider — the only lever is the
        prose the strategy model writes into voice_delivery, so the schema
        must ask for fast and energetic up front. Otherwise every strategy
        invents its own pace, usually slow and flat, and the scene lock then
        enforces exactly that.
        """
        import ai_service

        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [{"index": 0, "role": "hook", "seconds": 3,
                              "goal": "g", "script": "s", "action": "a"},
                             {"index": 1, "role": "middle", "seconds": 17,
                              "goal": "g", "script": "s", "action": "a"}],
            }

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        asyncio.run(ai_service.generate_video_strategy(
            profile={"brand_name": "Sleeply"},
            template={"name": "T", "hook_seconds": 3},
            hook_seconds=3,
        ))
        assert "fast, upbeat, high-energy" in captured["prompt"]

    def test_the_strategy_schema_defaults_to_unpolished_phone_shot_look(self, monkeypatch):
        """
        The visual_style schema hint is the only lever on the look: whatever it
        names, the model writes into scene.visual_style, and the scene lock
        then enforces exactly that on the render. Polished studio footage
        reads as an ad on TikTok and dies there, so the hint must ask for a
        natural, amateur, phone-shot look up front. Otherwise every strategy
        defaults to polished UGC and the founder pays for a render that looks
        like marketing.
        """
        import ai_service

        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [{"index": 0, "role": "hook", "seconds": 3,
                              "goal": "g", "script": "s", "action": "a"},
                             {"index": 1, "role": "middle", "seconds": 17,
                              "goal": "g", "script": "s", "action": "a"}],
            }

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        asyncio.run(ai_service.generate_video_strategy(
            profile={"brand_name": "Sleeply"},
            template={"name": "T", "hook_seconds": 3},
            hook_seconds=3,
        ))
        assert "polished UGC" not in captured["prompt"]
        assert "never polished" in captured["prompt"]

    def test_a_fully_populated_prompt_stays_under_a_ceiling(self, monkeypatch):
        """
        The guard I promised and did not write the first time.

        Prompt length is not itself the budget problem -- the prompt is an input
        and 8192 covers the completion. It is a proxy for the thing that actually
        bites: every field the prompt asks for is a value the model must write
        back, so growing the request grows the reply, and the reply is what gets
        truncated. The strategy schema is already the largest in the codebase
        and 4000 tokens produced a real production failure, so this measures a
        worst case -- every field filled to its cap, the approved plan attached,
        feedback history and past performance all present -- and fails with the
        measured number, so raising the ceiling is a decision made with the
        figure in hand rather than a shrug.
        """
        import ai_service

        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "cta_strategy": "c", "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [{"index": 0, "role": "hook", "seconds": 5,
                              "goal": "g", "script": "s", "action": "a"}],
                "continuity_contract": {
                    "established": [], "must_not_change": [], "do_not_repeat": [],
                },
            }

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)

        # Eight items per list: that is the cap APP_PROFILE_LIST_KEYS applies on
        # the way in, so it is the true worst case rather than a generous one.
        eight = [f"item {i}" for i in range(1, 9)]
        asyncio.run(ai_service.generate_video_strategy(
            profile={
                "brand_name": "ShiftLog",
                "brand_description": "Shift logging for healthcare workers.",
                "app_category": "Productivity",
                "platforms": ["iOS", "Android"],
                "core_features": eight,
                "primary_use_cases": eight,
                "problems_solved": eight,
                "icp_segments": eight,
                "desired_outcomes": eight,
                # Six linked statements: the normalizer's cap, so the worst
                # case rather than a generous one. Leaving this out would
                # understate the real maximum now that every prompt carries it.
                "outcome_statements": [
                    {
                        "outcome": f"Benefit number {i} in the viewer's own terms",
                        "who_feels_it": "hospital nurses working rotating shifts",
                        "from_feature": "item 1",
                        "how_it_helps": f"How the solution works as a benefit, number {i}",
                    }
                    for i in range(6)
                ],
                "known_limitations": "iOS and Android only; no offline mode yet.",
                "must_not_show": eight,
                "usage_moments": eight,
                "proof_moment": "One tap and the shift is on the log",
                # Six is the normalizer's cap, so six is the worst case rather
                # than a generous guess. Leaving this field out of the fixture
                # would have made the ceiling test measure a profile that no
                # real profile resembles.
                "viewer_objections": [
                    {
                        "objection": f"Objection {i}",
                        "what_they_do_now": f"The alternative they use today, number {i}",
                        "honest_answer": f"The honest answer from the facts, number {i}",
                    }
                    for i in range(6)
                ],
                "target_audience": "hospital nurses working rotating shifts",
            },
            template={
                "name": "Stop Doing This", "category": "problem",
                "opening_structure": "Name the mistake.", "hook_seconds": 5,
                "continuation_structure": "Then the fix.", "cta_pattern": "Try it",
                "visual_style": "Talking head.", "camera_pacing": "Steady.",
            "content_slots": {f"slot{i}": f"value{i}" for i in range(1, 9)},
            "required_assets": ["character_reference"],
            # The anonymous trend aggregate a research-published template
            # carries. Part of the worst case: it is a prompt section, and its
            # absence from this fixture would understate the real maximum.
            "trend_evidence": json.dumps({
                "has_signal": True,
                "sample_size": 40,
                "median_view_band": "100K-1M",
                "median_engagement_band": "typical (5-10%)",
                "recency_band": "under 48h",
            }),
        },
            angle={
                "kind": "problem", "label": "Too many lists",
                "target_audience": "nurses", "user_problem": "paperwork",
                "hook_promise": "less admin", "app_feature": "one-tap logging",
                "desired_emotion": "relief", "recommended_cta": "Try it free",
                "claims_to_respect": ["works offline"],
            },
            objective="address_user_problem", hook_seconds=5,
            total_duration=30, tone="calm", brand_voice="plain, tired, warm",
            profile_feedback={
                "total": 200, "template_rejections": 9, "generation_rejections": 12,
                "heavy_script_edits": 2,
                "top_reasons": [{"reason": "hook_too_generic", "count": 7}],
                "selected_template": {},
            },
            plan={
                "hook_line": "h", "cta": "c", "feature_emphasis": "f",
                "visual_direction": "v", "voice_direction": "vd",
                "sound_direction": "sd",
                "beat_timeline": [
                    {"start": i * 5, "end": i * 5 + 5, "beat": f"beat {i}"}
                    for i in range(4)
                ],
            },
        ))

        prompt = captured["prompt"]
        # Measured worst case, with every list at its cap, six viewer objections,
        # six outcome statements and the anonymous trend aggregate.
        #
        # The number has moved five times now -- 13,692 before the objections,
        # 15,226 after, 20,675 after the outcome layer (linked statements in
        # every prompt plus the pitch rules that consume them), then the true
        # 22,499 at HEAD -- and four of those moved *because* the fixture was
        # corrected, not because the ceiling was raised. Two earlier versions of
        # this test used a round number picked without measuring and let a real
        # inflation through, so the figure quoted in the failure message is the
        # one to trust.
        #
        # This move is a raise, and it is deliberate and measured. HEAD measured
        # 22,499 against a 22,500 ceiling -- 1 character of headroom, so a quoted
        # 21,065 nobody had re-measured. Every spoken line now has to be held to
        # the same craft rules in BOTH prompts, and the strategy writes its own
        # hook_line and section scripts whenever it has no approved plan to bind
        # to. Withholding them there would leave exactly the draft this change
        # exists to fix. The block is 1,077 characters, so the ceiling moves by
        # a measured 2,000 to 24,500: ~250 tokens of prompt against the 8,192
        # output budget the schema already needs headroom in, which is the trade
        # this makes and the reason it is affordable.
        CEILING = 24_500
        assert len(prompt) <= CEILING, (
            f"fully-populated strategy prompt is {len(prompt)} chars "
            f"(~{len(prompt) // 4} tokens), over the {CEILING} ceiling. "
            f"Every field added here is a value the model must "
            f"write back, and a truncated strategy is a 502 the founder cannot fix."
        )

    def test_the_schema_still_asks_for_a_bounded_number_of_values(self):
        """
        The same concern counted directly rather than through prompt length.

        Was pinned on CONTINUATION_BEATS, which was the one part of the schema
        that scaled with a constant: pinning it is what stopped a future edit
        from quietly asking for twenty beats and paying for it in truncation
        retries.

        That constant is gone. A video is ONE render with exactly TWO sections —
        the hook and the middle — so the number is structural rather than a
        budget: a third section would be the product demo, which this workflow
        does not generate. What still has to hold is that the count is exactly
        two, that the two roles are the ones everything downstream reads, and
        that normalization cannot hand back more than the schema asked for.
        """
        import ai_service
        assert ai_service.GENERATED_SECTIONS == 2, (
            f"GENERATED_SECTIONS is {ai_service.GENERATED_SECTIONS}. It used to be "
            f"CONTINUATION_BEATS, a tunable budget; it is now structural — a third "
            f"generated section is a product demo, and the demo is the founder's own "
            f"recording attached afterwards."
        )
        assert ai_service.SECTION_ROLES == ("hook", "middle")
        # Truncation cannot rescue an over-long reply either: anything past the
        # second section is dropped rather than written out.
        assert ai_service.normalize_strategy({
            "hook_line": "h",
            "segments": [
                {"index": i, "role": "hook", "seconds": 3,
                 "goal": f"g{i}", "script": f"s{i}", "action": f"a{i}"}
                for i in range(9)
            ],
        })["segments"] == [
            {"index": 0, "role": "hook", "seconds": 3,
             "goal": "g0", "script": "s0", "action": "a0"},
            {"index": 1, "role": "middle", "seconds": 3,
             "goal": "g1", "script": "s1", "action": "a1"},
        ]


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
            brand_name="Truncation", app_category="Productivity",
            brand_description="A focus timer for people who stall on starting.",
            core_features=["Task timer", "Reminders"],
            usage_moments=["Starting a task they have been avoiding"],
            outcome_statements=[{
                "outcome": "Starting without stalling on setup",
                "who_feels_it": "people who stall on starting",
                "from_feature": "Task timer",
                "how_it_helps": "The timer starts in one tap so there is nothing to set up",
            }],
        ), user_id="anonymous"))
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


class TestPlanIsForcedToTwoSections:
    """
    The plan's beat timeline is the video's spine, and it is read straight into
    the render prompt. A video is ONE render with exactly two sections — a hook
    and a middle — so a four-beat hook/problem/demo/cta timeline would render a
    product demonstration and a closing ask in footage that is supposed to stop
    at the moment the presenter reaches for their phone.

    The prompt asks for two beats and the schema names only those two labels.
    This pins that the correction actually happens where the shape is known,
    because a model returning the old four-beat shape is strongly represented in
    its training and nothing downstream would stop it.
    """

    def _plan(self, beats, hook_seconds=3, duration=15):
        import ai_service
        return ai_service._enforce_two_sections(beats, hook_seconds)

    def test_the_old_four_beat_shape_is_folded_down_to_two(self):
        """
        The four-beat hook/problem/demo/cta arc a model returns from habit comes
        back as two sections, so there is no third beat for the render to film
        and no timeline whose length reserves seconds for a demo or a close.

        The SHAPE is corrected, and so are the WORDS of the two beats that were
        only ever a demonstration and a close. Correcting the labels while
        keeping their prose was the earlier behaviour, and it left "Show the
        timer" and "Try it free" sitting in the middle's text — which goes
        verbatim into the render prompt. So a demo gets dropped on the floor
        even while the story beats are kept, because a workflow that must not
        generate a product demo cannot inherit one from a beat's text.
        """
        import ai_service
        beats = ai_service._normalize_beats([
            {"start": 0, "end": 3, "label": "hook", "text": "Open hard"},
            {"start": 3, "end": 7, "label": "problem", "text": "The friction"},
            {"start": 7, "end": 13, "label": "demo", "text": "Show the timer"},
            {"start": 13, "end": 15, "label": "cta", "text": "Try it free"},
        ], 15)
        out = self._plan(beats)
        assert [b["label"] for b in out] == ["hook", "middle"]
        assert out[0]["text"] == "Open hard"
        assert out[0]["start"] == 0 and out[0]["end"] == 3
        assert out[1]["start"] == 3
        # Nothing survives as a separately-timed third or fourth beat.
        assert len(out) == 2
        # The story the model actually told is kept.
        assert "The friction" in out[1]["text"]
        # The demonstration and the call to action are not, in any form.
        blob = " ".join(str(b.get("text") or "") for b in out)
        assert "Show the timer" not in blob
        assert "Try it free" not in blob

    def test_the_middle_absorbs_the_remainder(self):
        out = self._plan([
            {"start": 0, "end": 3, "label": "hook", "text": "h"},
            {"start": 3, "end": 8, "label": "middle", "text": "m"},
            {"start": 8, "end": 15, "label": "extra", "text": "e"},
        ])
        assert len(out) == 2
        assert out[0]["end"] == 3
        assert out[1]["start"] == 3

    def test_a_hook_only_plan_is_left_alone_rather_than_invented(self):
        """
        One section is a real possibility — a model that returned a hook and
        nothing else has said less, not more. Padding the middle with invented
        text would be worse than letting the prompt state what is missing.
        """
        out = self._plan([{"start": 0, "end": 3, "label": "hook", "text": "h"}])
        assert [b["label"] for b in out] == ["hook"]

    def test_an_unlabelled_arc_is_not_thrown_away(self):
        out = self._plan([
            {"start": 0, "end": 2, "label": "", "text": "first"},
            {"start": 2, "end": 15, "label": "", "text": "then this"},
        ])
        assert [b["label"] for b in out] == ["hook", "middle"]
        assert out[1]["text"] == "then this"

    def test_junk_is_survivable(self):
        assert self._plan([]) == []
        assert self._plan(None) == []
        assert self._plan(["not a dict", None]) == []


def _run(coro):
    return asyncio.run(coro)


class TestGeneratedStoryRepair:
    @staticmethod
    def _plan(hook, script):
        return {
            "hook_line": hook, "script": script,
            "beat_timeline": [
                {"start": 0, "end": 3, "label": "hook", "text": hook},
                {"start": 3, "end": 15, "label": "middle", "text": script},
            ],
            "visual_direction": "A person reflecting at their desk.",
            "demo_brief": "Record the emotion suggestions.",
            "voice_direction": "Conversational.", "sound_direction": "Voice only.",
            "claims_used": [],
        }

    def test_overlong_hook_is_rewritten_not_split_into_fragments(self, monkeypatch):
        import ai_service
        bad = self._plan(
            "Unable to find words for feelings in the moment; hear suggested emotion words.",
            "It suggested emotion words and Body sensation mapping. Find words for feelings "
            "you couldn’t name before and leave an entry feeling more understood.",
        )
        good = self._plan(
            "I couldn't find words for what I felt.",
            "The suggestions helped me name the feeling. I left the entry understanding myself better.",
        )
        rec = _patch_client(monkeypatch, [
            _completion(json.dumps(bad)), _completion(json.dumps(good)),
        ])
        result = _run(ai_service.generate_creative_plan(
            profile={"brand_name": "Journal", "core_features": ["Emotion suggestions"]},
            template={"name": "T", "hook_seconds": 3}, duration_seconds=15,
        ))
        assert result["hook_line"] == good["hook_line"]
        assert result["script"] == good["script"]
        assert len(rec.payloads) == 2
        correction = rec.payloads[1]["messages"][1]["content"]
        assert bad["hook_line"] in correction
        assert "Rewrite" in correction
        assert "60" in correction and "180" in correction

    def test_already_short_fragments_are_rewritten_together(self, monkeypatch):
        import ai_service
        bad = self._plan(
            "End-of-day thoughts go uncaptured because typing feels like.",
            "a chore—one spoken minute. I felt understood.",
        )
        good = self._plan(
            "Typing my thoughts felt like a chore.",
            "I spoke instead. The reflection helped me understand what was on my mind.",
        )
        rec = _patch_client(monkeypatch, [
            _completion(json.dumps(bad)), _completion(json.dumps(good)),
        ])
        result = _run(ai_service.generate_creative_plan(
            profile={"brand_name": "Journal"}, template={"hook_seconds": 3},
            duration_seconds=15,
        ))
        assert result["hook_line"] == good["hook_line"]
        assert result["script"] == good["script"]
        assert len(rec.payloads) == 2

    def test_oversized_middle_is_rewritten_without_losing_its_resolution(self, monkeypatch):
        import ai_service
        bad = self._plan(
            "I couldn't name what I was feeling.",
            "I tried describing the day in detail, but I kept circling around the same "
            "thoughts without getting anywhere. " * 4 + "The suggestions helped me find the words.",
        )
        good = self._plan(
            bad["hook_line"],
            "The suggestions helped me find the words. I understood the feeling instead of circling around it.",
        )
        rec = _patch_client(monkeypatch, [
            _completion(json.dumps(bad)), _completion(json.dumps(good)),
        ])
        result = _run(ai_service.generate_creative_plan(
            profile={}, template={"hook_seconds": 3}, duration_seconds=15,
        ))
        assert result["hook_line"] == good["hook_line"]
        assert result["script"] == good["script"]
        assert len(rec.payloads) == 2

    def test_grammatical_preposition_endings_do_not_trigger_retries(self, monkeypatch):
        import ai_service
        good = self._plan(
            "I used to feel like that.",
            "Now I know what that feeling was like. Writing is something I look forward to.",
        )
        rec = _patch_client(monkeypatch, [_completion(json.dumps(good))])
        result = _run(ai_service.generate_creative_plan(
            profile={}, template={"hook_seconds": 3}, duration_seconds=15,
        ))
        assert result["hook_line"] == good["hook_line"]
        assert result["script"] == good["script"]
        assert len(rec.payloads) == 1

    def test_repeated_bad_drafts_fail_without_returning_chopped_copy(self, monkeypatch):
        import ai_service
        bad = self._plan("Unable to find words; hear.", "suggested emotion words.")
        rec = _patch_client(monkeypatch, [_completion(json.dumps(bad))])
        with pytest.raises(RuntimeError, match="complete.*spoken"):
            _run(ai_service.generate_creative_plan(
                profile={}, template={"hook_seconds": 3}, duration_seconds=15,
            ))
        assert len(rec.payloads) == 3, "editorial retries must be bounded"

    def test_clean_connected_draft_is_unchanged_without_extra_call(self, monkeypatch):
        import ai_service
        good = self._plan(
            "I couldn't name what I was feeling.",
            "The suggestions helped me find the words. I understood myself better after writing the entry.",
        )
        rec = _patch_client(monkeypatch, [_completion(json.dumps(good))])
        result = _run(ai_service.generate_creative_plan(
            profile={}, template={"hook_seconds": 3}, duration_seconds=15,
        ))
        assert result["hook_line"] == good["hook_line"]
        assert result["script"] == good["script"]
        assert len(rec.payloads) == 1
        prompt = rec.payloads[0]["messages"][1]["content"]
        assert "MIDDLE ONLY" in prompt
        assert "full spoken script for BOTH" not in prompt
        assert "SELF-REVIEW" in prompt


class TestSpokenLineCraft:
    """
    The two spoken lines are held to the same craft rules in BOTH prompts: the
    plan and the strategy. The strategy matters as much as the plan because it
    writes its own hook_line and section scripts whenever it has no approved
    plan to bind to — which is the draft that reaches a founder unrevised.

    The prompt is only half of it. The other half is that a draft which breaks
    these rules is rewritten rather than accepted, and that a genuinely good
    draft is not: a check that fires on a real customer line turns one bad plan
    into no plan at all, because the retry raises after its third attempt.
    """

    SRC = (BACKEND_DIR / "ai_service.py").read_text(encoding="utf-8")

    def test_the_rules_reach_both_prompts(self, monkeypatch):
        import ai_service
        prompts = []

        async def capture(system_message, prompt, context, **kwargs):
            prompts.append(prompt)
            return {
                "hook_line": "I could never name what I felt.",
                "script": "One sentence each night helped me understand the pattern.",
                "beat_timeline": [{"start": 0, "end": 3, "label": "hook", "text": "t"}],
                "visual_direction": "v", "demo_brief": "d",
                "voice_direction": "vd", "sound_direction": "sd", "claims_used": [],
            }

        monkeypatch.setattr(ai_service, "_chat_json", capture)
        _run(ai_service.generate_creative_plan(
            profile={"brand_name": "Journal"}, template={"name": "T", "hook_seconds": 3},
            duration_seconds=15,
        ))

        for prompt in prompts:
            assert "SPOKEN LINE CRAFT" in prompt
            assert "OUTCOMES, NOT FEATURES" in prompt
            assert "NO PROMOTION" in prompt

    def test_a_promotional_draft_is_rewritten(self, monkeypatch):
        """A draft that asks for the download is promotion, not a customer."""
        import ai_service
        bad = {
            "hook_line": "Download the app and start feeling better.",
            "script": "Install the app. It helps you name the feeling.",
            "beat_timeline": [{"start": 0, "end": 3, "label": "hook", "text": "t"}],
            "visual_direction": "v", "demo_brief": "d",
            "voice_direction": "vd", "sound_direction": "sd", "claims_used": [],
        }
        good = dict(bad, hook_line="I could never name what I felt.",
                    script="One sentence each night helped me understand the pattern.")
        rec = _patch_client(monkeypatch, [
            _completion(json.dumps(bad)), _completion(json.dumps(good)),
        ])
        result = _run(ai_service.generate_creative_plan(
            profile={"brand_name": "Journal"}, template={"name": "T", "hook_seconds": 3},
            duration_seconds=15,
        ))
        assert "download" not in result["script"].lower()
        assert len(rec.payloads) == 2
        assert "download" in rec.payloads[1]["messages"][1]["content"]

    def test_an_ai_sounding_draft_is_rewritten(self, monkeypatch):
        """The generic openers a customer never says out loud."""
        import ai_service
        bad = {
            "hook_line": "In today's fast-paced world, feelings get lost.",
            "script": "Imagine a world where you can name them all. It helps.",
            "beat_timeline": [{"start": 0, "end": 3, "label": "hook", "text": "t"}],
            "visual_direction": "v", "demo_brief": "d",
            "voice_direction": "vd", "sound_direction": "sd", "claims_used": [],
        }
        good = dict(bad, hook_line="I could never name what I felt.",
                    script="One sentence each night helped me understand the pattern.")
        rec = _patch_client(monkeypatch, [
            _completion(json.dumps(bad)), _completion(json.dumps(good)),
        ])
        _run(ai_service.generate_creative_plan(
            profile={"brand_name": "Journal"}, template={"name": "T", "hook_seconds": 3},
            duration_seconds=15,
        ))
        assert len(rec.payloads) == 2

    def test_a_genuine_customer_draft_is_not_rewritten(self, monkeypatch):
        """The false-positive guard: these are real lines, so one call only.

        Each of them trips an ordinary substring test — "look forward to"
        ends on a preposition, "I used to feel like that" is a comparison, and
        "download" would match a naive keyword scan if any of this fixture were
        about installing something. A check that rejects them is worse than no
        check, so they are the fixture.
        """
        import ai_service
        good = {
            "hook_line": "I used to feel like that.",
            "script": (
                "Now I know what that feeling was like. Writing is something I "
                "look forward to, and I finally understand where it came from."
            ),
            "beat_timeline": [{"start": 0, "end": 3, "label": "hook", "text": "t"}],
            "visual_direction": "v", "demo_brief": "d",
            "voice_direction": "vd", "sound_direction": "sd", "claims_used": [],
        }
        rec = _patch_client(monkeypatch, [_completion(json.dumps(good))])
        result = _run(ai_service.generate_creative_plan(
            profile={"brand_name": "Journal"}, template={"name": "T", "hook_seconds": 3},
            duration_seconds=15,
        ))
        assert result["hook_line"] == good["hook_line"]
        assert result["script"] == good["script"]
        assert len(rec.payloads) == 1

    def test_a_claimed_history_with_the_app_is_rewritten(self, monkeypatch):
        """The generator obeying its own safety layer.

        claim_safety warns when a spoken line claims a personal history with
        the app, so a draft that does it is rewritten here instead of accepted
        and then warned about. The shared patterns are what keep the two from
        disagreeing about what counts.
        """
        import ai_service
        bad = {
            "hook_line": "I use this every single morning.",
            "script": "I have been using it for months now. It helps me a lot.",
            "beat_timeline": [{"start": 0, "end": 3, "label": "hook", "text": "t"}],
            "visual_direction": "v", "demo_brief": "d",
            "voice_direction": "vd", "sound_direction": "sd", "claims_used": [],
        }
        good = dict(bad, hook_line="I could never name what I felt.",
                    script="One sentence each night helped me understand the pattern.")
        rec = _patch_client(monkeypatch, [
            _completion(json.dumps(bad)), _completion(json.dumps(good)),
        ])
        result = _run(ai_service.generate_creative_plan(
            profile={"brand_name": "Journal"}, template={"name": "T", "hook_seconds": 3},
            duration_seconds=15,
        ))
        assert result["hook_line"] == good["hook_line"]
        assert len(rec.payloads) == 2
        correction = rec.payloads[1]["messages"][1]["content"]
        assert "personal history" in correction

    def test_a_past_habit_is_not_rewritten(self, monkeypatch):
        """'I used to <verb>' is a past habit, not a usage claim.

        The exclusion lives in the shared patterns, so this guards both sides
        at once: the safety layer must not warn it, and the generator must not
        rewrite it.
        """
        import ai_service
        import claim_safety
        good = {
            "hook_line": "I used to dread mornings.",
            "script": "One sentence each night helped me understand the pattern.",
            "beat_timeline": [{"start": 0, "end": 3, "label": "hook", "text": "t"}],
            "visual_direction": "v", "demo_brief": "d",
            "voice_direction": "vd", "sound_direction": "sd", "claims_used": [],
        }
        assert claim_safety.find_risk_patterns(good["hook_line"]) == []
        rec = _patch_client(monkeypatch, [_completion(json.dumps(good))])
        result = _run(ai_service.generate_creative_plan(
            profile={"brand_name": "Journal"}, template={"name": "T", "hook_seconds": 3},
            duration_seconds=15,
        ))
        assert result["hook_line"] == good["hook_line"]
        assert len(rec.payloads) == 1

    def test_the_character_limits_are_untouched(self):
        """Rule one of the brief, pinned as a number rather than a promise.

        The craft rules steer wording; the budgets are what the render enforces,
        so a change here would change what fits even though nothing else moved.
        """
        import ai_service
        assert ai_service.SPOKEN_CHARS_PER_SECOND == 15
        assert ai_service.HOOK_CHARS_PER_SECOND == 20
        assert ai_service.spoken_budget(10) == 150
        assert ai_service.hook_ceiling(3) == 60
        assert ai_service.hook_ceiling(5) == 100
        assert ai_service.HOOK_TARGET_CHARS == 70
        assert ai_service.SCRIPT_TARGET_CHARS == 150

    def test_naming_the_app_is_reported_not_refused(self):
        """The founder sees the flag; the plan is not destroyed for it.

        A veto would take a whole plan down the moment an app was named after a
        common noun ("Journal", "Notes"), and a customer's line that mentions
        the product is one sentence the founder can rewrite themselves.
        """
        import ai_service
        check = ai_service.check_spoken_story(
            "Journal every night.", "It helps me name the feeling.", 3, 15,
            app_name="Journal",
        )
        assert check["story"]["names_the_app"] is True
        clean = ai_service.check_spoken_story(
            "I could never name what I felt.",
            "One sentence each night helped me understand the pattern.",
            3, 15, app_name="Journal",
        )
        assert clean["story"]["names_the_app"] is False
        # And the flag is opt-in: without a name there is nothing to match.
        assert "names_the_app" not in ai_service.check_spoken_story("Hi.", "There.", 3, 15)

    def test_the_founder_settings_reach_the_prompt(self, monkeypatch):
        """Rule two: a regeneration drafts for what is already selected.

        The audience and the look were chosen on the project; a regeneration
        that ignored both answered a different brief than the one selected.
        """
        import ai_service
        captured = {}

        async def capture(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return {
                "hook_line": "I could never name what I felt.",
                "script": "One sentence each night helped me understand the pattern.",
                "beat_timeline": [{"start": 0, "end": 3, "label": "hook", "text": "t"}],
                "visual_direction": "v", "demo_brief": "d",
                "voice_direction": "vd", "sound_direction": "sd", "claims_used": [],
            }

        monkeypatch.setattr(ai_service, "_chat_json", capture)
        _run(ai_service.generate_creative_plan(
            profile={"brand_name": "Journal", "target_audience": "shift workers",
                     "tone_voice": "plain and tired"},
            template={"name": "T", "hook_seconds": 3},
            angle={"target_audience": "the angle's audience", "user_problem": "p"},
            duration_seconds=15,
            audience="nurses on a night shift",
            visual_direction="A kitchen at 2am, warm lamp light.",
        ))
        prompt = captured["prompt"]
        # The founder's audience beats the angle's.
        assert "nurses on a night shift" in prompt
        assert "the angle's audience" not in prompt
        # The founder's look is one the returned visual_direction must describe.
        assert "A kitchen at 2am, warm lamp light." in prompt
        assert "describes it" in prompt
        # And the profile's own voice reached the prompt.
        assert "plain and tired" in prompt

    def test_the_project_serializer_carries_the_app_name_for_the_check(self):
        """The flag is only real if the name actually reaches the check.

        `studio_projects` has no brand_name column, so the serializer takes it
        from the caller. Without this the flag is silently absent on every
        response — a test on the pure function alone would not notice.
        """
        import server
        out = server._public_project(
            {"hook_line": "Journal every night.", "script": "It helps me name the feeling."},
            brand_name="Journal",
        )
        assert out["spoken_check"]["story"]["names_the_app"] is True
        bare = server._public_project(
            {"hook_line": "Journal every night.", "script": "It helps me name the feeling."}
        )
        assert "names_the_app" not in bare["spoken_check"]["story"]


class TestHookScriptContinuity:
    """
    Production failure: a stored plan reached Review with hook "My workday is
    still loud in my head." and script "I just start talking right here in
    the car. By the time I walk in, the day is written down and I can finally
    put it down." — the hook and the script read as two separate pieces, and
    "walk in" has no destination. The validator must read the two lines
    together and flag exactly that: the dangling reference, and the hook's
    image word the script never resolves.

    The flags are reported, never acted on: the editorial retry loop stays for
    observable defects (promotion, fragments, over-length lines), because a
    continuity check that fires on a real customer line turns one bad plan
    into no plan at all. The prompt carries the five rules; the check carries
    the evidence.
    """

    HOOK = "My workday is still loud in my head."
    DANGLING_SCRIPT = (
        "I just start talking right here in the car. By the time I walk in, "
        "the day is written down and I can finally put it down."
    )
    CONTINUOUS_SCRIPT = (
        "I am sitting in my car outside my house and the loud day is still buzzing. "
        "I say it all out here, and by the time I walk into my house the noise "
        "is written down and I can finally put it down."
    )

    def test_a_dangling_walk_in_and_unresolved_hook_word_are_flagged(self):
        import ai_service
        check = ai_service.check_spoken_story(self.HOOK, self.DANGLING_SCRIPT, 3, 15)
        assert any("walk in" in ref for ref in check["story"]["dangling_refs"])
        # "loud" is the hook's image; the script never echoes or resolves it.
        assert check["story"]["echoes_hook"] is False

    def test_a_continuous_pair_passes_every_continuity_flag(self):
        import ai_service
        check = ai_service.check_spoken_story(self.HOOK, self.CONTINUOUS_SCRIPT, 3, 15)
        assert check["story"]["dangling_refs"] == []
        assert check["story"]["echoes_hook"] is True
        assert check["story"]["sets_scene"] is True
        assert check["story"]["ends_on_handoff"] is True

    def test_unestablished_person_and_meeting_are_flagged(self):
        import ai_service
        check = ai_service.check_spoken_story(
            "I dread the weekly review.",
            "He told me that meeting went fine. I wrote it down after.",
            3, 15,
        )
        refs = " ".join(check["story"]["dangling_refs"])
        assert "he" in refs.lower()
        assert "that meeting" in refs.lower()

    def test_the_prompt_writes_hook_and_script_as_one_thought(self, monkeypatch):
        import ai_service
        captured = {}

        async def capture(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            return {
                "hook_line": "I could never name what I felt.",
                "script": "One sentence each night helped me understand the pattern.",
                "beat_timeline": [{"start": 0, "end": 3, "label": "hook", "text": "t"}],
                "visual_direction": "v", "demo_brief": "d",
                "voice_direction": "vd", "sound_direction": "sd", "claims_used": [],
            }

        monkeypatch.setattr(ai_service, "_chat_json", capture)
        _run(ai_service.generate_creative_plan(
            profile={"brand_name": "Journal"}, template={"name": "T", "hook_seconds": 3},
            duration_seconds=15,
        ))
        prompt = captured["prompt"]
        assert "ONE CONTINUOUS THOUGHT" in prompt
        assert "one breath" in prompt
        # The old rule stays: one problem named, one problem answered.
        assert "ONE STORY, TWO LINES" in prompt

    def test_continuity_flags_never_trigger_an_editorial_retry(self, monkeypatch):
        """A draft with a dangling reference is returned, not rewritten.

        The walk-in script is grammatical, complete, fitting and promotion-free,
        so the retry loop must accept it on the first call exactly as written —
        the continuity flags travel in the report for the founder, and a third
        failed attempt must never destroy a plan over a matter of craft.
        """
        import ai_service
        plan = {
            "hook_line": self.HOOK, "script": self.DANGLING_SCRIPT,
            "beat_timeline": [
                {"start": 0, "end": 3, "label": "hook", "text": "t"},
                {"start": 3, "end": 15, "label": "middle", "text": "t"},
            ],
            "visual_direction": "v", "demo_brief": "d",
            "voice_direction": "vd", "sound_direction": "sd", "claims_used": [],
        }
        rec = _patch_client(monkeypatch, [_completion(json.dumps(plan))])
        result = _run(ai_service.generate_creative_plan(
            profile={}, template={"hook_seconds": 3}, duration_seconds=15,
        ))
        assert result["hook_line"] == self.HOOK
        assert result["script"] == self.DANGLING_SCRIPT
        assert len(rec.payloads) == 1


class TestCompleteSentences:
    """
    Production failure, 2026-10-13: a stored plan reached Review with hook_line
    "End-of-day thoughts go uncaptured because typing feels like." and its
    script opening "a chore—..." — a fragment that satisfied the word-count
    floor ("never a short fragment") while ending on a preposition. The prompt
    never required complete sentences. Even the later sentence-aware clamp
    still split a long first sentence at a word and added punctuation. Bad
    generated dialogue must be rewritten, not passed through either clamp.
    """

    def _generate(self, monkeypatch, hook, script, corrected=None):
        import ai_service
        captured = {}
        plan = {
            "hook_line": hook, "script": script,
            "beat_timeline": [
                {"start": 0, "end": 3, "label": "hook", "text": "t"},
                {"start": 3, "end": 20, "label": "middle", "text": "t"},
            ],
            "visual_direction": "v", "demo_brief": "d",
            "voice_direction": "vd", "sound_direction": "sd",
            "claims_used": [],
        }

        calls = []

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            calls.append(prompt)
            return {**plan, **(corrected or {})} if len(calls) > 1 else dict(plan)

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        out = _run(ai_service.generate_creative_plan(
            profile={"brand_name": "B"}, template={"name": "T"}))
        return out, captured["prompt"]

    def test_the_prompt_demands_complete_sentences(self, monkeypatch):
        _, prompt = self._generate(monkeypatch, "A full hook line here.", "A full script here.")
        assert "COMPLETE SENTENCES" in prompt
        assert "conjunction, preposition or article" in prompt
        assert "no semicolon joining a statement to a command" in prompt

    def test_an_overlong_hook_is_rewritten_as_a_complete_sentence(self, monkeypatch):
        hook = "First complete opener here. " + "filler words " * 60
        out, prompt = self._generate(
            monkeypatch, hook, "A full script here.",
            corrected={"hook_line": "I finally found the words."},
        )
        assert out["hook_line"] == "I finally found the words."
        assert "EDITORIAL CORRECTION" in prompt

    def test_a_hook_without_any_terminator_is_not_returned_as_a_fragment(self, monkeypatch):
        hook = ("word " * 60).strip()
        with pytest.raises(RuntimeError, match="complete.*spoken"):
            self._generate(monkeypatch, hook, "A full script here.")

    def test_an_overlong_script_is_rewritten_not_sliced(self, monkeypatch):
        script = "Opening sentence here. " + "filler words " * 900
        assert len(script) > 6000
        replacement = "The suggestions helped me name it. I understood my feelings better."
        out, prompt = self._generate(
            monkeypatch, "A full hook line here.", script,
            corrected={"script": replacement},
        )
        assert out["script"] == replacement
        assert "EDITORIAL CORRECTION" in prompt

    def test_a_strategy_hook_snaps_to_a_sentence(self):
        import ai_service
        hook = "First complete opener here. " + "filler words " * 60
        out = ai_service.normalize_strategy({"hook_line": hook})
        assert out["hook_line"] == "First complete opener here."
        assert len(out["hook_line"]) <= 200
