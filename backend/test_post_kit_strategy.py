"""The fresh-account hashtag strategy: a researched five, or wording alone.

The strategy lives in three places by design (ADR 0139): the prompt asks
for a candidate pool (12 to 15 niche tags, relevance-ordered — the
problem anchor, the community vocabulary, one category tag),
`hashtag_volume` researches each candidate's post count and selects
exactly five by size (three small, two larger, nothing million-plus),
and `normalize_post_kit_hashtags` is the gate that fails loudly when the
final set steps off the shape rules. When the research cannot speak,
the pool's first five ship on wording alone. These tests pin all three
places — a prompt-only strategy drifts, and a validator without the
prompt burns billed calls on refused kits. The volume lookup is stubbed
to "no counts" here; test_hashtag_volume.py pins the research itself.
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai_service
import hashtag_volume


PROJECT = {
    "hook_line": "You do not have a focus problem.",
    "script": "You have too many lists, and every one of them asks for you.",
    "cta": "Clear one list by hand today.",
    "objective": "address_user_problem",
    "audience": "people with too many lists",
}
PROFILE = {
    "id": "app-1",
    "brand_name": "FocusTimer",
    "status": "approved",
    "brand_description": "One list, not eleven.",
    "app_category": "productivity",
    "target_audience": ["people with too many lists"],
    "claims_banned": ["cures ADHD"],
}
CAPTION = "I stopped fighting my phone and cleared one list instead \u2014 you?"


def kit(tags):
    return {"caption": CAPTION, "hashtags": tags, "cover_text": "One list, not eleven"}


def generate(monkeypatch, payload):
    monkeypatch.setattr(ai_service, "_chat_json", AsyncMock(return_value=payload))
    # No volume source in these tests: the research stays silent and the
    # wording-only fallback is what the assertions below exercise.
    monkeypatch.setattr(
        hashtag_volume, "lookup_hashtag_counts",
        AsyncMock(return_value={}),
    )
    return asyncio.run(ai_service.generate_post_kit(PROJECT, PROFILE))


def test_the_pool_is_accepted_and_the_fallback_takes_its_first_five(monkeypatch):
    # Missing '#' and stray whitespace normalize; the tag itself stays as the
    # audience writes it (case is not the point, the token is). With the
    # research silent, the kit ships the pool's first five in pool order.
    out = generate(
        monkeypatch,
        kit(
            [
                "doomscrolling",
                " #productivitytok ",
                "#productivity",
                "#FocusTimer",
                "#deepwork",
                "#phonehabits",
            ]
        ),
    )
    assert out["hashtags"] == [
        "#doomscrolling",
        "#productivitytok",
        "#productivity",
        "#FocusTimer",
        "#deepwork",
    ]


@pytest.mark.parametrize(
    "tags, why",
    [
        (["#one", "#two", "#three"], "three candidates cannot make five"),
        (["#fyp", "#viral", "#deep work", "#tren ding"], "no usable candidates at all"),
        (["#doomscrolling", "#DoomScrolling", "#productivitytok", "#productivity"], "a repeat"),
        (["#doomscrolling", "#fyp", "#productivitytok", "#productivity"], "#fyp bait"),
        (["#doomscrolling", "#viral", "#productivitytok", "#productivity"], "#viral bait"),
        (["#doomscrolling", "#deep work", "#productivitytok", "#productivity"], "a spaced tag"),
        (["#doomscrolling", "#fyp\u30b7", "#productivitytok", "#productivity"], "non-ascii"),
        (["#doomscrolling", "#" + "x" * 60, "#productivitytok", "#productivity"], "over 60 chars"),
    ],
)
def test_off_strategy_sets_fail_loudly(monkeypatch, tags, why):
    with pytest.raises(RuntimeError):
        generate(monkeypatch, kit(tags))


def test_the_prompt_states_the_strategy_and_the_schema_bounds_it(monkeypatch):
    chat = AsyncMock(
        return_value=kit(
            [
                "#doomscrolling",
                "#productivitytok",
                "#productivity",
                "#FocusTimer",
                "#deepwork",
            ]
        )
    )
    monkeypatch.setattr(ai_service, "_chat_json", chat)
    monkeypatch.setattr(
        hashtag_volume, "lookup_hashtag_counts",
        AsyncMock(return_value={}),
    )
    asyncio.run(ai_service.generate_post_kit(PROJECT, PROFILE))
    prompt = chat.call_args.kwargs["prompt"]
    # The pool the founder pays for is asked for in words: 12 to 15 niche
    # candidates, most relevant first — the specific problem anchor, the
    # community vocabulary, and one category tag — from which research
    # later selects the five by size.
    assert "12 to 15" in prompt
    assert "problem or behaviour" in prompt
    assert "community" in prompt
    assert "app-category" in prompt
    assert "#fyp" in prompt and "never allowed" in prompt
    schema = chat.call_args.kwargs["json_schema"]
    assert schema["properties"]["hashtags"]["minItems"] == 5
    assert schema["properties"]["hashtags"]["maxItems"] == 15
