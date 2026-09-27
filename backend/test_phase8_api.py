"""
DB-backed tests for feedback, analytics, research, and operations.

The properties worth pinning: feedback reasons must belong to their event,
research drafts must be unpublished and must never carry a source reference,
manual performance must never be reported as verified, and research must fail
loudly rather than silently returning nothing when Apify is unconfigured.
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
    tmpdir = tempfile.mkdtemp(prefix="tiktok-p8-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    os.environ["APIFY_API_TOKEN"] = ""  # research must degrade loudly

    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(server.init_db())
    yield server
    sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


def _profile(api, name):
    from models import BrandProfileCreateRequest, ApproveAppProfileRequest
    p = _run(api.create_brand(payload=BrandProfileCreateRequest(brand_name=name), user_id=ANON))
    _run(api.approve_app_profile(
        profile_id=p["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    return p


def _generation(api, profile, status="completed", cost=0.25, **overrides):
    from models import CreateStudioProjectRequest, now_iso
    template = _run(api.list_templates(user_id=ANON))["templates"][0]
    project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"], template_id=template["id"],
        objective=overrides.pop("objective", "demonstrate_feature")), user_id=ANON))
    gen_id = str(uuid.uuid4())
    now = now_iso()
    _run(api._execute(
        """INSERT INTO generations
           (id, studio_project_id, brand_profile_id, template_id, template_version,
            model, duration, status, cost_usd, cost_source, attempt,
            parent_generation_id, created_at, updated_at, started_at, completed_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, 20, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (gen_id, project["id"], profile["id"], template["id"], template["version"],
         overrides.pop("model", "minimax-h3"), status, cost,
         "usage.cost" if cost is not None else "unavailable",
         overrides.pop("attempt", 1), overrides.pop("parent_generation_id", None),
         now, now, overrides.pop("started_at", now), overrides.pop("completed_at", now),
         ANON)))
    return _run(api.get_generation(gen_id, ANON))


class TestFeedbackCatalog:
    def test_catalog_lists_events_with_reasons(self, api):
        catalog = _run(api.feedback_catalog())
        assert len(catalog["events"]) == 8
        for event in catalog["events"]:
            assert event["reasons"], event["key"]

    def test_every_reason_has_a_label(self, api):
        import feedback as fb
        for reasons in fb.REASONS.values():
            for reason in reasons:
                assert reason in fb.REASON_LABELS, reason


class TestRecordFeedback:
    def test_records_a_valid_pair(self, api):
        from models import FeedbackRequest
        profile = _profile(api, "FB OK")
        created = _run(api.record_feedback(
            FeedbackRequest(event="video_regenerated", reason="pacing_too_slow",
                           brand_profile_id=profile["id"]), ANON))
        assert created["event"] == "video_regenerated"
        assert created["reason"] == "pacing_too_slow"

    def test_unknown_event_is_rejected(self, api):
        from models import FeedbackRequest
        with pytest.raises(HTTPException) as err:
            _run(api.record_feedback(FeedbackRequest(event="nonsense", reason="x"), ANON))
        assert err.value.status_code == 400

    def test_reason_must_belong_to_the_event(self, api):
        """
        'hook_too_weak' is valid for a rejected template but not for a failed
        generation. Allowing it would put codes in the table that analytics
        cannot group meaningfully.
        """
        from models import FeedbackRequest
        with pytest.raises(HTTPException) as err:
            _run(api.record_feedback(
                FeedbackRequest(event="generation_failed", reason="hook_too_weak"), ANON))
        assert err.value.status_code == 400

    def test_empty_reason_is_rejected(self, api):
        from models import FeedbackRequest
        with pytest.raises(HTTPException):
            _run(api.record_feedback(FeedbackRequest(event="video_approved"), ANON))

    def test_detail_is_stored_but_not_aggregated(self, api):
        from models import FeedbackRequest
        _run(api.record_feedback(
            FeedbackRequest(event="template_rejected", reason="hook_too_weak",
                           detail="felt flat"), ANON))
        listed = _run(api.list_feedback(user_id=ANON))
        assert any(f.get("detail") == "felt flat" for f in listed["feedback"])
        # Only fixed reasons are counted in the summary.
        assert all("reason" in r for r in listed["summary"]["top_reasons"])

    def test_listing_is_scoped_to_user(self, api):
        from models import FeedbackRequest
        _run(api.record_feedback(
            FeedbackRequest(event="video_approved", reason="worked_well"), ANON))
        assert _run(api.list_feedback(user_id=OTHER_USER))["feedback"] == []

    def test_summary_counts_events(self, api):
        from models import FeedbackRequest
        _run(api.record_feedback(
            FeedbackRequest(event="script_edited", reason="cta_unclear"), ANON))
        _run(api.record_feedback(
            FeedbackRequest(event="script_edited", reason="cta_unclear"), ANON))
        summary = _run(api.list_feedback(user_id=ANON))["summary"]
        assert summary["by_event"]["script_edited"] >= 2


class TestAnalyticsReport:
    def test_empty_report_is_shaped_correctly(self, api):
        report = _run(api.analytics_report(user_id=OTHER_USER))
        assert report["totals"]["videos_created"] == 0
        assert report["totals"]["success_rate"] is None
        assert report["performance"]["verified"] is False
        assert report["scope"] == "internal"
        assert report["publishing"] == "manual"

    def test_report_totals(self, api):
        profile = _profile(api, "An One")
        _generation(api, profile, "completed", 0.5, id_note=None) if False else None
        _generation(api, profile, "completed", 0.5)
        _generation(api, profile, "failed", 0.25)
        report = _run(api.analytics_report(brand_profile_id=profile["id"], user_id=ANON))
        assert report["totals"]["videos_created"] == 2
        assert report["totals"]["completed"] == 1
        assert report["totals"]["failed"] == 1
        assert report["totals"]["total_usd"] == pytest.approx(0.75)

    def test_report_breaks_down_by_model_and_app(self, api):
        profile = _profile(api, "An Two")
        _generation(api, profile, model="minimax-h3")
        _generation(api, profile, model="seedance-2.5")
        report = _run(api.analytics_report(brand_profile_id=profile["id"], user_id=ANON))
        keys = {e["key"] for e in report["by_model"]}
        assert keys == {"minimax-h3", "seedance-2.5"}
        assert report["by_app"][0]["label"] == "An Two"

    def test_report_lists_templates_with_outcomes(self, api):
        profile = _profile(api, "An Three")
        _generation(api, profile)
        report = _run(api.analytics_report(brand_profile_id=profile["id"], user_id=ANON))
        assert report["by_template"][0]["name"]
        assert report["by_template"][0]["used"] == 1

    def test_report_never_marks_performance_verified(self, api):
        from models import PerformanceEntryRequest
        profile = _profile(api, "An Four")
        gen = _generation(api, profile)
        _run(api.record_performance(gen["id"], PerformanceEntryRequest(views=500), ANON))
        report = _run(api.analytics_report(brand_profile_id=profile["id"], user_id=ANON))
        assert report["performance"]["verified"] is False
        assert report["performance"]["source"] == "manual"
        assert report["performance"]["views"] == 500

    def test_unpriced_runs_are_surfaced(self, api):
        profile = _profile(api, "An Five")
        _generation(api, profile, cost=None)
        report = _run(api.analytics_report(brand_profile_id=profile["id"], user_id=ANON))
        assert report["totals"]["unpriced_runs"] == 1
        assert report["totals"]["complete"] is False

    def test_report_counts_rework(self, api):
        profile = _profile(api, "An Six")
        _generation(api, profile)
        _generation(api, profile, attempt=2)
        report = _run(api.analytics_report(brand_profile_id=profile["id"], user_id=ANON))
        assert report["rework"]["regenerated"] == 1


class TestOperations:
    def test_reports_job_counts(self, api):
        profile = _profile(api, "Ops One")
        _generation(api, profile, "completed")
        _generation(api, profile, "failed")
        ops = _run(api.operations_overview(user_id=ANON))
        assert ops["jobs"]["total"] >= 2
        assert ops["jobs"]["failed"] >= 1

    def test_failures_carry_retry_classification(self, api):
        profile = _profile(api, "Ops Two")
        gen = _generation(api, profile, "failed")
        _run(api._execute(
            "UPDATE generations SET error = ?, retryable = 1 WHERE id = ?",
            ("HTTP 503 overloaded", gen["id"])))
        ops = _run(api.operations_overview(user_id=ANON))
        failing = [f for f in ops["failures"] if f["id"] == gen["id"]]
        assert failing
        assert failing[0]["retryable"] is True
        assert "503" in failing[0]["error"]

    def test_reports_provider_availability(self, api):
        ops = _run(api.operations_overview(user_id=ANON))
        keys = {p["key"] for p in ops["providers"]}
        assert "seedance-2.5" in keys and "minimax-h3" in keys
        assert any(p["is_default"] for p in ops["providers"])
        assert all("studio_eligible" in p for p in ops["providers"])

    def test_reports_integration_state(self, api):
        ops = _run(api.operations_overview(user_id=ANON))
        config = ops["config"]
        assert config["ai_configured"] is True
        # Unconfigured integrations are reported as False, not hidden.
        assert config["apify_configured"] is False
        assert config["r2_configured"] is False

    def test_states_that_publishing_is_manual(self, api):
        ops = _run(api.operations_overview(user_id=ANON))
        assert "never posts" in ops["manual_publishing"].lower()

    def test_is_scoped_to_user(self, api):
        profile = _profile(api, "Ops Three")
        _generation(api, profile)
        assert _run(api.operations_overview(user_id=OTHER_USER))["jobs"]["total"] == 0


class TestDashboard:
    def test_lists_profiles_and_pending_drafts(self, api):
        _profile(api, "Dash One")
        tpl_id = str(uuid.uuid4())
        _run(api._execute(
            """INSERT INTO hook_templates (id, name, category, opening_structure,
               origin, review_status, archived, version, created_at, updated_at, user_id)
               VALUES (?, 'Research Draft', 'other', 'A structure', 'research_draft',
               'draft', 0, 1, '', '', ?)""", (tpl_id, ANON)))
        board = _run(api.dashboard(user_id=ANON))
        assert any(p["brand_name"] == "Dash One" for p in board["profiles"])
        assert any(d["id"] == tpl_id for d in board["pending_template_drafts"])

    def test_empty_dashboard(self, api):
        board = _run(api.dashboard(user_id=OTHER_USER))
        assert board["totals"]["videos_created"] == 0
        assert board["profiles"] == []

    def test_surfaces_unapproved_profiles(self, api):
        from models import BrandProfileCreateRequest
        _run(api.create_brand(payload=BrandProfileCreateRequest(brand_name="Draft App"), user_id=ANON))
        board = _run(api.dashboard(user_id=ANON))
        assert any(p["brand_name"] == "Draft App" for p in board["profiles_awaiting_approval"])


class TestSettings:
    def test_reports_provider_and_integration_state(self, api):
        result = _run(api.settings_overview(user_id=ANON))
        assert result["providers"]["default"]
        assert result["providers"]["thirty_second_request"]["primary_seconds"] > 0
        assert result["integrations"]["openrouter"] is True

    def test_states_the_honest_notes(self, api):
        result = _run(api.settings_overview(user_id=ANON))
        joined = " ".join(result["notes"]).lower()
        assert "published by hand" in joined or "publish" in joined
        assert "never verified" in joined
        assert "not proven performers" in joined
        assert result["publishing"] == "manual"


class TestResearch:
    def test_scan_requires_a_target(self, api):
        from models import ResearchScanRequest
        with pytest.raises(HTTPException) as err:
            _run(api.run_trend_research(ResearchScanRequest(kind="keyword"), ANON))
        assert err.value.status_code == 400

    def test_invalid_kind_is_rejected(self, api):
        from models import ResearchScanRequest
        with pytest.raises(HTTPException) as err:
            _run(api.run_trend_research(
                ResearchScanRequest(kind="telepathy", query="x"), ANON))
        assert err.value.status_code == 400

    def test_scan_fails_loudly_without_apify(self, api):
        """
        No trend data configured must be an explicit 503, not a silent empty
        result that reads like "we found nothing interesting".
        """
        from models import ResearchScanRequest
        with pytest.raises(HTTPException) as err:
            _run(api.run_trend_research(
                ResearchScanRequest(kind="keyword", query="journaling app"), ANON))
        assert err.value.status_code == 503
        assert "APIFY_API_TOKEN" in str(err.value.detail)

    def test_failed_run_is_recorded_for_operations(self, api):
        runs = _run(api.list_research_runs(user_id=ANON))
        assert runs["runs"]
        assert any(r["status"] == "failed" for r in runs["runs"])

    def test_run_detail_is_scoped(self, api):
        runs = _run(api.list_research_runs(user_id=ANON))
        run_id = runs["runs"][0]["id"]
        with pytest.raises(HTTPException) as err:
            _run(api.get_research_run(run_id, OTHER_USER))
        assert err.value.status_code == 404


class TestResearchDraftPublication:
    def test_drafts_from_research_are_unusable_until_published(self, api):
        """
        A research draft must never be usable in a video, so nothing observed in
        public data can reach generation unreviewed.
        """
        tpl_id = str(uuid.uuid4())
        _run(api._execute(
            """INSERT INTO hook_templates (id, name, category, opening_structure,
               continuation_structure, origin, review_status, archived, version,
               created_at, updated_at, user_id)
               VALUES (?, 'Observed Pattern', 'other', 'Opens with a question',
               'Then the answer', 'research_draft', 'draft', 0, 1, '', '', ?)""",
            (tpl_id, ANON)))
        row = _run(api.get_template(tpl_id, ANON))
        assert row["is_usable"] is False
        assert row["review_status"] == "draft"

    def test_publishing_makes_it_usable(self, api):
        tpl_id = str(uuid.uuid4())
        _run(api._execute(
            """INSERT INTO hook_templates (id, name, category, opening_structure,
               continuation_structure, origin, review_status, archived, version,
               created_at, updated_at, user_id)
               VALUES (?, 'Observed Pattern 2', 'other', 'Opens with a question',
               'Then the answer', 'research_draft', 'draft', 0, 1, '', '', ?)""",
            (tpl_id, ANON)))
        published = _run(api.publish_template(tpl_id, ANON))
        assert published["is_usable"] is True
        assert published["review_status"] == "approved"

    def test_unpublished_drafts_are_excluded_from_recommendations(self, api):
        from models import CreateStudioProjectRequest, BrandProfileCreateRequest, ApproveAppProfileRequest
        profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name="Draft Exclusion"), user_id=ANON))
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        tpl_id = str(uuid.uuid4())
        _run(api._execute(
            """INSERT INTO hook_templates (id, name, category, opening_structure,
               origin, review_status, archived, version, created_at, updated_at, user_id)
               VALUES (?, 'Hidden Draft', 'other', 'A structure', 'research_draft',
               'draft', 0, 1, '', '', ?)""", (tpl_id, ANON)))
        recs = _run(api.recommend_templates(profile_id=profile["id"], user_id=ANON))
        assert tpl_id not in [r["template"]["id"] for r in recs["recommendations"]]
        del CreateStudioProjectRequest

    def test_creating_a_project_with_a_draft_template_is_refused(self, api):
        from models import CreateStudioProjectRequest, BrandProfileCreateRequest, ApproveAppProfileRequest
        profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name="Draft Project"), user_id=ANON))
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        tpl_id = str(uuid.uuid4())
        _run(api._execute(
            """INSERT INTO hook_templates (id, name, category, opening_structure,
               origin, review_status, archived, version, created_at, updated_at, user_id)
               VALUES (?, 'Hidden Draft 2', 'other', 'A structure', 'research_draft',
               'draft', 0, 1, '', '', ?)""", (tpl_id, ANON)))
        with pytest.raises(HTTPException) as err:
            _run(api.create_studio_project(payload=CreateStudioProjectRequest(
                brand_profile_id=profile["id"], template_id=tpl_id), user_id=ANON))
        assert err.value.status_code == 409


class TestNoPlatformAutomation:
    """
    The exclusions are structural: there is no code path in this app that
    posts, schedules, or authenticates against a social platform.
    """

    def test_no_video_publishing_endpoints_exist(self, api):
        """
        Note: POST /templates/{id}/publish DOES exist and is legitimate -- it
        publishes a template into the internal library, not a video to a
        platform. What must not exist is anything that sends a video out.
        """
        paths = {getattr(r, "path", "") for r in api.app.routes}
        for forbidden in ("/publish-video", "/post-video", "/tiktok/post",
                          "/share-to", "/engagement", "/schedule",
                          "/upload-to", "/queue-post"):
            assert not any(forbidden in p for p in paths), forbidden

    def test_no_generation_endpoint_publishes(self, api):
        """Nothing under /generations may hand a video to a platform."""
        for r in api.app.routes:
            path = getattr(r, "path", "")
            if path.startswith("/api/generations"):
                assert not any(
                    w in path for w in ("publish", "post", "share", "schedule")
                ), path

    def test_no_credential_capture_endpoints(self, api):
        paths = " ".join(getattr(r, "path", "") for r in api.app.routes)
        for forbidden in ("login", "cookie", "session-token", "credentials"):
            assert forbidden not in paths.lower()

    def test_operations_states_publishing_is_manual(self, api):
        ops = _run(api.operations_overview(user_id=ANON))
        text = ops["manual_publishing"].lower()
        assert "never posts" in text
        assert "by hand" in text
