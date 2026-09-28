"""
Unit tests for the provider capability layer and generation planning.

Pure logic, no network: these are the rules that keep the app swappable across
video models and guarantee a single coherent generation.
"""
import os

import pytest

import generation_planning as gp
import video_providers as vp


class TestProviderResolution:
    def test_default_is_the_configured_app_default(self):
        assert vp.default_model_key() == "seedance-2.5"

    def test_env_override_changes_the_default(self, monkeypatch):
        monkeypatch.setenv("VIDEO_MODEL_DEFAULT", "seedance-2.5")
        assert vp.default_model_key() == "seedance-2.5"

    def test_bad_env_default_is_ignored(self, monkeypatch):
        monkeypatch.setenv("VIDEO_MODEL_DEFAULT", "not-a-model")
        assert vp.default_model_key() == "seedance-2.5"

    def test_allowlist_restricts_usage(self, monkeypatch):
        monkeypatch.setenv("VIDEO_MODEL_ALLOWLIST", "seedance-2.5")
        assert vp.is_allowed("seedance-2.5") is True
        assert vp.is_allowed("minimax-h3") is False
        assert vp.default_model_key() == "seedance-2.5"

    def test_unknown_keys_in_allowlist_do_not_break_default(self, monkeypatch):
        monkeypatch.setenv("VIDEO_MODEL_ALLOWLIST", "garbage,seedance-2.5")
        assert vp.default_model_key() == "seedance-2.5"

    def test_resolve_honours_an_allowed_request(self):
        key, reason = vp.resolve("seedance-2.5")
        assert key == "seedance-2.5"
        assert "requested" in reason

    def test_resolve_falls_back_for_unknown_model(self):
        key, reason = vp.resolve("does-not-exist")
        assert key == vp.default_model_key()
        assert "unknown" in reason

    def test_resolve_refuses_video_editors(self):
        """Aleph edits a clip; the template workflow has no clip to edit."""
        key, reason = vp.resolve("aleph-2")
        assert key != "aleph-2"
        assert "cannot generate from a prompt" in reason

    def test_resolve_defaults_when_no_model_named(self):
        key, reason = vp.resolve(None)
        assert key == vp.default_model_key()
        assert "default" in reason

    def test_editor_is_not_studio_eligible(self):
        assert vp.is_studio_eligible("aleph-2") is False
        assert vp.is_studio_eligible("seedance-2.5") is True
        assert vp.is_studio_eligible("minimax-h3") is True


class TestCapabilities:
    def test_every_studio_model_reports_vertical(self):
        for cap in vp.list_capabilities():
            assert cap["vertical"] is True

    def test_seedance_supports_a_single_30s_pass(self):
        cap = vp.capability("seedance-2.5")
        assert cap["max_duration"] >= 30
        assert cap["supports_first_frame"] is True
        assert cap["supports_native_audio"] is True

    def test_minimax_is_capped_at_15s(self):
        cap = vp.capability("minimax-h3")
        assert cap["max_duration"] == 15
        assert cap["supports_combined_refs"] is False

    def test_unknown_key_falls_back_instead_of_raising(self):
        cap = vp.capability("nope")
        assert cap["key"] == vp.default_model_key()

    def test_ineligible_list_excludes_editors_from_models(self):
        keys = [c["key"] for c in vp.list_capabilities()]
        assert "aleph-2" not in keys

    def test_capability_record_has_the_planning_fields(self):
        cap = vp.capability("seedance-2.5")
        for field in (
            "id", "name", "min_duration", "max_duration", "resolution",
            "supports_references", "supports_native_audio", "vertical",
            "supports_first_frame", "supports_last_frame", "notes",
        ):
            assert field in cap


class TestDurationPlanning:
    """
    A second model call is only justified when the duration genuinely exceeds
    one pass, so these rules must be exact.
    """

    def test_duration_within_one_pass_needs_no_extension(self):
        plan = vp.plan_duration("seedance-2.5", 20)
        assert plan["primary_seconds"] == 20
        assert plan["needs_extension"] is False
        assert plan["extension_seconds"] == 0

    def test_over_limit_splits_into_primary_plus_extension(self):
        plan = vp.plan_duration("minimax-h3", 30)
        assert plan["primary_seconds"] == 15
        assert plan["extension_seconds"] == 15
        assert plan["needs_extension"] is True

    def test_split_is_explicitly_explained(self):
        plan = vp.plan_duration("minimax-h3", 20)
        assert plan["needs_extension"] is True
        assert any("second job" in a for a in plan["adjustments"])

    def test_seedance_needs_no_extension_at_any_supported_length(self):
        for want in (10, 15, 20, 30):
            assert vp.plan_duration("seedance-2.5", want)["needs_extension"] is False

    def test_below_provider_floor_is_raised(self):
        plan = vp.plan_duration("minimax-h3", 2)
        assert plan["primary_seconds"] == vp.capability("minimax-h3")["min_duration"]
        assert any("cannot go below" in a for a in plan["adjustments"])

    def test_never_returns_zero(self):
        for model in ("seedance-2.5", "minimax-h3"):
            assert vp.plan_duration(model, 1)["primary_seconds"] > 0

    def test_adjustment_records_provider_fallback(self):
        plan = vp.plan_duration("aleph-2", 20)
        assert plan["model"] != "aleph-2"
        assert plan["adjustments"]

    def test_clamp_helper_matches_plan(self):
        assert vp.clamp_for_single_pass("minimax-h3", 30) == 15
        assert vp.clamp_for_single_pass("seedance-2.5", 30) == 30


PLAN = {
    "hook_line": "Stop writing empty pages",
    "script": "Taskly gives you one prompt and a reminder.",
    "beat_timeline": [
        {"start": 0, "end": 3, "label": "hook", "text": "Stop writing empty pages"},
        {"start": 3, "end": 8, "label": "problem", "text": "Blank page friction"},
        {"start": 8, "end": 17, "label": "demo", "text": "Complete one task"},
        {"start": 17, "end": 20, "label": "cta", "text": "Try it free"},
    ],
    "overlays": [{"start": 0, "end": 3, "text": "one prompt"}],
    "visual_direction": "Close on hands, then a screen recording.",
    "voice_direction": "Warm and unhurried",
    "sound_direction": "Lo-fi bed",
    "feature_emphasis": "The task timer",
    "cta": "Try the free trial",
}
PROFILE = {"brand_name": "Taskly", "app_category": "Productivity"}
TEMPLATE = {
    "name": "Quick App Demonstration",
    "visual_style": "screen_recording_first",
    "camera_pacing": "follows the interaction",
    "continuation_structure": "Complete one task, then CTA.",
}


class TestSinglePassPrompt:
    def test_one_prompt_covers_hook_and_continuation(self):
        prompt = gp.build_single_pass_prompt(PLAN, PROFILE, TEMPLATE, 20)
        # The whole timeline must be described in a single generation.
        assert "Stop writing empty pages" in prompt
        assert "Complete one task" in prompt
        assert "Try the free trial" in prompt

    def test_demands_a_single_coherent_take(self):
        prompt = gp.build_single_pass_prompt(PLAN, PROFILE, TEMPLATE, 20)
        assert "single coherent take" in prompt.lower()
        assert "20-second" in prompt

    def test_forbids_rendering_app_ui_or_text(self):
        prompt = gp.build_single_pass_prompt(PLAN, PROFILE, TEMPLATE, 20)
        lowered = prompt.lower()
        for banned in ("interface", "screenshot", "price", "rating", "logo"):
            assert banned in lowered
        assert "do not draw or render" in lowered

    def test_requests_vertical_framing(self):
        prompt = gp.build_single_pass_prompt(PLAN, PROFILE, TEMPLATE, 20)
        assert "9:16" in prompt

    def test_includes_beat_timings(self):
        prompt = gp.build_single_pass_prompt(PLAN, PROFILE, TEMPLATE, 20)
        assert "0-3s" in prompt
        assert "17-20s" in prompt

    def test_overlay_text_is_handed_over_not_drawn(self):
        prompt = gp.build_single_pass_prompt(PLAN, PROFILE, TEMPLATE, 20)
        assert "one prompt" in prompt
        assert "added afterwards" in prompt

    def test_uses_the_real_app_name(self):
        prompt = gp.build_single_pass_prompt(PLAN, PROFILE, TEMPLATE, 20)
        assert "Taskly" in prompt

    def test_extension_prompt_does_not_repeat_the_hook(self):
        prompt = gp.build_single_pass_prompt(
            PLAN, PROFILE, TEMPLATE, 10, is_extension=True
        )
        lowered = prompt.lower()
        assert "continues" in lowered
        assert "do not re-introduce" in lowered
        assert "repeat the hook" in lowered

    def test_primary_prompt_does_not_claim_to_continue(self):
        prompt = gp.build_single_pass_prompt(PLAN, PROFILE, TEMPLATE, 20)
        assert "CONTINUES an existing video" not in prompt

    def test_sound_direction_forbids_named_commercial_tracks(self):
        prompt = gp.build_single_pass_prompt(PLAN, PROFILE, TEMPLATE, 20)
        assert "licensed audio" in prompt

    def test_asset_notes_appear_when_supplied(self):
        prompt = gp.build_single_pass_prompt(
            PLAN, PROFILE, TEMPLATE, 20,
            asset_notes="screenshot (Onboarding), logo",
        )
        assert "Onboarding" in prompt

    def test_missing_plan_fields_do_not_crash(self):
        prompt = gp.build_single_pass_prompt({}, {}, {}, 15)
        assert isinstance(prompt, str) and len(prompt) > 0

    def test_empty_assets_yield_no_notes(self):
        assert gp.asset_notes([]) == ""
        assert gp.asset_notes([{"kind": "screenshot", "name": "Home"}]) == "screenshot (Home)"


class TestCostExtraction:
    def test_reads_usage_cost(self):
        cost, source = gp.extract_cost({"usage": {"cost": 0.42}})
        assert cost == 0.42
        assert source == "usage.cost"

    def test_reads_nested_data_usage_cost(self):
        cost, _ = gp.extract_cost({"data": {"usage": {"cost": 1.5}}})
        assert cost == 1.5

    def test_reads_top_level_cost(self):
        cost, _ = gp.extract_cost({"cost": 0.09})
        assert cost == 0.09

    def test_missing_cost_is_explicit_not_zero(self):
        """A silent 0.0 would read as 'free' in analytics."""
        cost, source = gp.extract_cost({"status": "completed"})
        assert cost is None
        assert source == "unavailable"

    def test_absent_response_is_handled(self):
        assert gp.extract_cost(None) == (None, "unavailable")

    def test_zero_cost_is_preserved_as_zero(self):
        cost, _ = gp.extract_cost({"usage": {"cost": 0}})
        assert cost == 0.0

    def test_negative_cost_is_ignored(self):
        cost, source = gp.extract_cost({"usage": {"cost": -5}})
        assert cost is None
        assert source == "unavailable"


class TestRecoverableErrors:
    @pytest.mark.parametrize("message", [
        "Request timed out",
        "HTTP 429 rate limit exceeded",
        "HTTP 502 bad gateway",
        "HTTP 503 service unavailable",
        "Connection reset by peer",
        "Server temporarily overloaded",
    ])
    def test_transient_failures_are_retryable(self, message):
        assert gp.is_recoverable_error(message) is True

    @pytest.mark.parametrize("message", [
        "Blocked by content policy",
        "Safety system triggered",
        "Unsupported parameter: duration",
        "Validation error: prompt too long",
        "Video job not found (404). It may have expired.",
    ])
    def test_permanent_failures_are_not_retryable(self, message):
        assert gp.is_recoverable_error(message) is False

    def test_empty_message_is_not_retryable(self):
        assert gp.is_recoverable_error("") is False
        assert gp.is_recoverable_error(None) is False
