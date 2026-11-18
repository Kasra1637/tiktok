"""Angle fit reads the angle's grounding, not its rank (ADR 0193).

Across Kasra's Nov 14 / Nov 17 2026 screenshots every angle in a
set scored Fit 3/10 or 4/10. The number was computed in the
frontend from the angle's SUGGESTION RANK alone — a pure rank
transform floored at 3 — so for six untested angles it returned
{4,3,3,3,3,3} no matter what the angles said. The fit now comes
from the server, where the angle's grounding against the profile
is already resolved: `angle_content_fit` pays for a feature that
links to a real profile feature (exact, then unique near match —
the same two tiers `angle_grounding` certifies), an outcome that
is the certified one, and a problem and promise actually stated.
Rank plays no part in it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from angle_policy import angle_content_fit

PROFILE = {
    "id": "prof-vocolens",
    "core_features": [
        "Voice-first journaling with AI transcription",
        "Emotion naming from your own words",
        "Pattern timeline across entries",
    ],
    "outcome_statements": [
        {"from_feature": "Voice-first journaling with AI transcription",
         "outcome": "A clearer read on the day"},
    ],
    "desired_outcomes": ["A clearer read on the day", "Less stuck at night"],
}

FULL_PROBLEM = ("On Monday morning at an orchard gate, the person feels "
                "thoughts outrun their hands and typing is too slow")
FULL_PROMISE = ("The person at the orchard gate says the feeling out loud "
                "instead of typing it")


def _angle(**overrides):
    base = {
        "kind": "problem_solution",
        "app_feature": "Voice-first journaling with AI transcription",
        "viewer_outcome": "A clearer read on the day",
        "user_problem": FULL_PROBLEM,
        "hook_promise": FULL_PROMISE,
        "origin": "generated",
    }
    base.update(overrides)
    return base


class TestContentFit:
    def test_a_fully_grounded_angle_earns_the_top(self):
        fit = angle_content_fit(PROFILE, _angle())
        assert fit["score"] == 10
        assert "Voice-first journaling with AI transcription" in fit["basis"]

    def test_a_unique_near_match_scores_below_the_exact_link(self):
        fit = angle_content_fit(
            PROFILE, _angle(app_feature="voice journaling with AI transcription")
        )
        assert fit["score"] == 9

    def test_an_ungrounded_feature_loses_the_feature_points(self):
        # The angle names a feature the profile does not have: its prose
        # remains, but nothing certifies it, and the fit says so.
        fit = angle_content_fit(
            PROFILE, _angle(app_feature="Talking instead of typing")
        )
        assert fit["score"] == 4
        assert "not tied to a feature on your profile" in fit["basis"]

    def test_an_outcome_that_is_not_the_certified_one_earns_less(self):
        certified = angle_content_fit(PROFILE, _angle())
        other = angle_content_fit(
            PROFILE, _angle(viewer_outcome="Less stuck at night")
        )
        assert other["score"] < certified["score"]

    def test_thin_fields_earn_thin_points(self):
        fit = angle_content_fit(
            PROFILE, _angle(user_problem="Typing is slow.", hook_promise="")
        )
        assert fit["score"] == 7

    def test_a_manual_angle_is_scored_on_its_content_not_its_origin(self):
        fit = angle_content_fit(
            PROFILE,
            _angle(origin="manual", app_feature="", viewer_outcome=""),
        )
        assert fit["score"] == 4

    def test_the_screenshot_set_spreads(self):
        # Six angles like the ones in the screenshots. Under the old
        # rank transform this set scored {4,3,3,3,3,3} in some order;
        # scored on content it separates by grounding.
        angles = [
            _angle(),
            _angle(app_feature="voice journaling with AI transcription",
                   viewer_outcome="Less stuck at night"),
            _angle(app_feature="Emotion naming from your own words",
                   viewer_outcome="Less stuck at night"),
            _angle(app_feature="Talking instead of typing",
                   viewer_outcome="Less stuck at night"),
            _angle(user_problem="Typing is slow."),
            _angle(app_feature="", viewer_outcome="", origin="manual"),
        ]
        scores = [angle_content_fit(PROFILE, a)["score"] for a in angles]
        assert scores == [10, 8, 10, 4, 9, 4]
        assert max(scores) - min(scores) >= 5
