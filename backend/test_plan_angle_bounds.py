"""The angle's own bounds reach the words a viewer hears.

"Bounded By" (the angle's claims_to_respect) is data the founder set on the
angle, restated in the plan prompt as a hard constraint on what the spoken
words may promise — prompt guidance, not a checker: nothing scans or refuses
the result (ADR 0119 removed the claim-safety system; the bounds themselves
stay, ADR 0089).
"""

import asyncio


def _run(coro):
    return asyncio.run(coro)


def _draft(hook, script, visual="v"):
    return {
        "hook_line": hook, "script": script, "beat_timeline": [],
        "visual_direction": visual, "demo_brief": "Record once.",
        "voice_direction": "vd", "sound_direction": "sd",
    }


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
