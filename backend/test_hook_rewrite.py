"""One-click hook rewrite: a suggestion only, never saved (ADR 0084)."""
import asyncio
import importlib
import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

ANON = "anonymous"


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-hook-rewrite-")
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


def _project(api, hook_line="I don't want to type anything"):
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
    _run(api.update_studio_project(project["id"], UpdateStudioProjectRequest(hook_line=hook_line), ANON))
    return project


def _fake(calls, reply="I don't want to write in my journal today"):
    async def fake(profile, angle, hook_line, objective="", **kwargs):
        calls.append(hook_line)
        return reply
    return fake


def test_suggestion_returned_and_nothing_saved(api, monkeypatch):
    from models import RewriteHookRequest
    project = _project(api)
    calls = []
    monkeypatch.setattr(api.ai_service, "rewrite_hook_line", _fake(calls))
    out = _run(api.suggest_hook_rewrite(project["id"], RewriteHookRequest(hook_line="Typing is the last thing I want"), ANON))
    assert out == {"hook_line": "I don't want to write in my journal today", "original": "Typing is the last thing I want"}
    assert calls == ["Typing is the last thing I want"]
    stored = _run(api.get_studio_project(project["id"], ANON))
    assert stored["hook_line"] == "I don't want to type anything"


def test_saved_hook_used_when_body_sends_none(api, monkeypatch):
    from models import RewriteHookRequest
    project = _project(api)
    calls = []
    monkeypatch.setattr(api.ai_service, "rewrite_hook_line", _fake(calls))
    _run(api.suggest_hook_rewrite(project["id"], RewriteHookRequest(), ANON))
    assert calls == ["I don't want to type anything"]


def test_unknown_project_and_empty_hook_are_refused(api):
    from models import RewriteHookRequest
    with pytest.raises(HTTPException) as missing:
        _run(api.suggest_hook_rewrite("no-such-project", RewriteHookRequest(hook_line="x"), ANON))
    assert missing.value.status_code == 404
    project = _project(api, hook_line="")
    with pytest.raises(HTTPException) as empty:
        _run(api.suggest_hook_rewrite(project["id"], RewriteHookRequest(hook_line="  "), ANON))
    assert empty.value.status_code == 400


def test_failed_rewrite_names_the_next_step(api, monkeypatch):
    from models import RewriteHookRequest
    project = _project(api)

    async def boom(*args, **kwargs):
        raise RuntimeError("The rewrite came back unchanged.")
    monkeypatch.setattr(api.ai_service, "rewrite_hook_line", boom)
    with pytest.raises(HTTPException) as err:
        _run(api.suggest_hook_rewrite(project["id"], RewriteHookRequest(), ANON))
    assert err.value.status_code == 502
    assert "Try again" in err.value.detail


def test_a_truncated_hook_rewrite_names_the_cutoff(api, monkeypatch):
    # The hook endpoint shares the line endpoint's failure classes: a
    # rewrite cut off by the token budget must say so, not flatten into
    # the generic sentence kept for unclassified failures.
    from models import RewriteHookRequest
    project = _project(api)

    async def boom(*args, **kwargs):
        raise api.ai_service.TruncatedResponse("Hook rewrite was cut off")
    monkeypatch.setattr(api.ai_service, "rewrite_hook_line", boom)
    with pytest.raises(HTTPException) as err:
        _run(api.suggest_hook_rewrite(project["id"], RewriteHookRequest(), ANON))
    assert err.value.status_code == 502
    assert "cut off" in err.value.detail
    assert "Try again" in err.value.detail


def test_a_refusal_reason_reaches_the_founder(api, monkeypatch):
    from models import RewriteHookRequest
    project = _project(api)
    reason = (
        "The rewrite came back unchanged; "
        "try again, or edit the line yourself."
    )

    async def refuse(*args, **kwargs):
        raise api.ai_service.RewriteRefusal(reason)
    monkeypatch.setattr(api.ai_service, "rewrite_hook_line", refuse)
    with pytest.raises(HTTPException) as err:
        _run(api.suggest_hook_rewrite(project["id"], RewriteHookRequest(), ANON))
    # The service named why no clearer hook exists; the founder sees that
    # reason, not the generic sentence kept for provider failures.
    assert err.value.status_code == 422
    assert err.value.detail == reason
