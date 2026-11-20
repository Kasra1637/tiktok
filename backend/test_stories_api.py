"""Stories endpoints (ADR 0228): create, plan, generate, and the kit.

DB-backed like test_cover_text.py, with OpenRouter fully mocked. These
assert OUR rules: a story is a project row with kind='story' and a type;
the plan saves the whole written layer plus the assembled strategy; the
generate endpoint submits ONE frame through the one render path at the
frame's own seconds (a 5s question/poll frame renders at 5, never
rounded up to the hook-video floor of 8); and at completion a story
render grows a story kit and never a post kit, while a hook-video
render does the reverse.
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

HOOK = "I keep losing count again."
SCRIPT = "At the stall I say it out loud once."
SCREEN = "Losing count by the tomatoes again"
STICKERS = [
    {"platform": "both", "sticker": "poll",
     "wording": "Do you lose count too? — Yes / Every time",
     "placement": "lower third, above the caption zone"},
]
LOCATION = "A market stall on Saturday afternoon"

PLAN = {
    "hook_line": HOOK,
    "script": SCRIPT,
    "screen_text": SCREEN,
    "sticker_plan": [dict(s) for s in STICKERS],
    "hook_action": "Lifts the paper bag high and counts on raised fingers.",
    "middle_action": "Turns back to the stall, still counting quietly.",
    "location": LOCATION,
    "story_type": "question_poll",
    "frame_seconds": 5,
}

KIT = {
    "caption": "Losing count by the tomatoes, again.",
    "screen_text": SCREEN,
    "sticker_plan": [dict(s) for s in STICKERS],
    "checklist": ["Add the screen text as a native text sticker."],
    "story_type": "question_poll",
    "frame_seconds": 5,
}


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-stories-")
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


def _profile(api, name):
    from models import ApproveAppProfileRequest, BrandProfileCreateRequest
    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name, app_category="Wellness",
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
    return profile


def _story(api, name="Story App", story_type="question_poll", **kwargs):
    from models import CreateStoryProjectRequest
    profile = _profile(api, name)
    project = _run(api.create_story_project(payload=CreateStoryProjectRequest(
        brand_profile_id=profile["id"], story_type=story_type, **kwargs,
    ), user_id=ANON))
    return project, profile


def _plan(api, project_id, monkeypatch):
    from models import GenerateStoryPlanRequest

    async def fake_plan(project, profile):
        return dict(PLAN)

    monkeypatch.setattr(api.ai_service, "generate_story_plan", fake_plan)
    return _run(api.generate_story_plan(
        project_id, GenerateStoryPlanRequest(), ANON))


def _attach_face(api, project):
    """Attach a real character_reference so the identity resolver accepts it."""
    from models import now_iso
    face = Path(tempfile.mkdtemp(prefix="tiktok-story-face-")) / "face.png"
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
    """Completion schedules a poster encode beside the kits; it is not
    what these tests assert, and there is no local clip to encode."""

    async def no_poster(background_tasks, generation_id, user_id):
        return None

    monkeypatch.setattr(api, "_schedule_poster", no_poster)


# ---------------------------------------------------------------- create

class TestCreateStoryProject:
    def test_create_carries_kind_type_and_the_type_default_length(self, api):
        project, _ = _story(api, "Create Basic")
        assert project["kind"] == "story"
        assert project["story_type"] == "question_poll"
        # The settled default for a question/poll frame (research Q4).
        assert project["duration_seconds"] == 5
        assert project["frame_count"] == 1
        assert project["status"] == "draft"
        row = _run(api._fetch_one(
            "SELECT kind, story_type FROM studio_projects WHERE id = ?",
            (project["id"],)))
        assert row["kind"] == "story" and row["story_type"] == "question_poll"

    def test_create_accepts_a_frame_length_pick(self, api):
        project, _ = _story(api, "Create Pick", frame_seconds=15)
        assert project["duration_seconds"] == 15

    def test_create_refuses_an_unknown_type_loudly(self, api):
        from models import CreateStoryProjectRequest
        profile = _profile(api, "Create Unknown")
        with pytest.raises(HTTPException) as exc:
            _run(api.create_story_project(payload=CreateStoryProjectRequest(
                brand_profile_id=profile["id"], story_type="testimonial",
            ), user_id=ANON))
        assert exc.value.status_code == 400
        assert "testimonial" in exc.value.detail

    def test_create_refuses_a_length_outside_the_pick(self, api):
        from models import CreateStoryProjectRequest
        profile = _profile(api, "Create Length")
        with pytest.raises(HTTPException) as exc:
            _run(api.create_story_project(payload=CreateStoryProjectRequest(
                brand_profile_id=profile["id"], story_type="hook_teaser",
                frame_seconds=7,
            ), user_id=ANON))
        assert exc.value.status_code == 400

    def test_story_fields_ride_the_existing_patch(self, api):
        from models import UpdateStudioProjectRequest
        project, _ = _story(api, "Patch Fields")
        _run(api.update_studio_project(project["id"], UpdateStudioProjectRequest(
            screen_text=SCREEN, sticker_plan=[dict(s) for s in STICKERS]), ANON))
        stored = _run(api.get_studio_project(project["id"], ANON))
        assert stored["screen_text"] == SCREEN
        assert stored["sticker_plan"] == STICKERS

    def test_story_frame_length_survives_a_patch(self, api):
        from models import UpdateStudioProjectRequest
        project, _ = _story(api, "Patch Length")
        # The hook-video clamp's floor is 8: a story's 5s pick must not
        # be silently rewritten to 8 by a draft edit.
        _run(api.update_studio_project(project["id"], UpdateStudioProjectRequest(
            duration_seconds=5), ANON))
        stored = _run(api.get_studio_project(project["id"], ANON))
        assert stored["duration_seconds"] == 5
        with pytest.raises(HTTPException) as exc:
            _run(api.update_studio_project(project["id"], UpdateStudioProjectRequest(
                duration_seconds=7), ANON))
        assert exc.value.status_code == 400


# ------------------------------------------------------------------ plan

class TestStoryPlanEndpoint:
    def test_plan_saves_the_written_layer_and_the_strategy(self, api, monkeypatch):
        project, _ = _story(api, "Plan Saves")
        out = _plan(api, project["id"], monkeypatch)
        assert out["hook_line"] == HOOK
        assert out["script"] == SCRIPT
        assert out["screen_text"] == SCREEN
        assert out["sticker_plan"] == STICKERS
        assert out["story_type"] == "question_poll"
        # The craft check rides the response, all four checks passing on
        # the settled fake plan.
        report = out["story_quality"]
        assert report["passed"] == report["total"] == 4
        # The assembled strategy is stored for the render: scene locked
        # from the plan's location, and the story brief rides inside it.
        row = _run(api._fetch_one(
            "SELECT strategy FROM studio_projects WHERE id = ?", (project["id"],)))
        strategy = row["strategy"]
        if isinstance(strategy, str):
            strategy = json.loads(strategy)
        assert strategy["scene"]["location"] == LOCATION
        assert strategy["story_brief"]["frame_seconds"] == 5
        assert strategy["story_brief"]["story_type"] == "question_poll"
        assert strategy["segments"][0]["script"] == HOOK
        assert strategy["segments"][1]["script"] == SCRIPT

    def test_plan_refuses_a_hook_video_project(self, api):
        from models import (
            CreateStudioProjectRequest, GenerateStoryPlanRequest)
        profile = _profile(api, "Plan Video")
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"]), user_id=ANON))
        with pytest.raises(HTTPException) as exc:
            _run(api.generate_story_plan(
                project["id"], GenerateStoryPlanRequest(), ANON))
        assert exc.value.status_code == 400
        assert "not a story" in exc.value.detail

    def test_plan_404s_for_a_missing_project(self, api):
        from models import GenerateStoryPlanRequest
        with pytest.raises(HTTPException) as exc:
            _run(api.generate_story_plan(
                "no-such-project", GenerateStoryPlanRequest(), ANON))
        assert exc.value.status_code == 404


# -------------------------------------------------------------- generate

class TestStoryGenerateEndpoint:
    def test_generate_submits_one_frame_at_the_frames_own_seconds(
            self, api, monkeypatch):
        """The end-to-end proof: plan, then one provider submit at 5s —
        the question/poll frame's settled length, not the hook-video
        clamp's 8s floor — with the story brief in the prompt."""
        from models import GenerateStoryRequest
        project, _ = _story(api, "Generate E2E")
        _plan(api, project["id"], monkeypatch)
        _attach_face(api, project)
        calls = _mock_submit(api, monkeypatch)
        generation = _run(api.generate_story(
            project["id"], GenerateStoryRequest(), ANON))
        assert len(calls) == 1
        assert calls[0]["duration"] == 5
        prompt = calls[0]["prompt"]
        assert "STORY FRAME" in prompt
        assert "5 seconds" in prompt
        # The founder's sticker sits in the lower frame at posting, so
        # the brief keeps the presenter's gestures out of it.
        assert "lower" in prompt
        assert generation["segment_index"] == 0
        row = _run(api._fetch_one(
            "SELECT requested_duration, segment_index FROM generations WHERE id = ?",
            (generation["id"],)))
        assert row["requested_duration"] == 5
        assert row["segment_index"] == 0

    def test_generate_refuses_before_a_plan_exists(self, api):
        from models import GenerateStoryRequest
        project, _ = _story(api, "Generate No Plan")
        with pytest.raises(HTTPException) as exc:
            _run(api.generate_story(
                project["id"], GenerateStoryRequest(), ANON))
        assert exc.value.status_code == 409
        assert "plan" in exc.value.detail

    def test_generate_refuses_an_unknown_model(self, api, monkeypatch):
        from models import GenerateStoryRequest
        project, _ = _story(api, "Generate Model")
        _plan(api, project["id"], monkeypatch)
        with pytest.raises(HTTPException) as exc:
            _run(api.generate_story(
                project["id"], GenerateStoryRequest(model="no-such-model"), ANON))
        assert exc.value.status_code == 400


# ------------------------------------------------------------------- kit

def _completed_story_render(api, monkeypatch, name):
    """A planned story project with one submitted render, driven to
    completion through the same outcome path poll uses."""
    from models import GenerateStoryRequest
    project, _ = _story(api, name)
    _plan(api, project["id"], monkeypatch)
    _attach_face(api, project)
    _mock_submit(api, monkeypatch)
    generation = _run(api.generate_story(
        project["id"], GenerateStoryRequest(), ANON))

    async def fake_story_kit(project_row, profile_row, generation_row):
        return dict(KIT)

    async def fake_post_kit(project_row, profile_row):
        return {"caption": "A hook-video kit?", "hashtags": [], "cover_text": "x"}

    monkeypatch.setattr(api.ai_service, "generate_story_kit", fake_story_kit)
    monkeypatch.setattr(api.ai_service, "generate_post_kit", fake_post_kit)
    _silence_poster(api, monkeypatch)
    _run(api._apply_persist_outcome(
        generation["id"], ANON, "https://example.invalid/clip.mp4",
        "https://example.invalid/stored.mp4", None, 5))
    return project, generation


class TestStoryKit:
    def test_completion_writes_the_story_kit_and_never_a_post_kit(
            self, api, monkeypatch):
        _, generation = _completed_story_render(api, monkeypatch, "Kit Write")
        row = _run(api._fetch_one(
            "SELECT story_kit, post_kit FROM generations WHERE id = ?",
            (generation["id"],)))
        assert json.loads(row["story_kit"]) == KIT
        assert row["post_kit"] is None
        detail = _run(api.get_generation(generation["id"], ANON))
        assert detail["story_kit"] == KIT

    def test_a_hook_video_completion_grows_no_story_kit(self, api, monkeypatch):
        from models import (
            CreateStudioProjectRequest, UpdateStudioProjectRequest)
        profile = _profile(api, "Kit Video")
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"]), user_id=ANON))
        _run(api.update_studio_project(project["id"], UpdateStudioProjectRequest(
            hook_line=HOOK, script=SCRIPT), ANON))
        gen_id = str(uuid.uuid4())
        from models import now_iso
        now = now_iso()
        _run(api._execute(
            """INSERT INTO generations
               (id, studio_project_id, brand_profile_id, status, created_at,
                updated_at, user_id)
               VALUES (?, ?, ?, 'generating', ?, ?, ?)""",
            (gen_id, project["id"], profile["id"], now, now, ANON)))
        story_kit_calls = []

        async def spy_story_kit(project_row, profile_row, generation_row):
            story_kit_calls.append(generation_row)
            return dict(KIT)

        async def fake_post_kit(project_row, profile_row):
            return {"caption": "A hook-video kit?", "hashtags": [], "cover_text": "x"}

        monkeypatch.setattr(api.ai_service, "generate_story_kit", spy_story_kit)
        monkeypatch.setattr(api.ai_service, "generate_post_kit", fake_post_kit)
        _silence_poster(api, monkeypatch)
        _run(api._apply_persist_outcome(
            gen_id, ANON, "https://example.invalid/clip.mp4",
            "https://example.invalid/stored.mp4", None, 15))
        row = _run(api._fetch_one(
            "SELECT story_kit, post_kit FROM generations WHERE id = ?", (gen_id,)))
        assert row["story_kit"] is None
        assert story_kit_calls == []
        # The hook video's own kit still writes, exactly as before.
        assert json.loads(row["post_kit"])["caption"] == "A hook-video kit?"

    def test_regenerate_replaces_the_story_kit(self, api, monkeypatch):
        _, generation = _completed_story_render(api, monkeypatch, "Kit Regen")
        fresh = {**KIT, "caption": "A fresher caption for the same frame."}

        async def fake_story_kit(project_row, profile_row, generation_row):
            return dict(fresh)

        monkeypatch.setattr(api.ai_service, "generate_story_kit", fake_story_kit)
        out = _run(api.regenerate_story_kit(generation["id"], ANON))
        assert out["story_kit"] == fresh
        row = _run(api._fetch_one(
            "SELECT story_kit FROM generations WHERE id = ?", (generation["id"],)))
        assert json.loads(row["story_kit"]) == fresh

    def test_regenerate_story_kit_refuses_a_hook_video_render(
            self, api, monkeypatch):
        from models import (
            CreateStudioProjectRequest, UpdateStudioProjectRequest, now_iso)
        profile = _profile(api, "Kit Regen Video")
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"]), user_id=ANON))
        _run(api.update_studio_project(project["id"], UpdateStudioProjectRequest(
            hook_line=HOOK, script=SCRIPT), ANON))
        gen_id = str(uuid.uuid4())
        now = now_iso()
        _run(api._execute(
            """INSERT INTO generations
               (id, studio_project_id, brand_profile_id, status, created_at,
                updated_at, user_id)
               VALUES (?, ?, ?, 'completed', ?, ?, ?)""",
            (gen_id, project["id"], profile["id"], now, now, ANON)))
        with pytest.raises(HTTPException) as exc:
            _run(api.regenerate_story_kit(gen_id, ANON))
        assert exc.value.status_code == 409
        assert "story" in exc.value.detail


# ------------------------------------------------------------ architecture

def test_stories_router_is_owned_by_routers_stories(api):
    """Story routes live in routers.stories; server re-exports them."""
    import routers.stories as stories
    for name in ("create_story_project", "generate_story_plan",
                 "generate_story", "regenerate_story_kit",
                 "_parse_story_kit", "_schedule_story_kit"):
        assert getattr(api, name) is getattr(stories, name), name


def test_stories_router_never_imports_the_composition_root():
    import ast
    tree = ast.parse((BACKEND_DIR / "routers/stories.py").read_text(encoding="utf-8"))
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add((node.module or "").split(".")[0])
    assert "server" not in imports
