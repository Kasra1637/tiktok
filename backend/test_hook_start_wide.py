"""
Start wide, land close (ADR 0323, Kasra's ruling, Nov 24 2026).

A Hook + CTA hook must OPEN wide — camera further from her face,
waist-up, the place visible around her, even on a handheld selfie —
and her own hand eases the camera toward her face as she delivers
the line, LANDING at the close framing by the end. Starting zoomed
in is the fault; arriving close is fine. The shared selfie hold
("hold that framing, no push in") is Create Video's framing and
must not change: the hook surface swaps it for its own camera move,
in both budget modes, and only there.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generation_planning as gp


def _strategy(camera_setup="handheld"):
    return {
        "camera_setup": camera_setup,
        "camera_beat": {"direction": "left", "gesture": "a small relieved smile"},
    }


def _segment_prompt(plan, prompt_budget=None):
    kwargs = dict(
        strategy=_strategy(), profile={}, template={}, duration=5, plan=plan,
    )
    if prompt_budget is not None:
        kwargs["prompt_budget"] = prompt_budget
    return gp.build_segment_prompt(**kwargs)


class TestHookCameraMove:
    def test_the_hook_move_starts_wide_and_lands_close(self):
        section = gp.camera_move_section(_strategy(), hook_surface=True)
        assert "START WIDE" in section
        assert "waist up" in section.lower()
        assert "place visible around her" in section
        assert "landing" in section.lower() and "close" in section.lower()
        # The shared hold it replaces is gone from this surface.
        assert "Hold that straight-on selfie framing" not in section

    def test_the_hook_move_condensed_twin_carries_the_same_rule(self):
        section = gp.camera_move_section(
            _strategy(), condensed=True, hook_surface=True)
        assert "Start wide" in section
        assert "never open on a face filling the frame" in section.lower()
        assert "Hold that straight-on selfie framing" not in section

    def test_the_default_move_is_unchanged(self):
        section = gp.camera_move_section(_strategy())
        assert "Hold that straight-on selfie framing" in section
        assert "START WIDE" not in section

    def test_a_fixed_strategy_keeps_the_fixed_move_even_for_a_hook(self):
        section = gp.camera_move_section(_strategy("fixed"), hook_surface=True)
        assert "Camera stays locked" in section
        assert "START WIDE" not in section


class TestHookRenderPrompt:
    def test_a_hook_prompt_starts_wide_in_both_budget_modes(self):
        for budget in (None, 4090):
            prompt = _segment_prompt(
                {"hook_seconds": 3, "surface": "hook_cta"}, budget)
            assert "start wide" in prompt.lower()
            assert "Hold that straight-on selfie framing" not in prompt
            # The surface's standing rules ride along untouched.
            assert "FOR THIS HOOK, THE OPENING IS PHYSICAL" in prompt or \
                "This hook opens on its physical gesture" in prompt

    def test_a_wizard_prompt_keeps_the_hold_and_never_starts_wide(self):
        for budget in (None, 4090):
            prompt = _segment_prompt({"hook_seconds": 3}, budget)
            assert "straight-on selfie framing" in prompt
            assert "start wide" not in prompt.lower()
