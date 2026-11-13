"""Blocking removed: wording never fails a draft or the render.

No claim-safety system exists (ADR 0119): wording is never checked,
reported on, or refused anywhere in the app, so a strategy whose words
contain a profile's banned-listed word is accepted as written, in a
single attempt, with no retry.
"""

import asyncio


def _run(coro):
    return asyncio.run(coro)


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
