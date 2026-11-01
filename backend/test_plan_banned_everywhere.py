"""Blocking removed: a banned word anywhere is accepted, never retried."""

import asyncio


def _run(coro):
    return asyncio.run(coro)


def _draft(hook, script, visual="v"):
    return {
        "hook_line": hook, "script": script, "beat_timeline": [],
        "visual_direction": visual, "demo_brief": "Record once.",
        "voice_direction": "vd", "sound_direction": "sd",
    }


def test_banned_word_in_direction_is_accepted(monkeypatch):
    import ai_service

    calls = []
    bad = _draft("Morning rush.", "One prompt helped me start.", visual="focus room")

    async def fake_chat_json(system_message, prompt, context, **kwargs):
        calls.append(prompt)
        return dict(bad)

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
    result = _run(ai_service.generate_creative_plan(
        profile={"brand_name": "V", "claims_banned": ["focus"]},
        template={"name": "T"}, objective="ease_daily_moment", duration_seconds=20))
    assert len(calls) == 1, "wording never triggers a retry"
    assert "focus" in result["visual_direction"].lower()
