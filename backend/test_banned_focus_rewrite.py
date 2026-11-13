"""Blocking removed: wording never fails a draft or the render.

The word-boundary matcher is kept for the advisory helpers, but neither
the plan nor the strategy retries on wording — the draft is accepted as
written in a single attempt and the report always passes.
"""

import asyncio

import claim_safety


def _run(coro):
    return asyncio.run(coro)


def test_single_word_ban_needs_whole_word():
    assert claim_safety.find_banned_violations("stay focused daily", ["focus"]) == []
    assert claim_safety.find_banned_violations("time to focus daily", ["focus"]) != []


def test_strategy_accepts_banned_claim_without_retry(monkeypatch):
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

    async def fake_chat_json(system_message, prompt, context, **kwargs):
        calls.append(prompt)
        return dict(bad)

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
    result = _run(ai_service.generate_video_strategy(
        profile={"brand_name": "V", "claims_banned": ["focus"]},
        template={"name": "T", "required_assets": ["character_reference"]},
        angle=None, objective="ease_daily_moment",
        hook_seconds=2, total_duration=15, tone="", brand_voice="",
        verdict_feedback=None))
    assert len(calls) == 1, "wording never triggers a retry"
    assert "focus" in result["segments"][1]["script"].lower()
    report = claim_safety.build_safety_report(
        {"hook_line": "Morning rush.", "script": "This helps you focus daily.",
         "strategy": result},
        {"brand_name": "V", "claims_banned": ["focus"]},
    )
    assert report["passed"] is True
    assert report["blocking"] == []
