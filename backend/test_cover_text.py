"""The cover text is a first-class plan line (ADR 0145).

Drafted with the plan, shown and scored in Review, regenerated only
from its own button as a suggestion that is never auto-saved, and
shipped verbatim by the post kit when the founder has approved one.
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

ANON = "anonymous"

HOOK = "Friday morning in the bakery queue, the words won't come."
SCRIPT = (
    "I move the two sliders for how pleasant and calm I feel, warm paper "
    "bag in my hand. What sets it off is still unclear."
)
COVER = "Bakery queue, words won't come"


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-cover-text-")
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


def _project(api, with_words=True):
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
    if with_words:
        _run(api.update_studio_project(project["id"], UpdateStudioProjectRequest(
            hook_line=HOOK, script=SCRIPT), ANON))
    return project


def test_suggestion_returns_cover_and_scores_and_saves_nothing(api, monkeypatch):
    from models import CoverTextRequest
    project = _project(api)
    _run(api.update_studio_project(
        project["id"],
        __import__("models").UpdateStudioProjectRequest(cover_text="Old cover"),
        ANON,
    ))

    async def fake_generate(profile, angle, hook_line, script, current_cover="", objective=""):
        assert current_cover == "Old cover"
        return COVER

    monkeypatch.setattr(api.ai_service, "generate_cover_text", fake_generate)
    out = _run(api.suggest_cover_text(project["id"], CoverTextRequest(), ANON))
    assert out["cover_text"] == COVER
    assert out["original"] == "Old cover"
    assert out["hook_score"]["max"] == 20
    assert out["hook_score"]["suggested"] >= out["hook_score"]["current"]
    # Advisory: the stored cover is still the founder's, untouched.
    stored = _run(api.get_studio_project(project["id"], ANON))
    assert stored["cover_text"] == "Old cover"


def test_suggestion_refuses_before_any_words_exist(api):
    from models import CoverTextRequest
    project = _project(api, with_words=False)
    with pytest.raises(HTTPException) as exc:
        _run(api.suggest_cover_text(project["id"], CoverTextRequest(), ANON))
    assert exc.value.status_code == 400


def test_cover_edit_writes_without_touching_the_plan(api):
    from models import UpdateStudioProjectRequest
    project = _project(api)
    before = _run(api.get_studio_project(project["id"], ANON))
    _run(api.update_studio_project(
        project["id"], UpdateStudioProjectRequest(cover_text=COVER), ANON))
    after = _run(api.get_studio_project(project["id"], ANON))
    assert after["cover_text"] == COVER
    # Post copy, not plan content: no version bump, no status change —
    # the spoken words never moved, so nothing goes stale.
    assert after["script_version"] == before["script_version"]
    assert after["status"] == before["status"]


def test_quality_report_scores_the_cover_with_the_hook(api):
    from models import UpdateStudioProjectRequest
    project = _project(api)
    # A hook with no concrete anchor of its own: the cover's bakery is
    # the only anchor in the opening, so the evidence must name it.
    _run(api.update_studio_project(
        project["id"], UpdateStudioProjectRequest(
            hook_line="The words won't come when I need them most.",
            cover_text=COVER), ANON))
    stored = _run(api.get_studio_project(project["id"], ANON))
    report = stored["quality_report"]
    assert report["cover_text"] == {"text": COVER, "scored_with_hook": True}
    evidence = " ".join(
        report["dimensions"]["hook_stopping_power"]["evidence"]).lower()
    assert "cover text carries the concrete anchor" in evidence


def _stub_chat(monkeypatch, replies):
    import ai_service
    queue = list(replies)

    async def fake_chat(**kwargs):
        return queue.pop(0) if queue else {}

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)


def test_generate_cover_text_accepts_a_fresh_cover(monkeypatch):
    import ai_service
    _stub_chat(monkeypatch, [{"cover_text": COVER}])
    out = asyncio.run(ai_service.generate_cover_text(
        {"brand_name": "Voice Journal"}, None, HOOK, SCRIPT,
        current_cover="Old cover",
    ))
    assert out == COVER


def test_generate_cover_text_refuses_an_echo_after_one_correction(monkeypatch):
    import ai_service
    _stub_chat(monkeypatch, [
        {"cover_text": "Old cover"}, {"cover_text": "Old cover"},
    ])
    with pytest.raises(ai_service.RewriteRefusal):
        asyncio.run(ai_service.generate_cover_text(
            {"brand_name": "Voice Journal"}, None, HOOK, SCRIPT,
            current_cover="Old cover",
        ))


def test_generate_cover_text_refuses_a_copy_of_the_hook(monkeypatch):
    import ai_service
    _stub_chat(monkeypatch, [
        {"cover_text": HOOK}, {"cover_text": HOOK},
    ])
    with pytest.raises(ai_service.RewriteRefusal):
        asyncio.run(ai_service.generate_cover_text(
            {"brand_name": "Voice Journal"}, None, HOOK, SCRIPT,
        ))


def test_post_kit_ships_the_approved_cover(monkeypatch):
    import ai_service
    import hashtag_volume
    monkeypatch.setattr(ai_service, "_chat_json", AsyncMock(return_value={
        "caption": "I stopped fighting my phone and cleared one list instead — you?",
        "hashtags": ["#one", "#two", "#three", "#four", "#five"],
        "cover_text": "A different unseen draft",
    }))
    monkeypatch.setattr(
        hashtag_volume, "lookup_hashtag_counts", AsyncMock(return_value={}))
    project = {
        "hook_line": HOOK, "script": SCRIPT, "cta": "",
        "cover_text": COVER,
    }
    out = asyncio.run(ai_service.generate_post_kit(
        project, {"brand_name": "Voice Journal", "status": "approved"}))
    assert out["cover_text"] == COVER
