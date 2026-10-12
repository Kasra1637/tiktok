"""
DB-backed tests for video generation orchestration.

OpenRouter is fully mocked, so these assert OUR rules: one job per video, the
three justified cases for a second call, the readiness and claim gates, cost
persistence, and that a failed attempt is never silently overwritten.
"""
import asyncio
import importlib
import io
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import mp4_samples  # noqa: E402

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


# A minimal but structurally real strategy: the fields build_segment_prompt
# reads. Written straight to the row so these tests assert our gates rather than
# the strategy builder's output.
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


def _ready_project(api, name="Gen App", template_query="Stop Doing This",
                   duration=20, model_note=None, with_character=True,
                   user_id=ANON):
    """An approved profile, a face-anchored template, and a project marked ready.

    Face-only library: every template puts a person on camera, so the fixture
    attaches a real character_reference unless a test explicitly opts out to
    exercise the refusal.

    The project also carries a strategy stamped against its current
    script_version. Rendering without one is now refused server-side, because a
    video built from the plan alone is a generic take with the app's name in it
    -- so a fixture that omitted it was testing a path no founder can reach.
    """
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
    ), user_id=user_id))
    _run(api.approve_app_profile(
        profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=user_id))
    template = _run(api.list_templates(q=template_query, user_id=user_id))["templates"][0]
    project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"],
        template_id=template["id"],
        duration_seconds=duration,
        # Marking ready now requires a stated objective; see mark_project_ready.
        objective="demonstrate_feature",
    ), user_id=user_id))
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
             str(face), "Founder face", now, now, user_id)))
        assets = [{
            "asset_id": asset_id, "kind": "character_reference",
            "label": "Founder face", "file_path": str(face),
        }]
    _run(api._execute(
        """UPDATE studio_projects SET assets = ?, hook_line = ?, script = ?,
              status = 'ready_for_generation', script_version = 1,
              strategy = ?, strategy_version = 1, strategy_script_version = 1
           WHERE id = ?""",
        (json.dumps(assets), "Stop writing empty pages", "A short script for the app.",
         json.dumps(FAKE_STRATEGY), project["id"])))
    return _run(api.get_studio_project(project["id"], user_id)), profile, template


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
        # The strategy's hook line is what the video opens on, NOT the plan's
        # hook_line. They are two different fields and the strategy is the one
        # the founder reviewed as the video's own words -- build_single_pass_prompt
        # read the plan's copy, which is the generic path this no longer takes.
        assert FAKE_STRATEGY["hook_line"] in prompt
        assert "ONE continuous" in prompt

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

    def test_status_is_generating_after_submit(self, api, monkeypatch):
        _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Status After Submit")
        result = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert result["status"] == "generating"
        assert result["openrouter_job_id"]


class TestResolutionOverride:
    """
    heygen-video-1 offers 480p beside its 768p default so renders can be
    compared cheaply. The request carries the choice end to end; anything
    unlisted is refused before anything is billed.
    """

    def test_unlisted_resolution_is_refused_with_the_allowed_values(self, api, monkeypatch):
        _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Resolution Refused")
        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project["id"],
                payload=StudioGenerationRequest(model="heygen-video-1", resolution="2K"),
                user_id=ANON))
        assert err.value.status_code == 400
        assert "480p" in str(err.value.detail)
        assert "768p" in str(err.value.detail)

    def test_listed_resolution_reaches_the_provider_call(self, api, monkeypatch):
        calls = _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Resolution Override")
        _run(api.submit_project_generation(
            project_id=project["id"],
            payload=StudioGenerationRequest(model="heygen-video-1", resolution="480p"),
            user_id=ANON))
        assert calls[0]["resolution"] == "480p"

    def test_omitted_resolution_stays_omitted(self, api, monkeypatch):
        calls = _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Resolution Default")
        _run(api.submit_project_generation(
            project_id=project["id"],
            payload=StudioGenerationRequest(model="heygen-video-1"),
            user_id=ANON))
        assert calls[0]["resolution"] is None


class TestIdempotency:
    """
    One click, one render.

    The generate endpoint had no key and no in-flight check, so a double-tap, a
    client retry of the same request, or the same project in two tabs could each
    create a real billed job. The provider is mocked throughout, so these assert
    how many jobs were SUBMITTED rather than what came back.
    """

    def _submit(self, api, key, **kw):
        from models import StudioGenerationRequest
        return _run(api.submit_project_generation(
            project_id=kw["project_id"],
            payload=StudioGenerationRequest(idempotency_key=key),
            user_id=kw.get("user_id", ANON),
        ))

    def test_the_same_key_returns_the_first_generation(self, api, monkeypatch):
        calls = _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Idem Repeat")
        first = self._submit(api, "key-one", project_id=project["id"])
        second = self._submit(api, "key-one", project_id=project["id"])
        assert first["id"] == second["id"]
        # The whole point: one provider submit, not two billed jobs.
        assert len(calls) == 1
        rows = _run(api.list_generations(studio_project_id=project["id"], user_id=ANON))
        assert len(rows["generations"]) == 1

    def test_a_fresh_key_is_a_fresh_render(self, api, monkeypatch):
        """Reuses must not become a way to make "Generate another" free."""
        calls = _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Idem Fresh")
        first = self._submit(api, "key-a", project_id=project["id"])
        second = self._submit(api, "key-b", project_id=project["id"])
        assert first["id"] != second["id"]
        assert len(calls) == 2

    def test_no_key_keeps_the_old_behaviour(self, api, monkeypatch):
        """A caller that sends no key is unaffected -- twice is still twice."""
        calls = _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Idem None")
        first = self._submit(api, None, project_id=project["id"])
        second = self._submit(api, "", project_id=project["id"])
        assert first["id"] != second["id"]
        assert len(calls) == 2

    def test_one_users_key_does_not_silence_another(self, api, monkeypatch):
        """
        The lookup is (user_id, idempotency_key), so a key is not a
        cross-tenant suppressor: two founders whose clients happened to pick the
        same key each get their own render.
        """
        calls = _mock_submit(api, monkeypatch)
        mine, _, _ = _ready_project(api, "Idem Tenant A")
        theirs, _, _ = _ready_project(api, "Idem Tenant B", user_id=OTHER_USER)
        first = self._submit(api, "shared-key", project_id=mine["id"])
        second = self._submit(
            api, "shared-key", project_id=theirs["id"], user_id=OTHER_USER)
        assert first["id"] != second["id"]
        assert len(calls) == 2

    def test_a_replay_is_flagged_so_the_ui_can_tell(self, api, monkeypatch):
        _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Idem Flagged")
        self._submit(api, "key-flag", project_id=project["id"])
        replay = self._submit(api, "key-flag", project_id=project["id"])
        assert replay.get("idempotent_replay") is True


class TestGenerationGates:
    def test_unready_project_is_blocked(self, api, monkeypatch):
        _mock_submit(api, monkeypatch)
        from models import CreateStudioProjectRequest, StudioGenerationRequest
        from models import BrandProfileCreateRequest, ApproveAppProfileRequest
        profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name="Not Ready",
            brand_description="A focus timer for people who stall on starting.",
            core_features=["Task timer"],
            usage_moments=["Starting a task they have been avoiding"],
            outcome_statements=[{
                "outcome": "Starting without stalling on setup",
                "who_feels_it": "people who stall on starting",
                "from_feature": "Task timer",
                "how_it_helps": "The timer starts in one tap so there is nothing to set up",
            }],
        ), user_id=ANON))
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        template = _run(api.list_templates(user_id=ANON))["templates"][0]
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"], template_id=template["id"]), user_id=ANON))
        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert err.value.status_code == 409

    def test_marking_ready_refuses_a_project_with_no_photograph(self, api):
        """
        Marking ready is what enables the Generate button, so it is the last
        place a missing photo can be caught before the founder spends. Without
        this the project was approved, the button lit up, and the refusal
        arrived only at the click — where a 409 reads as a broken app rather
        than a rule they had not met.

        The generate endpoint keeps its own check; this one is about the button.
        """
        from models import CreateStudioProjectRequest, StudioGenerationRequest
        from models import BrandProfileCreateRequest, ApproveAppProfileRequest
        profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name="No Photo",
            brand_description="A focus timer for people who stall on starting.",
            core_features=["Task timer"],
            usage_moments=["Starting a task they have been avoiding"],
            outcome_statements=[{
                "outcome": "Starting without stalling on setup",
                "who_feels_it": "people who stall on starting",
                "from_feature": "Task timer",
                "how_it_helps": "The timer starts in one tap so there is nothing to set up",
            }],
        ), user_id=ANON))
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        template = _run(api.list_templates(user_id=ANON))["templates"][0]
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"],
            template_id=template["id"],
            objective="demonstrate_feature",
        ), user_id=ANON))
        # Write the plan the way _ready_project does, straight to the row. generate_plan
        # would make a live LLM call, which is not what this test is about.
        from models import now_iso
        _run(api._execute(
            """UPDATE studio_projects SET hook_line = ?, script = ?, script_version = 1
               WHERE id = ?""",
            ("Stop writing empty pages.", "Stop writing empty pages.", project["id"])))

        with pytest.raises(HTTPException) as err:
            _run(api.mark_project_ready(project["id"], user_id=ANON))
        assert err.value.status_code == 400
        detail = err.value.detail
        # Says what is missing, why it matters, and which step fixes it.
        assert "character reference" in detail
        assert "looks nothing like you" in detail
        assert "Template & photo" in detail

        # And the project is still draft, so the button never lights up.
        fresh = _run(api.get_studio_project(project["id"], user_id=ANON))
        assert fresh["status"] != "ready_for_generation"

        # The generate endpoint still refuses independently, for any caller
        # that reaches it without going through the ready gate.
        with pytest.raises(HTTPException) as gen_err:
            _run(api.submit_project_generation(
                project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert gen_err.value.status_code == 409

    def test_blocking_claim_prevents_spend(self, api, monkeypatch):
        calls = _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Blocked Claim")
        # Put the banned claim in the SCRIPT rather than in the stored report.
        # The gate used to read safety_report straight off the row, so a test
        # could make it fail by writing that column. It is now recomputed from
        # the project and the live profile, so the claim has to be real for the
        # verdict to be real.
        _run(api._execute(
            "UPDATE studio_projects SET script = ? WHERE id = ?",
            ("Taskly cures anxiety for good.", project["id"])))
        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert err.value.status_code == 409
        assert "cures anxiety" in str(err.value.detail)
        # Crucially, no provider call was made.
        assert calls == []

    def test_a_claim_banned_after_approval_still_blocks(self, api, monkeypatch):
        """
        The safety report stored on the project is a cache, and must not be able
        to wave through a claim the App Profile now bans.

        App Profile edits deliberately do NOT revoke approval, so this is an
        ordinary sequence: research, approve, mark the plan ready, then go back
        and ban a claim on the profile. The cached "passed" verdict written at
        ready-time is still on the project row, and reading it would render the
        newly-banned claim for money.
        """
        from models import BrandProfileUpdateRequest, StudioGenerationRequest
        calls = _mock_submit(api, monkeypatch)
        project, profile, _ = _ready_project(api, "Late Ban")
        _run(api._execute(
            "UPDATE studio_projects SET script = ? WHERE id = ?",
            ("Taskly cures anxiety for good.", project["id"])))

        # Banned after the project was approved and marked ready. The profile
        # still reads as approved, which is the point.
        _run(api.update_app_profile(
            profile_id=profile["id"],
            payload=BrandProfileUpdateRequest(claims_banned=["cures anxiety"]),
            user_id=ANON))
        assert _run(api.get_app_profile(profile["id"], ANON))["status"] == "approved"

        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert err.value.status_code == 409
        assert "cures anxiety" in str(err.value.detail)
        assert calls == []

    def test_mark_ready_recomputes_the_verdict_it_stores(self, api, monkeypatch):
        """
        The panel the founder approves against must be the same verdict the
        render is checked against.

        Otherwise approving shows a green SafetyPanel from a stale cache and the
        Generate button then refuses, which reads as a bug rather than a rule.
        """
        from models import BrandProfileUpdateRequest
        project, profile, _ = _ready_project(api, "Stale Panel")
        _run(api._execute(
            "UPDATE studio_projects SET script = ? WHERE id = ?",
            ("Taskly cures anxiety for good.", project["id"])))
        _run(api.update_app_profile(
            profile_id=profile["id"],
            payload=BrandProfileUpdateRequest(claims_banned=["cures anxiety"]),
            user_id=ANON))
        with pytest.raises(HTTPException) as err:
            _run(api.mark_project_ready(project_id=project["id"], user_id=ANON))
        assert err.value.status_code == 409

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



class TestPolling:
    def _submitted(self, api, monkeypatch, name="Poll App"):
        from models import StudioGenerationRequest
        _mock_submit(api, monkeypatch, response={"id": "job-poll"})
        project, _, _ = _ready_project(api, name)
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        return gen

    def test_poll_completes_and_persists_the_result(self, api, monkeypatch):
        gen = self._submitted(api, monkeypatch, "Poll Complete")
        _mock_poll(api, monkeypatch, {
            "status": "completed",
            "unsigned_urls": ["https://example.invalid/clip.mp4"],
        })
        # Storage is not configured in tests; the URL still resolves.
        result = _run(api.poll_generation(gen["id"], ANON))
        assert result["status"] == "completed"
        assert result["video_url"] == "https://example.invalid/clip.mp4"
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

    def test_expired_is_terminal_not_endless_generating(self, api, monkeypatch):
        """
        OpenRouter lists "expired" in its status enum, but it matched none of
        the failure branches — so the row polled forever with no banner.
        Expired is terminal: the provider discarded the job, its clip is not
        recoverable, and the message must say retrying renders anew rather
        than repairing this one.
        """
        gen = self._submitted(api, monkeypatch, "Poll Expired")
        _mock_poll(api, monkeypatch, {"status": "expired"})
        result = _run(api.poll_generation(gen["id"], ANON))
        assert result["status"] == "failed"
        assert result["retryable"] is True
        assert "expired" in result["error"]
        assert "renders it anew" in result["error"]

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
        A replacement is a new row, so the failure stays in history
        instead of being overwritten.
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
        assert original["error"]

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

    def test_retry_is_refused_when_the_project_is_no_longer_ready(self, api, monkeypatch):
        """
        A retry is the same render, so it obeys the same readiness gate.

        This path used to load the project and call _submit_generation directly,
        inheriting none of the submit checks. Editing a project back to draft and
        then retrying an old failure still spent real money.
        """
        from models import StudioGenerationRequest, UpdateStudioProjectRequest
        gen, calls = self._failed(api, monkeypatch, "Retry Not Ready")
        _run(api.update_studio_project(
            project_id=gen["studio_project_id"],
            payload=UpdateStudioProjectRequest(hook_line="Rewritten after the failure"),
            user_id=ANON,
        ))
        with pytest.raises(HTTPException) as err:
            _run(api.retry_generation(gen["id"], ANON))
        assert err.value.status_code == 409
        # Refused before the provider was called, so nothing was spent.
        assert len(calls) == 1

    def test_retry_is_refused_when_the_profile_is_no_longer_approved(self, api, monkeypatch):
        """
        Retry used to load the App Profile by id and render against whatever
        state it happened to be in, skipping the approval requirement entirely.

        Note that editing a profile deliberately does NOT revoke approval, so
        the unapproved state is reached the way it is reached in the product: the
        row is a draft that was never approved.
        """
        gen, calls = self._failed(api, monkeypatch, "Retry Unapproved")
        project = _run(api.get_studio_project(gen["studio_project_id"], ANON))
        _run(api._execute(
            "UPDATE brand_profiles SET status = 'draft' WHERE id = ?",
            (project["brand_profile_id"],)))
        with pytest.raises(HTTPException) as err:
            _run(api.retry_generation(gen["id"], ANON))
        assert err.value.status_code == 409
        assert len(calls) == 1

    def test_retry_refuses_a_length_the_model_can_no_longer_fill(self, api, monkeypatch):
        """
        A recorded length past the current model's ceiling used to be silently
        clamped, so the founder got a shorter clip than the one that was asked for
        than the plan describes.
        """
        gen, calls = self._failed(api, monkeypatch, "Retry Long")
        _run(api._execute(
            "UPDATE generations SET duration = ? WHERE id = ?", (9999, gen["id"])))
        with pytest.raises(HTTPException) as err:
            _run(api.retry_generation(gen["id"], ANON))
        assert err.value.status_code == 400
        assert len(calls) == 1

    def test_retry_refuses_a_model_that_has_left_the_allowlist(self, api, monkeypatch):
        """
        resolve() falls back to the default for a model that is no longer
        allowed, which on the retry path meant paying for one model and getting
        another with no error. The refusal is what makes the retry trustworthy.
        """
        import video_providers
        gen, calls = self._failed(api, monkeypatch, "Retry Model Drift")
        real_allowlist = video_providers._allowlist

        def empty_allowlist():
            return [k for k in real_allowlist() if k != gen["model"]]

        monkeypatch.setattr(video_providers, "_allowlist", empty_allowlist)
        with pytest.raises(HTTPException) as err:
            _run(api.retry_generation(gen["id"], ANON))
        assert err.value.status_code == 409
        assert len(calls) == 1

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

    def test_every_response_hands_out_a_url_the_media_route_will_accept(self, api, monkeypatch):
        """
        The media route is signed now, so a response carrying a bare
        /api/media/videos/x.mp4 gives the player a 404. This walks every endpoint
        that returns a generation — detail, list, history, asset usage — because
        each reaches the client by a different route and a miss on any of them
        breaks a screen that otherwise works.

        History is the one worth watching: it builds its rows by hand instead of
        going through _public_generation, so it is the one most likely to miss
        the signing, and its player sits on the page a founder uses most. It
        takes `r2_url || video_url`, so both fields are asserted here: signing
        only video_url is exactly how that row ended up saying "Preview
        unavailable" for a clip whose durable copy was the local fallback path.
        """
        import media_signing

        from models import StudioGenerationRequest
        _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Signed URL")
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        _mock_poll(api, monkeypatch, {
            "status": "completed",
            "unsigned_urls": ["https://example.invalid/clip.mp4"],
        })
        _run(api.poll_generation(gen["id"], ANON))
        # The poll stored a provider URL, which is not a media path and so has
        # nothing to sign. Point the row at real ones so this exercises the
        # signing rather than passing on an unrelated URL shape. Both fields
        # carry the path, which is the shape a render has when the upload to
        # cloud storage failed and the local copy became the durable one.
        media_path = f"/api/media/videos/{gen['id']}.mp4"
        _run(api._execute(
            "UPDATE generations SET video_url = ?, r2_url = ? WHERE id = ?",
            (media_path, media_path, gen["id"])))

        def assert_plays(payload, label):
            for field in ("video_url", "r2_url"):
                url = payload.get(field)
                assert url and url.startswith("/api/media/videos/"), (
                    f"{label}: expected a media path in {field}, got {url!r}")
                assert "?" in url, f"{label}: {field} ({url}) carries no signature"
                query = dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))
                assert media_signing.verify(
                    url.split("/")[-1].split("?", 1)[0], query["exp"], query["sig"]
                ), f"{label}: the media route would reject {field} {url}"

        assert_plays(_run(api.get_generation(gen["id"], user_id=ANON)), "detail")
        assert_plays(
            _run(api.list_generations(studio_project_id=project["id"], user_id=ANON))["generations"][0],
            "list",
        )
        assert_plays(_run(api.generation_history(user_id=ANON))["generations"][0], "history")

    def test_detail_response_includes_the_prompt(self, api, monkeypatch):
        from models import StudioGenerationRequest
        _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Prompt Shown")
        gen = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        detail = _run(api.get_generation(gen["id"], ANON))
        assert FAKE_STRATEGY["hook_line"] in detail["prompt_used"]

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
        """
        The endpoint offers exactly the generative providers that remain. The
        default stays Hailuo 3.
        """
        result = _run(api.list_studio_video_models())
        keys = [m["key"] for m in result["models"]]
        assert keys == ["minimax-h3", "minimax-h3-max", "heygen-video-1"]
        assert "aleph-2" not in keys
        assert result["default"] == "minimax-h3"



class TestStudioIdentityReference:
    def _anchor_project(self, api, name="Anchor Person"):
        """A ready project with a real character_reference asset attached."""
        from models import (
            BrandProfileCreateRequest, ApproveAppProfileRequest,
            CreateStudioProjectRequest, now_iso,
        )
        profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name=name, app_category="Productivity",
            brand_description="A focus timer for people who stall on starting.",
            core_features=["Task timer"],
            usage_moments=["Starting a task they have been avoiding"],
            outcome_statements=[{
                "outcome": "Starting without stalling on setup",
                "who_feels_it": "people who stall on starting",
                "from_feature": "Task timer",
                "how_it_helps": "The timer starts in one tap so there is nothing to set up",
            }],
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
            " status = 'ready_for_generation', script_version = 1,"
            " strategy = ?, strategy_version = 1, strategy_script_version = 1"
            " WHERE id = ?",
            (json.dumps([{
                "asset_id": asset_id, "kind": "character_reference",
                "label": "Founder face", "file_path": str(face),
            }]),
             "Stop writing empty pages", "A short script for the app.",
             json.dumps(FAKE_STRATEGY), project["id"])))
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
        # Hailuo 3 keeps the reference-image field, so nothing goes in the
        # frame slot — that routing is H3 Max's alone.
        assert calls[0].get("reference_image_path") is None
        # Hailuo 3 and HeyGen both keep the reference-image field, so nothing
        # goes in the frame slot for either — that routing is H3 Max's alone.
        # The photograph is named as the only authority on who the person is.
        assert "The person on camera is the person in the attached character reference" in (
            calls[0]["prompt"]
        )
        assert "The image is the only authority on the person" in calls[0]["prompt"]
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
        in the studio, but nothing stopped the click. A render could go out
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

    def test_h3_max_carries_identity_as_first_frame(self, api, monkeypatch):
        """
        Hailuo 3 Max refuses input_references outright — proven live, the
        serving provider 400s the submit. So the same face rides as the opening
        frame instead, the one image field OpenRouter documents as supported
        for this model. What the founder uploaded still reaches the render;
        only the field changes, chosen per model at submit time.
        """
        from models import StudioGenerationRequest
        calls = _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "Max Face", duration=10)
        _run(api.submit_project_generation(
            project_id=project["id"],
            payload=StudioGenerationRequest(model="minimax-h3-max"),
            user_id=ANON))
        assert len(calls) == 1
        assert not calls[0].get("input_references"), \
            "Max must never send input_references — the provider refuses them"
        face = calls[0].get("reference_image_path")
        assert face is not None, "the photo must still ride along, as the first frame"
        assert Path(str(face)).is_file()
        # ...and the two-section prompt is identical on both models.
        assert "The person on camera is the person in the attached character reference" in (
            calls[0]["prompt"])

    def test_heygen_carries_identity_as_a_reference_not_a_pinned_frame(self, api, monkeypatch):
        """
        The whole-clip rule for HeyGen: no frame may be pinned.

        Sending the founder's photograph in the frame slot is what made the
        opening of every clip the uploaded photo itself — its room, its light,
        its framing — with the planned scene only arriving once the model had
        morphed away from it. Identity goes into input_references instead, the
        field Hailuo 3 uses, so the first frame is already the plan and the
        provider generates the whole clip from it.
        """
        from models import StudioGenerationRequest
        calls = _mock_submit(api, monkeypatch)
        project, _, _ = _ready_project(api, "HeyGen Face", duration=10)
        _run(api.submit_project_generation(
            project_id=project["id"],
            payload=StudioGenerationRequest(model="heygen-video-1"),
            user_id=ANON))
        assert len(calls) == 1
        assert calls[0].get("reference_image_path") is None, \
            "HeyGen must never pin the photo as the opening frame"
        refs = calls[0].get("input_references") or []
        assert len(refs) == 1
        assert refs[0]["type"] == "image_url"
        assert refs[0]["image_url"]["url"].startswith("data:image/png;base64,")
        # The face still reaches the render, and the prompt still names it as
        # the only authority on who the person is.
        assert "The person on camera is the person in the attached character reference" in (
            calls[0]["prompt"])

    def test_a_prompt_over_the_provider_ceiling_prevents_spend(self, api, monkeypatch):
        """
        Each provider has its own prompt ceiling and the two limits we can
        actually hit here -- prompt characters and encoded body bytes -- are
        ours, not the provider's, so neither appears in anything the founder is
        shown. When the assembled prompt still exceeds the ceiling after
        scaling, the refusal has to happen BEFORE the submit.

        Cost of getting this wrong is concrete: the founder pays for an attempt
        that cannot succeed, and the error they see names a parameter they have
        no way to set.
        """
        import video_providers as vp
        calls = _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Over Ceiling")

        # Squeeze the ceiling below what the prompt's fixed instructions alone
        # occupy, which is the only way the scaled variables cannot save it.
        original = vp._CAPABILITY_NOTES["minimax-h3"]["prompt_char_limit"]
        vp._CAPABILITY_NOTES["minimax-h3"]["prompt_char_limit"] = 200
        try:
            with pytest.raises(HTTPException) as err:
                _run(api.submit_project_generation(
                    project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        finally:
            vp._CAPABILITY_NOTES["minimax-h3"]["prompt_char_limit"] = original

        assert err.value.status_code == 409
        detail = str(err.value.detail)
        # Names the size, the ceiling, and reassures that nothing has been charged.
        assert "character prompt" in detail
        assert "nothing has been charged" in detail


# A genuinely playable clip for the download path to accept.
#
# This was a hand-assembled byte string -- an ftyp box, some zeros, an 8-byte
# moov -- on the grounds that "real ffmpeg is not needed to exercise the
# container check". That was true of the old check and is exactly why the real
# bug survived: a fixture with an 8-byte index cannot express the thing that
# broke, because the four bytes spelling "moov" are the start of a box whose body
# is thousands of bytes of sample tables on an actual render.
#
# The download path now asks ffprobe whether any video packets decode, so a file
# containing no video is correctly refused. That makes the fixture honest rather
# than merely convenient. See mp4_samples.
_DL_MP4 = mp4_samples.real_mp4()


class TestClipDownload:
    """
    The durable-save download: authentication, browser headers, retries,
    self-diagnosing errors. Regression cover for two distinct failures:

    - H3 Max, where the provider clip played fine in the browser but the
      server-side fetch failed, leaving the render with only its expiring
      temporary copy.
    - `unsigned_urls` not actually being presigned. The downloader sent
      browser-like headers only, so every completed render came back 401 at the
      moment its durable copy was being taken. That is the bug the auth
      assertions below exist to prevent returning.
    """

    def _fake_client(self, api, monkeypatch, behaviours, seen):
        class FakeStream:
            def __init__(self, behaviour):
                self.behaviour = behaviour

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            def raise_for_status(self):
                if isinstance(self.behaviour, Exception):
                    raise self.behaviour

            async def aiter_bytes(self):
                if isinstance(self.behaviour, Exception):
                    return
                yield self.behaviour if isinstance(self.behaviour, bytes) else _DL_MP4

        class FakeClient:
            def __init__(self, **kwargs):
                seen.update(kwargs)

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            def stream(self, method, url):
                seen["method"] = method
                seen["url"] = url
                seen["calls"] = seen.get("calls", 0) + 1
                return FakeStream(behaviours.pop(0))

        async def _no_sleep(delay):
            return None

        monkeypatch.setattr(api.httpx, "AsyncClient", FakeClient)
        monkeypatch.setattr(api.asyncio, "sleep", _no_sleep)

    def test_success_sends_browser_headers(self, api, monkeypatch):
        seen = {}
        self._fake_client(api, monkeypatch, [None], seen)
        path, err = _run(api._download_generation_video(
            "https://cdn.invalid/clip.mp4", "dl-ok"))
        assert err is None
        assert path.read_bytes() == _DL_MP4
        assert seen["method"] == "GET"
        assert "Mozilla" in seen["headers"]["User-Agent"]

    def test_an_openrouter_url_is_authenticated(self, api, monkeypatch):
        """
        The load-bearing one. `unsigned_urls` is a misleading name: those URLs
        are NOT presigned, so a download of one that points at the OpenRouter
        API without the bearer token is refused with 401 -- which is exactly
        how every completed render lost its durable copy.

        The key is set on the module rather than read from the environment:
        ai_service binds OPENROUTER_API_KEY at import time, and this module
        re-imports server but not ai_service, so an ambient key would make the
        assertion depend on which test module happened to import it first.
        """
        monkeypatch.setattr(api.ai_service, "OPENROUTER_API_KEY", "test-key-not-real")
        seen = {}
        self._fake_client(api, monkeypatch, [None], seen)
        path, err = _run(api._download_generation_video(
            "https://openrouter.ai/api/v1/videos/job-1/content?index=0", "dl-auth"))
        assert err is None
        assert path is not None
        assert "Authorization" in seen["headers"]
        assert "Mozilla" in seen["headers"]["User-Agent"]

    def test_a_third_party_url_is_never_given_the_key(self, api, monkeypatch):
        """
        The leak guard, at the point the header is actually built. OpenRouter's
        own docs show unsigned_urls carrying a third-party storage URL, and
        forwarding the account key there hands that host the key.
        """
        monkeypatch.setattr(api.ai_service, "OPENROUTER_API_KEY", "test-key-not-real")
        seen = {}
        self._fake_client(api, monkeypatch, [None], seen)
        path, err = _run(api._download_generation_video(
            "https://storage.example.com/clip.mp4", "dl-noauth"))
        assert err is None
        assert path is not None
        assert "Authorization" not in seen["headers"]

    def test_a_truncated_download_is_not_treated_as_success(self, api, monkeypatch):
        """
        A stream that ends early leaves a file with an ftyp and no moov. Saving
        that would report the render as durable while handing the founder
        something no player can open, so it must fail and be retried.
        """
        seen = {}
        truncated = b"\x00\x00\x00\x18ftypmp42" + (b"\x00" * 512)
        self._fake_client(api, monkeypatch, [truncated, truncated, truncated], seen)
        path, err = _run(api._download_generation_video(
            "https://cdn.invalid/clip.mp4", "dl-truncated"))
        assert path is None
        assert "truncated" in err
        assert seen["calls"] == 3

    def test_transient_failure_is_retried_then_succeeds(self, api, monkeypatch):
        import httpx
        seen = {}
        self._fake_client(api, monkeypatch, [
            httpx.ConnectError("blip"),
            httpx.ConnectError("blip"),
            None,
        ], seen)
        path, err = _run(api._download_generation_video(
            "https://cdn.invalid/clip.mp4", "dl-retry"))
        assert err is None
        assert path.read_bytes() == _DL_MP4
        assert seen["calls"] == 3

    def test_rejection_names_the_status_and_is_not_retried(self, api, monkeypatch):
        import httpx
        seen = {}
        req = httpx.Request("GET", "https://cdn.invalid/clip.mp4")
        status_err = httpx.HTTPStatusError(
            "forbidden", request=req, response=httpx.Response(403, request=req))
        self._fake_client(api, monkeypatch, [status_err], seen)
        path, err = _run(api._download_generation_video(
            "https://cdn.invalid/clip.mp4", "dl-403"))
        assert path is None
        assert "403" in err
        assert seen["calls"] == 1


class TestSpokenWordsBeforeTheRender:
    """
    Both counts and the one story, validated on the way to the provider.

    The hook line used to reach the render uncounted: partition_spoken_words
    sized the middle and passed the hook through untouched, so an opening line
    several times the length of the opening beat was sent whole and then cut
    mid-sentence by the prompt builder, with nothing telling the founder.
    """

    def _project_with_a_long_hook(self, api, name):
        project, _profile, _template = _ready_project(api, name)
        hook = (
            "Do you know what triggers your emotions and keeps them running the "
            "whole day? Most people never find out."
        )
        script = "Most evenings blur together. Yours ends with one sentence written down."
        strategy = {
            "hook_line": hook,
            "segments": [
                {"index": 0, "role": "hook", "seconds": 3, "goal": "name the problem",
                 "script": hook, "action": "hold the look"},
                {"index": 1, "role": "middle", "seconds": 12, "goal": "answer it",
                 "script": script, "action": "count"},
            ],
        }
        _run(api._execute(
            "UPDATE studio_projects SET hook_line = ?, script = ?, strategy = ?,"
            " strategy_version = 2, strategy_script_version = script_version WHERE id = ?",
            (hook, script, json.dumps(strategy), project["id"])))
        return project["id"], hook

    def test_an_overlong_hook_reaches_the_provider_cut_back_not_cut_off(self, api, monkeypatch):
        calls = _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project_id, hook = self._project_with_a_long_hook(api, "Spoken Words")
        result = _run(api.submit_project_generation(
            project_id=project_id, payload=StudioGenerationRequest(), user_id=ANON))
        assert len(calls) == 1
        prompt = calls[0]["prompt"]
        # The uncounted hook line never reaches the provider.
        assert hook not in prompt
        # Its opening sentence does, restored as the question it was ...
        assert "Do you know what triggers your emotions and keeps them?" in prompt
        # ... and what came off it is spoken by the middle rather than deleted.
        assert "Most people never find out." in prompt
        # The generation says what was rewritten, rather than leaving the
        # founder to hear the difference once the clip comes back.
        assert result["spoken_repair"]["rewritten"] is True
        after = result["spoken_repair"]["after"]
        assert after["hook"]["chars"] <= after["hook"]["ceiling"]
        assert after["story"]["problem_in_hook"] is True

    def test_a_plan_that_already_fits_is_sent_as_written(self, api, monkeypatch):
        calls = _mock_submit(api, monkeypatch)
        from models import StudioGenerationRequest
        project, _, _ = _ready_project(api, "Fit As Written")
        result = _run(api.submit_project_generation(
            project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        # Nothing is rewritten that does not have to be: the approved words are
        # the words, and no extra judgement is run over them on the way out.
        assert "spoken_repair" not in result
        assert FAKE_STRATEGY["hook_line"] in calls[0]["prompt"]
