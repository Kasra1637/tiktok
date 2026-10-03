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
        assert vp.default_model_key() == "minimax-h3"

    def test_env_override_changes_the_default(self, monkeypatch):
        monkeypatch.setenv("VIDEO_MODEL_DEFAULT", "minimax-h3")
        assert vp.default_model_key() == "minimax-h3"

    def test_bad_env_default_is_ignored(self, monkeypatch):
        monkeypatch.setenv("VIDEO_MODEL_DEFAULT", "not-a-model")
        assert vp.default_model_key() == "minimax-h3"

    def test_allowlist_restricts_usage(self, monkeypatch):
        monkeypatch.setenv("VIDEO_MODEL_ALLOWLIST", "minimax-h3")
        assert vp.is_allowed("minimax-h3") is True
        assert vp.is_allowed("aleph-2") is False
        assert vp.default_model_key() == "minimax-h3"

    def test_unknown_keys_in_allowlist_do_not_break_default(self, monkeypatch):
        monkeypatch.setenv("VIDEO_MODEL_ALLOWLIST", "garbage,minimax-h3")
        assert vp.default_model_key() == "minimax-h3"

    def test_resolve_honours_an_allowed_request(self):
        key, reason = vp.resolve("minimax-h3")
        assert key == "minimax-h3"
        assert "requested" in reason

    def test_resolve_falls_back_for_unknown_model(self):
        key, reason = vp.resolve("does-not-exist")
        assert key == vp.default_model_key()
        assert "unknown" in reason

    def test_resolve_falls_back_for_a_removed_provider(self):
        """
        Seedance was removed from VIDEO_MODELS. Old rows still name it, so
        resolving it must degrade to the default with a reason — never raise,
        never silently keep it.
        """
        key, reason = vp.resolve("seedance-2.5")
        assert key == "minimax-h3"
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
        assert vp.is_studio_eligible("minimax-h3") is True

    def test_removed_provider_is_not_studio_eligible(self):
        assert vp.is_studio_eligible("seedance-2.5") is False
        assert vp.is_allowed("seedance-2.5") is False

    def test_capability_falls_back_for_a_removed_provider(self):
        """
        A stale model id in the database degrades to a working generation
        rather than a 500 — that is the contract that makes removal safe.
        """
        cap = vp.capability("seedance-2.5")
        assert cap["key"] == "minimax-h3"


class TestCapabilities:
    def test_every_studio_model_reports_vertical(self):
        for cap in vp.list_capabilities():
            assert cap["vertical"] is True

    def test_only_minimax_models_are_studio_providers(self):
        """
        The point of this list is that every entry can generate a video from a
        prompt, so no in-context editor is ever offered. H3 Max is a second
        MiniMax generative model, added for side-by-side comparison.
        """
        keys = [c["key"] for c in vp.list_capabilities()]
        assert keys == ["minimax-h3", "minimax-h3-max"]
        assert "aleph-2" not in keys
        for cap in vp.list_capabilities():
            assert cap["is_video_editor"] is False

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
        cap = vp.capability("minimax-h3")
        for field in (
            "id", "name", "min_duration", "max_duration", "resolution",
            "supports_references", "supports_native_audio", "vertical",
            "supports_first_frame", "supports_last_frame", "notes",
        ):
            assert field in cap


class TestHailuo3MaxIsOptIn:
    """
    H3 Max is offered alongside Hailuo 3 so the two can be compared on the same
    script. These tests pin the two halves of that promise: adding it must not
    change Hailuo 3, and it must never become the model a render uses unless it
    was asked for by name.
    """

    def test_hailuo_3_entry_is_untouched(self):
        """
        The founder's working model is the baseline for every comparison, so its
        recorded capabilities are pinned. A change here is a deliberate product
        decision, not a side effect of adding another provider.
        """
        from ai_service import VIDEO_MODELS

        assert VIDEO_MODELS["minimax-h3"] == {
            "id": "minimax/hailuo-3",
            "name": "MiniMax H3",
            "description": (
                "Omni-modal video generation. Native audio, V2V motion transfer, "
                "2K resolution, up to 15s."
            ),
            "max_duration": 15,
            "min_duration": 5,
            "supports_references": True,
            "supports_native_audio": True,
            "supports_v2v_motion": True,
            "resolution": "2K",
            "supports_combined_refs": False,
        }

    def test_h3_max_is_registered_at_its_real_id(self):
        cap = vp.capability("minimax-h3-max")
        assert cap["id"] == "minimax/hailuo-3-max"
        assert cap["max_duration"] == 15
        assert cap["min_duration"] == 5
        # The whole point of adding it: a second rendering of the same script.
        assert cap["supports_references"] is True

    def test_h3_max_is_768p_not_2k(self):
        """
        OpenRouter accepts only "768p" or "480p" for this model and rejects an
        unlisted value, so 2K would 400 on every render. This is the one field
        that cannot be copied from the Hailuo 3 entry.
        """
        assert vp.capability("minimax-h3-max")["resolution"] == "768p"
        assert vp.capability("minimax-h3")["resolution"] == "2K"

    def test_h3_max_does_not_request_native_audio(self):
        """
        generate_audio is absent from OpenRouter's accepted fields for H3 Max,
        so the studio must omit it rather than send it and risk a 400. If a real
        clip comes back silent, this flag is the thing to flip.
        """
        assert vp.capability("minimax-h3-max")["supports_native_audio"] is False

    def test_h3_max_is_offered_in_the_studio(self):
        assert vp.is_studio_eligible("minimax-h3-max")
        assert "minimax-h3-max" in [c["key"] for c in vp.list_capabilities()]

    def test_hailuo_3_remains_the_default(self):
        """
        Listing a second model must not change which one a render uses when the
        caller does not name one — otherwise adding a test provider would
        silently move production spend onto a 768p model.
        """
        assert vp.default_model_key() == "minimax-h3"
        assert vp.resolve(None)[0] == "minimax-h3"
        assert vp.resolve("") [0] == "minimax-h3"

    def test_named_h3_max_is_honoured(self):
        key, _reason = vp.resolve("minimax-h3-max")
        assert key == "minimax-h3-max"

    def test_h3_max_takes_a_face_reference(self):
        assert vp.accepts_identity_reference("minimax-h3-max")

    def test_h3_max_identity_rides_as_first_frame_not_references(self):
        """
        The serving provider 400s input_references for this model ("does not
        support image input references"), even though OpenRouter lists the
        field. The capacity count records that refusal so nothing reads it as
        permission; identity_via_first_frame records where the photo actually
        goes — the opening frame, which OpenRouter documents as supported.
        """
        max_cap = vp.capability("minimax-h3-max")
        assert max_cap["max_reference_images"] == 0
        assert max_cap["identity_via_first_frame"] is True
        # ...while Hailuo 3 keeps the reference-image path, and the editor
        # keeps refusing both:
        assert vp.capability("minimax-h3").get("identity_via_first_frame") is not True
        assert vp.accepts_identity_reference("minimax-h3") is True
        assert vp.accepts_identity_reference("aleph-2") is False

    def test_allowlisting_hailuo_3_alone_still_excludes_h3_max(self, monkeypatch):
        """
        The env allowlist is the existing lever for restricting spend. It must
        keep working now that there is a second model, so a deployment that only
        trusts one provider can still pin itself to it.
        """
        monkeypatch.setenv("VIDEO_MODEL_ALLOWLIST", "minimax-h3")
        assert vp.is_allowed("minimax-h3") is True
        assert vp.is_allowed("minimax-h3-max") is False
        assert vp.is_studio_eligible("minimax-h3-max") is False
        assert [c["key"] for c in vp.list_capabilities()] == ["minimax-h3"]

    def test_allowlisting_h3_max_alone_makes_it_the_default(self, monkeypatch):
        """The documented switch for making H3 Max the production model."""
        monkeypatch.setenv("VIDEO_MODEL_ALLOWLIST", "minimax-h3-max")
        assert vp.default_model_key() == "minimax-h3-max"


class TestHailuo3MaxPayload:
    """
    What actually goes over the wire for an H3 Max render.

    The capability record is only half the answer; these assert the request
    body, because the failure this guards against is a 400 from the provider on
    a parameter the docs say it does not accept.
    """

    @staticmethod
    def _capture(monkeypatch):
        import ai_service

        seen = []

        class _Resp:
            status_code = 202
            text = '{"id": "job-1", "status": "queued"}'

            def json(self):
                return {"id": "job-1", "status": "queued"}

        class _Client:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, headers=None, json=None):
                seen.append(json)
                return _Resp()

        monkeypatch.setattr(ai_service.httpx, "AsyncClient", _Client)
        monkeypatch.setattr(ai_service, "OPENROUTER_API_KEY", "test")
        return seen

    def test_sends_the_model_id_and_768p(self, monkeypatch):
        import asyncio

        import ai_service

        seen = self._capture(monkeypatch)
        asyncio.run(ai_service.generate_video(prompt="A founder reaches for their phone.",
                                             duration=10, model="minimax-h3-max"))
        assert len(seen) == 1
        assert seen[0]["model"] == "minimax/hailuo-3-max"
        assert seen[0]["resolution"] == "768p"
        assert seen[0]["aspect_ratio"] == "9:16"
        assert seen[0]["duration"] == 10

    def test_never_sends_generate_audio(self, monkeypatch):
        """
        OpenRouter does not list generate_audio for this model. The studio also
        defaults the flag off via supports_native_audio, but the payload layer
        must not add it just because a caller passes True — an unlisted field is
        a 400 and the founder pays nothing for the attempt, but loses the run.
        """
        import asyncio

        import ai_service

        seen = self._capture(monkeypatch)
        asyncio.run(ai_service.generate_video(prompt="A founder reaches for their phone.",
                                             duration=10, model="minimax-h3-max",
                                             generate_audio=True))
        assert "generate_audio" not in seen[0]

    def test_hailuo_3_still_sends_2k_and_audio(self, monkeypatch):
        """The comparison only means something if the baseline is unchanged."""
        import asyncio

        import ai_service

        seen = self._capture(monkeypatch)
        asyncio.run(ai_service.generate_video(prompt="A founder reaches for their phone.",
                                             duration=10, model="minimax-h3",
                                             generate_audio=True))
        assert seen[0]["model"] == "minimax/hailuo-3"
        assert seen[0]["resolution"] == "2K"
        assert seen[0]["generate_audio"] is True

    def test_face_rides_as_first_frame_not_references(self, monkeypatch, tmp_path):
        """
        The serving provider 400s input_references for this model, so the
        photo rides as the opening frame — the one image field OpenRouter
        documents as supported for it. Same face, different field; the
        data-URI encoding is unchanged.
        """
        import asyncio

        import ai_service

        face = tmp_path / "face.png"
        face.write_bytes(bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000d49444154789c626001000000ffff0300000600055d3866680000000049454e44ae426082"))
        seen = self._capture(monkeypatch)
        asyncio.run(ai_service.generate_video(prompt="A founder reaches for their phone.",
                                             duration=10, model="minimax-h3-max",
                                             reference_image_path=face))
        assert "input_references" not in seen[0]
        frames = seen[0]["frame_images"]
        assert len(frames) == 1
        assert frames[0]["frame_type"] == "first_frame"
        assert frames[0]["image_url"]["url"].startswith("data:image/png;base64,")

    def test_unknown_key_still_falls_back_inside_the_provider(self, monkeypatch):
        """
        The 400 for an unknown key lives at the API boundary, not here. This
        records that generate_video itself remains a last-resort guard, so a
        direct caller cannot reach the provider with a nonsense model.
        """
        import asyncio

        import ai_service

        seen = self._capture(monkeypatch)
        asyncio.run(ai_service.generate_video(prompt="A founder reaches for their phone.",
                                             duration=10, model="not-a-real-model"))
        assert seen[0]["model"] == "minimax/hailuo-3"


class TestDurationPlanning:
    """
    A second model call is only justified when the duration genuinely exceeds
    one pass, so these rules must be exact.
    """

    def test_duration_within_one_pass_needs_no_extension(self):
        plan = vp.plan_duration("minimax-h3", 12)
        assert plan["primary_seconds"] == 12
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

    def test_minimax_needs_a_second_job_past_15s(self):
        for want in (20, 30):
            plan = vp.plan_duration("minimax-h3", want)
            assert plan["needs_extension"] is True
            assert plan["primary_seconds"] == 15

    def test_below_provider_floor_is_raised(self):
        plan = vp.plan_duration("minimax-h3", 2)
        assert plan["primary_seconds"] == vp.capability("minimax-h3")["min_duration"]
        assert any("cannot go below" in a for a in plan["adjustments"])

    def test_never_returns_zero(self):
        assert vp.plan_duration("minimax-h3", 1)["primary_seconds"] > 0

    def test_adjustment_records_provider_fallback(self):
        plan = vp.plan_duration("aleph-2", 20)
        assert plan["model"] != "aleph-2"
        assert plan["adjustments"]

    def test_clamp_helper_matches_plan(self):
        assert vp.clamp_for_single_pass("minimax-h3", 30) == 15


PLAN = {
    "hook_line": "Stop writing empty pages",
    "script": "Taskly gives you one prompt and a reminder.",
    # Exactly two sections, as the plan schema now demands: the hook, then the
    # middle that develops it and stops at the moment the presenter reaches for
    # their phone. There is no demonstration beat and no closing beat — the
    # founder records the demo and adds their own call to action.
    "beat_timeline": [
        {"start": 0, "end": 3, "label": "hook", "text": "Stop writing empty pages"},
        {"start": 3, "end": 20, "label": "middle", "text": "The blank page loses its grip"},
    ],
    "overlays": [{"start": 0, "end": 3, "text": "one prompt"}],
    "visual_direction": "Close on hands, then a screen recording.",
    "voice_direction": "Warm and unhurried",
    "sound_direction": "Lo-fi bed",
    # A note to the founder about what to record themselves. It is stored on the
    # project and read in their studio, and it must never reach a render.
    "demo_brief": "Record yourself tapping the timer once.",
    # The two retired fields are left in deliberately. Their columns survive in
    # the schema for rows written before they were dropped, so this fixture is
    # what proves a stale one cannot reach a prompt.
    "feature_emphasis": "The task timer",
    "cta": "Try the free trial",
}
PROFILE = {"brand_name": "Taskly", "app_category": "Productivity"}
TEMPLATE = {
    "name": "Quick App Demonstration",
    "visual_style": "screen_recording_first",
    "camera_pacing": "follows the interaction",
    "middle_structure": "Name the friction, then stop at the reach.",
    "continuation_structure": "Complete one task, then CTA.",
}


class TestSinglePassPrompt:
    def test_one_prompt_covers_the_hook_and_the_middle(self):
        """
        Was `test_one_prompt_covers_hook_and_continuation`, and it asserted the
        plan's CTA reached the prompt.

        A video is now ONE render with exactly two sections: a hook and a
        middle. There is no continuation in the old sense — it is not a second
        clip — and no CTA, because the founder adds their own after the demo they
        record. So the third assertion became the property that matters more:
        nothing from the retired CTA column can reach the render.
        """
        prompt = gp.build_single_pass_prompt(PLAN, PROFILE, TEMPLATE, 20)
        # The whole timeline must be described in a single generation.
        assert "Stop writing empty pages" in prompt
        assert "The blank page loses its grip" in prompt
        assert "Try the free trial" not in prompt
        # And the founder's demo brief is a note to them, not to the model.
        assert "Record yourself tapping the timer once." not in prompt

    def test_the_prompt_says_the_demo_and_close_are_not_generated(self):
        """
        The strongest form of "no CTA reaches the render": the prompt does not
        merely omit one, it forbids the model from inventing a demonstration or
        a request, and says where the video stops.
        """
        prompt = gp.build_single_pass_prompt(PLAN, PROFILE, TEMPLATE, 20)
        lowered = prompt.lower()
        assert "do not film the app being used" in lowered
        assert "do not ask the viewer to do anything" in lowered
        assert "reaches for their phone" in lowered
        assert "adds their own call to action" in lowered

    def test_the_middle_boundary_comes_from_the_hook_length(self):
        """
        The two sections are split at the hook's own length, so the plan and the
        render agree on where the hook ends instead of each re-deriving it.
        """
        prompt = gp.build_single_pass_prompt(PLAN, PROFILE, TEMPLATE, 20)
        assert "The first 3 seconds are the hook" in prompt
        assert "The rest of the 20 seconds are the middle" in prompt

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
        assert "3-20s" in prompt

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

    def test_no_composited_assets_section(self):
        # Face-only product: the photograph is covered by the person anchor
        # and nothing else can be attached, so the prompt no longer lists
        # real assets to composite — only the captions carve-out remains.
        prompt = gp.build_single_pass_prompt(PLAN, PROFILE, TEMPLATE, 20)
        assert "Real app assets" not in prompt

    def test_person_anchor_locks_the_face(self):
        plan = dict(PLAN, assets=[{
            "kind": "character_reference", "name": "Founder face",
            "label": "Founder face", "file_path": "face.png",
        }])
        prompt = gp.build_single_pass_prompt(plan, PROFILE, TEMPLATE, 20)
        assert "the person in the attached character reference" in prompt

    def test_missing_plan_fields_do_not_crash(self):
        prompt = gp.build_single_pass_prompt({}, {}, {}, 15)
        assert isinstance(prompt, str) and len(prompt) > 0

    def test_person_anchor_ignores_retired_kinds(self):
        assert gp.person_anchor_notes([]) == ""
        assert gp.person_anchor_notes([{"kind": "screenshot", "name": "Home"}]) == ""
        assert "character reference" in gp.person_anchor_notes(
            [{"kind": "character_reference", "name": "Home"}])


class TestRenderPromptLengthCap:
    """
    The provider refuses content[0].text past 7,000 characters, proven live by
    a 7,724-char submit that 400d. The founder cannot fix that failure
    themselves — the verbosity lives in model-generated strategy text, not in
    anything they typed — so the builders must guarantee the cap instead of
    letting a long strategy spend a failed submit.
    """
    BIG = "w " * 3000

    def _verbose_strategy(self):
        big = self.BIG
        return {
            "hook_line": big, "hook_concept": big, "hook_action": big,
            "hook_dialogue": big, "hook_promise": big,
            "strategy_summary": big, "audience_problem": big,
            "emotional_triggers": [big] * 6, "messaging_pillars": [big] * 6,
            "primary_feature": big, "desired_outcome": big,
            "differentiation_beat": big,
            "scene": {
                "environment": big, "background": big, "setting": big,
                "camera_angle": big, "framing": big, "lighting": big,
                "color_palette": big,
            },
            "performance": {"movement": big, "voice_delivery": big},
            "segments": [
                {"role": "hook", "goal": big, "script": big, "action": big},
                {"role": "middle", "goal": big, "script": big, "action": big},
            ],
        }

    def _verbose_template(self):
        big = self.BIG
        return {
            "opening_structure": big, "middle_structure": big,
            "visual_style": big, "camera_pacing": big, "hook_seconds": 3,
        }

    def _verbose_profile(self):
        return {
            "brand_name": "Taskly",
            "must_not_show": [self.BIG] * 10,
        }

    def _verbose_assets(self):
        return [{"kind": "character_reference", "name": self.BIG}]

    def test_segment_prompt_stays_within_the_provider_limit(self):
        """
        Every variable field at 6,000 chars — far past anything a strategy,
        template, profile or asset label really carries — must still assemble
        under RENDER_PROMPT_LIMIT. The number is measured, not picked: this
        fixture lands at 6,632 against the 6,800 ceiling (provider refuses past
        7,000, 200 margin for measuring differences).
        """
        prompt = gp.build_segment_prompt(
            strategy=self._verbose_strategy(),
            profile=self._verbose_profile(),
            template=self._verbose_template(),
            duration=12,
            assets=self._verbose_assets(),
            plan={"hook_seconds": 3},
        )
        assert len(prompt) <= gp.RENDER_PROMPT_LIMIT, (
            f"verbose render prompt is {len(prompt)} chars, over the "
            f"{gp.RENDER_PROMPT_LIMIT} ceiling — a submit this long 400s."
        )

    def test_clipping_never_amputates_the_identity_close(self):
        """
        The cap is enforced by clipping variable content, never by cutting the
        finished tail: the person anchor and the same-individual close are the
        worst part of the prompt to lose, and they sit at the end.
        """
        prompt = gp.build_segment_prompt(
            strategy=self._verbose_strategy(),
            profile=self._verbose_profile(),
            template=self._verbose_template(),
            duration=12,
            assets=self._verbose_assets(),
            plan={"hook_seconds": 3},
        )
        assert prompt.startswith("Create ONE continuous 12-second")
        assert "The person on camera is the same individual" in prompt
        assert prompt.rstrip().endswith("under the same light.")

    def test_single_pass_prompt_stays_within_the_provider_limit(self):
        """
        The no-strategy fallback reads founder-written fields (script, beats,
        overlays) that are equally unbounded, so it gets the same guarantee:
        a 12-beat, 10-overlay plan at 6,000 chars a field still assembles
        under the ceiling (measured 5,859).
        """
        big = self.BIG
        prompt = gp.build_single_pass_prompt(
            plan={
                "hook_line": big, "script": big,
                "visual_direction": big, "voice_direction": big,
                "sound_direction": big, "tone": big,
                "beat_timeline": [
                    {"start": i, "end": i + 1, "label": "b", "text": big}
                    for i in range(12)
                ],
                "overlays": [{"text": big}] * 10,
                "assets": self._verbose_assets(),
            },
            profile=self._verbose_profile(),
            template=self._verbose_template(),
            duration=20,
        )
        assert len(prompt) <= gp.RENDER_PROMPT_LIMIT, (
            f"verbose fallback prompt is {len(prompt)} chars, over the "
            f"{gp.RENDER_PROMPT_LIMIT} ceiling — a submit this long 400s."
        )


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
        # Real provider refusal of the character reference photo: the model
        # vendors it as InputImageSensitiveContentDetected. Retrying the same
        # photo burns money and always fails identically.
        '{"error":{"code":"InputImageSensitiveContentDetected.PrivacyInformation",'
        '"message":"The request failed because the input image contains private content"}}',
        "Video generation failed (HTTP 400): {\"error\":{\"message\":\"HTTP 400: "
        "{\"error\":{\"code\":\"InputImageSensitiveContentDetected.PrivacyInformation\"}}\"}}}}",
    ])
    def test_permanent_failures_are_not_retryable(self, message):
        assert gp.is_recoverable_error(message) is False

    def test_empty_message_is_not_retryable(self):
        assert gp.is_recoverable_error("") is False
        assert gp.is_recoverable_error(None) is False


class TestProviderRefusalMessage:
    def test_photo_refusal_gets_a_human_message(self):
        import ai_service
        message = ai_service.describe_provider_refusal(
            '{"error":{"code":"InputImageSensitiveContentDetected.PrivacyInformation",'
            '"message":"The request failed because the input image"}}'
        )
        assert message is not None
        assert "privacy filter" in message
        assert "different photo" in message
        # Short enough to survive the server's truncation of the submit
        # detail: the raw nested JSON used to arrive cut off mid-string.
        assert len(message) <= 190

    def test_non_refusal_errors_get_no_message(self):
        import ai_service
        assert ai_service.describe_provider_refusal("Request timed out") is None
        assert ai_service.describe_provider_refusal("HTTP 500 internal error") is None
        assert ai_service.describe_provider_refusal("") is None
        assert ai_service.describe_provider_refusal(None) is None
