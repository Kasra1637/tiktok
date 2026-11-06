"""
Selfie endings: a physical beat per render, never a phone (ADR 0093).

A selfie video is filmed with the phone in the character's hand, so the
recording device cannot be raised, held or shown at the end. Fixed-camera
renders keep the phone handoff. The selfie ending rotates per render, prefers
the hook's mood, and is written into the strategy fields and the final prompt.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import final_beat
import generation_planning as gp
import server


def test_endings_rotate_and_never_repeat_recent_ones():
    first = final_beat.pick({}, index=0)
    second = final_beat.pick({}, index=1)
    assert first != second
    assert final_beat.pick({}, exclude=[first], index=0) != first
    assert final_beat.pick({}, exclude=[first, second], index=0) not in (first, second)


def test_the_ending_fits_the_hooks_mood():
    strategy = {"emotional_triggers": ["relief"]}
    for index in range(len(final_beat.ENDINGS)):
        ending = final_beat.pick(strategy, index=index)
        moods = next(entry["moods"] for entry in final_beat.ENDINGS if entry["text"] == ending)
        assert "relief" in moods


def test_phone_clauses_are_removed_but_the_action_survives():
    kept, removed = final_beat.split_phone_clauses(
        "She sets the mug down and picks up the phone, then raises the phone into view"
    )
    assert "sets the mug down" in kept
    assert "phone" not in kept
    assert removed
    assert final_beat.strip_props("A mug, her phone, a notebook") == ("A mug, a notebook", True)


def test_the_chosen_ending_reaches_the_strategy_fields():
    strategy = {
        "performance": {"movement": "Stands up from the desk."},
        "segments": [{"role": "middle", "action": "Counts on fingers."}],
    }
    out = final_beat.apply_ending(strategy, final_beat.ENDINGS[3]["text"])
    text = out["strategy"]["segments"][0]["action"]
    movement = out["strategy"]["performance"]["movement"]
    assert final_beat.ENDINGS[3]["text"].rstrip(".") in text
    assert final_beat.ENDINGS[3]["text"].rstrip(".") in movement
    assert out["strategy"]["final_beat"].endswith(".")
    assert "Final beat" not in json.dumps(out)


def test_selfie_guard_strips_the_phone_and_applies_one_ending():
    strategy = {
        "camera_setup": "handheld",
        "hook_action": "Turns to the lens and lifts the phone",
        "scene": {"location": "A kitchen", "props": "A mug, her phone",
                  "framing": "Raises the phone into view"},
        "performance": {"movement": "Stands up, then raises the phone into view"},
        "segments": [{"role": "hook", "action": "Looks up"},
                     {"role": "middle", "action": "Counts on fingers, then shows the phone"}],
    }
    project = {"id": "p1", "location": "A kitchen", "beat_timeline": []}
    patched = server._guard_render_scene(strategy, project, render_index=0)
    blob = json.dumps(patched).lower()
    assert "raises the phone" not in blob
    assert "shows the phone" not in blob
    assert "lifts the phone" not in blob
    assert "her phone" not in (patched["scene"]["props"] or "").lower()
    assert patched["final_beat"]
    assert patched["final_beat"].rstrip(".") in patched["segments"][1]["action"]
    assert patched["final_beat"].rstrip(".") in patched["performance"]["movement"]


def test_fixed_camera_guard_keeps_the_phone_handoff():
    strategy = {
        "camera_setup": "fixed",
        "hook_action": "Turns to the lens",
        "scene": {"location": "A kitchen", "props": "A mug, her phone"},
        "performance": {"movement": "Stands up, then raises the phone into view"},
        "segments": [{"role": "middle", "action": "Shows the phone at the end"}],
    }
    project = {"id": "p1", "location": "A kitchen", "beat_timeline": []}
    patched = server._guard_render_scene(strategy, project, render_index=0)
    assert "final_beat" not in patched
    assert "her phone" in (patched["scene"]["props"] or "")
    assert "raises the phone into view" in patched["performance"]["movement"]


def test_the_final_prompt_has_no_phone_for_selfie_and_keeps_it_for_fixed():
    selfie = gp.build_segment_prompt(
        strategy={"camera_setup": "handheld", "final_beat": final_beat.ENDINGS[0]["text"]},
        profile={}, template={}, duration=10, plan={"hook_seconds": 3},
    )
    fixed = gp.build_segment_prompt(
        strategy={"camera_setup": "fixed"},
        profile={}, template={}, duration=10, plan={"hook_seconds": 3},
    )
    assert final_beat.ENDINGS[0]["text"] in selfie
    assert "raises the phone into view" not in selfie
    assert "never reach toward" in selfie
    assert "reaches for their phone" not in selfie
    assert "raises the phone into view" in fixed


def test_reach_camera_and_second_hand_clauses_are_removed_but_action_survives():
    kept, removed = final_beat.split_phone_clauses(
        "Counts on fingers and reaches a hand toward the lens with her other hand"
    )
    assert "counts on fingers" in kept.lower()
    assert "lens" not in kept.lower()
    assert "other hand" not in kept.lower()
    assert removed
    for text, args in [
        ("Reaches for the phone", ("", "Reaches for the phone")),
        ("Holds the camera up", ("", "Holds the camera up")),
        ("Types with both hands", ("", "Types with both hands")),
        ("Reaches toward the camera", ("", "Reaches toward the camera")),
    ]:
        _kept, _removed = final_beat.split_phone_clauses(text)
        assert _kept == args[0], (text, _kept)
        assert _removed, text
    kept, removed = final_beat.split_phone_clauses("No phone on camera, eyes on the lens")
    assert kept
    assert not removed
    assert final_beat.strip_props("A mug, her phone, the camera, a notebook") == ("A mug, a notebook", True)


def test_selfie_guard_strips_reach_and_second_hand_end_to_end():
    strategy = {
        "camera_setup": "handheld",
        "hook_action": "Steps in and turns to the lens",
        "scene": {"location": "A kitchen", "props": "A mug, her phone"},
        "performance": {"movement": "Counts on fingers, then reaches toward the lens"},
        "segments": [{"role": "hook", "action": "Looks up"},
                     {"role": "middle", "action": "Counts on fingers, then reaches a hand toward the lens with her other hand"}],
    }
    project = {"id": "p1", "location": "A kitchen", "beat_timeline": []}
    patched = server._guard_render_scene(strategy, project, render_index=0)
    blob = json.dumps(patched).lower()
    assert "toward the lens" not in blob
    assert "other hand" not in blob
    assert "reaches for" not in blob
    assert "her phone" not in (patched["scene"]["props"] or "").lower()
    assert "counts on fingers" in patched["segments"][1]["action"].lower()
    assert patched["final_beat"]


def test_selfie_guard_blocks_when_middle_is_only_the_reach():
    import pytest
    from fastapi import HTTPException
    strategy = {
        "camera_setup": "handheld",
        "hook_action": "Steps in and turns to the lens",
        "scene": {"location": "A kitchen"},
        "performance": {"movement": "Still"},
        "segments": [{"role": "hook", "action": "Looks up"},
                     {"role": "middle", "action": "Reaches a hand toward the lens"}],
    }
    project = {"id": "p1", "location": "A kitchen", "beat_timeline": []}
    with pytest.raises(HTTPException) as exc:
        server._guard_render_scene(strategy, project, render_index=0)
    assert exc.value.status_code == 409
    assert "Middle" in exc.value.detail
    assert "Nothing has been charged" in exc.value.detail


def test_a_phone_named_as_an_object_leaves_a_selfie_frame():
    # The camera IS the phone in their hand, so a second phone in the frame is
    # the recording device appearing as a prop (ADR 0093). It cannot be a prop
    # for a selfie, and it must not come back through the Props completion.
    kept, removed = final_beat.split_phone_clauses(
        "Sits at the desk and slams the phone down"
    )
    assert kept.strip().lower() == "sits at the desk"
    assert removed
    # A phone CALL is not a phone on camera, so the clause survives.
    kept, removed = final_beat.split_phone_clauses("Takes a phone call and laughs")
    assert "phone call" in kept.lower()
    assert not removed


def test_the_guard_strips_the_phone_out_of_the_middle_action():
    # The founder's own words keep the reach; the render sees the action
    # without it, and the phone never becomes a prop.
    strategy = {
        "camera_setup": "handheld",
        "hook_action": "Sits at the desk",
        "scene": {"location": "A kitchen", "props": "A mug"},
        "performance": {"movement": "Stands up from the desk"},
        "segments": [{"role": "hook", "action": "Looks up"},
                     {"role": "middle", "action": "Counts on fingers and reaches for the phone"}],
    }
    project = {"id": "p1", "location": "A kitchen", "beat_timeline": []}
    patched = server._guard_render_scene(strategy, project, render_index=0)
    action = patched["segments"][1]["action"].lower()
    assert "reaches for the phone" not in action
    assert "counts on fingers" in action
    assert "phone" not in (patched["scene"]["props"] or "").lower()
    assert "phone" not in patched["performance"]["movement"].lower()


def test_the_spoken_words_are_never_rewritten():
    # The hook dialogue may BE the founder's spoken line, so a phone word in it
    # is theirs and stays: only the on-camera action wording is stripped.
    strategy = {
        "camera_setup": "handheld",
        "hook_action": "Turns to the lens and reaches for the phone",
        "hook_dialogue": "I reached for my phone at that point",
        "scene": {"location": "A kitchen", "props": "A mug"},
        "performance": {"movement": "Stands up from the desk"},
        "segments": [{"role": "hook", "action": "Looks up",
                      "script": "I reached for my phone at that point"},
                     {"role": "middle", "action": "Counts on fingers"}],
    }
    project = {"id": "p1", "location": "A kitchen", "beat_timeline": []}
    patched = server._guard_render_scene(strategy, project, render_index=0)
    assert patched["hook_dialogue"] == "I reached for my phone at that point"
    assert patched["segments"][0]["script"] == "I reached for my phone at that point"


def test_consecutive_renders_get_different_endings():
    strategy = {
        "camera_setup": "handheld",
        "scene": {"location": "A kitchen"},
        "performance": {"movement": "Still"},
        "segments": [{"role": "middle", "action": "Counts on fingers"}],
    }
    project = {"id": "p1", "location": "A kitchen", "beat_timeline": []}
    endings = [
        server._guard_render_scene(strategy, project, render_index=index)["final_beat"]
        for index in range(3)
    ]
    assert len(set(endings)) == 3
