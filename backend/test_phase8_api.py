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
    # Keep generated-file side effects inside the temp tree, not real storage.
    server.pipeline.VIDEOS_DIR = Path(tmpdir) / "videos"
    server.pipeline.ASSETS_DIR = Path(tmpdir) / "assets"
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    server.pipeline.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
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


class TestDeleteAppProfile:
    def test_delete_cascades_and_removes_profile(self, api):
        profile = _profile(api, "Cascade Target")
        _generation(api, profile, status="completed")
        from models import now_iso
        _run(api._execute(
            "INSERT INTO feedback_events (id, brand_profile_id, event, created_at, user_id)"
            " VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), profile["id"], "video_approved", now_iso(), ANON)))

        result = _run(api.delete_app_profile(profile["id"], user_id=ANON))
        assert result["deleted"] is True
        assert result["generations_removed"] == 1

        with pytest.raises(HTTPException) as err:
            _run(api.get_app_profile(profile["id"], user_id=ANON))
        assert err.value.status_code == 404

        for table in ("content_angles", "studio_projects", "generations",
                      "assets", "overlay_compositions", "performance_entries",
                      "feedback_events", "asset_events"):
            rows = _run(api._fetch_all(
                f"SELECT id FROM {table} WHERE brand_profile_id = ?",
                (profile["id"],)))
            assert rows == [], table

    def test_delete_is_404_for_unknown_profile(self, api):
        with pytest.raises(HTTPException) as err:
            _run(api.delete_app_profile(str(uuid.uuid4()), user_id=ANON))
        assert err.value.status_code == 404

    def test_delete_refused_while_generation_in_flight(self, api):
        profile = _profile(api, "In Flight")
        _generation(api, profile, status="generating")
        with pytest.raises(HTTPException) as err:
            _run(api.delete_app_profile(profile["id"], user_id=ANON))
        assert err.value.status_code == 409


class TestApproveAppProfile:
    def test_approve_commits_status_with_no_pending_proposal(self, api):
        # A freshly researched profile carries no pending_research: the status
        # flip must commit on its own, otherwise the approval looks successful
        # while the row stays a draft — and data appears to vanish on relogin.
        from models import BrandProfileCreateRequest, ApproveAppProfileRequest
        profile = _run(api.create_brand(
            payload=BrandProfileCreateRequest(brand_name="No Pending"), user_id=ANON))
        assert profile["status"] == "draft"
        approved = _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        assert approved["status"] == "approved"
        assert approved["approved_at"] is not None
        reread = _run(api.get_app_profile(profile["id"], user_id=ANON))
        assert reread["status"] == "approved"

    def test_approve_without_applying_pending_still_approves(self, api):
        from models import ApproveAppProfileRequest
        profile = _profile(api, "Skip Pending")
        approved = _run(api.approve_app_profile(
            profile_id=profile["id"],
            payload=ApproveAppProfileRequest(apply_pending=False),
            user_id=ANON))
        assert approved["status"] == "approved"

    def test_approve_unknown_profile_is_404(self, api):
        from models import ApproveAppProfileRequest
        with pytest.raises(HTTPException) as err:
            _run(api.approve_app_profile(
                profile_id=str(uuid.uuid4()),
                payload=ApproveAppProfileRequest(), user_id=ANON))
        assert err.value.status_code == 404


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
        'cta_unclear' is valid for an edited script but not for a rejected
        generation. Allowing it would put codes in the table that analytics
        cannot group meaningfully.
        """
        from models import FeedbackRequest
        with pytest.raises(HTTPException) as err:
            _run(api.record_feedback(
                FeedbackRequest(event="generation_rejected", reason="cta_unclear"), ANON))
        assert err.value.status_code == 400

    def test_event_with_neither_signal_nor_reason_is_rejected(self, api):
        """
        Feedback with no half at all says nothing. A reason alone is still
        required to be valid, but it may now be omitted when a signal is
        present, so this is the only bare case that must fail.
        """
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


class TestRecordSignal:
    """
    Signals are the automatic half of the feedback loop: factual triggers the
    software observes, recorded without asking the founder anything.
    """

    def test_a_signal_alone_is_enough(self, api):
        from models import FeedbackRequest
        created = _run(api.record_feedback(
            FeedbackRequest(event="video_downloaded", signal="downloaded"), ANON))
        assert created["signal"] == "downloaded"
        assert created["reason"] == ""

    def test_a_signal_and_a_reason_can_travel_together(self, api):
        from models import FeedbackRequest
        created = _run(api.record_feedback(
            FeedbackRequest(event="marked_successful", reason="good_performance"), ANON))
        assert created["reason"] == "good_performance"
        assert created["signal"] == ""

    def test_unknown_signal_is_rejected(self, api):
        from models import FeedbackRequest
        with pytest.raises(HTTPException) as err:
            _run(api.record_feedback(
                FeedbackRequest(event="video_downloaded", signal="teleported"), ANON))
        assert err.value.status_code == 400

    def test_signal_must_belong_to_the_event(self, api):
        """
        The point of keeping signal and event separate is that neither is
        inferred from the other. A mismatched pair means one of them is wrong,
        so it is refused rather than stored.
        """
        from models import FeedbackRequest
        with pytest.raises(HTTPException) as err:
            _run(api.record_feedback(
                FeedbackRequest(event="video_approved", signal="regenerated"), ANON))
        assert err.value.status_code == 400

    def test_every_signal_maps_to_a_known_event(self, api):
        import feedback as fb
        for signal, event in fb.SIGNALS.items():
            assert event in fb.EVENTS, signal
            assert fb.signal_event(signal) == event

    def test_signals_and_reasons_are_never_inferred_from_each_other(self, api):
        """
        A regenerate says nothing about *why*. Storing a guessed reason against
        a trigger would corrupt the "common regeneration reasons" aggregate
        with counterfactuals, so the reason column stays empty.
        """
        from models import FeedbackRequest
        # A dedicated user, so this test's summary is not diluted by the rows
        # every other test in this file leaves behind.
        solo = "signal-solo-user"
        created = _run(api.record_feedback(
            FeedbackRequest(event="video_regenerated", signal="regenerated"), solo))
        assert created["reason"] == ""
        summary = _run(api.list_feedback(user_id=solo))["summary"]
        assert summary["top_signals"] == [
            {"signal": "regenerated", "count": 1}
        ]
        assert summary["top_reasons"] == []

    def test_summary_separates_triggers_from_explanations(self, api):
        """
        Frequent-but-unexplained rework must be readable as such, not mistaken
        for an absence of problems.
        """
        from models import FeedbackRequest
        solo = "signal-summary-user"
        for _ in range(3):
            _run(api.record_feedback(
                FeedbackRequest(event="video_regenerated", signal="regenerated"), solo))
        _run(api.record_feedback(
            FeedbackRequest(event="marked_unsuccessful", reason="poor_performance"), solo))
        summary = _run(api.list_feedback(user_id=solo))["summary"]
        assert summary["total"] == 4
        assert summary["explained"] == 1
        assert summary["top_signals"][0]["count"] == 3

    def test_catalog_publishes_the_heavy_edit_threshold(self, api):
        """
        The heavy/light boundary is arbitrary, so it is published rather than
        hidden: both the backend and the frontend classifier must agree, and a
        reader can check what the number actually is.
        """
        import feedback as fb
        catalog = _run(api.feedback_catalog())
        assert catalog["heavy_edit"]["ratio"] == fb.HEAVY_EDIT_RATIO
        assert catalog["heavy_edit"]["min_chars"] == fb.HEAVY_EDIT_MIN_CHARS
        assert {s["key"] for s in catalog["signals"]} == set(fb.SIGNALS)


class TestClassifyScriptEdit:
    def test_no_change_is_not_an_edit(self):
        import feedback as fb
        assert fb.classify_script_edit("same text", "same text") == ""

    def test_a_large_rewrite_is_heavy(self):
        import feedback as fb
        original = "Open the app and tap the button to start your session today."
        rewritten = "Try it free for three days, then decide."
        assert fb.classify_script_edit(original, rewritten) == "script_edited_heavy"

    def test_a_one_character_tweak_is_light(self):
        import feedback as fb
        original = "Open the app and tap the button to start your session today."
        assert fb.classify_script_edit(original, original + "!") == "script_edited_light"

    def test_a_growing_script_counts_as_heavy_once_past_the_floor(self):
        """
        Length is measured on the longer text, so padding a short script is
        measured on what it became rather than on the tiny original.
        """
        import feedback as fb
        short = "Try it."
        padded = short + (" Very easy to use and very quick to set up." * 3)
        assert fb.classify_script_edit(short, padded) == "script_edited_heavy"


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


class TestModelRequestLedger:
    USER = "ops-model-user"

    def test_success_and_failure_are_recorded(self, api):
        async def succeed():
            return {"usage": {"cost": 0.03}}

        async def fail():
            raise RuntimeError("provider unavailable")

        result = _run(api._log_model_call(
            "ops-text-check", "text", "text-model", succeed, self.USER,
            brand_profile_id="profile-1",
        ))
        assert result["usage"]["cost"] == 0.03
        with pytest.raises(RuntimeError):
            _run(api._log_model_call(
                "ops-vision-check", "vision", "vision-model", fail, self.USER,
                brand_profile_id="profile-1",
            ))
        rows = _run(api._fetch_all(
            "SELECT operation, status, cost_usd, error, latency_ms FROM model_requests "
            "WHERE user_id = ? ORDER BY created_at",
            (self.USER,),
        ))
        assert [(r["operation"], r["status"]) for r in rows] == [
            ("ops-text-check", "completed"),
            ("ops-vision-check", "failed"),
        ]
        assert rows[0]["cost_usd"] == pytest.approx(0.03)
        assert "unavailable" in rows[1]["error"]
        assert rows[0]["latency_ms"] >= 0

    def test_asset_events_and_research_runs_are_persisted_for_their_owner(self, api):
        """
        Used to assert this through the Operations page. The page is gone, but
        what it was reading is a real invariant: these ledgers exist, they are
        written, and they are scoped to their owner. So they are asserted where
        they actually live.
        """
        _run(api._record_asset_event(
            "upload_rejected", "Uploaded file is empty.", self.USER,
            brand_profile_id="profile-1", asset_kind="audio", filename="empty.mp3",
        ))
        run_id = str(uuid.uuid4())
        _run(api._execute(
            """INSERT INTO research_runs
               (id, kind, query, status, created_at, user_id)
               VALUES (?, 'keyword', 'journaling app', 'failed', ?, ?)""",
            (run_id, "2026-01-01T00:00:00+00:00", self.USER),
        ))

        events = _run(api._fetch_all(
            "SELECT kind, reason FROM asset_events WHERE user_id = ?", (self.USER,)))
        assert any(e["kind"] == "upload_rejected" for e in events)

        runs = _run(api._fetch_all(
            "SELECT id, status FROM research_runs WHERE user_id = ?", (self.USER,)))
        assert [r["id"] for r in runs] == [run_id]
        assert runs[0]["status"] == "failed"

        # And they are scoped: another user sees neither.
        assert _run(api._fetch_all(
            "SELECT id FROM asset_events WHERE user_id = ?", (OTHER_USER,))) == []
        assert _run(api._fetch_all(
            "SELECT id FROM research_runs WHERE user_id = ?", (OTHER_USER,))) == []

    def test_model_request_ledger_summarises_by_modality(self, api):
        """
        analytics.model_request_summary is still used by the analytics report,
        so the summary it produces keeps being worth asserting.
        """
        import analytics

        async def succeed():
            return {"usage": {"cost": 0.02}}

        _run(api._log_model_call(
            "summary-text-check", "text", "text-model", succeed, self.USER))
        rows = _run(api._fetch_all(
            "SELECT operation, modality, status, cost_usd FROM model_requests WHERE user_id = ?",
            (self.USER,)))
        summary = analytics.model_request_summary(rows)
        assert summary["total"] >= 1
        assert summary["by_modality"]["text"]["completed"] >= 1

    def test_completed_generation_storage_failure_is_recorded_and_retryable(
        self, api, monkeypatch
    ):
        """
        A storage failure has to be recoverable, not just reported. With the
        Operations page gone there is no longer a view that surfaces it, so the
        record itself is what must carry it.
        """
        profile = _profile(api, "Ops Storage")
        gen = _generation(api, profile, "completed")
        local_path = api.pipeline.VIDEOS_DIR / f"{gen['id']}.mp4"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"fake-video")
        _run(api._execute(
            "UPDATE generations SET r2_url = '', storage_error = ? WHERE id = ?",
            ("R2 upload failed", gen["id"]),
        ))

        # The failure is readable from the generation record itself, and it is
        # scoped to its owner.
        stored = _run(api.get_generation(gen["id"], ANON))
        assert stored["storage_error"] == "R2 upload failed"
        with pytest.raises(HTTPException):
            _run(api.get_generation(gen["id"], OTHER_USER))

        monkeypatch.setattr(api.storage_service, "is_configured", lambda: True)
        monkeypatch.setattr(
            api.storage_service, "upload_video",
            lambda user_id, job_id, path: "https://example.invalid/video.mp4",
        )
        retried = _run(api.retry_generation_storage(gen["id"], ANON))
        assert retried["r2_url"] == "https://example.invalid/video.mp4"
        assert retried["storage_error"] is None
        assert _run(api.get_generation(gen["id"], ANON))["storage_error"] is None

    def test_storage_retry_reports_a_missing_local_copy(self, api):
        profile = _profile(api, "Ops Missing Copy")
        gen = _generation(api, profile, "completed")
        local_path = api.pipeline.VIDEOS_DIR / f"{gen['id']}.mp4"
        if local_path.exists():
            local_path.unlink()
        with pytest.raises(HTTPException) as err:
            _run(api.retry_generation_storage(gen["id"], ANON))
        assert err.value.status_code == 409

    def test_storage_retry_requires_configured_remote_storage(self, api, monkeypatch):
        profile = _profile(api, "Ops Unconfigured Storage")
        gen = _generation(api, profile, "completed")
        local_path = api.pipeline.VIDEOS_DIR / f"{gen['id']}.mp4"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"fake-video")
        monkeypatch.setattr(api.storage_service, "is_configured", lambda: False)
        with pytest.raises(HTTPException) as err:
            _run(api.retry_generation_storage(gen["id"], ANON))
        assert err.value.status_code == 409


# The Dashboard page and GET /api/dashboard are gone. Its three tests went with
# the endpoint, and nothing they covered became untested:
#
#   profiles / profiles_awaiting_approval   GET /api/app-profiles; the same
#                                           approved-vs-draft split is asserted
#                                           in test_studio_api's picker tests
#   totals (videos_created, spend, rate)     GET /api/analytics
#   pending_template_drafts                  GET /api/templates by review_status
#   recent_failures                          GET /api/generations, which History
#                                           renders with a Failed badge and Retry


# The Settings page and GET /api/settings are gone. The three honesty notes it
# carried are each stated somewhere the user still is, so none of them went dark
# with the page:
#
#   never publishes          frontend/src/pages/CreateVideo.jsx (studio footer)
#   TikTok figures are by hand   frontend/src/pages/Analytics.jsx
#   templates are not proven     frontend/src/pages/CreateVideo.jsx
#
# Integration status went with it. It was a read-only self-serve report, so
# nothing is stranded and no behaviour depended on the endpoint.


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

    def test_legacy_creation_routes_are_unregistered(self, api):
        """
        Exact-match creation is disabled at the router boundary. Research
        discovery, analysis, bookmarks, and history remain; creation paths do
        not, even though their implementation helpers may still exist for old
        records and shared media code.
        """
        paths = {getattr(r, "path", "") for r in api.api_router.routes}
        for disabled in api.DISABLED_LEGACY_CREATION_ROUTES:
            assert f"/api{disabled}" not in paths, disabled
        app_paths = {getattr(r, "path", "") for r in api.app.routes}
        for disabled in api.DISABLED_LEGACY_CREATION_ROUTES:
            assert f"/api{disabled}" not in app_paths, disabled

    def test_research_routes_remain_registered(self, api):
        paths = {getattr(r, "path", "") for r in api.api_router.routes}
        for retained in (
            "/api/niches",
            "/api/videos/ingest",
            "/api/videos/{video_id}/analyze-hook",
            "/api/videos/{video_id}/analysis",
            "/api/bookmarks",
            "/api/history",
            "/api/research/scan",
        ):
            assert retained in paths, retained

    def test_no_credential_capture_endpoints(self, api):
        paths = " ".join(getattr(r, "path", "") for r in api.app.routes)
        for forbidden in ("login", "cookie", "session-token", "credentials"):
            assert forbidden not in paths.lower()

    # The "publishing is manual" guarantee used to be asserted as a string in the
    # Operations payload. It is no longer asserted that way, because a copy-text
    # check on a sentence is worth nothing next to the three structural tests
    # above it, which prove there is no code path that can post a video at all.
    # The user-facing statement now lives on the Assets and Review screens.
