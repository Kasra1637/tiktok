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


class TestDurationIsOnePass:
    """
    A video is ONE render now: a hook and a middle in a single pass.

    There is no split across jobs, so `duration_plan` is gone from the response.
    What replaced the old "report the split" behaviour is a refusal: a request
    longer than one pass is not a longer video, it is a video the workflow cannot
    make, and the founder's own demo and CTA are what they attach afterwards.
    """

    def test_over_limit_is_refused_rather_than_truncated_or_split(self, api, monkeypatch):
        """
        A 20s request on a 15s model must not silently produce a 15s video, and
        must not quietly become a two-job chain either. It is refused, and the
        message says why and what to do instead.
        """
        calls = _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Too Long", duration=20)
        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project["id"],
                payload=StudioGenerationRequest(model="minimax-h3", duration_seconds=20),
                user_id=ANON))
        assert err.value.status_code == 400
        assert "one pass" in str(err.value.detail)
        # The founder's own demo is the answer, so the message points at it
        # rather than at an extend button that no longer exists.
        assert "demo" in str(err.value.detail).lower()
        # Nothing was spent on a video we cannot deliver.
        assert calls == []

    def test_within_limit_renders_at_the_requested_length(self, api, monkeypatch):
        _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "One Pass", duration=10)
        result = _run(api.submit_project_generation(
            project_id=project["id"],
            payload=StudioGenerationRequest(model="minimax-h3"),
            user_id=ANON))
        assert "duration_plan" not in result
        assert result["duration"] == 10

    def test_exactly_the_ceiling_is_allowed(self, api, monkeypatch):
        """The boundary itself must not be refused: 15s on a 15s model is one pass."""
        _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "At Ceiling", duration=15)
        result = _run(api.submit_project_generation(
            project_id=project["id"],
            payload=StudioGenerationRequest(model="minimax-h3", duration_seconds=15),
            user_id=ANON))
        assert result["duration"] == 15

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


class TestOneRenderHasNoChain:
    """
    The chain endpoints are gone, and something must say so.

    A video is one render now. `extend_generation` and `approve_generation`
    were deleted rather than left answering calls nothing makes, so this pins
    that they are gone — otherwise a stale frontend build would keep calling
    them and get an opaque 405 instead of an explanation.

    Their columns stay (segment_index, parent_generation_id, approved), so a
    chain recorded before this change still lists its children in history.
    """

    def test_the_chain_endpoints_are_not_registered(self, api):
        paths = {r.path for r in api.app.routes if hasattr(r, "path")}
        for gone in (
            "/api/generations/{generation_id}/extend",
            "/api/generations/{generation_id}/approve",
            "/api/generations/{generation_id}/assemble",
            "/api/generations/{generation_id}/continuity",
            "/api/studio/projects/{project_id}/hook",
        ):
            assert gone not in paths, f"{gone} still exists; a video is one render"
            assert not hasattr(api, gone.rsplit("/", 1)[-1]), gone

    def test_a_generation_records_no_parent_and_no_approval(self, api, monkeypatch):
        from models import StudioGenerationRequest
        _mock_submit(api, monkeypatch, response={"id": "j"})
        project, _, _ = _ready_project(api, "One Render")
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        # The columns are still written, so the row shape is unchanged for
        # history -- they just carry their defaults forever now.
        assert gen["segment_index"] == 0
        assert gen["approved"] is False


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
        assert keys == ["minimax-h3", "minimax-h3-max"]
        assert "aleph-2" not in keys
        assert result["default"] == "minimax-h3"

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


class TestModelSelectionAtTheApiBoundary:
    """
    Which provider a render actually uses.

    video_providers.resolve() falls back to the default with a reason string, and
    on its own that is not enough: the founder is charged for a real render and
    handed a clip from a model they did not pick. These tests pin the boundary
    behaviour — an unrecognised key is refused, an omitted key is the default,
    and both generative models work by name.
    """

    def test_unknown_model_is_refused_before_spending(self, api, monkeypatch):
        from models import StudioGenerationRequest
        calls = _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Bad Model", duration=10)
        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project["id"],
                payload=StudioGenerationRequest(model="minimax-hailuo-4"),
                user_id=ANON))
        assert err.value.status_code == 400
        assert "minimax-hailuo-4" in str(err.value.detail)
        # The message has to say what IS available, or the founder cannot recover.
        assert "minimax-h3" in str(err.value.detail)
        assert "minimax-h3-max" in str(err.value.detail)
        assert not calls, "a render was submitted for an unknown model"

    def test_omitted_model_uses_hailuo_3(self, api, monkeypatch):
        from models import StudioGenerationRequest
        calls = _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Default Model", duration=10)
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert gen["model"] == "minimax-h3"
        assert len(calls) == 1

    def test_h3_max_is_honoured_when_named(self, api, monkeypatch):
        """
        The A/B path: the same script renders on the model the founder picked,
        so the comparison is meaningful.
        """
        from models import StudioGenerationRequest
        calls = _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Max Model", duration=10)
        gen = _run(api.submit_project_generation(
            project_id=project["id"],
            payload=StudioGenerationRequest(model="minimax-h3-max"),
            user_id=ANON))
        assert gen["model"] == "minimax-h3-max"
        assert len(calls) == 1

    def test_h3_max_carries_the_same_face_reference(self, api, monkeypatch):
        """
        Adding a provider must not change what the founder uploaded. One image
        goes on the request exactly as it does for Hailuo 3.
        """
        from models import StudioGenerationRequest
        calls = _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Max Face", duration=10)
        _run(api.submit_project_generation(
            project_id=project["id"],
            payload=StudioGenerationRequest(model="minimax-h3-max"),
            user_id=ANON))
        assert len(calls) == 1
        refs = calls[0].get("input_references") or []
        assert len(refs) == 1
        assert refs[0]["type"] == "image_url"
        # ...and the two-section prompt is identical on both models.
        assert "The person on camera is the person in the attached character reference" in (
            calls[0]["prompt"])
