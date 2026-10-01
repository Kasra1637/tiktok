"""
DB-backed tests for studio projects: the approval gate, the template
requirement, claim-safety enforcement across edits, and version bookkeeping.

The AI plan call is mocked, so these tests assert our own orchestration rules
rather than model behaviour.
"""
import asyncio
import importlib
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
    tmpdir = tempfile.mkdtemp(prefix="tiktok-p4-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""

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


def _approved_profile(api, name="Studio App", **kwargs):
    from models import BrandProfileCreateRequest, ApproveAppProfileRequest
    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name,
        app_category=kwargs.get("app_category", "Productivity"),
        core_features=kwargs.get("core_features", ["Task timer", "Reminders"]),
        pricing_trial=kwargs.get("pricing_trial", "Free, Pro $79.99/year"),
        claims_approved=kwargs.get("claims_approved", ["3-day free trial", "works offline"]),
        claims_review=kwargs.get("claims_review", ["4.8 star rating"]),
        claims_banned=kwargs.get("claims_banned", ["cures anxiety", "guaranteed results"]),
        ctas=["Try it free"],
    ), user_id=ANON))
    if kwargs.get("approve", True):
        _run(api.approve_app_profile(
            profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        profile = _run(api.get_app_profile(profile["id"], ANON))
    return profile


def _a_template(api, name="Stop Doing This"):
    return _run(api.list_templates(q=name, user_id=ANON))["templates"][0]


def _a_project(api, profile, template):
    from models import CreateStudioProjectRequest
    return _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"],
        template_id=template["id"],
        objective="demonstrate_feature",
    ), user_id=ANON))


# A realistic plan the mocked generator returns.
FAKE_PLAN = {
    "hook_line": "Stop writing empty pages",
    "script": "Taskly gives you one short prompt and a reminder. It works offline.",
    "beat_timeline": [
        {"start": 0, "end": 3, "label": "hook", "text": "Stop writing empty pages"},
        {"start": 3, "end": 8, "label": "problem", "text": "Blank page friction"},
        {"start": 8, "end": 17, "label": "demo", "text": "Complete one task"},
        {"start": 17, "end": 20, "label": "cta", "text": "Try it free"},
    ],
    "visual_direction": "Close on hands, then a screen recording with clean space for overlays.",
    "feature_emphasis": "The task timer, shown mid-video",
    "overlays": [{"start": 0, "end": 3, "text": "one prompt"}],
    "voice_direction": "Warm, unhurried",
    "sound_direction": "Lo-fi bed, rights-safe",
    "cta": "Try the 3-day free trial",
    "claims_used": ["works offline"],
}

BANNED_PLAN = {**FAKE_PLAN, "script": "Taskly cures anxiety for good."}


def _patch_plan(monkey, server, plan):
    """Replace the AI plan call so tests exercise orchestration, not the model."""
    async def fake_generate_creative_plan(**kwargs):
        return dict(plan)
    monkey.setattr(server, "generate_creative_plan", fake_generate_creative_plan)


class TestProjectCreation:
    def test_create_against_approved_profile(self, api):
        profile = _approved_profile(api, "Create OK")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        assert project["status"] == "draft"
        assert project["brand_profile_id"] == profile["id"]
        assert project["template_id"] == template["id"]

    def test_template_version_is_pinned(self, api):
        profile = _approved_profile(api, "Pin Version")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        assert project["template_version"] == template["version"]

    def test_duration_defaults_from_template(self, api):
        profile = _approved_profile(api, "Duration Default")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        assert project["duration_seconds"] == template["default_duration"]

    def test_unapproved_profile_is_blocked(self, api):
        profile = _approved_profile(api, "Not Approved", approve=False)
        template = _a_template(api)
        with pytest.raises(HTTPException) as err:
            _a_project(api, profile, template)
        assert err.value.status_code == 409

    def test_unknown_profile_is_404(self, api):
        from models import CreateStudioProjectRequest
        with pytest.raises(HTTPException) as err:
            _run(api.create_studio_project(payload=CreateStudioProjectRequest(
                brand_profile_id=str(uuid.uuid4())), user_id=ANON))
        assert err.value.status_code == 404

    def test_unknown_template_is_404(self, api):
        from models import CreateStudioProjectRequest
        profile = _approved_profile(api, "Bad Template")
        with pytest.raises(HTTPException) as err:
            _run(api.create_studio_project(payload=CreateStudioProjectRequest(
                brand_profile_id=profile["id"], template_id=str(uuid.uuid4())), user_id=ANON))
        assert err.value.status_code == 404

    def test_duration_is_clamped_to_supported_values(self, api):
        from models import CreateStudioProjectRequest
        profile = _approved_profile(api, "Clamp Duration")
        template = _a_template(api)
        for requested, expected in ((7, 10), (45, 30), (20, 20)):
            project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
                brand_profile_id=profile["id"], template_id=template["id"],
                duration_seconds=requested), user_id=ANON))
            assert project["duration_seconds"] == expected

    def test_list_is_scoped_to_user(self, api):
        profile = _approved_profile(api, "List Scoped")
        template = _a_template(api)
        _a_project(api, profile, template)
        mine = _run(api.list_studio_projects(user_id=ANON))
        theirs = _run(api.list_studio_projects(user_id=OTHER_USER))
        assert mine["projects"]
        assert theirs["projects"] == []

    def test_one_profile_backs_many_drafts(self, api):
        """
        An App Profile is a reusable starting point, not something consumed by
        the first video. This is the invariant behind the profile page's "New
        video" button and its list of drafts: if a one-draft-per-profile
        constraint ever gets added, reuse silently dies here first.
        """
        profile = _approved_profile(api, "Reusable")
        template = _a_template(api)
        first = _a_project(api, profile, template)
        second = _a_project(api, profile, template)
        assert first["id"] != second["id"]
        # The profile is still intact and still approved after both.
        assert _run(api.get_app_profile(profile["id"], ANON))["status"] == "approved"

    def test_drafts_can_be_filtered_to_one_profile(self, api):
        """
        The profile page lists only this app's drafts. Two apps, so a filter
        that ignored brand_profile_id would show the wrong app's history.
        """
        a = _approved_profile(api, "Filter A")
        b = _approved_profile(api, "Filter B")
        template = _a_template(api)
        draft_a = _a_project(api, a, template)
        draft_b = _a_project(api, b, template)

        only_a = _run(api.list_studio_projects(brand_profile_id=a["id"], user_id=ANON))
        assert [p["id"] for p in only_a["projects"]] == [draft_a["id"]]

        only_b = _run(api.list_studio_projects(brand_profile_id=b["id"], user_id=ANON))
        assert [p["id"] for p in only_b["projects"]] == [draft_b["id"]]

        # The filter must not become a way to read someone else's drafts.
        leaked = _run(api.list_studio_projects(
            brand_profile_id=a["id"], user_id=OTHER_USER))
        assert leaked["projects"] == []


class TestProfilePickerFeedsTheWizard:
    """
    The wizard's first step is a picker over GET /api/app-profiles. It splits
    that list itself into selectable and waiting, then NAMES the waiting ones,
    because a profile you already created but have not approved used to be
    invisible there: the step rendered only the approved half and said nothing
    about the rest, so five apps and two approvals looked like two.

    That makes this endpoint load-bearing for a promise it does not itself
    enforce. It must keep returning unapproved profiles, or the wizard has
    nothing left to name and the problem returns silently.
    """

    def test_listing_returns_unapproved_profiles_too(self, api):
        _approved_profile(api, "Picked App")
        _approved_profile(api, "Still Waiting", approve=False)
        profiles = _run(api.list_app_profiles(user_id=ANON))["profiles"]
        by_name = {p["brand_name"]: p for p in profiles}
        assert "Still Waiting" in by_name, "an unapproved profile must still be returned"
        assert by_name["Still Waiting"]["status"] != "approved"

    def test_every_created_profile_is_returned_exactly_once(self, api):
        # The `api` fixture is module-scoped, so ANON's profiles accumulate
        # across every test in this file. Count the names this test created
        # rather than the whole list, which is what makes the assertion about
        # duplication still hold.
        for name in ("One", "Twice", "Twice", "Three"):
            _approved_profile(api, name, approve=(name != "Twice"))
        profiles = _run(api.list_app_profiles(user_id=ANON))["profiles"]
        names = [p["brand_name"] for p in profiles]
        assert names.count("One") == 1
        assert names.count("Three") == 1
        # Two genuinely distinct profiles may share a name, and both must come
        # back. The picker keys on id, not name, so a duplicate label is fine —
        # but losing one is not.
        assert names.count("Twice") == 2, names
        waiting = [p for p in profiles if p["brand_name"] == "Twice"]
        assert all(p["status"] != "approved" for p in waiting)
        assert len({p["id"] for p in waiting}) == 2, "both must be distinct records"

    def test_listing_stays_scoped_to_the_caller(self, api):
        _approved_profile(api, "Mine Approved")
        _approved_profile(api, "Mine Waiting", approve=False)
        assert _run(api.list_app_profiles(user_id=OTHER_USER))["profiles"] == []

    def test_status_is_exactly_the_string_the_picker_compares(self, api):
        """
        The frontend compares status === "approved" verbatim, so the approve
        endpoint has to write that exact literal. A rename on either side would
        make every profile unselectable, or worse, make drafts selectable.
        """
        approved = _approved_profile(api, "Exact Match")
        waiting = _approved_profile(api, "Not Exact", approve=False)
        profiles = {p["id"]: p for p in _run(api.list_app_profiles(user_id=ANON))["profiles"]}
        assert profiles[approved["id"]]["status"] == "approved"
        assert profiles[waiting["id"]]["status"] != "approved"


class TestPlanGating:
    def test_plan_requires_a_template(self, api, monkeypatch):
        _patch_plan(monkeypatch, api, FAKE_PLAN)
        from models import CreateStudioProjectRequest, GeneratePlanRequest
        profile = _approved_profile(api, "No Template")
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"]), user_id=ANON))
        with pytest.raises(HTTPException) as err:
            _run(api.generate_plan(project_id=project["id"],
                                   payload=GeneratePlanRequest(), user_id=ANON))
        assert err.value.status_code == 400
        assert "template" in str(err.value.detail).lower()

    def test_plan_blocked_for_unapproved_profile(self, api, monkeypatch):
        """
        The plan step re-checks approval independently of project creation, so
        a profile that loses approval after the draft exists still blocks.
        """
        _patch_plan(monkeypatch, api, FAKE_PLAN)
        from models import GeneratePlanRequest
        profile = _approved_profile(api, "Plan Recheck")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        # Simulate a profile being sent back to draft (e.g. a pending refresh).
        _run(api._execute(
            "UPDATE brand_profiles SET status = 'draft' WHERE id = ?", (profile["id"],)))
        with pytest.raises(HTTPException) as err:
            _run(api.generate_plan(project_id=project["id"],
                                   payload=GeneratePlanRequest(), user_id=ANON))
        assert err.value.status_code == 409

    def test_plan_stores_every_generated_field(self, api, monkeypatch):
        _patch_plan(monkeypatch, api, FAKE_PLAN)
        from models import GeneratePlanRequest
        profile = _approved_profile(api, "Plan Full")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        result = _run(api.generate_plan(project_id=project["id"],
                                        payload=GeneratePlanRequest(), user_id=ANON))
        assert result["hook_line"] == FAKE_PLAN["hook_line"]
        assert result["script"] == FAKE_PLAN["script"]
        assert result["cta"] == FAKE_PLAN["cta"]
        assert len(result["beat_timeline"]) == 4
        assert result["overlays"]
        assert result["script_version"] == 1

    def test_duration_cannot_be_changed_once_a_plan_exists(self, api, monkeypatch):
        """
        The plan's beat timeline is built for the length the plan was generated
        at, and every beat is clamped to it. Patching duration_seconds afterwards
        therefore produced a timeline that no longer adds up to the stated
        runtime — with the shot timeline displayed read-only, so nothing on
        screen could say so.
        """
        _patch_plan(monkeypatch, api, FAKE_PLAN)
        from models import GeneratePlanRequest, UpdateStudioProjectRequest
        profile = _approved_profile(api, "Locked Length")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        _run(api.generate_plan(project_id=project["id"],
                               payload=GeneratePlanRequest(duration_seconds=20),
                               user_id=ANON))
        with pytest.raises(HTTPException) as err:
            _run(api.update_studio_project(
                project_id=project["id"],
                payload=UpdateStudioProjectRequest(duration_seconds=30),
                user_id=ANON))
        assert err.value.status_code == 409
        assert "regenerate the plan" in err.value.detail

    def test_the_same_duration_is_accepted_idempotently(self, api, monkeypatch):
        """Re-sending the current length is not a change, so it is not refused."""
        _patch_plan(monkeypatch, api, FAKE_PLAN)
        from models import GeneratePlanRequest, UpdateStudioProjectRequest
        profile = _approved_profile(api, "Same Length")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        _run(api.generate_plan(project_id=project["id"],
                               payload=GeneratePlanRequest(duration_seconds=20),
                               user_id=ANON))
        result = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(duration_seconds=20),
            user_id=ANON))
        assert result["duration_seconds"] == 20

    def test_duration_is_free_before_a_plan_exists(self, api):
        """The length is chosen on the Audience & goal step, which is earlier."""
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Pre Plan Length")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        result = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(duration_seconds=30),
            user_id=ANON))
        assert result["duration_seconds"] == 30

    def test_regenerating_the_plan_at_a_new_length_rewrites_the_timeline(
        self, api, monkeypatch
    ):
        """The sanctioned route: the plan writes the length with its beats."""
        _patch_plan(monkeypatch, api, FAKE_PLAN)
        from models import GeneratePlanRequest
        profile = _approved_profile(api, "Regen Length")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        _run(api.generate_plan(project_id=project["id"],
                               payload=GeneratePlanRequest(duration_seconds=20),
                               user_id=ANON))
        again = _run(api.generate_plan(project_id=project["id"],
                                       payload=GeneratePlanRequest(duration_seconds=10),
                                       user_id=ANON))
        assert again["duration_seconds"] == 10
        assert again["script_version"] == 2

    def test_plan_bumps_script_version_on_regenerate(self, api, monkeypatch):
        _patch_plan(monkeypatch, api, FAKE_PLAN)
        from models import GeneratePlanRequest
        profile = _approved_profile(api, "Regen")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        _run(api.generate_plan(project_id=project["id"],
                               payload=GeneratePlanRequest(), user_id=ANON))
        again = _run(api.generate_plan(project_id=project["id"],
                                       payload=GeneratePlanRequest(), user_id=ANON))
        assert again["script_version"] == 2

    def test_clean_plan_passes_safety(self, api, monkeypatch):
        _patch_plan(monkeypatch, api, FAKE_PLAN)
        from models import GeneratePlanRequest
        profile = _approved_profile(api, "Clean Plan")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        result = _run(api.generate_plan(project_id=project["id"],
                                        payload=GeneratePlanRequest(), user_id=ANON))
        assert result["safety_report"]["passed"] is True
        assert "works offline" in result["safety_report"]["claims_used"]
        assert "Clean" in result["safety_summary"]

    def test_banned_claim_fails_safety_but_is_still_returned(self, api, monkeypatch):
        """The founder must SEE the bad plan in order to fix it."""
        _patch_plan(monkeypatch, api, BANNED_PLAN)
        from models import GeneratePlanRequest
        profile = _approved_profile(api, "Banned Plan")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        result = _run(api.generate_plan(project_id=project["id"],
                                        payload=GeneratePlanRequest(), user_id=ANON))
        assert result["script"] == BANNED_PLAN["script"]
        assert result["safety_report"]["passed"] is False
        assert [b["claim"] for b in result["safety_report"]["blocking"]] == ["cures anxiety"]


class TestClaimSafetyOnEdit:
    """
    A founder editing the script must not be able to smuggle a prohibited
    claim past the gate — the report is recomputed on every edit.
    """

    def test_pasting_a_banned_claim_fails_the_report(self, api, monkeypatch):
        _patch_plan(monkeypatch, api, FAKE_PLAN)
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Edit Safety")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        edited = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(script="Taskly cures anxiety."),
            user_id=ANON,
        ))
        assert edited["safety_report"]["passed"] is False
        assert edited["safety_report"]["blocking"]

    def test_edit_bumps_script_version(self, api):
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Edit Version")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        edited = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(script="A new script."),
            user_id=ANON,
        ))
        assert edited["script_version"] == 1

    def test_every_editable_field_is_writable(self, api):
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Edit Fields")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        edited = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(
                hook_line="New hook", script="New script.", cta="New cta",
                visual_direction="New direction", voice_direction="Calm",
                sound_direction="Ambient", feature_emphasis="The timer",
                tone="playful", audience="Busy parents",
                beat_timeline=[{"start": 0, "end": 3, "label": "hook", "text": "Hi"}],
                overlays=[{"start": 0, "end": 2, "text": "Hi"}],
            ),
            user_id=ANON,
        ))
        assert edited["hook_line"] == "New hook"
        assert edited["cta"] == "New cta"
        assert edited["voice_direction"] == "Calm"
        assert edited["beat_timeline"][0]["text"] == "Hi"
        assert edited["overlays"][0]["text"] == "Hi"

    def test_switching_template_repins_version(self, api):
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Repin")
        first = _a_template(api, "Stop Doing This")
        second = _a_template(api, "Pain-Point Question")
        project = _a_project(api, profile, first)
        edited = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(template_id=second["id"]),
            user_id=ANON,
        ))
        assert edited["template_id"] == second["id"]
        assert edited["template_version"] == second["version"]

    def test_unknown_field_is_ignored(self, api):
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Unknown Field")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        # status is intentionally NOT in STUDIO_EDITABLE_FIELDS.
        result = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(script="Fine."),
            user_id=ANON,
        ))
        assert result["status"] == "draft"


class TestOverlayNormalization:
    """
    On-screen text is hand-editable in the review step, so it arrives with the
    mistakes a text box invites. Storing them unfiltered would make a saved
    plan list text the video never shows.
    """

    def test_blank_overlays_are_dropped(self, api):
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Overlay Blank")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        edited = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(overlays=[
                {"start": 0, "end": 2, "text": "Real text"},
                {"start": 2, "end": 4, "text": "   "},
                {"start": 4, "end": 6},
            ]),
            user_id=ANON,
        ))
        assert [o["text"] for o in edited["overlays"]] == ["Real text"]

    def test_an_inverted_window_is_given_a_minimum_length(self, api):
        """
        end <= start means the caption's enable window is never true, so it
        would be stored but never rendered.
        """
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Overlay Inverted")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        edited = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(overlays=[
                {"start": 5, "end": 5, "text": "Backwards"},
                {"start": 6, "end": 2, "text": "Also backwards"},
            ]),
            user_id=ANON,
        ))
        for overlay in edited["overlays"]:
            assert overlay["end"] > overlay["start"], overlay

    def test_a_negative_start_is_clamped(self, api):
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Overlay Negative")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        edited = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(overlays=[
                {"start": -3, "end": 2, "text": "Hi"},
            ]),
            user_id=ANON,
        ))
        assert edited["overlays"][0]["start"] == 0

    def test_clearing_every_overlay_is_allowed(self, api):
        """
        A founder may decide a video needs no on-screen text, so an empty list
        is a real edit rather than something to reject.
        """
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Overlay Cleared")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        edited = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(overlays=[]),
            user_id=ANON,
        ))
        assert edited["overlays"] == []

    def test_normalize_matches_the_renderers_cap(self, api):
        """
        What is stored is what gets sent to the model and to ffmpeg, so the
        12-item cap has to agree across all three.
        """
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Overlay Cap")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        edited = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(overlays=[
                {"start": i, "end": i + 1, "text": f"Line {i}"} for i in range(20)
            ]),
            user_id=ANON,
        ))
        assert len(edited["overlays"]) == 12
        assert edited["overlays"][-1]["text"] == "Line 11"

    def test_tone_and_duration_are_editable(self, api):
        """
        Both are generated fields the review step is expected to expose, and
        both seed the plan in the previous step.
        """
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Tone Duration")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        edited = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(tone="calm and direct", duration_seconds=30),
            user_id=ANON,
        ))
        assert edited["tone"] == "calm and direct"
        assert edited["duration_seconds"] == 30

    def test_duration_is_clamped_not_rejected(self, api):
        """
        An out-of-range duration is corrected rather than refused, because the
        founder picked it from a fixed list and the only way to get here is a
        stale value or a hand-written request.
        """
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Duration Clamp")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        edited = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(duration_seconds=9999),
            user_id=ANON,
        ))
        assert 5 <= edited["duration_seconds"] <= 60


class TestReadyGate:
    def _with_plan(self, api, monkeypatch, plan, name):
        _patch_plan(monkeypatch, api, plan)
        from models import GeneratePlanRequest
        profile = _approved_profile(api, name)
        template = _a_template(api)
        project = _a_project(api, profile, template)
        _run(api.generate_plan(project_id=project["id"],
                               payload=GeneratePlanRequest(), user_id=ANON))
        return project

    def test_clean_plan_becomes_ready(self, api, monkeypatch):
        project = self._with_plan(api, monkeypatch, FAKE_PLAN, "Ready Clean")
        result = _run(api.mark_project_ready(project_id=project["id"], user_id=ANON))
        assert result["status"] == "ready_for_generation"

    def test_banned_claim_blocks_ready(self, api, monkeypatch):
        project = self._with_plan(api, monkeypatch, BANNED_PLAN, "Ready Banned")
        with pytest.raises(HTTPException) as err:
            _run(api.mark_project_ready(project_id=project["id"], user_id=ANON))
        assert err.value.status_code == 409

    def test_blocking_claim_names_are_surfaced(self, api, monkeypatch):
        project = self._with_plan(api, monkeypatch, BANNED_PLAN, "Ready Names")
        with pytest.raises(HTTPException) as err:
            _run(api.mark_project_ready(project_id=project["id"], user_id=ANON))
        assert "cures anxiety" in str(err.value.detail)

    def test_ready_requires_a_script(self, api):
        profile = _approved_profile(api, "Ready No Script")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        with pytest.raises(HTTPException) as err:
            _run(api.mark_project_ready(project_id=project["id"], user_id=ANON))
        assert err.value.status_code == 400

    def test_ready_requires_a_template(self, api):
        from models import CreateStudioProjectRequest
        profile = _approved_profile(api, "Ready No Template")
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"]), user_id=ANON))
        with pytest.raises(HTTPException) as err:
            _run(api.mark_project_ready(project_id=project["id"], user_id=ANON))
        assert err.value.status_code == 400


class TestIsolation:
    def test_another_users_project_is_404(self, api):
        profile = _approved_profile(api, "Private Project")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        with pytest.raises(HTTPException) as err:
            _run(api.get_studio_project(project["id"], OTHER_USER))
        assert err.value.status_code == 404

    def test_another_user_cannot_edit(self, api):
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Private Edit")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        with pytest.raises(HTTPException) as err:
            _run(api.update_studio_project(
                project_id=project["id"],
                payload=UpdateStudioProjectRequest(script="hijack"), user_id=OTHER_USER))
        assert err.value.status_code == 404

    def test_missing_project_is_404(self, api):
        with pytest.raises(HTTPException) as err:
            _run(api.get_studio_project(str(uuid.uuid4()), ANON))
        assert err.value.status_code == 404
