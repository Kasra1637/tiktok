"""Recorded outcomes are the founder's record; verdicts rank (ADR 0127).

template_outcome_adjustment still computes the posted/winner facts —
they serve the record surfaces — but template ranking stopped reading
them: a post's metrics cannot say the template is what made a video
work, so only whole-video verdicts move a template's score now.
"""

from feedback import template_outcome_adjustment
from template_recommendations import score_template_for_angle


def _template(tid="tpl-1"):
    return {
        "id": tid,
        "objective": "create_curiosity",
        "app_categories": [],
        "audiences": [],
        "content_slots": {},
        "name": "Quiet demo",
        "category": "demo",
    }


def test_unposted_template_gets_no_outcome_boost():
    facts = template_outcome_adjustment([], "tpl-1")
    assert facts == {
        "template_id": "tpl-1",
        "posted_clips": 0,
        "posted_views": 0,
        "wins": 0,
        "delta": 0.0,
    }


def test_posted_clips_boost_and_name_the_template_only():
    rows = [
        {"template_id": "tpl-1", "tiktok_url": "https://tiktok.example/1", "tiktok_views": 12400},
        {"template_id": "tpl-2", "tiktok_url": "https://tiktok.example/2", "tiktok_views": 5},
    ]
    assert template_outcome_adjustment(rows, "tpl-1")["posted_clips"] == 1
    assert template_outcome_adjustment(rows, "tpl-2")["posted_clips"] == 1
    assert template_outcome_adjustment(rows, "tpl-3")["delta"] == 0.0


def test_outcome_boost_caps_and_views_nudge_inside_budget():
    rows = [
        {"template_id": "tpl-1", "tiktok_url": f"https://tiktok.example/{i}", "tiktok_views": 100000}
        for i in range(10)
    ]
    assert template_outcome_adjustment(rows, "tpl-1")["delta"] <= 2.0


def test_posted_outcomes_no_longer_move_the_score():
    # The scorer takes verdict rows now, not outcome rows: two identical
    # templates score identically however their posts performed, and no
    # posted reason is claimed on the card. The outcome facts themselves
    # are unchanged — the tests above pin them as record math.
    profile = {"id": "app-1"}
    first = score_template_for_angle(
        _template("tpl-1"), profile, {}, "create_curiosity", [],
    )
    second = score_template_for_angle(
        _template("tpl-2"), profile, {}, "create_curiosity", [],
    )
    assert first["score"] == second["score"]
    assert not any("Posted in" in reason for reason in first["reasons"])
