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
        assert len(calls) == 2
        assert "correction" in str(calls[1]).lower() or "12 words" in str(calls[1])

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

    def test_unpicked_the_prompt_is_the_prompt_it_always_was(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [_hook_reply()])
        out = _run(ai_service.generate_hook_line(_hook_project(), STEERING_PROFILE))
        assert out["hook_line"] == HOOK
        assert len(calls) == 1
        prompt = calls[0]["prompt"]
        assert "FOUNDER'S STEERING" not in prompt
        assert "HOOK RULES (this hook, on top of the craft above):" in prompt
        assert "- hook_line opens with the GOAL:" in prompt
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
        assert len(calls) == 1

    def test_a_question_pick_corrects_a_statement_reply(self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [
            _hook_reply(), _hook_reply(hook_line=QUESTION_HOOK)])
        out = _run(ai_service.generate_hook_line(
            _hook_project(hook_shape="question"), STEERING_PROFILE))
        assert out["hook_line"] == QUESTION_HOOK
        assert len(calls) == 2
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
        assert len(calls) == 2


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
