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


# ------------------------------------------------ the tightened cover
#
# ADR 0206: covers still came out too long at the old sizing — the ask
# said under eight words while the caps allowed ten words and a
# hundred characters, and the headroom swallowed the ask. Kasra's
# ruling: the cover lives on screen for the opening's first two
# seconds, so the optimized cover is 3 to 5 words, eye catching,
# punchy and enticing; an 8-word cap was proposed and he rejected it
# as too long. The caps now sit just past the ask — 6 words, 35
# characters (his final sizing for a cover: 30 to 35 characters,
# superseding an interim 50) — so a cover at the top of the ask
# always fits, and the bounded correction corrects against the
# tighter caps.

SEVEN_WORDS = "Bakery queue on Friday, words won't come"  # 7 words, 40 chars
LONG_FIVE = "Grandmother's heavy old suitcase collection"  # 5 words, 43 chars


def test_cover_caps_sit_just_past_the_ask():
    import ai_service
    assert ai_service.COVER_TEXT_MAX_WORDS == 6
    assert ai_service.COVER_TEXT_MAX_CHARS == 35


def test_cover_rules_ask_for_three_to_five_words():
    import ai_service
    block = ai_service._cover_text_rules_block()
    assert "3 to 5 words" in block
    # Kasra's words for what the short cover must still be.
    assert "Eye catching, punchy and enticing" in block
    assert "under eight" not in block
    assert "under 8" not in block


def _recording_chat(monkeypatch, replies):
    import ai_service
    queue = list(replies)
    calls = []

    async def fake_chat(**kwargs):
        calls.append(kwargs)
        return queue.pop(0) if queue else {}

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    return calls


def test_generate_cover_text_corrects_a_seven_word_cover(monkeypatch):
    import ai_service
    # Seven words passed the old ten-word cap untouched; the tighter
    # ceiling corrects it, naming the new limit.
    calls = _recording_chat(monkeypatch, [
        {"cover_text": SEVEN_WORDS}, {"cover_text": COVER},
    ])
    out = asyncio.run(ai_service.generate_cover_text(
        {"brand_name": "Voice Journal"}, None, HOOK, SCRIPT,
        current_cover="Old cover",
    ))
    assert out == COVER
    assert len(calls) == 2
    assert "CORRECTION" in calls[1]["prompt"]
    assert "6 words at most" in calls[1]["prompt"]


def test_generate_cover_text_corrects_a_cover_past_the_char_cap(monkeypatch):
    import ai_service
    # Five words — inside the word ask — but 43 characters: inside
    # the interim 50 cap, past Kasra's 35. The char ceiling is a
    # real second bound, not a formality.
    calls = _recording_chat(monkeypatch, [
        {"cover_text": LONG_FIVE}, {"cover_text": COVER},
    ])
    out = asyncio.run(ai_service.generate_cover_text(
        {"brand_name": "Voice Journal"}, None, HOOK, SCRIPT,
        current_cover="Old cover",
    ))
    assert out == COVER
    assert len(calls) == 2
    assert "CORRECTION" in calls[1]["prompt"]


def test_generate_cover_text_refuses_a_cover_that_stays_long(monkeypatch):
    import ai_service
    _stub_chat(monkeypatch, [
        {"cover_text": SEVEN_WORDS}, {"cover_text": SEVEN_WORDS},
    ])
    with pytest.raises(ai_service.RewriteRefusal, match="running long"):
        asyncio.run(ai_service.generate_cover_text(
            {"brand_name": "Voice Journal"}, None, HOOK, SCRIPT,
            current_cover="Old cover",
        ))


def test_generate_cover_text_corrects_a_cut_off_cover(monkeypatch):
    import ai_service
    # ADR 0231: a cover is a fragment by design, but it may not be a
    # thought cut in half. This reply is 34 characters and 6 words —
    # inside both caps, so the length branch cannot see it; only the
    # finished-cover gate catches the dangling 'and'.
    calls = _recording_chat(monkeypatch, [
        {"cover_text": "Bakery queue, words won't come and"}, {"cover_text": COVER},
    ])
    out = asyncio.run(ai_service.generate_cover_text(
        {"brand_name": "Voice Journal"}, None, HOOK, SCRIPT,
        current_cover="Old cover",
    ))
    assert out == COVER
    assert len(calls) == 2
    assert "CORRECTION" in calls[1]["prompt"]
    assert "cut off" in calls[1]["prompt"]


def test_generate_cover_text_refuses_a_persistent_cut_off_cover(monkeypatch):
    import ai_service
    _stub_chat(monkeypatch, [
        {"cover_text": "Bakery queue, words won't come and"},
        {"cover_text": "Bakery queue, words won't come and"},
    ])
    with pytest.raises(ai_service.RewriteRefusal, match="cut off"):
        asyncio.run(ai_service.generate_cover_text(
            {"brand_name": "Voice Journal"}, None, HOOK, SCRIPT,
            current_cover="Old cover",
        ))


def test_post_kit_prompt_asks_for_three_to_five_words(monkeypatch):
    import ai_service
    import hashtag_volume
    calls = _recording_chat(monkeypatch, [{
        "caption": "I stopped fighting my phone and cleared one list instead — you?",
        "hashtags": ["#one", "#two", "#three", "#four", "#five"],
        "cover_text": "A different unseen draft",
    }])
    monkeypatch.setattr(
        hashtag_volume, "lookup_hashtag_counts", AsyncMock(return_value={}))
    project = {
        "hook_line": HOOK, "script": SCRIPT, "cta": "",
        "cover_text": COVER,
    }
    asyncio.run(ai_service.generate_post_kit(
        project, {"brand_name": "Voice Journal", "status": "approved"}))
    prompt = calls[0]["prompt"]
    assert "3 to 5 words" in prompt
    assert "under 8 words" not in prompt


# ------------------------------------------------ covers validated, never sliced
#
# ADR 0232: the plan's first-draft cover and the post kit's model
# cover were stored after a hard [:100] slice and never validated
# against the cover rule — a 63-character draft came back stored as
# its first 100 characters would allow, and a fragment draft was
# stored whole. Now the draft answers to the same validation as the
# cover suggestion flow: a plan draft that fails stores NO cover
# (the plan is never refused over post copy; Review's Suggest flow
# writes one), a post-kit model cover that fails is a loud error,
# and the founder's approved cover ships verbatim, unsliced.

OVERLONG_COVER = "Bakery queue on a Friday morning, the words just won't come out"
FRAGMENT_COVER = "Bakery queue, words won't come and"
LONG_APPROVED_COVER = (
    "The founder approved this exact cover line for the opening frame, "
    "every single word of it, exactly as written"
)


def _plan_with_cover(monkeypatch, cover):
    import ai_service

    async def capture(system_message, prompt, context, **kwargs):
        return {
            "hook_line": "Naming what I felt never worked.",
            "script": "One sentence each night helped me understand the pattern. I stopped guessing what the day had done to me, and the tight feeling in my chest eased.",
            "cover_text": cover,
            "beat_timeline": [{"start": 0, "end": 3, "label": "hook", "text": "t"}],
            "visual_direction": "v", "demo_brief": "d",
            "voice_direction": "vd", "sound_direction": "sd", "claims_used": [],
        }

    monkeypatch.setattr(ai_service, "_chat_json", capture)
    return asyncio.run(ai_service.generate_creative_plan(
        profile={"brand_name": "Journal"}, template={"name": "T", "hook_seconds": 3},
        duration_seconds=15,
    ))


def test_plan_stores_no_cover_when_the_draft_runs_long(monkeypatch):
    result = _plan_with_cover(monkeypatch, OVERLONG_COVER)
    # Never the sliced draft: no cover at all, left to the Suggest flow.
    assert result["cover_text"] == ""


def test_plan_stores_no_cover_when_the_draft_is_a_fragment(monkeypatch):
    result = _plan_with_cover(monkeypatch, FRAGMENT_COVER)
    assert result["cover_text"] == ""


def test_plan_stores_a_valid_draft_cover_verbatim(monkeypatch):
    result = _plan_with_cover(monkeypatch, COVER)
    assert result["cover_text"] == COVER


def test_post_kit_refuses_an_over_length_model_cover(monkeypatch):
    import ai_service
    import hashtag_volume
    monkeypatch.setattr(ai_service, "_chat_json", AsyncMock(return_value={
        "caption": "I stopped fighting my phone and cleared one list instead — you?",
        "hashtags": ["#one", "#two", "#three", "#four", "#five"],
        "cover_text": OVERLONG_COVER,
    }))
    monkeypatch.setattr(
        hashtag_volume, "lookup_hashtag_counts", AsyncMock(return_value={}))
    project = {"hook_line": HOOK, "script": SCRIPT, "cta": ""}
    with pytest.raises(RuntimeError, match="cover"):
        asyncio.run(ai_service.generate_post_kit(
            project, {"brand_name": "Voice Journal", "status": "approved"}))


def test_post_kit_ships_a_long_approved_cover_verbatim(monkeypatch):
    import ai_service
    import hashtag_volume
    assert len(LONG_APPROVED_COVER) > 100
    monkeypatch.setattr(ai_service, "_chat_json", AsyncMock(return_value={
        "caption": "I stopped fighting my phone and cleared one list instead — you?",
        "hashtags": ["#one", "#two", "#three", "#four", "#five"],
        "cover_text": "A different unseen draft",
    }))
    monkeypatch.setattr(
        hashtag_volume, "lookup_hashtag_counts", AsyncMock(return_value={}))
    project = {
        "hook_line": HOOK, "script": SCRIPT, "cta": "",
        "cover_text": LONG_APPROVED_COVER,
    }
    out = asyncio.run(ai_service.generate_post_kit(
        project, {"brand_name": "Voice Journal", "status": "approved"}))
    # ADR 0145 verbatim means verbatim: past the old 100-char slice,
    # the founder's exact words ship whole.
    assert out["cover_text"] == LONG_APPROVED_COVER


def test_plan_prompt_asks_for_three_to_five_words(monkeypatch):
    import ai_service
    prompts = []

    async def capture(system_message, prompt, context, **kwargs):
        prompts.append(prompt)
        return {
            "hook_line": "Naming what I felt never worked.",
            "script": "One sentence each night helped me understand the pattern. I stopped guessing what the day had done to me, and the tight feeling in my chest eased.",
            "beat_timeline": [{"start": 0, "end": 3, "label": "hook", "text": "t"}],
            "visual_direction": "v", "demo_brief": "d",
            "voice_direction": "vd", "sound_direction": "sd", "claims_used": [],
        }

    monkeypatch.setattr(ai_service, "_chat_json", capture)
    asyncio.run(ai_service.generate_creative_plan(
        profile={"brand_name": "Journal"}, template={"name": "T", "hook_seconds": 3},
        duration_seconds=15,
    ))
    # Every cover-writing surface reads the tightened ask: the shared
    # block rides in the plan prompt, and no plan prompt still carries
    # the old sizing.
    assert any("3 to 5 words" in prompt for prompt in prompts)
    assert all("under eight" not in prompt for prompt in prompts)
    assert all("under 8 words" not in prompt for prompt in prompts)
