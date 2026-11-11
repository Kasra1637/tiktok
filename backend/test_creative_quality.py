"""Craft quality is advisory: it scores the spoken pair, never gates a render.

The seam is `creative_quality.assess_spoken_quality(hook, script, ...)`: a pure
function of the two spoken lines and their seconds. The tests assert bands and
relative improvement, not a magic total, so the rubric can be tuned without
turning the suite into a snapshot of its own arithmetic.
"""
import creative_quality

SAMPLE_HOOK = "Every week I look back and my mood shifts surprise me again."
SAMPLE_SCRIPT = (
    "In the garden stretching, I speak my days out loud and notice shifts tend "
    "to come after busy mornings. That surprise feels steadier, a rhythm I can spot."
)
REWRITE_HOOK = "Bad moods weren't random. They followed busy mornings."
REWRITE_SCRIPT = (
    "In the garden, I talked through my day. There it was again: flat afternoon, "
    "busy morning. Now I can name it, but not what sets it off."
)


def _dims(report):
    return report["dimensions"]


def test_sample_is_scored_as_competent_but_generic():
    report = creative_quality.assess_spoken_quality(
        SAMPLE_HOOK, SAMPLE_SCRIPT, hook_seconds=3, total_seconds=15
    )

    assert report["advisory"] is True
    assert 55 <= report["total"] <= 65
    assert report["grade"] == "C"
    assert report["band"] == "competent_but_generic"
    assert _dims(report)["hook_stopping_power"]["score"] <= 10
    assert _dims(report)["spoken_naturalness"]["score"] <= 5
    assert _dims(report)["demo_handoff"]["score"] <= 5
    assert _dims(report)["trust_compliance"]["score"] >= 8


def test_the_rewrite_improves_hook_naturalness_and_handoff():
    sample = creative_quality.assess_spoken_quality(
        SAMPLE_HOOK, SAMPLE_SCRIPT, hook_seconds=3, total_seconds=15
    )
    rewrite = creative_quality.assess_spoken_quality(
        REWRITE_HOOK, REWRITE_SCRIPT, hook_seconds=3, total_seconds=15
    )

    assert rewrite["total"] >= sample["total"] + 15
    assert _dims(rewrite)["hook_stopping_power"]["score"] >= 14
    assert _dims(rewrite)["spoken_naturalness"]["score"] >= 7
    assert _dims(rewrite)["demo_handoff"]["score"] >= 8


def test_promotion_and_personal_history_reduce_trust():
    report = creative_quality.assess_spoken_quality(
        "Download the app and try it free today.",
        "I use it every day and it changed my life.",
    )

    assert _dims(report)["trust_compliance"]["score"] <= 4
    assert report["grade"] == "F"
    assert report["band"] == "off_brief"
    evidence = " ".join(_dims(report)["trust_compliance"]["evidence"]).lower()
    assert "promotion" in evidence or "personal history" in evidence


def test_empty_lines_and_over_ceiling_are_reported():
    empty = creative_quality.assess_spoken_quality("", "")
    assert empty["total"] == 0
    assert all(dimension["score"] == 0 for dimension in _dims(empty).values())

    over = creative_quality.assess_spoken_quality(
        "x" * 61, "y" * 200, hook_seconds=3, total_seconds=12
    )
    assert _dims(over)["trust_compliance"]["score"] < 10
    evidence = " ".join(_dims(over)["trust_compliance"]["evidence"]).lower()
    assert "exceed" in evidence or "over" in evidence


def test_report_sums_to_its_total_and_exposes_one_next_step():
    report = creative_quality.assess_spoken_quality(
        SAMPLE_HOOK, SAMPLE_SCRIPT, hook_seconds=3, total_seconds=15
    )

    assert report["total"] == sum(d["score"] for d in _dims(report).values())
    assert report["max"] == 100
    assert report["next_steps"]
    assert all(dimension["next_step"] for dimension in _dims(report).values())
