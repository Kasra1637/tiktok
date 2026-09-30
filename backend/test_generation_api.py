"""
DB-backed tests for video generation orchestration.

OpenRouter is fully mocked, so these assert OUR rules: one job per video, the
three justified cases for a second call, the readiness and claim gates, cost
persistence, and that a failed attempt is never silently overwritten.
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
OTHER_USER = "other-user"


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-p5-")
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

    # Keep generated media out of live storage. pipeline.VIDEOS_DIR is a
    # module-level constant pointing at the real storage/videos, so a test that
    # stands in a clip on disk would otherwise write into it.
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


def _ready_project(api, name="Gen App", template_query="Stop Doing This",
                   duration=20, model_note=None, with_character=True):
    """An approved profile, a face-anchored template, and a project marked ready.

    Face-only library: every template puts a person on camera, so the fixture
    attaches a real character_reference unless a test explicitly opts out to
    exercise the refusal.
    """
    from models import (
        BrandProfileCreateRequest, ApproveAppProfileRequest,
        CreateStudioProjectRequest,
    )
    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name,
        app_category="Productivity",
        core_features=["Task timer"],
        pricing_trial="Free, Pro $79.99/year",
        claims_approved=["3-day free trial"],
        claims_banned=["cures anxiety"],
    ), user_id=ANON))
    _run(api.approve_app_profile(
        profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    template = _run(api.list_templates(q=template_query, user_id=ANON))["templates"][0]
    project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"],
        template_id=template["id"],
        duration_seconds=duration,
    ), user_id=ANON))
    from models import now_iso
    assets = []
    if with_character:
        # A real 1x1 PNG on disk so the identity resolver accepts it.
        face = Path(tempfile.mkdtemp(prefix="tiktok-ready-")) / "face.png"
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
        """UPDATE studio_projects SET assets = ?, hook_line = ?, script = ?, status = 'ready_for_generation'
           WHERE id = ?""",
        (json.dumps(assets), "Stop writing empty pages", "A short script for the app.", project["id"])))
    return _run(api.get_studio_project(project["id"], ANON)), profile, template


def _mock_submit(api, monkeypatch, response=None, raises=None):
    """Replace the provider submit call. Records the calls it receives."""
    calls = []

    async def fake_generate_video(**kwargs):
        calls.append(kwargs)
        if raises:
            raise raises
        return response or {
            "id": f"job-{len(calls)}",
            "status": "queued",
            "usage": {"cost": 0.25},
        }

    monkeypatch.setattr(api, "generate_video", fake_generate_video)
    return calls


def _mock_poll(api, monkeypatch, response):
    async def fake_poll(job_id):
        return response

    monkeypatch.setattr(api, "poll_video_job", fake_poll)


class TestSinglePassGeneration:
    def test_one_submit_produces_one_generation(self, api, monkeypatch):
        """The hook and its continuation must be ONE job, not two."""
        _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Single Pass")
        result = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        rows = _run(api.list_generations(studio_project_id=project["id"], user_id=ANON))
        assert len(rows["generations"]) == 1
        assert result["segment_role"] == "primary"

    def test_prompt_covers_the_whole_timeline(self, api, monkeypatch):
        calls = _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Prompt Coverage")
        _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert len(calls) == 1
        prompt = calls[0]["prompt"]
        assert "Stop writing empty pages" in prompt
        assert "single coherent take" in prompt.lower()

    def test_generation_records_provenance(self, api, monkeypatch):
        _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, profile, template = _ready_project(api, "Provenance")
        result = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert result["brand_profile_id"] == profile["id"]
        assert result["template_id"] == template["id"]
        assert result["template_version"] == template["version"]
        assert result["script_version"] == project["script_version"]
        assert result["model"]

    def test_cost_is_captured_on_submit(self, api, monkeypatch):
        _mock_submit(api, monkeypatch, response={"id": "j1", "usage": {"cost": 0.31}})
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Cost Submit")
        result = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert result["cost_usd"] == pytest.approx(0.31)
        assert result["cost_source"] == "usage.cost"

    def test_status_is_generating_after_submit(self, api, monkeypatch):
        _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Status After Submit")
        result = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert result["status"] == "generating"
        assert result["openrouter_job_id"]


class TestGenerationGates:
    def test_unready_project_is_blocked(self, api, monkeypatch):
        _mock_submit(api, monkeypatch)
        from models import CreateStudioProjectRequest, StudioGenerationRequest
        from models import BrandProfileCreateRequest, ApproveAppProfileRequest
        profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name="Not Ready"), user_id=ANON))
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        template = _run(api.list_templates(user_id=ANON))["templates"][0]
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"], template_id=template["id"]), user_id=ANON))
        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert err.value.status_code == 409

    def test_blocking_claim_prevents_spend(self, api, monkeypatch):
        calls = _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Blocked Claim")
        _run(api._execute(
            """UPDATE studio_projects SET safety_report = ? WHERE id = ?""",
            ('{"passed": false, "blocking": [{"claim": "cures anxiety"}]}', project["id"])))
        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert err.value.status_code == 409
        assert "cures anxiety" in str(err.value.detail)
        # Crucially, no provider call was made.
        assert calls == []

    def test_missing_script_is_blocked(self, api, monkeypatch):
        _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "No Script")
        _run(api._execute(
            "UPDATE studio_projects SET script = '' WHERE id = ?", (project["id"],)))
        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert err.value.status_code == 400

    def test_missing_project_is_404(self, api, monkeypatch):
        _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=str(uuid.uuid4()), payload=StudioGenerationRequest(), user_id=ANON))
        assert err.value.status_code == 404


class TestDurationSplitting:
    def test_over_limit_reports_the_split_rather_than_truncating(self, api, monkeypatch):
        """
        A 20s request on a 15s model must not silently produce a 15s video:
        the response has to say an extension is required.
        """
        _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Split", duration=20)
        result = _run(api.submit_project_generation(
            project_id=project["id"],
            payload=StudioGenerationRequest(model="minimax-h3"),
            user_id=ANON))
        plan = result["duration_plan"]
        assert plan["needs_extension"] is True
        assert plan["extension_seconds"] > 0
        # The job itself covers only what one pass can do.
        assert result["duration"] == plan["primary_seconds"]

    def test_within_limit_needs_no_extension(self, api, monkeypatch):
        _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "No Split", duration=20)
        result = _run(api.submit_project_generation(
            project_id=project["id"],
            payload=StudioGenerationRequest(model="seedance-2.5"),
            user_id=ANON))
        assert result["duration_plan"]["needs_extension"] is False
        assert result["duration"] == 20

    def test_editor_model_is_refused_for_the_studio(self, api, monkeypatch):
        """Aleph needs a source clip, which the template flow does not have."""
        calls = _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Editor Refused", duration=20)
        result = _run(api.submit_project_generation(
            project_id=project["id"],
            payload=StudioGenerationRequest(model="aleph-2"),
            user_id=ANON))
        assert result["model"] != "aleph-2"
        assert calls[0]["model"] != "aleph-2"


class TestPolling:
    def _submitted(self, api, monkeypatch, name="Poll App"):
        from models import StudioGenerationRequest
        _mock_submit(api, monkeypatch, response={"id": "job-poll", "usage": {"cost": 0.4}})
        project, _, _ = _ready_project(api, name)
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        return gen

    def test_poll_completes_and_persists_cost(self, api, monkeypatch):
        gen = self._submitted(api, monkeypatch, "Poll Complete")
        _mock_poll(api, monkeypatch, {
            "status": "completed",
            "unsigned_urls": ["https://example.invalid/clip.mp4"],
            "usage": {"cost": 0.55},
        })
        # Storage is not configured in tests; the URL still resolves.
        result = _run(api.poll_generation(gen["id"], ANON))
        assert result["status"] == "completed"
        assert result["video_url"] == "https://example.invalid/clip.mp4"
        assert result["cost_usd"] == pytest.approx(0.55)
        assert result["completed_at"]

    def test_poll_marks_failure_and_retryability(self, api, monkeypatch):
        gen = self._submitted(api, monkeypatch, "Poll Failed")
        _mock_poll(api, monkeypatch, {"status": "failed", "error": "HTTP 503 overloaded"})
        result = _run(api.poll_generation(gen["id"], ANON))
        assert result["status"] == "failed"
        assert result["retryable"] is True
        assert "503" in result["error"]

    def test_permanent_failure_is_not_retryable(self, api, monkeypatch):
        gen = self._submitted(api, monkeypatch, "Poll Permanent")
        _mock_poll(api, monkeypatch, {"status": "failed", "error": "Blocked by content policy"})
        result = _run(api.poll_generation(gen["id"], ANON))
        assert result["status"] == "failed"
        assert result["retryable"] is False

    def test_in_progress_stays_generating(self, api, monkeypatch):
        gen = self._submitted(api, monkeypatch, "Poll Pending")
        _mock_poll(api, monkeypatch, {"status": "processing"})
        result = _run(api.poll_generation(gen["id"], ANON))
        assert result["status"] == "generating"

    def test_completed_generation_short_circuits(self, api, monkeypatch):
        gen = self._submitted(api, monkeypatch, "Poll Done")
        _mock_poll(api, monkeypatch, {"status": "completed", "unsigned_urls": ["u"]})
        first = _run(api.poll_generation(gen["id"], ANON))
        second = _run(api.poll_generation(gen["id"], ANON))
        assert second["status"] == first["status"] == "completed"

    def test_unsubmitted_generation_cannot_poll(self, api, monkeypatch):
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Poll Unsubmitted")
        _run(api._execute(
            """INSERT INTO generations (id, studio_project_id, status, user_id, created_at, updated_at)
               VALUES (?, ?, 'submitted', ?, '', '')""",
            (str(uuid.uuid4()), project["id"], ANON)))
        row = _run(api._fetch_one(
            "SELECT id FROM generations WHERE studio_project_id = ? AND status = 'submitted'",
            (project["id"],)))
        with pytest.raises(HTTPException) as err:
            _run(api.poll_generation(row["id"], ANON))
        assert err.value.status_code == 409


class TestRetry:
    def _failed(self, api, monkeypatch, name="Retry App", error="HTTP 503 overloaded"):
        from models import StudioGenerationRequest
        calls = _mock_submit(api, monkeypatch, response={"id": "j", "usage": {"cost": 0.2}})
        project, _, _ = _ready_project(api, name)
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        # Derive retryability the same way the poll path does, so these tests
        # exercise the real decision rather than asserting a hardcoded flag.
        import generation_planning as gp
        _run(api._execute(
            "UPDATE generations SET status = 'failed', error = ?, retryable = ? WHERE id = ?",
            (error, 1 if gp.is_recoverable_error(error) else 0, gen["id"])))
        return gen, calls

    def test_retry_creates_a_child_generation(self, api, monkeypatch):
        """
        A replacement is a new row, so the failure and its cost stay in
        history instead of being overwritten.
        """
        gen, calls = self._failed(api, monkeypatch, "Retry Child")
        replacement = _run(api.retry_generation(gen["id"], ANON))
        assert replacement["id"] != gen["id"]
        assert replacement["parent_generation_id"] == gen["id"]
        assert replacement["attempt"] == 2
        assert len(calls) == 2

    def test_original_failure_is_preserved(self, api, monkeypatch):
        gen, _ = self._failed(api, monkeypatch, "Retry Preserved")
        _run(api.retry_generation(gen["id"], ANON))
        original = _run(api.get_generation(gen["id"], ANON))
        assert original["status"] == "failed"
        assert original["cost_usd"] == pytest.approx(0.2)

    def test_non_retryable_failure_is_refused(self, api, monkeypatch):
        gen, calls = self._failed(
            api, monkeypatch, "Retry Refused", error="Blocked by content policy")
        with pytest.raises(HTTPException) as err:
            _run(api.retry_generation(gen["id"], ANON))
        assert err.value.status_code == 409
        assert len(calls) == 1

    def test_completed_generation_cannot_be_retried(self, api, monkeypatch):
        from models import StudioGenerationRequest
        _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Retry Completed")
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        with pytest.raises(HTTPException) as err:
            _run(api.retry_generation(gen["id"], ANON))
        assert err.value.status_code == 409

    def test_failed_submission_is_recorded(self, api, monkeypatch):
        from models import StudioGenerationRequest
        _mock_submit(api, monkeypatch, raises=RuntimeError("HTTP 429 rate limit"))
        project, _, _ = _ready_project(api, "Submit Failure")
        with pytest.raises(HTTPException):
            _run(api.submit_project_generation(
                project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        rows = _run(api.list_generations(studio_project_id=project["id"], user_id=ANON))
        assert len(rows["generations"]) == 1
        assert rows["generations"][0]["status"] == "failed"
        assert rows["generations"][0]["retryable"] is True


class TestExtension:
    """
    The segmented influencer extension contract.

    An extension is only allowed to continue an APPROVED take produced from the
    project's app-specific STRATEGY, and it must carry that strategy forward.
    These tests pin that contract: the approval gate, the strategy-version
    match, and the prompt actually containing the app-specific brief rather
    than replaying the whole original timeline.
    """

    @staticmethod
    def _strategy(api, project_id, hook_line="I was tracking this at midnight"):
        """Give a project a minimal valid app-specific strategy."""
        from ai_service import normalize_strategy
        strategy = normalize_strategy({
            "strategy_summary": "Show a night-shift nurse logging a shift in 20 seconds.",
            "audience_problem": "Shift paperwork eats the end of a long shift.",
            "emotional_triggers": ["relief", "being seen"],
            "hook_concept": "Open on the tired laugh of someone who just realised they logged the shift.",
            "hook_line": hook_line,
            "hook_promise": "Show how the last 20 seconds of a shift get done.",
            "hook_action": "Holds up a phone to camera, already logging.",
            "hook_dialogue": "Delivered low and quick, mid-laugh.",
            "messaging_pillars": ["Logs in under 20 seconds"],
            "primary_feature": "One-tap shift logging",
            "desired_outcome": "Leaving work on time",
            "differentiation_beat": "No timesheet gymnastics.",
            "cta_strategy": "Try it free",
            "character": {
                "appearance": "late-20s healthcare worker, scrubs",
                "facial_features": "round face, dark brows",
                "hairstyle": "shoulder-length dark hair in a low bun",
                "wardrobe": "teal scrubs, silver badge, small hoop earrings",
                "body_appearance": "average height, upright but tired posture",
                "age_range": "late 20s",
                "facial_expression": "tired half-smile that breaks into a real grin",
                "styling_details": "no glasses, no visible tattoos",
            },
            "scene": {
                "camera_angle": "eye-level, phone held at arm's length",
                "framing": "medium close-up, head and shoulders",
                "lighting": "flat overhead corridor fluorescents, cool",
                "environment": "hospital staff corridor outside a break room",
                "background": "grey vinyl floor, beige wall, a fire door",
                "setting": "late shift, 11pm",
                "visual_style": "authentic handheld UGC",
                "character_positioning": "centred, phone at chest height",
                "props": "phone only, no coffee cup",
                "color_palette": "cool greys with teal scrubs",
            },
            "performance": {
                "movement": "one-handed, small gestures, phone stays in frame",
                "voice_delivery": "low, quick, tired but warm",
            },
            # Hook plus a planned arc, as generate_video_strategy now emits.
            "segments": [
                {"index": 0, "role": "hook", "seconds": 4, "goal": "land the exhaustion",
                 "script": hook_line, "action": "holds up the phone"},
                {"index": 1, "role": "continuation", "seconds": 5, "goal": "show the log",
                 "script": "One tap and it's done.", "action": "taps the phone once"},
            ] + [
                {"index": i, "role": "cta" if i == 7 else "continuation", "seconds": 5,
                 "goal": f"beat {i}", "script": f"Beat {i}.",
                 "action": f"action {i}"}
                for i in range(2, 8)
            ],
            "continuity_contract": {
                "established": [
                    "the same person in teal scrubs",
                    "a hospital staff corridor",
                    "cool overhead lighting",
                    "a phone held at chest height",
                ],
                "must_not_change": [
                    "the face",
                    "the low bun",
                    "the teal scrubs and silver badge",
                    "the corridor background",
                    "the eye-level medium close-up framing",
                ],
                "do_not_repeat": [
                    "the hook line about logging at midnight",
                    "the opening laugh",
                ],
            },
        })
        _run(api._execute(
            "UPDATE studio_projects SET strategy = ?, strategy_version = 1 WHERE id = ?",
            (json.dumps(strategy), project_id)))
        return strategy

    def _completed(self, api, monkeypatch, name="Extend App", model="seedance-2.5",
                   approve=True, with_strategy=True):
        from models import StudioGenerationRequest
        _mock_submit(api, monkeypatch, response={"id": "j", "usage": {"cost": 0.3}})
        project, _, _ = _ready_project(api, name)
        if with_strategy:
            self._strategy(api, project["id"])
        gen = _run(api.submit_project_generation(
            project_id=project["id"],
            payload=StudioGenerationRequest(model=model), user_id=ANON))
        _run(api._execute(
            "UPDATE generations SET status = 'completed', video_url = 'https://x/y.mp4' WHERE id = ?",
            (gen["id"],)))
        if approve:
            _run(api.approve_generation(
                gen["id"], __import__("models").ApproveSegmentRequest(), ANON))
        return _run(api.get_generation(gen["id"], ANON))

    def test_extend_creates_a_linked_second_job(self, api, monkeypatch):
        gen = self._completed(api, monkeypatch, "Extend OK")
        from models import StudioGenerationRequest
        extension = _run(api.extend_generation(
            gen["id"], StudioGenerationRequest(duration_seconds=5), ANON))
        assert extension["segment_role"] == "extension"
        assert extension["parent_generation_id"] == gen["id"]
        assert extension["extension_of"] == gen["id"]
        # The chain is positional, so the assembler can order it.
        assert extension["segment_index"] == 1
        assert extension["strategy_version"] == 1

    def test_unapproved_segment_cannot_be_extended(self, api, monkeypatch):
        """A rejected take must never become the opening of the final video."""
        gen = self._completed(api, monkeypatch, "Extend Unapproved", approve=False)
        from models import StudioGenerationRequest
        with pytest.raises(HTTPException) as err:
            _run(api.extend_generation(gen["id"], StudioGenerationRequest(duration_seconds=5), ANON))
        assert err.value.status_code == 409
        assert "Approve" in str(err.value.detail)

    def test_project_without_a_strategy_keeps_the_legacy_extension(self, api, monkeypatch):
        """
        A project with no strategy stays on the original one-shot flow, and its
        Extend button must keep working exactly as before. The segmented
        contract below only applies once a strategy exists.
        """
        gen = self._completed(api, monkeypatch, "Extend No Strategy", with_strategy=False)
        from models import StudioGenerationRequest
        calls = _mock_submit(api, monkeypatch, response={"id": "j2"})
        extension = _run(api.extend_generation(
            gen["id"], StudioGenerationRequest(duration_seconds=5), ANON))
        assert extension["segment_role"] == "extension"
        assert extension["segment_index"] == 0
        assert not extension.get("continuity")
        assert "CONTINUES an existing video" in calls[0]["prompt"]

    def test_extension_refuses_a_stale_strategy_version(self, api, monkeypatch):
        """A hook made under strategy v1 must not be extended under v2."""
        gen = self._completed(api, monkeypatch, "Extend Stale Strategy")
        _run(api._execute(
            "UPDATE studio_projects SET strategy_version = 2 WHERE id = ?",
            (gen["studio_project_id"],)))
        from models import StudioGenerationRequest
        with pytest.raises(HTTPException) as err:
            _run(api.extend_generation(gen["id"], StudioGenerationRequest(duration_seconds=5), ANON))
        assert err.value.status_code == 409
        assert "strategy v1" in str(err.value.detail)

    def test_extension_prompt_carries_the_app_strategy_and_continuity(self, api, monkeypatch):
        """
        The extension must not replay the hook with a new face.

        It has to carry the app-specific brief, the locked persona and scene,
        and an explicit statement of what the opening already established.
        """
        from models import StudioGenerationRequest
        gen = self._completed(api, monkeypatch, "Extend Prompt")
        calls = _mock_submit(api, monkeypatch, response={"id": "j2", "usage": {"cost": 0.1}})
        _run(api.extend_generation(gen["id"], StudioGenerationRequest(duration_seconds=5), ANON))
        prompt = calls[0]["prompt"]

        # App-specific messaging survives the extension.
        assert "Shift paperwork eats the end of a long shift" in prompt
        assert "One-tap shift logging" in prompt
        assert "Try it free" in prompt
        # The locked persona is restated, not assumed.
        assert "teal scrubs" in prompt
        assert "hospital staff corridor" in prompt
        assert "low bun" in prompt
        # Continuity, in both directions: what is fixed, and what not to repeat.
        assert "opening segment already established" in prompt
        assert "Do NOT repeat" in prompt
        assert "Do not re-introduce the app" in prompt
        # And it must NOT regenerate the whole video from the top.
        assert "One continuous 5-second take" in prompt

    def test_extension_beyond_provider_max_is_refused(self, api, monkeypatch):
        gen = self._completed(api, monkeypatch, "Extend Too Long", model="minimax-h3")
        from models import StudioGenerationRequest
        with pytest.raises(HTTPException) as err:
            _run(api.extend_generation(gen["id"], StudioGenerationRequest(duration_seconds=30), ANON))
        assert err.value.status_code == 400

    def test_incomplete_generation_cannot_be_extended(self, api, monkeypatch):
        from models import StudioGenerationRequest
        _mock_submit(api, monkeypatch, response={"id": "j"})
        project, _, _ = _ready_project(api, "Extend Pending")
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        with pytest.raises(HTTPException) as err:
            _run(api.extend_generation(gen["id"], StudioGenerationRequest(duration_seconds=5), ANON))
        assert err.value.status_code == 409


class TestListingAndCapabilities:
    def test_history_filters_by_project(self, api, monkeypatch):
        from models import StudioGenerationRequest
        _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Filter Project")
        _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        scoped = _run(api.list_generations(studio_project_id=project["id"], user_id=ANON))
        assert len(scoped["generations"]) == 1
        assert _run(api.list_generations(studio_project_id=str(uuid.uuid4()), user_id=ANON))["generations"] == []

    def test_listing_is_scoped_to_user(self, api, monkeypatch):
        from models import StudioGenerationRequest
        _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Private Gen")
        _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert _run(api.list_generations(user_id=OTHER_USER))["generations"] == []

    def test_list_response_omits_the_prompt(self, api, monkeypatch):
        from models import StudioGenerationRequest
        _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Prompt Hidden")
        _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        listing = _run(api.list_generations(studio_project_id=project["id"], user_id=ANON))
        assert "prompt_used" not in listing["generations"][0]

    def test_detail_response_includes_the_prompt(self, api, monkeypatch):
        from models import StudioGenerationRequest
        _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Prompt Shown")
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        detail = _run(api.get_generation(gen["id"], ANON))
        assert "single coherent take" in detail["prompt_used"]

    def test_another_users_generation_is_404(self, api, monkeypatch):
        from models import StudioGenerationRequest
        _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Isolated Gen")
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        with pytest.raises(HTTPException) as err:
            _run(api.get_generation(gen["id"], OTHER_USER))
        assert err.value.status_code == 404

    def test_capability_endpoint_reports_studio_models(self, api):
        result = _run(api.list_studio_video_models())
        keys = [m["key"] for m in result["models"]]
        assert "seedance-2.5" in keys and "minimax-h3" in keys
        assert "aleph-2" not in keys
        assert result["default"]

    def test_capability_endpoint_lists_ineligible_separately(self, api):
        result = _run(api.list_studio_video_models())
        assert any(m["key"] == "aleph-2" for m in result["ineligible"])


class TestStudioIdentityReference:
    def _anchor_project(self, api, name="Anchor Person"):
        """A ready project with a real character_reference asset attached."""
        from models import (
            BrandProfileCreateRequest, ApproveAppProfileRequest,
            CreateStudioProjectRequest, now_iso,
        )
        profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name=name, app_category="Productivity",
        ), user_id=ANON))
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        template = _run(api.list_templates(user_id=ANON))["templates"][0]
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"], template_id=template["id"],
        ), user_id=ANON))

        # A real 1x1 PNG on disk so the identity resolver accepts it.
        face = Path(tempfile.mkdtemp(prefix="tiktok-anchor-")) / "face.png"
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
        _run(api._execute(
            "UPDATE studio_projects SET assets = ?, hook_line = ?, script = ?,"
            " status = 'ready_for_generation' WHERE id = ?",
            (json.dumps([{
                "asset_id": asset_id, "kind": "character_reference",
                "label": "Founder face", "file_path": str(face),
            }]),
             "Stop writing empty pages", "A short script for the app.", project["id"])))
        return _run(api.get_studio_project(project["id"], ANON))

    def test_identity_reference_rides_along(self, api, monkeypatch):
        from models import StudioGenerationRequest
        project = self._anchor_project(api)
        calls = _mock_submit(api, monkeypatch)
        _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert len(calls) == 1
        refs = calls[0].get("input_references") or []
        assert len(refs) == 1
        assert refs[0]["type"] == "image_url"
        assert refs[0]["image_url"]["url"].startswith("data:image/png;base64,")
        # The photograph is named as the only authority on who the person is.
        assert "The person on camera is the person in the attached character reference" in (
            calls[0]["prompt"]
        )
        assert "The image is the only authority on who they are" in calls[0]["prompt"]
        # ...and no invented description of them rides along with it.
        for invented in ("round face", "teal scrubs", "low bun"):
            assert invented not in calls[0]["prompt"], f"prompt invents an appearance: {invented}"

    def test_no_anchor_means_refusal_not_silent_generation(self, api, monkeypatch):
        """
        Face-only library: a project with no character reference cannot
        generate at all. The refusal happens before the provider is called —
        there is no mode where the model quietly invents a presenter.
        """
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "No Anchor", with_character=False)
        calls = _mock_submit(api, monkeypatch)
        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert err.value.status_code == 409
        assert "character reference" in str(err.value.detail)
        assert not calls, "the provider was called despite the refusal"

    def test_a_template_that_needs_a_face_refuses_without_one(self, api, monkeypatch):
        """
        The requirement used to be decoration: it was listed on the template and
        in the studio, but nothing stopped the click. A paid render could go out
        with no identity input at all, and the model free to invent a presenter.
        The refusal has to happen before the provider is called, not after.
        """
        from models import StudioGenerationRequest
        project = self._anchor_project(api, "Needs A Face")
        # Drop the reference, and use a template that genuinely puts a person on
        # camera so the requirement applies.
        _run(api._execute(
            "UPDATE studio_projects SET assets = '[]', template_id = "
            "(SELECT id FROM hook_templates WHERE required_assets LIKE '%character_reference%' "
            "AND review_status = 'approved' LIMIT 1) WHERE id = ?",
            (project["id"],)))
        calls = _mock_submit(api, monkeypatch)
        with pytest.raises(HTTPException) as excinfo:
            _run(api.submit_project_generation(
                project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert excinfo.value.status_code == 409
        assert "character reference" in str(excinfo.value.detail)
        assert not calls, "the provider was called despite the refusal"

    def test_retired_attachment_is_refused_before_the_face_check(self, api, monkeypatch):
        """
        A project holding a screenshot from before uploads went face-only is
        refused loudly. The retired input is reported first — even though no
        face is attached either — so the founder detaches it instead of
        chasing the face requirement on a project that still cannot run.
        """
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Retired Attach", with_character=False)
        _run(api._execute(
            "UPDATE studio_projects SET assets = ? WHERE id = ?",
            (json.dumps([{
                "asset_id": "old-shot", "kind": "screenshot",
                "label": "Old screenshot", "file_path": "gone.png",
            }]), project["id"])))
        calls = _mock_submit(api, monkeypatch)
        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert err.value.status_code == 409
        assert "face-only" in str(err.value.detail)
        assert not calls, "the provider was called despite the refusal"

    def test_missing_file_is_refused_loudly(self, api, monkeypatch):
        from models import StudioGenerationRequest
        project = self._anchor_project(api, "Missing Face")
        _run(api._execute(
            "UPDATE studio_projects SET assets = ? WHERE id = ?",
            (json.dumps([{
                "asset_id": "no-such-asset", "kind": "character_reference",
                "label": "Founder face", "file_path": "does-not-exist.png",
            }]), project["id"])))
        _mock_submit(api, monkeypatch)
        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert err.value.status_code == 409

    def test_archive_marks_status(self, api, monkeypatch):
        from models import StudioGenerationRequest
        _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Archive Gen")
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        archived = _run(api.archive_generation(gen["id"], ANON))
        assert archived["status"] == "archived"
