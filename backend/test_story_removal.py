"""The Stories removal (ADR 0243): the surface is gone, the data stays.

Kasra retired the Stories page for the hook-straight-into-CTA workflow.
These pin the two halves of that decision:

- ABSENCE: no /stories route, no story-kit regenerate route, and the
  story generation functions are gone from the AI service.
- PRESERVATION: a legacy story project and its render stay readable —
  History still answers the row with its story kit parsed and its kind
  named, and the post-kit writer still refuses a story render (a story
  render carries a story kit, never post copy). No row is deleted or
  rewritten by the removal.
"""
import asyncio
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

import uuid

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

ANON = "anonymous"

LEGACY_KIT = {
    "caption": "Losing count by the tomatoes, again.",
    "screen_text": "Losing count by the tomatoes again",
    "sticker_plan": [],
    "checklist": ["Add the screen text as a native text sticker."],
    "story_type": "question_poll",
    "frame_seconds": 3,
}


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-story-removal-")
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


def _route_paths(api):
    return {getattr(route, "path", "") for route in api.app.routes}


class TestStoriesSurfaceIsGone:
    def test_no_stories_routes_are_mounted(self, api):
        paths = _route_paths(api)
        assert not any("/stories" in path for path in paths), paths
        assert not any("story-kit" in path for path in paths), paths

    def test_story_generation_functions_are_gone(self, api):
        for name in ("generate_story_plan", "generate_story_kit",
                     "suggest_story_screen_text"):
            assert not hasattr(api.ai_service, name), name

    def test_story_quality_scorer_is_gone(self, api):
        import creative_quality
        assert not hasattr(creative_quality, "assess_story_quality")


class TestLegacyStoryDataSurvives:
    def _seed(self, api):
        """A story project + a finished render carrying a story kit,
        seeded the way the retired page left them."""
        from models import (ApproveAppProfileRequest,
                            BrandProfileCreateRequest,
                            CreateStudioProjectRequest)
        profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name="Legacy Story App", app_category="Wellness",
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
            profile_id=profile["id"], payload=ApproveAppProfileRequest(),
            user_id=ANON))
        project = _run(api.create_studio_project(
            payload=CreateStudioProjectRequest(
                brand_profile_id=profile["id"], kind="story"),
            user_id=ANON))
        generation_id = f"legacy-story-render-{uuid.uuid4().hex[:8]}"
        _run(api._execute(
            """INSERT INTO generations
               (id, user_id, studio_project_id, brand_profile_id, status,
                story_kit, created_at)
               VALUES (?, ?, ?, ?, 'completed', ?, '2026-11-20T00:00:00Z')""",
            (generation_id, ANON, project["id"], profile["id"],
             json.dumps(LEGACY_KIT))))
        return project, generation_id

    def test_history_still_serves_the_legacy_story_kit(self, api):
        project, generation_id = self._seed(api)
        result = _run(api.generation_history(user_id=ANON))
        row = next(r for r in result["generations"] if r["id"] == generation_id)
        assert row["project_kind"] == "story"
        assert row["story_kit"] == LEGACY_KIT
        # The project row itself is untouched by the removal.
        saved = _run(api.get_studio_project(project["id"], ANON))
        assert saved["kind"] == "story"

    def test_post_kit_regenerate_still_refuses_a_story_render(self, api):
        _, generation_id = self._seed(api)
        with pytest.raises(HTTPException) as excinfo:
            _run(api.regenerate_post_kit(generation_id, ANON))
        assert excinfo.value.status_code == 409

    def test_story_kit_parser_still_reads_stored_kits(self, api):
        assert api._parse_story_kit(json.dumps(LEGACY_KIT)) == LEGACY_KIT
        assert api._parse_story_kit(None) is None
        assert api._parse_story_kit("{broken") is None
