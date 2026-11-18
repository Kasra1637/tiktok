"""The generator carries the craft rubric's lessons (ADR 0201).

The founder's order (Nov 18 2026): read what each Craft check category
says a pair must do to earn its points, then strengthen the GENERATION
prompts so future pairs close those gaps. The scorer does not change
(Kasra's standing order); these tests pin the new instructions in the
shared spoken-line block and in the two assembled prompts that carry it
(the plan and the strategy), the way test_hook_voice pins the older
rules. Each pin names the scorer payment it serves.
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai_service


def _block():
    return ai_service._spoken_line_rules_block()


def test_the_hook_names_its_cost_not_only_its_attempt():
    # Hook stopping power pays +3 for a cost or problem cue and Story
    # arc +2/+3 for the hook opening a problem; a bare trying-line
    # "states a situation" and earns neither — the founder's own pairs
    # scored exactly that evidence line on Nov 18 2026.
    block = _block()
    assert "THE COST RIDES ALONG" in block
    assert "states a situation" in block
    assert "I keep losing count" in block


def test_the_time_grounding_is_an_instruction_not_a_permission():
    # The hook's concrete anchor (+2) was earned only when a time
    # grounding happened to ride along; the block used to merely
    # permit one ("may ride along").
    block = _block()
    assert "A time grounding rides along" in block
    assert "may ride along" not in block
    # ADR 0182 stands untouched: the anchor is a time, never the place.
    assert "never the place" in block


def test_both_lines_must_be_finished_sentences():
    # Trust & compliance charges 3 points per unfinished sentence —
    # the two charges that capped the founder's 72/100 pair at F.
    # The plan prompt stated the rule; the shared block (and so the
    # strategy and the rewrites) never did.
    block = _block()
    assert "FINISHED SENTENCES" in block
    assert "full stop" in block
    assert "semicolon" in block
    assert "never an unfinished sentence" in block


def test_the_script_opens_inside_the_scene_and_answers_at_once():
    # Concreteness pays +2 for a place named anywhere in the pair, and
    # the hook may never name it (ADR 0182) — so the place lives in the
    # script's words. Story arc pays for the scene in the first
    # sentence and charges when the answer waits behind a preamble.
    block = _block()
    assert "at the bus stop" in block
    assert "at bus stop" in block  # named as the article-dropping shape to avoid
    assert "Looking back over my recent days" in block
    assert "opens in retrospect" in block
    assert "first sentence" in block


def test_sentences_stay_inside_one_breath():
    # Spoken naturalness charges 2 points per sentence past 18 words;
    # no prompt stated a word limit anywhere before this rule.
    block = _block()
    assert "18 words" in block
    assert "needs a breath" in block
    # The fronted modifier is written order: a scene phrase trailing
    # into a comma before the person arrives.
    assert "written order" in block


def test_the_payoff_is_never_a_vague_stand_in():
    # Concreteness and Story arc both charge for a vague stand-in
    # payoff; the plan's schema named the shapes, the shared block
    # only said "strongest concrete line".
    block = _block()
    assert "vague stand-in" in block
    assert "that vague sense" in block


def _run(coro):
    return asyncio.run(coro)


def test_the_plan_prompt_carries_the_new_rules(monkeypatch):
    captured = {}

    async def capture(system_message, prompt, context, **kwargs):
        captured["prompt"] = prompt
        return {
            "hook_line": "Naming what I felt never worked.",
            "script": "One sentence each night helped me understand the pattern.",
            "beat_timeline": [{"start": 0, "end": 3, "label": "hook", "text": "t"}],
            "visual_direction": "v", "demo_brief": "d",
            "voice_direction": "vd", "sound_direction": "sd", "claims_used": [],
        }

    monkeypatch.setattr(ai_service, "_chat_json", capture)
    _run(ai_service.generate_creative_plan(
        profile={"brand_name": "Journal"}, template={"name": "T", "hook_seconds": 3},
        duration_seconds=15,
    ))
    prompt = captured["prompt"]
    for rule in ("THE COST RIDES ALONG", "FINISHED SENTENCES", "18 words",
                 "at the bus stop", "vague stand-in"):
        assert rule in prompt, f"{rule!r} missing from the plan prompt"


def test_the_strategy_prompt_carries_the_new_rules(monkeypatch):
    captured = {}

    async def fake_chat_json(system_message, prompt, context, **kwargs):
        captured["prompt"] = prompt
        return {
            "strategy_summary": "s", "audience_problem": "p",
            "emotional_triggers": ["t"], "hook_concept": "c",
            "hook_line": "h", "hook_promise": "p", "hook_action": "a",
            "messaging_pillars": ["m"], "primary_feature": "f",
            "desired_outcome": "o", "mechanism_beat": "mb",
            "payoff_beat": "pb", "differentiation_beat": "b",
            "cta_strategy": "c", "scene": {"location": "kitchen"},
            "performance": {"movement": "still"},
            "segments": [{"index": 0, "role": "hook", "seconds": 5,
                          "goal": "g", "script": "s", "action": "a"}],
            "continuity_contract": {
                "established": [], "must_not_change": [], "do_not_repeat": [],
            },
        }

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
    _run(ai_service.generate_video_strategy(
        profile={"brand_name": "Sleeply"},
        template={"name": "T", "hook_seconds": 3},
        hook_seconds=3,
    ))
    prompt = captured["prompt"]
    for rule in ("THE COST RIDES ALONG", "FINISHED SENTENCES", "18 words",
                 "at the bus stop", "vague stand-in"):
        assert rule in prompt, f"{rule!r} missing from the strategy prompt"
