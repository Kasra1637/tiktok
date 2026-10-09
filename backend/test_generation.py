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

    def test_only_generative_models_are_studio_providers(self):
        """
        The point of this list is that every entry can generate a video from a
        prompt, so no in-context editor is ever offered. H3 Max is a second
        MiniMax generative model and Grok Imagine Video a third, both offered
        for comparison against the default. Aleph stays out because it edits a
        clip rather than making one.
        """
        keys = [c["key"] for c in vp.list_capabilities()]
        assert keys == ["minimax-h3", "minimax-h3-max", "heygen-video-1"]
        assert "aleph-2" not in keys
        for cap in vp.list_capabilities():
            assert cap["is_video_editor"] is False











    def test_heygen_video_is_opt_in_and_not_the_default(self):
        """
        Audio + listed 2K makes this a default-challenger on paper, but paper
        is not evidence: likeness and 2K reality are unproven until the first
        renders. Listing it must not move production spend, so the default
        stays Hailuo 3 and explicit requests are honoured, not swapped.
        """
        assert vp.is_studio_eligible("heygen-video-1") is True
        assert vp.default_model_key() == "minimax-h3"
        assert vp.resolve("heygen-video-1")[0] == "heygen-video-1"

    def test_heygen_video_is_registered_at_its_real_id(self):
        cap = vp.capability("heygen-video-1")
        assert cap["id"] == "heygen/heygen-video-1"
        assert cap["max_duration"] == 15
        assert cap["min_duration"] == 5

    def test_heygen_video_requests_768p_not_2k(self):
        """
        2K is listed but costs 3x 768p per the live price SKUs ($0.09/s vs
        $0.03/s) for detail no render has proven real. 768p is the cheapest
        credible tier and is equally drift-clean; revisit 2K only on render
        evidence.
        """
        assert vp.capability("heygen-video-1")["resolution"] == "768p"

    def test_heygen_video_requests_native_audio(self):
        """
        The endpoint accepts generate_audio for this model (listed, defaults
        off), so the catalog declares it and the studio sends it by default —
        the second audio-capable entry after Hailuo 3. If real clips come
        back silent or the field is refused, this is the flag to flip.
        """
        assert vp.capability("heygen-video-1")["supports_native_audio"] is True

    def test_heygen_video_integrates_identity_into_a_generated_first_frame(self):
        """
        HeyGen no longer receives the raw uploaded photo as first_frame.
        Identity is still accepted, but submission integrates it into a
        strategy-derived opening scene so the provider starts in the generated
        environment rather than the uploaded background.
        """
        cap = vp.capability("heygen-video-1")
        assert cap["supports_first_frame"] is True
        assert cap["supports_last_frame"] is False
        assert cap["max_reference_images"] == 0
        assert vp.accepts_identity_reference("heygen-video-1") is True

    def test_an_removed_provider_falls_back_to_the_default(self):
        """
        Providers get retired, and generation rows or a founder's saved model
        choice may still name one. Whether it was removed deliberately or never
        existed, capability() and resolve() must degrade to a working provider
        rather than raise or 400.
        """
        for gone in ("heygen-avatar-iv", "heygen-video-9", "some-retired-model"):
            assert vp.is_known(gone) is False
            assert vp.is_studio_eligible(gone) is False
            assert vp.capability(gone)["key"] == vp.default_model_key()
            key, reason = vp.resolve(gone)
            assert key == vp.default_model_key()
            assert "unknown provider" in reason

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

    def test_heygen_sends_768p_and_audio(self, monkeypatch):
        """
        The whole point of the entry: the endpoint accepts generate_audio, so
        asking for audio must reach the payload alongside 768p — unlike every
        other opt-in, which omits the field.
        """
        import asyncio

        import ai_service

        seen = self._capture(monkeypatch)
        asyncio.run(ai_service.generate_video(prompt="A founder reaches for their phone.",
                                             duration=10, model="heygen-video-1",
                                             generate_audio=True))
        assert seen[0]["model"] == "heygen/heygen-video-1"
        assert seen[0]["resolution"] == "768p"
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


class TestAppearanceIsLockedAndClothingIsNot:
    """
    The person's appearance comes from their photograph and nothing may change
    it; their clothing is the one thing a scene may decide.

    This split is the whole policy. It exists because the render prompt used to
    (a) require the clothing to match the photograph, which contradicted the
    scene deciding it, and (b) say the person was "animated rather than
    re-imagined" while only asking the model to *match* what it was shown —
    which is how a founder with short hair got long black hair added, because
    nothing forbade adding any.
    """

    ANCHOR = [{"kind": "character_reference", "name": "face.png"}]

    def test_the_anchor_forbids_adding_to_the_hair(self):
        anchor = gp.person_anchor_notes(self.ANCHOR)
        # Naming hair specifically, since that is what the model invents:
        # video models express motion in hair by lengthening it.
        assert "do not add, lengthen, restyle or recolour their hair" in anchor
        assert "same hairline, colour, length, texture and parting" in anchor
        # And the general form, so the next invented attribute is covered too.
        assert "do not add or remove anything absent from the image" in anchor

    def test_the_anchor_no_longer_asks_for_the_person_to_be_animated(self):
        """
        "Animated rather than re-imagined" is removed rather than reworded: it
        is the phrasing that invited hair growth in the first place. Movement is
        still asked for, but as movement only — the identity stays fixed.
        """
        anchor = gp.person_anchor_notes(self.ANCHOR)
        assert "animated rather than re-imagined" not in anchor
        assert "Move and speak naturally, but do not change who they are" in anchor

    def test_the_anchor_no_longer_binds_clothing_to_the_photograph(self):
        anchor = gp.person_anchor_notes(self.ANCHOR)
        assert "clothing as they appear in the photograph" not in anchor
        # ...and it says the opposite, so the two halves cannot be misread.
        assert "Their clothing is the one exception" in anchor

    def test_the_anchor_still_names_the_photograph_as_the_only_authority(self):
        anchor = gp.person_anchor_notes(self.ANCHOR)
        assert "the person in the attached character reference" in anchor
        assert "The image is the only authority on who they are" in anchor

    def test_a_scene_may_choose_the_wardrobe_and_it_is_locked(self):
        """
        Clothing belongs to the scene, so it reaches the lock and holds for both
        sections like the room does. Its trailer already forbade re-wardrobing;
        this is what makes that enforceable.
        """
        lock = gp.character_scene_lock({
            "scene": {"wardrobe": "teal scrubs, silver ID badge", "lighting": "cool fluorescents"},
        })
        assert "wardrobe: teal scrubs, silver ID badge" in lock
        assert "THE SCENE AND THE DELIVERY ARE LOCKED" in lock

    def test_a_legacy_written_appearance_is_still_refused(self):
        """
        Strategies written before `character` was dropped still carry one. It
        stays excluded by name — a fabricated face next to the real photograph
        is the failure that put a founder's own face on someone else.
        """
        assert gp.character_scene_lock({
            "character": {
                "appearance": "a late-20s nurse", "hairstyle": "low bun",
                "wardrobe": "teal scrubs", "age_range": "late 20s",
            },
        }) == ""

    def test_an_empty_wardrobe_simply_omits_the_line(self):
        """
        Degrades gracefully: a strategy that named no clothing falls back to the
        photograph's own, so nothing breaks and the rest of the lock still ships.
        """
        lock = gp.character_scene_lock({
            "scene": {"wardrobe": "", "lighting": "cool fluorescents"},
        })
        # The labelled field line is what carries the value; the trailer still
        # says "do not re-wardrobe", so the bare word is always present.
        assert "wardrobe:" not in lock
        assert "lighting: cool fluorescents" in lock

    def test_the_strategy_schema_actually_carries_a_wardrobe(self):
        """
        A field the schema never asks for is never returned, so the scene cannot
        choose clothing at all. This is the whole reason wardrobe was readmitted
        alongside — and the reason it is a scene field rather than a character
        one.
        """
        import ai_service

        assert "wardrobe" in ai_service.STRATEGY_SCENE_FIELDS
        normalized = ai_service.normalize_strategy(
            {"scene": {"wardrobe": "a grey knit jumper"}}
        )
        assert normalized["scene"]["wardrobe"] == "a grey knit jumper"


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
        fixture lands at 6,706 against the 6,800 ceiling (provider refuses past
        7,000, 200 margin for measuring differences). It moved when the person
        anchor grew its no-additions clause and wardrobe joined the lock, which
        is why the figure is re-measured rather than carried forward.
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
        under the ceiling (measured 6,077).
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

    def test_unrecognised_provider_error_is_left_to_the_caller(self):
        """
        This helper classifies only the failures it can explain. An unrecognised
        body must return None so the caller can describe the request it sent,
        rather than being told the photo was the problem.
        """
        import ai_service
        assert ai_service.describe_provider_refusal("HTTP 500 internal error") is None
        assert ai_service.describe_provider_refusal("") is None
        assert ai_service.describe_provider_refusal(None) is None

    def test_non_refusal_errors_get_no_message(self):
        import ai_service
        assert ai_service.describe_provider_refusal("Request timed out") is None
        assert ai_service.describe_provider_refusal("HTTP 500 internal error") is None
        assert ai_service.describe_provider_refusal("") is None
        assert ai_service.describe_provider_refusal(None) is None


class TestPerProviderPromptBudget:
    """
    RENDER_PROMPT_LIMIT was measured against Hailuo's 7,000-char refusal. A
    second provider with a lower ceiling cannot be handed the same prompt: it
    400s, and the founder pays for the attempt. These pin the scaling.
    """

    # Derived, never typed in: a literal here goes stale the moment a ceiling
    # moves, and a stale literal keeps testing a budget no provider uses.
    _TIGHTEST = min(
        vp.capability(k)["prompt_char_limit"] for k in vp.STUDIO_ELIGIBLE
    )

    def _verbose_kwargs(self):
        """
        A strategy with every field saturated, so the prompt is as large as this
        code can build.

        Sized from the real refusal, not invented. A founder's render came back
        4,689 characters against Grok's ceiling; this saturates every field and
        reaches well past that, so the ceiling tests below are strictly harder
        than the case that actually failed.

        Every field the assembler reads has to be populated, not just the obvious
        ones: `scene` and `performance` feed the locked-scene block, which is the
        single largest variable section at 1,100 characters. A fixture missing
        them lands around 4,775 and fits every ceiling whether the scaling works
        or not, which is how the floor-blind formula survived the first version
        of this test.
        """
        big = "P" * 900
        return {
            "strategy": {
                "hook_line": "H" * 200, "hook_concept": "C" * 200,
                "hook_action": "A" * 200, "hook_promise": "P" * 200,
                "hook_dialogue": "D" * 200,
                "audience_problem": big, "primary_feature": big,
                "desired_outcome": big, "differentiation_beat": big,
                "strategy_summary": big, "proof_moment": big, "key_takeaway": big,
                "emotional_triggers": [big] * 5, "messaging_pillars": [big] * 5,
                "objection_overcomes": [big] * 5,
                "scene": {k: big for k, _ in gp._SECTION_LABELS["scene"]},
                "performance": {k: big for k, _ in gp._SECTION_LABELS["performance"]},
                "segments": [
                    {"role": "hook", "goal": big, "script": big, "action": big},
                    {"role": "middle", "goal": big, "script": big, "action": big},
                ],
            },
            "profile": {
                "brand_name": "Test", "must_not_show": [big] * 8,
                "viewer_objections": [big] * 5,
                "proof_moment": "R" * 900, "usage_moments": [big] * 5,
                "tone_voice": big,
            },
            "template": {
                "name": "T", "opening_structure": big, "middle_structure": big,
                "visual_style": big, "camera_pacing": big,
            },
            "duration": 12,
            "assets": {"character_reference": {
                "kind": "character_reference", "name": "A" * 400,
            }},
            "plan": {"hook_seconds": 3},
        }

    def test_the_fixture_is_harder_than_the_render_that_broke(self):
        """
        Guard the guard. The founder's real prompt was 4,689; if this fixture ever
        assembles below that, every ceiling test resting on it is vacuous and will
        pass without exercising the scaling at all.
        """
        unscaled = len(gp.build_segment_prompt(**self._verbose_kwargs()))
        assert unscaled >= 5500, (
            f"fixture assembles to {unscaled} chars, below the 4,689 that actually "
            f"failed and near the 4,775 of a fixture missing the locked-scene "
            f"fields. Ceiling tests resting on it stop testing anything."
        )

    def test_the_default_is_unchanged(self):
        """
        Every pre-existing caller passes no budget, so the assembled prompt must
        be byte-identical to what it was before this parameter existed.
        """
        kwargs = self._verbose_kwargs()
        assert gp.build_segment_prompt(**kwargs) == gp.build_segment_prompt(
            **kwargs, prompt_budget=gp.RENDER_PROMPT_LIMIT
        )

    def test_a_lower_ceiling_produces_a_shorter_prompt(self):
        kwargs = self._verbose_kwargs()
        full = len(gp.build_segment_prompt(**kwargs))
        tight = len(gp.build_segment_prompt(**kwargs, prompt_budget=self._TIGHTEST))
        assert tight < full

    def test_the_scale_does_not_leak_between_calls(self):
        """
        The scale is a ContextVar, so it must be cleared even though the builder
        is the only thing that sets it. A leak would silently shrink the NEXT
        render's Hailuo prompt.
        """
        kwargs = self._verbose_kwargs()
        before = gp._PROMPT_SCALE.get()
        gp.build_segment_prompt(**kwargs, prompt_budget=1200)
        assert gp._PROMPT_SCALE.get() == before

    def test_the_condensed_flag_does_not_leak_between_calls(self):
        """
        Same reason as the scale. A leak would condense a Hailuo render after a
        Grok one, which is silent: the prompt is still valid, just thinner, and
        nothing in the submit log would say why.
        """
        kwargs = self._verbose_kwargs()
        before = gp._PROMPT_CONDENSED.get()
        gp.build_segment_prompt(**kwargs, prompt_budget=4096)
        assert gp._PROMPT_CONDENSED.get() == before
        assert gp._PROMPT_CONDENSED.get() is before

    def test_every_studio_prompt_fits_its_own_ceiling(self):
        """
        The regression that motivated condensing, on the verbose strategy that
        produced the founder's 4,689-character refusal.

        Scaling the variable budget alone could not fix this: the fixed
        instructions do not scale, and measured with no app data at all they are
        2,047 characters — over half of a 4,096 ceiling. Every provider has to
        fit its real data now, not just the small-strategy case.
        """
        kwargs = self._verbose_kwargs()
        for key in vp.STUDIO_ELIGIBLE:
            limit = vp.capability(key)["prompt_char_limit"]
            prompt = gp.build_segment_prompt(**kwargs, prompt_budget=limit)
            assert len(prompt) <= limit, (
                f"{key}: {len(prompt)} chars exceeds its {limit} ceiling. The submit "
                f"guard will refuse this and the founder pays nothing, but the model "
                f"is then unusable for any realistic strategy."
            )

    def test_the_measured_floors_still_match_their_constants(self):
        """
        The scale divides by the variable space these constants imply, so drift in
        either one silently pushes every prompt back over its ceiling. The scale
        would keep producing plausible numbers while the prompts stopped fitting,
        which is exactly how the 4,689-character refusal happened unnoticed.
        """
        empty = dict(strategy={}, profile={}, template={}, duration=10,
                     assets={}, plan={"hook_seconds": 3})
        full = gp.build_segment_prompt(**empty)
        condensed = gp.build_segment_prompt(**empty, prompt_budget=4096)
        assert len(full) == gp.FULL_PROMPT_FLOOR
        assert len(condensed) == gp.CONDENSED_PROMPT_FLOOR
        assert gp.CONDENSED_PROMPT_FLOOR < gp.FULL_PROMPT_FLOOR

    def test_the_variable_budget_excludes_the_fixed_floor(self):
        """
        A ceiling is a TOTAL, so the floor comes out of it before the variables
        get anything. The old scale divided by the total, over-allocating by the
        floor and producing 4,175 characters against a 4,096 ceiling.
        """
        kwargs = self._verbose_kwargs()
        full_budget = len(gp.build_segment_prompt(**kwargs))
        for limit in (4096, 4600, gp.RENDER_PROMPT_LIMIT):
            prompt = gp.build_segment_prompt(**kwargs, prompt_budget=limit)
            headroom = limit - gp.CONDENSED_PROMPT_FLOOR
            assert len(prompt) <= limit
            assert len(prompt) <= (
                gp.CONDENSED_PROMPT_FLOOR + headroom
                if limit < gp.CONDENSE_BELOW
                else limit
            )

    def test_condensing_drops_only_redundant_words(self):
        """
        Condensing exists to buy room for the app-specific brief, so it must not
        quietly become censorship. Every constraint has to survive it, checked
        against the full prompt for the parts it compresses.
        """
        kwargs = self._verbose_kwargs()
        full = gp.build_segment_prompt(**kwargs)
        condensed = gp.build_segment_prompt(**kwargs, prompt_budget=4096)
        for constraint in (
            "reference photograph",  # identity lock, appears only in the close
            "verified app facts",    # invented-claims rule, merged into the handoff
            "do not",                 # the prohibitions
            "one outfit",
        ):
            assert constraint in full, f"fixture drifted: {constraint!r} not in full"
            assert constraint in condensed, (
                f"condensing dropped {constraint!r} — that is a lost constraint, not "
                f"redundant wording"
            )
        assert len(condensed) < len(full)

    def test_a_nonsense_budget_falls_back_to_the_default(self):
        kwargs = self._verbose_kwargs()
        baseline = gp.build_segment_prompt(**kwargs)
        assert gp.build_segment_prompt(**kwargs, prompt_budget=0) == baseline
        assert gp.build_segment_prompt(**kwargs, prompt_budget="nonsense") == baseline
        assert gp.build_segment_prompt(**kwargs, prompt_budget=-5) == baseline


    def test_the_budget_leaves_the_condensed_path_for_tight_providers_only(self):
        kwargs = self._verbose_kwargs()
        assert gp._budget_scale(4096, True) < 1.0
        assert gp._budget_scale(gp.RENDER_PROMPT_LIMIT, False) == 1.0
        # A ceiling below the condensed floor still cannot go to zero: a prompt of
        # one-character stubs reads as corruption. The guard refuses it instead.
        assert gp._budget_scale(500, True) >= 0.10

    def test_every_studio_model_declares_a_ceiling(self):
        for key in vp.STUDIO_ELIGIBLE:
            limit = vp.capability(key).get("prompt_char_limit")
            assert isinstance(limit, int) and limit > 0, key

    def test_the_hailuo_prompt_is_untouched_by_all_of_this(self):
        """
        The founder is happy with H3 Max's output, so every mechanism added for
        the tight ceiling has to be invisible to it: clean endings, protected
        values and the retry loop. All three are gated on condensing, and 6,800
        never condenses, so its prompt must be byte-identical to what it was
        before this work — including when a budget is passed explicitly.
        """
        kwargs = self._verbose_kwargs()
        baseline = gp.build_segment_prompt(**kwargs)
        for key in ("minimax-h3", "minimax-h3-max"):
            limit = vp.capability(key)["prompt_char_limit"]
            assert gp.build_segment_prompt(**kwargs, prompt_budget=limit) == baseline, (
                f"{key} is not condensed, so nothing here should change its prompt"
            )

    def test_the_protect_flag_does_not_leak_between_calls(self):
        """
        Same reason as the scale: protection is withdrawn mid-render when a
        prompt will not fit, and leaking that would leave the NEXT render short
        of its script with nothing in the logs to explain it.
        """
        kwargs = self._verbose_kwargs()
        assert gp._PROMPT_PROTECT.get() is True
        gp.build_segment_prompt(**kwargs, prompt_budget=self._TIGHTEST)
        assert gp._PROMPT_PROTECT.get() is True

    def test_the_spoken_script_survives_a_tight_ceiling(self):
        """
        The regression that motivates protection. Scaling every value equally cut
        the founder's dialogue mid-word — "he list I actually needed th" — which
        is the one field the render cannot be built without. A prompt missing
        half of what the person says is not a shorter prompt, it is a different
        video.

        Each value here is deliberately longer than its scaled budget and shorter
        than its protected one, and each is asserted WHOLE. Asserting a prefix
        would pass either way and prove nothing: protection only changes how much
        of the tail survives, so the tail is what has to be checked.
        """
        script = (
            "I used to have nine lists open at once, and not one of them was "
            "the list I actually needed that day, which is the whole joke."
        )
        action = (
            "exhales, half a laugh, shrugs once, then looks back down at the desk"
        )
        strategy = {
            "hook_line": "You are not lazy, you are just carrying eleven apps.",
            "segments": [
                {
                    "role": "hook",
                    "goal": "stop the scroll with recognition",
                    "script": script,
                    "action": action,
                },
                {
                    "role": "middle",
                    "goal": "show the relief",
                    "script": "Now there is just the one, already sorted, waiting.",
                    "action": "taps the phone once and slides it face-down",
                },
            ],
        }
        prompt = gp.build_segment_prompt(
            strategy=strategy, profile={}, template={}, duration=10,
            assets={"character_reference": {"kind": "character_reference",
                                           "name": "Founder"}},
            plan={"hook_seconds": 3}, prompt_budget=self._TIGHTEST,
        )
        assert script in prompt, "the spoken script lost its tail"
        assert action in prompt, "the on-camera action lost its tail"
        # And the budget actually is tight enough that protection was needed,
        # otherwise this test would pass with protection switched off.
        scale = gp._budget_scale(self._TIGHTEST, True)
        assert len(script) > 160 * scale, (
            f"fixture is too short to test protection: {len(script)} chars vs a "
            f"scaled budget of {160 * scale:.0f}"
        )

    def test_clipping_ends_cleanly_rather_than_mid_word(self):
        """
        The founder-facing bug this replaced: a hard character cut produced
        instructions like "looks up from the phone, tired, into the le", which a
        model either ignores or reads as complete. This pins the clean ending
        directly, with a value whose budget lands mid-word.
        """
        source = "looks up slowly from the phone into the lens and holds a long beat"
        scale = gp._PROMPT_SCALE.set(1.0)
        condensed = gp._PROMPT_CONDENSED.set(True)
        try:
            clipped = gp._clip(source, 30)
        finally:
            gp._PROMPT_CONDENSED.reset(condensed)
            gp._PROMPT_SCALE.reset(scale)
        assert clipped == "looks up slowly from the", (
            f"expected a word-boundary ending, got {clipped!r}"
        )

    def test_a_line_delimited_block_ends_on_a_line(self):
        """
        The strategy brief and the locked scene are newline-delimited, so cutting
        them mid-line drops a field's label along with its value. Line has to be
        preferred over sentence for those two, or the condensed brief loses whole
        fields that the full prompt keeps.
        """
        scale = gp._PROMPT_SCALE.set(1.0)
        condensed = gp._PROMPT_CONDENSED.set(True)
        try:
            clipped = gp._clip(
                "location: a dark office\nlighting: one lamp\nprops: a phone", 40
            )
        finally:
            gp._PROMPT_CONDENSED.reset(condensed)
            gp._PROMPT_SCALE.reset(scale)
        # 40 reaches just past the first newline, so the line boundary is
        # available. Without the line rule this would stop at the last space
        # instead and read "location: a dark", losing the value with the label.
        assert clipped == "location: a dark office", (
            f"expected the line-boundary ending, got {clipped!r}"
        )

    def test_a_saturated_strategy_still_fits_by_giving_up_protection(self):
        """
        Protection has to be best-effort. Holding the script, brief and locked
        scene at full length costs about 1,000 characters, and a saturated
        strategy can spend more than that on those three alone — which produced a
        4,879 prompt against a 4,096 ceiling and made the model unusable for the
        most detailed founders. The retry has to converge regardless.
        """
        kwargs = self._verbose_kwargs()
        for key in vp.STUDIO_ELIGIBLE:
            limit = vp.capability(key)["prompt_char_limit"]
            prompt = gp.build_segment_prompt(**kwargs, prompt_budget=limit)
            assert len(prompt) <= limit, f"{key}: {len(prompt)} over {limit}"

    def test_the_tail_survives_a_tight_budget(self):
        """
        Clipping must stay structural. Cutting the finished string instead would
        amputate the identity close at the very end, which is the worst part of
        the prompt to lose -- so the ending has to be intact at any budget.
        """
        kwargs = self._verbose_kwargs()
        prompt = gp.build_segment_prompt(**kwargs, prompt_budget=self._TIGHTEST)
        assert "Vertical 9:16 throughout" in prompt
        assert prompt.rstrip().endswith("under the same light.")


class TestBoundForSubmit:
    """
    The identity reference is embedded as a base64 data URI inside a JSON body,
    and nothing capped it: the upload ceiling is 200 MB, and crop_face_from_path
    crops without resizing -- and two of its three return paths hand back the
    original untouched. A phone photo therefore arrives as megabytes of data URI
    that the provider can refuse without naming anything we control.
    """

    def _photo(self, tmp_path, size, fmt="PNG"):
        from PIL import Image
        img = Image.new("RGB", size, (120, 90, 60))
        path = tmp_path / f"face{fmt.lower() if fmt == 'JPEG' else ''}.{ 'jpg' if fmt == 'JPEG' else 'png'}"
        img.save(path, format=fmt)
        return path

    def test_a_large_photo_is_downscaled(self, tmp_path):
        import face_crop
        src = self._photo(tmp_path, (4000, 3000))
        out = face_crop.bound_for_submit(src)
        from PIL import Image
        with Image.open(out) as img:
            assert max(img.size) <= 1024

    def test_a_small_photo_is_left_alone(self, tmp_path):
        """
        Re-encoding a small JPEG would only lose quality, so a reference already
        inside the bound is passed through byte-identical.
        """
        import face_crop
        src = self._photo(tmp_path, (400, 300), fmt="JPEG")
        assert face_crop.bound_for_submit(src) == src

    def test_the_encoded_size_actually_drops(self, tmp_path):
        """
        The point of the exercise. Noise defeats compression, so this is the
        worst realistic case: a photo that will not compress well but still has
        to fit in a request body.
        """
        import random
        import face_crop
        from PIL import Image
        rnd = random.Random(7)
        img = Image.new("RGB", (4000, 3000))
        img.putdata([
            (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
            for _ in range(4000 * 3000)
        ])
        src = tmp_path / "noise.png"
        img.save(src, format="PNG")
        before = src.stat().st_size
        out = face_crop.bound_for_submit(src)
        after = out.stat().st_size
        assert after < before / 4, f"{before} -> {after}"

    def test_bounding_twice_does_not_chain(self, tmp_path):
        import face_crop
        src = self._photo(tmp_path, (4000, 3000))
        once = face_crop.bound_for_submit(src)
        twice = face_crop.bound_for_submit(once)
        assert twice == once

    def test_a_missing_file_is_returned_unchanged(self, tmp_path):
        import face_crop
        missing = tmp_path / "gone.png"
        assert face_crop.bound_for_submit(missing) == missing

    def test_an_unreadable_file_is_returned_unchanged(self, tmp_path):
        """
        Never raises. An oversized-but-valid reference still renders, so losing
        the generation over a failed re-encode would be strictly worse.
        """
        import face_crop
        broken = tmp_path / "broken.png"
        broken.write_bytes(b"this is not an image")
        assert face_crop.bound_for_submit(broken) == broken

    def test_the_result_is_a_jpeg(self, tmp_path):
        """
        The declared MIME has to match the bytes, and image_data_uri derives it
        from the extension.
        """
        import face_crop
        from PIL import Image
        src = self._photo(tmp_path, (2000, 2000))
        out = face_crop.bound_for_submit(src)
        with Image.open(out) as img:
            assert img.format == "JPEG"
class TestOpeningPatternInterrupt:
    """
    The opening is a pattern interrupt, so the physical detail that makes one
    has to survive the trip to the video model.

    It used to not: `hook_action` was clipped to 75 characters, which is roughly
    thirteen words, so a strategy written as ordered timed beats arrived at the
    render as a fragment and the opening reverted to a person standing still and
    then talking. These pin the detail arriving intact at both ceilings.
    """

    # A realistic opening performance: ordered, timed, body part by body part.
    ACTION = (
        "Frame one is already moving: the hand snaps up holding the phone, thumb "
        "turning it to the lens; on that beat the brows lift and the eyes widen, "
        "jaw dropping open; the hand drops out of frame as the shoulders break "
        "forward and they step in; end on the sharp look into the camera."
    )

    def _strategy(self):
        return {
            "hook_line": "Nobody warned me this would happen at 3am.",
            "hook_concept": (
                "The viewer catches the middle of a gesture they did not see "
                "start, so they have to stay to find out what it was."
            ),
            "hook_action": self.ACTION,
            "segments": [
                {
                    "role": "hook",
                    "goal": "Stop the scroll inside half a second.",
                    "script": "Nobody warned me this would happen at 3am.",
                    "action": self.ACTION,
                },
                {
                    "role": "middle",
                    "goal": "Develop it into the moment they reach for the phone.",
                    "script": "I was mid-shift and completely done for the night.",
                    "action": "The shoulders drop, the hands stay low and busy.",
                },
            ],
        }

    def _prompt(self, budget=None):
        kwargs = dict(
            strategy=self._strategy(), profile={"brand_name": "ShiftLog"},
            template={}, duration=12, assets={}, plan={"hook_seconds": 3},
        )
        if budget is None:
            return gp.build_segment_prompt(**kwargs)
        return gp.build_segment_prompt(**kwargs, prompt_budget=budget)

    def test_the_directive_is_in_both_prompt_forms(self):
        """
        Condensing must not cost the model the requirement. The condensed form
        carries every constraint of the full one; only the examples of how to
        satisfy them are dropped.
        """
        full = self._prompt()
        tight = self._prompt(min(vp.capability(k)["prompt_char_limit"]
                                 for k in vp.STUDIO_ELIGIBLE))
        assert gp._OPENING_INTERRUPT in full
        assert gp._CONDENSED_OPENING in tight
        for constraint in ("first frame is already", "half-second", "escalat",
                           "face, gaze, hands", "own situation", "question"):
            assert constraint in full
            assert constraint in tight

    def test_the_directive_precedes_the_beats_it_governs(self):
        """A requirement read after the beats is read as a footnote."""
        full = self._prompt()
        assert full.index(gp._OPENING_INTERRUPT) < full.index(
            "What the person physically does in the opening"
        )

    def test_the_opening_detail_arrives_whole_at_the_default_ceiling(self):
        """The whole point: no fragment of the performance at 280 characters."""
        prompt = self._prompt()
        assert self.ACTION in prompt
        assert f"What the person physically does in the opening: {self.ACTION}" \
            in prompt

    def test_the_opening_detail_survives_condensing(self):
        """
        Protected means protected. Grok's 4,096 ceiling is the tight one, and
        losing the physical score there would put the opening back to a talking
        head on the provider most likely to need the help.
        """
        tight = self._prompt(4096)
        assert self.ACTION in tight
        assert len(tight) <= 4096

    def test_the_opening_and_the_middle_share_one_situation(self):
        """
        The failure this closes: a striking opening the rest of the video has
        nothing to do with. The directive says so, and the section headings carry
        the same props and place into both halves, so a strategy that grounds its
        hook on the scene reaches the render with both sections describing it.
        """
        strategy = self._strategy()
        strategy["scene"] = {
            "environment": "a hospital corridor at night",
            "props": "a scrunchie on the wrist, a phone in the hand",
        }
        strategy["segments"][1]["action"] = (
            "The scrunchie comes off the wrist and is pocketed; they look back "
            "down the corridor and start walking."
        )
        prompt = gp.build_segment_prompt(
            strategy=strategy, profile={"brand_name": "ShiftLog"},
            template={}, duration=12, assets={}, plan={"hook_seconds": 3},
        )
        assert "hospital corridor at night" in prompt
        assert "scrunchie" in prompt
        assert "own situation" in prompt
        assert prompt.index("HOOK") < prompt.index("MIDDLE")

    def test_a_pathological_opening_still_respects_the_ceiling(self):
        """Detail is never a licence to overflow: the guard is the ceiling."""
        strategy = self._strategy()
        strategy["hook_action"] = "A" * 3000
        strategy["segments"][0]["action"] = "B" * 3000
        prompt = gp.build_segment_prompt(
            strategy=strategy, profile={"brand_name": "ShiftLog"}, template={},
            duration=12, assets={}, plan={"hook_seconds": 3}, prompt_budget=4096,
        )
        assert len(prompt) <= 4096


class TestBindSpokenWords:
    """The spoken words are the founder's approved words, verbatim.

    The strategy prompt also asks the model for its own section scripts, and
    those drafts reached the provider as "spoken, performed naturally" — so a
    founder could approve outcome-framed words on the Review step and hear the
    model's paraphrase in the render. Binding runs after the model call and
    rewrites the two section scripts from the plan, and these tests pin that
    the words that reach the video model are the approved ones.
    """

    def _strategy(self, hook_script="Model wrote this hook.", middle_script="Model wrote this middle."):
        return {
            "hook_line": "Model wrote a hook line.",
            "segments": [
                {"index": 0, "role": "hook", "seconds": 3, "goal": "stop",
                 "script": hook_script, "action": "look up"},
                {"index": 1, "role": "middle", "seconds": 7, "goal": "develop",
                 "script": middle_script, "action": "count"},
            ],
        }

    def test_hook_and_middle_take_the_approved_words(self):
        import ai_service
        plan = {
            "hook_line": "Do you know what triggers your emotions?",
            "script": "Most evenings blur together. Yours ends with one sentence written down.",
        }
        bound, overflow = ai_service.bind_spoken_words(self._strategy(), plan, 3, 10)
        assert bound["hook_line"] == plan["hook_line"]
        assert bound["segments"][0]["script"] == plan["hook_line"]
        assert bound["segments"][1]["script"] == plan["script"]
        assert overflow == {}
        # Delivery stays the model's: the binding touches words, not action.
        assert bound["segments"][1]["action"] == "count"

    def test_the_caller_keeps_its_own_words(self):
        """Binding returns a copy — persisting the caller's dict unbound would
        mean the stored strategy says one thing while the words spoken say
        another, which is exactly the drift being removed."""
        import ai_service
        strategy = self._strategy()
        plan = {"hook_line": "Approved hook.", "script": "Approved middle."}
        bound, _ = ai_service.bind_spoken_words(strategy, plan, 3, 10)
        assert strategy["segments"][1]["script"] == "Model wrote this middle."
        assert bound["segments"][1]["script"] == "Approved middle."

    def test_a_script_opening_with_its_hook_line_does_not_stutter(self):
        import ai_service
        plan = {
            "hook_line": "Do you know what triggers your emotions?",
            "script": "Do you know what triggers your emotions? I never used to notice mine.",
        }
        bound, _ = ai_service.bind_spoken_words(self._strategy(), plan, 3, 10)
        assert bound["segments"][1]["script"] == "I never used to notice mine."

    def test_an_overlong_script_is_cut_at_a_sentence_and_reported(self):
        import ai_service
        script = "First sentence that fits. " + "x" * 500 + " Final payoff sentence."
        bound, overflow = ai_service.bind_spoken_words(
            self._strategy(), {"hook_line": "Hook.", "script": script}, 3, 10
        )
        assert overflow["dropped_chars"] > 0
        assert overflow["budget"] == ai_service.spoken_budget(7)
        assert bound["segments"][1]["script"] == "First sentence that fits."
        # The budget is per-second, not flat: a longer middle speaks more.
        assert ai_service.spoken_budget(7) > ai_service.spoken_budget(3)

    def test_no_plan_means_no_binding_and_no_overflow(self):
        """A strategy built without a plan keeps the model's words.

        No approval exists to bind to, and reporting overflow of nothing would
        be a false alarm — so both the words and the record stay untouched."""
        import ai_service
        strategy = self._strategy()
        bound, overflow = ai_service.bind_spoken_words(strategy, None, 3, 10)
        assert bound["segments"][1]["script"] == "Model wrote this middle."
        assert overflow == {}

    def test_a_paraphrased_opening_hook_is_not_spent_twice(self):
        """The hook must be found in the script even when the model introduces it.

        The plan's script is the whole piece, so it normally opens with the hook
        line. Matching was an exact prefix test, so "So, <hook line>? ..." kept
        that copy in the middle: the hook was spoken twice and its characters
        were charged to the middle's seconds, which the render then reports as
        an overflow the founder is asked to fix.
        """
        import ai_service
        hook = "Do you know what triggers your emotions?"
        plan = {
            "hook_line": hook,
            "script": f"So, {hook} I never used to notice mine.",
        }
        part = ai_service.partition_spoken_words(plan, 3, 10)
        assert part["middle_text"] == "I never used to notice mine."
        bound, overflow = ai_service.bind_spoken_words(self._strategy(), plan, 3, 10)
        assert bound["segments"][0]["script"] == hook
        assert bound["segments"][1]["script"] == "I never used to notice mine."
        assert overflow == {}

    def test_a_middle_that_merely_mentions_the_hook_is_left_alone(self):
        """Only a leading sentence is the hook. A longer first sentence that
        happens to contain the hook's words is the middle, and cutting it would
        delete the founder's actual words."""
        import ai_service
        hook = "Save more."
        middle = "Saving more is what I do every payday, once I stopped guessing."
        plan = {"hook_line": hook, "script": middle}
        part = ai_service.partition_spoken_words(plan, 3, 10)
        assert part["middle_text"] == middle

    def test_partition_is_the_one_rule_the_clamp_and_the_gate_share(self):
        """The arrival clamp and the render gate must not disagree.

        The clamp decides a stored script fits; the gate decides the same script
        fits. If they were separate arithmetic, a plan could be stored short
        enough for one and refused by the other, and the founder would have no
        action that resolves it.
        """
        import ai_service
        plan = {
            "hook_line": "Hook line here.",
            "script": "Hook line here. " + "Filler sentence. " * 40 + "The payoff.",
        }
        part = ai_service.partition_spoken_words(plan, 3, 12)
        assert part["dropped_chars"] > 0
        # Whatever the clamp kept is what the gate recomputes as fitting.
        stored = {"hook_line": part["hook_line"], "script": f"{part['hook_line']} {part['kept']}"}
        again = ai_service.partition_spoken_words(stored, 3, 12)
        assert again["dropped_chars"] == 0
        assert again["kept"] == part["kept"]

    def test_bound_words_reach_the_provider_verbatim(self):
        """The end-to-end leg: approved plan words in, identical spoken lines in
        the real segment prompt. This is the user-visible guarantee, asserted
        against the prompt text rather than the strategy dict."""
        import ai_service
        plan = {
            "hook_line": "Do you know what triggers your emotions?",
            "script": "Most evenings blur together. Yours ends with one sentence written down.",
        }
        bound, _ = ai_service.bind_spoken_words(self._strategy(), plan, 3, 10)
        prompt = gp.build_segment_prompt(
            strategy=bound, profile={"brand_name": "Vocolens"}, template={},
            duration=10, assets={}, plan={"hook_seconds": 3},
            prompt_budget=16384,
        )
        assert f'The spoken hook line, delivered on camera: "{plan["hook_line"]}"' in prompt
        assert f'spoken, performed naturally: "{plan["script"]}"' in prompt
