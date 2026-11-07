"""
The Location is the single source of truth for the place (ADR 0090).

Three rules are pinned here:

1. Editing the plan's Location rewrites the strategy's place-bearing lines in
   the same save — the scene's location becomes the canonical text, any legacy
   environment/background/setting copies are overwritten, and direction lines
   lose the clauses that contradict it — and the strategy stays current, so
   the render is not blocked by the version number the same save just
   reconciled.
2. Before any render, the same rewrite runs again as an audit; direction
   lines are patched, and spoken words that still name another place refuse
   the render with the field named.
3. The opening's first beat must be a clearly visible movement inside the
   first 1-2 seconds: the strategy prompt requires it and the render prompt
   states it in both budget modes.
"""
import asyncio
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import ai_service
import angle_scene
import generation_planning as gp

ANON = "anonymous"

# Place-only on purpose: the split of lighting/time out of a Location is
# covered by its own tests (backend/tests/test_scene_consistency.py), and these
# tests are about the Location propagation itself.
LOCATION = "A park bench by the pond"


def _run(coro):
    return asyncio.run(coro)


def desk_strategy():
    """An indoor strategy the founder is about to move outdoors."""
    return {
        "hook_concept": "She sits at her desk at home, scrolling, frustrated",
        "hook_action": "Sits at the desk and slams the phone down",
        "hook_line": "I keep losing track of my day",
        "hook_promise": "A day you can see",
        "hook_dialogue": "Delivered while seated",
        "strategy_summary": "Stuck at the desk, a person finds the app",
        "audience_problem": "Days vanish at the desk",
        "messaging_pillars": ["See the day at a glance"],
        "primary_feature": "one-tap logging",
        "desired_outcome": "A visible day",
        "mechanism_beat": "One tap logs it",
        "payoff_beat": "Never lose a day again",
        "differentiation_beat": "No forms",
        "scene": {
            "location": "Home office desk",
            "lighting": "Warm lamp light",
            "color_palette": "Warm browns",
            "character_positioning": "Seated at the desk",
            "wardrobe": "Blue t-shirt",
            "props": "A mug",
            "visual_style": "Natural phone footage",
            "camera_angle": "Use STARTING SHOT",
            "framing": "",
        },
        "performance": {"movement": "Stands up from the desk", "voice_delivery": "fast, upbeat"},
        "segments": [
            {"index": 0, "role": "hook", "seconds": 3, "goal": "stop the scroll",
             "action": "Sits on the couch and looks up", "script": "I keep losing track of my day"},
            {"index": 1, "role": "middle", "seconds": 9, "goal": "develop the hook",
             "action": "Walks outside and reaches for the phone", "script": "Then I found one"},
        ],
        "camera_setup": "handheld",
        "camera_beat": {"direction": "left", "gesture": "a small head tilt"},
    }


class TestReconcileLocation:
    def test_the_place_field_becomes_the_location(self):
        out = angle_scene.reconcile_location(desk_strategy(), LOCATION)
        assert out["strategy"]["scene"]["location"] == LOCATION
        assert "Location" in out["changed"]

    def test_legacy_place_fields_are_overwritten_too(self):
        # Old rows split the place across environment/background/setting, and
        # ai_service.merge_legacy_location folds those back together for
        # consumers — so leaving one behind would resurrect the old place.
        strategy = desk_strategy()
        strategy["scene"].update({
            "environment": "Home office desk",
            "background": "Bookshelf and window",
            "setting": "Late evening at home",
        })
        out = angle_scene.reconcile_location(strategy, LOCATION)
        scene = out["strategy"]["scene"]
        assert scene["location"] == LOCATION
        assert scene["environment"] == LOCATION
        assert scene["background"] == LOCATION
        assert scene["setting"] == LOCATION
        assert {"Location", "Environment", "Background", "Setting"} <= set(out["changed"])

    def test_direction_lines_lose_only_the_conflicting_clauses(self):
        out = angle_scene.reconcile_location(desk_strategy(), LOCATION)
        # "She sits at her desk at home" names an indoor place and is dropped;
        # the rest of the line is kept verbatim.
        assert out["strategy"]["hook_concept"] == "scrolling, frustrated"
        assert out["strategy"]["scene"]["lighting"] == ""
        assert out["strategy"]["performance"]["movement"] == ""
        assert out["strategy"]["scene"]["character_positioning"] == ""
        # A line that already agrees is untouched: "Walks outside" is outdoor,
        # the same place the Location names.
        assert out["strategy"]["segments"][1]["action"] == "Walks outside and reaches for the phone"
        assert "Middle — what they do" not in out["changed"]

    def test_preserved_fields_are_never_touched(self):
        original = desk_strategy()
        out = angle_scene.reconcile_location(original, LOCATION)
        for key in ("hook_line", "hook_dialogue", "strategy_summary", "audience_problem",
                    "desired_outcome", "mechanism_beat", "payoff_beat",
                    "differentiation_beat"):
            assert out["strategy"][key] == original[key]
        scene = out["strategy"]["scene"]
        assert scene["wardrobe"] == original["scene"]["wardrobe"]
        assert scene["props"] == original["scene"]["props"]
        assert scene["visual_style"] == original["scene"]["visual_style"]
        assert out["strategy"]["performance"]["voice_delivery"] == "fast, upbeat"
        # The input is never mutated.
        assert original["scene"]["location"] == "Home office desk"

    def test_thorough_also_rewrites_prompt_prose(self):
        out = angle_scene.reconcile_location(desk_strategy(), LOCATION, thorough=True)
        assert out["strategy"]["strategy_summary"] == "a person finds the app"
        assert "Strategy summary" in out["changed"]
        # Non-thorough (the save) leaves the prose alone.
        saved = angle_scene.reconcile_location(desk_strategy(), LOCATION)
        assert saved["strategy"]["strategy_summary"] == "Stuck at the desk, a person finds the app"

    def test_spoken_words_are_blocked_not_rewritten(self):
        strategy = desk_strategy()
        strategy["hook_line"] = "I hate being stuck in my living room"
        strategy["segments"][1]["script"] = "So I stayed in bed all morning"
        out = angle_scene.reconcile_location(strategy, LOCATION, thorough=True)
        fields = {b["field"] for b in out["blocked"]}
        assert "Hook line" in fields
        assert "Middle — spoken words" in fields
        assert out["strategy"]["hook_line"] == "I hate being stuck in my living room"
        assert out["strategy"]["segments"][1]["script"] == "So I stayed in bed all morning"

    def test_a_matching_spoken_line_is_never_blocked(self):
        out = angle_scene.reconcile_location(desk_strategy(), LOCATION)
        assert out["blocked"] == []

    def test_an_empty_location_changes_nothing(self):
        out = angle_scene.reconcile_location(desk_strategy(), "")
        assert out == {"strategy": desk_strategy(), "changed": [], "blocked": []}

    def test_no_scene_block_still_reports_spoken_conflicts(self):
        strategy = {"hook_line": "I hate being stuck in my living room"}
        out = angle_scene.reconcile_location(strategy, LOCATION)
        assert out["strategy"] == {"hook_line": "I hate being stuck in my living room"}
        assert [b["field"] for b in out["blocked"]] == ["Hook line"]


class TestPromptCarriesTheLocation:
    def test_the_lock_skips_the_place_field_when_the_location_exists(self):
        lock = gp.character_scene_lock(desk_strategy(), LOCATION)
        assert "Location: Home office desk" not in lock
        assert "wardrobe: Blue t-shirt" in lock

    def test_without_a_location_the_lock_states_the_place_as_before(self):
        lock = gp.character_scene_lock(desk_strategy())
        assert "Location: Home office desk" in lock

    def test_the_render_prompt_names_the_place_once_from_the_location(self):
        prompt = gp._assemble_prompt(
            desk_strategy(), {}, {}, 12, [],
            plan={"location": LOCATION, "hook_seconds": 3},
        )
        assert "WHERE THIS HAPPENS" in prompt
        assert LOCATION in prompt
        # The strategy's own place copy is not restated next to it.
        assert "Location: Home office desk" not in prompt

    def test_the_legacy_visual_direction_still_names_the_place(self):
        prompt = gp._assemble_prompt(
            desk_strategy(), {}, {}, 12, [],
            plan={"visual_direction": LOCATION, "hook_seconds": 3},
        )
        assert LOCATION in prompt

    def test_an_angle_row_is_checked_against_the_location(self):
        # The stored angle is the third place carrier: its opening moment must
        # agree with the plan Location, or the render would carry two places.
        angle = {
            "hook_promise": "A desk in a dark bedroom at midnight",
            "user_problem": "Days vanish at the desk",
        }
        with pytest.raises(ValueError, match="stopped before it cost anything"):
            gp.build_segment_prompt(
                strategy=desk_strategy(), profile={}, template={}, duration=12,
                assets=[], plan={"location": LOCATION, "hook_seconds": 3},
                angle=angle,
            )

    def test_a_content_angle_id_alone_never_crashes_the_prompt(self):
        # Production 2026-11-07: every render with a Location raised NameError
        # because the builder tried to resolve the stored row itself. The row
        # now arrives as a parameter; an absent row is simply nothing to
        # compare, never a crash on an otherwise ready render.
        strategy = desk_strategy()
        strategy["content_angle_id"] = "angle-1"
        prompt = gp.build_segment_prompt(
            strategy=strategy, profile={}, template={}, duration=12,
            assets=[], plan={"location": LOCATION, "hook_seconds": 3},
        )
        assert LOCATION in prompt

    def test_both_budget_modes_state_the_visible_first_move(self):
        empty = dict(strategy={}, profile={}, template={}, duration=10,
                     assets=[], plan={"hook_seconds": 3})
        full = gp.build_segment_prompt(**empty)
        tight = gp.build_segment_prompt(**empty, prompt_budget=4096)
        assert "first 1-2 seconds show a clearly visible movement" in full
        assert "1-2s: clearly visible movement" in tight


class TestStrategyPromptRequiresTheVisibleFirstMove:
    def test_the_rule_and_the_schema_both_demand_it(self, monkeypatch):
        captured = {}

        async def fake_chat(**kwargs):
            captured.update(kwargs)
            return {
                "strategy_summary": "s", "audience_problem": "p",
                "emotional_triggers": ["e"], "hook_concept": "hc",
                "hook_line": "hl", "hook_promise": "hp",
                "hook_action": "ha", "hook_dialogue": "hd",
                "messaging_pillars": ["m"], "primary_feature": "f",
                "desired_outcome": "o", "mechanism_beat": "mb",
                "payoff_beat": "pb", "differentiation_beat": "db",
                "scene": {
                    "camera_angle": "Use STARTING SHOT", "framing": "f",
                    "lighting": "l", "location": "a kitchen at 7am",
                    "visual_style": "v",
                    "character_positioning": "cp", "wardrobe": "w",
                    "props": "p", "color_palette": "c",
                },
                "performance": {"movement": "mv", "voice_delivery": "vd"},
                "segments": [
                    {"index": 0, "role": "hook", "seconds": 3, "goal": "g",
                     "script": "s", "action": "a"},
                    {"index": 1, "role": "middle", "seconds": 9, "goal": "g",
                     "script": "s", "action": "a"},
                ],
                "camera_beat": {"direction": "left", "gesture": "a tilt"},
            }

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
        asyncio.run(ai_service.generate_video_strategy(
            profile={"brand_name": "Test App"}, template={"name": "T"},
            hook_seconds=3, total_duration=12,
        ))
        assert "THE OPENING'S FIRST BEAT IS A VISIBLE MOVE" in captured["prompt"]
        assert "first 1-2 seconds" in captured["prompt"]
        # The schema the model writes into says the same thing.
        assert "first 1-2 seconds" in captured["prompt"].split('"hook_action"')[1]
        assert "first 1-2 seconds" in captured["prompt"].split('"action": "what they do')[1]


# ---------------------------------------------------------------------------
# Server orchestration: the save-time rewrite and the pre-render guard.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-location-")
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


def _project_with_strategy(api, location="An old desk at home"):
    from models import BrandProfileCreateRequest, ApproveAppProfileRequest, CreateStudioProjectRequest
    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name="Loc App",
        app_category="Productivity",
        brand_description="A focus timer.",
        core_features=["Timer"],
        usage_moments=["Starting a task"],
        outcome_statements=[{
            "outcome": "Starting without stalling on setup",
            "who_feels_it": "people who stall on starting",
            "from_feature": "Timer",
            "how_it_helps": "The timer starts in one tap so there is nothing to set up",
        }],
    ), user_id=ANON))
    _run(api.approve_app_profile(
        profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    template = _run(api.list_templates(q="Stop", user_id=ANON))["templates"][0]
    project = _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"], template_id=template["id"],
        objective="demonstrate_feature",
    ), user_id=ANON))
    strategy = desk_strategy()
    _run(api._execute(
        "UPDATE studio_projects SET strategy = ?, strategy_version = 1,"
        " script_version = 2, strategy_script_version = 2, hook_line = ?,"
        " script = ?, location = ?, visual_direction = ? WHERE id = ?",
        (json.dumps(strategy), strategy["hook_line"],
         strategy["segments"][1]["script"], location, location, project["id"]),
    ))
    return _run(api.get_studio_project(project["id"], user_id=ANON))


class TestLocationSave:
    def test_editing_the_location_rewrites_the_strategy_in_the_same_save(self, api):
        from models import UpdateStudioProjectRequest
        project = _project_with_strategy(api)

        updated = _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(location=LOCATION), ANON))

        assert updated["location"] == LOCATION
        change = updated.get("location_change") or {}
        assert "Location" in change["changed"]
        # `_public_project` normalizes the strategy for display, and the
        # normalizer ends the merged Location with a period.
        assert updated["strategy"]["scene"]["location"].rstrip(".") == LOCATION
        # The strategy stays current: no paid rebuild is required to move a
        # place name.
        assert updated["strategy_is_current"] is True

    def test_the_legacy_mirror_is_kept_in_sync(self, api):
        from models import UpdateStudioProjectRequest
        project = _project_with_strategy(api)

        _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(location=LOCATION), ANON))

        row = _run(api._fetch_one(
            "SELECT location, visual_direction FROM studio_projects WHERE id = ?",
            (project["id"],)))
        assert row["location"] == LOCATION
        assert row["visual_direction"] == LOCATION

    def test_the_rewrite_is_persisted_and_versioned(self, api):
        from models import UpdateStudioProjectRequest
        project = _project_with_strategy(api)
        before = _run(api._fetch_one(
            "SELECT strategy_version FROM studio_projects WHERE id = ?",
            (project["id"],)))

        _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(location=LOCATION), ANON))

        row = _run(api._fetch_one(
            "SELECT strategy, strategy_version, strategy_script_version, script_version"
            " FROM studio_projects WHERE id = ?", (project["id"],)))
        stored = row["strategy"]
        if isinstance(stored, str):
            stored = json.loads(stored)
        assert stored["scene"]["location"] == LOCATION
        assert row["strategy_version"] == int(before["strategy_version"]) + 1
        assert row["strategy_script_version"] == row["script_version"]

    def test_a_legacy_visual_direction_save_still_works(self, api):
        from models import UpdateStudioProjectRequest
        project = _project_with_strategy(api)
        updated = _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(visual_direction=LOCATION), ANON))
        assert updated["location"] == LOCATION
        assert updated["strategy"]["scene"]["location"].rstrip(".") == LOCATION

    def test_spoken_words_still_naming_the_old_place_are_reported(self, api):
        from models import UpdateStudioProjectRequest
        project = _project_with_strategy(api)
        strategy = desk_strategy()
        strategy["hook_line"] = "I hate being stuck in my living room"
        _run(api._execute(
            "UPDATE studio_projects SET strategy = ?, hook_line = ? WHERE id = ?",
            (json.dumps(strategy), strategy["hook_line"], project["id"])))

        updated = _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(location=LOCATION), ANON))

        blocked = (updated.get("location_change") or {}).get("blocked") or []
        assert [b["field"] for b in blocked] == ["Hook line"]
        # The words themselves are untouched.
        assert updated["strategy"]["hook_line"] == "I hate being stuck in my living room"

    def test_an_unchanged_location_reports_nothing(self, api):
        from models import UpdateStudioProjectRequest
        project = _project_with_strategy(api, location=LOCATION)
        updated = _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(location=LOCATION), ANON))
        assert "location_change" not in updated

    def test_saving_lighting_words_moves_them_out_of_the_stored_location(self, api):
        # The Location keeps the place only; the time of day it carried is
        # stored with the strategy's Lighting in the same save (ADR 0092).
        from models import UpdateStudioProjectRequest
        project = _project_with_strategy(api)
        updated = _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(location="A kitchen at 7am"), ANON))

        assert updated["location"] == "A kitchen"
        assert updated["strategy"]["scene"]["location"].rstrip(".") == "A kitchen"
        assert "7am" in (updated["strategy"]["scene"]["lighting"] or "")
        change = updated.get("location_change") or {}
        assert "Location" in change["changed"] and "Lighting" in change["changed"]

    def test_props_and_movement_are_completed_in_the_same_save(self, api):
        from models import UpdateStudioProjectRequest
        project = _project_with_strategy(api)
        updated = _run(api.update_studio_project(
            project["id"], UpdateStudioProjectRequest(location=LOCATION), ANON))

        change = updated.get("location_change") or {}
        assert "Movement" in change["changed"]
        # desk_strategy's actions name the phone and the couch; the couch
        # belongs to the place, and the phone is NOT a prop: this is a
        # handheld selfie, where the camera IS the phone in their hand, so a
        # phone on camera is the recording device appearing as a prop
        # (ADR 0093). It must not come back through the completion pass.
        props = (updated["strategy"]["scene"]["props"] or "").lower()
        assert "phone" not in props
        assert updated["strategy"]["performance"]["movement"]


class TestRenderGuard:
    def test_direction_lines_are_patched_before_the_prompt(self, api):
        project = {"id": "p1", "location": LOCATION}
        patched = api._guard_render_scene(desk_strategy(), project)
        assert patched["scene"]["location"] == LOCATION
        assert patched["hook_concept"] == "scrolling, frustrated"

    def test_the_legacy_mirror_can_supply_the_location(self, api):
        project = {"id": "p1", "location": "", "visual_direction": LOCATION}
        patched = api._guard_render_scene(desk_strategy(), project)
        assert patched["scene"]["location"] == LOCATION

    def test_spoken_contradictions_refuse_the_render(self, api):
        project = {"id": "p1", "location": LOCATION}
        strategy = desk_strategy()
        strategy["hook_line"] = "I hate being stuck in my living room"
        with pytest.raises(HTTPException) as exc:
            api._guard_render_scene(strategy, project)
        assert exc.value.status_code == 409
        assert "Hook line" in exc.value.detail
        assert "Nothing has been charged" in exc.value.detail

    def test_the_guard_splits_lighting_and_completes_the_scene(self, api):
        # A Location that still carries its time of day, a strategy whose
        # scene fields name no props, and a placeholder camera line: the guard
        # fixes all three in memory, then the prompt is built from the result.
        project = {"id": "p1", "location": "Home office desk at 7am"}
        strategy = desk_strategy()
        strategy["scene"]["props"] = "None"
        strategy["scene"]["camera_angle"] = "Use STARTING SHOT"
        patched = api._guard_render_scene(strategy, project, render_index=0, exclude=[])

        assert patched["scene"]["location"] == "Home office desk"
        assert "7am" in (patched["scene"]["lighting"] or "")
        assert patched["scene"]["camera_angle"] == ""
        props = (patched["scene"]["props"] or "").lower()
        # Handheld selfie: the camera is the phone in their hand, so no phone
        # may appear as a prop — not the one the founder's action names
        # (ADR 0093).
        assert "phone" not in props
        assert patched["performance"]["movement"]
        assert "phone" not in patched["performance"]["movement"].lower()

    def test_no_location_leaves_the_strategy_alone(self, api):
        project = {"id": "p1", "location": "", "visual_direction": ""}
        strategy = desk_strategy()
        assert api._guard_render_scene(strategy, project) is strategy
