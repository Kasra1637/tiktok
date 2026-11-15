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
    # The hook pin rose from 10 when ADR 0145 landed: the sample hook is
    # first person with a time anchor, and that voice now earns points
    # instead of a diary tax. The pair stays generic on the other seven
    # dimensions — app behavior, written phrasing, a wrapped-up ending —
    # which is what keeps the total in the C band above.
    assert _dims(report)["hook_stopping_power"]["score"] <= 13
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


def test_first_person_hooks_outscore_third_person_reports():
    # Kasra's doctrine (ADR 0145): the strongest hooks speak in first
    # person — "After masking all day words in the quiet garden aren't
    # mine" — so the scorer rewards the anchored first-person voice
    # instead of taxing it as a diary. Same moment, same place; only the
    # voice differs.
    first = creative_quality.assess_spoken_quality(
        "After masking all day, words in the quiet garden aren't mine.",
        REWRITE_SCRIPT, hook_seconds=3, total_seconds=15,
    )
    third = creative_quality.assess_spoken_quality(
        "After masking all day, words in the quiet garden feel borrowed.",
        REWRITE_SCRIPT, hook_seconds=3, total_seconds=15,
    )

    assert (
        _dims(first)["hook_stopping_power"]["score"]
        > _dims(third)["hook_stopping_power"]["score"]
    )
    assert (
        _dims(first)["audience_truth"]["score"]
        > _dims(third)["audience_truth"]["score"]
    )


def test_cover_text_is_scored_with_the_hook():
    # The opening moment is the spoken hook plus the cover text together
    # (ADR 0145): a hook with no concrete anchor of its own gains the
    # anchor the cover carries, and the evidence says the cover brought it.
    hook = "The words for my feelings won't come again."
    bare = creative_quality.assess_spoken_quality(
        hook, REWRITE_SCRIPT, hook_seconds=3, total_seconds=15
    )
    covered = creative_quality.assess_spoken_quality(
        hook, REWRITE_SCRIPT, hook_seconds=3, total_seconds=15,
        cover_text="Friday morning, bakery queue, paper bag in hand",
    )

    assert (
        _dims(covered)["hook_stopping_power"]["score"]
        > _dims(bare)["hook_stopping_power"]["score"]
    )
    evidence = " ".join(_dims(covered)["hook_stopping_power"]["evidence"]).lower()
    assert "cover" in evidence
    assert covered["cover_text"]["scored_with_hook"] is True
    assert bare["cover_text"]["scored_with_hook"] is False


def test_bakery_and_felt_detail_count_as_concrete():
    # The cue lists grew the founder's real places and props (ADR 0145):
    # a bakery is a place the viewer can picture, and a paper bag in hand
    # is a felt detail — the generic stand-in earns neither.
    bakery = creative_quality.assess_spoken_quality(
        REWRITE_HOOK,
        "I queue in the bakery, warm paper bag in my hand, and talk it out.",
    )
    generic = creative_quality.assess_spoken_quality(
        REWRITE_HOOK,
        "I wait in the building, plain object in my hand, and talk it out.",
    )

    assert (
        _dims(bakery)["concreteness"]["score"]
        > _dims(generic)["concreteness"]["score"]
    )
    evidence = " ".join(_dims(bakery)["concreteness"]["evidence"]).lower()
    assert "place is named" in evidence


def test_story_arc_does_not_punish_the_open_ending():
    # Kasra's standing rule: the script ends on the strongest concrete
    # line that OPENS the discovery — the demo is the resolution. Story
    # arc must not pay a closed ending more than the open one (ADR 0145);
    # the two scripts below share every beat but the last line.
    open_script = (
        "In the garden, I talked through my day. There it was again: flat "
        "afternoon, busy morning. I can see the pattern clear as day, "
        "but not what sets it off."
    )
    closed_script = (
        "In the garden, I talked through my day. There it was again: flat "
        "afternoon, busy morning. Now I finally know the answer and it is fixed."
    )
    opened = creative_quality.assess_spoken_quality(REWRITE_HOOK, open_script)
    closed = creative_quality.assess_spoken_quality(REWRITE_HOOK, closed_script)

    assert _dims(opened)["story_arc"]["score"] >= _dims(closed)["story_arc"]["score"]
    assert (
        _dims(opened)["demo_handoff"]["score"]
        > _dims(closed)["demo_handoff"]["score"]
    )


def test_report_sums_to_its_total_and_exposes_one_next_step():
    report = creative_quality.assess_spoken_quality(
        SAMPLE_HOOK, SAMPLE_SCRIPT, hook_seconds=3, total_seconds=15
    )

    assert report["total"] == sum(d["score"] for d in _dims(report).values())
    assert report["max"] == 100
    assert report["next_steps"]
    assert all(dimension["next_step"] for dimension in _dims(report).values())
