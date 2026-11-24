"""ADR 0317: a Fixed-camera conflict is caught where the strategy is
written, not at the render button.

The live failure (Nov 24 2026, request_id=dd5dc5ec1143): a Fixed
project's stored strategy carried a hook_action that leaned toward
the camera, and the first thing that ever checked it was the
submit-time guard — the founder met the refusal at Generate, for a
direction the app itself had written. These tests pin the
generation-time behaviour: one automatic repair, the field's other
content preserved, and the guard's own wording surfaced when the
repair cannot land. The submit-time guard itself is untouched.
"""

import asyncio

import pytest

import ai_service
from generation_planning import require_camera_setup_directions

# The live incident's direction, verbatim.
LEANING_HOOK_ACTION = (
    "Mid-exhale leaning toward camera with one hand already "
    "sweeping up from the counter"
)
# The same action with the lean gone: the exhale, the mid-motion
# opening and the hand sweep all survive.
STATIONARY_HOOK_ACTION = (
    "Mid-exhale, already in frame, with one hand already "
    "sweeping up from the counter"
)


def _raw_strategy(**overrides):
    strategy = {key: "x" for key in ai_service.REQUIRED_STRATEGY_KEYS}
    strategy.update({
        "scene": {},
        "performance": {},
        "segments": [
            {"seconds": 3, "goal": "g", "script": "A short hook line.",
             "action": "a"},
            {"seconds": 12, "goal": "g", "script": "A short middle line.",
             "action": "a"},
        ],
        "messaging_pillars": [],
        "emotional_triggers": [],
    })
    strategy.update(overrides)
    return strategy


def _patch_chat(monkeypatch, raw, repair):
    """Route the two model calls by context. `repair` may be a dict
    reply or an Exception to raise. Returns the captured calls."""
    calls = []

    async def fake_chat_json(system_message, prompt, context, **kwargs):
        calls.append({"context": context, "prompt": prompt, "kwargs": kwargs})
        if context == "Fixed camera strategy repair":
            if isinstance(repair, Exception):
                raise repair
            return repair
        return raw

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
    return calls


def _generate(**kwargs):
    return asyncio.run(ai_service.generate_video_strategy(
        profile={}, template={}, hook_seconds=3, total_duration=15, **kwargs,
    ))


class TestFixedCameraRepairAtGeneration:
    def test_a_leaning_hook_action_is_repaired_before_the_strategy_returns(
            self, monkeypatch):
        calls = _patch_chat(
            monkeypatch,
            _raw_strategy(hook_action=LEANING_HOOK_ACTION),
            {"rewritten": STATIONARY_HOOK_ACTION},
        )
        result = _generate(camera_setup="fixed")
        # The returned strategy — the one the endpoint stores — passes
        # the submit-time guard as written.
        require_camera_setup_directions(result)
        assert result["hook_action"] == STATIONARY_HOOK_ACTION
        assert len(calls) == 2
        repair_prompt = calls[1]["prompt"]
        # The repair instruction names the conflicting clause and the
        # Fixed contract it must satisfy.
        assert "leaning toward camera" in repair_prompt
        assert "stationary" in repair_prompt
        assert "head-to-mid-thigh" in repair_prompt

    def test_the_repair_preserves_the_fields_non_conflicting_content(
            self, monkeypatch):
        _patch_chat(
            monkeypatch,
            _raw_strategy(hook_action=LEANING_HOOK_ACTION),
            {"rewritten": STATIONARY_HOOK_ACTION},
        )
        result = _generate(camera_setup="fixed")
        # The hand sweep and the mid-motion exhale survive; only the
        # lean toward the camera is gone.
        assert "sweeping up from the counter" in result["hook_action"]
        assert "Mid-exhale" in result["hook_action"]
        assert "leaning toward camera" not in result["hook_action"]
        # Nothing else in the strategy was rewritten.
        assert result["hook_concept"] == "x"
        assert result["segments"][0]["action"] == "a"

    def test_a_conflicting_segment_action_is_repaired_in_place(
            self, monkeypatch):
        raw = _raw_strategy()
        raw["segments"][0]["action"] = LEANING_HOOK_ACTION
        calls = _patch_chat(
            monkeypatch, raw, {"rewritten": STATIONARY_HOOK_ACTION})
        result = _generate(camera_setup="fixed")
        require_camera_setup_directions(result)
        assert result["segments"][0]["action"] == STATIONARY_HOOK_ACTION
        assert "segments.0.action" in calls[1]["prompt"]

    def test_a_strategy_still_conflicting_after_one_repair_surfaces_the_guard(
            self, monkeypatch):
        calls = _patch_chat(
            monkeypatch,
            _raw_strategy(hook_action=LEANING_HOOK_ACTION),
            {"rewritten": "Leaning toward camera again, hand sweeping up"},
        )
        with pytest.raises(ValueError, match="Fixed camera conflicts with hook_action"):
            _generate(camera_setup="fixed")
        # Exactly one repair was attempted — no loop.
        assert len(calls) == 2

    def test_a_failed_repair_call_surfaces_the_original_conflict(
            self, monkeypatch):
        _patch_chat(
            monkeypatch,
            _raw_strategy(hook_action=LEANING_HOOK_ACTION),
            RuntimeError("provider down"),
        )
        with pytest.raises(ValueError, match="Fixed camera conflicts with hook_action"):
            _generate(camera_setup="fixed")

    def test_a_clean_fixed_strategy_spends_no_repair_call(self, monkeypatch):
        calls = _patch_chat(
            monkeypatch,
            _raw_strategy(hook_action=STATIONARY_HOOK_ACTION),
            {"rewritten": "unused"},
        )
        result = _generate(camera_setup="fixed")
        assert result["hook_action"] == STATIONARY_HOOK_ACTION
        assert len(calls) == 1

    def test_a_handheld_strategy_is_never_checked_or_repaired(
            self, monkeypatch):
        calls = _patch_chat(
            monkeypatch,
            _raw_strategy(hook_action=LEANING_HOOK_ACTION),
            {"rewritten": "unused"},
        )
        result = _generate(camera_setup="handheld")
        assert result["hook_action"] == LEANING_HOOK_ACTION
        assert len(calls) == 1
