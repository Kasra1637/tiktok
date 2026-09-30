"""
DB-backed tests for the Hook Template Library and content-angle endpoints.

Runs against a temporary SQLite file so it never touches the dev database.
No network: the AI paths (content-angle generation) are exercised only for
their approval gate, which rejects before any model call.
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
    """Import server against an isolated temp DB, initialised once."""
    tmpdir = tempfile.mkdtemp(prefix="tiktok-p3-")
    db_path = Path(tmpdir) / "test.db"

    os.environ["TURSO_DATABASE_URL"] = ""  # force local aiosqlite
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""  # anonymous auth

    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = db_path
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    async def _init():
        await server.init_db()

    asyncio.run(_init())
    server.TEST_ANON = ANON
    yield server
    sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


def _make_profile(server, user_id, name="Testly", category="Productivity"):
    from models import BrandProfileCreateRequest
    return _run(server.create_brand(
        payload=BrandProfileCreateRequest(
            brand_name=name,
            app_category=category,
            core_features=["Task timer", "Reminders"],
            icp_segments=["Busy students — need structure"],
        ),
        user_id=user_id,
    ))


class TestLibrarySeeding:
    def test_curated_templates_seeded_once(self, api):
        rows = _run(api._fetch_all(
            "SELECT id FROM hook_templates WHERE origin = 'curated'"
        ))
        assert len(rows) == 10

    def test_seed_is_idempotent(self, api):
        _run(api.init_db())
        _run(api.init_db())
        rows = _run(api._fetch_all(
            "SELECT id FROM hook_templates WHERE origin = 'curated'"
        ))
        assert len(rows) == 10

    def test_seeded_templates_are_shared_and_approved(self, api):
        rows = _run(api._fetch_all(
            "SELECT user_id, review_status, opening_structure FROM hook_templates "
            "WHERE origin = 'curated'"
        ))
        assert all(r["user_id"] == "system" for r in rows)
        assert all(r["review_status"] == "approved" for r in rows)
        assert all(r["opening_structure"] for r in rows)


class TestFaceOnlyMigration:
    """
    Face-only library: every curated template requires exactly
    ["character_reference"], and templates whose whole mechanic was real app
    footage are archived, not deleted. The literals alone cannot do either:
    seeding matches on name and skips anything already present, so a database
    seeded before the rule keeps stale requirements and retired templates
    forever. These tests drive init_db against rows that already exist, which
    is the only case that actually happens in production.
    """

    def test_fresh_database_seeds_face_only_requirements(self, api):
        import template_library as tl
        assert len(tl.CURATED_TEMPLATES) == 10
        for tpl in tl.CURATED_TEMPLATES:
            row = _run(api._fetch_one(
                "SELECT required_assets, archived FROM hook_templates "
                "WHERE name = ? AND origin = 'curated'",
                (tpl["name"],),
            ))
            assert row["required_assets"] == ["character_reference"], (tpl["name"], row)
            assert not row["archived"], tpl["name"]

    def test_migration_resets_a_stale_requirement(self, api):
        """
        Simulates the real upgrade: the row is already there with retired
        requirements, so the name-match seed skips it and only the migration
        can put it right. Ends in the clean state, so the shared fixture is
        left as found.
        """
        name = "Pain-Point Question"
        _run(api._execute(
            "UPDATE hook_templates SET required_assets = ? WHERE name = ? AND origin = 'curated'",
            ('["screenshot", "logo"]', name),
        ))
        stale = _run(api._fetch_one(
            "SELECT required_assets FROM hook_templates WHERE name = ?", (name,)))
        assert stale["required_assets"] == ["screenshot", "logo"]

        _run(api.init_db())

        fixed = _run(api._fetch_one(
            "SELECT required_assets FROM hook_templates WHERE name = ?", (name,)))
        assert fixed["required_assets"] == ["character_reference"], fixed

    def test_migration_leaves_an_already_correct_row_alone(self, api):
        name = "Pain-Point Question"
        before = _run(api._fetch_one(
            "SELECT required_assets, version FROM hook_templates WHERE name = ?", (name,)))
        _run(api.init_db())
        row = _run(api._fetch_one(
            "SELECT required_assets, version FROM hook_templates WHERE name = ?", (name,)))
        assert row["required_assets"] == ["character_reference"], row
        assert row["version"] == before["version"], row

    def test_migration_archives_retired_templates(self, api):
        """
        Simulates the real upgrade: the database was seeded when "Fast
        Tutorial" was still a library template. Deleting the literal cannot
        remove the row, so the migration archives it instead — the picker
        hides archived rows but existing projects keep their foreign keys.
        The row is removed afterwards so the shared fixture is left clean.
        """
        import uuid as _uuid
        _run(api._execute(
            "INSERT INTO hook_templates (id, name, category, origin, required_assets, "
            "archived, created_at, updated_at, user_id) VALUES (?, 'Fast Tutorial', "
            "'tutorial', 'curated', ?, 0, '', '', 'system')",
            (str(_uuid.uuid4()), '["screen_recording"]'),
        ))
        _run(api.init_db())
        row = _run(api._fetch_one(
            "SELECT archived FROM hook_templates "
            "WHERE name = 'Fast Tutorial' AND origin = 'curated'"))
        assert row["archived"] == 1, row
        assert "Fast Tutorial" not in [
            t["name"] for t in _run(api.list_templates(user_id=ANON))["templates"]]
        _run(api._execute(
            "DELETE FROM hook_templates WHERE name = 'Fast Tutorial' AND origin = 'curated'"))

    def test_backfill_never_touches_a_users_own_template(self, api):
        """
        Curated rows are shared and editable, so the backfill is keyed on
        origin='curated' and must not follow a same-named private copy.
        """
        import uuid as _uuid
        mine = str(_uuid.uuid4())
        _run(api._execute(
            "INSERT INTO hook_templates (id, name, category, origin, required_assets, "
            "created_at, updated_at, user_id) VALUES (?, ?, 'other', 'custom', ?, '', '', ?)",
            (mine, "Pain-Point Question", '["creator_photo"]', ANON),
        ))
        _run(api.init_db())
        row = _run(api._fetch_one(
            "SELECT required_assets FROM hook_templates WHERE id = ?", (mine,)))
        assert row["required_assets"] == ["creator_photo"], row
        _run(api._execute("DELETE FROM hook_templates WHERE id = ?", (mine,)))


    def test_legacy_bookmarks_backfilled_to_bookmark_origin(self, api):
        """Rows predating the library must not masquerade as curated."""
        _run(api._execute(
            """INSERT INTO hook_templates (id, name, category, created_at, updated_at, user_id)
               VALUES (?, 'Legacy saved hook', 'other', '', '', ?)""",
            (str(uuid.uuid4()), ANON),
        ))
        row = _run(api._fetch_one(
            "SELECT origin, review_status FROM hook_templates WHERE name = 'Legacy saved hook'"
        ))
        assert row["origin"] == "bookmark"
        # A bookmark is not a library template and must not be usable as one.
        public = api._public_library_template(row)
        assert public["is_library_template"] is False
        assert public["is_usable"] is False


class TestTemplateListing:
    def test_lists_curated_templates(self, api):
        # Scoped to origin='curated': other tests in this shared database
        # create custom rows, which the default listing correctly includes.
        result = _run(api.list_templates(origin="curated", user_id=ANON))
        assert len(result["templates"]) == 10

    def test_every_listed_template_is_usable(self, api):
        result = _run(api.list_templates(origin="curated", user_id=ANON))
        assert all(t["is_usable"] for t in result["templates"])

    def test_no_template_claims_proven(self, api):
        result = _run(api.list_templates(user_id=ANON))
        for t in result["templates"]:
            assert "proven" not in (t.get("evidence_note") or "").lower()

    def test_search_matches_name(self, api):
        result = _run(api.list_templates(q="mistakes", user_id=ANON))
        names = [t["name"] for t in result["templates"]]
        assert "Three Mistakes" in names

    def test_search_matches_opening_structure(self, api):
        result = _run(api.list_templates(q="open mid-motion", user_id=ANON))
        assert "Pattern Interrupt" in [t["name"] for t in result["templates"]]

    def test_category_filter(self, api):
        result = _run(api.list_templates(category="story", user_id=ANON))
        assert len(result["templates"]) == 2
        assert all(t["category"] == "story" for t in result["templates"])

    def test_objective_filter(self, api):
        result = _run(api.list_templates(objective="educate_viewers", user_id=ANON))
        assert result["templates"]
        assert all(t["objective"] == "educate_viewers" for t in result["templates"])

    def test_app_category_filter_matches_json_array(self, api):
        result = _run(api.list_templates(app_category="productivity", user_id=ANON))
        assert isinstance(result["templates"], list)

    def test_facets_expose_vocabularies(self, api):
        facets = _run(api.template_facets(user_id=ANON))
        assert len(facets["hook_categories"]) >= 12
        assert len(facets["objectives"]) == 10
        assert len(facets["content_angle_kinds"]) == 12
        assert facets["supported_durations"] == [10, 15, 20, 30]

    def test_unknown_category_filter_returns_empty_not_error(self, api):
        # Scoped to curated: "nonsense" normalizes to "other", which matches
        # other tests' leftover custom rows in this shared database.
        result = _run(api.list_templates(category="nonsense", origin="curated", user_id=ANON))
        assert result["templates"] == []


class TestFavorites:
    def test_favorite_toggles_on_and_off(self, api):
        tpl_id = _run(api.list_templates(user_id=ANON))["templates"][0]["id"]
        assert _run(api.toggle_template_favorite(template_id=tpl_id, user_id=ANON))["is_favorite"] is True
        assert _run(api.toggle_template_favorite(template_id=tpl_id, user_id=ANON))["is_favorite"] is False

    def test_favorites_only_filter(self, api):
        tpl_id = _run(api.list_templates(user_id=ANON))["templates"][1]["id"]
        _run(api.toggle_template_favorite(template_id=tpl_id, user_id=ANON))
        favs = _run(api.list_templates(favorites_only=True, user_id=ANON))
        assert [t["id"] for t in favs["templates"]] == [tpl_id]
        _run(api.toggle_template_favorite(template_id=tpl_id, user_id=ANON))

    def test_favorite_is_per_user_on_shared_template(self, api):
        """Curated templates are shared; one user's favorite must not leak."""
        tpl_id = _run(api.list_templates(user_id=ANON))["templates"][2]["id"]
        _run(api.toggle_template_favorite(template_id=tpl_id, user_id=ANON))
        mine = _run(api.get_template(template_id=tpl_id, user_id=ANON))
        theirs = _run(api.get_template(template_id=tpl_id, user_id=OTHER_USER))
        assert mine["is_favorite"] is True
        assert theirs["is_favorite"] is False
        _run(api.toggle_template_favorite(template_id=tpl_id, user_id=ANON))


class TestTemplateCrud:
    def test_create_requires_name_and_opening_structure(self, api):
        from models import CreateTemplateRequest
        with pytest.raises(HTTPException) as no_name:
            _run(api.create_template(
                payload=CreateTemplateRequest(name="  ", opening_structure="x"), user_id=ANON))
        assert no_name.value.status_code == 400
        with pytest.raises(HTTPException) as no_structure:
            _run(api.create_template(
                payload=CreateTemplateRequest(name="X", opening_structure=""), user_id=ANON))
        assert no_structure.value.status_code == 400

    def test_create_then_get(self, api):
        from models import CreateTemplateRequest
        made = _run(api.create_template(payload=CreateTemplateRequest(
            name="Internal QA Template", category="demo",
            opening_structure="Open on the finished result.",
            continuation_structure="Explain, then CTA.",
            required_assets=["screenshot", "logo"],
            default_duration=15,
            content_slots={"app_feature": "the timer"},
            example_preview="Open on the finished timer, then show two taps.",
        ), user_id=ANON))
        assert made["origin"] == "custom"
        assert made["is_usable"] is True
        assert made["required_assets"] == ["screenshot", "logo"]
        assert made["content_slots"] == {"app_feature": "the timer"}
        assert made["example_preview"] == "Open on the finished timer, then show two taps."

        fetched = _run(api.get_template(template_id=made["id"], user_id=ANON))
        assert fetched["name"] == "Internal QA Template"
        assert fetched["example_preview"] == made["example_preview"]

    def test_update_bumps_version(self, api):
        from models import CreateTemplateRequest, UpdateTemplateRequest
        made = _run(api.create_template(payload=CreateTemplateRequest(
            name="Versioned Template", opening_structure="A"), user_id=ANON))
        assert made["version"] == 1
        updated = _run(api.update_template(
            template_id=made["id"],
            payload=UpdateTemplateRequest(continuation_structure="B"),
            user_id=ANON,
        ))
        assert updated["version"] == 2
        assert updated["continuation_structure"] == "B"

    def test_update_supports_every_editable_field(self, api):
        from models import CreateTemplateRequest, UpdateTemplateRequest
        made = _run(api.create_template(payload=CreateTemplateRequest(
            name="Editable Template", opening_structure="A"), user_id=ANON))
        updated = _run(api.update_template(
            template_id=made["id"],
            payload=UpdateTemplateRequest(
                name="Edited Template",
                category="demo",
                app_categories=["productivity"],
                audiences=["busy parents"],
                objective="demonstrate_feature",
                opening_structure="Edited opening.",
                hook_seconds=4,
                continuation_structure="Edited continuation.",
                cta_pattern="Edited CTA.",
                visual_style="Edited visual.",
                camera_pacing="Edited pacing.",
                required_assets=["screenshot"],
                default_duration=15,
                content_slots={"app_feature": "timer"},
                example_preview="Edited example.",
                evidence_note="Edited evidence.",
                notes="Edited notes.",
            ),
            user_id=ANON,
        ))
        assert updated["version"] == 2
        assert updated["name"] == "Edited Template"
        assert updated["category"] == "demo"
        assert updated["app_categories"] == ["productivity"]
        assert updated["audiences"] == ["busy parents"]
        assert updated["objective"] == "demonstrate_feature"
        assert updated["hook_seconds"] == 4
        assert updated["required_assets"] == ["screenshot"]
        assert updated["default_duration"] == 15
        assert updated["content_slots"] == {"app_feature": "timer"}
        assert updated["example_preview"] == "Edited example."

    def test_update_rejects_empty_name(self, api):
        from models import CreateTemplateRequest, UpdateTemplateRequest
        made = _run(api.create_template(payload=CreateTemplateRequest(
            name="Keep Name", opening_structure="A"), user_id=ANON))
        with pytest.raises(HTTPException) as err:
            _run(api.update_template(
                template_id=made["id"], payload=UpdateTemplateRequest(name="   "), user_id=ANON))
        assert err.value.status_code == 400

    def test_duplicate_copies_structure_and_becomes_custom(self, api):
        from models import CreateTemplateRequest
        source = _run(api.create_template(payload=CreateTemplateRequest(
            name="Duplicated QA Template",
            opening_structure="Open on the finished result.",
            continuation_structure="Explain, then CTA.",
            content_slots={"app_feature": "the timer"},
            example_preview="Duplicated example.",
        ), user_id=ANON))
        copy = _run(api.duplicate_template(template_id=source["id"], user_id=ANON))
        assert copy["origin"] == "custom"
        assert copy["opening_structure"] == source["opening_structure"]
        assert copy["continuation_structure"] == source["continuation_structure"]
        assert copy["content_slots"] == source["content_slots"]
        assert copy["example_preview"] == "Duplicated example."
        assert copy["id"] != source["id"]
        assert copy["name"].endswith("(copy)")

    def test_archive_hides_and_include_archived_reveals(self, api):
        source = _run(api.list_templates(q="POV Scenario", user_id=ANON))["templates"][0]
        copy = _run(api.duplicate_template(template_id=source["id"], user_id=ANON))
        _run(api.archive_template(template_id=copy["id"], archived=True, user_id=ANON))

        default_ids = [t["id"] for t in _run(api.list_templates(user_id=ANON))["templates"]]
        assert copy["id"] not in default_ids

        all_ids = [t["id"] for t in
                   _run(api.list_templates(include_archived=True, user_id=ANON))["templates"]]
        assert copy["id"] in all_ids

        _run(api.archive_template(template_id=copy["id"], archived=False, user_id=ANON))
        default_ids = [t["id"] for t in _run(api.list_templates(user_id=ANON))["templates"]]
        assert copy["id"] in default_ids

    def test_archived_template_is_not_usable(self, api):
        source = _run(api.list_templates(q="Curiosity Gap", user_id=ANON))["templates"][0]
        copy = _run(api.duplicate_template(template_id=source["id"], user_id=ANON))
        _run(api.archive_template(template_id=copy["id"], archived=True, user_id=ANON))
        assert _run(api.get_template(template_id=copy["id"], user_id=ANON))["is_usable"] is False

    def test_publish_makes_draft_usable(self, api):
        from models import CreateTemplateRequest
        made = _run(api.create_template(payload=CreateTemplateRequest(
            name="Research Draft", opening_structure="A"), user_id=ANON))
        _run(api._execute(
            "UPDATE hook_templates SET review_status = 'draft' WHERE id = ?", (made["id"],)))
        assert _run(api.get_template(template_id=made["id"], user_id=ANON))["is_usable"] is False
        published = _run(api.publish_template(template_id=made["id"], user_id=ANON))
        assert published["review_status"] == "approved"
        assert published["is_usable"] is True

    def test_publish_rejects_template_without_structure(self, api):
        tpl_id = str(uuid.uuid4())
        _run(api._execute(
            """INSERT INTO hook_templates (id, name, category, origin, review_status,
               created_at, updated_at, user_id) VALUES (?, 'No Structure', 'other',
               'research_draft', 'draft', '', '', ?)""", (tpl_id, ANON)))
        with pytest.raises(HTTPException) as err:
            _run(api.publish_template(template_id=tpl_id, user_id=ANON))
        assert err.value.status_code == 400

    def test_missing_template_is_404(self, api):
        with pytest.raises(HTTPException) as err:
            _run(api.get_template(template_id=str(uuid.uuid4()), user_id=ANON))
        assert err.value.status_code == 404


class TestContentAngles:
    def test_manual_angle_requires_label_audience_and_problem(self, api):
        from models import CreateContentAngleRequest
        profile = _make_profile(api, ANON)
        with pytest.raises(HTTPException) as no_label:
            _run(api.create_manual_content_angle(
                profile_id=profile["id"],
                payload=CreateContentAngleRequest(label="", target_audience="a", user_problem="p"),
                user_id=ANON))
        assert no_label.value.status_code == 400
        with pytest.raises(HTTPException) as no_problem:
            _run(api.create_manual_content_angle(
                profile_id=profile["id"],
                payload=CreateContentAngleRequest(label="L", target_audience="a", user_problem=""),
                user_id=ANON))
        assert no_problem.value.status_code == 400

    def test_manual_angle_created_and_listed(self, api):
        from models import CreateContentAngleRequest
        profile = _make_profile(api, ANON)
        made = _run(api.create_manual_content_angle(
            profile_id=profile["id"],
            payload=CreateContentAngleRequest(
                kind="feature_demonstration", label="Show the timer",
                target_audience="People who lose track of time",
                user_problem="Cannot remember what to do next",
                app_feature="Task timer",
                claims_to_respect=["Do not claim iOS support"],
            ),
            user_id=ANON,
        ))
        assert made["kind"] == "feature_demonstration"
        assert made["claims_to_respect"] == ["Do not claim iOS support"]
        listed = _run(api.list_content_angles(profile_id=profile["id"], user_id=ANON))
        assert made["id"] in [a["id"] for a in listed["angles"]]

    def test_unknown_angle_kind_falls_back(self, api):
        from models import CreateContentAngleRequest
        profile = _make_profile(api, ANON)
        made = _run(api.create_manual_content_angle(
            profile_id=profile["id"],
            payload=CreateContentAngleRequest(
                kind="nonsense_kind", label="Fallback", target_audience="a", user_problem="p"),
            user_id=ANON,
        ))
        assert made["kind"] == "problem_solution"

    def test_angle_update_and_delete(self, api):
        from models import CreateContentAngleRequest, UpdateContentAngleRequest
        profile = _make_profile(api, ANON)
        made = _run(api.create_manual_content_angle(
            profile_id=profile["id"],
            payload=CreateContentAngleRequest(label="Editable", target_audience="a", user_problem="p"),
            user_id=ANON,
        ))
        updated = _run(api.update_content_angle(
            profile_id=profile["id"], angle_id=made["id"],
            payload=UpdateContentAngleRequest(label="Edited", desired_emotion="relief"),
            user_id=ANON,
        ))
        assert updated["label"] == "Edited"
        assert updated["desired_emotion"] == "relief"

        _run(api.delete_content_angle(profile_id=profile["id"], angle_id=made["id"], user_id=ANON))
        remaining = _run(api.list_content_angles(profile_id=profile["id"], user_id=ANON))
        assert made["id"] not in [a["id"] for a in remaining["angles"]]

    def test_angles_scoped_to_owning_profile(self, api):
        from models import CreateContentAngleRequest, UpdateContentAngleRequest
        p1 = _make_profile(api, ANON, name="App One")
        p2 = _make_profile(api, ANON, name="App Two")
        made = _run(api.create_manual_content_angle(
            profile_id=p1["id"],
            payload=CreateContentAngleRequest(label="Scoped", target_audience="a", user_problem="p"),
            user_id=ANON,
        ))
        # Same angle id under the wrong profile must not resolve.
        with pytest.raises(HTTPException) as err:
            _run(api.update_content_angle(
                profile_id=p2["id"], angle_id=made["id"],
                payload=UpdateContentAngleRequest(label="hijack"), user_id=ANON))
        assert err.value.status_code == 404

    def test_ai_generation_blocked_until_profile_approved(self, api):
        """Unverified research must not steer the video plan."""
        profile = _make_profile(api, ANON, name="Unapproved App")
        assert profile["status"] == "draft"
        with pytest.raises(HTTPException) as err:
            _run(api.generate_profile_content_angles(profile_id=profile["id"], user_id=ANON))
        assert err.value.status_code == 409

    def test_ai_generation_allowed_after_approval(self, api):
        """After approval the gate passes; the model call itself is the only
        thing left, so this asserts the gate no longer rejects."""
        profile = _make_profile(api, ANON, name="Approved App")
        _run(api.approve_app_profile(profile_id=profile["id"], payload={}, user_id=ANON))
        try:
            _run(api.generate_profile_content_angles(profile_id=profile["id"], user_id=ANON))
            gate = "passed"
        except Exception as e:
            gate = getattr(e, "status_code", "other")
            assert gate == 502, f"expected a model error, got {gate}"
        assert gate in ("passed", 502)


class TestRecommendations:
    def test_recommendations_returned_for_profile(self, api):
        profile = _make_profile(api, ANON, name="Reco App")
        result = _run(api.recommend_templates(profile_id=profile["id"], user_id=ANON))
        assert result["recommendations"]
        top = result["recommendations"][0]
        for key in ("template", "why_it_fits", "target_audience", "required_assets",
                    "suggested_duration", "limitations"):
            assert key in top

    def test_only_usable_templates_recommended(self, api):
        profile = _make_profile(api, ANON, name="Reco App 2")
        result = _run(api.recommend_templates(profile_id=profile["id"], user_id=ANON))
        assert all(r["template"]["is_usable"] for r in result["recommendations"])

    def test_archived_templates_never_recommended(self, api):
        source = _run(api.list_templates(q="Day in the Life", user_id=ANON))["templates"][0]
        copy = _run(api.duplicate_template(template_id=source["id"], user_id=ANON))
        _run(api.archive_template(template_id=copy["id"], archived=True, user_id=ANON))
        profile = _make_profile(api, ANON, name="Reco App 3")
        result = _run(api.recommend_templates(profile_id=profile["id"], user_id=ANON))
        assert copy["id"] not in [r["template"]["id"] for r in result["recommendations"]]

    def test_demonstration_angle_returns_face_only_templates(self, api):
        """
        The interface-led demo templates are gone, so a demonstration angle
        can no longer prefer them. What it must still guarantee: every
        recommendation is usable with nothing but a character reference, and
        no limitation names a retired upload.
        """
        from models import CreateContentAngleRequest
        profile = _make_profile(api, ANON, name="Reco App 4")
        angle = _run(api.create_manual_content_angle(
            profile_id=profile["id"],
            payload=CreateContentAngleRequest(
                kind="feature_demonstration", label="Demo",
                target_audience="Busy professionals", user_problem="No structure",
                app_feature="Task timer"),
            user_id=ANON,
        ))
        result = _run(api.recommend_templates(
            profile_id=profile["id"], angle_id=angle["id"],
            objective="demonstrate_feature", user_id=ANON))
        assert result["recommendations"]
        # Curated scope: other tests in this shared database create custom
        # rows with retired requirements, which recommendations correctly
        # include until those rows are edited under the face-only rule.
        curated = [r for r in result["recommendations"]
                   if r["template"].get("origin") == "curated"]
        assert curated
        for r in curated:
            assert r["required_assets"] == ["character_reference"], r
            assert not any(
                retired in lim
                for lim in r["limitations"]
                for retired in ("screenshot", "screen recording", "logo")
            ), r["limitations"]
        top = result["recommendations"][0]
        assert top["app_feature"] == "Task timer"

    def test_recommendations_sorted_by_score_desc(self, api):
        profile = _make_profile(api, ANON, name="Reco App 5")
        result = _run(api.recommend_templates(profile_id=profile["id"], user_id=ANON))
        scores = [r["score"] for r in result["recommendations"]]
        assert scores == sorted(scores, reverse=True)

    def test_limit_respected(self, api):
        profile = _make_profile(api, ANON, name="Reco App 6")
        result = _run(api.recommend_templates(profile_id=profile["id"], limit=3, user_id=ANON))
        assert len(result["recommendations"]) <= 3

    def test_unknown_angle_is_404(self, api):
        profile = _make_profile(api, ANON, name="Reco App 7")
        with pytest.raises(HTTPException) as err:
            _run(api.recommend_templates(
                profile_id=profile["id"], angle_id=str(uuid.uuid4()), user_id=ANON))
        assert err.value.status_code == 404


class TestFeedbackInfluence:
    def _target(self, api, profile):
        baseline = _run(api.recommend_templates(
            profile_id=profile["id"], limit=30, user_id=ANON
        ))
        target = baseline["recommendations"][0]
        return baseline, target["template"]["id"], target["score"]

    def _record(self, api, profile, template_id, event, reason="", signal=""):
        from models import FeedbackRequest
        return _run(api.record_feedback(
            FeedbackRequest(
                event=event,
                reason=reason,
                signal=signal,
                brand_profile_id=profile["id"],
                template_id=template_id,
            ),
            ANON,
        ))

    def _after(self, api, profile, template_id):
        after = _run(api.recommend_templates(
            profile_id=profile["id"], limit=30, user_id=ANON
        ))
        return next(r for r in after["recommendations"] if r["template"]["id"] == template_id)

    def test_repeated_template_rejection_lowers_score_and_names_it(self, api):
        profile = _make_profile(api, ANON, name="Feedback Penalty")
        _, template_id, before = self._target(api, profile)
        self._record(api, profile, template_id, "template_rejected", reason="hook_too_weak")
        self._record(api, profile, template_id, "template_rejected", reason="hook_too_weak")
        updated = self._after(api, profile, template_id)
        assert updated["score"] == pytest.approx(before - 4.0)
        assert updated["limitations"][0] == "Rejected or replaced 2 time(s) for this app."
        assert updated["feedback"]["explicit_rejections"] == 2
        assert updated["feedback"]["delta"] == pytest.approx(-4.0)

    def test_automatic_change_counts_less_than_an_explicit_rejection(self, api):
        profile = _make_profile(api, ANON, name="Feedback Signal")
        _, template_id, before = self._target(api, profile)
        self._record(api, profile, template_id, "template_rejected", signal="template_changed")
        updated = self._after(api, profile, template_id)
        assert updated["score"] == pytest.approx(before - 1.0)
        assert updated["feedback"]["automatic_changes"] == 1

    def test_success_marks_raise_score_and_name_it(self, api):
        profile = _make_profile(api, ANON, name="Feedback Success")
        _, template_id, before = self._target(api, profile)
        self._record(api, profile, template_id, "marked_successful", reason="good_performance")
        updated = self._after(api, profile, template_id)
        assert updated["score"] == pytest.approx(before + 2.0)
        assert updated["why_it_fits"][0] == "Approved or marked successful 1 time(s) for this app."

    def test_feedback_is_capped_and_template_scoped(self, api):
        import feedback as feedback_mod
        profile = _make_profile(api, ANON, name="Feedback Cap")
        _, template_id, _ = self._target(api, profile)
        rows = [
            {
                "event": "template_rejected",
                "signal": "",
                "reason": "hook_too_weak",
                "template_id": template_id,
            }
            for _ in range(10)
        ]
        rows.append({
            "event": "template_rejected",
            "signal": "",
            "reason": "hook_too_weak",
            "template_id": "another-template",
        })
        facts = feedback_mod.template_feedback_adjustment(rows, template_id)
        assert facts["explicit_rejections"] == 10
        assert facts["delta"] == pytest.approx(-6.0)

    def test_prompt_context_uses_counts_and_stated_reasons_only(self, api):
        import feedback as feedback_mod
        summary = feedback_mod.summarize_profile_feedback([
            {
                "event": "template_rejected",
                "signal": "",
                "reason": "hook_too_weak",
                "template_id": "template-one",
            },
            {
                "event": "video_regenerated",
                "signal": "regenerated",
                "reason": "",
                "template_id": "template-one",
            },
            {
                "event": "marked_successful",
                "signal": "",
                "reason": "good_performance",
                "template_id": "template-one",
            },
        ], "template-one")
        section = feedback_mod.build_profile_feedback_section(summary)
        assert "Template rejections: 1." in section
        assert "hook too weak (1)" in section
        assert "good performance (1)" in section
        assert "regenerated" not in section


class TestCrossUserIsolation:
    def test_another_users_custom_template_is_hidden(self, api):
        from models import CreateTemplateRequest
        mine = _run(api.create_template(payload=CreateTemplateRequest(
            name="Private QA Template", opening_structure="A"), user_id=OTHER_USER))
        theirs = _run(api.list_templates(user_id=ANON))
        assert mine["id"] not in [t["id"] for t in theirs["templates"]]
        with pytest.raises(HTTPException) as err:
            _run(api.get_template(template_id=mine["id"], user_id=ANON))
        assert err.value.status_code == 404

    def test_curated_templates_visible_to_everyone(self, api):
        listing = _run(api.list_templates(user_id=OTHER_USER))
        assert len(listing["templates"]) >= 10

    def test_another_users_profile_is_404(self, api):
        profile = _make_profile(api, ANON, name="Secret App")
        with pytest.raises(HTTPException) as err:
            _run(api.list_content_angles(profile_id=profile["id"], user_id=OTHER_USER))
        assert err.value.status_code == 404
        with pytest.raises(HTTPException) as err2:
            _run(api.recommend_templates(profile_id=profile["id"], user_id=OTHER_USER))
        assert err2.value.status_code == 404
