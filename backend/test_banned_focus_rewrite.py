"""Regression: single-word bans never surface as CHECKS errors.

Red: _contains did substring matching (so "focused" flagged "focus"),
and generate_video_strategy failed loudly on a banned claim instead of
rewriting it — the founder approved words, then met "generation blocked".
Green: word-boundary matching plus strategy retry, so both plan and
strategy rewrite the thought without the banned word.
"""

import asyncio

import claim_safety


def _run(coro):
    return asyncio.run(coro)


def test_single_word_ban_needs_whole_word():
    assert claim_safety.find_banned_violations("stay focused daily", ["focus"]) == []
    assert claim_safety.find_banned_violations("time to focus daily", ["focus"]) != []


def test_strategy_rewrites_banned_claim(monkeypatch):
    import ai_service

    calls = []

    def _strategy(hook_script, middle_script):
        return {
            "strategy_summary": "s", "audience_problem": "p",
            "emotional_triggers": ["t"], "hook_concept": "c",
            "hook_line": hook_script, "hook_promise": "p", "hook_action": "a",
            "messaging_pillars": ["m"], "primary_feature": "f",
            "desired_outcome": "o", "mechanism_beat": "mb",
            "payoff_beat": "pb", "differentiation_beat": "b",
            "scene": {"environment": "kitchen"},
            "performance": {"movement": "still"},
            "segments": [
                {"index": 0, "role": "hook", "seconds": 2,
                 "goal": "g", "script": hook_script, "action": "a"},
                {"index": 1, "role": "middle", "seconds": 13,
                 "goal": "g2", "script": middle_script, "action": "a2"},
            ],
        }

    bad = _strategy("Morning rush.", "This helps you focus daily.")
    good = _strategy("Morning rush.", "One prompt helped me start writing.")

    async def fake_chat_json(system_message, prompt, context, **kwargs):
        calls.append(prompt)
        return dict(bad if len(calls) == 1 else good)

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
    result = _run(ai_service.generate_video_strategy(
        profile={"brand_name": "V", "claims_banned": ["focus"]},
        template={"name": "T", "required_assets": ["character_reference"]},
        angle=None, objective="ease_daily_moment",
        hook_seconds=2, total_duration=15, tone="", brand_voice="",
        profile_feedback={}))
    assert len(calls) == 2, "strategy should retry, not fail loudly"
    assert "focus" not in result["segments"][1]["script"].lower()
