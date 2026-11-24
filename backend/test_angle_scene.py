"""The angle owns where and when the video happens (ADR 0084)."""
import subprocess
import sys
import asyncio
from pathlib import Path

import pytest

import angle_scene
import template_library
from template_recommendations import score_template_for_angle

OFFICE = {"id": "a1", "hook_promise": "a person steps outside an office building after a call"}


def test_policy_imports_no_adapter():
    result = subprocess.run(
        [sys.executable, "-c", (
            "import angle_scene, sys; "
            "bad = {'server', 'ai_service', 'auth', 'httpx', 'fastapi', 'aiosqlite'} & set(sys.modules); "
            "assert not bad, bad"
        )], cwd=Path(__file__).resolve().parent, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_office_exit_reads_as_outdoors():
    assert angle_scene.angle_scene(OFFICE)["place"] == "outdoor"


def test_dropdowns_never_offer_indoor_options_for_an_outdoor_angle():
    options = template_library.DIRECTION_OPTIONS["wellness"]
    fitted = angle_scene.fit_direction_options(options, OFFICE)
    assert fitted["location"][0] == "A person steps outside an office building after a call"
    for field in ("location", "lighting"):
        for option in fitted[field]:
            assert "living room" not in option.lower() and "lamp" not in option.lower(), option
        assert len(fitted[field]) >= 3


def test_no_angle_leaves_dropdowns_unchanged():
    options = template_library.DIRECTION_OPTIONS["wellness"]
    fitted = angle_scene.fit_direction_options(options, None)
    assert fitted["location"] == options["location"]


def test_indoor_look_is_adjusted_with_a_note():
    out = angle_scene.reconcile_look(
        "Quiet living room corner, Warm low lamp glow, Plain charcoal t-shirt", OFFICE
    )
    assert "living room" not in out["visual_direction"].lower()
    assert "lamp" not in out["visual_direction"].lower()
    assert "Plain charcoal t-shirt" in out["visual_direction"]
    assert out["visual_direction"].startswith("A person steps outside an office building")
    assert "adjusted your look" in out["note"]


def test_matching_look_is_untouched():
    out = angle_scene.reconcile_look("Plain charcoal t-shirt", OFFICE)
    assert out == {"visual_direction": "Plain charcoal t-shirt", "note": "", "dropped": []}


def test_night_bed_template_ranks_lower_with_a_plain_note():
    bed = {"name": "Bed", "opening_structure": "Lies in bed late at night with racing thoughts"}
    neutral = {"name": "Neutral", "opening_structure": "Names the frustration in one line"}
    profile = {"id": "p1"}
    a = score_template_for_angle(bed, profile, OFFICE, "")
    b = score_template_for_angle(neutral, profile, OFFICE, "")
    assert a["angle_scene"]["fits"] is False
    assert a["limitations"][0].startswith("Doesn't fit this angle")
    assert b["angle_scene"]["fits"] is True
    assert a["score"] <= b["score"]


def test_conflicting_example_is_flagged_for_replacement():
    tpl = {"opening_structure": "Names the frustration", "example_preview": "Lies in bed at eleven at night"}
    assert angle_scene.template_angle_fit(tpl, OFFICE)["example_conflicts"] is True


def test_prompts_bind_the_angle_moment_and_name_the_pain():
    import ai_service
    assert "ANGLE SCENE" in ai_service.scene_location_guidance(OFFICE)
    assert "steps outside an office building" in ai_service.scene_location_guidance(OFFICE)
    assert "ANGLE SCENE" not in ai_service.scene_location_guidance()
    # The pain-first doctrine (ADR 0289, Kasra's order Nov 23 2026):
    # the hook names the internal pain the app resolves, never the
    # app's activity — the old NAME THE ACTION rule, whose exemplar
    # was a journaling line, is superseded.
    block = ai_service._spoken_line_rules_block()
    assert "NAME THE PAIN, NOT THE ACTIVITY" in block
    assert "NAME THE ACTION" not in block
    assert "nobody cares about writing a journal" in block
    assert "the demo that follows lands as the answer" in block
    assert "PLACE + TIME" in ai_service._angle_goal_block(OFFICE, "")


TRAVEL_MOMENTS = [
    ("stuck on her commute home after work", "outdoor", "evening"),
    ("waiting on the station platform", "outdoor", ""),
    ("sitting in her parked car before going in", "indoor", ""),
    ("on the train at the end of the day", "", "evening"),
    ("walks out of the office after a long meeting", "outdoor", ""),
    ("alone in his apartment on a Sunday", "indoor", ""),
    ("steps out of the car outside the cafe", "outdoor", ""),
]


def test_travel_and_room_wording_is_read():
    for moment, place, time in TRAVEL_MOMENTS:
        assert angle_scene.scene_of(moment) == {"place": place, "time": time}, moment


def test_lighting_words_are_not_mistaken_for_places():
    assert angle_scene.scene_of("Flat even studio light")["place"] == ""


def test_unclear_place_is_detected():
    assert angle_scene.scene_is_unclear({"hook_promise": "right after a hard conversation"})
    assert not angle_scene.scene_is_unclear(OFFICE)
    assert not angle_scene.scene_is_unclear(None)
    assert not angle_scene.scene_is_unclear({"hook_promise": ""})


def test_place_rule_only_when_the_angle_names_no_place():
    import ai_service
    vague = {"hook_promise": "right after a hard conversation"}
    assert "ANGLE PLACE" in ai_service.scene_location_guidance(vague)
    assert "ANGLE PLACE" in ai_service._angle_goal_block(vague, "")
    assert "ANGLE PLACE" not in ai_service.scene_location_guidance(OFFICE)
    assert "ANGLE PLACE" not in ai_service._angle_goal_block(OFFICE, "")
    assert "ANGLE PLACE" not in ai_service.scene_location_guidance()


def test_hook_rewrite_returns_the_clearer_line(monkeypatch):
    import ai_service
    # The canned reply carries its period: since ADR 0231 the rewrite
    # surface runs the finished-sentence gate, and a reply without a
    # terminator is a fragment it corrects or refuses, never returns.
    seen = {}

    async def fake_chat(**kwargs):
        seen.update(kwargs)
        return {"hook_line": "I don't want to write in my journal today."}
    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    line = asyncio.run(ai_service.rewrite_hook_line(
        {"brand_name": "Voice Journal"}, OFFICE, "I don't want to type anything"))
    assert line == "I don't want to write in my journal today."
    assert "I don't want to type anything" in seen["prompt"]
    assert "NAME THE PAIN, NOT THE ACTIVITY" in seen["prompt"]
    assert seen["json_schema"] is ai_service.HOOK_REWRITE_JSON_SCHEMA


def test_hook_rewrite_refuses_empty_and_unchanged(monkeypatch):
    import ai_service

    async def same(**kwargs):
        return {"hook_line": "I don't want to type anything"}
    monkeypatch.setattr(ai_service, "_chat_json", same)
    with pytest.raises(RuntimeError):
        asyncio.run(ai_service.rewrite_hook_line({}, OFFICE, "   "))
    with pytest.raises(RuntimeError):
        asyncio.run(ai_service.rewrite_hook_line({}, OFFICE, "I don't want to type anything"))


# ---------------------------------------------------------------------------
# ADR 0233: a fixed camera's angle display restates outdoor places indoors.
# The stored angle never changes; only the serialized display fields do,
# and only for the place phrases the restatement table knows.
# ---------------------------------------------------------------------------

OUTDOOR_ANGLE = {
    "label": "The courthouse queue",
    "target_audience": "busy professionals",
    "user_problem": "You wait at the courthouse and the blank page wins.",
    "hook_promise": "Feelings at the coastline finally get words",
    "app_feature": "Voice journaling",
    "desired_emotion": "Relief",
    "viewer_outcome": "They name the feeling before the day starts.",
    "claims_to_respect": ["Never promise the courthouse Wi-Fi works"],
}


def test_fixed_display_restates_the_known_places():
    overlay = angle_scene.indoor_restatement(OUTDOOR_ANGLE, "fixed")
    assert overlay is not None
    assert overlay["hook_promise"] == "Feelings by the large window finally get words"
    assert overlay["user_problem"] == "You wait in the living room and the blank page wins."
    assert overlay["label"] == "The living room queue"
    assert overlay["claims_to_respect"] == ["Never promise the living room Wi-Fi works"]
    # Fields naming no known place are absent from the overlay, so the
    # caller keeps them byte-identical.
    for field in ("target_audience", "app_feature", "desired_emotion", "viewer_outcome"):
        assert field not in overlay


def test_a_courtyard_moment_restates_as_an_atrium():
    angle = dict(OUTDOOR_ANGLE, hook_promise="Feelings in the courtyard finally get words")
    overlay = angle_scene.indoor_restatement(angle, "fixed")
    assert overlay is not None
    assert overlay["hook_promise"] == "Feelings in the atrium finally get words"


def test_handheld_display_is_never_restated():
    assert angle_scene.indoor_restatement(OUTDOOR_ANGLE, "handheld") is None
    assert angle_scene.indoor_restatement(OUTDOOR_ANGLE, "") is None
    assert angle_scene.indoor_restatement(OUTDOOR_ANGLE, None) is None


def test_fixed_display_leaves_an_indoor_angle_alone():
    angle = dict(OUTDOOR_ANGLE, hook_promise="Feelings in the kitchen finally get words")
    assert angle_scene.indoor_restatement(angle, "fixed") is None


def test_fixed_display_leaves_an_unknown_outdoor_place_alone():
    # The scene reads outdoors (the café — this module reads it as an
    # outdoor word), but the restatement table knows no indoor counterpart
    # for it: the text stays as written and the angle section's note
    # carries the staging instead (ADR 0233's boundary).
    angle = dict(
        OUTDOOR_ANGLE,
        label="The café queue",
        user_problem="You sit at the café and the blank page wins.",
        hook_promise="Feelings at the café finally get words",
        claims_to_respect=["Never promise the café Wi-Fi works"],
    )
    assert angle_scene.indoor_restatement(angle, "fixed") is None


def test_the_restatement_changes_only_the_place_phrase():
    text = "A woman at the beach at 7am, before the emails start"
    assert angle_scene.restate_text_indoors(text) == \
        "A woman by the large window at 7am, before the emails start"


def test_the_restatement_preserves_sentence_case():
    assert angle_scene.restate_text_indoors("At the beach she breathes") == \
        "By the large window she breathes"
    assert angle_scene.restate_text_indoors("She waits at the courthouse") == \
        "She waits in the living room"
