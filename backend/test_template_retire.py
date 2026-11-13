"""Templates retire after repeated flops; plans see posted proof."""

from feedback import (
    build_profile_feedback_section,
    is_template_retired,
    is_template_retired_by_verdicts,
    summarize_profile_feedback,
    template_feedback_adjustment,
    template_verdict_facts,
)
from template_recommendations import score_template_for_angle


def _template(tid="tpl-1"):
    return {
        "id": tid, "objective": "create_curiosity", "app_categories": [],
        "audiences": [], "content_slots": {}, "name": "Quiet demo",
        "category": "demo",
    }


def _verdict_row(verdict, template_id="tpl-1"):
    return {"verdict": verdict, "bundle": {"opening_visual": {
        "template_id": template_id, "template_version": 3}}}


def test_retired_after_two_flops_with_no_posts():
    feedback = template_feedback_adjustment(
        [{"event": "thumb_down", "step": "template", "template_id": "tpl-1"},
         {"event": "thumb_down", "step": "template", "template_id": "tpl-1"}],
        "tpl-1",
    )
    assert is_template_retired(feedback, {"posted_clips": 0, "wins": 0})


def test_post_revives_flopped_template():
    feedback = template_feedback_adjustment(
        [{"event": "thumb_down", "step": "template", "template_id": "tpl-1"},
         {"event": "thumb_down", "step": "template", "template_id": "tpl-1"}],
        "tpl-1",
    )
    assert not is_template_retired(feedback, {"posted_clips": 1, "wins": 0})


def test_retired_after_two_didnt_work_verdicts_and_none_worked():
    # The ranking's retirement reads whole-video verdicts now (ADR 0127):
    # two finished videos that didn't work, and none that did, retire the
    # template in the presented order.
    facts = template_verdict_facts(
        [_verdict_row("down"), _verdict_row("down")], "tpl-1")
    assert is_template_retired_by_verdicts(facts)
    result = score_template_for_angle(
        _template("tpl-1"), {"id": "app-1"}, {}, "create_curiosity",
        [_verdict_row("down"), _verdict_row("down")],
    )
    assert result["retired"] is True
    assert any("Retired after repeated" in lim for lim in result["limitations"])


def test_a_worked_verdict_revives_a_flopped_template():
    facts = template_verdict_facts(
        [_verdict_row("down"), _verdict_row("down"), _verdict_row("up")], "tpl-1")
    assert not is_template_retired_by_verdicts(facts)
    result = score_template_for_angle(
        _template("tpl-1"), {"id": "app-1"}, {}, "create_curiosity",
        [_verdict_row("down"), _verdict_row("down"), _verdict_row("up")],
    )
    assert result["retired"] is False


def test_thumbs_alone_no_longer_retire_a_template():
    # The record is kept, but ranking stopped reading it (ADR 0127): the
    # scorer takes verdict rows, so a thumbs-only history cannot retire.
    result = score_template_for_angle(
        _template("tpl-1"), {"id": "app-1"}, {}, "create_curiosity", [],
    )
    assert result["retired"] is False


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
