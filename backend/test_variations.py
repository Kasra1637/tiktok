"""
Tests for the controlled variation catalogue.

The important properties are that a variation changes exactly one dimension,
that cheap axes stay free, and that a bad value is refused rather than
silently coerced.
"""
import pytest

import variations as v


class TestCatalogue:
    def test_nine_variation_axes(self):
        assert len(v.VARIATIONS) == 9

    def test_catalogue_covers_the_specified_axes(self):
        expected = {
            "hook_line", "cta", "audience", "tone", "pacing",
            "template", "visual_opening", "app_feature", "duration",
        }
        assert set(v.VARIATIONS) == expected

    def test_structural_axes_need_no_plan(self):
        """Changing the template or length is free: no model call at all."""
        assert v.get_variation("template").needs_plan is False
        assert v.get_variation("duration").needs_plan is False

    def test_creative_axes_need_a_rewrite(self):
        for key in ("hook_line", "cta", "audience", "tone", "pacing",
                    "visual_opening", "app_feature"):
            assert v.get_variation(key).needs_plan is True

    def test_every_axis_has_a_label_and_description(self):
        for spec in v.VARIATIONS.values():
            assert spec.label and spec.description

    def test_public_listing_shape(self):
        entry = v.list_variations()[0]
        for key in ("key", "label", "description", "needs_plan", "fields", "value_kind"):
            assert key in entry

    def test_unknown_kind_is_not_found(self):
        assert v.get_variation("nonsense") is None
        assert v.get_variation("") is None

    def test_lookup_is_case_insensitive(self):
        assert v.get_variation("HOOK_LINE") is not None

    def test_only_known_fields_are_writable(self):
        for spec in v.VARIATIONS.values():
            for field in spec.fields:
                assert field in v.ALLOWED_FIELDS, field


class TestValueCoercion:
    def test_duration_must_be_numeric(self):
        spec = v.get_variation("duration")
        assert v.coerce_value(spec, "25") == 25
        with pytest.raises(ValueError):
            v.coerce_value(spec, "twenty")

    def test_duration_is_bounded(self):
        spec = v.get_variation("duration")
        with pytest.raises(ValueError):
            v.coerce_value(spec, 1)
        with pytest.raises(ValueError):
            v.coerce_value(spec, 500)

    def test_pacing_accepts_only_faster_or_slower(self):
        spec = v.get_variation("pacing")
        assert v.coerce_value(spec, "Faster") == "faster"
        assert v.coerce_value(spec, "SLOWER") == "slower"
        with pytest.raises(ValueError) as err:
            v.coerce_value(spec, "sideways")
        assert "faster" in str(err.value)

    def test_text_value_is_required(self):
        spec = v.get_variation("hook_line")
        with pytest.raises(ValueError):
            v.coerce_value(spec, "   ")

    def test_text_value_is_length_capped(self):
        spec = v.get_variation("cta")
        with pytest.raises(ValueError):
            v.coerce_value(spec, "x" * 700)

    def test_text_value_is_trimmed(self):
        spec = v.get_variation("hook_line")
        assert v.coerce_value(spec, "  New hook  ") == "New hook"


class TestApplyVariation:
    PROJECT = {
        "hook_line": "Old hook",
        "script": "Old spoken script.",
        "cta": "Old CTA",
        "audience": "Busy parents",
        "tone": "calm",
        "duration_seconds": 20,
        "visual_direction": "Close on hands.",
        "feature_emphasis": "The timer",
    }

    def test_hook_variation_updates_hook_and_opens_script(self):
        spec = v.get_variation("hook_line")
        updates, _ = v.apply_variation(self.PROJECT, spec, "Stop doing this")
        assert updates["hook_line"] == "Stop doing this"
        assert updates["script"].startswith("Stop doing this")
        assert "Old spoken script." in updates["script"]

    def test_cta_variation_touches_only_the_cta(self):
        spec = v.get_variation("cta")
        updates, _ = v.apply_variation(self.PROJECT, spec, "Get it on the App Store")
        assert set(updates) == {"cta"}

    def test_audience_variation_touches_only_the_audience(self):
        spec = v.get_variation("audience")
        updates, _ = v.apply_variation(self.PROJECT, spec, "Students")
        assert set(updates) == {"audience"}

    def test_tone_variation_touches_only_the_tone(self):
        spec = v.get_variation("tone")
        updates, _ = v.apply_variation(self.PROJECT, spec, "playful")
        assert set(updates) == {"tone"}

    def test_template_variation_touches_only_the_template(self):
        spec = v.get_variation("template")
        updates, _ = v.apply_variation(self.PROJECT, spec, "some-template-id")
        assert set(updates) == {"template_id"}

    def test_duration_variation_touches_only_the_duration(self):
        spec = v.get_variation("duration")
        updates, _ = v.apply_variation(self.PROJECT, spec, "30")
        assert set(updates) == {"duration_seconds"}
        assert updates["duration_seconds"] == 30

    def test_feature_variation_touches_only_the_emphasis(self):
        spec = v.get_variation("app_feature")
        updates, _ = v.apply_variation(self.PROJECT, spec, "The reminders")
        assert set(updates) == {"feature_emphasis"}

    def test_visual_opening_touches_only_the_direction(self):
        spec = v.get_variation("visual_opening")
        updates, _ = v.apply_variation(self.PROJECT, spec, "Open on a coffee cup")
        assert set(updates) == {"visual_direction"}

    def test_pacing_appends_a_directive_without_losing_existing_direction(self):
        spec = v.get_variation("pacing")
        updates, _ = v.apply_variation(self.PROJECT, spec, "faster")
        assert "Close on hands." in updates["visual_direction"]
        assert "PACING: FAST" in updates["visual_direction"]

    def test_re_pacing_replaces_rather_than_stacking(self):
        """Changing pacing twice must not leave two contradictory directives."""
        spec = v.get_variation("pacing")
        once, _ = v.apply_variation(self.PROJECT, spec, "slower")
        twice, _ = v.apply_variation({**self.PROJECT, **once}, spec, "faster")
        assert twice["visual_direction"].count("PACING:") == 1
        assert "PACING: FAST" in twice["visual_direction"]
        assert "SLOW" not in twice["visual_direction"]

    def test_pacing_preserves_the_original_direction_text(self):
        spec = v.get_variation("pacing")
        once, _ = v.apply_variation(self.PROJECT, spec, "faster")
        twice, _ = v.apply_variation({**self.PROJECT, **once}, spec, "slower")
        assert twice["visual_direction"].startswith("Close on hands.")

    def test_pacing_directive_covers_both_directions(self):
        assert "FAST" in v.pacing_directive("faster")
        assert "SLOW" in v.pacing_directive("slower")
        assert v.pacing_directive("") == ""

    def test_every_axis_changes_something(self):
        sample = {
            "hook_line": "New hook", "cta": "New CTA", "audience": "New audience",
            "tone": "new tone", "pacing": "faster", "template": "tid",
            "visual_opening": "New opening", "app_feature": "New feature",
            "duration": "15",
        }
        for key, value in sample.items():
            spec = v.get_variation(key)
            updates, _ = v.apply_variation(self.PROJECT, spec, value)
            assert updates, f"{key} produced no changes"
            assert set(updates) <= v.ALLOWED_FIELDS

    def test_a_variation_never_rewrites_the_script_except_for_the_hook(self):
        """Only a new hook line may prepend to the script."""
        for key, value in (("cta", "New CTA"), ("tone", "x"), ("audience", "y")):
            spec = v.get_variation(key)
            updates, _ = v.apply_variation(self.PROJECT, spec, value)
            assert "script" not in updates, key
