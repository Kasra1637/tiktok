"""
DB-backed tests for variations, generation history, and manual performance.

The rules being pinned here: a variation produces a DRAFT (never a paid
generation on its own), lineage is recorded on both sides, cheap axes stay
free, and manually entered performance is always labelled unverified.
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
    tmpdir = tempfile.mkdtemp(prefix="tiktok-p7-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    os.environ.pop("VIDEO_MODEL_DEFAULT", None)

    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    server.pipeline.VIDEOS_DIR = Path(tmpdir) / "videos"
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.run(server.init_db())
    yield server
    sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


def _profile(api, name):
    from models import BrandProfileCreateRequest, ApproveAppProfileRequest
    p = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name,
        brand_description="A focus timer for people who stall on starting.",
        core_features=["Task timer", "Reminders"],
        usage_moments=["Starting a task they have been avoiding"],
        outcome_statements=[{
            "outcome": "Starting without stalling on setup",
            "who_feels_it": "people who stall on starting",
            "from_feature": "Task timer",
            "how_it_helps": "The timer starts in one tap so there is nothing to set up",
        }],
    ), user_id=ANON))
    _run(api.approve_app_profile(
        profile_id=p["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    return _run(api.get_app_profile(p["id"], ANON))


def _generation(api, profile, name, status="completed", with_plan=True):
    """A project plus a generation row, so variations have a parent."""
    from models import CreateStudioProjectRequest, now_iso
    template = _run(api.list_templates(user_id=ANON))["templates"][0]
    project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"], template_id=template["id"]), user_id=ANON))
    if with_plan:
        # `demo_brief` replaced `feature_emphasis`: the founder's note about what
        # to record for their own demo. `cta` is still written because the column
        # survives in the schema — a stale value that the copy paths must drop,
        # which is what the assertions below check.
        _run(api._execute(
            """UPDATE studio_projects SET hook_line = ?, script = ?, cta = ?,
               visual_direction = ?, demo_brief = ?, audience = ?, tone = ?,
               script_version = 1, status = 'ready_for_generation' WHERE id = ?""",
            ("Old hook", "Old spoken script.", "Old CTA", "Close on hands.",
             "Record yourself tapping the timer once.", "Busy parents", "calm",
             project["id"])))
    gen_id = str(uuid.uuid4())
    now = now_iso()
    _run(api._execute(
"""INSERT INTO generations
           (id, studio_project_id, brand_profile_id, template_id, template_version,
             script_version, model, duration, status, video_url,
             created_at, updated_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, 'minimax-h3', 20, ?, ?, ?, ?, ?)""",
        (gen_id, project["id"], profile["id"], template["id"], template["version"],
         1, status, f"/api/media/videos/{gen_id}.mp4", now, now, ANON)))
    return _run(api.get_generation(gen_id, ANON)), _run(
        api.get_studio_project(project["id"], ANON)), template


class TestVariationCatalogueEndpoint:
    def test_lists_the_eight_axes(self, api):
        result = _run(api.list_variation_kinds())
        assert len(result["variations"]) == 8
        assert {v["key"] for v in result["variations"]} >= {"hook_line", "duration", "template"}

    def test_the_retired_cta_axis_is_not_advertised(self, api):
        """
        The UI builds its variation menu from this endpoint, so an axis that is
        gone from the catalogue but still listed here would offer the founder a
        control that cannot change the video.
        """
        keys = {v["key"] for v in _run(api.list_variation_kinds())["variations"]}
        assert "cta" not in keys


class TestCreateVariation:
    def test_variation_produces_a_draft_not_a_generation(self, api):
        """
        The core safety property: a variation must never spend money on its
        own. It returns a draft project and nothing is submitted.
        """
        from models import CreateVariationRequest
        profile = _profile(api, "Var Draft")
        gen, _, _ = _generation(api, profile, "Var Draft")
        before = len(_run(api.list_generations(user_id=ANON))["generations"])
        result = _run(api.create_variation(
            gen["id"], CreateVariationRequest(kind="hook_line", value="Stop doing this"), ANON))
        assert result["project"]["status"] == "draft"
        after = len(_run(api.list_generations(user_id=ANON))["generations"])
        assert after == before, "a variation must not create a generation"

    def test_hook_variation_updates_the_draft(self, api):
        from models import CreateVariationRequest
        profile = _profile(api, "Var Hook")
        gen, _, _ = _generation(api, profile, "Var Hook")
        result = _run(api.create_variation(
            gen["id"], CreateVariationRequest(kind="hook_line", value="Stop doing this"), ANON))
        assert result["project"]["hook_line"] == "Stop doing this"
        assert result["project"]["script"].startswith("Stop doing this")

    def test_template_variation_copies_everything_else(self, api):
        from models import CreateVariationRequest
        profile = _profile(api, "Var Template")
        gen, project, _ = _generation(api, profile, "Var Template")
        other = [t for t in _run(api.list_templates(user_id=ANON))["templates"]
                 if t["id"] != project["template_id"]][0]
        result = _run(api.create_variation(
            gen["id"], CreateVariationRequest(kind="template", value=other["id"]), ANON))
        derived = result["project"]
        assert derived["template_id"] == other["id"]
        assert derived["template_version"] == other["version"]
        # Hook, script, demo brief, assets and audience carry over untouched.
        assert derived["hook_line"] == project["hook_line"]
        assert derived["script"] == project["script"]
        assert derived["demo_brief"] == project["demo_brief"]
        # The retired cta column does not: there is no call to action in a
        # generated piece, and carrying a stale one into the copy would put a
        # closing beat into footage meant to stop at the reach.
        assert derived["cta"] is None

    def test_duration_variation_clamps_to_supported(self, api):
        """
        A length is one render, so a variation that asks for 7s gets the
        shortest supported piece (8s) rather than something no single pass can
        produce. 7 was below every supported length when 10 was the floor.
        """
        import template_library as tl
        from models import CreateVariationRequest
        profile = _profile(api, "Var Duration")
        gen, _, _ = _generation(api, profile, "Var Duration")
        result = _run(api.create_variation(
            gen["id"], CreateVariationRequest(kind="duration", value="7"), ANON))
        assert result["project"]["duration_seconds"] == tl.SUPPORTED_DURATIONS[0] == 8

    def test_audience_variation_changes_only_the_audience(self, api):
        from models import CreateVariationRequest
        profile = _profile(api, "Var Audience")
        gen, project, _ = _generation(api, profile, "Var Audience")
        result = _run(api.create_variation(
            gen["id"], CreateVariationRequest(kind="audience", value="Students"), ANON))
        assert result["project"]["audience"] == "Students"
        assert result["project"]["hook_line"] == project["hook_line"]

    def test_pacing_variation_records_a_directive(self, api):
        from models import CreateVariationRequest
        profile = _profile(api, "Var Pacing")
        gen, _, _ = _generation(api, profile, "Var Pacing")
        result = _run(api.create_variation(
            gen["id"], CreateVariationRequest(kind="pacing", value="faster"), ANON))
        assert "PACING: FAST" in result["project"]["visual_direction"]

    def test_variation_resets_script_version(self, api):
        """A derived draft has not had its script reviewed yet."""
        from models import CreateVariationRequest
        profile = _profile(api, "Var Reset")
        gen, _, _ = _generation(api, profile, "Var Reset")
        result = _run(api.create_variation(
            gen["id"], CreateVariationRequest(kind="app_feature", value="The reminders"), ANON))
        assert result["project"]["script_version"] == 0

    def test_variation_is_not_ready_for_generation_until_reviewed(self, api):
        from models import CreateVariationRequest
        profile = _profile(api, "Var NotReady")
        gen, _, _ = _generation(api, profile, "Var NotReady")
        result = _run(api.create_variation(
            gen["id"], CreateVariationRequest(kind="tone", value="playful"), ANON))
        assert result["project"]["status"] == "draft"

    def test_lineage_is_recorded_on_the_parent(self, api):
        from models import CreateVariationRequest
        profile = _profile(api, "Var Lineage")
        gen, _, _ = _generation(api, profile, "Var Lineage")
        result = _run(api.create_variation(
            gen["id"], CreateVariationRequest(kind="hook_line", value="New", note="test"), ANON))
        parent = _run(api.get_generation(gen["id"], ANON))
        # variation_params is a JSON column, so the row factory decodes it. It
        # used to arrive as a string, which is why this used to need json.loads
        # and why _public_generation's `or {}` fallback never fired.
        params = parent["variation_params"]
        assert isinstance(params, dict)
        assert parent["variation_kind"] == "hook_line"
        assert params["derived_project_id"] == result["project"]["id"]
        assert params["note"] == "test"

    def test_unknown_kind_is_rejected(self, api):
        from models import CreateVariationRequest
        profile = _profile(api, "Var Unknown")
        gen, _, _ = _generation(api, profile, "Var Unknown")
        with pytest.raises(HTTPException) as err:
            _run(api.create_variation(
                gen["id"], CreateVariationRequest(kind="nonsense", value="x"), ANON))
        assert err.value.status_code == 400

    def test_bad_value_is_rejected(self, api):
        from models import CreateVariationRequest
        profile = _profile(api, "Var BadValue")
        gen, _, _ = _generation(api, profile, "Var BadValue")
        with pytest.raises(HTTPException) as err:
            _run(api.create_variation(
                gen["id"], CreateVariationRequest(kind="pacing", value="sideways"), ANON))
        assert err.value.status_code == 400

    def test_unknown_template_is_rejected(self, api):
        from models import CreateVariationRequest
        profile = _profile(api, "Var BadTpl")
        gen, _, _ = _generation(api, profile, "Var BadTpl")
        with pytest.raises(HTTPException) as err:
            _run(api.create_variation(
                gen["id"], CreateVariationRequest(kind="template", value=str(uuid.uuid4())), ANON))
        assert err.value.status_code == 404

    def test_unpublished_template_is_rejected(self, api):
        from models import CreateVariationRequest
        profile = _profile(api, "Var DraftTpl")
        gen, project, _ = _generation(api, profile, "Var DraftTpl")
        tpl_id = str(uuid.uuid4())
        _run(api._execute(
            """INSERT INTO hook_templates (id, name, category, opening_structure,
               origin, review_status, archived, version, created_at, updated_at, user_id)
               VALUES (?, 'Unpublished', 'other', 'A structure', 'research_draft',
               'draft', 0, 1, '', '', 'system')""", (tpl_id,)))
        with pytest.raises(HTTPException) as err:
            _run(api.create_variation(
                gen["id"], CreateVariationRequest(kind="template", value=tpl_id), ANON))
        assert err.value.status_code == 409

    def test_missing_generation_is_404(self, api):
        from models import CreateVariationRequest
        with pytest.raises(HTTPException) as err:
            _run(api.create_variation(
                str(uuid.uuid4()), CreateVariationRequest(kind="hook_line", value="x"), ANON))
        assert err.value.status_code == 404

    def test_another_users_generation_is_404(self, api):
        from models import CreateVariationRequest
        profile = _profile(api, "Var Isolated")
        gen, _, _ = _generation(api, profile, "Var Isolated")
        with pytest.raises(HTTPException) as err:
            _run(api.create_variation(
                gen["id"], CreateVariationRequest(kind="hook_line", value="x"), OTHER_USER))
        assert err.value.status_code == 404

    def test_variation_catalogued_as_free_or_needs_plan(self, api):
        from models import CreateVariationRequest
        profile = _profile(api, "Var Cost")
        gen, _, _ = _generation(api, profile, "Var Cost")
        cheap = _run(api.create_variation(
            gen["id"], CreateVariationRequest(kind="duration", value="15"), ANON))
        assert cheap["regenerate_plan"] is False
        creative = _run(api.create_variation(
            gen["id"], CreateVariationRequest(kind="hook_line", value="New"), ANON))
        assert creative["regenerate_plan"] is False  # opt-in only


class TestVariationLineage:
    def test_children_are_listed_under_the_parent(self, api):
        from models import CreateVariationRequest
        profile = _profile(api, "Line List")
        gen, _, _ = _generation(api, profile, "Line List")
        _run(api.create_variation(
            gen["id"], CreateVariationRequest(kind="hook_line", value="A"), ANON))
        child = _run(api.create_variation(
            gen["id"], CreateVariationRequest(kind="app_feature", value="The reminders"), ANON))
        assert child["parent_generation_id"] == gen["id"]
        listed = _run(api.list_generation_variations(gen["id"], ANON))
        assert isinstance(listed["variations"], list)

    def test_listing_for_unknown_generation_is_404(self, api):
        with pytest.raises(HTTPException) as err:
            _run(api.list_generation_variations(str(uuid.uuid4()), ANON))
        assert err.value.status_code == 404


class TestDuplicate:
    """
    Duplicate is the third way to work from an existing video, and the only one
    that changes nothing. Retry recovers a failure, a variation changes one axis
    on purpose, and a duplicate re-rolls the identical setup.
    """

    def test_copies_the_setup_unchanged(self, api):
        gen, project, _ = _generation(api, _profile(api, "Dup Copy"), "Dup Copy")
        result = _run(api.duplicate_generation(gen["id"], ANON))
        copy = result["project"]
        assert copy["hook_line"] == project["hook_line"]
        assert copy["script"] == project["script"]
        assert copy["demo_brief"] == project["demo_brief"]
        assert copy["template_id"] == project["template_id"]
        assert copy["template_version"] == project["template_version"]
        assert copy["duration_seconds"] == project["duration_seconds"]
        assert copy["tone"] == project["tone"]
        assert copy["audience"] == project["audience"]
        assert copy["assets"] == project["assets"]
        # Deliberately NOT copied, and the reason it is still here in the
        # fixture: a generated piece has no call to action. A duplicate that
        # carried a stale cta forward would close a video that is supposed to
        # stop at the moment the presenter reaches for their phone.
        assert copy["cta"] is None

    def test_the_plan_survives_so_no_text_call_is_needed(self, api):
        """
        Resetting script_version would force a fresh plan and quietly change the
        thing being duplicated. The copy has to be ready to render as it stands.
        """
        gen, project, _ = _generation(api, _profile(api, "Dup Plan"), "Dup Plan")
        result = _run(api.duplicate_generation(gen["id"], ANON))
        assert result["project"]["script_version"] == project["script_version"]
        assert result["project"]["script_version"] > 0

    def test_the_copy_starts_as_a_draft(self, api):
        """
        A draft, never a video: producing it stays an explicit decision so a
        duplicate cannot spend money on its own.
        """
        gen, _, _ = _generation(api, _profile(api, "Dup Draft"), "Dup Draft")
        result = _run(api.duplicate_generation(gen["id"], ANON))
        assert result["project"]["status"] == "draft"
        assert result["note"]

    def test_lineage_is_recorded_on_the_parent(self, api):
        gen, _, _ = _generation(api, _profile(api, "Dup Lineage"), "Dup Lineage")
        result = _run(api.duplicate_generation(gen["id"], ANON))
        assert result["parent_generation_id"] == gen["id"]
        after = _run(api.get_generation(gen["id"], ANON))
        assert after["variation_params"]["derived_project_id"] == result["project"]["id"]

    def test_a_variation_lineage_is_not_overwritten(self, api):
        """
        COALESCE on purpose: a generation can spawn several children, and the
        first lineage note should survive a later duplicate.
        """
        from models import CreateVariationRequest
        gen, _, _ = _generation(api, _profile(api, "Dup Keeps"), "Dup Keeps")
        _run(api.create_variation(
            gen["id"], CreateVariationRequest(kind="app_feature", value="The reminders"), ANON))
        _run(api.duplicate_generation(gen["id"], ANON))
        after = _run(api.get_generation(gen["id"], ANON))
        assert after["variation_kind"] == "app_feature"

    def test_the_copy_is_independent_of_its_parent(self, api):
        """Editing the copy must not write back to the original."""
        from models import UpdateStudioProjectRequest
        gen, project, _ = _generation(api, _profile(api, "Dup Indep"), "Dup Indep")
        result = _run(api.duplicate_generation(gen["id"], ANON))
        _run(api.update_studio_project(
            project_id=result["project"]["id"],
            payload=UpdateStudioProjectRequest(hook_line="Changed"),
            user_id=ANON,
        ))
        assert _run(api.get_studio_project(project["id"], ANON))["hook_line"] == "Old hook"

    def test_unknown_generation_is_404(self, api):
        with pytest.raises(HTTPException) as err:
            _run(api.duplicate_generation(str(uuid.uuid4()), ANON))
        assert err.value.status_code == 404

    def test_another_users_generation_is_404(self, api):
        gen, _, _ = _generation(api, _profile(api, "Dup Private"), "Dup Private")
        with pytest.raises(HTTPException) as err:
            _run(api.duplicate_generation(gen["id"], OTHER_USER))
        assert err.value.status_code == 404

    def test_missing_source_project_is_404(self, api):
        gen, _, _ = _generation(api, _profile(api, "Dup No Project"), "Dup No Project")
        _run(api._execute(
            "UPDATE generations SET studio_project_id = ? WHERE id = ?",
            (str(uuid.uuid4()), gen["id"]),
        ))
        with pytest.raises(HTTPException) as err:
            _run(api.duplicate_generation(gen["id"], ANON))
        assert err.value.status_code == 404

    def test_missing_app_profile_is_409(self, api):
        """
        The project must still belong to a live App Profile. This pins the
        awaited profile lookup: without it, the guard always passes.
        """
        gen, project, _ = _generation(api, _profile(api, "Dup No Profile"), "Dup No Profile")
        _run(api._execute(
            "UPDATE studio_projects SET brand_profile_id = ? WHERE id = ?",
            (str(uuid.uuid4()), project["id"]),
        ))
        with pytest.raises(HTTPException) as err:
            _run(api.duplicate_generation(gen["id"], ANON))
        assert err.value.status_code == 409

    def test_duplicate_is_distinct_from_a_variation(self, api):
        """A variation changes one field; a duplicate changes none.

        Pinned on `hook_line` because it is the one axis whose change is
        observable in both halves of the comparison. An axis writing a retired
        field could not evidence "one field changed" here: both sides would
        read None and the test would pass vacuously.
        """
        from models import CreateVariationRequest
        profile = _profile(api, "Dup Distinct")
        gen, project, _ = _generation(api, profile, "Dup Distinct")
        varied = _run(api.create_variation(
            gen["id"],
            CreateVariationRequest(kind="hook_line", value="Totally different"), ANON))
        copied = _run(api.duplicate_generation(gen["id"], ANON))
        assert varied["project"]["hook_line"] == "Totally different"
        assert varied["project"]["hook_line"] != project["hook_line"]
        assert copied["project"]["hook_line"] == project["hook_line"]


class TestHistory:
    def test_history_includes_profile_and_template_context(self, api):
        profile = _profile(api, "Hist Ctx")
        _generation(api, profile, "Hist Ctx")
        rows = _run(api.generation_history(brand_profile_id=profile["id"], user_id=ANON))
        assert rows["generations"]
        row = rows["generations"][0]
        assert row["brand_name"] == "Hist Ctx"
        assert row["model"]
        assert row["template_version"]

    def test_history_is_scoped_to_user(self, api):
        profile = _profile(api, "Hist User")
        _generation(api, profile, "Hist User")
        mine = _run(api.generation_history(user_id=ANON))["generations"]
        theirs = _run(api.generation_history(user_id=OTHER_USER))["generations"]
        assert mine
        assert theirs == []

    def test_history_filters_by_status(self, api):
        profile = _profile(api, "Hist Status")
        _generation(api, profile, "Hist Status", status="failed")
        failed = _run(api.generation_history(status="failed", user_id=ANON))["generations"]
        assert all(g["status"] == "failed" for g in failed)
        completed = _run(api.generation_history(status="completed", user_id=ANON))["generations"]
        assert all(g["status"] == "completed" for g in completed)

    def test_history_omits_the_long_prompt(self, api):
        profile = _profile(api, "Hist Light")
        _generation(api, profile, "Hist Light")
        row = _run(api.generation_history(user_id=ANON))["generations"][0]
        assert "prompt_used" not in row

    def test_history_reports_no_composition(self, api):
        profile = _profile(api, "Hist Comp")
        _generation(api, profile, "Hist Comp")
        row = _run(api.generation_history(user_id=ANON))["generations"][0]
        assert row["composition"] is None

    def test_delete_removes_generation_and_dependents(self, api):
        from models import PerformanceEntryRequest
        profile = _profile(api, "Hist Delete")
        gen, _, _ = _generation(api, profile, "Hist Delete")
        _run(api.record_performance(
            gen["id"], PerformanceEntryRequest(views=100, outcome="successful"), ANON))
        assert _run(api._fetch_all(
            "SELECT id FROM performance_entries WHERE generation_id = ?", (gen["id"],)))

        _run(api.delete_generation(gen["id"], ANON))

        with pytest.raises(HTTPException):
            _run(api.get_generation(gen["id"], ANON))
        # Dependents are cleaned up rather than left orphaned.
        assert _run(api._fetch_all(
            "SELECT id FROM performance_entries WHERE generation_id = ?", (gen["id"],))) == []
        assert _run(api._fetch_all(
            "SELECT job_id FROM video_assets WHERE job_id = ?", (gen["id"],))) == []

    def test_another_user_cannot_delete(self, api):
        profile = _profile(api, "Hist DelUser")
        gen, _, _ = _generation(api, profile, "Hist DelUser")
        with pytest.raises(HTTPException) as err:
            _run(api.delete_generation(gen["id"], OTHER_USER))
        assert err.value.status_code == 404

    def test_archive_preserves_the_row(self, api):
        """Archive, not delete, is the default: the row keeps the render."""
        profile = _profile(api, "Hist Archive")
        gen, _, _ = _generation(api, profile, "Hist Archive")
        archived = _run(api.archive_generation(gen["id"], ANON))
        assert archived["status"] == "archived"
        assert archived["video_url"] == gen["video_url"]


class TestManualPerformance:
    def test_recorded_entry_is_labelled_manual_and_unverified(self, api):
        from models import PerformanceEntryRequest
        profile = _profile(api, "Perf Manual")
        gen, _, _ = _generation(api, profile, "Perf Manual")
        created = _run(api.record_performance(
            gen["id"],
            PerformanceEntryRequest(
                views=12000, likes=800, comments=40, shares=90, saves=250,
                notes="Posted 3pm", outcome="successful"),
            ANON))
        assert created["source"] == "manual"
        assert created["verified"] is False
        assert created["views"] == 12000

    def test_outcome_must_be_recognised(self, api):
        from models import PerformanceEntryRequest
        profile = _profile(api, "Perf Outcome")
        gen, _, _ = _generation(api, profile, "Perf Outcome")
        with pytest.raises(HTTPException) as err:
            _run(api.record_performance(
                gen["id"], PerformanceEntryRequest(outcome="viral"), ANON))
        assert err.value.status_code == 400

    def test_negative_counts_are_clamped_to_zero(self, api):
        from models import PerformanceEntryRequest
        profile = _profile(api, "Perf Neg")
        gen, _, _ = _generation(api, profile, "Perf Neg")
        created = _run(api.record_performance(
            gen["id"], PerformanceEntryRequest(views=-5, likes=-1), ANON))
        assert created["views"] == 0
        assert created["likes"] == 0

    def test_all_fields_are_optional(self, api):
        from models import PerformanceEntryRequest
        profile = _profile(api, "Perf Empty")
        gen, _, _ = _generation(api, profile, "Perf Empty")
        created = _run(api.record_performance(gen["id"], PerformanceEntryRequest(), ANON))
        assert created["views"] is None

    def test_entries_accumulate(self, api):
        from models import PerformanceEntryRequest
        profile = _profile(api, "Perf Acc")
        gen, _, _ = _generation(api, profile, "Perf Acc")
        _run(api.record_performance(gen["id"], PerformanceEntryRequest(views=100), ANON))
        _run(api.record_performance(gen["id"], PerformanceEntryRequest(views=250), ANON))
        entries = _run(api.get_performance(gen["id"], ANON))["performance"]
        assert len(entries) == 2

    def test_listing_states_nothing_is_verified(self, api):
        profile = _profile(api, "Perf Verified")
        gen, _, _ = _generation(api, profile, "Perf Verified")
        result = _run(api.get_performance(gen["id"], ANON))
        assert result["source"] == "manual"
        assert result["verified"] is False

    def test_another_user_cannot_record(self, api):
        from models import PerformanceEntryRequest
        profile = _profile(api, "Perf User")
        gen, _, _ = _generation(api, profile, "Perf User")
        with pytest.raises(HTTPException) as err:
            _run(api.record_performance(
                gen["id"], PerformanceEntryRequest(views=1), OTHER_USER))
        assert err.value.status_code == 404
