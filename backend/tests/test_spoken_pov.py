"""Live first-person POV: quoted, narrated or repeated hook words are defects.

Spoken contract (future generation only): the script is spoken live straight
to camera in first person. Quotation marks, stage directions ("I said
quietly"), quoting own words back as a past event, repeating the hook's words
or ideas, scene-setting before the answer, and vague payoffs ("a word",
"that vague sense") are failures of that contract, while the hook line itself
stays as written.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import ai_spoken
import creative_quality

import pytest


def _issues(script):
    return ai_spoken._generated_spoken_issues(
        "I can't write in my journal when thoughts race like this.",
        script,
        100,
        220,
    )


def test_script_with_quotation_marks_is_a_hard_issue():
    issues = _issues("On the porch, I say, 'Too much, too fast,' and it stays out of my head.")
    assert any("quotation" in issue.lower() for issue in issues), issues


def test_script_quoting_a_past_line_is_a_hard_issue():
    issues = _issues('I said quietly, "Too much, too fast," before opening the day.')
    assert any("quotation" in issue.lower() or "said" in issue.lower() for issue in issues), issues


@pytest.mark.parametrize(
    "script",
    [
        'On the porch, I say, "Too much, too fast," and it stays out of my head.',
        "On the porch, I say, \u201cToo much, too fast,\u201d and it stays out of my head.",
        "On the porch, I say, \u2018Too much, too fast,\u2019 and it stays out of my head.",
        "'Too much, too fast,' and it stays out of my head.",
    ],
)
def test_every_quote_form_is_flagged(script):
    issues = _issues(script)
    assert any("quotation" in issue.lower() for issue in issues), issues


def test_contraction_apostrophes_are_not_quotes():
    issues = _issues("I can't write in my journal when thoughts race like this.")
    assert not any("quotation" in issue.lower() for issue in issues), issues


def _plan_with_script(script):
    return {
        "hook_line": "Friday evenings feel off, and the reason never has a name.",
        "script": script,
        "beat_timeline": [
            {"start": 0, "end": 3, "label": "hook", "text": "hook"},
            {"start": 3, "end": 15, "label": "middle", "text": "middle"},
        ],
        "location": "porch",
        "visual_direction": "v",
        "demo_brief": "d",
        "voice_direction": "vd",
        "sound_direction": "sd",
        "claims_used": [],
    }


def _fake_plan(monkeypatch, script):
    import ai_service
    calls = []

    async def fake_chat(*, system_message, prompt, context, **kwargs):
        result = _plan_with_script(script)
        calls.append(prompt)
        # The craft correction asks the model again; keep insisting on quotes
        # so the keep-best path has to prove the first salvaged draft survives.
        return dict(result)

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    return calls


def test_persistent_quotes_still_ship_a_quote_free_plan(monkeypatch):
    import asyncio
    import ai_service
    quoted = "At the desk, I say, 'Too much, too fast,' and the entry finally steadies for the morning."
    _fake_plan(monkeypatch, quoted)
    result = asyncio.run(ai_service.generate_creative_plan(
        profile={"brand_name": "Journal"},
        template={"name": "T", "hook_seconds": 3},
        duration_seconds=15,
    ))
    assert "Too much, too fast" in result["script"]
    assert not ai_spoken._has_quoted_span(result["script"]), result["script"]


def test_non_quote_hard_issue_still_refuses(monkeypatch):
    import asyncio
    import ai_service
    _fake_plan(monkeypatch, "I lean against the railing and stare into the camera before speaking.")
    with pytest.raises(RuntimeError, match="complete, fitting spoken"):
        asyncio.run(ai_service.generate_creative_plan(
            profile={"brand_name": "Journal"},
            template={"name": "T", "hook_seconds": 3},
            duration_seconds=15,
        ))


def test_script_stage_direction_is_a_hard_issue():
    issues = _issues("I lean against the railing and stare into the camera before speaking.")
    assert any(
        ("stage" in issue.lower() or "narrat" in issue.lower() or "camera" in issue.lower())
        for issue in issues
    ), issues


def test_script_restating_the_hook_is_flagged_in_the_story_check():
    check = ai_spoken.check_spoken_story(
        "I can't write in my journal when thoughts race like this.",
        "I can't write in my journal when thoughts race like this. I speak the racing thought aloud.",
        hook_seconds=3,
        total_seconds=15,
    )
    story = check["story"]
    assert story.get("repeats_hook_words") is True, story
    assert story.get("restates_hook") is True, story


def test_script_that_answers_in_the_first_clause_is_flagged():
    check = ai_spoken.check_spoken_story(
        "I can't write in my journal when thoughts race like this.",
        "Then I say it out loud on the porch, and the blank page loses its grip.",
        hook_seconds=3,
        total_seconds=15,
    )
    assert check["story"].get("answers_hook_first_clause") is True, check["story"]


def test_quoted_script_scores_below_a_direct_script():
    quoted = creative_quality.assess_spoken_quality(
        "I can't write in my journal when thought race like this.",
        "On the porch, I say, 'Too much, too fast,' and it stays out of my head.",
        hook_seconds=3,
        total_seconds=15,
    )
    direct = creative_quality.assess_spoken_quality(
        "I can't write in my journal when thoughts race like this.",
        "Then I say it out loud on the porch, and the blank page loses its grip.",
        hook_seconds=3,
        total_seconds=15,
    )
    assert quoted["total"] < direct["total"], (quoted["total"], direct["total"])


def test_craft_retry_targets_eighty_and_freezes_the_hook():
    import ai_service
    assert ai_service.CRAFT_RETRY_BELOW == 80
    report = creative_quality.assess_spoken_quality(
        "I can't write in my journal when thoughts race like this.",
        "On the porch, I say, 'Too much, too fast,' and it stays out of my head.",
        hook_seconds=3,
        total_seconds=15,
    )
    block = ai_service._craft_retry_block(
        {
            "hook_line": "I can't write in my journal when thoughts race like this.",
            "script": "On the porch, I say, 'Too much, too fast,' and it stays out of my head.",
        },
        report,
    )
    assert "Rewrite ONLY the script" in block, block[:400]
    assert "EXACTLY as written" in block, block[:400]
    assert "including BOTH" not in block, block[:800]


def test_vague_payoff_is_penalized():
    vague = creative_quality.assess_spoken_quality(
        "I can't write in my journal when thoughts race like this.",
        "Then I call it a word, and that vague sense is gone.",
        hook_seconds=3,
        total_seconds=15,
    )
    specific = creative_quality.assess_spoken_quality(
        "I can't write in my journal when thoughts race like this.",
        "Then I call it a word, and the morning kettle clicks off by the porch rail.",
        hook_seconds=3,
        total_seconds=15,
    )
    assert vague["total"] < specific["total"], (vague["total"], specific["total"])
