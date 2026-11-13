"""Per-line rewrite assist: a suggestion for any spoken line, never saved.

The endpoint half mirrors test_hook_rewrite.py (the hook-only original);
the service half mirrors test_hook_voice.py's `_chat_json` fakes and pins
the two rules that are a middle line's own: the script never asks a
question, and the rewrite must fit the room the rest of the script leaves
in the middle's seconds.
"""
import asyncio
import importlib
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import ai_service
from ai_spoken import spoken_targets

ANON = "anonymous"

HOOK = "I don't want to type anything"
SCRIPT = (
    "Typing is the last thing I want to do at night. "
    "My head is still loud from the whole day."
)
FIRST_LINE = "Typing is the last thing I want to do at night."
CLEARER = "Writing in my journal is the last thing I want at night."


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-line-rewrite-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    sys.modules.pop("server", None)
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    asyncio.run(server.init_db())
    yield server
    sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


def _project(api, hook_line=HOOK, script=SCRIPT):
    from models import (
        ApproveAppProfileRequest, BrandProfileCreateRequest,
        CreateStudioProjectRequest, UpdateStudioProjectRequest,
    )
    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name="Voice Journal", app_category="Wellness",
        brand_description="Speak your journal entry instead of writing it.",
        core_features=["Voice entries"],
        usage_moments=["Winding down after work"],
        outcome_statements=[{
            "outcome": "Clearing the day's thoughts out loud",
            "who_feels_it": "people too tired to write",
            "from_feature": "Voice entries",
            "how_it_helps": "Talking replaces writing the entry",
        }],
    ), user_id=ANON))
    _run(api.approve_app_profile(profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"]), user_id=ANON))
    _run(api.update_studio_project(
        project["id"],
        UpdateStudioProjectRequest(hook_line=hook_line, script=script),
        ANON,
    ))
    return _run(api.get_studio_project(project["id"], ANON))


def _fake(calls, reply=CLEARER):
    async def fake(profile, angle, line, role="middle", **kwargs):
        calls.append({"line": line, "role": role, **kwargs})
        return reply
    return fake


# ---------------------------------------------------------------- endpoint


def test_middle_suggestion_returned_and_nothing_saved(api, monkeypatch):
    from models import RewriteLineRequest
    project = _project(api)
    calls = []
    monkeypatch.setattr(api.ai_service, "rewrite_spoken_line", _fake(calls))
    out = _run(api.suggest_line_rewrite(
        project["id"], RewriteLineRequest(line=FIRST_LINE, role="middle"), ANON))
    assert out == {"line": CLEARER, "original": FIRST_LINE, "role": "middle"}
    assert calls[0]["line"] == FIRST_LINE
    assert calls[0]["role"] == "middle"
    assert calls[0]["hook_line"] == HOOK
    assert calls[0]["script"] == SCRIPT
    # The budget handed to the rewrite is the room the rest of the script
    # leaves in the middle's ceiling — no more, so an accepted suggestion
    # cannot push the script over.
    ceiling = spoken_targets(
        project.get("hook_seconds") or 3, project.get("duration_seconds") or 15,
    )["script"]["ceiling"]
    assert calls[0]["max_chars"] == ceiling - (len(SCRIPT) - len(FIRST_LINE))
    stored = _run(api.get_studio_project(project["id"], ANON))
    assert stored["script"] == SCRIPT
    assert stored["hook_line"] == HOOK


def test_hook_role_falls_back_to_the_saved_hook(api, monkeypatch):
    from models import RewriteLineRequest
    project = _project(api)
    calls = []
    monkeypatch.setattr(api.ai_service, "rewrite_spoken_line", _fake(calls))
    out = _run(api.suggest_line_rewrite(
        project["id"], RewriteLineRequest(role="hook"), ANON))
    assert out == {"line": CLEARER, "original": HOOK, "role": "hook"}
    assert calls[0]["line"] == HOOK
    assert calls[0]["max_chars"] == 0


def test_unknown_project_bad_role_and_empty_line_are_refused(api):
    from models import RewriteLineRequest
    with pytest.raises(HTTPException) as missing:
        _run(api.suggest_line_rewrite(
            "no-such-project", RewriteLineRequest(line="x", role="middle"), ANON))
    assert missing.value.status_code == 404
    project = _project(api)
    with pytest.raises(HTTPException) as bad_role:
        _run(api.suggest_line_rewrite(
            project["id"], RewriteLineRequest(line="x", role="chorus"), ANON))
    assert bad_role.value.status_code == 400
    with pytest.raises(HTTPException) as empty:
        _run(api.suggest_line_rewrite(
            project["id"], RewriteLineRequest(line="  ", role="middle"), ANON))
    assert empty.value.status_code == 400


def test_no_room_left_in_the_middle_names_the_fix(api, monkeypatch):
    from models import RewriteLineRequest
    # A script far past anything its seconds can hold leaves no room for
    # any one line: the refusal names the fix and the model is never called.
    project = _project(api, script="word " * 400)
    calls = []
    monkeypatch.setattr(api.ai_service, "rewrite_spoken_line", _fake(calls))
    with pytest.raises(HTTPException) as err:
        _run(api.suggest_line_rewrite(
            project["id"], RewriteLineRequest(line="word", role="middle"), ANON))
    assert err.value.status_code == 400
    assert "shorten it first" in err.value.detail
    assert calls == []


def test_failed_rewrite_names_the_next_step(api, monkeypatch):
    from models import RewriteLineRequest
    project = _project(api)

    async def boom(*args, **kwargs):
        raise RuntimeError("The rewrite came back unchanged.")
    monkeypatch.setattr(api.ai_service, "rewrite_spoken_line", boom)
    with pytest.raises(HTTPException) as err:
        _run(api.suggest_line_rewrite(
            project["id"], RewriteLineRequest(line=FIRST_LINE, role="middle"), ANON))
    assert err.value.status_code == 502
    assert "Try again" in err.value.detail


# ----------------------------------------------------------------- service


def _chat_fake(replies, calls):
    async def fake_chat(**kwargs):
        calls.append(kwargs)
        return replies[len(calls) - 1]
    return fake_chat


def test_middle_rewrite_prompts_with_the_whole_story(monkeypatch):
    calls = []
    monkeypatch.setattr(ai_service, "_chat_json", _chat_fake([{"line": CLEARER}], calls))
    line = asyncio.run(ai_service.rewrite_spoken_line(
        {}, None, FIRST_LINE, "middle", hook_line=HOOK, script=SCRIPT))
    assert line == CLEARER
    prompt = calls[0]["prompt"]
    assert f"HOOK: {HOOK}" in prompt
    assert f"FULL SCRIPT: {SCRIPT}" in prompt
    assert FIRST_LINE in prompt
    assert "never a question" in prompt


def test_middle_rewrite_corrects_a_question_reply(monkeypatch):
    calls = []
    monkeypatch.setattr(ai_service, "_chat_json", _chat_fake([
        {"line": "Why is typing the last thing I want at night?"},
        {"line": CLEARER},
    ], calls))
    line = asyncio.run(ai_service.rewrite_spoken_line(
        {}, None, FIRST_LINE, "middle", hook_line=HOOK, script=SCRIPT))
    assert line == CLEARER
    assert len(calls) == 2
    assert "CORRECTION" in calls[1]["prompt"]
    assert "never asks one" in calls[1]["prompt"]


def test_middle_rewrite_refuses_a_persistent_question(monkeypatch):
    monkeypatch.setattr(
        ai_service, "_chat_json",
        AsyncMock(return_value={"line": "Why is typing the last thing I want?"}),
    )
    with pytest.raises(RuntimeError, match="question"):
        asyncio.run(ai_service.rewrite_spoken_line(
            {}, None, FIRST_LINE, "middle", hook_line=HOOK, script=SCRIPT))


def test_middle_rewrite_keeps_the_lines_budget(monkeypatch):
    calls = []
    monkeypatch.setattr(ai_service, "_chat_json", _chat_fake([
        {"line": "Writing in my journal is honestly the very last thing I want to do."},
        {"line": "Journaling is the last thing I want."},
    ], calls))
    line = asyncio.run(ai_service.rewrite_spoken_line(
        {}, None, FIRST_LINE, "middle", hook_line=HOOK, script=SCRIPT, max_chars=40))
    assert line == "Journaling is the last thing I want."
    assert len(line) <= 40
    assert len(calls) == 2
    assert "CORRECTION" in calls[1]["prompt"]
    assert "40" in calls[1]["prompt"]


def test_middle_rewrite_refuses_a_persistent_overrun(monkeypatch):
    monkeypatch.setattr(
        ai_service, "_chat_json",
        AsyncMock(return_value={"line": "Writing in my journal is the very last thing I want to do at night."}),
    )
    with pytest.raises(RuntimeError, match="running long"):
        asyncio.run(ai_service.rewrite_spoken_line(
            {}, None, FIRST_LINE, "middle", hook_line=HOOK, script=SCRIPT, max_chars=40))


def test_middle_rewrite_unchanged_reply_raises(monkeypatch):
    monkeypatch.setattr(
        ai_service, "_chat_json",
        AsyncMock(return_value={"line": FIRST_LINE}),
    )
    with pytest.raises(RuntimeError, match="unchanged"):
        asyncio.run(ai_service.rewrite_spoken_line(
            {}, None, FIRST_LINE, "middle", hook_line=HOOK, script=SCRIPT))


def test_hook_role_delegates_to_the_hook_rewrite(monkeypatch):
    async def fake_hook(profile, angle, hook_line, objective=""):
        return "A sharper hook."
    monkeypatch.setattr(ai_service, "rewrite_hook_line", fake_hook)
    line = asyncio.run(ai_service.rewrite_spoken_line({}, None, "A dull hook.", "hook"))
    assert line == "A sharper hook."


# ------------------------------------------------- the Nov 12 screenshot
#
# Kasra's Review step: the script body sat over its ceiling, and every
# clearer-line click — the hook and both script sentences — came back with
# the one generic failure. Three defects compounded. The room the endpoint
# leaves a line did not credit the line's own length, so a rewrite shorter
# than the line it replaced was refused as running long. An unchanged
# reply (the current hook handed back in quotes) raised with no correction
# retry, though question and length failures got one. And the endpoint
# flattened every failure into the same sentence, so the reason the
# service had already named never reached the founder.

SHOT_HOOK = "Mood flipped again halfway down this path today."
SHOT_S1 = (
    "It turns at one, after I eat lunch at my desk most days, and "
    "I keep thinking that flipped mood is not random."
)
SHOT_S2 = "I still don't know what sets that flip off."
SHOT_SCRIPT = SHOT_S1 + " " + SHOT_S2
# Clearer replies a real provider gives: each shorter than the line it
# replaces, the softener gone — but each longer than the room the old
# math left (106 of 109 for the first line, 40 of 43 for the second).
SHOT_S1_CLEARER = (
    "It turns at one, after I eat lunch at my desk most days, and "
    "I have noticed that flipped mood is not random."
)
SHOT_S2_CLEARER = "I still don't know what's setting it off."
SHOT_HOOK_CLEARER = "My mood flips at one every day, right after lunch at my desk."


def _shot_project(api):
    from models import (
        ApproveAppProfileRequest, BrandProfileCreateRequest,
        CreateStudioProjectRequest, UpdateStudioProjectRequest,
    )
    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name="Voice Journal", app_category="Wellness",
        brand_description="Speak your journal entry instead of writing it.",
        core_features=["Voice entries"],
        usage_moments=["Winding down after work"],
        outcome_statements=[{
            "outcome": "Clearing the day's thoughts out loud",
            "who_feels_it": "people too tired to write",
            "from_feature": "Voice entries",
            "how_it_helps": "Talking replaces writing the entry",
        }],
    ), user_id=ANON))
    _run(api.approve_app_profile(
        profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"]), user_id=ANON))
    # The screenshot's shape, written in one update: a 3-second hook in a
    # 13-second piece leaves the script a 150-character ceiling, and the
    # body is 153 — over it.
    _run(api.update_studio_project(
        project["id"],
        UpdateStudioProjectRequest(
            hook_line=SHOT_HOOK, script=SHOT_SCRIPT,
            hook_seconds=3, duration_seconds=13),
        ANON,
    ))
    return _run(api.get_studio_project(project["id"], ANON))


def test_over_ceiling_body_credits_the_lines_own_length(api, monkeypatch):
    from models import RewriteLineRequest
    project = _shot_project(api)
    calls = []
    monkeypatch.setattr(api.ai_service, "rewrite_spoken_line", _fake(calls))
    for line in (SHOT_S1, SHOT_S2):
        _run(api.suggest_line_rewrite(
            project["id"],
            RewriteLineRequest(
                line=line, role="middle", hook_line=SHOT_HOOK, script=SHOT_SCRIPT),
            ANON))
    # Replacing a line frees the line's own length, so the room a line is
    # handed can never be smaller than the line itself — even when the
    # body is already over its ceiling, which is exactly when a shorter
    # rewrite helps most.
    assert [c["max_chars"] for c in calls] == [len(SHOT_S1), len(SHOT_S2)]


def test_the_screenshot_clicks_all_succeed(api, monkeypatch):
    from models import RewriteLineRequest
    project = _shot_project(api)
    queues = {
        # The provider first hands the current hook back in quotes; the
        # correction retry is what wins the clearer line.
        "Hook rewrite": [
            {"hook_line": f'"{SHOT_HOOK}"'},
            {"hook_line": SHOT_HOOK_CLEARER},
        ],
        "Line rewrite": [
            {"line": SHOT_S1_CLEARER},
            {"line": SHOT_S2_CLEARER},
        ],
    }

    async def fake_chat(**kwargs):
        return queues[kwargs["context"]].pop(0)
    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    hook = _run(api.suggest_line_rewrite(
        project["id"], RewriteLineRequest(line=SHOT_HOOK, role="hook"), ANON))
    assert hook["line"] == SHOT_HOOK_CLEARER
    first = _run(api.suggest_line_rewrite(
        project["id"],
        RewriteLineRequest(
            line=SHOT_S1, role="middle", hook_line=SHOT_HOOK, script=SHOT_SCRIPT),
        ANON))
    assert first["line"] == SHOT_S1_CLEARER
    second = _run(api.suggest_line_rewrite(
        project["id"],
        RewriteLineRequest(
            line=SHOT_S2, role="middle", hook_line=SHOT_HOOK, script=SHOT_SCRIPT),
        ANON))
    assert second["line"] == SHOT_S2_CLEARER
    # Suggestions still never save themselves.
    stored = _run(api.get_studio_project(project["id"], ANON))
    assert stored["script"] == SHOT_SCRIPT
    assert stored["hook_line"] == SHOT_HOOK


def test_a_refusal_reason_reaches_the_founder(api, monkeypatch):
    from models import RewriteLineRequest
    project = _project(api)
    reason = (
        "The rewrite kept running long — past the characters this line's "
        "seconds hold; try again, or edit the line yourself."
    )

    async def refuse(*args, **kwargs):
        raise ai_service.RewriteRefusal(reason)
    monkeypatch.setattr(api.ai_service, "rewrite_spoken_line", refuse)
    with pytest.raises(HTTPException) as err:
        _run(api.suggest_line_rewrite(
            project["id"], RewriteLineRequest(line=FIRST_LINE, role="middle"), ANON))
    # The service named why no clearer line exists; the founder sees that
    # reason, not the generic sentence kept for provider failures.
    assert err.value.status_code == 422
    assert err.value.detail == reason


def test_a_provider_failure_keeps_the_generic_line(api, monkeypatch):
    from models import RewriteLineRequest
    project = _project(api)

    async def boom(*args, **kwargs):
        raise RuntimeError("Line rewrite did not return valid JSON")
    monkeypatch.setattr(api.ai_service, "rewrite_spoken_line", boom)
    with pytest.raises(HTTPException) as err:
        _run(api.suggest_line_rewrite(
            project["id"], RewriteLineRequest(line=FIRST_LINE, role="middle"), ANON))
    assert err.value.status_code == 502
    assert err.value.detail == (
        "Couldn't write a clearer line just now. "
        "Try again, or edit the line yourself."
    )


def test_middle_rewrite_corrects_an_unchanged_reply(monkeypatch):
    calls = []
    monkeypatch.setattr(ai_service, "_chat_json", _chat_fake([
        {"line": FIRST_LINE},
        {"line": CLEARER},
    ], calls))
    line = asyncio.run(ai_service.rewrite_spoken_line(
        {}, None, FIRST_LINE, "middle", hook_line=HOOK, script=SCRIPT))
    assert line == CLEARER
    assert len(calls) == 2
    assert "CORRECTION" in calls[1]["prompt"]
    assert "unchanged" in calls[1]["prompt"]


def test_middle_rewrite_refuses_a_persistent_echo(monkeypatch):
    monkeypatch.setattr(
        ai_service, "_chat_json",
        AsyncMock(return_value={"line": FIRST_LINE}),
    )
    with pytest.raises(ai_service.RewriteRefusal, match="unchanged"):
        asyncio.run(ai_service.rewrite_spoken_line(
            {}, None, FIRST_LINE, "middle", hook_line=HOOK, script=SCRIPT))


def test_middle_rewrite_prompt_cuts_softeners(monkeypatch):
    calls = []
    monkeypatch.setattr(ai_service, "_chat_json", _chat_fake([{"line": CLEARER}], calls))
    asyncio.run(ai_service.rewrite_spoken_line(
        {}, None, FIRST_LINE, "middle", hook_line=HOOK, script=SCRIPT))
    prompt = calls[0]["prompt"]
    assert "One idea per sentence" in prompt
    assert "cut softeners" in prompt
    assert "I keep thinking" in prompt


# ------------------------------------------- the Nov 13 generic failures
#
# All three clearer-line clicks failed live AGAIN, this time on lines the
# Nov 12 fixes already handled, with the same flat sentence. The classes
# below are every way the rewrite path can die, pinned one by one: the
# token budget a Max-reasoning model truncates against, and the endpoint
# messages, which must name the class instead of flattening all of them
# into "Couldn't write a clearer line just now."


class _BudgetResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _BudgetRecorder:
    """A provider whose thought tokens eat the completion budget.

    The shipped text model reasons at Max and bills that reasoning
    against max_tokens (see the note at the top of ai_service.py), so a
    small budget comes back as empty content with finish_reason=length
    even though the visible answer is one short line. This recorder
    plays exactly that: below the threshold every reply truncates;
    above it the line comes back whole.
    """

    THRESHOLD = 1000

    def __init__(self):
        self.payloads = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        self.payloads.append(json)
        if (json or {}).get("max_tokens", 0) < self.THRESHOLD:
            return _BudgetResponse({"choices": [{
                "finish_reason": "length", "message": {"content": ""}}]})
        return _BudgetResponse({"choices": [{
            "finish_reason": "stop",
            "message": {"content": (
                '{"line": "Writing in my journal is the last thing '
                'I want at night.", "hook_line": "I don\'t want to '
                'write in my journal today."}'
            )},
        }]})


def _patch_budget_provider(monkeypatch):
    rec = _BudgetRecorder()
    monkeypatch.setattr(ai_service.httpx, "AsyncClient", lambda *a, **k: rec)
    monkeypatch.setattr(ai_service, "OPENROUTER_API_KEY", "test")
    return rec


def test_middle_rewrite_survives_a_reasoning_sized_budget(monkeypatch):
    rec = _patch_budget_provider(monkeypatch)
    line = asyncio.run(ai_service.rewrite_spoken_line(
        {}, None, FIRST_LINE, "middle", hook_line=HOOK, script=SCRIPT))
    assert line == CLEARER
    # The first attempt's budget already clears the truncation threshold:
    # the pre-fix 400 (and its doubled 800 retry) both came back empty.
    assert rec.payloads[0]["max_tokens"] >= _BudgetRecorder.THRESHOLD
    assert len(rec.payloads) == 1


def test_hook_rewrite_survives_a_reasoning_sized_budget(monkeypatch):
    rec = _patch_budget_provider(monkeypatch)
    line = asyncio.run(ai_service.rewrite_hook_line(
        {}, None, "Typing is the last thing I want"))
    assert line == "I don't want to write in my journal today."
    assert rec.payloads[0]["max_tokens"] >= _BudgetRecorder.THRESHOLD
    assert len(rec.payloads) == 1


def _raise(exc):
    async def boom(*args, **kwargs):
        raise exc
    return boom


def test_a_truncated_rewrite_names_the_cutoff(api, monkeypatch):
    from models import RewriteLineRequest
    project = _project(api)
    monkeypatch.setattr(
        api.ai_service, "rewrite_spoken_line",
        _raise(ai_service.TruncatedResponse("Line rewrite was cut off")))
    with pytest.raises(HTTPException) as err:
        _run(api.suggest_line_rewrite(
            project["id"], RewriteLineRequest(line=FIRST_LINE, role="middle"), ANON))
    assert err.value.status_code == 502
    assert "cut off" in err.value.detail
    assert "Try again" in err.value.detail


def test_a_declined_rewrite_names_the_refusal(api, monkeypatch):
    from models import RewriteLineRequest
    project = _project(api)
    monkeypatch.setattr(
        api.ai_service, "rewrite_spoken_line",
        _raise(ai_service.ModelRefusal("Line rewrite was refused")))
    with pytest.raises(HTTPException) as err:
        _run(api.suggest_line_rewrite(
            project["id"], RewriteLineRequest(line=FIRST_LINE, role="middle"), ANON))
    assert err.value.status_code == 502
    assert "declined" in err.value.detail


def test_an_unusable_reply_names_the_shape(api, monkeypatch):
    from models import RewriteLineRequest
    project = _project(api)
    monkeypatch.setattr(
        api.ai_service, "rewrite_spoken_line",
        _raise(ai_service.UnusableResponse("Line rewrite did not return valid JSON")))
    with pytest.raises(HTTPException) as err:
        _run(api.suggest_line_rewrite(
            project["id"], RewriteLineRequest(line=FIRST_LINE, role="middle"), ANON))
    assert err.value.status_code == 502
    assert "couldn't be used" in err.value.detail
    # The parse class no longer hides behind the flat generic sentence.
    assert err.value.detail != (
        "Couldn't write a clearer line just now. "
        "Try again, or edit the line yourself."
    )


def test_a_slow_rewrite_names_the_wait(api, monkeypatch):
    import httpx
    from models import RewriteLineRequest
    project = _project(api)
    request = httpx.Request("POST", "https://openrouter.example/chat")
    monkeypatch.setattr(
        api.ai_service, "rewrite_spoken_line",
        _raise(httpx.TimeoutException("read timed out", request=request)))
    with pytest.raises(HTTPException) as err:
        _run(api.suggest_line_rewrite(
            project["id"], RewriteLineRequest(line=FIRST_LINE, role="middle"), ANON))
    assert err.value.status_code == 502
    assert "too long" in err.value.detail


def test_a_busy_provider_names_the_throttle(api, monkeypatch):
    import httpx
    from models import RewriteLineRequest
    project = _project(api)
    request = httpx.Request("POST", "https://openrouter.example/chat")
    response = httpx.Response(429, request=request)
    monkeypatch.setattr(
        api.ai_service, "rewrite_spoken_line",
        _raise(httpx.HTTPStatusError("429", request=request, response=response)))
    with pytest.raises(HTTPException) as err:
        _run(api.suggest_line_rewrite(
            project["id"], RewriteLineRequest(line=FIRST_LINE, role="middle"), ANON))
    assert err.value.status_code == 502
    assert "busy" in err.value.detail


def test_a_truly_unknown_failure_keeps_the_generic_line(api, monkeypatch):
    from models import RewriteLineRequest
    project = _project(api)
    monkeypatch.setattr(
        api.ai_service, "rewrite_spoken_line",
        _raise(ValueError("an unclassified surprise")))
    with pytest.raises(HTTPException) as err:
        _run(api.suggest_line_rewrite(
            project["id"], RewriteLineRequest(line=FIRST_LINE, role="middle"), ANON))
    # The flat sentence survives for exactly one class: a failure nobody
    # classified. Its cause is in the server log and the model-call
    # ledger, not hidden — it just has no honest name to give the founder.
    assert err.value.status_code == 502
    assert err.value.detail == (
        "Couldn't write a clearer line just now. "
        "Try again, or edit the line yourself."
    )
