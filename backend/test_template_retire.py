"""Templates retire after repeated flops; plans see posted proof."""

from feedback import (
    build_profile_feedback_section,
    is_template_retired,
    summarize_profile_feedback,
    template_feedback_adjustment,
)
from template_recommendations import score_template_for_angle


def _template(tid="tpl-1"):
    return {
        "id": tid, "objective": "create_curiosity", "app_categories": [],
        "audiences": [], "content_slots": {}, "name": "Quiet demo",
        "category": "demo",
    }


def test_retired_after_two_flops_with_no_posts():
    feedback = template_feedback_adjustment(
        [{"event": "thumb_down", "step": "template", "template_id": "tpl-1"},
         {"event": "thumb_down", "step": "template", "template_id": "tpl-1"}],
        "tpl-1",
    )
    assert is_template_retired(feedback, {"posted_clips": 0, "wins": 0})
    result = score_template_for_angle(
        _template("tpl-1"), {"id": "app-1"}, {}, "create_curiosity",
        [{"event": "thumb_down", "step": "template", "template_id": "tpl-1"},
         {"event": "thumb_down", "step": "template", "template_id": "tpl-1"}], [],
    )
    assert result["retired"] is True
    assert any("Retired after repeated poor fit" in lim for lim in result["limitations"])


def test_post_revives_flopped_template():
    feedback = template_feedback_adjustment(
        [{"event": "thumb_down", "step": "template", "template_id": "tpl-1"},
         {"event": "thumb_down", "step": "template", "template_id": "tpl-1"}],
        "tpl-1",
    )
    assert not is_template_retired(feedback, {"posted_clips": 1, "wins": 0})


def test_plan_prompt_names_posted_performance():
    summary = summarize_profile_feedback(
        [], "",
        posted_rows=[{"tiktok_url": "https://tiktok.example/1", "tiktok_views": 5000}],
    )
    assert summary["posted_clips"] == 1
    assert summary["posted_views"] == 5000
    section = build_profile_feedback_section(summary)
    assert "Posted performance" in section
    assert "Reproduce what earned posts" in section
