"""Post kit frozen on completion, read through the existing endpoints.

Seam: submit → poll → get/list/history. No new page or entity.
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

KIT = {
    "caption": (
        "Stop writing empty pages with one timed start — "
        "a focus timer that starts in one tap. "
        "What stalls your first sentence?"
    ),
    "hashtags": ["#FocusTimer", "#productivity", "#studytok", "#focus"],
    "cover_text": "Stop writing empty pages",
}

KIT2 = {
    "caption": (
        "Stop staring at a blank page — "
        "this timer starts your session in one tap. "
        "What will you start first?"
    ),
    "hashtags": ["#FocusTimer", "#studywithme", "#deepwork", "#habits"],
    "cover_text": "Start without stalling",
}

LEGACY_KIT = {
    "captions": [
        "Stop writing empty pages with one timed start.",
        "A focus timer that starts in one tap.",
        "What stalls your first sentence?",
    ],
    "hashtags": ["#FocusTimer", "#productivity", "#studytok"],
    "cover_text": "Stop writing empty pages",
}


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-postkit-")
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


async def _fake_generate_video(**kwargs):
    return {"id": "job-kit", "status": "queued"}


async def _fake_poll(job_id):
    return {"status": "completed",
            "unsigned_urls": ["https://example.invalid/clip.mp4"]}


def _ready_project(api, name="Post Kit App"):
    from models import (
        BrandProfileCreateRequest, ApproveAppProfileRequest,
        CreateStudioProjectRequest,
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
    strategy = {
        "strategy_summary": "Stop opening a blank page.",
        "hook_line": "Stop writing empty pages",
        "hook_promise": "One prompt gets you going.",
        "hook_action": "Look straight down the lens.",
        "messaging_pillars": ["one prompt at a time"],
        "primary_feature": "Task timer",
        "cta_strategy": "Try it free",
        "scene": {"environment": "kitchen"},
        "performance": {"movement": "still"},
        "segments": [{"index": 0, "role": "hook", "seconds": 5,
                      "goal": "name the problem",
                      "script": "Stop writing empty pages",
                      "action": "hold the look"}],
        "continuity_contract": {"established": ["kitchen"]},
    }
    from models import now_iso
    face = Path(tempfile.mkdtemp(prefix="tiktok-kit-")) / "face.png"
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
    assets = [{"asset_id": asset_id, "kind": "character_reference",
               "label": "Founder face", "file_path": str(face)}]
    _run(api._execute(
        """UPDATE studio_projects SET assets = ?, hook_line = ?, script = ?,
              status = 'ready_for_generation', script_version = 1,
              strategy = ?, strategy_version = 1, strategy_script_version = 1
           WHERE id = ?""",
        (json.dumps(assets), "Stop writing empty pages",
         "A short script for the app.", json.dumps(strategy), project["id"])))
    return _run(api.get_studio_project(project["id"], ANON))


class TestPostKitFrozenOnCompletion:
    def test_completed_render_persists_and_returns_its_kit(self, api, monkeypatch):
        from models import StudioGenerationRequest

        async def fake_kit(project, profile):
            # Grounded in THIS render: the hook the fixture approved.
            assert project.get("hook_line") == "Stop writing empty pages"
            return dict(KIT)

        monkeypatch.setattr(api, "generate_video", _fake_generate_video)
        monkeypatch.setattr(api, "poll_video_job", _fake_poll)
        monkeypatch.setattr(api.ai_service, "generate_post_kit", fake_kit)

        project = _ready_project(api)
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        # No kit at submit time: it is written at completion, not at submit.
        assert gen.get("post_kit") in (None, {}, [])

        completed = _run(api.poll_generation(gen["id"], ANON))
        assert completed["status"] == "completed"
        assert completed.get("post_kit") == KIT

        # Frozen: a second poll returns the same kit without regenerating it.
        async def boom_kit(project, profile):
            raise AssertionError("post kit must be frozen, not regenerated")

        monkeypatch.setattr(api.ai_service, "generate_post_kit", boom_kit)
        again = _run(api.poll_generation(gen["id"], ANON))
        assert again.get("post_kit") == KIT

        # Every existing surface carries the frozen kit.
        assert _run(api.get_generation(gen["id"], ANON)).get("post_kit") == KIT
        listed = _run(api.list_generations(
            studio_project_id=project["id"], user_id=ANON))["generations"]
        assert listed and listed[0].get("post_kit") == KIT
        history = _run(api.generation_history(user_id=ANON))["generations"]
        row = next(g for g in history if g["id"] == gen["id"])
        assert row.get("post_kit") == KIT

        # And it is really frozen on the row, not re-derived per read.
        stored = _run(api._fetch_one(
            "SELECT post_kit FROM generations WHERE id = ?", (gen["id"],)))
        assert json.loads(stored["post_kit"]) == KIT

    def test_kit_write_runs_after_the_poll_response(self, api, monkeypatch):
        """The completion poll must not wait on the kit's text call: on HTTP
        the write is a BackgroundTask, and direct callers stay inline.
        """
        from starlette.background import BackgroundTasks

        from models import StudioGenerationRequest

        async def fake_kit(project, profile):
            return dict(KIT)

        monkeypatch.setattr(api, "generate_video", _fake_generate_video)
        monkeypatch.setattr(api, "poll_video_job", _fake_poll)
        monkeypatch.setattr(api.ai_service, "generate_post_kit", fake_kit)

        project = _ready_project(api, "Post Kit Deferred")
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))

        tasks = BackgroundTasks()
        completed = _run(api.poll_generation(gen["id"], ANON, tasks))
        assert completed["status"] == "completed"
        # The video is done but the kit has not been written yet: the
        # response did not wait for it.
        assert completed.get("post_kit") is None
        stored = _run(api._fetch_one(
            "SELECT post_kit FROM generations WHERE id = ?", (gen["id"],)))
        assert stored["post_kit"] is None

        _run(tasks())
        assert _run(api.get_generation(gen["id"], ANON)).get("post_kit") == KIT


class TestStrandedRender:
    """One slice: the founder's stranded story through this file's seam.

    A 429 while polling leaves the row alone, the kit write fails
    best-effort at completion, and list/history show a finished render
    with no kit — the row the History banner offers to rescue. (The
    rescue press itself is pinned by the regenerate tests below.)
    """

    def test_throttled_poll_then_failed_kit_leaves_a_kitless_finished_row(
        self, api, monkeypatch
    ):
        from fastapi import HTTPException
        from models import StudioGenerationRequest

        async def boom_kit(project, profile):
            raise RuntimeError("text model is down")

        monkeypatch.setattr(api, "generate_video", _fake_generate_video)
        monkeypatch.setattr(api.ai_service, "generate_post_kit", boom_kit)

        seen = []

        async def throttled_once_then_done(job_id):
            if not seen:
                seen.append(job_id)
                raise RuntimeError("Client error '429 Too Many Requests' for url")
            return await _fake_poll(job_id)

        monkeypatch.setattr(api, "poll_video_job", throttled_once_then_done)

        project = _ready_project(api, "Stranded Rescue App")
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert gen.get("post_kit") in (None, {}, [])

        # The throttled check: still going, row untouched, nothing written.
        with pytest.raises(HTTPException) as err:
            _run(api.poll_generation(gen["id"], ANON))
        assert err.value.status_code == 429
        row = _run(api._fetch_one(
            "SELECT status, error FROM generations WHERE id = ?", (gen["id"],)))
        assert row["status"] in ("submitted", "generating")
        assert not row["error"]

        # Completion with a failing kit writer: finished, but kit-less.
        completed = _run(api.poll_generation(gen["id"], ANON))
        assert completed["status"] == "completed"
        assert completed.get("post_kit") is None

        # The surfaces a founder reads agree: finished, no kit.
        listed = _run(api.list_generations(
            studio_project_id=project["id"], user_id=ANON))["generations"]
        assert listed and listed[0]["status"] == "completed"
        assert listed[0].get("post_kit") is None
        history = _run(api.generation_history(user_id=ANON))["generations"]
        history_row = next(g for g in history if g["id"] == gen["id"])
        assert history_row["status"] == "completed"
        assert history_row.get("post_kit") is None


class TestPostKitSingleCaption:
    """One caption per render: grounded, guarded, and exactly one."""

    def _completed_gen(self, api, monkeypatch, kit, name="Post Kit Single"):
        from models import StudioGenerationRequest

        async def fake_kit(project, profile):
            return dict(kit)

        monkeypatch.setattr(api, "generate_video", _fake_generate_video)
        monkeypatch.setattr(api, "poll_video_job", _fake_poll)
        monkeypatch.setattr(api.ai_service, "generate_post_kit", fake_kit)
        project = _ready_project(api, name)
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        completed = _run(api.poll_generation(gen["id"], ANON))
        assert completed["status"] == "completed"
        return gen

    def test_regenerate_replaces_the_saved_kit(self, api, monkeypatch):
        gen = self._completed_gen(api, monkeypatch, KIT)

        async def fresh_kit(project, profile):
            return dict(KIT2)

        monkeypatch.setattr(api.ai_service, "generate_post_kit", fresh_kit)
        res = _run(api.regenerate_post_kit(gen["id"], ANON))
        assert res.get("post_kit") == KIT2
        assert _run(api.get_generation(gen["id"], ANON)).get("post_kit") == KIT2
        stored = _run(api._fetch_one(
            "SELECT post_kit FROM generations WHERE id = ?", (gen["id"],)))
        assert json.loads(stored["post_kit"]) == KIT2

    def test_regenerate_failure_keeps_the_current_kit(self, api, monkeypatch):
        gen = self._completed_gen(api, monkeypatch, KIT)

        async def boom_kit(project, profile):
            raise RuntimeError("text model is down")

        monkeypatch.setattr(api.ai_service, "generate_post_kit", boom_kit)
        err = None
        try:
            _run(api.regenerate_post_kit(gen["id"], ANON))
        except Exception as e:  # noqa: BLE001 — asserting the loud failure
            err = e
        assert err is not None and getattr(err, "status_code", None) == 502
        assert _run(api.get_generation(gen["id"], ANON)).get("post_kit") == KIT

    def test_regenerate_non_completed_render_is_loud(self, api, monkeypatch):
        gen = self._completed_gen(api, monkeypatch, KIT, "Post Kit Gated")
        _run(api._execute(
            "UPDATE generations SET status = ?, post_kit = NULL WHERE id = ?",
            ("failed", gen["id"])))
        err = None
        try:
            _run(api.regenerate_post_kit(gen["id"], ANON))
        except Exception as e:  # noqa: BLE001 — asserting the loud failure
            err = e
        assert err is not None and getattr(err, "status_code", None) == 409
        stored = _run(api._fetch_one(
            "SELECT post_kit FROM generations WHERE id = ?", (gen["id"],)))
        assert stored["post_kit"] is None

    def test_regenerate_missing_generation_is_404(self, api):
        err = None
        try:
            _run(api.regenerate_post_kit(str(uuid.uuid4()), ANON))
        except Exception as e:  # noqa: BLE001 — asserting the loud failure
            err = e
        assert err is not None and getattr(err, "status_code", None) == 404

    def test_legacy_three_caption_kit_still_reads_through(self, api, monkeypatch):
        gen = self._completed_gen(api, monkeypatch, KIT, "Post Kit Legacy")
        _run(api._execute(
            "UPDATE generations SET post_kit = ? WHERE id = ?",
            (json.dumps(LEGACY_KIT), gen["id"])))
        # The backend passes the frozen row through untouched; the UI shows
        # the first of the three captions.
        assert _run(api.get_generation(gen["id"], ANON)).get("post_kit") == LEGACY_KIT


class TestPostKitCaptionGuards:
    """The model response is validated before it can become post copy."""

    def _materials(self):
        project = {
            "hook_line": "Stop writing empty pages",
            "script": "A short script for the app.",
            "cta": "Try it free",
        }
        profile = {
            "brand_name": "FocusTimer",
            "brand_description": "A focus timer.",
            "target_audience": "students",
            "tone_voice": "plain",
            "claims_approved": ["3-day free trial"],
            "claims_banned": ["cures anxiety"],
        }
        return project, profile

    def test_happy_path_returns_single_caption(self, api, monkeypatch):
        async def fake_chat(**kwargs):
            return {
                "caption": "Stop writing empty pages — a timer that starts in one tap. What stalls you?",
                "hashtags": ["#FocusTimer", "#a", "#b", "#c"],
                "cover_text": "Stop writing empty pages",
            }

        monkeypatch.setattr(api.ai_service, "_chat_json", fake_chat)
        project, profile = self._materials()
        kit = _run(api.ai_service.generate_post_kit(project, profile))
        assert kit["caption"].startswith("Stop writing empty pages")
        assert "captions" not in kit
        assert len(kit["hashtags"]) == 4

    def test_too_few_hashtags_is_loud(self, api, monkeypatch):
        async def fake_chat(**kwargs):
            return {
                "caption": "Stop writing empty pages — a timer that starts in one tap. What stalls you?",
                "hashtags": ["#FocusTimer"],
                "cover_text": "Stop writing empty pages",
            }

        monkeypatch.setattr(api.ai_service, "_chat_json", fake_chat)
        project, profile = self._materials()
        with pytest.raises(RuntimeError):
            _run(api.ai_service.generate_post_kit(project, profile))

    def test_missing_caption_is_loud(self, api, monkeypatch):
        async def fake_chat(**kwargs):
            return {
                "caption": "   ",
                "hashtags": ["#FocusTimer", "#a", "#b", "#c"],
                "cover_text": "Stop writing empty pages",
            }

        monkeypatch.setattr(api.ai_service, "_chat_json", fake_chat)
        project, profile = self._materials()
        with pytest.raises(RuntimeError):
            _run(api.ai_service.generate_post_kit(project, profile))

    def test_caption_without_its_question_is_loud(self, api, monkeypatch):
        async def fake_chat(**kwargs):
            return {
                "caption": "Stop writing empty pages — a timer that starts in one tap.",
                "hashtags": ["#FocusTimer", "#a", "#b", "#c"],
                "cover_text": "Stop writing empty pages",
            }

        monkeypatch.setattr(api.ai_service, "_chat_json", fake_chat)
        project, profile = self._materials()
        with pytest.raises(RuntimeError, match="question"):
            _run(api.ai_service.generate_post_kit(project, profile))

    def test_banned_claim_in_caption_is_loud(self, api, monkeypatch):
        async def fake_chat(**kwargs):
            return {
                "caption": "Stop writing empty pages — this cures anxiety fast. Ready to try?",
                "hashtags": ["#FocusTimer", "#a", "#b", "#c"],
                "cover_text": "Stop writing empty pages",
            }

        monkeypatch.setattr(api.ai_service, "_chat_json", fake_chat)
        project, profile = self._materials()
        with pytest.raises(RuntimeError, match="banned claim"):
            _run(api.ai_service.generate_post_kit(project, profile))

    def test_caption_outside_length_window_is_loud(self, api, monkeypatch):
        for caption in (
            "Timer on, pages done. What worked?",  # 34 chars: too short
            "Stop writing empty pages with one timed start — "
            "a focus timer that starts in one tap. "
            "What stalls your first sentence?",  # over 100 chars: too long
        ):
            async def fake_chat(**kwargs):
                return {
                    "caption": caption,
                    "hashtags": ["#FocusTimer", "#a", "#b", "#c"],
                    "cover_text": "Stop writing empty pages",
                }

            monkeypatch.setattr(api.ai_service, "_chat_json", fake_chat)
            project, profile = self._materials()
            with pytest.raises(RuntimeError, match="50 to 80"):
                _run(api.ai_service.generate_post_kit(project, profile))

    def test_three_relevant_hashtags_are_enough(self, api, monkeypatch):
        async def fake_chat(**kwargs):
            return {
                "caption": "Stop writing empty pages — a timer that starts in one tap. What stalls you?",
                "hashtags": ["#FocusTimer", "#studytok", "#deepwork"],
                "cover_text": "Stop writing empty pages",
            }

        monkeypatch.setattr(api.ai_service, "_chat_json", fake_chat)
        project, profile = self._materials()
        kit = _run(api.ai_service.generate_post_kit(project, profile))
        assert len(kit["hashtags"]) == 3

    def test_six_hashtags_is_loud(self, api, monkeypatch):
        async def fake_chat(**kwargs):
            return {
                "caption": "Stop writing empty pages — a timer that starts in one tap. What stalls you?",
                "hashtags": ["#FocusTimer", "#a", "#b", "#c", "#d", "#e"],
                "cover_text": "Stop writing empty pages",
            }

        monkeypatch.setattr(api.ai_service, "_chat_json", fake_chat)
        project, profile = self._materials()
        with pytest.raises(RuntimeError):
            _run(api.ai_service.generate_post_kit(project, profile))

    def test_hashtag_prompt_demands_relevance_over_trends(self, api, monkeypatch):
        seen = {}

        async def fake_chat(**kwargs):
            seen.update(kwargs)
            return {
                "caption": "Stop writing empty pages — a timer that starts in one tap. What stalls you?",
                "hashtags": ["#FocusTimer", "#studytok", "#deepwork"],
                "cover_text": "Stop writing empty pages",
            }

        monkeypatch.setattr(api.ai_service, "_chat_json", fake_chat)
        project, profile = self._materials()
        _run(api.ai_service.generate_post_kit(project, profile))
        brief = str(seen.get("system_message", "")) + str(seen.get("prompt", ""))
        assert "3 to 5" in brief
        assert "truly relevant" in brief

    def test_caption_prompt_demands_user_voice_and_length(self, api, monkeypatch):
        seen = {}

        async def fake_chat(**kwargs):
            seen.update(kwargs)
            return {
                "caption": "Stop writing empty pages — a timer that starts in one tap. What stalls you?",
                "hashtags": ["#FocusTimer", "#a", "#b", "#c"],
                "cover_text": "Stop writing empty pages",
            }

        monkeypatch.setattr(api.ai_service, "_chat_json", fake_chat)
        project, profile = self._materials()
        _run(api.ai_service.generate_post_kit(project, profile))
        brief = str(seen.get("system_message", "")) + str(seen.get("prompt", ""))
        assert "50 to 80" in brief
        assert "everyday user" in brief
        assert "founder" in brief
