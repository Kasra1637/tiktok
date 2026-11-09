"""Regression: render prompt must not state hook/spoken lines twice.

bind_spoken_words copies the approved hook line into segments[0].script and
the hook score into segments[0].action. The assembler previously emitted
both copies, so a realistic strategy carried the hook line 3x and the action
twice, squeezed the brief past its cap, and lost payoff/differentiation.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import generation_planning as gp

ACTION = (
    "Frame one is already moving: the hand snaps up holding the phone, thumb "
    "turning it to the lens; on that beat the brows lift and the eyes widen, "
    "jaw dropping open; the hand drops out of frame as the shoulders break "
    "forward and they step in; end on the sharp look into the camera."
)


def _fixture():
    strategy = {
        "camera_setup": "handheld",
        "hook_line": "Nobody warned me this would happen at 3am.",
        "hook_concept": "The viewer catches the middle of a gesture they did not see start.",
        "hook_action": ACTION,
        "hook_dialogue": "Nobody warned me this would happen at 3am.",
        "hook_promise": "You will recognise the 3am spiral.",
        "strategy_summary": "A night-shift worker catches themselves mid-spiral and names it.",
        "audience_problem": "They replay the day at 3am and cannot switch off.",
        "emotional_triggers": ["exhaustion", "self-recognition"],
        "messaging_pillars": ["Name the spiral", "End the replay"],
        "primary_feature": "a two-minute wind-down prompt",
        "desired_outcome": "They put the day down and sleep.",
        "mechanism_beat": "One prompt turns the replay into a sentence.",
        "payoff_beat": "The sentence is written and the page closes.",
        "differentiation_beat": "It asks one question instead of a journal.",
        "scene": {
            "location": "a hospital corridor at night",
            "lighting": "cold overhead strip light",
            "wardrobe": "a grey scrub top",
            "props": "a scrunchie on the wrist, a phone in the hand",
            "visual_style": "natural amateur phone footage",
            "color_palette": "cool green and grey",
            "character_positioning": "centre frame, standing",
        },
        "performance": {"movement": "small weight shifts", "voice_delivery": "tired, quiet"},
        "camera_beat": {"direction": "right", "gesture": "the hand snaps up"},
        "final_beat": "They pocket the phone and look down the corridor.",
        "segments": [
            {"role": "hook", "goal": "Stop the scroll inside half a second.",
             "script": "Nobody warned me this would happen at 3am.", "action": ACTION},
            {"role": "middle", "goal": "Develop it into the moment they reach for the phone.",
             "script": "I was mid-shift and completely done for the night.",
             "action": "The shoulders drop, the hands stay low and busy."},
        ],
    }
    profile = {"brand_name": "ShiftLog", "must_not_show": ["a hospital bed", "a patient"]}
    template = {
        "opening_structure": "Start mid-gesture, then name the problem.",
        "middle_structure": "Name the friction, then stop at the reach.",
        "visual_style": "natural amateur phone footage",
        "camera_pacing": "handheld, slow push-in",
        "hook_seconds": 3,
    }
    plan = {"hook_seconds": 3, "location": "a hospital corridor at night"}
    assets = [{"kind": "character_reference", "name": "founder photo"}]
    return strategy, profile, template, plan, assets


def test_hook_line_and_action_appear_once():
    strategy, profile, template, plan, assets = _fixture()
    prompt = gp.build_segment_prompt(
        strategy=strategy, profile=profile, template=template,
        duration=20, assets=assets, plan=plan,
    )
    assert prompt.count("Nobody warned me this would happen at 3am.") == 1
    assert prompt.count("Frame one is already moving") == 1
    assert len(prompt) <= gp.RENDER_PROMPT_LIMIT


def test_template_camera_style_do_not_reach_render():
    strategy, profile, template, plan, assets = _fixture()
    prompt = gp.build_segment_prompt(
        strategy=strategy, profile=profile, template=template,
        duration=20, assets=assets, plan=plan,
    )
    assert "Camera and pacing" not in prompt
    # scene lock carries visual style once, template copy is gone
    assert prompt.count("natural amateur phone footage") == 1


def test_payoff_and_differentiation_reach_final_prompt():
    strategy, profile, template, plan, assets = _fixture()
    prompt = gp.build_segment_prompt(
        strategy=strategy, profile=profile, template=template,
        duration=20, assets=assets, plan=plan,
    )
    assert "One prompt turns the replay into a sentence." in prompt
    assert "The sentence is written and the page closes." in prompt
    assert "It asks one question instead of a journal." in prompt
    assert "a scrunchie on the wrist" in prompt


def test_person_anchor_says_skin_not_build():
    prompt = gp.person_anchor_notes([{"kind": "character_reference", "name": "x"}])
    assert "face, hair and skin" in prompt
    assert "face, hair and build" not in prompt
