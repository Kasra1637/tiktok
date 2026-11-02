"""The angle owns where and when the video happens (ADR 0084)."""
import subprocess
import sys
from pathlib import Path

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
    assert fitted["setting"][0] == "A person steps outside an office building after a call"
    for field in ("setting", "lighting"):
        for option in fitted[field]:
            assert "living room" not in option.lower() and "lamp" not in option.lower(), option
        assert len(fitted[field]) >= 3


def test_no_angle_leaves_dropdowns_unchanged():
    options = template_library.DIRECTION_OPTIONS["wellness"]
    fitted = angle_scene.fit_direction_options(options, None)
    assert fitted["setting"] == options["setting"]


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


def test_vague_hook_is_flagged_but_never_blocks():
    import claim_safety
    assert claim_safety.detect_vague_hook("I don't want to type anything")
    assert claim_safety.detect_vague_hook("Typing is the last thing I want to do")
    assert not claim_safety.detect_vague_hook("I don't want to write in my journal today")
    report = claim_safety.build_safety_report({"hook_line": "I don't want to type anything"}, {})
    assert report["passed"] is True
    assert any("vague" in w["reason"] for w in report["risk_warnings"])


def test_prompts_bind_the_angle_moment_and_name_the_action():
    import ai_service
    assert "ANGLE SCENE" in ai_service.scene_setting_guidance(OFFICE)
    assert "steps outside an office building" in ai_service.scene_setting_guidance(OFFICE)
    assert "ANGLE SCENE" not in ai_service.scene_setting_guidance()
    assert "NAME THE ACTION" in ai_service._spoken_line_rules_block()
    assert "PLACE + TIME" in ai_service._angle_goal_block(OFFICE, "")
