"""
Scene fields that must agree with each other before the render reads them (ADR 0092).

Four rules are pinned here:

1. Location names the place only; lighting and time of day move into Lighting.
2. Props lists every object the hook/middle actions and the shot timeline show.
3. Movement covers every action those lines show.
4. Internal wording ("Use STARTING SHOT") never survives as a scene value, and
   a list that cannot hold everything it must is reported, never cut.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ai_service
import scene_consistency


def test_location_is_split_from_lighting_and_time():
    assert scene_consistency.split_location("Kitchen at 7am") == ("Kitchen", "7am")
    assert scene_consistency.split_location("A park bench on a sunny afternoon") == (
        "A park bench", "sunny afternoon",
    )
    assert scene_consistency.split_location("Quiet garden bench at golden hour") == (
        "Quiet garden bench", "golden hour",
    )
    assert scene_consistency.split_location("Kitchen with warm light") == (
        "Kitchen", "warm light",
    )


def test_place_only_and_lighting_only_texts_are_untouched():
    # Nothing to move: the place stands as written.
    assert scene_consistency.split_location("Home office desk") == ("Home office desk", "")
    # Nothing but lighting: with no place to name, the split declines rather
    # than emptying the field.
    assert scene_consistency.split_location("Soft morning light") == ("Soft morning light", "")


def test_scene_placeholders_are_removed():
    strategy = {"scene": {
        "camera_angle": "Use STARTING SHOT",
        "framing": "Use STARTING SHOT and final-phone rule",
        "location": "Kitchen",
    }}
    out = scene_consistency.reconcile_scene(strategy)
    assert out["strategy"]["scene"]["camera_angle"] == ""
    assert out["strategy"]["scene"]["framing"] == ""
    assert {"Camera angle", "Framing"} <= set(out["changed"])


def test_normalize_strategy_never_returns_placeholder_wording():
    normalized = ai_service.normalize_strategy({"scene": {
        "camera_angle": "Use STARTING SHOT",
        "framing": "Use STARTING SHOT and final-phone rule",
    }})
    assert normalized["scene"]["camera_angle"] == ""
    assert normalized["scene"]["framing"] == ""


def test_props_learn_every_object_the_actions_and_timeline_show():
    strategy = {
        "hook_action": "She sets the mug down and picks up the phone",
        "scene": {"location": "Kitchen", "props": "A notebook"},
        "performance": {"movement": ""},
        "segments": [
            {"role": "hook", "action": "Looks up from the notebook"},
            {"role": "middle", "action": "Counts on fingers"},
        ],
    }
    plan = {"beat_timeline": [
        {"label": "hook", "text": "Stops mid-scroll and grabs the keys"},
    ]}
    out = scene_consistency.reconcile_scene(strategy, plan)
    props = out["strategy"]["scene"]["props"].lower()
    for word in ("mug", "phone", "keys", "notebook"):
        assert word in props, f"{word} missing from props: {props}"
    assert out["strategy"]["performance"]["movement"]
    assert "Props" in out["changed"] and "Movement" in out["changed"]


def test_body_parts_places_and_abstractions_are_never_props():
    strategy = {
        "hook_action": "Turns her face to the window with a smile in the moment",
        "scene": {"location": "Kitchen", "props": ""},
        "performance": {"movement": "turns"},
    }
    out = scene_consistency.reconcile_scene(strategy)
    props = (out["strategy"]["scene"]["props"] or "").lower()
    for word in ("face", "window", "moment", "smile"):
        assert word not in props, f"{word} is not an object: {props}"


def test_a_list_that_cannot_hold_everything_is_blocked_not_cut():
    strategy = {
        "hook_action": "Picks up the mug",
        "scene": {"location": "Kitchen", "props": "z" * 298},
        "performance": {"movement": "stands"},
    }
    out = scene_consistency.reconcile_scene(strategy)
    assert [b["field"] for b in out["blocked"]] == ["Props"]
    # The field is reported, not silently trimmed to fit.
    assert out["strategy"]["scene"]["props"] == "z" * 298


def test_movement_is_completed_from_the_sections_and_the_timeline():
    strategy = {
        "hook_action": "Stands up from the desk",
        "scene": {"location": "Kitchen", "props": ""},
        "performance": {"movement": "Still"},
        "segments": [{"role": "middle", "action": "Reaches for the phone"}],
    }
    plan = {"beat_timeline": [{"label": "middle", "text": "Sits back down and sighs"}]}
    out = scene_consistency.reconcile_scene(strategy, plan)
    movement = out["strategy"]["performance"]["movement"].lower()
    for phrase in ("stands up from the desk", "reaches for the phone", "sits back down"):
        assert phrase in movement, f"{phrase} missing from movement: {movement}"


def test_the_viewer_rows_are_written_from_the_viewers_point_of_view():
    # Source pins on the strategy prompt: these three fields are the panel's
    # "What the viewer ends up with" block, so the wording that generates them
    # must ask for the viewer's point of view.
    src = Path(ai_service.__file__).read_text(encoding="utf-8")
    assert "written from the viewer" in src
    assert "what the viewer is left with" in src
    assert "never a lighting word and never a time of day" in src
    assert "PROPS AND MOVEMENT ARE COMPLETE LISTS" in src
