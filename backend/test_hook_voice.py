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

WEAK_HOOK = "Every week I look back and my mood shifts surprise me again."
WEAK_SCRIPT = (
    "In the garden stretching, I speak my days out loud and notice shifts tend "
    "to come after busy mornings. That surprise feels steadier, a rhythm I can spot."
)
STRONG_HOOK = "Bad moods weren't random. They followed busy mornings."
STRONG_SCRIPT = (
    "In the garden, I talked through my day. There it was again: flat afternoon, "
    "busy morning. Now I can name it, but not what sets it off."
)


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


def test_the_craft_block_states_statement_default_and_two_beats():
    block = ai_service._spoken_line_rules_block()
    assert "HOOK FORM" in block
    assert "silently ask" in block
    assert "confession" in block
    assert "observation" in block
    assert "Never default to a" in block
    assert "TWO BEATS MAX" in block
    assert "one concrete action, then one lingering thought" in block
    assert "Cut filler items" in block
    assert "problem, then insight, then the shift" in block


def test_question_hooks_are_an_issue_by_default():
    issues = issues_for("Why do Friday evenings always feel so off?")
    assert any("question" in issue for issue in issues)


def test_question_hooks_pass_only_when_plan_requests_question():
    allowed = ai_service._generated_spoken_issues(
        "Why do Friday evenings always feel so off?", SCRIPT, 60, 300,
        allows_question=True,
    )
    assert not any("question" in issue for issue in allowed)


def test_statement_hooks_pass_by_default():
    issues = issues_for("Friday evenings feel off, and the reason never has a name.")
    assert not any("question" in issue for issue in issues)


def test_question_format_request_is_detected_from_the_template():
    assert ai_service._plan_requests_question_format(
        {"name": "Pain-Point Question", "category": "pain-point-question",
         "opening_structure": "Ask the viewer's problem out loud as a question in the first 2 seconds."},
    )
    assert not ai_service._plan_requests_question_format(
        {"name": "Pattern Interrupt", "category": "pattern-interrupt",
         "opening_structure": "Open mid-motion on something unexpected, then resolve it into the product question."},
    )
    assert not ai_service._plan_requests_question_format(
        {"name": "Stop Doing This", "category": "contrarian",
         "opening_structure": "Tell the viewer to stop doing the thing they are doing."},
    )


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


def test_rewrite_retries_a_question_hook(monkeypatch):
    replies = [
        {"hook_line": "Why do Friday evenings always feel off?"},
        {"hook_line": "Friday evenings feel off, and the reason never has a name."},
    ]
    calls = []

    async def fake_chat(**kwargs):
        calls.append(kwargs)
        return replies[len(calls) - 1]

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    line = asyncio.run(ai_service.rewrite_hook_line({}, None, "Fridays feel off."))
    assert line == "Friday evenings feel off, and the reason never has a name."
    assert len(calls) == 2
    assert "CORRECTION" in calls[1]["prompt"]
    assert "question" in calls[1]["prompt"].lower()


def test_rewrite_allows_question_when_founder_hook_asks_for_one(monkeypatch):
    monkeypatch.setattr(
        ai_service,
        "_chat_json",
        AsyncMock(return_value={"hook_line": "Why do Friday evenings feel so heavy?"}),
    )
    line = asyncio.run(
        ai_service.rewrite_hook_line({}, None, "Why do Fridays feel so heavy?")
    )
    assert line == "Why do Friday evenings feel so heavy?"


def test_rewrite_corrects_an_unchanged_reply(monkeypatch):
    # A provider that hands the current hook back — here in quotes, which
    # the cleanup strips — has not refused the rewrite; it gets the same
    # one bounded correction a question or a diary open gets, instead of
    # failing the click on the spot.
    replies = [
        {"hook_line": '"Fridays feel off."'},
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
    assert "unchanged" in calls[1]["prompt"]


def test_rewrite_refuses_a_persistent_echo(monkeypatch):
    monkeypatch.setattr(
        ai_service,
        "_chat_json",
        AsyncMock(return_value={"hook_line": "Fridays feel off."}),
    )
    with pytest.raises(ai_service.RewriteRefusal, match="unchanged"):
        asyncio.run(ai_service.rewrite_hook_line({}, None, "Fridays feel off."))


def test_rewrite_prompt_names_the_exact_moment(monkeypatch):
    calls = []

    async def fake_chat(**kwargs):
        calls.append(kwargs)
        return {"hook_line": "Friday off-feelings never come with a reason."}

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    asyncio.run(ai_service.rewrite_hook_line(
        {}, None, "Mood flipped again halfway down this path today."))
    prompt = calls[0]["prompt"]
    assert "NAME THE MOMENT" in prompt
    assert "halfway down this path" in prompt
    assert "names the exact moment" in prompt


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
        "The reflection at the desk helped me name the feeling, and I left the entry calmer.",
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


def test_the_plan_loop_rewrites_a_question_hook(monkeypatch):
    bad = _plan(
        "Why do Friday evenings always feel so off?",
        "One prompt helped me start writing, and I finished the entry.",
    )
    good = _plan(
        "Friday evenings feel off, and the reason never has a name.",
        "The reflection at the desk helped me name the feeling, and I left the entry calmer.",
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
    assert "question" in calls[1]["prompt"].lower()


def test_the_plan_loop_allows_question_for_question_template(monkeypatch):
    good = _plan(
        "Why do Friday evenings always feel so off?",
        "One prompt helped me start writing, and I finished the entry.",
    )

    async def fake_chat(**kwargs):
        return good

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    result = asyncio.run(
        ai_service.generate_creative_plan(
            profile={"brand_name": "Journal"},
            template={
                "name": "Pain-Point Question",
                "category": "pain-point-question",
                "opening_structure": "Ask the viewer's problem out loud as a question in the first 2 seconds.",
                "hook_seconds": 3,
            },
            duration_seconds=15,
        )
    )
    assert result["hook_line"] == good["hook_line"]


def test_the_plan_loop_retries_a_hard_valid_but_craft_weak_draft(monkeypatch):
    weak = _plan(WEAK_HOOK, WEAK_SCRIPT)
    strong = _plan(STRONG_HOOK, STRONG_SCRIPT)
    calls = []

    async def fake_chat(**kwargs):
        calls.append(kwargs)
        return weak if len(calls) == 1 else strong

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    result = asyncio.run(
        ai_service.generate_creative_plan(
            profile={"brand_name": "Journal"},
            template={"name": "T", "hook_seconds": 3},
            duration_seconds=15,
        )
    )
    # The quality pass rewrites the script only: the hook is frozen byte-for-
    # byte, so the strong script lands under the weak hook rather than the
    # retry's own hook. The retry is targeted at the craft finding, not a
    # generic "try again".
    assert result["hook_line"] == WEAK_HOOK
    assert result["script"] == STRONG_SCRIPT
    assert len(calls) == 2
    assert "CRAFT CORRECTION" in calls[1]["prompt"]
    assert "Rewrite ONLY the script" in calls[1]["prompt"]
    assert "EXACTLY as written" in calls[1]["prompt"]


def test_a_craft_retry_never_refuses_the_plan(monkeypatch):
    weak = _plan(WEAK_HOOK, WEAK_SCRIPT)
    invalid = _plan(
        "I feel off and I cannot say why.",
        "I use the app every day and it changed my life.",
    )
    calls = []

    async def fake_chat(**kwargs):
        calls.append(kwargs)
        return weak if len(calls) == 1 else invalid

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    result = asyncio.run(
        ai_service.generate_creative_plan(
            profile={"brand_name": "Journal"},
            template={"name": "T", "hook_seconds": 3},
            duration_seconds=15,
        )
    )
    # The craft retry is advisory: a worse or invalid rewrite keeps the
    # hard-valid draft instead of failing a plan the founder can already use.
    assert result["hook_line"] == WEAK_HOOK
    assert result["script"] == WEAK_SCRIPT
    assert len(calls) == 2


def test_a_good_draft_gets_no_craft_retry(monkeypatch):
    good = _plan(STRONG_HOOK, STRONG_SCRIPT)
    calls = []

    async def fake_chat(**kwargs):
        calls.append(kwargs)
        return good

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    result = asyncio.run(
        ai_service.generate_creative_plan(
            profile={"brand_name": "Journal"},
            template={"name": "T", "hook_seconds": 3},
            duration_seconds=15,
        )
    )
    assert result["hook_line"] == STRONG_HOOK
    assert len(calls) == 1


# Kasra's reviewed pair (Nov 12): the rules already said the script never
# asks one, yet the plan shipped "What sets it off?" as its last line — and
# the line had drifted off the story (a mood label, not a trigger). The
# prompt rule alone drifted, so the ending is now an observable defect in
# the same list the hook's question has always been checked in.
KASRA_HOOK = "On this sidewalk, that generic label still felt wrong."
KASRA_SCRIPT_QUESTION_END = (
    "I changed it to worn out on this sidewalk after my evening walk. "
    "Now reflections sound like me, not wrong. What sets it off?"
)
KASRA_SCRIPT_STATEMENT_END = (
    "I changed it to worn out on this sidewalk after my evening walk. "
    "Now the words sound like me. I still don't know what sets it off."
)


def test_a_script_ending_on_a_question_is_an_issue():
    issues = issues_for(KASRA_HOOK, KASRA_SCRIPT_QUESTION_END)
    assert any("ends on a question" in issue for issue in issues)


def test_a_script_naming_the_unknown_as_a_statement_passes():
    # The discovery stays open — what is unknown is named in the story's
    # own terms — but as a statement, not a question.
    issues = issues_for(KASRA_HOOK, KASRA_SCRIPT_STATEMENT_END)
    assert not any("ends on a question" in issue for issue in issues)


def test_a_question_ending_without_its_mark_is_an_issue():
    # Subject-auxiliary inversion is question form even when the model
    # drops the mark: the sentence still asks.
    issues = issues_for(
        KASRA_HOOK,
        "I changed it to worn out after my evening walk. Can I say it out loud",
    )
    assert any("ends on a question" in issue for issue in issues)


def test_the_question_guard_is_scoped_to_the_ending():
    # A question in the middle is the prompt's business (the rules ban it
    # there too); the deterministic guard owns only the ending, where the
    # handoff to the demo lives.
    issues = issues_for(
        KASRA_HOOK,
        "What sets it off? I still do not know, and I keep walking.",
    )
    assert not any("ends on a question" in issue for issue in issues)


def test_the_craft_block_bans_the_apps_own_feature_nouns():
    block = ai_service._spoken_line_rules_block()
    assert "feature names" in block
    assert "reflections sound like me" in block
    assert "what I wrote" in block


def test_the_craft_block_treats_hook_and_script_as_one_text():
    block = ai_service._spoken_line_rules_block()
    assert "one text" in block
    assert "still felt wrong" in block
    assert "not wrong" in block


def test_the_craft_block_keeps_the_last_line_on_the_subject():
    block = ai_service._spoken_line_rules_block()
    assert "stays on the hook's own subject" in block
    assert "still unknown" in block
    assert "new topic" in block


def test_the_plan_loop_rewrites_a_question_ending_script(monkeypatch):
    bad = _plan(KASRA_HOOK, KASRA_SCRIPT_QUESTION_END)
    good = _plan(STRONG_HOOK, STRONG_SCRIPT)
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
    assert result["script"] == STRONG_SCRIPT
    assert len(calls) == 2
    # The correction names the defect, so the rewrite is targeted.
    assert "ends on a question" in calls[1]["prompt"]


def test_the_plan_loop_refuses_a_script_that_keeps_ending_on_a_question(monkeypatch):
    bad = _plan(KASRA_HOOK, KASRA_SCRIPT_QUESTION_END)
    calls = []

    async def fake_chat(**kwargs):
        calls.append(kwargs)
        return bad

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    with pytest.raises(RuntimeError):
        asyncio.run(
            ai_service.generate_creative_plan(
                profile={"brand_name": "Journal"},
                template={"name": "T", "hook_seconds": 3},
                duration_seconds=15,
            )
        )
    # The bounded editorial loop, no more: three attempts, then an honest
    # refusal instead of a shipped question.
    assert len(calls) == 3

