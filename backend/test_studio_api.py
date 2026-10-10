"""
DB-backed tests for studio projects: the approval gate, the template
requirement, claim-safety enforcement across edits, and version bookkeeping.

The AI plan call is mocked, so these tests assert our own orchestration rules
rather than model behaviour.
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
        brand_description="A focus timer for people who stall on starting.",
        core_features=kwargs.get("core_features", ["Task timer", "Reminders"]),
        usage_moments=["Starting a task they have been avoiding"],
        outcome_statements=[{
            "outcome": "Starting without stalling on setup",
            "who_feels_it": "people who stall on starting",
            "from_feature": "Task timer",
            "how_it_helps": "The timer starts in one tap so there is nothing to set up",
        }],
        claims_approved=kwargs.get("claims_approved", ["works offline"]),
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


def _attach_photo(api, profile, project):
    """Attach the founder's photograph to a project, as the upload endpoint does.

    A real 1x1 PNG on disk, because the identity resolver checks the file
    exists rather than trusting the row.
    """
    from models import now_iso
    face = Path(tempfile.mkdtemp(prefix="tiktok-studio-")) / "face.png"
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
        "UPDATE studio_projects SET assets = ? WHERE id = ?",
        (json.dumps([{
            "asset_id": asset_id, "kind": "character_reference",
            "label": "Founder face", "file_path": str(face),
        }]), project["id"])))
    return project


def _a_project(api, profile, template, with_character=True):
    """
    A project on an approved profile, with an objective already set.

    `with_character` attaches the founder's photograph, which every template
    requires and mark_project_ready now enforces. It defaults on because a
    fixture that omitted it would be exercising the missing-photo refusal
    instead of whatever the caller is actually testing — pass False to opt out.
    """
    from models import CreateStudioProjectRequest
    project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"],
        template_id=template["id"],
        objective="demonstrate_feature",
    ), user_id=ANON))
    if not with_character:
        return project
    _attach_photo(api, profile, project)
    return _run(api.get_studio_project(project["id"], user_id=ANON))


# A realistic plan the mocked generator returns.
#
# Exactly two sections, as the plan schema now demands: the hook, then the
# middle that develops it and stops at the moment the presenter reaches for
# their phone. `demo_brief` replaced `feature_emphasis` — the founder's note
# about what to record for their own demo — and it is deliberately never passed
# to a render. The retired `cta` key is still here so the tests below can assert
# it never reaches a prompt.
FAKE_PLAN = {
    "hook_line": "Stop writing empty pages",
    "script": "Taskly gives you one short prompt and a reminder. It works offline.",
    "beat_timeline": [
        {"start": 0, "end": 3, "label": "hook", "text": "Stop writing empty pages"},
        {"start": 3, "end": 15, "label": "middle", "text": "The blank page loses its grip"},
    ],
    "visual_direction": "Close on hands, then a real desk with clean space for overlays.",
    "demo_brief": "Record yourself tapping the timer once, hands only.",
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

    def test_a_project_from_the_previous_version_is_repaired_on_read(self, api):
        """
        A 20s / 5s project predates one-render generation and is unreachable now.

        It has to be repaired, and PERSISTED rather than only reported. If it
        were only reported, the founder would be shown 15s while the render read
        20 off the row and refused it at the single-pass ceiling — the two
        disagreeing in the one place they are about to pay.

        A duration is a whole number of seconds the studio can actually render,
        and a hook lands in 2-4s. Anything outside that was a target for a chain
        of separately-rendered segments, which no longer exists.
        """
        profile = _approved_profile(api, "Legacy Lengths")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        _run(api._execute(
            "UPDATE studio_projects SET duration_seconds = 20, hook_seconds = 5"
            " WHERE id = ?", (project["id"],)))

        reopened = _run(api.get_studio_project(project["id"], ANON))
        assert reopened["duration_seconds"] <= 15
        assert 2 <= reopened["hook_seconds"] <= 4

        # Stored, not just shown: the value the render reads off the row has to
        # be the value the founder was shown, or the two disagree in the one
        # place they are about to pay.
        stored = _run(api._fetch_one(
            "SELECT duration_seconds, hook_seconds FROM studio_projects WHERE id = ?",
            (project["id"],)))
        assert stored["duration_seconds"] == reopened["duration_seconds"]
        assert stored["hook_seconds"] == reopened["hook_seconds"]

    def test_a_current_project_is_not_rewritten_by_being_read(self, api):
        """
        The repair writes. It must not fire on a project that needs nothing.

        Otherwise every read would bump `updated_at` on every draft in the list,
        and a project list ordered by recency would be reordered by whoever
        opened it rather than by whoever last worked on it.
        """
        profile = _approved_profile(api, "Stable Reads")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        before = _run(api._fetch_one(
            "SELECT updated_at FROM studio_projects WHERE id = ?", (project["id"],)))
        _run(api.get_studio_project(project["id"], ANON))
        _run(api.list_studio_projects(user_id=ANON))
        after = _run(api._fetch_one(
            "SELECT updated_at FROM studio_projects WHERE id = ?", (project["id"],)))
        assert after["updated_at"] == before["updated_at"]

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
        """
        A length is one render, so the clamp is a single-pass clamp: 45s cannot
        become a longer video, it becomes the longest one the library supports.
        Every supported value passes through untouched.
        """
        import template_library as tl
        from models import CreateStudioProjectRequest
        profile = _approved_profile(api, "Clamp Duration")
        template = _a_template(api)
        longest = max(tl.SUPPORTED_DURATIONS)
        for requested, expected in ((7, tl.SUPPORTED_DURATIONS[0]), (45, longest), (12, 12)):
            project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
                brand_profile_id=profile["id"], template_id=template["id"],
                duration_seconds=requested), user_id=ANON))
            assert project["duration_seconds"] == expected, requested

    def test_a_length_over_one_pass_is_never_accepted(self, api):
        """
        The 30s the old tests asked for is not merely clamped here — there is no
        product surface that accepts it at all, because a video is one render and
        a request longer than a single pass produces a broken file rather than a
        longer one. Pinning the ceiling directly means a future widening of
        SUPPORTED_DURATIONS past what a model can actually do fails loudly.
        """
        import template_library as tl
        import video_providers
        assert max(tl.SUPPORTED_DURATIONS) <= video_providers.capability()["max_duration"]

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
        # demo_brief replaced cta as the plan's stored note. It is the founder's
        # brief for the demo they record, so it is stored and editable — and,
        # deliberately, never passed to a render.
        assert result["demo_brief"] == FAKE_PLAN["demo_brief"]
        assert result["cta"] is None
        # Two sections, exactly: the hook and the middle. No overlays: a fresh
        # plan always clears the column, because burned-in captions are gone
        # and nothing renders them anymore.
        assert [b["label"] for b in result["beat_timeline"]] == ["hook", "middle"]
        assert result["overlays"] == []
        assert result["script_version"] == 1

    def test_duration_cannot_be_changed_once_a_plan_exists(self, api, monkeypatch):
        """
        The plan's beat timeline is built for the length the plan was generated
        at, and every beat is clamped to it. Patching duration_seconds afterwards
        therefore produced a timeline that no longer adds up to the stated
        runtime — with the shot timeline displayed read-only, so nothing on
        screen could say so.

        12s and 15s, because those are two different supported lengths now: with
        both ends clamped to a 15s ceiling, 20 and 30 were the same request and
        this test would have passed for the wrong reason.
        """
        _patch_plan(monkeypatch, api, FAKE_PLAN)
        from models import GeneratePlanRequest, UpdateStudioProjectRequest
        profile = _approved_profile(api, "Locked Length")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        _run(api.generate_plan(project_id=project["id"],
                               payload=GeneratePlanRequest(duration_seconds=12),
                               user_id=ANON))
        with pytest.raises(HTTPException) as err:
            _run(api.update_studio_project(
                project_id=project["id"],
                payload=UpdateStudioProjectRequest(duration_seconds=15),
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
                               payload=GeneratePlanRequest(duration_seconds=12),
                               user_id=ANON))
        result = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(duration_seconds=12),
            user_id=ANON))
        assert result["duration_seconds"] == 12

    def test_duration_is_free_before_a_plan_exists(self, api):
        """The length is chosen on the Audience & goal step, which is earlier."""
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Pre Plan Length")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        result = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(duration_seconds=12),
            user_id=ANON))
        assert result["duration_seconds"] == 12

    def test_regenerating_the_plan_at_a_new_length_rewrites_the_timeline(
        self, api, monkeypatch
    ):
        """The sanctioned route: the plan writes the length with its beats."""
        import template_library
        _patch_plan(monkeypatch, api, FAKE_PLAN)
        from models import GeneratePlanRequest
        profile = _approved_profile(api, "Regen Length")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        _run(api.generate_plan(project_id=project["id"],
                               payload=GeneratePlanRequest(duration_seconds=12),
                               user_id=ANON))
        again = _run(api.generate_plan(project_id=project["id"],
                                       payload=GeneratePlanRequest(duration_seconds=10),
                                       user_id=ANON))
        assert again["duration_seconds"] == 10
        assert again["script_version"] == 2
        # And a length one render cannot produce is never honoured verbatim, so a
        # project saved with a 30s target from before this change still
        # regenerates to something the model can actually produce.
        assert again["duration_seconds"] in template_library.SUPPORTED_DURATIONS
        assert again["duration_seconds"] <= 15

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

    def test_unchanged_resend_does_not_bump_script_version(self, api):
        """The wizard's background draft sync resends tone/objective/template
        on every selection change. Bumping on key presence alone minted phantom
        "Plan v1" versions with blank fields: Review then saw script_version >
        0, concluded a plan existed, and never auto-generated — a blank form
        only a manual regenerate could recover.
        """
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "No Phantom Version")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        assert project["script_version"] == 0
        for _ in range(3):
            edited = _run(api.update_studio_project(
                project_id=project["id"],
                payload=UpdateStudioProjectRequest(
                    content_angle_id="", template_id=template["id"],
                    objective="demonstrate_feature", tone="",
                ),
                user_id=ANON,
            ))
            assert edited["script_version"] == 0
            assert edited["hook_line"] in (None, "")
            assert edited["script"] in (None, "")

    def test_changed_tone_still_bumps_script_version(self, api):
        """Value semantics, not presence: the same key that is ignored
        unchanged must still bump when its value actually changes.
        """
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Tone Change")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        edited = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(tone="calm"),
            user_id=ANON,
        ))
        assert edited["tone"] == "calm"
        assert edited["script_version"] == 1
        # And resending that same value is a no-op again.
        again = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(tone="calm"),
            user_id=ANON,
        ))
        assert again["script_version"] == 1

    def test_every_editable_field_is_writable(self, api):
        """
        The review step promises that every generated field is editable, so the
        list is driven off STUDIO_EDITABLE_FIELDS rather than hard-coded here: a
        field added to the editable set and forgotten in this test would be
        silent, and a field removed from the set but still sent here would be a
        silent no-op that reads as "saved".

        `demo_brief` replaced `cta` and `feature_emphasis` in that list, and the
        request model had to be told too — it was still declaring the two retired
        fields, so the one field that tells the founder what to record for their
        own demo could not be corrected at all.
        """
        from models import (
            STUDIO_EDITABLE_FIELDS, STUDIO_TEXT_FIELDS, UpdateStudioProjectRequest,
        )
        profile = _approved_profile(api, "Edit Fields")
        template = _a_template(api)
        project = _a_project(api, profile, template)

        # Every editable text field, sent in one payload.
        payload = UpdateStudioProjectRequest(
            hook_line="New hook", script="New script.",
            demo_brief="Record the timer tap yourself.",
            visual_direction="New direction", voice_direction="Calm",
            sound_direction="Ambient",
            tone="playful", audience="Busy parents",
        )
        edited = _run(api.update_studio_project(
            project_id=project["id"], payload=payload, user_id=ANON,
        ))
        # Nothing in the editable set may be a field the request model does not
        # declare, or it is a dead input: accepted, stored nowhere, reported as
        # saved. demo_brief was exactly that for a while.
        for field in STUDIO_TEXT_FIELDS:
            assert field in STUDIO_EDITABLE_FIELDS, field
            assert field in UpdateStudioProjectRequest.model_fields, field
        assert edited["hook_line"] == "New hook"
        assert edited["script"] == "New script."
        assert edited["demo_brief"] == "Record the timer tap yourself."
        assert edited["visual_direction"] == "New direction"
        assert edited["voice_direction"] == "Calm"
        assert edited["sound_direction"] == "Ambient"
        assert edited["tone"] == "playful"
        assert edited["audience"] == "Busy parents"

        # And the retired trio is not an editable field any more, so a client
        # still sending one gets a 200 that changed nothing — which is exactly
        # why it was removed from the model rather than left to be filtered.
        assert "cta" not in STUDIO_EDITABLE_FIELDS
        assert "feature_emphasis" not in STUDIO_EDITABLE_FIELDS
        assert "overlays" not in STUDIO_EDITABLE_FIELDS
        assert "cta" not in UpdateStudioProjectRequest.model_fields
        assert "feature_emphasis" not in UpdateStudioProjectRequest.model_fields
        assert "overlays" not in UpdateStudioProjectRequest.model_fields

        # The JSON and template fields take their own normalization.
        edited = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(
                beat_timeline=[{"start": 0, "end": 3, "label": "hook", "text": "Hi"}],
            ),
            user_id=ANON,
        ))
        assert edited["beat_timeline"][0]["text"] == "Hi"

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


class TestOverlaysAreRetired:
    """
    Burned-in captions are gone: the model is never asked for on-screen text,
    the column is cleared on every fresh plan, and the edit endpoint no longer
    accepts the field. An old client still sending it gets a 200 that changed
    nothing — and, crucially, no phantom version, since presence alone never
    bumps (see the no-phantom-version tests).
    """

    def test_sending_overlays_changes_nothing_and_bumps_nothing(self, api):
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Overlay Retired")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        assert project["script_version"] == 0
        edited = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest.model_construct(
                _fields_set={"overlays"},
                overlays=[{"start": 0, "end": 2, "text": "Hi"}],
            ),
            user_id=ANON,
        ))
        assert edited["overlays"] == []
        assert edited["script_version"] == 0

    def test_a_fresh_plan_clears_legacy_overlay_text(self, api, monkeypatch):
        from models import GeneratePlanRequest
        profile = _approved_profile(api, "Overlay Cleared")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        _run(api._execute(
            "UPDATE studio_projects SET overlays = ? WHERE id = ?",
            ('[{"start": 0, "end": 2, "text": "legacy line"}]', project["id"]),
        ))
        _patch_plan(monkeypatch, api, FAKE_PLAN)
        result = _run(api.generate_plan(project_id=project["id"],
                                        payload=GeneratePlanRequest(), user_id=ANON))
        assert result["overlays"] == []


    def test_tone_and_duration_are_editable(self, api):
        """
        Both are generated fields the review step is expected to expose, and
        both seed the plan in the previous step.

        12s rather than the 30s this used to send, because there is no 30s
        piece any more: a video is one render.
        """
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Tone Duration")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        edited = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(tone="calm and direct", duration_seconds=12),
            user_id=ANON,
        ))
        assert edited["tone"] == "calm and direct"
        assert edited["duration_seconds"] == 12

    def test_duration_is_clamped_not_rejected(self, api):
        """
        An out-of-range duration is corrected rather than refused, because the
        founder picked it from a fixed list and the only way to get here is a
        stale value or a hand-written request.

        Corrected to a real piece, not merely to something plausible: 9999s
        clamps to the longest single pass the library supports, because
        submitting it as a render length produces a broken file rather than a
        long video.
        """
        import template_library
        from models import UpdateStudioProjectRequest
        profile = _approved_profile(api, "Duration Clamp")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        edited = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(duration_seconds=9999),
            user_id=ANON,
        ))
        assert edited["duration_seconds"] == max(template_library.SUPPORTED_DURATIONS)


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

    def test_building_a_strategy_does_not_un_ready_the_project(self, api, monkeypatch):
        """A strategy build must not demote a project the founder already approved.

        generate_project_strategy re-derives from the approved plan and changes
        nothing the founder read, so it used to write status='draft' -- which
        re-enabled the "Mark ready for generation" button sitting on the
        previous step, bouncing anyone who built their strategy back a step to
        re-approve a project they had not touched.
        """
        project = self._with_plan(api, monkeypatch, FAKE_PLAN, "Ready Then Strategy")
        _run(api.mark_project_ready(project_id=project["id"], user_id=ANON))
        from models import GenerateStrategyRequest

        # Exercise the real endpoint with the model call replaced, the same way
        # _patch_plan does for the plan: the point under test is the status the
        # endpoint writes, not what the model returns.
        async def fake_generate_video_strategy(**kwargs):
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "You do not have a focus problem.",
                "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "cta_strategy": "c",
                "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                "segments": [{"index": 0, "role": "hook", "seconds": 5,
                              "goal": "g", "script": "You do not have a focus problem.",
                              "action": "a"}],
                "continuity_contract": {
                    "established": ["kitchen"],
                    "must_not_change": ["shirt"],
                    "do_not_repeat": ["the opening line"],
                },
            }
        monkeypatch.setattr(api, "generate_video_strategy", fake_generate_video_strategy)

        after = _run(api.generate_project_strategy(
            project_id=project["id"], payload=GenerateStrategyRequest(), user_id=ANON))
        assert after["status"] == "ready_for_generation"

    def test_a_content_edit_un_readies_an_approved_project(self, api, monkeypatch):
        """
        Editing an approved project must withdraw the approval.

        update_studio_project used to leave status alone, so a founder who had
        marked a project ready could rewrite the hook line, save, and spend
        again immediately -- and because the status never moved off
        ready_for_generation, the "Mark ready for generation" button stayed
        disabled, so there was no way to review the revision at all. The
        approval was for the PREVIOUS text.
        """
        from models import UpdateStudioProjectRequest, StudioGenerationRequest
        project = self._with_plan(api, monkeypatch, FAKE_PLAN, "Ready Then Edited")
        _run(api.mark_project_ready(project_id=project["id"], user_id=ANON))
        assert _run(api.get_studio_project(project["id"], ANON))["status"] == "ready_for_generation"

        after = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(hook_line="A completely different hook"),
            user_id=ANON,
        ))
        assert after["status"] == "draft"
        # And the spend gate follows the status, rather than only the button.
        with pytest.raises(HTTPException) as err:
            _run(api.submit_project_generation(
                project_id=project["id"], payload=StudioGenerationRequest(), user_id=ANON))
        assert err.value.status_code == 409

    def test_a_preference_edit_leaves_readiness_alone(self, api, monkeypatch):
        """
        Only a CONTENT edit withdraws approval.

        The same endpoint carries preferences (hook length, extend intent).
        Bumping script_version on those made a project the founder had already
        approved look rewritten, which is the mirror image of the bug above --
        and re-enabling the review gate for a change nobody read would teach
        founders the gate is noise.
        """
        from models import UpdateStudioProjectRequest
        project = self._with_plan(api, monkeypatch, FAKE_PLAN, "Ready Then Preference")
        _run(api.mark_project_ready(project_id=project["id"], user_id=ANON))

        after = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(hook_seconds=4),
            user_id=ANON,
        ))
        assert after["status"] == "ready_for_generation"

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

    def test_ready_requires_an_objective(self, api, monkeypatch):
        """
        The objective is what the video is FOR, and the wizard required it
        client-side only.

        A direct caller could approve and spend on a project with no stated
        objective, and the plan fell back to whatever the template scored. The
        gate belongs on the one review step that gates every later spend.
        """
        _patch_plan(monkeypatch, api, FAKE_PLAN)
        from models import CreateStudioProjectRequest, GeneratePlanRequest
        profile = _approved_profile(api, "Ready No Objective")
        template = _a_template(api)
        project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
            brand_profile_id=profile["id"], template_id=template["id"]), user_id=ANON))
        # The photograph is attached so the objective is the ONLY thing wrong:
        # two unmet gates would otherwise race, and this test would keep
        # passing or failing on whichever the server happened to check first.
        _attach_photo(api, profile, project)
        _run(api.generate_plan(project_id=project["id"],
                               payload=GeneratePlanRequest(), user_id=ANON))
        with pytest.raises(HTTPException) as err:
            _run(api.mark_project_ready(project_id=project["id"], user_id=ANON))
        assert err.value.status_code == 400
        assert "Audience & goal" in str(err.value.detail)

    def test_ready_requires_a_photograph(self, api, monkeypatch):
        """
        Marking ready is what enables the Generate button, so it is the last
        point at which a missing photograph can be caught before the founder
        decides to spend.

        The generate endpoint has always refused this case. Refusing there was
        not enough: the project was approved, the button lit up, and the 409
        only arrived on click — which reads as the app breaking rather than a
        rule not yet met. The message has to name the step that fixes it.
        """
        _patch_plan(monkeypatch, api, FAKE_PLAN)
        from models import GeneratePlanRequest
        profile = _approved_profile(api, "Ready No Photo")
        template = _a_template(api)
        project = _a_project(api, profile, template, with_character=False)
        _run(api.generate_plan(project_id=project["id"],
                               payload=GeneratePlanRequest(), user_id=ANON))
        with pytest.raises(HTTPException) as err:
            _run(api.mark_project_ready(project_id=project["id"], user_id=ANON))
        assert err.value.status_code == 400
        detail = str(err.value.detail)
        assert "character reference" in detail
        assert "looks nothing like you" in detail
        # Names the step, so the founder is not left hunting for an upload that
        # used to live on a step called "Assets" and no longer exists.
        assert "Template & photo" in detail

        # Still a draft, so the button never lights up in the first place.
        fresh = _run(api.get_studio_project(project["id"], user_id=ANON))
        assert fresh["status"] != "ready_for_generation"

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




class _StrategyCapture:
    """
    Capture the strategy prompt generate_video_strategy actually builds.

    Asserting on source text was the first attempt and it is the wrong
    instrument: the prompt is assembled from adjacent string literals, so a
    phrase that reads as one sentence in the file is split across lines and a
    grep for it finds nothing. Capturing the built prompt is the only version
    of this assertion that means anything.
    """

    def __init__(self, monkeypatch):
        import ai_service
        self.captured = {}
        captured = self.captured

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["prompt"] = prompt
            captured["system"] = system_message
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["t"], "hook_concept": "c",
                "hook_line": "h", "hook_promise": "p", "hook_action": "a",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "b",
                "scene": {"environment": "kitchen"},
                "performance": {"movement": "still"},
                # Exactly two sections, as the schema asks for. `cta_strategy`
                # and `continuity_contract` are gone and no longer named in the
                # prompt, so this reply leaves them out entirely.
                "segments": [
                    {"index": 0, "role": "hook", "seconds": 3,
                     "goal": "g", "script": "s", "action": "a"},
                    {"index": 1, "role": "middle", "seconds": 12,
                     "goal": "g2", "script": "s2", "action": "a2"},
                ],
            }

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)

    def run(self, *, profile_overrides=None, template_extra=None):
        import ai_service
        profile = {"brand_name": "ShiftLog"}
        profile.update(profile_overrides or {})
        template = {"name": "T", "content_slots": {}}
        template.update(template_extra or {})
        asyncio.run(ai_service.generate_video_strategy(
            profile=profile,
            template=template,
            angle=None, objective="address_user_problem",
            hook_seconds=5, total_duration=20, tone="", brand_voice="",
            profile_feedback={},
        ))
        return self.captured["prompt"]


class TestViewerObjections:
    """
    The middle's material.

    There used to be seven continuation beats and no argument for any of them,
    so the middle of every video was another feature restated. An objection is a
    turn the story can take, and it needs a current alternative to turn against,
    not just a complaint to acknowledge.

    With one middle instead of a chain, the shape of the obligation changed too:
    an objection is no longer a beat of its own but something woven into the
    single section that exists. What must not come back is the model ignoring
    the field, or answering it with a promise.
    """

    OBJECTIONS = [{
        "objection": "It is just another subscription",
        "what_they_do_now": "Three habit trackers I already pay for",
        "honest_answer": "One that costs nothing and works offline",
    }]

    def test_the_triples_reach_the_strategy_prompt(self, monkeypatch):
        prompt = _StrategyCapture(monkeypatch).run(profile_overrides={"viewer_objections": self.OBJECTIONS})
        assert "It is just another subscription" in prompt
        assert "Three habit trackers I already pay for" in prompt
        assert "One that costs nothing and works offline" in prompt

    def test_they_are_obliged_to_become_beats(self, monkeypatch):
        """
        Was `..._to_become_beats`, asserting one beat per objection and no two
        objections in a beat. Two sections cannot carry one beat each, so the
        directive is now: weave the ones this audience would actually have into
        the middle, answered by the situation on screen rather than by a feature
        list.

        The obligation is still the point — a list the model may ignore
        reproduces the problem the field was added to solve.
        """
        prompt = _StrategyCapture(monkeypatch).run(profile_overrides={"viewer_objections": self.OBJECTIONS})
        assert "viewer_objections are what the middle has to answer" in prompt
        assert "Weave the objections that matter into the middle" in prompt
        # Answered by showing, not by listing.
        assert "answered by the situation on screen rather than by a list of features" in prompt
        # And it says what to leave out rather than demanding all of them.
        assert "Two sections cannot carry every objection" in prompt

    def test_an_answer_may_not_be_a_promise(self, monkeypatch):
        """
        The tempting failure: an objection the model wants to close with a
        guarantee. That is exactly the copy the claim checker blocks, so the
        prompt has to forbid it before it is written.
        """
        prompt = _StrategyCapture(monkeypatch).run(profile_overrides={"viewer_objections": self.OBJECTIONS})
        assert "may not promise a result" in prompt
        assert "leave it out rather than inventing one" in prompt

    def test_the_prompt_states_the_cost_of_an_empty_profile(self, monkeypatch):
        """
        Without objections, the middle has nothing to argue with and becomes a
        feature restatement. The prompt has to say so, or the model quietly
        falls back to listing features again.
        """
        prompt = _StrategyCapture(monkeypatch).run()
        assert '"viewer_objections": []' in prompt


class TestViewerObjectionNormalization:
    """
    Normalization drops an objection that has no answer rather than keeping it
    half-built: material the model will improvise a resolution for is worse than
    a short middle, because there is no third section to absorb the improvisation.
    """

    def test_a_complete_triple_survives(self):
        import ai_service
        result = {"viewer_objections": [dict(TestViewerObjections.OBJECTIONS[0])]}
        ai_service._normalize_objection_list(result)
        kept = result["viewer_objections"]
        assert len(kept) == 1
        assert kept[0]["what_they_do_now"].startswith("Three habit")

    def test_an_objection_without_an_answer_is_dropped(self):
        import ai_service
        result = {"viewer_objections": [
            {"objection": "Too expensive", "what_they_do_now": "Nothing"},
            {"objection": "Takes too long", "what_they_do_now": "By hand",
             "honest_answer": "Under a minute once set up"},
        ]}
        ai_service._normalize_objection_list(result)
        assert [o["objection"] for o in result["viewer_objections"]] == ["Takes too long"]

    def test_a_missing_current_alternative_is_kept(self):
        """
        Only the answer is load-bearing. "Doing nothing" is a real alternative,
        so the founder may have left it blank rather than typing it.
        """
        import ai_service
        result = {"viewer_objections": [
            {"objection": "Too expensive", "honest_answer": "Free tier"},
        ]}
        ai_service._normalize_objection_list(result)
        assert result["viewer_objections"][0]["honest_answer"] == "Free tier"
        assert result["viewer_objections"][0]["what_they_do_now"] == ""

    def test_malformed_input_becomes_an_empty_list(self):
        import ai_service
        for raw in (None, "not json", {"a": 1}, 42, [1, 2, 3]):
            result = {"viewer_objections": raw}
            ai_service._normalize_objection_list(result)
            assert result["viewer_objections"] == [], raw

    def test_a_json_string_is_parsed(self):
        """
        The stored column can arrive as a raw string through a path that has not
        been through row_to_dict, and str()-ing a list of dicts would produce
        unreadable reprs in the prompt.
        """
        import ai_service
        result = {"viewer_objections": json.dumps(TestViewerObjections.OBJECTIONS)}
        ai_service._normalize_objection_list(result)
        assert len(result["viewer_objections"]) == 1

    def test_it_is_capped(self):
        import ai_service
        result = {"viewer_objections": [
            {"objection": f"o{i}", "honest_answer": "a"} for i in range(20)
        ]}
        ai_service._normalize_objection_list(result)
        assert len(result["viewer_objections"]) == 6

    def test_the_phrase_list_normalizer_leaves_it_alone(self):
        """
        The bug this guards: viewer_objections was listed among the phrase lists,
        so the generic loop str()'d each dict into a repr and the objection
        normalizer then dropped every one as malformed. The field came out empty
        100% of the time and "Why they would not download" never rendered.

        Every other test here calls _normalize_objection_list directly, which is
        why they all passed while the real path was broken. This one asserts the
        key is genuinely absent from the list that does the damage.
        """
        import ai_service
        assert "viewer_objections" not in ai_service.APP_PROFILE_LIST_KEYS

    def test_survives_the_real_normalization_sequence(self):
        """
        Runs the two normalizers in the order analyze_app_profile runs them,
        rather than only the objection normalizer in isolation.
        """
        import ai_service

        result = {"viewer_objections": [dict(TestViewerObjections.OBJECTIONS[0])]}
        for key in ai_service.APP_PROFILE_LIST_KEYS:
            val = result.get(key)
            if isinstance(val, str):
                val = [val] if val.strip() else []
            if not isinstance(val, list):
                val = []
            result[key] = [str(v).strip() for v in val if str(v).strip()][:8]
        ai_service._normalize_objection_list(result)

        kept = result["viewer_objections"]
        assert len(kept) == 1
        assert kept[0]["objection"]
        assert kept[0]["honest_answer"]
        assert isinstance(kept[0], dict)


class TestObjectionFieldSurvivesASave:
    """
    PATCH /app-profiles/{id} 500'd on any save that carried viewer_objections,
    because the field was in neither the editable list nor the encoder, so a raw
    Python list was bound into a TEXT column. The editor always sends the key, so
    every save on an existing profile failed. No test touched this endpoint.
    """

    def test_update_parts_encodes_it_as_json(self):
        import server
        triples = [{
            "objection": "Just another subscription",
            "what_they_do_now": "Three habit trackers I already pay for",
            "honest_answer": "One app that costs nothing and works offline",
        }]
        clauses, values = server._brand_update_parts({"viewer_objections": triples})
        assert clauses == ["viewer_objections = ?"]
        # Bound into a TEXT column, so it has to arrive as a JSON string.
        assert isinstance(values[0], str)
        decoded = json.loads(values[0])
        assert decoded[0]["objection"] == "Just another subscription"
        assert decoded[0]["honest_answer"].startswith("One app")

    def test_update_parts_does_not_flatten_the_dicts(self):
        """
        _normalize_str_list turns a dict into its "label"/"name" key, and these
        triples have neither, so it would store three empty strings.
        """
        import server
        triples = [{
            "objection": "Too many apps",
            "what_they_do_now": "Notes",
            "honest_answer": "It replaces them",
        }]
        _clauses, values = server._brand_update_parts({"viewer_objections": triples})
        assert "Too many apps" in values[0]

    def test_update_parts_accepts_a_json_string(self):
        """The editor round-trips this field through text, so both shapes arrive."""
        import server
        triples = [{
            "objection": "Not sure it works",
            "what_they_do_now": "Asking a friend",
            "honest_answer": "Here is what it does",
        }]
        _clauses, values = server._brand_update_parts({
            "viewer_objections": json.dumps(triples),
        })
        assert json.loads(values[0])[0]["honest_answer"] == "Here is what it does"

    def test_update_parts_drops_a_half_built_triple(self):
        """An objection with no honest reply gives the arc nothing to aim at."""
        import server
        _clauses, values = server._brand_update_parts({"viewer_objections": [
            {"objection": "Too expensive", "what_they_do_now": "Nothing"},
        ]})
        assert json.loads(values[0]) == []

    def test_phrase_lists_still_encode_as_before(self):
        """The new branch must not have changed the existing list fields."""
        import server
        _clauses, values = server._brand_update_parts({
            "core_features": "Timer, Journal",
        })
        assert json.loads(values[0]) == ["Timer", "Journal"]

    def test_it_is_editable(self):
        """Otherwise the field is filtered out before it ever reaches the SQL."""
        from models import (
            APP_PROFILE_EDITABLE_FIELDS, APP_PROFILE_LIST_FIELDS,
            APP_PROFILE_OBJECT_LIST_FIELDS,
        )
        assert "viewer_objections" in APP_PROFILE_EDITABLE_FIELDS
        assert "viewer_objections" in APP_PROFILE_OBJECT_LIST_FIELDS
        assert "viewer_objections" not in APP_PROFILE_LIST_FIELDS


class TestOutcomeStatementsSurviveASave:
    """
    Same save-path coverage as the objection triples: outcome_statements is a
    second list-of-objects field, so it needs its own normalizer on the way
    in, JSON encoding on the way to the TEXT column, and membership in the
    editable tuple — or the editor's key is silently dropped and the approval
    gate can never pass for a hand-built profile.
    """

    STATEMENTS = [{
        "outcome": "Fall asleep without checking your phone",
        "who_feels_it": "night-time scrollers",
        "from_feature": "Sleep timer",
        "how_it_helps": "The wind-down starts itself so there is no reason to pick the phone back up",
    }]

    def test_extraction_keeps_linked_entries(self):
        import ai_service
        result = {"outcome_statements": [dict(self.STATEMENTS[0])]}
        ai_service._normalize_outcome_statements(result)
        assert len(result["outcome_statements"]) == 1
        assert result["outcome_statements"][0]["from_feature"] == "Sleep timer"

    def test_extraction_drops_entries_with_no_source_feature(self):
        """
        An outcome nobody can trace to a feature leaves every later prompt
        guessing the mapping, which is how pitches decay into feature lists.
        """
        import ai_service
        result = {"outcome_statements": [
            {"outcome": "Sleep better", "who_feels_it": "everyone"},
        ]}
        ai_service._normalize_outcome_statements(result)
        assert result["outcome_statements"] == []

    def test_extraction_is_capped(self):
        import ai_service
        result = {"outcome_statements": [
            {"outcome": f"o{i}", "from_feature": "Sleep timer"} for i in range(20)
        ]}
        ai_service._normalize_outcome_statements(result)
        assert len(result["outcome_statements"]) == 6

    def test_the_phrase_list_normalizer_leaves_it_alone(self):
        """
        The viewer_objections bug, guarded for the second object list: if this
        key ever lands in APP_PROFILE_LIST_KEYS, the generic loop str()'s each
        dict and the entry normalizer drops every one as malformed.
        """
        import ai_service
        assert "outcome_statements" not in ai_service.APP_PROFILE_LIST_KEYS

    def test_update_parts_encodes_it_as_json(self):
        import server
        _clauses, values = server._brand_update_parts(
            {"outcome_statements": self.STATEMENTS})
        assert isinstance(values[0], str)
        decoded = json.loads(values[0])
        assert decoded[0]["outcome"] == "Fall asleep without checking your phone"
        assert decoded[0]["from_feature"] == "Sleep timer"

    def test_update_parts_accepts_a_json_string(self):
        """The editor round-trips this field through text, so both shapes arrive."""
        import server
        _clauses, values = server._brand_update_parts(
            {"outcome_statements": json.dumps(self.STATEMENTS)})
        assert json.loads(values[0])[0]["how_it_helps"].startswith("The wind-down")

    def test_update_parts_drops_a_half_built_entry(self):
        import server
        _clauses, values = server._brand_update_parts({"outcome_statements": [
            {"outcome": "Sleep better", "who_feels_it": "everyone"},
        ]})
        assert json.loads(values[0]) == []

    def test_it_is_editable(self):
        from models import (
            APP_PROFILE_EDITABLE_FIELDS, APP_PROFILE_LIST_FIELDS,
            APP_PROFILE_OBJECT_LIST_FIELDS,
        )
        assert "outcome_statements" in APP_PROFILE_EDITABLE_FIELDS
        assert "outcome_statements" in APP_PROFILE_OBJECT_LIST_FIELDS
        assert "outcome_statements" not in APP_PROFILE_LIST_FIELDS

    def test_approval_refuses_a_profile_with_no_outcome_statement(self, api):
        """
        The strategy pitches benefits instead of listing features, so a
        profile with no linked outcome would approve straight into the
        fallback path. The gate names the gap like the others.
        """
        from models import BrandProfileCreateRequest, ApproveAppProfileRequest
        profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name="No Outcomes",
            brand_description="A focus timer for people who stall on starting.",
            core_features=["Task timer", "Reminders"],
            usage_moments=["Starting a task they have been avoiding"],
        ), user_id=ANON))
        with pytest.raises(HTTPException) as err:
            _run(api.approve_app_profile(
                profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
        assert err.value.status_code == 409
        assert "outcome" in str(err.value.detail).lower()

    def test_approval_passes_with_one_linked_statement(self, api):
        profile = _approved_profile(api, "Outcomes OK")
        assert profile["status"] == "approved"
        assert profile["outcome_statements"][0]["from_feature"] == "Task timer"


class TestPlanPromptSeedsVoiceDefault:
    """The plan's voice_direction is what the founder reads, edits and trusts."""

    def _capture(self, monkeypatch):
        import ai_service
        captured = {}

        # generate_creative_plan routes through the shared _chat_json helper,
        # so the seam is the context manager: replace AsyncClient with a stub
        # whose post() records the request body and returns a well-formed
        # completion.
        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self_inner):
                return {"choices": [{"message": {"content": json.dumps({
                    "hook_line": "h", "script": "s", "beat_timeline": [],
                    "visual_direction": "v",
                    "demo_brief": "Record yourself tapping the timer once.",
                    "overlays": [], "voice_direction": "vd",
                    "sound_direction": "sd",
                })}}]}

        class _AsyncClient:
            def __init__(self_inner, *a, **k):
                pass

            async def __aenter__(self_inner):
                return self_inner

            async def __aexit__(self_inner, *exc):
                return False

            async def post(self_inner, url, **kwargs):
                captured["messages"] = (kwargs.get("json") or {}).get("messages")
                return _Resp()

        monkeypatch.setattr(ai_service.httpx, "AsyncClient", _AsyncClient)
        return captured

    def test_plan_prompt_seeds_energetic_voice_default(self, monkeypatch):
        """
        Same no-knob problem one step earlier: the plan's voice_direction is
        what the founder sees and edits on Review, and what the strategy model
        later copies into voice_delivery — so the seed has to ask for fast and
        energetic here, or flat delivery is baked in two steps before the render.
        """
        import ai_service
        captured = self._capture(monkeypatch)
        asyncio.run(ai_service.generate_creative_plan(
            profile={"brand_name": "ShiftLog"},
            template={"name": "T"},
            objective="address_user_problem",
            duration_seconds=20,
        ))
        prompt = json.dumps(captured["messages"])
        assert "fast, upbeat, high-energy delivery" in prompt


class TestSpokenBudgetReachesThePlanPrompt:
    """
    The plan prompt states, in characters, exactly what the middle can speak.

    The failure this closes: the plan schema asked for "the full spoken script"
    with no length, so the model routinely wrote 238+ characters for a 7s
    middle (a 140-character budget at the current pace), and the founder first
    learned the script was too long at the render gate — after approving it. The gate itself does
    not need a test here (TestSpokenWordsGate covers it); what needs asserting
    is that the request is now sized to the budget that gate enforces, at its
    cause.
    """

    def _capture(self, monkeypatch):
        import ai_service
        captured = {}

        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"choices": [{"message": {"content": json.dumps({
                    "hook_line": "h", "script": "s", "beat_timeline": [],
                    "visual_direction": "v",
                    "demo_brief": "Record yourself tapping the timer once.",
                    "overlays": [], "voice_direction": "vd",
                    "sound_direction": "sd",
                })}}]}

        class _AsyncClient:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *exc):
                return False

            async def post(self, url, **kwargs):
                captured["messages"] = (kwargs.get("json") or {}).get("messages")
                return _Resp()

        monkeypatch.setattr(ai_service.httpx, "AsyncClient", _AsyncClient)
        return captured

    def test_the_prompt_carries_the_middle_budget_for_the_real_seconds(self, monkeypatch):
        import ai_service
        captured = self._capture(monkeypatch)
        asyncio.run(ai_service.generate_creative_plan(
            profile={"brand_name": "ShiftLog"},
            template={"name": "T", "hook_seconds": 3},
            objective="address_user_problem",
            duration_seconds=10,  # 7s middle — the shape that produced the error
        ))
        prompt = json.dumps(captured["messages"])
        # The exact numbers the render gate would derive downstream (7s middle
        # at 20 chars/sec = 140, and the 3s hook floors at 60). If the prompt and
        # the gate ever disagree again, this fails first.
        assert "SPOKEN BUDGET" in prompt
        assert "140 characters for the rest of the script" in prompt
        assert "first 3s" in prompt
        assert "60 characters for the hook line" in prompt
        # Fill-target, not under-fill: the model must use the budget, or the
        # video stretches a short script across the full duration (slow delivery).
        assert "CLOSE TO each ceiling" in prompt
        assert "room to spare" not in prompt
        assert "render is refused" in prompt

    def test_the_budget_tracks_the_template_declared_hook(self, monkeypatch):
        """A 3s hook on a 15s piece squeezes the middle to 12s / 240 chars at the current pace."""
        import ai_service
        captured = self._capture(monkeypatch)
        asyncio.run(ai_service.generate_creative_plan(
            profile={"brand_name": "ShiftLog"},
            template={"name": "T", "hook_seconds": 3},
            objective="address_user_problem",
            duration_seconds=15,
        ))
        prompt = json.dumps(captured["messages"])
        assert "240 characters for the rest of the script" in prompt
        # And the two ceilings must never collide: the hook budget is on the
        # hook line, the middle budget on the remainder after it.
        assert "60 characters for the hook line" in prompt
        assert "CLOSE TO each ceiling" in prompt
        assert "payoff sentence as the last thing said inside it" in prompt

    def test_the_strategy_prompt_carries_the_same_spoken_budget(self, monkeypatch):
        """The strategy prompt sizes its section scripts to the same ceilings.

        _StrategyCapture runs hook_seconds=5, total_duration=20, so the middle
        is 15s: 100 chars of hook dialogue and 300 of middle script at the
        20 chars/sec pace. Same fill-target wording as the plan prompt.
        """
        prompt = _StrategyCapture(monkeypatch).run()
        assert "SPOKEN BUDGET" in prompt
        assert "100 characters of hook dialogue" in prompt
        assert "300 characters of middle script" in prompt
        assert "CLOSE TO each ceiling" in prompt
        assert "room to spare" not in prompt


class TestTrendEvidenceReachesTheStrategy:
    """The gap this closes: virality_score reached no generation prompt."""

    def test_the_section_is_present_when_the_template_has_evidence(self, monkeypatch):
        import ai_service
        prompt = _StrategyCapture(monkeypatch).run(template_extra={
            "trend_evidence": {
                "has_signal": True, "sample_size": 12,
                "median_view_band": "100K-1M",
                "median_engagement_band": "typical (5-10%)",
                "recency_band": "under 48h",
            },
        })
        assert "WHAT OPENINGS OF THIS SHAPE HAVE ACTUALLY CARRIED" in prompt
        assert "Across 12 public openings" in prompt
        assert "100K-1M" in prompt

    def test_a_json_string_column_is_parsed(self, monkeypatch):
        """The stored column arrives as text through paths that skip row_to_dict."""
        import ai_service
        prompt = _StrategyCapture(monkeypatch).run(template_extra={
            "trend_evidence": (
                '{"has_signal": true, "sample_size": 8, "median_view_band": "10K-100K",'
                ' "median_engagement_band": "high (10%+ of views)",'
                ' "recency_band": "under 48h"}'
            ),
        })
        assert "Across 8 public openings" in prompt
        assert "10K-100K" in prompt

    def test_no_section_without_evidence(self, monkeypatch):
        """
        A heading with nothing under it implies a search was run and found
        nothing, which is a different claim from never having looked.
        """
        import ai_service
        prompt = _StrategyCapture(monkeypatch).run()
        assert "WHAT OPENINGS OF THIS SHAPE HAVE ACTUALLY CARRIED\n" not in prompt
        assert "median one had" not in prompt

    def test_the_directive_forbids_chasing_the_number(self, monkeypatch):
        """
        The failure this invites: told a shape carried 100K views, a model asked
        to beat the number will pad the hook or promise a result. The prompt has
        to say the evidence biases the shape, not the target.
        """
        import ai_service
        prompt = _StrategyCapture(monkeypatch).run(template_extra={
            "trend_evidence": {
                "has_signal": True, "sample_size": 12,
                "median_view_band": "1M+", "median_engagement_band": "high (10%+ of views)",
                "recency_band": "under 48h",
            },
        })
        assert "Do not chase the number itself" in prompt
        assert "do not pad the hook to fill time" in prompt
        assert "do not" in prompt and "state or imply a view" in prompt


class TestPlanArrivalClamp:
    """
    A generated script is measured against the middle's seconds before it is
    stored.

    The prompt has always stated this budget and nothing checked the answer, so
    an over-length plan was stored whole: the founder read it on Review with
    nothing wrong on screen, and the first sign of it was the render gate
    refusing with a fix the studio did not offer. These pin that the plan now
    arrives renderable.
    """

    def _over_budget_plan(self):
        # Well past any budget: a 15s piece is a 12s middle, 240 characters at
        # 20 chars/sec. The margin below is deliberately wide -- the fixture has
        # to stay over-budget if the pace is ever retuned again.
        return {
            **FAKE_PLAN,
            "hook_line": "Stop writing empty pages",
            "script": (
                "Stop writing empty pages. Taskly gives you one short prompt and a "
                "reminder. It works offline, and it never nags you about the streak. "
                "The blank page loses its grip by the end of the first sentence, and "
                "that is the whole point of the thing you are looking at right now. "
                "The timer starts when you do, and stops when you stop."
            ),
        }

    def test_an_over_budget_plan_is_stored_already_trimmed(self, api, monkeypatch):
        import ai_service
        plan = self._over_budget_plan()
        _patch_plan(monkeypatch, api, plan)
        from models import GeneratePlanRequest
        profile = _approved_profile(api, "Clamp Store")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        result = _run(api.generate_plan(project_id=project["id"],
                                        payload=GeneratePlanRequest(), user_id=ANON))
        assert result["plan_trim"]["dropped_chars"] > 0
        # The stored script is measured, not merely reported.
        part = ai_service.partition_spoken_words(
            result, result["hook_seconds"] or 3, result["duration_seconds"] or 0
        )
        assert part["dropped_chars"] == 0
        assert len(result["script"]) < len(plan["script"])

    def test_a_clamped_plan_passes_the_render_gate(self, api, monkeypatch):
        """The whole point: no dead end. What the clamp stored must be what the
        gate would have accepted, or the founder is back to a 409."""
        import server
        _patch_plan(monkeypatch, api, self._over_budget_plan())
        from models import GeneratePlanRequest
        profile = _approved_profile(api, "Clamp Gate")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        result = _run(api.generate_plan(project_id=project["id"],
                                        payload=GeneratePlanRequest(), user_id=ANON))
        assert server._require_spoken_words_fit({
            "hook_line": result["hook_line"],
            "script": result["script"],
            "hook_seconds": result["hook_seconds"],
            "duration_seconds": result["duration_seconds"],
            "strategy": {"segments": [{"role": "hook"}, {"role": "middle"}]},
        }) == {}
        # And nothing is reported as un-spoken on a freshly generated plan.
        assert result["spoken_overflow"] == {}

    def test_the_hook_line_is_stored_once_not_repeated_in_the_script(self, api, monkeypatch):
        """The hook line lives in its own column, so the script must not open
        with a second copy of it.

        The model is asked for the whole piece because it is writing the whole
        piece, and the hook line is written once. Review shows the two fields
        side by side, so a stored copy made the founder read the same sentence
        twice and left them unable to tell what the middle would actually say.
        """
        _patch_plan(monkeypatch, api, {
            **FAKE_PLAN,
            "hook_line": "Stop writing empty pages",
            "script": "Stop writing empty pages. Taskly gives you one short prompt.",
        })
        from models import GeneratePlanRequest
        profile = _approved_profile(api, "Clamp Once")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        result = _run(api.generate_plan(project_id=project["id"],
                                        payload=GeneratePlanRequest(), user_id=ANON))
        assert result["hook_line"] == "Stop writing empty pages"
        assert "empty pages" not in result["script"]
        assert result["script"] == "Taskly gives you one short prompt."

    def test_a_paraphrased_hook_is_also_stored_once(self, api, monkeypatch):
        """The same rule when the model introduces the hook before saying it."""
        _patch_plan(monkeypatch, api, {
            **FAKE_PLAN,
            "hook_line": "Stop writing empty pages",
            "script": "So, stop writing empty pages. Taskly gives you one prompt.",
        })
        from models import GeneratePlanRequest
        profile = _approved_profile(api, "Clamp Paraphrase")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        result = _run(api.generate_plan(project_id=project["id"],
                                        payload=GeneratePlanRequest(), user_id=ANON))
        assert result["script"] == "Taskly gives you one prompt."

    def test_the_hook_is_still_spoken_once_after_being_deduplicated(self, api, monkeypatch):
        """Deduplication must not cost the video its opening line.

        The hook moves from the head of the script to its own column, and
        bind_spoken_words is what puts it back into the rendered strategy. If
        that binding stopped reading hook_line, the video would open on the
        middle instead.
        """
        import ai_service
        _patch_plan(monkeypatch, api, {
            **FAKE_PLAN,
            "hook_line": "Stop writing empty pages",
            "script": "Stop writing empty pages. Taskly gives you one short prompt.",
        })
        from models import GeneratePlanRequest
        profile = _approved_profile(api, "Clamp Spoken")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        result = _run(api.generate_plan(project_id=project["id"],
                                        payload=GeneratePlanRequest(), user_id=ANON))
        strategy = {"segments": [
            {"role": "hook", "script": "model hook draft"},
            {"role": "middle", "script": "model middle draft"},
        ]}
        bound, _ = ai_service.bind_spoken_words(
            strategy,
            {"hook_line": result["hook_line"], "script": result["script"]},
            result["hook_seconds"] or 3,
            result["duration_seconds"] or 0,
        )
        assert bound["segments"][0]["script"] == "Stop writing empty pages"
        assert bound["segments"][1]["script"] == "Taskly gives you one short prompt."

    def test_a_fitting_plan_records_no_trim(self, api, monkeypatch):
        _patch_plan(monkeypatch, api, FAKE_PLAN)
        from models import GeneratePlanRequest
        profile = _approved_profile(api, "Clamp Clean")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        result = _run(api.generate_plan(project_id=project["id"],
                                        payload=GeneratePlanRequest(), user_id=ANON))
        assert result["plan_trim"] == {}
        assert result["script"] == FAKE_PLAN["script"]

    def test_regenerating_clears_a_previous_trim(self, api, monkeypatch):
        """The note is about the plan in hand. After a regenerate the plan is a
        different one, and leaving the old count would tell the founder their
        fresh script is short when it may not be."""
        from models import GeneratePlanRequest
        profile = _approved_profile(api, "Clamp Reset")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        _patch_plan(monkeypatch, api, self._over_budget_plan())
        first = _run(api.generate_plan(project_id=project["id"],
                                       payload=GeneratePlanRequest(), user_id=ANON))
        assert first["plan_trim"]["dropped_chars"] > 0
        _patch_plan(monkeypatch, api, FAKE_PLAN)
        second = _run(api.generate_plan(project_id=project["id"],
                                        payload=GeneratePlanRequest(), user_id=ANON))
        assert second["plan_trim"] == {}

    def test_a_founder_edit_cannot_erase_the_record_of_a_trim(self, api, monkeypatch):
        from models import GeneratePlanRequest, UpdateStudioProjectRequest
        _patch_plan(monkeypatch, api, self._over_budget_plan())
        profile = _approved_profile(api, "Clamp Edit")
        template = _a_template(api)
        project = _a_project(api, profile, template)
        _run(api.generate_plan(project_id=project["id"],
                               payload=GeneratePlanRequest(), user_id=ANON))
        after = _run(api.update_studio_project(
            project_id=project["id"],
            payload=UpdateStudioProjectRequest(script="Shortened by hand."),
            user_id=ANON))
        assert after["plan_trim"]["dropped_chars"] > 0


class TestSpokenWordsGate:
    """The render refuses words the founder cannot actually speak.

    Two separate refusals share this gate. The framing check (a feature
    inventory in the spoken lines) lives in claim_safety and reaches the
    render through the recomputed verdict; the overflow check below is the
    second half — approved words that do not fit the middle's seconds would
    otherwise be silently dropped from the provider prompt, and the tail is
    usually the payoff sentence.
    """

    def _project(self, script, **overrides):
        row = {
            "hook_line": "Do you know what triggers your emotions?",
            "script": script,
            "hook_seconds": 3,
            "duration_seconds": 10,
            "strategy": {
                "hook_line": "Do you know what triggers your emotions?",
                "segments": [
                    {"role": "hook", "script": "Do you know what triggers your emotions?"},
                    {"role": "middle", "script": script},
                ],
            },
        }
        row.update(overrides)
        return row

    def test_a_fitting_script_carries_no_overflow(self):
        import server
        out = server._public_project(self._project(
            "Most evenings blur together. Yours ends with one sentence written down."
        ))
        assert out["spoken_overflow"] == {}
        # The Review step shows this partition and trims to it, so it has to be
        # the bound middle text rather than a second implementation of the rule.
        assert out["spoken_middle"] == "Most evenings blur together. Yours ends with one sentence written down."

    def test_an_overlong_script_is_reported_with_its_budget(self):
        import server
        out = server._public_project(self._project(
            "First sentence that fits. " + "x" * 500 + " Final payoff sentence."
        ))
        overflow = out["spoken_overflow"]
        assert overflow["dropped_chars"] > 0
        assert overflow["budget"] == 140  # 7s middle at the current 20 chars/sec pace
        assert overflow["middle_seconds"] == 7
        # The trim target: exactly the kept prefix, so trimming to it and
        # saving is stable — rebinding the trimmed script yields the same words.
        assert out["spoken_middle"] == "First sentence that fits."

    def test_overflow_refuses_the_render_with_the_fix_named(self):
        import server
        with pytest.raises(Exception) as exc:
            server._require_spoken_words_fit(self._project(
                "First sentence that fits. " + "x" * 500 + " Final payoff sentence."
            ))
        assert getattr(exc.value, "status_code", None) == 409
        assert "do not fit" in str(exc.value.detail)
        # The old wording pointed at a Review button that does not exist. A
        # generated plan is trimmed on arrival, so the honest fix for a
        # hand-edited script is to shorten it or regenerate.
        assert "Regenerate the plan" in str(exc.value.detail)
        assert "rebuild the strategy" in str(exc.value.detail)

    def test_a_fitting_script_passes_the_gate(self):
        import server
        overflow = server._require_spoken_words_fit(self._project(
            "Most evenings blur together. Yours ends with one sentence written down."
        ))
        assert overflow == {}

    def test_a_feature_inventory_refuses_the_render(self):
        """The user-visible half of the guarantee: the spoken words of a real
        posted video were a feature list, so the gate must fire on that shape
        through the recomputed verdict, not just in a unit test of patterns."""
        import server
        project = self._project(
            "With Vocolens, you can track your emotional states and uncover "
            "your triggers through voice journaling and mood tracking."
        )
        report = server._safety_report_for(project, {})
        assert report["passed"] is False
        with pytest.raises(Exception) as exc:
            server._require_claims_clear(project, {})
        assert getattr(exc.value, "status_code", None) == 409
