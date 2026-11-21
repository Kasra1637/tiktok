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
