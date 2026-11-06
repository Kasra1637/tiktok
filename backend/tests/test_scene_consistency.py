"""
Scene fields that must agree with each other before the render reads them
(ADRs 0092 and 0103).

Six rules are pinned here:

1. Location names the place only; lighting and time of day move into Lighting.
2. Props lists every object the person carries, wears or uses in the
   hook/middle actions and the shot timeline — never scenery Location names.
3. Movement covers every action those lines show.
4. Internal wording ("Use STARTING SHOT") never survives as a scene value, and
   a list that cannot hold everything it must is reported, never cut.
5. Camera angle and Visual style call the filming device "the camera", never
   the phone, and never rewrite a spoken line.
6. The read path normalizes the same scene wording the save/render path does,
   so Render & result never shows a phone or a counter in Props.
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
        # Fixed camera: both hands are free, so a phone is a legitimate prop.
        "camera_setup": "fixed",
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


def test_selfie_renders_never_list_a_phone_as_a_prop():
    # In a selfie video the camera IS the phone: a phone clause in an action
    # cannot become a prop (ADR 0093).
    strategy = {
        "hook_action": "She sets the mug down and picks up the phone",
        "scene": {"location": "Kitchen", "props": "A notebook"},
        "performance": {"movement": "Still"},
        "segments": [{"role": "middle", "action": "Looks up from the notebook"}],
    }
    out = scene_consistency.reconcile_scene(strategy)
    props = out["strategy"]["scene"]["props"].lower()
    assert "phone" not in props
    assert "mug" in props


def test_props_never_list_scenery_the_location_already_names():
    # A counter and a window are the place. Listing them in Props repeats
    # Location and tells the model to put scenery in the person's hands; the
    # mug they lift is the prop.
    strategy = {
        "camera_setup": "fixed",
        "hook_action": "Sets the mug on the kitchen counter and glances at the window",
        "scene": {
            "location": "A tidy kitchen with a wooden counter and a bright window",
            "props": "The kitchen counter, a bright window, a ceramic mug",
        },
        "performance": {"movement": ""},
        "segments": [{"role": "middle", "action": "Lifts the mug"}],
    }
    out = scene_consistency.reconcile_scene(strategy)
    props = out["strategy"]["scene"]["props"].lower()
    assert "counter" not in props
    assert "window" not in props
    assert "mug" in props
    assert "Props" in out["changed"]
    assert out["blocked"] == []


def test_scenery_an_action_only_places_something_on_is_not_added_to_props():
    # Completing the list from the actions must not copy "the counter" or the
    # sign the Location already names back into Props.
    strategy = {
        "camera_setup": "fixed",
        "hook_action": "Sets the mug down on the counter and looks at the sign",
        "scene": {
            "location": "A cafe with a chalkboard sign by the door",
            "props": "",
        },
        "performance": {"movement": "Sits"},
        "segments": [{"role": "middle", "action": "Picks up the mug"}],
    }
    out = scene_consistency.reconcile_scene(strategy)
    props = (out["strategy"]["scene"]["props"] or "").lower()
    assert "counter" not in props
    assert "sign" not in props
    assert "mug" in props
    assert out["blocked"] == []


def test_a_carried_sign_is_still_a_prop_when_location_does_not_name_one():
    # Signage is not banned outright: a sign the person picks up is an object,
    # and only the sign already named in Location is scenery.
    strategy = {
        "camera_setup": "fixed",
        "hook_action": "Lifts the protest sign and steps forward",
        "scene": {"location": "A city street", "props": ""},
        "performance": {"movement": "Steps forward"},
        "segments": [{"role": "middle", "action": "Holds the sign steady"}],
    }
    out = scene_consistency.reconcile_scene(strategy)
    assert "sign" in (out["strategy"]["scene"]["props"] or "").lower()


def test_props_drop_the_place_tail_but_keep_the_object():
    strategy = {
        "camera_setup": "fixed",
        "hook_action": "Picks up the mug",
        "scene": {
            "location": "A tidy kitchen with a wooden counter",
            "props": "a notebook on the counter, a mug on the desk",
        },
        "performance": {"movement": "Picks up the mug"},
        "segments": [{"role": "middle", "action": "Lifts the mug"}],
    }
    out = scene_consistency.reconcile_scene(strategy)
    props = out["strategy"]["scene"]["props"].lower()
    assert props == "a notebook, a mug"
    assert "counter" not in props and "desk" not in props


def test_camera_angle_and_visual_style_call_the_filming_device_the_camera():
    strategy = {
        "camera_setup": "fixed",
        "hook_line": "I keep reaching for my phone",
        "hook_action": "Picks up the mug",
        "scene": {
            "location": "Kitchen",
            "props": "A mug",
            "camera_angle": "Handheld phone camera at eye level",
            "visual_style": "Shot on her smartphone, amateur phone footage",
        },
        "performance": {"movement": "Picks up the mug"},
        "segments": [{
            "role": "hook",
            "script": "My phone is where the evening goes",
            "action": "Picks up the mug",
        }],
    }
    out = scene_consistency.reconcile_scene(strategy)
    scene = out["strategy"]["scene"]
    assert "phone" not in scene["camera_angle"].lower()
    assert "smartphone" not in scene["visual_style"].lower()
    assert "camera" in scene["camera_angle"].lower()
    assert "the camera" in scene["visual_style"].lower()
    assert {"Camera angle", "Visual style"} <= set(out["changed"])
    # Spoken words are not direction: they are read back exactly as written.
    assert out["strategy"]["hook_line"] == strategy["hook_line"]
    assert out["strategy"]["segments"][0]["script"] == strategy["segments"][0]["script"]


def test_normalize_strategy_cleans_scene_wording_for_the_panel():
    normalized = ai_service.normalize_strategy({
        "hook_line": "I keep reaching for my phone",
        "scene": {
            "location": "A kitchen with a wooden counter",
            "camera_angle": "Shot on her phone at eye level",
            "visual_style": "iPhone footage, phone-camera look",
            "props": "The kitchen counter, a ceramic mug",
        },
        "segments": [{
            "index": 0, "role": "hook", "seconds": 3, "goal": "g",
            "script": "My phone is where the evening goes",
            "action": "Picks up the mug",
        }],
    })
    scene = normalized["scene"]
    assert "phone" not in scene["camera_angle"].lower()
    assert "phone" not in scene["visual_style"].lower()
    assert "camera" in scene["camera_angle"].lower()
    assert "camera" in scene["visual_style"].lower()
    assert scene["props"] == "a ceramic mug"
    assert normalized["hook_line"] == "I keep reaching for my phone"
    assert normalized["segments"][0]["script"] == "My phone is where the evening goes"


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


def test_movement_covers_the_action_fields_and_ignores_the_narrated_beats():
    # Only the action fields (hook_action and the section actions) are copied
    # into Movement. The timeline's *text* beats are narration: dumping them
    # into the movement line every render is what pushed ordinary strategies
    # past its size cap and blocked the render.
    # Selfie (the default here): "reaches for the phone" is a forbidden
    # clause (ADR 0093 as superseded), so it is stripped before the
    # completion pass and must never re-enter Movement. What survives is
    # still covered.
    strategy = {
        "hook_action": "Stands up from the desk",
        "scene": {"location": "Kitchen", "props": ""},
        "performance": {"movement": "Still"},
        "segments": [{"role": "middle", "action": "Reaches for the phone"}],
    }
    plan = {"beat_timeline": [{"label": "middle", "text": "Sits back down and sighs"}]}
    out = scene_consistency.reconcile_scene(strategy, plan)
    movement = out["strategy"]["performance"]["movement"].lower()
    assert "stands up from the desk" in movement
    assert "reaches for the phone" not in movement
    assert "phone" not in movement
    assert "sits back down and sighs" not in movement
    assert out["blocked"] == []


def test_a_verbose_timeline_can_no_longer_block_the_render():
    # The regression behind "Movement cannot cover every action": two beats of
    # narration alone are longer than the movement field can hold, so checking
    # them against Movement refused renders that used to work.
    strategy = {
        "hook_action": "Looks up from the notebook",
        "scene": {"location": "Kitchen", "props": ""},
        "performance": {"movement": "Still"},
        "segments": [{"role": "middle", "action": "Counts on fingers"}],
    }
    plan = {"beat_timeline": [
        {"label": "hook", "text": "Stops mid-scroll and looks at the phone, then turns back "
                                   "with a question on her face and a slow blink"},
        {"label": "middle", "text": "The blank page loses its grip, then she taps the mug "
                                     "and laughs once without sound"},
    ]}
    out = scene_consistency.reconcile_scene(strategy, plan)
    assert out["blocked"] == []
    movement = out["strategy"]["performance"]["movement"].lower()
    assert "looks up from the notebook" in movement
    assert "counts on fingers" in movement


def test_the_viewer_rows_are_written_from_the_viewers_point_of_view():
    # Source pins on the strategy prompt: these three fields are the panel's
    # "What the viewer ends up with" block, so the wording that generates them
    # must ask for the viewer's point of view.
    src = Path(ai_service.__file__).read_text(encoding="utf-8")
    assert "written from the viewer" in src
    assert "what the viewer is left with" in src
    assert "never a lighting word and never a time of day" in src
    assert "PROPS ARE OBJECTS THE PERSON CARRIES, WEARS OR USES" in src
    assert "never furniture, buildings or signs already named in location" in src
    assert "natural amateur handheld camera footage" in src
