"""The render-time craft score is stored on the generation row.

ADR 0117: the craft report stops being a read-time-only mirror. At submit,
the words this render will actually speak are scored once and the report is
frozen onto the generation row, so a later performance snapshot can be joined
against the score the clip was rendered with. Reads prefer the stored
report; a row from before the column existed recomputes from its project's
words instead of reporting nothing.
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

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

ANON = "anonymous"


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-quality-store-")
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

    original_dirs = (server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR)
    server.pipeline.VIDEOS_DIR = Path(tmpdir) / "videos"
    server.pipeline.GENERATED_DIR = Path(tmpdir) / "generated"
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    server.pipeline.GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    asyncio.run(server.init_db())
    try:
        yield server
    finally:
        server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR = original_dirs
        sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


FAKE_STRATEGY = {
    "strategy_summary": "Stop opening a blank page.",
    "audience_problem": "Starting is harder than doing.",
    "emotional_triggers": ["frustration"],
    "hook_concept": "Name the blank page",
    "hook_line": "You do not have a writing problem.",
    "hook_promise": "One prompt gets you going.",
    "hook_action": "Look straight down the lens.",
    "messaging_pillars": ["one prompt at a time"],
    "primary_feature": "Task timer",
    "desired_outcome": "A finished page",
    "differentiation_beat": "It works offline.",
    "cta_strategy": "Try it free",
    "scene": {"environment": "kitchen"},
    "performance": {"movement": "still"},
    "segments": [{
        "index": 0, "role": "hook", "seconds": 5,
        "goal": "name the problem", "script": "You do not have a writing problem.",
        "action": "hold the look",
    }],
    "continuity_contract": {
        "established": ["kitchen"],
        "must_not_change": ["shirt"],
        "do_not_repeat": ["the opening line"],
    },
}

HOOK = "Stop writing empty pages"
SCRIPT = "A short script for the app."


def _ready_project(api, name):
    from models import (
        BrandProfileCreateRequest, ApproveAppProfileRequest,
        CreateStudioProjectRequest, now_iso,
    )
    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name,
        app_category="Productivity",
        brand_description="A focus timer for people who stall on starting.",
        core_features=["Task timer"],
        usage_moments=["Starting a task they have been avoiding"],
        outcome_statements=[{
            "outcome": "Starting without stalling on setup",
            "who_feels_it": "people who stall on starting",
            "from_feature": "Task timer",
            "how_it_helps": "The timer starts in one tap so there is nothing to set up",
        }],
        claims_approved=["3-day free trial"],
        claims_banned=["cures anxiety"],
    ), user_id=ANON))
    _run(api.approve_app_profile(
        profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    template = _run(api.list_templates(q="Stop Doing This", user_id=ANON))["templates"][0]
    project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"],
        template_id=template["id"],
        duration_seconds=20,
        objective="demonstrate_feature",
    ), user_id=ANON))
    face = Path(tempfile.mkdtemp(prefix="tiktok-quality-face-")) / "face.png"
    face.write_bytes(bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c626001000000ffff0300000600055d3866680000000049454e44ae426082"))
    asset_id = str(uuid.uuid4())
    now = now_iso()
    _run(api._execute(
        "INSERT INTO assets (id, brand_profile_id, kind, name, file_path, label,"
        " created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (asset_id, profile["id"], "character_reference", "Founder face",
         str(face), "Founder face", now, now, ANON)))
    assets = [{
        "asset_id": asset_id, "kind": "character_reference",
        "label": "Founder face", "file_path": str(face),
    }]
    _run(api._execute(
        """UPDATE studio_projects SET assets = ?, hook_line = ?, script = ?,
              status = 'ready_for_generation', script_version = 1,
              strategy = ?, strategy_version = 1, strategy_script_version = 1
           WHERE id = ?""",
        (json.dumps(assets), HOOK, SCRIPT, json.dumps(FAKE_STRATEGY), project["id"])))
    return _run(api.get_studio_project(project["id"], ANON)), profile


def _mock_submit(api, monkeypatch):
    async def fake_generate_video(**kwargs):
        return {"id": "job-quality-1", "status": "queued", "usage": {"cost": 0.25}}

    monkeypatch.setattr(api, "generate_video", fake_generate_video)


def _expected_total(hook, script, app_name):
    import creative_quality

    return creative_quality.assess_spoken_quality(
        hook, script, hook_seconds=3, total_seconds=20,
        app_name=app_name, allows_question=True,
    )["total"]


class TestStoredQualityReport:
    def test_submit_stores_the_craft_score_on_the_generation_row(self, api, monkeypatch):
        _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, profile = _ready_project(api, "Stored Score App")
        result = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        row = _run(api._fetch_one(
            "SELECT quality_report FROM generations WHERE id = ?", (result["id"],)))
        assert row is not None and row.get("quality_report")
        stored = json.loads(row["quality_report"])
        assert stored["total"] == _expected_total(HOOK, SCRIPT, "Stored Score App")
        assert stored["grade"]
        assert set(stored["dimensions"]) == {
            "hook_stopping_power", "audience_truth", "clarity", "concreteness",
            "story_arc", "spoken_naturalness", "demo_handoff", "trust_compliance",
        }
        # The submit response itself carries the same stored report.
        assert result["quality_report"]["total"] == stored["total"]

    def test_read_prefers_the_stored_report_over_the_projects_current_words(self, api, monkeypatch):
        _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _profile = _ready_project(api, "Frozen Score App")
        result = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        frozen_total = result["quality_report"]["total"]
        # The founder rewrites the plan after the render. The generation's
        # score must still describe the words that were rendered, not the
        # words the project carries now.
        _run(api._execute(
            "UPDATE studio_projects SET hook_line = ?, script = ? WHERE id = ?",
            ("A completely different opening line about mornings",
             "And a completely different middle that rambles on about the "
             "weather and the commute and everything else under the sun.",
             project["id"])))
        detail = _run(api.get_generation(result["id"], ANON))
        assert detail["quality_report"]["total"] == frozen_total

    def test_row_without_a_stored_report_recomputes_from_the_project_words(self, api):
        from models import now_iso
        # A generation from before the column existed: no stored report, but
        # its project still carries the words, so the read recomputes rather
        # than reporting nothing.
        project_id = str(uuid.uuid4())
        generation_id = str(uuid.uuid4())
        now = now_iso()
        _run(api._execute(
            "INSERT INTO studio_projects (id, brand_profile_id, hook_line, script,"
            " hook_seconds, duration_seconds, status, created_at, updated_at, user_id)"
            " VALUES (?, NULL, ?, ?, 3, 20, 'draft', ?, ?, ?)",
            (project_id, HOOK, SCRIPT, now, now, ANON)))
        _run(api._execute(
            "INSERT INTO generations (id, studio_project_id, user_id, status,"
            " created_at, updated_at) VALUES (?, ?, ?, 'completed', ?, ?)",
            (generation_id, project_id, ANON, now, now)))
        detail = _run(api.get_generation(generation_id, ANON))
        assert detail["quality_report"] is not None
        assert detail["quality_report"]["total"] == _expected_total(HOOK, SCRIPT, "")

    def test_row_with_no_words_and_no_stored_report_reads_as_none(self, api):
        from models import now_iso
        generation_id = str(uuid.uuid4())
        now = now_iso()
        _run(api._execute(
            "INSERT INTO generations (id, user_id, status, created_at, updated_at)"
            " VALUES (?, ?, 'completed', ?, ?)",
            (generation_id, ANON, now, now)))
        detail = _run(api.get_generation(generation_id, ANON))
        assert detail["quality_report"] is None
