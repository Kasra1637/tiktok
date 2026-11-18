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
    # The hook pin sits at 10: ADR 0145's first-person payment moved to
    # its one home in Audience truth (ADR 0188), so the sample hook's
    # voice no longer lifts this category — and its wrapped-up ending
    # costs the handoff the same way. The pair stays generic on the
    # other dimensions — app behavior, written phrasing — which is what
    # keeps the total in the C band above.
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
    evidence = " ".join(_dims(report)["trust_compliance"]["evidence"]).lower()
    assert "promotion" in evidence or "personal history" in evidence
    # ADR 0202: Trust still scores and still counts toward the total,
    # but it no longer caps the grade. This pair's F comes from its
    # total (36) alone — the same letter the total would earn with a
    # clean Trust score — and no cap marker is attached.
    assert report["total"] < 40
    assert report["grade"] == "F"
    assert report["band"] == "off_brief"
    assert "capped_by" not in report


def test_a_low_trust_score_no_longer_caps_the_grade():
    # The founder's own panel, Nov 18 2026 (ADR 0202): eight category
    # scores of 16/12/10/7/6/7/10/4 — a 72 total — displayed as F
    # because Trust sat at 4, its two charges being unfinished
    # sentences. Kasra's ruling: "The whole grade should be
    # independent" — the grade is calculated from the eight
    # categories' total alone. The cover below carries the problem
    # cue and concrete anchor the panel's 16/20 hook score implies
    # (the opening is scored whole, ADR 0145).
    report = creative_quality.assess_spoken_quality(
        "I'm trying to say what's repeating instead of writing today",
        "Lately I felt low after lunch again and again, every day, and "
        "I still don't know how my count adds up over time",
        app_name="Vocolens",
        cover_text="Losing count again at lunch",
    )

    assert _dims(report)["trust_compliance"]["score"] == 4
    assert report["total"] == 72
    assert report["grade"] == "B"
    assert report["band"] == "strong"
    assert "capped_by" not in report


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
    # voice differs. Since ADR 0188 the reward has ONE home — Audience
    # truth, the customer-voice category — so the voice moves that
    # score alone: Hook stopping power reads the same moment either
    # way and scores the pair identically there.
    first = creative_quality.assess_spoken_quality(
        "After masking all day, words in the quiet garden aren't mine.",
        REWRITE_SCRIPT, hook_seconds=3, total_seconds=15,
    )
    third = creative_quality.assess_spoken_quality(
        "After masking all day, words in the quiet garden feel borrowed.",
        REWRITE_SCRIPT, hook_seconds=3, total_seconds=15,
    )

    assert (
        _dims(first)["audience_truth"]["score"]
        > _dims(third)["audience_truth"]["score"]
    )
    assert (
        _dims(first)["hook_stopping_power"]["score"]
        == _dims(third)["hook_stopping_power"]["score"]
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


def test_the_open_ending_is_paid_once_in_demo_handoff():
    # ADR 0188: the open ending used to earn in Story arc AND Demo
    # handoff, so one trait moved two scores. It now has one home —
    # Demo handoff, which owns the last line. Two scripts sharing every
    # beat but the ending therefore score the SAME story arc, and the
    # whole difference lands in the handoff.
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

    assert (
        _dims(opened)["story_arc"]["score"]
        == _dims(closed)["story_arc"]["score"]
    )
    assert (
        _dims(opened)["demo_handoff"]["score"]
        > _dims(closed)["demo_handoff"]["score"]
    )


def test_everyday_places_count_as_concrete():
    # ADR 0188: the cue lists stopped at rooms and furniture, so real
    # scripts set on the quad steps or a station platform scored as if
    # the scene were abstract. Both scripts below are the founder's
    # actual rendered lines; each names its in-between place, and the
    # platform script's announcement is a sound that grounds the scene.
    steps = creative_quality.assess_spoken_quality(
        REWRITE_HOOK,
        "I say it out loud on the quad steps after class on Thursday. "
        "That tight chest feeling is what I can tell a friend now.",
    )
    platform = creative_quality.assess_spoken_quality(
        REWRITE_HOOK,
        "I speak for sixty seconds while the announcement plays on the "
        "platform. On my Tuesday commute I still don't know what sets it off.",
    )

    for report in (steps, platform):
        evidence = " ".join(
            _dims(report)["concreteness"]["evidence"]).lower()
        assert "a place is named" in evidence
    assert _dims(platform)["concreteness"]["score"] >= 8


def test_report_sums_to_its_total_and_exposes_one_next_step():
    report = creative_quality.assess_spoken_quality(
        SAMPLE_HOOK, SAMPLE_SCRIPT, hook_seconds=3, total_seconds=15
    )

    assert report["total"] == sum(d["score"] for d in _dims(report).values())
    assert report["max"] == 100
    assert report["next_steps"]
    assert all(dimension["next_step"] for dimension in _dims(report).values())
