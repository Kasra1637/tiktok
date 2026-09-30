"""
Tests for the Hook Template Library: curated seed integrity, controlled
vocabularies, duration clamping, and the recommendation scorer.

Pure unit tests — no network, no database. The DB-backed endpoint behaviour
lives in test_template_library_api.py.
"""
import pytest

import template_library as tl
from server import _score_template_for_angle


class TestCuratedSeeds:
    """The shipped library must be complete, abstract, and honestly labelled."""

    def test_ten_templates_seeded(self):
        assert len(tl.CURATED_TEMPLATES) == 10

    def test_every_template_has_full_structure(self):
        """A template missing any structural field cannot drive a generation."""
        required = (
            "name", "category", "opening_structure", "hook_seconds",
            "continuation_structure", "cta_pattern", "visual_style",
            "camera_pacing", "required_assets", "default_duration", "content_slots",
        )
        for tpl in tl.CURATED_TEMPLATES:
            for key in required:
                assert tpl.get(key), f"{tpl.get('name')} is missing {key}"

    def test_categories_are_all_in_vocabulary(self):
        for tpl in tl.CURATED_TEMPLATES:
            assert tpl["category"] in tl.HOOK_CATEGORIES, tpl["name"]

    def test_objectives_are_all_in_vocabulary(self):
        for tpl in tl.CURATED_TEMPLATES:
            assert tpl["objective"] in tl.VIDEO_OBJECTIVES, tpl["name"]

    def test_every_template_requires_exactly_the_character_reference(self):
        """
        Face-only library: the character reference is the single permitted
        asset kind. Every template puts the founder on camera, so each one
        requires exactly ["character_reference"] — no screenshots, recordings,
        logos, photos, or audio, not even as options.
        """
        for tpl in tl.CURATED_TEMPLATES:
            assert tpl["required_assets"] == ["character_reference"], tpl["name"]

    def test_hook_seconds_within_first_three_seconds(self):
        """A hook that runs long is not a hook."""
        for tpl in tl.CURATED_TEMPLATES:
            assert 1 <= tpl["hook_seconds"] <= 3, tpl["name"]

    def test_durations_are_supported_values(self):
        for tpl in tl.CURATED_TEMPLATES:
            assert tpl["default_duration"] in tl.SUPPORTED_DURATIONS, tpl["name"]

    def test_no_template_claims_to_be_proven(self):
        """
        No template has internal performance data, so nothing may be described
        as proven. This is the wording rule from the product spec.
        """
        for tpl in tl.CURATED_TEMPLATES:
            blob = " ".join(str(v) for v in tpl.values()).lower()
            for banned in ("proven", "guaranteed", "viral"):
                assert banned not in blob, f"{tpl['name']} uses {banned!r}"

    def test_no_template_requires_a_source_video(self):
        """
        The library replaced exact-match recreation, so a template must be
        usable with no source clip at all.
        """
        for tpl in tl.CURATED_TEMPLATES:
            assert "reference_video_path" not in tpl
            for asset in tpl["required_assets"]:
                assert asset != "reference_video", tpl["name"]

    def test_content_slots_are_non_empty(self):
        for tpl in tl.CURATED_TEMPLATES:
            assert isinstance(tpl["content_slots"], dict) and tpl["content_slots"]

    def test_retired_interface_led_templates_are_gone(self):
        """
        Templates whose whole mechanic was real app footage were deleted, not
        rewritten: no screenshot, recording, logo, or product shot can ever be
        uploaded again, so nothing may reference them.
        """
        names = {tpl["name"] for tpl in tl.CURATED_TEMPLATES}
        for retired in (
            "Before and After",
            "Quick App Demonstration",
            "Feature Reveal",
            "Competitor Alternative",
            "Fast Tutorial",
            "Screen-Recording Reveal",
            "Problem, App, Result",
            "Three Taps to Solve This",
        ):
            assert retired not in names, retired

    def test_creator_photo_is_gone_everywhere(self):
        """
        Inversion of the old pin. creator_photo never anchored a face and no
        second upload kind survives: "Three Mistakes" and "Short
        Transformation Story" are presenter-led now and require the same
        character reference as everything else.
        """
        for tpl in tl.CURATED_TEMPLATES:
            assert "creator_photo" not in tpl["required_assets"], tpl["name"]
        by_name = {tpl["name"]: tpl for tpl in tl.CURATED_TEMPLATES}
        for name in ("Three Mistakes", "Short Transformation Story"):
            assert by_name[name]["required_assets"] == ["character_reference"]

    def test_seed_rows_carry_honest_evidence_note(self):
        for row in tl.curated_template_rows():
            assert "No internal performance data" in row["evidence_note"]
            assert row["origin"] == "curated"
            assert row["review_status"] == "approved"
            assert row["archived"] == 0


class TestVocabularies:
    def test_twelve_content_angle_kinds(self):
        assert len(tl.CONTENT_ANGLE_KINDS) == 12

    def test_unknown_values_fall_back(self):
        assert tl.normalize_category("not-a-real-category") == "other"
        assert tl.normalize_objective("not_a_real_objective") == ""
        assert tl.normalize_angle_kind("nonsense") == "problem_solution"
        assert tl.normalize_asset_kind("nonsense") == ""

    def test_normalizers_accept_loose_input(self):
        assert tl.normalize_category("Pain Point Question") == "pain-point-question"
        assert tl.normalize_category("pain_point_question") == "pain-point-question"
        assert tl.normalize_objective("Build Awareness") == "build_awareness"
        assert tl.normalize_angle_kind("Before-After") == "before_after"

    def test_empty_input_is_safe(self):
        assert tl.normalize_category(None) == "other"
        assert tl.normalize_objective(None) == ""
        assert tl.normalize_angle_kind("") == "problem_solution"


class TestClampDuration:
    """
    Duration clamping is the guard against silently requesting more than a
    model can produce, which yields a broken file rather than a clear error.
    """

    def test_exact_supported_value_passes_through(self):
        assert tl.clamp_duration(20, model_max=30) == 20
        assert tl.clamp_duration(15, model_max=30) == 15

    def test_clamps_down_to_model_ceiling(self):
        assert tl.clamp_duration(30, model_max=15) == 15
        assert tl.clamp_duration(20, model_max=10) == 10

    def test_rounds_unsupported_values_down(self):
        assert tl.clamp_duration(7, model_max=30) == 5 or tl.clamp_duration(7, model_max=30) == 10
        assert tl.clamp_duration(18, model_max=30) == 15

    def test_rounds_up_to_smallest_supported_when_below_all(self):
        assert tl.clamp_duration(3, model_max=30) == 10

    def test_garbage_input_falls_back_to_default(self):
        assert tl.clamp_duration("banana", model_max=30) == tl.DEFAULT_DURATION
        assert tl.clamp_duration(None, model_max=30) == tl.DEFAULT_DURATION

    def test_never_exceeds_model_max(self):
        for model_max in (5, 10, 15, 20, 30):
            for want in (1, 5, 10, 15, 20, 30, 99):
                assert tl.clamp_duration(want, model_max=model_max) <= model_max


class TestRecommendationScorer:
    """
    The scorer is deliberately transparent and deterministic so a
    recommendation can be re-derived and audited by the founder.
    """

    def _template(self, **overrides):
        base = {
            "name": "T", "category": "demo", "objective": "demonstrate_feature",
            "app_categories": ["productivity"], "audiences": ["cold_audience"],
            "required_assets": ["character_reference"], "content_slots": {"app_feature": "the timer"},
            "continuation_structure": "Then CTA.", "review_status": "approved",
        }
        base.update(overrides)
        return base

    def _profile(self, **overrides):
        base = {"app_category": "Productivity", "target_audience": "Busy professionals"}
        base.update(overrides)
        return base

    def test_objective_match_scores_highest(self):
        angle = {"kind": "feature_demonstration", "target_audience": "Busy professionals",
                 "app_feature": "timer", "claims_to_respect": []}
        result = _score_template_for_angle(
            self._template(), self._profile(), angle, "demonstrate_feature"
        )
        assert result["score"] >= 7.0
        assert any("demonstrate feature" in r for r in result["reasons"])

    def test_objective_mismatch_scores_lower(self):
        angle = {"kind": "feature_demonstration", "target_audience": "x",
                 "app_feature": "timer", "claims_to_respect": []}
        match = _score_template_for_angle(
            self._template(), self._profile(), angle, "demonstrate_feature"
        )
        mismatch = _score_template_for_angle(
            self._template(), self._profile(), angle, "build_awareness"
        )
        assert match["score"] > mismatch["score"]

    def test_category_mismatch_is_flagged_as_limitation(self):
        angle = {"kind": "problem_solution", "target_audience": "", "app_feature": "",
                 "claims_to_respect": []}
        result = _score_template_for_angle(
            self._template(app_categories=["fitness"]),
            self._profile(app_category="Productivity"),
            angle, "",
        )
        assert any("fitness" in lim for lim in result["limitations"])

    def test_required_assets_always_surface_as_limitation(self):
        angle = {"kind": "problem_solution", "target_audience": "", "app_feature": "",
                 "claims_to_respect": []}
        result = _score_template_for_angle(
            self._template(required_assets=["character_reference"]),
            self._profile(), angle, "",
        )
        assert any("character reference" in lim for lim in result["limitations"])

    def test_claims_to_respect_are_carried_into_limitations(self):
        angle = {
            "kind": "problem_solution", "target_audience": "", "app_feature": "",
            "claims_to_respect": ["Do not claim iOS support", "Trial terms unverified"],
        }
        result = _score_template_for_angle(self._template(), self._profile(), angle, "")
        joined = " ".join(result["limitations"])
        assert "iOS" in joined and "Trial terms" in joined

    def test_unpublished_draft_is_flagged(self):
        angle = {"kind": "problem_solution", "target_audience": "", "app_feature": "",
                 "claims_to_respect": []}
        result = _score_template_for_angle(
            self._template(review_status="draft"), self._profile(), angle, ""
        )
        assert any("draft" in lim.lower() for lim in result["limitations"])

    def test_scoring_without_an_angle_still_works(self):
        result = _score_template_for_angle(self._template(), self._profile(), None, "build_awareness")
        assert result["score"] > 0
        assert isinstance(result["reasons"], list)

    def test_always_returns_why_and_limitations_lists(self):
        for kind in tl.CONTENT_ANGLE_KINDS:
            angle = {"kind": kind, "target_audience": "a", "app_feature": "f",
                     "claims_to_respect": []}
            result = _score_template_for_angle(self._template(), self._profile(), angle, "")
            assert isinstance(result["reasons"], list)
            assert isinstance(result["limitations"], list)
            assert isinstance(result["score"], float)


class TestAbstractStructureGuarantee:
    """
    The library replaced exact-match recreation. These tests fail if a
    template ever starts depending on a specific creator's recording.
    """

    def test_templates_reference_no_creator_identity(self):
        for tpl in tl.CURATED_TEMPLATES:
            blob = " ".join(str(v) for v in tpl.values()).lower()
            assert "@" not in blob, tpl["name"]

    def test_no_template_requires_gesture_replication(self):
        for tpl in tl.CURATED_TEMPLATES:
            blob = " ".join(str(v) for v in tpl.values()).lower()
            for banned in ("frame by frame", "frame-by-frame", "exact copy", "replicate the"):
                assert banned not in blob, f"{tpl['name']} uses {banned!r}"
