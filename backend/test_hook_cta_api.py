"""
Tests for the Hook + CTA page's backend (ADR 0244).

The claims under test:
  * A hook-cta draft is a VIDEO project (kind "video") carrying the
    surface marker, so History, post kits and analytics treat its
    renders as video renders — never a story, never a new kind.
  * The hook endpoint writes ONE goal-first hook line plus its render
    direction through the finished-sentence gate (ADR 0231) and the
    ADR 0238 word budgets re-homed in ai_spoken (4s ≤ 9 words,
    5s ≤ 12 words) — and never a script.
  * The generate endpoint submits through the exact-duration path, so
    a 4-second pick records trim_to_seconds 4 against the models' 5s
    floor (the beat trim itself is pinned in test_beat_trim.py), and
    a 5-second pick records no trim.
  * The page's endpoints refuse other surfaces' projects in words
    that send the founder to the right page.
"""
import asyncio
import importlib
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

ANON = "anonymous"
HOOK = "I'm trying to clear my head before bed but my thoughts race."
assert len(HOOK.split()) == 12  # exactly the 5-second budget (ADR 0238)


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-hookcta-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""

    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    original = (server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR)
    server.pipeline.VIDEOS_DIR = Path(tmpdir) / "videos"
    server.pipeline.GENERATED_DIR = Path(tmpdir) / "generated"
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    server.pipeline.GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    asyncio.run(server.init_db())
    try:
        yield server
    finally:
        server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR = original
        sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


def _profile(api, name, approve=True):
    from models import ApproveAppProfileRequest, BrandProfileCreateRequest
    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name, app_category="Wellness",
        brand_description="Speak your journal entry instead of writing it.",
        target_audience="people too tired to write at night",
        core_features=["Voice entries", "Emotion check-ins"],
        usage_moments=["Winding down after work"],
        outcome_statements=[{
            "outcome": "Clearing the day's thoughts out loud",
            "who_feels_it": "people too tired to write",
            "from_feature": "Voice entries",
            "how_it_helps": "Talking replaces writing the entry",
        }],
    ), user_id=ANON))
    if approve:
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    return profile


def _hook_cta(api, name, **kwargs):
    from models import CreateHookCtaProjectRequest
    profile = _profile(api, name)
    project = _run(api.create_hook_cta_project(payload=CreateHookCtaProjectRequest(
        brand_profile_id=profile["id"], **kwargs,
    ), user_id=ANON))
    return project, profile


def _hook_reply(**overrides):
    reply = {
        "hook_line": HOOK,
        "hook_action": "Jerks upright in her chair, both hands flying up as the thought lands.",
        "closing_action": "Leans in, eyebrows up, holding the look straight at the camera.",
        "location": "A quiet bedroom in the evening",
    }
    reply.update(overrides)
    return reply


def _stub_hook_model(api, monkeypatch, reply=None):
    async def fake_hook_line(project, profile):
        return _hook_reply(**(reply or {}))

    monkeypatch.setattr(api.ai_service, "generate_hook_line", fake_hook_line)


def _write_hook(api, project_id, monkeypatch, reply=None):
    from models import GenerateHookLineRequest
    _stub_hook_model(api, monkeypatch, reply)
    return _run(api.generate_hook_cta_hook(
        project_id, GenerateHookLineRequest(), ANON))


def _attach_face(api, project):
    """Attach a real character_reference so the identity resolver accepts it."""
    from models import now_iso
    face = Path(tempfile.mkdtemp(prefix="tiktok-hookcta-face-")) / "face.png"
    face.write_bytes(bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c626001000000ffff0300000600055d3866680000000049454e44ae426082"))
    asset_id = str(uuid.uuid4())
    now = now_iso()
    _run(api._execute(
        "INSERT INTO assets (id, brand_profile_id, kind, name, file_path, label,"
        " created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (asset_id, project["brand_profile_id"], "character_reference",
         "Founder face", str(face), "Founder face", now, now, ANON)))
    assets = [{"asset_id": asset_id, "kind": "character_reference",
               "label": "Founder face", "file_path": str(face)}]
    _run(api._execute(
        "UPDATE studio_projects SET assets = ? WHERE id = ?",
        (json.dumps(assets), project["id"])))
    return assets


def _mock_submit(api, monkeypatch):
    calls = []

    async def fake_generate_video(**kwargs):
        calls.append(kwargs)
        return {"id": f"job-{len(calls)}", "status": "queued",
                "usage": {"cost": 0.05}}

    monkeypatch.setattr(api, "generate_video", fake_generate_video)
    return calls


def _silence_poster(api, monkeypatch):
    async def no_poster(background_tasks, generation_id, user_id):
        return None

    monkeypatch.setattr(api, "_schedule_poster", no_poster)


# ---------------------------------------------------------------- create

class TestCreateHookCtaProject:
    def test_create_is_a_video_project_with_the_surface_marker(self, api):
        project, profile = _hook_cta(api, "Create Marker")
        assert project["kind"] == "video"
        assert project["surface"] == "hook_cta"
        # The settled default length (ADR 0244): the longer beat.
        assert project["duration_seconds"] == 5
        assert project["frame_count"] == 1
        assert project["status"] == "draft"
        assert project["audience"] == profile["target_audience"]
        row = _run(api._fetch_one(
            "SELECT kind, surface, hook_seconds FROM studio_projects WHERE id = ?",
            (project["id"],)))
        assert row["kind"] == "video" and row["surface"] == "hook_cta"
        # Stored at the shared machinery's widest hook window so the
        # line is never re-sliced into a script on read (ADR 0244).
        assert row["hook_seconds"] == 4

    def test_create_accepts_the_four_second_pick(self, api):
        project, _ = _hook_cta(api, "Create Four", frame_seconds=4)
        assert project["duration_seconds"] == 4

    def test_create_refuses_a_length_outside_the_pick(self, api):
        from models import CreateHookCtaProjectRequest
        profile = _profile(api, "Create Length")
        with pytest.raises(HTTPException) as exc:
            _run(api.create_hook_cta_project(payload=CreateHookCtaProjectRequest(
                brand_profile_id=profile["id"], frame_seconds=3,
            ), user_id=ANON))
        assert exc.value.status_code == 400

    def test_create_refuses_an_unapproved_profile(self, api):
        from models import CreateHookCtaProjectRequest
        profile = _profile(api, "Create Unapproved", approve=False)
        with pytest.raises(HTTPException):
            _run(api.create_hook_cta_project(payload=CreateHookCtaProjectRequest(
                brand_profile_id=profile["id"],
            ), user_id=ANON))


# ------------------------------------------------------------------ hook

class TestHookEndpoint:
    def test_hook_saves_the_line_the_strategy_and_no_script(self, api, monkeypatch):
        project, _ = _hook_cta(api, "Hook Saves")
        out = _write_hook(api, project["id"], monkeypatch)
        assert out["hook_line"] == HOOK
        # No script is ever written on this page.
        assert not (out["script"] or "").strip()
        strategy = out["strategy"]
        segments = {s["role"]: s for s in strategy["segments"]}
        assert segments["hook"]["script"] == HOOK
        assert segments["hook"]["seconds"] == 4
        assert segments["hook"]["action"]
        # The closing beat is direction only — it carries no words.
        assert segments["middle"]["script"] == ""
        assert segments["middle"]["action"]
        # The shared strategy normalizer punctuates the scene's place.
        assert strategy["scene"]["location"] == "A quiet bedroom in the evening."

    def test_hook_pick_of_four_shortens_the_draft(self, api, monkeypatch):
        from models import GenerateHookLineRequest
        project, _ = _hook_cta(api, "Hook Pick")
        _stub_hook_model(api, monkeypatch)
        out = _run(api.generate_hook_cta_hook(
            project["id"], GenerateHookLineRequest(frame_seconds=4), ANON))
        assert out["duration_seconds"] == 4

    def test_hook_refuses_a_wizard_project(self, api):
        from models import CreateStudioProjectRequest, GenerateHookLineRequest
        profile = _profile(api, "Hook Wizard Refusal")
        wizard = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"]), user_id=ANON))
        with pytest.raises(HTTPException) as exc:
            _run(api.generate_hook_cta_hook(
                wizard["id"], GenerateHookLineRequest(), ANON))
        assert exc.value.status_code == 400
        assert "Create Video" in exc.value.detail

    def test_hook_refuses_a_legacy_story_project(self, api):
        from models import CreateStudioProjectRequest, GenerateHookLineRequest
        profile = _profile(api, "Hook Story Refusal")
        story = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"], kind="story"), user_id=ANON))
        with pytest.raises(HTTPException) as exc:
            _run(api.generate_hook_cta_hook(
                story["id"], GenerateHookLineRequest(), ANON))
        assert exc.value.status_code == 400
        assert "History" in exc.value.detail

    def test_hook_refuses_a_missing_project(self, api):
        from models import GenerateHookLineRequest
        with pytest.raises(HTTPException) as exc:
            _run(api.generate_hook_cta_hook(
                "no-such-project", GenerateHookLineRequest(), ANON))
        assert exc.value.status_code == 404


# ------------------------------------------------- the length pick (PATCH)

class TestHookCtaLengthPatch:
    """The page's picks autosave through the shared studio PATCH, and the
    hook length is one of those picks. A hook runs 4 or 5 seconds — the
    wizard's duration rules (clamp into 8/10/12/15, and the 409 that
    protects a written plan's timeline) must not reach this surface:
    clamped, the pick silently becomes 8s and the hook endpoint refuses
    it; refused, the autosave fails on every retry, the page's edits
    never clear, and the render gate reads them as still saving —
    the Generate button stays disabled forever (Kasra's live report,
    Nov 20 2026)."""

    def test_a_length_pick_saves_as_itself(self, api):
        from models import UpdateStudioProjectRequest
        project, _profile = _hook_cta(api, "Length Pick Saves")
        out = _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(duration_seconds=4), ANON))
        assert out["duration_seconds"] == 4

    def test_a_length_pick_after_the_hook_still_saves(self, api, monkeypatch):
        from models import UpdateStudioProjectRequest
        project, _profile = _hook_cta(api, "Length Pick After Hook")
        _write_hook(api, project["id"], monkeypatch)
        out = _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(duration_seconds=4), ANON))
        assert out["duration_seconds"] == 4

    def test_a_length_outside_the_pick_is_refused_in_the_pages_words(self, api):
        from models import UpdateStudioProjectRequest
        project, _profile = _hook_cta(api, "Length Pick Refused")
        with pytest.raises(HTTPException) as exc:
            _run(api.update_studio_project(
                project["id"], UpdateStudioProjectRequest(duration_seconds=9), ANON))
        assert exc.value.status_code == 400
        assert "A hook runs 4 or 5 seconds." in exc.value.detail

    def test_a_wizard_project_keeps_the_wizard_clamp(self, api):
        from models import CreateStudioProjectRequest, UpdateStudioProjectRequest
        profile = _profile(api, "Length Wizard Clamp")
        wizard = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"]), user_id=ANON))
        out = _run(api.update_studio_project(
            wizard["id"], UpdateStudioProjectRequest(duration_seconds=4), ANON))
        assert out["duration_seconds"] == 8


# ------------------------------------------------------- the model call

PROFILE_FACTS = {
    "name": "Vocolens",
    "category": "Wellness",
    "description": "Speak your journal entry instead of writing it.",
    "platforms": [],
    "features": ["Voice entries"],
    "use_cases": ["Winding down after work"],
    "problems": [],
    "desired_outcomes": ["Clearing the day's thoughts out loud"],
    "outcome_statements": [],
    "differentiators": "",
    "known_limitations": "",
}


def _stub_chat(monkeypatch, replies):
    import ai_service
    queue = list(replies)
    calls = []

    async def fake_chat(**kwargs):
        calls.append(kwargs)
        return queue.pop(0) if queue else {}

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    return calls


def _draft_calls(calls):
    """The hook's own draft-loop calls (context "Hook line").

    Since ADR 0323 the generation continues past the accepted draft —
    the bake-off's candidates call and the craft correction are
    separate calls with their own contexts — so the draft loop's
    bounded-correction counts are read on its own calls, and the new
    stages are counted in their own tests below.
    """
    return [c for c in calls if c.get("context") == "Hook line"]


def _stub_chat_by_context(monkeypatch, replies_by_context):
    """Script _chat_json by call context (ADR 0323's stages).

    A reply value may be a dict (returned), an Exception (raised) or
    a callable taking the call kwargs. Unscripted contexts return {}.
    """
    import ai_service
    calls = []

    async def fake_chat(**kwargs):
        calls.append(kwargs)
        reply = replies_by_context.get(kwargs.get("context"), {})
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            return reply(kwargs)
        return reply

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    return calls


def _hook_project(**overrides):
    project = {
        "id": "hook-cta-1",
        "kind": "video",
        "surface": "hook_cta",
        "duration_seconds": 5,
        "camera_setup": "handheld",
        "location": "",
        "visual_direction": "",
    }
    project.update(overrides)
    return project


class TestGenerateHookLine:
    def test_the_budgets_are_the_settled_numbers(self):
        import ai_spoken
        # ADR 0238's story budgets, re-homed (ADR 0244): the 3-second
        # beat died with stories; 4 and 5 seconds are the page's pick.
        assert ai_spoken.SHORT_HOOK_SECONDS == (4, 5)
        assert ai_spoken.short_hook_word_budget(4) == 9
        assert ai_spoken.short_hook_word_budget(5) == 12

    def test_a_regenerate_names_the_line_on_file_and_refuses_its_repeat(self, monkeypatch):
        import ai_service
        # ADR 0343: the founder pressed Generate a new hook with a
        # line already on file. The prompt names that line as an
        # exclusion, and a reply that hands it straight back is a
        # hard failure the loop corrects — the button never reads
        # as doing nothing again.
        new_hook = "I'm trying to stop replaying today before it steals tonight."
        calls = _stub_chat(monkeypatch, [
            _hook_reply(hook_line=HOOK), _hook_reply(hook_line=new_hook)])
        out = _run(ai_service.generate_hook_line(
            _hook_project(hook_line=HOOK), PROFILE_FACTS))
        assert out["hook_line"] == new_hook
        assert "ALREADY ON FILE" in calls[0]["prompt"]
        assert HOOK in calls[0]["prompt"]
        assert len(_draft_calls(calls)) == 2
        assert "repeats the hook already on file" in str(calls[1])

    def test_a_first_generation_prompt_carries_no_already_on_file_block(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [_hook_reply()])
        _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))
        assert "ALREADY ON FILE" not in calls[0]["prompt"]

    def test_a_good_reply_returns_the_line_and_its_direction(self, monkeypatch):
        import ai_service
        _stub_chat(monkeypatch, [_hook_reply()])
        out = _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))
        assert out["hook_line"] == HOOK
        assert out["hook_action"].startswith("Jerks upright")
        assert out["closing_action"].startswith("Leans in")
        assert out["location"] == "A quiet bedroom in the evening"

    def test_an_over_budget_reply_is_corrected_once(self, monkeypatch):
        import ai_service
        long_hook = " ".join(["word"] * 13) + "."
        calls = _stub_chat(monkeypatch, [
            _hook_reply(hook_line=long_hook), _hook_reply()])
        out = _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))
        assert out["hook_line"] == HOOK
        assert len(_draft_calls(calls)) == 2
        assert "correction" in str(calls[1]).lower() or "12 words" in str(calls[1])

    def test_a_reply_corrected_twice_still_lands(self, monkeypatch):
        import ai_service
        # ADR 0301: the loop runs three attempts — Sonnet 5.5's first
        # live hook missed the 4-second word budget by one word on
        # both of the old loop's two attempts, correction named, and
        # the founder got a failure for a one-word miss.
        long_hook = " ".join(["word"] * 13) + "."
        calls = _stub_chat(monkeypatch, [
            _hook_reply(hook_line=long_hook),
            _hook_reply(hook_line=long_hook),
            _hook_reply()])
        out = _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))
        assert out["hook_line"] == HOOK
        assert len(_draft_calls(calls)) == 3

    def test_a_persistently_over_budget_reply_is_refused(self, monkeypatch):
        import ai_service
        long_hook = " ".join(["word"] * 13) + "."
        _stub_chat(monkeypatch, [
            _hook_reply(hook_line=long_hook), _hook_reply(hook_line=long_hook)])
        with pytest.raises(RuntimeError):
            _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))

    def test_an_unfinished_sentence_is_refused(self, monkeypatch):
        import ai_service
        fragment = "I'm trying to clear my head before bed and my thoughts"
        _stub_chat(monkeypatch, [
            _hook_reply(hook_line=fragment), _hook_reply(hook_line=fragment)])
        with pytest.raises(RuntimeError):
            _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))

    def test_the_four_second_budget_is_nine_words(self, monkeypatch):
        import ai_service
        ten_words = "I'm trying to sleep but my mind will not stop racing tonight."
        assert len(ten_words.split()) == 12  # over both budgets' edge use below
        nine = "I'm trying to sleep but my mind races on."
        assert len(nine.split()) == 9
        _stub_chat(monkeypatch, [
            _hook_reply(hook_line=ten_words), _hook_reply(hook_line=nine)])
        out = _run(ai_service.generate_hook_line(
            _hook_project(duration_seconds=4), PROFILE_FACTS))
        assert out["hook_line"] == nine


# ------------------------------------------- ADR 0323: the plan's machinery

# Craft totals against an empty script (the demo is not spoken words),
# measured on the shipped scorer: the stub draft HOOK scores 55, the
# strong line 60, the low line 48. The question line scores 58 — above
# the draft — but breaks the statement default, so the gate, not the
# score, must decide wherever it appears.
STRONG_HOOK = "I'm trying to name why my chest tightens every single night."
LOW_HOOK = "I'm trying to stop replaying today before it steals tonight too."
GATED_QUESTION_HOOK = "Why does my chest tighten every single night before bed?"


class TestGenerateHookLineBakeOff:
    """The hook bake-off comes to Hook + CTA (ADR 0323, Kasra's order
    to match Create Video's framework): after the draft passes the
    page's hard gates, three alternatives are written for the same
    story — here the demo that follows — the same gates filter them,
    and the craft scorer picks the strongest survivor. The draft is
    the incumbent: a candidate ships only when it scores strictly
    higher, so the bake-off can never make the hook worse."""

    def test_a_stronger_clean_candidate_replaces_the_draft_hook(self, monkeypatch):
        import ai_service
        _stub_chat_by_context(monkeypatch, {
            "Hook line": _hook_reply(),
            "Creative plan hook candidates": {"hooks": [LOW_HOOK, STRONG_HOOK]},
        })
        out = _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))
        assert out["hook_line"] == STRONG_HOOK
        # The direction was written for the story's moment, which the
        # candidates share (the plan's own precedent: its direction
        # survives a hook swap the same way).
        assert out["hook_action"].startswith("Jerks upright")
        assert out["location"] == "A quiet bedroom in the evening"

    def test_a_gated_candidate_never_wins_even_when_it_outscores_the_draft(self, monkeypatch):
        import ai_service
        calls = _stub_chat_by_context(monkeypatch, {
            "Hook line": _hook_reply(),
            "Creative plan hook candidates": {"hooks": [GATED_QUESTION_HOOK]},
        })
        out = _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))
        assert out["hook_line"] == HOOK
        # Every candidate broke a gate, so the best of them got the
        # bake-off's one bounded correction — unscripted here, it
        # returns nothing usable and the draft stands.
        corrections = [c for c in calls if c.get("context") == "Creative plan hook correction"]
        assert len(corrections) == 1

    def test_all_broken_candidates_get_one_correction_and_a_clean_fix_ships(self, monkeypatch):
        import ai_service
        _stub_chat_by_context(monkeypatch, {
            "Hook line": _hook_reply(),
            "Creative plan hook candidates": {"hooks": [GATED_QUESTION_HOOK]},
            "Creative plan hook correction": {"hook_line": STRONG_HOOK},
        })
        out = _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))
        assert out["hook_line"] == STRONG_HOOK

    def test_a_failed_candidates_call_keeps_the_draft_byte_for_byte(self, monkeypatch):
        import ai_service
        _stub_chat_by_context(monkeypatch, {
            "Hook line": _hook_reply(),
            "Creative plan hook candidates": RuntimeError("provider down"),
        })
        out = _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))
        assert out == _hook_reply()

    def test_the_candidates_prompt_carries_the_demo_as_the_story(self, monkeypatch):
        import ai_service
        calls = _stub_chat_by_context(monkeypatch, {
            "Hook line": _hook_reply(),
            "Creative plan hook candidates": {"hooks": []},
        })
        _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))
        candidates = [c for c in calls if c.get("context") == "Creative plan hook candidates"]
        assert len(candidates) == 1
        prompt = candidates[0]["prompt"]
        assert "HOOK BAKE-OFF" in prompt
        # The demo stands in as the hook's story: the candidates open
        # for the demo that answers them, anchored on the profile's
        # promised outcome.
        assert "THE DEMO THAT FOLLOWS" in prompt
        assert "Clearing the day's thoughts out loud" in prompt


class TestGenerateHookLineCraftPass:
    """The craft correction comes to Hook + CTA (ADR 0323, ADR 0115's
    pattern adapted to the hook package): when the winning hook
    scores below the plan's bar — the same fraction of the total this
    surface can reach, the two script dimensions being structurally
    silent here — ONE correction, steered by the weakest dimensions'
    findings, rewrites the hook line and its direction as one
    package. It ships only when it passes the same hard gates and
    scores strictly higher; it never refuses the hook."""

    CORRECTED_ACTION = "Counts the tightness out on her fingers, palm pressed to her chest."

    def _script(self, monkeypatch, craft_reply):
        return _stub_chat_by_context(monkeypatch, {
            "Hook line": _hook_reply(),
            "Creative plan hook candidates": {"hooks": []},
            "Hook line craft correction": craft_reply,
        })

    def test_a_weak_hook_gets_one_findings_steered_correction(self, monkeypatch):
        import ai_service
        calls = self._script(monkeypatch, _hook_reply(
            hook_line=STRONG_HOOK, hook_action=self.CORRECTED_ACTION))
        out = _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))
        assert out["hook_line"] == STRONG_HOOK
        # The package ships whole: the direction was rewritten for
        # the corrected line, not left describing the draft's moment.
        assert out["hook_action"] == self.CORRECTED_ACTION
        corrections = [c for c in calls if c.get("context") == "Hook line craft correction"]
        assert len(corrections) == 1
        prompt = corrections[0]["prompt"]
        assert "CRAFT CORRECTION" in prompt
        # The findings are the weakest dimensions' own next steps —
        # the hook dimension's lift is the ADR 0316 instruction.
        assert "Open on the moment, one concrete detail" in prompt

    def test_a_correction_that_scores_no_higher_keeps_the_draft(self, monkeypatch):
        import ai_service
        self._script(monkeypatch, _hook_reply(
            hook_line=LOW_HOOK, hook_action=self.CORRECTED_ACTION))
        out = _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))
        assert out == _hook_reply()

    def test_a_correction_that_breaks_a_gate_keeps_the_draft(self, monkeypatch):
        import ai_service
        self._script(monkeypatch, _hook_reply(hook_line=GATED_QUESTION_HOOK))
        out = _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))
        assert out == _hook_reply()

    def test_a_failed_craft_call_keeps_the_draft(self, monkeypatch):
        import ai_service
        self._script(monkeypatch, RuntimeError("provider down"))
        out = _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))
        assert out == _hook_reply()

    def test_a_strong_hook_gets_no_craft_call(self, monkeypatch):
        import ai_service
        calls = _stub_chat_by_context(monkeypatch, {
            "Hook line": _hook_reply(hook_line=STRONG_HOOK),
            "Creative plan hook candidates": {"hooks": []},
        })
        out = _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))
        assert out["hook_line"] == STRONG_HOOK
        assert not [c for c in calls if c.get("context") == "Hook line craft correction"]


class TestHookDirectionWording:
    """The hook's opening direction is written the Create Video way
    (ADR 0323): anchored in the scene — the place, the gesture already
    mid-motion — never led by the head and eyes, which pushed the
    camera in and overrode the render's wide framing. The gesture
    rule and the start-wide framing ride the same bullet."""

    def test_the_hook_action_is_a_scene_not_a_face(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [_hook_reply()])
        _run(ai_service.generate_hook_line(_hook_project(), PROFILE_FACTS))
        prompt = calls[0]["prompt"]
        assert "head already lifting" not in prompt
        assert "eyes already rising" not in prompt
        assert "already mid-gesture" in prompt
        assert "starts WIDE" in prompt
        assert "landing close" in prompt or "landing at the close" in prompt
        # The gesture rule stands: a face-only change never counts,
        # and the face rides the gesture.
        assert "never counts as the opening beat" in prompt
        assert "the face rides the gesture" in prompt


# -------------------------------------------------------------- generate

class TestGenerateHook:
    def _ready(self, api, monkeypatch, name, **create_kwargs):
        from models import GenerateHookLineRequest
        project, _ = _hook_cta(api, name, **create_kwargs)
        _stub_hook_model(api, monkeypatch)
        _run(api.generate_hook_cta_hook(
            project["id"], GenerateHookLineRequest(), ANON))
        _attach_face(api, project)
        return project

    def test_generate_refuses_before_a_hook_exists(self, api):
        from models import GenerateHookRequest
        project, _ = _hook_cta(api, "Generate No Hook")
        with pytest.raises(HTTPException) as exc:
            _run(api.generate_hook_cta(
                project["id"], GenerateHookRequest(), ANON))
        assert exc.value.status_code == 409
        assert "hook" in exc.value.detail.lower()

    def test_a_four_second_hook_records_a_trim_to_four(self, api, monkeypatch):
        from models import GenerateHookRequest
        project = self._ready(api, monkeypatch, "Generate Four", frame_seconds=4)
        calls = _mock_submit(api, monkeypatch)
        _silence_poster(api, monkeypatch)
        generation = _run(api.generate_hook_cta(
            project["id"], GenerateHookRequest(), ANON))
        # The submit asks for the pick's own seconds (exact-duration).
        assert calls[0]["duration"] == 4
        row = _run(api._fetch_one(
            "SELECT trim_to_seconds, duration, requested_duration"
            " FROM generations WHERE id = ?",
            (generation["id"],)))
        assert row["duration"] == 4
        assert row["requested_duration"] == 4
        assert row["trim_to_seconds"] == 4

    def test_a_five_second_hook_records_no_trim(self, api, monkeypatch):
        from models import GenerateHookRequest
        project = self._ready(api, monkeypatch, "Generate Five")
        calls = _mock_submit(api, monkeypatch)
        _silence_poster(api, monkeypatch)
        generation = _run(api.generate_hook_cta(
            project["id"], GenerateHookRequest(), ANON))
        assert calls[0]["duration"] == 5
        row = _run(api._fetch_one(
            "SELECT trim_to_seconds FROM generations WHERE id = ?",
            (generation["id"],)))
        # At the floor the render already IS the beat: nothing to cut.
        assert row["trim_to_seconds"] == 0

    def test_generate_refuses_an_unknown_model(self, api, monkeypatch):
        from models import GenerateHookRequest
        project = self._ready(api, monkeypatch, "Generate Model")
        with pytest.raises(HTTPException) as exc:
            _run(api.generate_hook_cta(
                project["id"], GenerateHookRequest(model="no-such-model"), ANON))
        assert exc.value.status_code == 400

    def test_the_render_is_a_video_kind_generation(self, api, monkeypatch):
        from models import GenerateHookRequest
        project = self._ready(api, monkeypatch, "Generate Kind")
        _mock_submit(api, monkeypatch)
        _silence_poster(api, monkeypatch)
        generation = _run(api.generate_hook_cta(
            project["id"], GenerateHookRequest(), ANON))
        # History reads the render's kind from its project: video, so
        # the post kit and analytics treat it as a video render.
        history = _run(api.generation_history(user_id=ANON))
        mine = [g for g in history["generations"] if g["id"] == generation["id"]]
        assert mine and mine[0]["project_kind"] == "video"


# ------------------------------------------------------------- voice mode

class TestVoiceMode:
    """The presenter voice pick (ADR 0246, relabeled and re-defaulted
    by ADR 0248): the character talks (voice with lip movement), or
    the character stays silent (no voice, and no lip movement at
    all). A fresh project starts silent (ADR 0248 — Kasra's ruling:
    silence is the starting point, talking is the opt-in); a project
    that already carries a pick keeps it. The pick lives on the
    project row, saves through the same studio PATCH as every other
    pick, and a silent project submits with audio off and a prompt
    that says plainly the presenter does not speak and the lips do
    not move."""

    def test_a_fresh_project_reads_silent(self, api):
        project, _profile = _hook_cta(api, "Voice Default")
        assert project["voice_mode"] == "silent"

    def test_an_existing_talking_project_keeps_its_pick(self, api):
        from models import UpdateStudioProjectRequest
        project, _profile = _hook_cta(api, "Voice Existing Talking")
        _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(voice_mode="talking"), ANON))
        fresh, _profile = _hook_cta(api, "Voice Fresh Neighbour")
        assert fresh["voice_mode"] == "silent"
        reread = _run(api.get_studio_project(project["id"], ANON))
        assert reread["voice_mode"] == "talking"

    def test_the_pick_saves_and_reads_back(self, api):
        from models import UpdateStudioProjectRequest
        project, _profile = _hook_cta(api, "Voice Pick Saves")
        out = _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(voice_mode="silent"), ANON))
        assert out["voice_mode"] == "silent"
        fresh = _run(api.get_studio_project(project["id"], ANON))
        assert fresh["voice_mode"] == "silent"
        back = _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(voice_mode="talking"), ANON))
        assert back["voice_mode"] == "talking"

    def test_the_pick_saves_on_a_wizard_project_too(self, api):
        from models import CreateStudioProjectRequest, UpdateStudioProjectRequest
        profile = _profile(api, "Voice Wizard Pick")
        wizard = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"]), user_id=ANON))
        assert wizard["voice_mode"] == "silent"
        out = _run(api.update_studio_project(
            wizard["id"], UpdateStudioProjectRequest(voice_mode="silent"), ANON))
        assert out["voice_mode"] == "silent"

    def test_an_unknown_voice_value_is_refused(self, api):
        from models import UpdateStudioProjectRequest
        project, _profile = _hook_cta(api, "Voice Refused")
        with pytest.raises(HTTPException) as exc:
            _run(api.update_studio_project(
                project["id"], UpdateStudioProjectRequest(voice_mode="loud"), ANON))
        assert exc.value.status_code == 400

    def test_a_silent_hook_submits_audio_off_and_says_so(self, api, monkeypatch):
        from models import GenerateHookRequest, UpdateStudioProjectRequest
        project = TestGenerateHook()._ready(api, monkeypatch, "Voice Silent Submit")
        _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(voice_mode="silent"), ANON))
        calls = _mock_submit(api, monkeypatch)
        _silence_poster(api, monkeypatch)
        _run(api.generate_hook_cta(project["id"], GenerateHookRequest(), ANON))
        assert calls[0]["generate_audio"] is False
        prompt = calls[0]["prompt"]
        assert "does not speak" in prompt
        assert "no lip movement" in prompt
        assert "mouth stays closed and still" in prompt

    def test_a_talking_hook_carries_no_silence_direction(self, api, monkeypatch):
        from models import GenerateHookRequest, UpdateStudioProjectRequest
        project = TestGenerateHook()._ready(api, monkeypatch, "Voice Talking Submit")
        # A fresh project starts silent (ADR 0248); the talking pick
        # is this test's subject, so it is set on purpose.
        _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(voice_mode="talking"), ANON))
        calls = _mock_submit(api, monkeypatch)
        _silence_poster(api, monkeypatch)
        _run(api.generate_hook_cta(project["id"], GenerateHookRequest(), ANON))
        assert calls[0]["generate_audio"] is not False
        assert "does not speak" not in calls[0]["prompt"]


# --------------------------------------------------------- steering picks

# The outcome lines the fixture profile below carries: the evidenced
# statement first, then the flat desired outcomes.
STATEMENT_OUTCOME = "Clearing the day's thoughts out loud"
FLAT_OUTCOME = "Fall asleep without replaying the day"


def _steering_profile(api, name):
    from models import ApproveAppProfileRequest, BrandProfileCreateRequest
    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name, app_category="Wellness",
        brand_description="Speak your journal entry instead of writing it.",
        target_audience="people too tired to write at night",
        core_features=["Voice entries", "Emotion check-ins"],
        usage_moments=["Winding down after work"],
        desired_outcomes=[FLAT_OUTCOME],
        outcome_statements=[{
            "outcome": STATEMENT_OUTCOME,
            "who_feels_it": "people too tired to write",
            "from_feature": "Voice entries",
            "how_it_helps": "Talking replaces writing the entry",
        }],
    ), user_id=ANON))
    _run(api.approve_app_profile(
        profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    return profile


class TestHookSteeringPicks:
    """The founder's steering picks for the hook (ADR 0247): a focus
    (one of the app profile's own outcome lines — never an invented
    one), a tone (the project's tone column, a closed pick on this
    surface), and a shape (the app's choice, a question, or a
    statement). They ride the project row through the same studio
    PATCH as the voice pick, and like it they are picks, not plan
    content: saving one never moves the words already written."""

    def _draft(self, api, name):
        from models import CreateHookCtaProjectRequest
        profile = _steering_profile(api, name)
        project = _run(api.create_hook_cta_project(payload=CreateHookCtaProjectRequest(
            brand_profile_id=profile["id"],
        ), user_id=ANON))
        return project, profile

    def test_a_fresh_project_lets_the_app_choose_everything(self, api):
        project, _profile = self._draft(api, "Picks Fresh")
        assert project["hook_shape"] == "auto"
        assert project["hook_focus"] == ""
        assert not (project["tone"] or "")

    def test_the_picks_save_and_read_back(self, api):
        from models import UpdateStudioProjectRequest
        project, _profile = self._draft(api, "Picks Save")
        out = _run(api.update_studio_project(
            project["id"],
            UpdateStudioProjectRequest(
                hook_focus=STATEMENT_OUTCOME, hook_shape="question", tone="warm"),
            ANON))
        assert out["hook_focus"] == STATEMENT_OUTCOME
        assert out["hook_shape"] == "question"
        assert out["tone"] == "warm"
        fresh = _run(api.get_studio_project(project["id"], ANON))
        assert fresh["hook_focus"] == STATEMENT_OUTCOME
        assert fresh["hook_shape"] == "question"
        assert fresh["tone"] == "warm"

    def test_a_focus_from_the_flat_outcomes_saves(self, api):
        from models import UpdateStudioProjectRequest
        project, _profile = self._draft(api, "Picks Flat Focus")
        out = _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(hook_focus=FLAT_OUTCOME), ANON))
        assert out["hook_focus"] == FLAT_OUTCOME

    def test_a_focus_the_app_does_not_have_is_refused(self, api):
        from models import UpdateStudioProjectRequest
        project, _profile = self._draft(api, "Picks Focus Refused")
        with pytest.raises(HTTPException) as exc:
            _run(api.update_studio_project(
                project["id"],
                UpdateStudioProjectRequest(hook_focus="An outcome this app never promised"),
                ANON))
        assert exc.value.status_code == 400
        assert "outcome" in exc.value.detail.lower()

    def test_clearing_the_focus_saves_as_no_pick(self, api):
        from models import UpdateStudioProjectRequest
        project, _profile = self._draft(api, "Picks Focus Cleared")
        _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(hook_focus=STATEMENT_OUTCOME), ANON))
        out = _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(hook_focus=""), ANON))
        assert out["hook_focus"] == ""

    def test_an_unknown_shape_is_refused(self, api):
        from models import UpdateStudioProjectRequest
        project, _profile = self._draft(api, "Picks Shape Refused")
        with pytest.raises(HTTPException) as exc:
            _run(api.update_studio_project(
                project["id"], UpdateStudioProjectRequest(hook_shape="sideways"), ANON))
        assert exc.value.status_code == 400
        assert "Shape" in exc.value.detail

    def test_an_unknown_tone_is_refused_on_this_surface(self, api):
        from models import UpdateStudioProjectRequest
        project, _profile = self._draft(api, "Picks Tone Refused")
        with pytest.raises(HTTPException) as exc:
            _run(api.update_studio_project(
                project["id"], UpdateStudioProjectRequest(tone="loud"), ANON))
        assert exc.value.status_code == 400
        assert "Tone" in exc.value.detail

    def test_a_wizard_project_keeps_its_free_text_tone(self, api):
        from models import CreateStudioProjectRequest, UpdateStudioProjectRequest
        profile = _profile(api, "Picks Wizard Tone")
        wizard = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"]), user_id=ANON))
        out = _run(api.update_studio_project(
            wizard["id"],
            UpdateStudioProjectRequest(tone="Warm and a little playful"), ANON))
        assert out["tone"] == "Warm and a little playful"

    def test_the_picks_do_not_move_the_written_words(self, api, monkeypatch):
        from models import UpdateStudioProjectRequest
        project, _profile = self._draft(api, "Picks Words Stay")
        _write_hook(api, project["id"], monkeypatch)
        written = _run(api.get_studio_project(project["id"], ANON))
        assert written["script_version"] == 1
        out = _run(api.update_studio_project(
            project["id"],
            UpdateStudioProjectRequest(
                hook_focus=STATEMENT_OUTCOME, hook_shape="question", tone="bold"),
            ANON))
        # A pick is not a content edit (the voice pick's rule, ADR
        # 0246): no version bump, no un-readying, the line untouched.
        assert out["script_version"] == 1
        assert out["status"] == "draft"
        assert out["hook_line"] == written["hook_line"]


STEERING_PROFILE = {
    **PROFILE_FACTS,
    "desired_outcomes": [FLAT_OUTCOME],
    "outcome_statements": [{"outcome": STATEMENT_OUTCOME, "from_feature": "Voice entries"}],
}

QUESTION_HOOK = "Why do my thoughts race the moment I lie down at night?"
assert len(QUESTION_HOOK.split()) == 12  # exactly the 5-second budget
LONG_QUESTION = "Why do my thoughts race every night when I lie down in bed?"
assert len(LONG_QUESTION.split()) == 13  # one word over the 5-second budget


class TestGenerateHookLineSteering:
    """The picks in the prompt (ADR 0247): unpicked, the prompt is
    byte-for-byte the one generate_hook_line has always built;
    picked, exactly one steering block joins it — and the shape is
    enforced beside the budgets, never instead of them."""

    def test_the_outcome_lines_flatten_statements_first(self):
        import ai_service
        assert ai_service.profile_outcome_lines(STEERING_PROFILE) == [
            STATEMENT_OUTCOME, FLAT_OUTCOME]
        assert ai_service.profile_outcome_lines(PROFILE_FACTS) == [
            "Clearing the day's thoughts out loud"]

    def test_the_focus_lines_never_offer_a_fragment(self):
        """ADR 0307: the pick vocabulary drops the chopped pieces an old
        profile still stores — "triggers", "and growth over time",
        "from your own words" — while the raw lines stay whole for the
        refresh's avoid list."""
        import ai_service
        profile = {
            "outcome_statements": [
                {"outcome": "See your own rhythms", "from_feature": "Patterns"},
                {"outcome": "triggers", "from_feature": "Patterns"},
            ],
            "desired_outcomes": [
                "and growth over time",
                "from your own words",
                "Fall asleep without replaying the day",
            ],
        }
        assert ai_service.profile_focus_lines(profile) == [
            "See your own rhythms",
            "Fall asleep without replaying the day",
        ]
        assert "triggers" in ai_service.profile_outcome_lines(profile)

    def test_the_focus_lines_stop_at_six(self):
        """Kasra's order (Nov 23 2026): the Focus pick shows six lines
        at a time — the first six that stand alone, never more."""
        import ai_service
        profile = {
            "desired_outcomes": [
                f"Outcome number {word} stands alone"
                for word in ["one", "two", "three", "four", "five", "six", "seven", "eight"]
            ],
        }
        lines = ai_service.profile_focus_lines(profile)
        assert len(lines) == 6
        assert lines[-1] == "Outcome number six stands alone"

    def test_the_focus_lines_stop_at_six(self):
        """ADR 0307 (Kasra's order, Nov 23 2026): the pick shows six
        lines at a time — the first six that stand alone, in the
        profile's own order; the rest are not offered."""
        import ai_service
        profile = {
            "desired_outcomes": [
                "Fall asleep without replaying the day",
                "See your own rhythms",
                "Name the feeling in plain words",
                "Spot the pattern before it builds",
                "End the day feeling settled",
                "Trust what your body is saying",
                "Carry the calm into the morning",
                "Notice the shift as it happens",
            ],
        }
        assert ai_service.profile_focus_lines(profile) == [
            "Fall asleep without replaying the day",
            "See your own rhythms",
            "Name the feeling in plain words",
            "Spot the pattern before it builds",
            "End the day feeling settled",
            "Trust what your body is saying",
        ]

    def test_unpicked_the_prompt_is_the_prompt_it_always_was(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [_hook_reply()])
        out = _run(ai_service.generate_hook_line(_hook_project(), STEERING_PROFILE))
        assert out["hook_line"] == HOOK
        assert len(_draft_calls(calls)) == 1
        prompt = calls[0]["prompt"]
        assert "FOUNDER'S STEERING" not in prompt
        assert "HOOK RULES (this hook, on top of the craft above):" in prompt
        assert "- hook_line opens with the GOAL:" in prompt
        # The pain-first doctrine (ADR 0289, Kasra's order Nov 23
        # 2026): the goal the hook opens with is the internal pain
        # the app resolves, never its activity, and the line ends
        # toward the demo that answers it.
        assert "the internal pain she is trying to get out of" in prompt
        assert "nobody cares about writing a journal" in prompt
        assert "the demo that follows lands as the answer to this exact pain" in prompt
        assert "Return ONLY a JSON object" in prompt

    def test_the_picked_prompt_differs_only_by_the_steering_block(self, monkeypatch):
        import ai_service
        plain = _stub_chat(monkeypatch, [_hook_reply()])
        _run(ai_service.generate_hook_line(_hook_project(), STEERING_PROFILE))
        picked = _stub_chat(monkeypatch, [_hook_reply(hook_line=QUESTION_HOOK)])
        _run(ai_service.generate_hook_line(
            _hook_project(hook_focus=STATEMENT_OUTCOME, tone="bold",
                          hook_shape="question"),
            STEERING_PROFILE))
        default_prompt = plain[0]["prompt"]
        picked_prompt = picked[0]["prompt"]
        start = picked_prompt.index("\nFOUNDER'S STEERING")
        end = picked_prompt.index("\nReturn ONLY")
        assert picked_prompt[:start] + picked_prompt[end:] == default_prompt
        block = picked_prompt[start:end]
        assert STATEMENT_OUTCOME in block
        assert "TONE: bold" in block
        assert "SHAPE: a question" in block

    def test_a_question_pick_keeps_the_trying_in_its_steering(self, monkeypatch):
        import ai_service
        # ADR 0344 (Kasra's rule): a question-shaped hook is asked
        # from inside the struggle — the steering line itself
        # carries the trying and its cost, so the pick never yields
        # a bare "can I" ask that drops the effort.
        calls = _stub_chat(monkeypatch, [_hook_reply(hook_line=QUESTION_HOOK)])
        _run(ai_service.generate_hook_line(
            _hook_project(hook_shape="question"), STEERING_PROFILE))
        prompt = calls[0]["prompt"]
        assert "keeps the trying and what it costs her" in prompt
        assert "never" in prompt and "bare" in prompt and "ask that drops the effort" in prompt

    def test_a_stale_focus_pick_steers_nothing(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [_hook_reply()])
        _run(ai_service.generate_hook_line(
            _hook_project(hook_focus="An outcome the profile no longer carries"),
            STEERING_PROFILE))
        assert "FOUNDER'S STEERING" not in calls[0]["prompt"]

    def test_a_question_pick_lets_a_question_hook_pass(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [_hook_reply(hook_line=QUESTION_HOOK)])
        out = _run(ai_service.generate_hook_line(
            _hook_project(hook_shape="question"), STEERING_PROFILE))
        assert out["hook_line"] == QUESTION_HOOK
        assert len(_draft_calls(calls)) == 1

    def test_a_question_pick_corrects_a_statement_reply(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [
            _hook_reply(), _hook_reply(hook_line=QUESTION_HOOK)])
        out = _run(ai_service.generate_hook_line(
            _hook_project(hook_shape="question"), STEERING_PROFILE))
        assert out["hook_line"] == QUESTION_HOOK
        assert len(_draft_calls(calls)) == 2
        assert "question" in str(calls[1]["prompt"]).lower()

    def test_a_question_pick_refuses_a_persistent_statement(self, monkeypatch):
        import ai_service
        _stub_chat(monkeypatch, [_hook_reply(), _hook_reply()])
        with pytest.raises(RuntimeError):
            _run(ai_service.generate_hook_line(
                _hook_project(hook_shape="question"), STEERING_PROFILE))

    def test_a_statement_pick_refuses_a_question_reply(self, monkeypatch):
        import ai_service
        _stub_chat(monkeypatch, [
            _hook_reply(hook_line=QUESTION_HOOK),
            _hook_reply(hook_line=QUESTION_HOOK)])
        with pytest.raises(RuntimeError):
            _run(ai_service.generate_hook_line(
                _hook_project(hook_shape="statement"), STEERING_PROFILE))

    def test_the_budgets_still_bind_a_question_pick(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [
            _hook_reply(hook_line=LONG_QUESTION),
            _hook_reply(hook_line=QUESTION_HOOK)])
        out = _run(ai_service.generate_hook_line(
            _hook_project(hook_shape="question"), STEERING_PROFILE))
        assert out["hook_line"] == QUESTION_HOOK
        assert len(_draft_calls(calls)) == 2


class TestHookRewriteSteering:
    """The clearer-hook surface on this page honors the same picks
    (ADR 0247): the rewrite endpoint hands the row's saved picks to
    the rewrite for a hook_cta project — and hands nothing for a
    wizard project, whose rewrite keeps its own rules."""

    def test_the_rewrite_endpoint_hands_the_picks_over(self, api, monkeypatch):
        from models import RewriteLineRequest, UpdateStudioProjectRequest
        project, _profile = TestHookSteeringPicks()._draft(api, "Rewrite Picks")
        _write_hook(api, project["id"], monkeypatch)
        _run(api.update_studio_project(
            project["id"],
            UpdateStudioProjectRequest(
                hook_focus=STATEMENT_OUTCOME, hook_shape="question", tone="warm"),
            ANON))
        captured = {}

        async def fake_rewrite(profile, angle, line, role, **kwargs):
            captured.update(kwargs)
            captured["role"] = role
            return QUESTION_HOOK

        monkeypatch.setattr(api.ai_service, "rewrite_spoken_line", fake_rewrite)
        out = _run(api.suggest_line_rewrite(
            project["id"], RewriteLineRequest(line=HOOK, role="hook"), ANON))
        assert out["line"] == QUESTION_HOOK
        assert captured["role"] == "hook"
        assert captured["hook_focus"] == STATEMENT_OUTCOME
        assert captured["hook_shape"] == "question"
        assert captured["hook_tone"] == "warm"

    def test_a_wizard_project_hands_no_steering(self, api, monkeypatch):
        from models import CreateStudioProjectRequest, RewriteLineRequest
        profile = _profile(api, "Rewrite Wizard")
        wizard = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"]), user_id=ANON))
        _run(api._execute(
            "UPDATE studio_projects SET hook_line = ? WHERE id = ?",
            (HOOK, wizard["id"])))
        captured = {}

        async def fake_rewrite(profile, angle, line, role, **kwargs):
            captured.update(kwargs)
            return HOOK

        monkeypatch.setattr(api.ai_service, "rewrite_spoken_line", fake_rewrite)
        _run(api.suggest_line_rewrite(
            wizard["id"], RewriteLineRequest(line=HOOK, role="hook"), ANON))
        assert "hook_shape" not in captured
        assert "hook_focus" not in captured
        assert "hook_tone" not in captured

    def test_a_question_pick_rewrite_may_ask(self, monkeypatch):
        import ai_service
        _stub_chat(monkeypatch, [{"hook_line": "Why can't I clear my head before bed?"}])
        out = _run(ai_service.rewrite_hook_line(
            {"brand_name": "Vocolens", "app_category": "Wellness",
             "brand_description": "Speak your journal entry instead of writing it."},
            None, "I cannot clear my head before bed.", "",
            hook_shape="question"))
        assert out == "Why can't I clear my head before bed?"

    def test_the_rewrite_prompt_carries_the_focus_and_tone(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [
            {"hook_line": "I'm trying to clear my head before bed, warmly and simply."}])
        _run(ai_service.rewrite_hook_line(
            {"brand_name": "Vocolens", "app_category": "Wellness",
             "brand_description": "Speak your journal entry instead of writing it."},
            None, "I cannot clear my head before bed.", "",
            hook_focus=STATEMENT_OUTCOME, hook_tone="warm"))
        prompt = str(calls[0]["prompt"])
        assert STATEMENT_OUTCOME in prompt
        assert "warm" in prompt


# ------------------------------------------- complete in meaning (0249)

MOOD_FOCUS = (
    "You can spot your own rhythms instead of feeling surprised by your mood"
)
MOOD_PROFILE = {**PROFILE_FACTS, "desired_outcomes": [MOOD_FOCUS]}

DANGLING_QUESTION = "I'm trying to spot my rhythms, why so surprised?"
assert len(DANGLING_QUESTION.split()) == 9  # exactly the 4-second budget
COMPLETE_QUESTION = "Why does my mood keep surprising me at night?"
assert len(COMPLETE_QUESTION.split()) == 9  # the same budget, thought whole


class TestGenerateHookLineCompleteThought:
    """A hook must be complete in MEANING, not only in punctuation (ADR 0249).

    The live failure: focus "…feeling surprised by your mood", shape
    Question, 4 seconds — the generator returned "I'm trying to spot
    my rhythms, why so surprised?". The finished-sentence gate passed
    it (it ends in "?") but the question dangles: surprised by WHAT?
    The focus's key noun (mood) was dropped to fit the budget, leaving
    a bare question tail spliced onto a statement with a comma. The
    correction loop now names that defect, and a reply that keeps
    dangling is refused rather than shipped.
    """

    def _project(self):
        return _hook_project(
            duration_seconds=4, hook_focus=MOOD_FOCUS, hook_shape="question")

    def test_a_dangling_question_is_corrected_to_a_complete_one(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [
            _hook_reply(hook_line=DANGLING_QUESTION),
            _hook_reply(hook_line=COMPLETE_QUESTION)])
        out = _run(ai_service.generate_hook_line(self._project(), MOOD_PROFILE))
        assert out["hook_line"] == COMPLETE_QUESTION
        assert len(_draft_calls(calls)) == 2
        # The correction names the defect, so the rewrite knows what
        # to fix rather than merely that something failed.
        assert "dangles" in str(calls[1]["prompt"])

    def test_a_persistently_dangling_question_is_refused(self, monkeypatch):
        import ai_service
        _stub_chat(monkeypatch, [
            _hook_reply(hook_line=DANGLING_QUESTION),
            _hook_reply(hook_line=DANGLING_QUESTION)])
        with pytest.raises(RuntimeError):
            _run(ai_service.generate_hook_line(self._project(), MOOD_PROFILE))

    def test_a_complete_question_passes_first_try(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [
            _hook_reply(hook_line=COMPLETE_QUESTION)])
        out = _run(ai_service.generate_hook_line(self._project(), MOOD_PROFILE))
        assert out["hook_line"] == COMPLETE_QUESTION
        assert len(_draft_calls(calls)) == 1

    def test_the_dangling_check_spares_whole_questions(self):
        import ai_service
        check = ai_service._dangling_question_issue
        assert check(DANGLING_QUESTION)
        assert check("Why so hard?")
        assert not check(COMPLETE_QUESTION)
        assert not check("How do I stop losing count?")
        assert not check("What sets it off?")
        assert not check("I'm trying to keep count and I keep losing it.")


# --------------------------------------------------------- handheld only

class TestHandheldOnly:
    """Hook + CTA shoots handheld selfie only (ADR 0252, Kasra's
    ruling): the page's clips are short, and a selfie framing is more
    engaging than a zoomed-out environment, so the surface carries
    no camera choice at all. The forcing follows ADR 0246's
    voice_mode precedent — the submit path and the hook chain treat
    a hook_cta project as handheld whatever its row still stores,
    and the stored value is NOT rewritten: a row that somehow holds
    'fixed' (created before the ruling, or written by another
    client) renders handheld and reads back exactly as stored."""

    def test_a_stored_fixed_hook_renders_handheld(self, api, monkeypatch):
        from models import GenerateHookRequest
        project = TestGenerateHook()._ready(
            api, monkeypatch, "Handheld Stored Fixed", camera_setup="fixed")
        calls = _mock_submit(api, monkeypatch)
        _silence_poster(api, monkeypatch)
        generation = _run(api.generate_hook_cta(
            project["id"], GenerateHookRequest(), ANON))
        prompt = calls[0]["prompt"]
        assert "HANDHELD SELFIE" in prompt
        assert "Fixed camera: a stationary phone" not in prompt
        row = _run(api._fetch_one(
            "SELECT camera_setup FROM generations WHERE id = ?",
            (generation["id"],)))
        assert row["camera_setup"] == "handheld"
        # The stored pick is not rewritten by the forcing.
        stored = _run(api.get_studio_project(project["id"], ANON))
        assert stored["camera_setup"] == "fixed"

    def test_the_hook_line_is_written_for_a_handheld_camera(
            self, api, monkeypatch):
        """The hook write itself: a stored-fixed row's hook prompt
        carries no FIXED CAMERA block, because the working copy the
        endpoint hands the model is already handheld — the fixed
        indoor restatement never engages on this surface."""
        import ai_service
        from models import GenerateHookLineRequest
        project, _profile_row = _hook_cta(
            api, "Handheld Hook Write", camera_setup="fixed")
        seen = {}

        async def fake_hook_line(project_arg, profile):
            seen["camera_setup"] = project_arg.get("camera_setup")
            return {
                "hook_line": "I'm trying to clear my head before bed.",
                "hook_action": "Jerks upright, both hands flying up.",
                "closing_action": "Leans in, holding the look.",
                "location": "A quiet bedroom in the evening",
            }

        monkeypatch.setattr(ai_service, "generate_hook_line", fake_hook_line)
        out = _run(api.generate_hook_cta_hook(
            project["id"], GenerateHookLineRequest(), ANON))
        assert seen["camera_setup"] == "handheld"
        assert out["strategy"]["camera_setup"] == "handheld"
        stored = _run(api.get_studio_project(project["id"], ANON))
        assert stored["camera_setup"] == "fixed"


# ------------------------------------------------- history names the surface

class TestHistoryNamesTheSurface:
    """History shows every video in one layout (ADR 0253): the card
    is shared, but until the list payload named the project's
    surface it could not tell a hook render from a wizard render —
    the invisibility behind the hook card's one real divergence,
    its draft link walking into the wrong page. The list now
    carries project_surface beside project_kind: "hook_cta" for a
    hook render, "" for a wizard render (and for a row whose
    project is gone)."""

    def test_history_rows_carry_the_project_surface(self, api, monkeypatch):
        from models import CreateStudioProjectRequest, GenerateHookRequest
        project = TestGenerateHook()._ready(api, monkeypatch, "History Surface")
        _mock_submit(api, monkeypatch)
        _silence_poster(api, monkeypatch)
        generation = _run(api.generate_hook_cta(
            project["id"], GenerateHookRequest(), ANON))
        profile = _profile(api, "History Surface Wizard")
        wizard = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"]), user_id=ANON))
        _run(api._execute(
            "INSERT INTO generations"
            " (id, user_id, studio_project_id, brand_profile_id, status, created_at)"
            " VALUES (?, ?, ?, ?, 'completed', '2026-11-21T00:00:00Z')",
            ("history-surface-wizard", ANON, wizard["id"], profile["id"])))
        history = _run(api.generation_history(user_id=ANON))
        by_id = {g["id"]: g for g in history["generations"]}
        assert by_id[generation["id"]]["project_surface"] == "hook_cta"
        assert by_id[generation["id"]]["project_kind"] == "video"
        assert by_id["history-surface-wizard"]["project_surface"] == ""
