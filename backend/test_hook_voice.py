"""The hook line speaks to the viewer, not as a diary: at most one 'I'.

The rule is the hook's alone — the middle is still the customer's own story —
and it is both asked for (the shared craft block) and enforced (the plan's
editorial loop and the rewrite's bounded correction), because a prompt-only
rule drifts and a gate without the prompt spends billed calls on refusals.
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai_service


SCRIPT = "One prompt helped me start writing and I finished the entry."


def issues_for(hook, script=SCRIPT):
    return ai_service._generated_spoken_issues(hook, script, 60, 300)


def test_two_first_person_hooks_are_an_issue():
    issues = issues_for("Friday evening, and I feel off, and I cannot say why.")
    assert any("first person" in issue for issue in issues)


def test_contractions_count_as_first_person():
    issues = issues_for("I'm off on Fridays and I can't say why.")
    assert any("first person" in issue for issue in issues)


def test_one_first_person_is_allowed():
    issues = issues_for("I can never say why Friday evenings feel off.")
    assert not any("first person" in issue for issue in issues)


def test_zero_first_person_is_the_target():
    issues = issues_for("Friday evenings feel off, and the reason never has a name.")
    assert not any("first person" in issue for issue in issues)


def test_the_body_may_stay_first_person():
    # The rule is the hook's opening; the middle is the customer's own story.
    issues = issues_for(
        "Friday evenings feel off, and the reason never has a name.",
        "I tried journaling for a week. I realised how often I circled the same thought.",
    )
    assert not any("first person" in issue for issue in issues)


def test_the_craft_block_states_the_rule():
    block = ai_service._spoken_line_rules_block()
    assert "at most ONCE" in block
    assert "diary" in block


def test_rewrite_retries_a_diary_open(monkeypatch):
    replies = [
        {"hook_line": "I feel off on Fridays and I cannot say why."},
        {"hook_line": "Friday off-feelings never come with a reason."},
    ]
    calls = []

    async def fake_chat(**kwargs):
        calls.append(kwargs)
        return replies[len(calls) - 1]

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    line = asyncio.run(ai_service.rewrite_hook_line({}, None, "Fridays feel off."))
    assert line == "Friday off-feelings never come with a reason."
    assert len(calls) == 2
    assert "CORRECTION" in calls[1]["prompt"]
    assert "first person" in calls[1]["prompt"]


def test_rewrite_refuses_replies_that_keep_narrating(monkeypatch):
    monkeypatch.setattr(
        ai_service,
        "_chat_json",
        AsyncMock(return_value={"hook_line": "I feel off on Fridays and I cannot say why."}),
    )
    with pytest.raises(RuntimeError, match="first person"):
        asyncio.run(ai_service.rewrite_hook_line({}, None, "Fridays feel off."))


def _plan(hook, script):
    return {
        "hook_line": hook,
        "script": script,
        "beat_timeline": [
            {"start": 0, "end": 3, "label": "hook", "text": hook},
            {"start": 3, "end": 15, "label": "middle", "text": script},
        ],
        "visual_direction": "A person reflecting at their desk.",
        "demo_brief": "Record the emotion suggestions.",
        "voice_direction": "Conversational.",
        "sound_direction": "Voice only.",
        "claims_used": [],
    }


def test_the_plan_loop_rewrites_a_diary_hook(monkeypatch):
    bad = _plan(
        "Friday evening, and I feel off, and I cannot say why.",
        "One prompt helped me start writing, and I finished the entry.",
    )
    good = _plan(
        "Friday evenings feel off, and the reason never has a name.",
        "The reflection helped me name the feeling, and I left the entry calmer.",
    )
    calls = []

    async def fake_chat(**kwargs):
        calls.append(kwargs)
        return bad if len(calls) == 1 else good

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    result = asyncio.run(
        ai_service.generate_creative_plan(
            profile={"brand_name": "Journal"},
            template={"name": "T", "hook_seconds": 3},
            duration_seconds=15,
        )
    )
    assert result["hook_line"] == good["hook_line"]
    assert len(calls) == 2
    # The correction names the defect, so the rewrite is targeted.
    assert "first person" in calls[1]["prompt"]
