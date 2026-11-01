"""Recorded outcomes lift template ranking within a small cap."""

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


def test_posted_template_outranks_identical_unposted_template():
    profile = {"id": "app-1"}
    posted = score_template_for_angle(
        _template("tpl-1"), profile, {}, "create_curiosity", [], [
            {"template_id": "tpl-1", "tiktok_url": "https://tiktok.example/1", "tiktok_views": 5000},
        ],
    )
    quiet = score_template_for_angle(_template("tpl-2"), profile, {}, "create_curiosity", [], [])
    assert posted["score"] > quiet["score"]
    assert any("Posted in 1 clip" in reason for reason in posted["reasons"])
