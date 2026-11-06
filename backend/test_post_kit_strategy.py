"""The fresh-account hashtag strategy: 4 to 6 single-token tags, unique, no bait.

The strategy lives in two places by design: the prompt asks for the balanced
mix (problem anchor, community, one category), and `normalize_post_kit_hashtags`
is the gate that fails loudly when the reply steps off it. These tests pin
both halves — a prompt-only strategy drifts, and a validator without the
prompt burns billed calls on refused kits.
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ai_service


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
    return asyncio.run(ai_service.generate_post_kit(PROJECT, PROFILE))


def test_four_to_six_tags_are_accepted_and_normalized(monkeypatch):
    # Missing '#' and stray whitespace normalize; the tag itself stays as the
    # audience writes it (case is not the point, the token is).
    out = generate(
        monkeypatch,
        kit(["doomscrolling", " #productivitytok ", "#productivity", "#FocusTimer"]),
    )
    assert out["hashtags"] == [
        "#doomscrolling",
        "#productivitytok",
        "#productivity",
        "#FocusTimer",
    ]
    six = generate(
        monkeypatch,
        kit(
            [
                "#doomscrolling",
                "#phonehabits",
                "#productivitytok",
                "#deepwork",
                "#productivity",
                "#FocusTimer",
            ]
        ),
    )
    assert len(six["hashtags"]) == 6


@pytest.mark.parametrize(
    "tags, why",
    [
        (["#one", "#two", "#three"], "three tags is under the floor"),
        (["#a", "#b", "#c", "#d", "#e", "#f", "#g"], "seven tags is over the ceiling"),
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
            ["#doomscrolling", "#productivitytok", "#productivity", "#FocusTimer"]
        )
    )
    monkeypatch.setattr(ai_service, "_chat_json", chat)
    asyncio.run(ai_service.generate_post_kit(PROJECT, PROFILE))
    prompt = chat.call_args.kwargs["prompt"]
    # The mix the founder pays for is asked for in words: the specific
    # problem anchor, the community vocabulary, and one category tag.
    assert "4 to 6" in prompt
    assert "problem or behaviour" in prompt
    assert "community" in prompt
    assert "app-category" in prompt
    assert "#fyp" in prompt and "never allowed" in prompt
    schema = chat.call_args.kwargs["json_schema"]
    assert schema["properties"]["hashtags"]["minItems"] == 4
    assert schema["properties"]["hashtags"]["maxItems"] == 6
