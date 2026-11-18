"""Template fit: the centre-word rationale and a scale that discriminates.

Two founder-visible failures from the Nov 14 / Nov 17 2026 screenshots,
pinned here against the pure scorer:

- A template titled "Reducing Stress with AI" carried the WHY IT FITS
  line "Puts 'with' at the centre of the piece" — the feature matcher
  kept the stop word "with" among its tokens and matched it against
  the template's name (ADR 0194).
- Every tailored template scored Fit 9/10 or 10/10 while every angle
  scored 3-4/10: the factors a tailored template earns merely by
  being generated for the profile (tailored, objective, category,
  structure affinity) summed to 9.5 of the 10 before any
  template-specific match was counted, so the specific matches that
  actually differ between cards could not move the number (ADR 0195).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from template_recommendations import score_template_for_angle

PROFILE = {
    "id": "prof-vocolens",
    "app_category": "Health & Fitness",
    "target_audience": "Adults with ADHD who think faster than they can type",
    "icp_segments": ["Adults with ADHD", "People who journal"],
    "problems_solved": [
        "Racing thoughts are lost before they can be written down",
        "Typing is too slow to capture thoughts in the moment",
    ],
    "core_features": [
        "Voice-first journaling with AI transcription",
        "Emotion naming from your own words",
    ],
}

ANGLE = {
    "kind": "problem_solution",
    "target_audience": "ADHD: speak instead of type — no blank page, "
                       "just talk through racing thoughts",
    "user_problem": "On Monday morning at an orchard gate, the person feels "
                    "thoughts outrun their hands and typing is too slow "
                    "before the day starts",
    "app_feature": "Voice-first journaling with AI transcription",
    "claims_to_respect": [],
}


def _tpl(name, category, slots, **overrides):
    base = {
        "name": name, "category": category, "objective": "educate_viewers",
        "brand_profile_id": "prof-vocolens",
        "app_categories": ["Health & Fitness"],
        "audiences": ["Adults with ADHD"],
        "required_assets": ["character_reference"],
        "opening_structure": "The person says, 'I will talk for sixty "
                             "seconds before the day starts.'",
        "middle_structure": "The video develops the interruption by "
                            "contrasting the slow typing habit with "
                            "speaking through racing thoughts.",
        "content_slots": slots,
        "review_status": "approved",
    }
    base.update(overrides)
    return base


def _score(template, angle=ANGLE, objective="educate_viewers"):
    return score_template_for_angle(template, PROFILE, angle, objective)


class TestCentreWord:
    def test_a_stop_word_is_never_the_centre(self):
        # The screenshot shape exactly: the only feature token the
        # template's name and slots contain is the stop word "with".
        result = _score(_tpl(
            "Reducing Stress with AI", "curiosity-gap",
            {"hook": "stress held in the body",
             "middle": "naming the feeling out loud"},
        ))
        assert result["matched"]["feature_keyword"] != "with"
        assert not any("'with'" in r for r in result["reasons"])
        assert not any("centre of the piece" in r for r in result["reasons"])

    def test_a_content_word_is_cited_when_one_matches(self):
        # The name still contains "with"; the slots carry the feature's
        # real content word. The citation must be the content word.
        result = _score(_tpl(
            "Reducing Stress with AI", "curiosity-gap",
            {"hook": "stress held in the body",
             "middle": "journaling the feeling out loud instead of typing"},
        ))
        assert result["matched"]["feature_keyword"] == "journaling"
        assert any("Puts 'journaling' at the centre of the piece" in r
                   for r in result["reasons"])

    def test_the_cited_word_is_deterministic(self):
        # The hit used to be picked by set iteration, so the same inputs
        # could cite different words on different runs.
        template = _tpl(
            "Effortless Self-Expression", "story",
            {"hook": "self-expression made easy",
             "middle": "journaling through voice, transcription included"},
        )
        first = _score(template)["matched"]["feature_keyword"]
        for _ in range(5):
            assert _score(template)["matched"]["feature_keyword"] == first
        assert first in ("journaling", "transcription")

    def test_a_feature_with_no_citable_word_falls_back_without_a_centre(self):
        # A feature named only "AI" has no content token to cite; when
        # the piece still names it, the rationale runs without a centre
        # rather than quoting a stop word or inventing one.
        angle = dict(ANGLE, app_feature="AI")
        result = _score(_tpl(
            "Reducing Stress with AI", "curiosity-gap",
            {"hook": "stress held in the body",
             "middle": "naming the feeling out loud, ai beside you"},
        ), angle=angle)
        assert not any("centre of the piece" in r for r in result["reasons"])
        assert any("main feature" in r for r in result["reasons"])



class TestFitDiscrimination:
    def _screenshot_set(self):
        return [
            _tpl("The Orchard Gate Pause That Interrupts Typing",
                 "pain-point-question",
                 {"hook": "typing habit interrupted",
                  "middle": "speaking through racing thoughts instead of typing"}),
            _tpl("Effortless Self-Expression", "story",
                 {"hook": "self-expression made easy",
                  "middle": "journaling through voice, effortlessly"}),
            _tpl("Reducing Stress with AI", "curiosity-gap",
                 {"hook": "stress held in the body",
                  "middle": "naming the feeling out loud"}),
        ]

    def test_tailored_templates_no_longer_bunch_at_the_top(self):
        scores = [_score(t)["score"] for t in self._screenshot_set()]
        # Before the rebalance this exact set scored 10.0 / 9.5 / 9.5:
        # nothing left for a founder to choose by.
        assert max(scores) - min(scores) >= 1.5
        assert all(s < 9.0 for s in scores)

    def test_a_template_matching_only_the_givens_scores_mid_scale(self):
        # Tailored + objective + category + affinity, and nothing that
        # is specific to THIS template: no audience overlap beyond the
        # fallback, no problem overlap, no feature hit, no scene gift.
        result = _score(_tpl(
            "Reducing Stress with AI", "curiosity-gap",
            {"hook": "stress held in the body",
             "middle": "naming the feeling out loud"},
        ))
        assert result["score"] <= 7.0

    def test_specific_matches_still_earn_the_top_of_the_scale(self):
        # The ceiling stays reachable — by the matches that differ
        # between templates, not by the givens alone.
        strong = _tpl(
            "The Orchard Gate Pause That Interrupts Typing",
            "pain-point-question",
            {"hook": "typing habit interrupted",
             "middle": "speaking through racing thoughts instead of typing"},
        )
        weak = _tpl(
            "Reducing Stress with AI", "curiosity-gap",
            {"hook": "stress held in the body",
             "middle": "naming the feeling out loud"},
        )
        assert _score(strong)["score"] > _score(weak)["score"]


# The angle these scale fixtures score against: its problem carries the
# stress tag, so the problem factor is in play, and its kind implies the
# cold_audience / scrollers funnel tags a template can meet.
SCALE_ANGLE = dict(
    ANGLE,
    user_problem="On Monday morning the person feels overwhelmed: "
                 "thoughts outrun their hands and typing is too slow",
)

STRONG = _tpl(
    "The Orchard Gate Pause", "pain-point-question",
    {"hook": "stress at the gate, overwhelmed before the day starts",
     "middle": "journaling the racing thoughts out loud"},
    audiences=["cold_audience"],
)
MID = _tpl(
    "Effortless Self-Expression", "pain-point-question",
    {"hook": "a quieter morning",
     "middle": "journaling through voice instead of typing"},
)
WEAK = _tpl(
    "A Calmer Start", "curiosity-gap",
    {"hook": "a calmer start",
     "middle": "naming the feeling out loud"},
    audiences=[],
)


class TestScaleDiscriminates:
    """ADR 0195: the same three tailored cards, before and after.

    Under the pre-0195 weights these fixtures scored 10 / 10 / 8.5 —
    the screenshot's bunching (10/9/9) reproduced: the givens alone
    (tailored 2.0 + objective 3.0 + category 2.5 + affinity 2.0)
    summed to 9.5, so the clamp ate whatever the specific matches
    added. Under the rebalanced weights the givens sum to 6.5 and
    the specifics (audience depth, problem depth, feature) carry
    the rest, so the cards separate.
    """

    def test_the_three_cards_spread_with_the_strongest_on_top(self):
        strong = _score(STRONG, angle=SCALE_ANGLE)["score"]
        mid = _score(MID, angle=SCALE_ANGLE)["score"]
        weak = _score(WEAK, angle=SCALE_ANGLE)["score"]
        assert strong == 10.0
        # MID: givens 6.5 + problem-foreground 0.5 + feature 1.0. Its
        # audience fallback and WEAK's affinity/audience fallbacks earn
        # nothing — the no-match fallbacks stopped paying (ADR 0195),
        # which is what drops WEAK from the sketched 6.0 to 5.0.
        assert mid == 8.0
        assert weak == 5.0
        assert strong > mid > weak
        assert strong - weak >= 3.0

    def test_a_givens_only_card_no_longer_sits_at_the_top(self):
        # WEAK earns every given (tailored, objective, category) and
        # no specific match at all. Before the rebalance that profile
        # scored 8.5-9.5; it must now read as the middling card it is.
        assert _score(WEAK, angle=SCALE_ANGLE)["score"] <= 6.5

    def test_identical_cards_tie(self):
        twin = dict(MID)
        assert _score(twin, angle=SCALE_ANGLE)["score"] == \
            _score(MID, angle=SCALE_ANGLE)["score"]
