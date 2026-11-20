"""The story's written layer (ADR 0228): plan text, screen text, kit copy.

A story plan is ONE generation — spoken lines, the big on-screen text and
the sticker plan together — because the three are written against each
other: the screen text must carry the whole message muted, the spoken
line is the second channel, and the stickers are the interaction the
render cannot carry. The screen text's caps are settled numbers (80
characters / 14 words, derived from TikTok's 5–10 words-per-second
pacing rule — research Q3/Q4), pinned here the way test_cover_text.py
pins the cover's.
"""
import asyncio

import pytest

HOOK = "I keep losing count again."
SCRIPT = "Saturday at the stall, the count holds."
SCREEN = "Losing count by the tomatoes again"
STICKERS = [
    {"platform": "both", "sticker": "poll",
     "wording": "Do you lose count too? — Yes / Every time",
     "placement": "lower third, above the caption zone"},
]

PROFILE = {
    "brand_name": "Voice Journal",
    "app_category": "Wellness",
    "brand_description": "Speak your journal entry instead of writing it.",
    "core_features": ["Voice entries"],
    "primary_use_cases": ["Winding down after work"],
    "problems_solved": ["Blank page dread"],
    "desired_outcomes": ["A clearer head"],
    "outcome_statements": [],
    "differentiation": "On-device only.",
    "known_limitations": "",
    "target_audience": "people too tired to write",
    "tone_voice": "plain and warm",
}

PROJECT = {
    "id": "story-1",
    "kind": "story",
    "story_type": "question_poll",
    "duration_seconds": 5,
    "camera_setup": "handheld",
    "location": "",
    "visual_direction": "",
    "content_angle": {
        "kind": "problem_solution",
        "label": "Losing count",
        "user_problem": "Losing count of the day by mid-afternoon",
        "hook_promise": "One spoken count that holds",
        "app_feature": "Voice entries",
        "desired_emotion": "relief",
        "viewer_outcome": "Keeping count without writing it down",
    },
}


def _stub_chat(monkeypatch, replies):
    import ai_service
    queue = list(replies)
    calls = []

    async def fake_chat(**kwargs):
        calls.append(kwargs)
        return queue.pop(0) if queue else {}

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    return calls


def _plan_reply(**overrides):
    reply = {
        "hook_line": HOOK,
        "script": SCRIPT,
        "screen_text": SCREEN,
        "hook_action": "Lifts the paper bag high and counts on raised fingers.",
        "middle_action": "Turns back to the stall, still counting quietly.",
        "location": "A market stall on Saturday afternoon",
        "sticker_plan": [dict(s) for s in STICKERS],
    }
    reply.update(overrides)
    return reply


# ------------------------------------------------------------ the caps

def test_story_text_caps_are_the_settled_numbers():
    import ai_service
    import story_types
    # Research-derived (plan section 6, Q3): the text reads whole inside
    # the shortest 3-second frame and stands alone muted.
    assert story_types.STORY_TEXT_MAX_CHARS == 80
    assert story_types.STORY_TEXT_MAX_WORDS == 14
    assert ai_service.STORY_TEXT_MAX_CHARS == 80
    assert ai_service.STORY_TEXT_MAX_WORDS == 14


def test_story_text_rules_carry_the_caps_and_the_muted_rule():
    import ai_service
    block = ai_service._story_text_rules_block()
    assert "80 characters" in block
    assert "14 words" in block
    # Sound-off first is the format's core writing rule: the text carries
    # the whole message alone, the spoken line is the second channel.
    assert "sound off" in block
    # Same family as the cover rules: first person, the moment up front,
    # the answer withheld — and a second angle, never a copy of the hook.
    assert "First person" in block
    assert "withholds the resolution" in block
    assert "never a copy of the spoken hook" in block
    # The text is a native sticker placed at posting, never burned in.
    assert "native text sticker" in block


# ------------------------------------------------------- the plan call

def test_generate_story_plan_returns_the_whole_written_layer(monkeypatch):
    import ai_service
    _stub_chat(monkeypatch, [_plan_reply()])
    out = asyncio.run(ai_service.generate_story_plan(dict(PROJECT), dict(PROFILE)))
    assert out["hook_line"] == HOOK
    assert out["script"] == SCRIPT
    assert out["screen_text"] == SCREEN
    assert out["sticker_plan"] == STICKERS
    assert out["story_type"] == "question_poll"
    assert out["frame_seconds"] == 5
    assert out["hook_action"]
    assert out["location"] == "A market stall on Saturday afternoon"


def test_story_plan_prompt_carries_both_rule_blocks_and_the_budget(monkeypatch):
    import ai_service
    calls = _stub_chat(monkeypatch, [_plan_reply()])
    asyncio.run(ai_service.generate_story_plan(dict(PROJECT), dict(PROFILE)))
    prompt = calls[0]["prompt"]
    # The shared spoken-line craft, unchanged, plus the story text rules.
    assert "SPOKEN LINE CRAFT" in prompt
    assert "80 characters" in prompt
    # The frame's spoken budget, from the app's own ruler: a 5s frame
    # holds spoken_budget(5) characters across both lines.
    assert str(ai_service.spoken_budget(5)) in prompt
    # The hook's move lands inside the first second — tighter than the
    # hook video's first-two-seconds rule.
    assert "first second" in prompt
    # Grounded in the profile facts and the picked angle.
    assert "Voice Journal" in prompt
    assert "Losing count of the day" in prompt


def test_story_plan_corrects_an_over_cap_screen_text(monkeypatch):
    import ai_service
    long_text = " ".join(["word"] * 15)  # 15 words, past the 14-word cap
    calls = _stub_chat(monkeypatch, [
        _plan_reply(screen_text=long_text), _plan_reply(),
    ])
    out = asyncio.run(ai_service.generate_story_plan(dict(PROJECT), dict(PROFILE)))
    assert out["screen_text"] == SCREEN
    assert len(calls) == 2
    assert "CORRECTION" in calls[1]["prompt"]


def test_story_plan_refuses_a_screen_text_that_stays_over_cap(monkeypatch):
    import ai_service
    long_text = "x" * 81  # one character past the cap, one word
    _stub_chat(monkeypatch, [
        _plan_reply(screen_text=long_text), _plan_reply(screen_text=long_text),
    ])
    with pytest.raises(RuntimeError, match="screen text"):
        asyncio.run(ai_service.generate_story_plan(dict(PROJECT), dict(PROFILE)))


def test_story_plan_prompt_carries_the_word_budget(monkeypatch):
    import ai_service
    calls = _stub_chat(monkeypatch, [_plan_reply()])
    asyncio.run(ai_service.generate_story_plan(dict(PROJECT), dict(PROFILE)))
    prompt = calls[0]["prompt"]
    # ADR 0238: a 5s frame holds one spoken line of at most 12 words —
    # the budget is instructed, not just enforced after the fact.
    assert "at most 12 WORDS" in prompt


def test_story_plan_corrects_spoken_lines_over_the_word_budget(monkeypatch):
    import ai_service
    long_hook = "I keep losing count by the second bag again today."
    long_script = (
        "Saturday afternoon at the market stall I say it out loud "
        "once more before I buy anything at all."
    )
    calls = _stub_chat(monkeypatch, [
        _plan_reply(hook_line=long_hook, script=long_script), _plan_reply(),
    ])
    out = asyncio.run(ai_service.generate_story_plan(dict(PROJECT), dict(PROFILE)))
    assert out["hook_line"] == HOOK
    assert len(calls) == 2
    assert "CORRECTION" in calls[1]["prompt"]
    assert "12 words" in calls[1]["prompt"]


def test_story_plan_refuses_spoken_lines_that_stay_over_the_word_budget(monkeypatch):
    import ai_service
    long_hook = "I keep losing count by the second bag again today."
    long_script = (
        "Saturday afternoon at the market stall I say it out loud "
        "once more before I buy anything at all."
    )
    _stub_chat(monkeypatch, [
        _plan_reply(hook_line=long_hook, script=long_script),
        _plan_reply(hook_line=long_hook, script=long_script),
    ])
    with pytest.raises(RuntimeError, match="spoken lines"):
        asyncio.run(ai_service.generate_story_plan(dict(PROJECT), dict(PROFILE)))


def test_story_plan_word_budget_scales_with_the_frame(monkeypatch):
    import ai_service
    # A 3s question/poll frame holds 7 words: the settled 5s pair
    # (12 words) is already too long there, and is refused after one
    # correction rather than stored.
    project = {**PROJECT, "duration_seconds": 3}
    _stub_chat(monkeypatch, [_plan_reply(), _plan_reply()])
    with pytest.raises(RuntimeError, match="7 words"):
        asyncio.run(ai_service.generate_story_plan(project, dict(PROFILE)))


def test_story_plan_refuses_an_unknown_story_type():
    import ai_service
    with pytest.raises(RuntimeError, match="story type"):
        asyncio.run(ai_service.generate_story_plan(
            {**PROJECT, "story_type": "testimonial"}, dict(PROFILE)))


def test_story_plan_normalizes_the_sticker_plan(monkeypatch):
    import ai_service
    _stub_chat(monkeypatch, [_plan_reply(sticker_plan=[
        {"platform": "Instagram", "sticker": "Countdown",
         "wording": "Launch day — May 3", "placement": "top third"},
        {"platform": "carrier pigeon", "sticker": "", "wording": "", "placement": ""},
        {"sticker": "poll", "wording": "Yes / No"},
    ])])
    out = asyncio.run(ai_service.generate_story_plan(dict(PROJECT), dict(PROFILE)))
    # Platforms normalize to the two the kit serves; an entry with no
    # sticker and no wording is not a plan entry and drops out.
    assert out["sticker_plan"] == [
        {"platform": "instagram", "sticker": "Countdown",
         "wording": "Launch day — May 3", "placement": "top third"},
        {"platform": "both", "sticker": "poll",
         "wording": "Yes / No", "placement": ""},
    ]


def test_story_plan_for_announcement_names_the_platform_asymmetry(monkeypatch):
    import ai_service
    calls = _stub_chat(monkeypatch, [_plan_reply()])
    project = {**PROJECT, "story_type": "announcement_countdown",
               "duration_seconds": 5, "countdown_date": "May 3"}
    asyncio.run(ai_service.generate_story_plan(project, dict(PROFILE)))
    prompt = calls[0]["prompt"]
    # TikTok has no countdown sticker: the date rides the screen text and
    # the spoken line there; the sticker itself is Instagram-only.
    assert "Instagram" in prompt and "TikTok" in prompt
    assert "May 3" in prompt


# ------------------------------------------------------------ the kit

def test_generate_story_kit_ships_the_accepted_text_verbatim(monkeypatch):
    import ai_service
    _stub_chat(monkeypatch, [{"caption": "Losing count by the tomatoes, again."}])
    project = {
        **PROJECT, "hook_line": HOOK, "script": SCRIPT,
        "screen_text": SCREEN, "sticker_plan": [dict(s) for s in STICKERS],
    }
    kit = asyncio.run(ai_service.generate_story_kit(
        project, dict(PROFILE), {"id": "gen-1"}))
    assert kit["caption"] == "Losing count by the tomatoes, again."
    # The accepted screen text, word for word — it is the founder's
    # sticker, not a fresh draft.
    assert kit["screen_text"] == SCREEN
    assert kit["sticker_plan"] == STICKERS
    assert kit["story_type"] == "question_poll"
    # The checklist is settled guidance, written in code: the native
    # sticker placement and the one-or-two-a-day cadence.
    joined = " ".join(kit["checklist"])
    assert "native text sticker" in joined
    assert "one or two" in joined.lower()


def test_story_kit_checklist_names_the_link_sticker_instagram_only(monkeypatch):
    import ai_service
    _stub_chat(monkeypatch, [{"caption": "The full one is up."}])
    project = {
        **PROJECT, "story_type": "hook_teaser", "hook_line": HOOK,
        "script": SCRIPT, "screen_text": SCREEN,
        "sticker_plan": [dict(s) for s in STICKERS],
    }
    kit = asyncio.run(ai_service.generate_story_kit(
        project, dict(PROFILE), {"id": "gen-1"}))
    joined = " ".join(kit["checklist"])
    # ADR 0238: TikTok Stories has no link sticker — the kit says the
    # step is Instagram-only and points TikTok viewers at the profile.
    assert "Instagram-only" in joined
    assert "TikTok has no link sticker" in joined
    assert "profile" in joined


def test_story_kit_checklist_names_the_countdown_sticker_instagram_only(monkeypatch):
    import ai_service
    _stub_chat(monkeypatch, [{"caption": "Launch day is coming."}])
    project = {
        **PROJECT, "story_type": "announcement_countdown", "hook_line": HOOK,
        "script": SCRIPT, "screen_text": SCREEN,
        "sticker_plan": [dict(s) for s in STICKERS],
    }
    kit = asyncio.run(ai_service.generate_story_kit(
        project, dict(PROFILE), {"id": "gen-1"}))
    joined = " ".join(kit["checklist"])
    # ADR 0238: TikTok Stories has no countdown sticker either — the
    # date goes in the text sticker there instead.
    assert "Instagram-only" in joined
    assert "TikTok has no countdown sticker" in joined
    assert "text sticker" in joined


def test_story_kit_caption_carries_no_hashtag_machinery(monkeypatch):
    import ai_service
    calls = _stub_chat(monkeypatch, [
        {"caption": "Losing count again #journal #adhd"},
        {"caption": "Losing count again #journal #adhd"},
    ])
    project = {
        **PROJECT, "hook_line": HOOK, "script": SCRIPT,
        "screen_text": SCREEN, "sticker_plan": [dict(s) for s in STICKERS],
    }
    with pytest.raises(RuntimeError, match="hashtag"):
        asyncio.run(ai_service.generate_story_kit(
            project, dict(PROFILE), {"id": "gen-1"}))
    # One correction was offered, naming the rule, before the refusal.
    assert "CORRECTION" in calls[1]["prompt"]


def test_story_kit_refuses_without_an_accepted_screen_text():
    import ai_service
    project = {**PROJECT, "hook_line": HOOK, "script": SCRIPT, "screen_text": ""}
    with pytest.raises(RuntimeError, match="screen text"):
        asyncio.run(ai_service.generate_story_kit(
            project, dict(PROFILE), {"id": "gen-1"}))


# ------------------------------------------------------- the craft check

def test_story_craft_check_passes_a_sound_plan():
    import creative_quality
    report = creative_quality.assess_story_quality(
        HOOK, SCRIPT, SCREEN, STICKERS, frame_seconds=15)
    assert report["advisory"] is True
    assert report["passed"] == report["total"] == 4
    assert report["next_steps"] == []
    for check in report["checks"].values():
        assert check["passed"], check


def test_story_craft_check_flags_a_slow_opening():
    import creative_quality
    long_hook = (
        "I have been thinking about the way the whole afternoon keeps "
        "slipping away from me lately."
    )
    report = creative_quality.assess_story_quality(
        long_hook, SCRIPT, SCREEN, STICKERS, frame_seconds=15)
    assert not report["checks"]["first_second_hook"]["passed"]
    assert report["passed"] == 3
    assert any("first second" in step for step in report["next_steps"])


def test_story_craft_check_flags_text_that_cannot_stand_alone():
    import creative_quality
    report = creative_quality.assess_story_quality(
        HOOK, SCRIPT, "x" * 81, STICKERS, frame_seconds=15)
    assert not report["checks"]["screen_text_stands_alone"]["passed"]
    report = creative_quality.assess_story_quality(
        HOOK, SCRIPT, "", STICKERS, frame_seconds=15)
    assert not report["checks"]["screen_text_stands_alone"]["passed"]


def test_story_craft_check_flags_a_frame_packed_past_its_seconds():
    import creative_quality
    packed = " ".join(["This one sentence keeps going with more of the day in it."] * 6)
    report = creative_quality.assess_story_quality(
        HOOK, packed, SCREEN, STICKERS, frame_seconds=5)
    assert not report["checks"]["one_idea_per_frame"]["passed"]


def test_story_craft_check_flags_a_missing_sticker_plan():
    import creative_quality
    report = creative_quality.assess_story_quality(
        HOOK, SCRIPT, SCREEN, [], frame_seconds=15)
    assert not report["checks"]["sticker_plan_present"]["passed"]
    report = creative_quality.assess_story_quality(
        HOOK, SCRIPT, SCREEN, [{"platform": "both", "sticker": "", "wording": ""}],
        frame_seconds=15)
    assert not report["checks"]["sticker_plan_present"]["passed"]


# ------------------------------------------- the screen-text suggestion

SUGGEST_PROJECT = {
    "id": "story-1",
    "kind": "story",
    "story_type": "question_poll",
    "duration_seconds": 5,
    "hook_line": HOOK,
    "script": SCRIPT,
    "screen_text": SCREEN,
    "content_angle": dict(PROJECT["content_angle"]),
}

SUGGEST_PROFILE = {
    "brand_name": "Vocolens",
    "app_category": "Wellness",
    "brand_description": "Speak your journal entry instead of writing it.",
}


def test_suggest_story_screen_text_returns_a_fresh_text(monkeypatch):
    import ai_service
    _stub_chat(monkeypatch, [{"screen_text": "Counting tomatoes, losing count again"}])
    text = asyncio.run(
        ai_service.suggest_story_screen_text(dict(SUGGEST_PROJECT), dict(SUGGEST_PROFILE)))
    assert text == "Counting tomatoes, losing count again"
    assert len(text) <= 80 and len(text.split()) <= 14


def test_suggest_story_screen_text_prompt_carries_the_rules_block(monkeypatch):
    import ai_service
    calls = _stub_chat(monkeypatch, [{"screen_text": "Counting tomatoes, losing count again"}])
    asyncio.run(
        ai_service.suggest_story_screen_text(dict(SUGGEST_PROJECT), dict(SUGGEST_PROFILE)))
    prompt = calls[0]["prompt"]
    # The suggestion is written under the same rules block the plan's
    # screen text is written under (ADR 0228): the caps and the
    # sound-off rule ride along, beside the frame's own spoken words.
    assert "80 characters" in prompt and "14 words" in prompt
    assert "sound off" in prompt
    assert HOOK in prompt and SCRIPT in prompt and SCREEN in prompt


def test_suggest_story_screen_text_corrects_an_over_cap_reply(monkeypatch):
    import ai_service
    calls = _stub_chat(monkeypatch, [
        {"screen_text": "word " * 20},
        {"screen_text": "Counting tomatoes, losing count again"},
    ])
    text = asyncio.run(
        ai_service.suggest_story_screen_text(dict(SUGGEST_PROJECT), dict(SUGGEST_PROFILE)))
    assert text == "Counting tomatoes, losing count again"
    assert len(calls) == 2
    assert "CORRECTION" in calls[1]["prompt"]


def test_suggest_story_screen_text_refuses_a_reply_that_stays_over_cap(monkeypatch):
    import ai_service
    _stub_chat(monkeypatch, [
        {"screen_text": "word " * 20},
        {"screen_text": "word " * 20},
    ])
    with pytest.raises(ai_service.RewriteRefusal):
        asyncio.run(
            ai_service.suggest_story_screen_text(dict(SUGGEST_PROJECT), dict(SUGGEST_PROFILE)))


def test_suggest_story_screen_text_refuses_an_echo_of_the_current_text(monkeypatch):
    import ai_service
    _stub_chat(monkeypatch, [
        {"screen_text": SCREEN},
        {"screen_text": SCREEN},
    ])
    with pytest.raises(ai_service.RewriteRefusal):
        asyncio.run(
            ai_service.suggest_story_screen_text(dict(SUGGEST_PROJECT), dict(SUGGEST_PROFILE)))


def test_suggest_story_screen_text_refuses_a_copy_of_the_spoken_hook(monkeypatch):
    import ai_service
    _stub_chat(monkeypatch, [
        {"screen_text": HOOK},
        {"screen_text": HOOK},
    ])
    with pytest.raises(ai_service.RewriteRefusal):
        asyncio.run(
            ai_service.suggest_story_screen_text(dict(SUGGEST_PROJECT), dict(SUGGEST_PROFILE)))


def test_suggest_story_screen_text_refuses_a_fragment(monkeypatch):
    import ai_service
    # Fewer than three words is not a message a muted viewer can read
    # whole — the craft check's own floor for standing alone.
    _stub_chat(monkeypatch, [
        {"screen_text": "Losing count"},
        {"screen_text": "Losing count"},
    ])
    with pytest.raises(ai_service.RewriteRefusal):
        asyncio.run(
            ai_service.suggest_story_screen_text(dict(SUGGEST_PROJECT), dict(SUGGEST_PROFILE)))
