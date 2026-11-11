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
    # The banned WORDING never triggers the hard editorial retry; this draft
    # scores 67 on craft, below the 80 bar, so exactly one script-only craft
    # correction runs (and keeps first draft, same words back).
    assert len(calls) == 2, calls[1][:200] if len(calls) > 1 else calls
    assert "CRAFT CORRECTION" in calls[1]
    assert "focus" in result["visual_direction"].lower()


def test_the_angle_bounds_reach_the_words_a_viewer_hears(monkeypatch):
    """
    "Bounded By" is the angle's own limit, so it has to bound the plan and the
    hook rewrite too — not just the template picker (ADR 0089). The claims are
    restated as a hard constraint, and never as a claim of their own.
    """
    import ai_service

    prompts = []

    async def fake_chat_json(system_message, prompt, context, **kwargs):
        prompts.append(prompt)
        return dict(_draft("Morning rush.", "One prompt helped me start."))

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
    angle = {
        "user_problem": "Naming a feeling fails.",
        "hook_promise": "The person types a word and deletes it.",
        "claims_to_respect": [
            "Reflections are suggestions, not a verdict",
            "Do not claim the app replaces therapy or professional care",
        ],
    }
    _run(ai_service.generate_creative_plan(
        profile={"brand_name": "V"}, template={"name": "T"}, angle=angle,
        objective="ease_daily_moment", duration_seconds=20))
    assert prompts, "no plan prompt was captured"
    assert "BOUNDED BY" in prompts[0]
    assert "Reflections are suggestions, not a verdict" in prompts[0]
    assert "Do not claim the app replaces therapy or professional care" in prompts[0]
