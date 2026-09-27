"""
Tests for the deterministic claim-safety checker.

This module is the safety net for generated scripts, so it is tested against
the failure modes it exists to prevent: prohibited claims, invented pricing,
fabricated social proof, guaranteed outcomes, regulated claims, and viewer
diagnosis framing.
"""
import pytest

import claim_safety as cs

PROFILE = {
    "brand_name": "Vocolens",
    "app_category": "Health & Fitness",
    "core_features": ["Voice journaling", "Prompts", "Reminders"],
    "primary_use_cases": ["Evening reflection"],
    "problems_solved": ["Blank-page friction"],
    "pricing_trial": "Free, Pro $79.99/year",
    "known_limitations": "iOS and Android only",
    "claims_approved": ["3-day free trial", "works offline", "no account needed"],
    "claims_review": ["4.8 star rating", "50k downloads"],
    "claims_banned": ["cures anxiety", "guaranteed results", "clinically proven"],
}


def plan(**overrides):
    base = {
        "hook_line": "Stop writing empty pages",
        "script": (
            "Vocolens gives you one short prompt, a voice note, and a reminder. "
            "It works offline and no account needed."
        ),
        "cta": "Try the 3-day free trial",
        "beat_timeline": [{"start": 0, "end": 3, "label": "hook", "text": "Stop writing empty pages"}],
        "overlays": [{"start": 0, "end": 3, "text": "one prompt"}],
    }
    base.update(overrides)
    return base


class TestNormalize:
    def test_lowercases_and_strips_punctuation(self):
        assert cs.normalize("Stop! Writing: Empty pages.") == "stop writing empty pages"

    def test_collapses_whitespace(self):
        assert cs.normalize("a\n\n  b\tc") == "a b c"

    def test_empty_input(self):
        assert cs.normalize("") == ""
        assert cs.normalize(None) == ""


class TestMoneyExtraction:
    """
    Prices are the highest-consequence thing an app promo can get wrong, so
    decimal points must survive matching.
    """

    def test_decimal_points_preserved(self):
        text = cs.script_money_text(plan(script="It costs $4.99 a month."))
        assert "$4.99" in text

    def test_invented_price_flagged(self):
        report = cs.build_safety_report(plan(script="Vocolens is just $4.99 a month."), PROFILE)
        assert [p["claim"] for p in report["pricing_mismatches"]] == ["$4.99"]

    def test_real_price_passes(self):
        report = cs.build_safety_report(plan(script="Pro is $79.99 per year."), PROFILE)
        assert report["pricing_mismatches"] == []

    def test_similar_price_is_still_flagged(self):
        """$4.50 must not be excused because the profile once said $4.99."""
        report = cs.build_safety_report(plan(script="Only $4.50 a month."), PROFILE)
        assert [p["claim"] for p in report["pricing_mismatches"]] == ["$4.50"]

    def test_pricing_in_overlay_text_is_checked(self):
        report = cs.build_safety_report(
            plan(script="A journaling app.", overlays=[{"start": 0, "end": 3, "text": "$9.99/mo"}]),
            PROFILE,
        )
        assert [p["claim"] for p in report["pricing_mismatches"]] == ["$9.99"]

    def test_no_prices_means_no_warnings(self):
        report = cs.build_safety_report(plan(), PROFILE)
        assert report["pricing_mismatches"] == []

    def test_dollar_amount_appears_in_claim(self):
        report = cs.build_safety_report(plan(script="Costs $12."), PROFILE)
        assert report["pricing_mismatches"][0]["claim"] == "$12"


class TestBannedClaims:
    def test_banned_claim_blocks(self):
        report = cs.build_safety_report(plan(script="This app cures anxiety."), PROFILE)
        assert report["passed"] is False
        assert [b["claim"] for b in report["blocking"]] == ["cures anxiety"]

    def test_multiple_banned_claims_all_caught(self):
        report = cs.build_safety_report(
            plan(script="Guaranteed results, and it cures anxiety."), PROFILE
        )
        assert report["passed"] is False
        assert len(report["blocking"]) == 2

    def test_banned_claim_in_overlay_blocks(self):
        """Overlays are on screen, so a banned claim there is equally a failure."""
        report = cs.build_safety_report(
            plan(script="A journaling app.", overlays=[{"text": "cures anxiety"}]), PROFILE
        )
        assert report["passed"] is False

    def test_clean_plan_passes(self):
        report = cs.build_safety_report(plan(), PROFILE)
        assert report["passed"] is True
        assert report["blocking"] == []

    def test_approved_claim_is_not_a_violation(self):
        report = cs.build_safety_report(
            plan(script="It works offline, no account needed."), PROFILE
        )
        assert report["passed"] is True

    def test_no_banned_list_means_nothing_blocks(self):
        report = cs.build_safety_report(plan(script="Anything at all."), {})
        assert report["passed"] is True


class TestClaimTiers:
    def test_approved_claim_detected_when_present(self):
        report = cs.build_safety_report(plan(), PROFILE)
        assert "works offline" in report["claims_used"]
        assert "no account needed" in report["claims_used"]

    def test_unapproved_claim_not_in_used(self):
        """A claims_review item must never be reported as a verified claim."""
        report = cs.build_safety_report(
            plan(script="A journaling app with a 4.8 star rating."), PROFILE
        )
        assert "4.8 star rating" not in report["claims_used"]

    def test_review_claim_surfaced_as_unverified(self):
        report = cs.build_safety_report(
            plan(script="Vocolens has a 4.8 star rating."), PROFILE
        )
        assert [u["claim"] for u in report["unverified"]] == ["4.8 star rating"]
        # Unverified is a warning, not a hard failure — the founder decides.
        assert report["passed"] is True

    def test_self_declared_claim_absent_from_text_is_flagged(self):
        """The model claiming a fact it did not write is itself a signal."""
        report = cs.build_safety_report(
            plan(claims_used=["works offline", "never actually said"]), PROFILE
        )
        assert "never actually said" in report["unverified_self_claims"]
        assert "works offline" not in report["unverified_self_claims"]


class TestRiskPatterns:
    @pytest.mark.parametrize("text", [
        "This is guaranteed to work.",
        "100% effective every time.",
        "No side effects at all.",
        "A proven-to-work method.",
    ])
    def test_guarantee_language_warns(self, text):
        report = cs.build_safety_report(plan(script=text), PROFILE)
        assert report["risk_warnings"], text

    @pytest.mark.parametrize("text", [
        "Our users say it changed everything.",
        "Join 500,000 happy users.",
        "Rated 4.8 five-star reviews.",
    ])
    def test_fabricated_social_proof_warns(self, text):
        report = cs.build_safety_report(plan(script=text), PROFILE)
        reasons = " ".join(w["reason"] for w in report["risk_warnings"])
        assert "social proof" in reasons

    def test_clinical_claim_flags_missing_disclosure(self):
        report = cs.build_safety_report(
            plan(script="Clinically proven to help."), PROFILE
        )
        assert any(w.get("disclosure_missing") for w in report["risk_warnings"])

    def test_disclosure_marks_the_claim_down(self):
        report = cs.build_safety_report(
            plan(script="This is not medical advice. Clinically proven to help."), PROFILE
        )
        assert not any(w.get("disclosure_missing") for w in report["risk_warnings"])

    def test_viewer_diagnosis_framing_warns(self):
        report = cs.build_safety_report(
            plan(script="Built for people with anxiety."), PROFILE
        )
        assert any(
            "describes the viewer" in w["reason"] for w in report["risk_warnings"]
        )

    def test_functional_framing_is_clean(self):
        """The product rule: describe what the app does, not the viewer."""
        report = cs.build_safety_report(
            plan(script="A low-friction journal with short prompts and reminders."), PROFILE
        )
        assert report["risk_warnings"] == []


class TestReportShape:
    def test_report_has_every_documented_key(self):
        report = cs.build_safety_report(plan(), PROFILE)
        for key in (
            "passed", "blocking", "claims_used", "unverified", "risk_warnings",
            "pricing_mismatches", "sources_used", "self_declared_claims",
            "unverified_self_claims",
        ):
            assert key in report

    def test_sources_reflect_populated_profile_fields(self):
        report = cs.build_safety_report(plan(), PROFILE)
        assert "core_features" in report["sources_used"]
        assert "pricing_trial" in report["sources_used"]

    def test_empty_profile_yields_no_sources(self):
        report = cs.build_safety_report(plan(), {})
        assert report["sources_used"] == []
        assert report["passed"] is True

    def test_empty_plan_is_handled(self):
        report = cs.build_safety_report({}, PROFILE)
        assert report["passed"] is True

    def test_none_plan_is_handled(self):
        assert cs.build_safety_report(None, PROFILE)["passed"] is True

    def test_summarize_clean(self):
        assert "Clean" in cs.summarize(cs.build_safety_report(plan(), PROFILE))

    def test_summarize_never_claims_clean_when_flagged(self):
        report = cs.build_safety_report(plan(script="Guaranteed results."), PROFILE)
        assert "Clean" not in cs.summarize(report)

    def test_summarize_mentions_blocking_claims(self):
        report = cs.build_safety_report(plan(script="It cures anxiety."), PROFILE)
        assert "prohibited" in cs.summarize(report)


class TestScriptTextCoverage:
    def test_includes_voice_and_cta(self):
        text = cs.script_text(plan(voice_direction="warm and low", cta="Download now"))
        assert "warm and low" in text
        assert "download now" in text

    def test_includes_beat_text(self):
        text = cs.script_text(plan(beat_timeline=[
            {"start": 0, "end": 3, "label": "hook", "text": "the promised thing"}
        ]))
        assert "the promised thing" in text
