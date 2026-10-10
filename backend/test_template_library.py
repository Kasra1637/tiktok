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
        """
        A template missing any structural field cannot drive a generation.

        `continuation_structure` + `cta_pattern` used to be required here. They
        are replaced by `middle_structure`, one field, and the list below
        deliberately does NOT ask for a CTA: a template promising a closing
        action would be describing footage this product does not make.
        """
        required = (
            "name", "category", "opening_structure", "hook_seconds",
            "middle_structure", "visual_style",
            "camera_pacing", "required_assets", "default_duration", "content_slots",
        )
        for tpl in tl.CURATED_TEMPLATES:
            for key in required:
                assert tpl.get(key), f"{tpl.get('name')} is missing {key}"

    def test_no_template_carries_the_retired_arc_fields(self):
        """
        `middle_structure` replaced `continuation_structure` + `cta_pattern`, so
        a curated row holding either would describe footage this product does not
        generate — a third beat would be the product demo, and a CTA beat has no
        ending left to write towards.
        """
        for tpl in tl.CURATED_TEMPLATES:
            assert "continuation_structure" not in tpl, tpl["name"]
            assert "cta_pattern" not in tpl, tpl["name"]

    def test_the_middle_never_describes_a_demonstration(self):
        """
        Each curated middle has to stop at the reach, because the demo and the
        call to action are the founder's own footage. A template whose middle
        "shows the app working" would reintroduce the product demo through the
        template library, which is the one route the plan and strategy prompts
        cannot police.
        """
        for tpl in tl.CURATED_TEMPLATES:
            middle = tpl["middle_structure"].lower()
            for banned in ("show the app", "show the feature", "demo the app",
                           "screen recording", "swipe to", "tap through"):
                assert banned not in middle, f"{tpl['name']} uses {banned!r}"

    def test_categories_are_all_in_vocabulary(self):
        for tpl in tl.CURATED_TEMPLATES:
            assert tpl["category"] in tl.HOOK_CATEGORIES, tpl["name"]

    def test_objectives_are_all_in_vocabulary(self):
        for tpl in tl.CURATED_TEMPLATES:
            assert tpl["objective"] in tl.VIDEO_OBJECTIVES, tpl["name"]

    def test_every_angle_has_six_unique_recommended_existing_goals(self):
        assert set(tl.ANGLE_GOAL_RECOMMENDATIONS) == set(tl.CONTENT_ANGLE_KINDS)
        for kind, goals in tl.ANGLE_GOAL_RECOMMENDATIONS.items():
            assert len(goals) == 6, kind
            assert len(set(goals)) == 6, kind
            assert set(goals) <= set(tl.VIDEO_OBJECTIVES), kind

    def test_pain_focused_angles_prioritize_viewer_problem_goals(self):
        assert tl.ANGLE_GOAL_RECOMMENDATIONS["problem_solution"][:3] == (
            "address_user_problem", "feel_seen_and_understood", "avoid_common_mistake"
        )
        assert "demonstrate_feature" not in tl.ANGLE_GOAL_RECOMMENDATIONS["problem_solution"]

    def test_feature_angles_prioritize_feature_and_explanation_goals(self):
        assert tl.ANGLE_GOAL_RECOMMENDATIONS["feature_demonstration"][:3] == (
            "demonstrate_feature", "explain_app", "achieve_desired_outcome"
        )


    def test_every_template_requires_exactly_the_character_reference(self):
        """
        Face-only library: the character reference is the single permitted
        asset kind. Every template puts the founder on camera, so each one
        requires exactly ["character_reference"] — no screenshots, recordings,
        logos, photos, or audio, not even as options.
        """
        for tpl in tl.CURATED_TEMPLATES:
            assert tpl["required_assets"] == ["character_reference"], tpl["name"]

    def test_hook_seconds_land_inside_the_hook_window(self):
        """
        Was pinned to the first three seconds, which every curated template
        happened to satisfy. The window is now named: 2-4 seconds, and 4 is the
        ceiling because the first four seconds are the only window a viewer
        decides in. A hook that needs longer to land is not a hook.
        """
        assert tl.MIN_HOOK_SECONDS == 2
        assert tl.MAX_HOOK_SECONDS == 4
        for tpl in tl.CURATED_TEMPLATES:
            assert tl.MIN_HOOK_SECONDS <= tpl["hook_seconds"] <= tl.MAX_HOOK_SECONDS, tpl["name"]

    def test_the_hook_fits_inside_its_own_piece(self):
        """
        The hook is directorial — where the middle begins — so it can never eat
        the whole runtime. A 4s hook on a 8s piece still leaves four seconds of
        middle to film, which is the least this product can produce.
        """
        for tpl in tl.CURATED_TEMPLATES:
            assert tpl["hook_seconds"] < tpl["default_duration"], tpl["name"]

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

    def test_every_template_carries_a_viewer_outcome(self):
        """
        The picker leads each card with what the viewer ends up with, so a
        template without one is described only by its mechanics again.
        """
        for tpl in tl.CURATED_TEMPLATES:
            assert isinstance(tpl.get("outcome"), str) and tpl["outcome"].strip(), (
                f"{tpl.get('name')} has no outcome"
            )

    def test_outcomes_are_distinct_per_template(self):
        """
        One shared sentence across templates would make the picker read as
        ten copies of the same promise. Each mechanic earns its own outcome.
        """
        outcomes = [tpl["outcome"].strip() for tpl in tl.CURATED_TEMPLATES]
        assert len(set(outcomes)) == len(outcomes)

    def test_outcomes_name_no_mechanic_and_claim_nothing(self):
        """
        An outcome that says "hook", "slot" or "structure" is the feature
        list wearing outcome clothes; one that says "proven" or "guaranteed"
        is a performance claim with no data behind it. Both fail the wording
        rule from the product spec.
        """
        for tpl in tl.CURATED_TEMPLATES:
            lowered = tpl["outcome"].lower()
            for banned in ("hook", "slot", "structure", "template",
                           "proven", "guaranteed", "viral"):
                assert banned not in lowered, f"{tpl['name']} outcome uses {banned!r}"


class TestVocabularies:
    def test_twelve_content_angle_kinds(self):
        assert len(tl.CONTENT_ANGLE_KINDS) == 12

    def test_every_objective_outcome_is_a_capitalized_sentence(self):
        """
        These are shown on their own line under the goal name on the picker,
        where a lowercase opener reads as a typo rather than a clause. They
        used to be lowercase clause fragments ("catches them before the
        mistake") and the picker displayed them verbatim.
        """
        for objective, outcome in tl.OBJECTIVE_OUTCOMES.items():
            assert outcome[:1].isupper(), f"{objective}: {outcome!r}"

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

    A video is now ONE render, so this is the whole story: exceeding a single
    pass is not a longer video, it is a failed one. That is why
    SUPPORTED_DURATIONS stops at 15 and why `model_max` defaults to asking the
    provider rather than assuming the old 30s ceiling.
    """

    def test_supported_durations_are_single_pass_lengths(self):
        assert tl.SUPPORTED_DURATIONS == [8, 10, 12, 15]
        assert tl.DEFAULT_DURATION == 15

    def test_exact_supported_value_passes_through(self):
        assert tl.clamp_duration(12, model_max=30) == 12
        assert tl.clamp_duration(15, model_max=30) == 15
        assert tl.clamp_duration(8, model_max=30) == 8

    def test_clamps_down_to_model_ceiling(self):
        assert tl.clamp_duration(15, model_max=15) == 15
        assert tl.clamp_duration(15, model_max=10) == 10
        # 20s was the shape of every test in this file before one render; the
        # ceiling is now a single pass, so it lands on the longest one.
        assert tl.clamp_duration(20, model_max=30) == 15

    def test_rounds_unsupported_values_down(self):
        assert tl.clamp_duration(14, model_max=30) == 12
        assert tl.clamp_duration(11, model_max=30) == 10

    def test_rounds_up_to_smallest_supported_when_below_all(self):
        # Nothing supported sits under 7 any more — the shortest piece is 8s —
        # so a shorter request is raised to the smallest length that exists
        # rather than returned as something unrenderable.
        assert tl.clamp_duration(7, model_max=30) == 8
        assert tl.clamp_duration(3, model_max=30) == 8

    def test_garbage_input_falls_back_to_default(self):
        assert tl.clamp_duration("banana", model_max=30) == tl.DEFAULT_DURATION
        assert tl.clamp_duration(None, model_max=30) == tl.DEFAULT_DURATION

    def test_never_exceeds_model_max(self):
        for model_max in (5, 10, 15, 20, 30):
            for want in (1, 5, 8, 10, 15, 20, 30, 99):
                assert tl.clamp_duration(want, model_max=model_max) <= model_max

    def test_no_model_max_asks_the_provider_for_the_ceiling(self):
        """
        `model_max=0` means "ask the model", not "assume 30s". A caller that has
        not loaded provider capability would otherwise clamp to a 30s ceiling
        this product can no longer reach — and a video over one pass is a
        broken file, not a longer one.

        Pinned against video_providers directly so the test states what the
        fallback is actually consulting.
        """
        import video_providers
        ceiling = int(video_providers.capability()["max_duration"])
        assert ceiling <= max(tl.SUPPORTED_DURATIONS)
        assert tl.clamp_duration(99) == min(ceiling, max(tl.SUPPORTED_DURATIONS))


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
            "middle_structure": "Then stop at the reach.", "review_status": "approved",
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

    def test_a_reason_never_splices_a_capitalized_outcome_after_a_dash(self):
        """
        The outcome sentences are capitalized for the picker, so the reason
        cannot paste one mid-sentence after an em dash -- that rendered
        "Built for 'create curiosity' — Leaves them wanting the answer." The
        separator is a full stop, and this pins the joined shape so a future
        edit back to the dash fails here rather than in the UI.
        """
        angle = {"kind": "feature_demonstration", "target_audience": "Busy professionals",
                 "app_feature": "timer", "claims_to_respect": []}
        result = _score_template_for_angle(
            self._template(), self._profile(), angle, "demonstrate_feature"
        )
        built = next(r for r in result["reasons"] if r.startswith("Built for"))
        assert built == (
            "Built for 'demonstrate feature'. "
            "Keeps them watching long enough to see it work."
        )
        assert " — K" not in built and "— L" not in built

    def test_a_mismatched_objective_reason_joins_cleanly_too(self):
        angle = {"kind": "feature_demonstration", "target_audience": "x",
                 "app_feature": "timer", "claims_to_respect": []}
        result = _score_template_for_angle(
            self._template(), self._profile(), angle, "build_awareness"
        )
        made = next(r for r in result["reasons"] if r.startswith("Made for"))
        assert made.endswith("Close to your 'build awareness' goal.")
        assert " — P" not in made

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

    def test_brand_tailored_template_outranks_identical_generic(self):
        angle = {"kind": "problem_solution", "target_audience": "", "app_feature": "",
                 "claims_to_respect": []}
        profile = self._profile(id="p1", brand_name="Taskly")
        generic = _score_template_for_angle(self._template(), profile, angle, "")
        tailored = _score_template_for_angle(
            self._template(brand_profile_id="p1"), profile, angle, "")
        assert tailored["score"] > generic["score"]
        assert any("Tailored for Taskly" in r for r in tailored["reasons"])

    def test_other_brands_template_gets_no_bonus(self):
        angle = {"kind": "problem_solution", "target_audience": "", "app_feature": "",
                 "claims_to_respect": []}
        profile = self._profile(id="p1", brand_name="Taskly")
        foreign = _score_template_for_angle(
            self._template(brand_profile_id="p2"), profile, angle, "")
        plain = _score_template_for_angle(self._template(), profile, angle, "")
        assert foreign["score"] == plain["score"]
        assert not any("Tailored for" in r for r in foreign["reasons"])

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


class TestBrandTemplateNormalization:
    """Invalid model-drafted structures are dropped, never repaired into guesses."""

    def test_drops_nameless_and_structureless_items(self):
        import ai_service
        assert ai_service.normalize_brand_template({}) is None
        assert ai_service.normalize_brand_template({"name": "No opening"}) is None
        assert ai_service.normalize_brand_template({"opening_structure": "No name"}) is None
        assert ai_service.normalize_brand_template("nonsense") is None

    def test_coerces_vocabularies_and_bounds(self):
        import ai_service
        good = ai_service.normalize_brand_template({
            "name": "T", "category": "nonsense-kind", "objective": "nonsense-objective",
            "opening_structure": "Open.", "hook_seconds": 99, "default_duration": 99,
            "content_slots": {"a": "b", "": "junk", "c": ""},
        })
        assert good["category"] == "other"
        # hook_seconds is directorial, not a render length, and a 99s opening is
        # not a hook: it clamps to the 4s window rather than being trusted.
        assert good["hook_seconds"] == tl.MAX_HOOK_SECONDS
        # default_duration IS a render length, and one video is one render, so
        # 99s clamps to the longest single pass the library supports.
        assert good["default_duration"] == max(tl.SUPPORTED_DURATIONS)
        assert good["content_slots"] == {"a": "b"}

    def test_a_cta_content_slot_is_dropped(self):
        """
        The CTA is added by the founder in their own editor. A template that
        asks for one is describing footage this product does not make, so the
        slots are popped rather than relabelled — a model asked for a slot it can
        only fill with a call to action will invent one.
        """
        import ai_service
        good = ai_service.normalize_brand_template({
            "name": "T", "opening_structure": "Open.",
            "content_slots": {"app_feature": "the timer", "cta": "Try it free",
                              "call_to_action": "Get it", "next_action": "Download"},
        })
        assert good["content_slots"] == {"app_feature": "the timer"}

    def test_a_retired_continuation_field_still_migrates(self):
        """
        `normalize_brand_template` accepts the old `continuation_structure` as a
        fallback for `middle_structure`. A template drafted by a model reading a
        cached older prompt lands with the old key, and dropping it outright
        would leave a curated row whose middle says nothing at all.
        """
        import ai_service
        good = ai_service.normalize_brand_template({
            "name": "T", "opening_structure": "Open.",
            "continuation_structure": "Name the friction, then stop at the reach.",
        })
        assert good["middle_structure"] == "Name the friction, then stop at the reach."

    def test_an_outcome_line_survives_normalization(self):
        """
        Tailored templates carry the same picker headline as curated ones. A
        missing outcome degrades to no headline rather than invented copy, so
        it is optional — but a supplied one must survive, capped.
        """
        import ai_service
        good = ai_service.normalize_brand_template({
            "name": "T", "opening_structure": "Open.",
            "outcome": "Stays to work out what it meant.",
        })
        assert good["outcome"] == "Stays to work out what it meant."
        missing = ai_service.normalize_brand_template({
            "name": "T", "opening_structure": "Open.",
        })
        assert missing["outcome"] == ""
        long = ai_service.normalize_brand_template({
            "name": "T", "opening_structure": "Open.",
            "outcome": "x" * 500,
        })
        assert len(long["outcome"]) == 300


class TestBrandTemplatePrompt:
    """
    The generator's directives, captured by stubbing _chat_json — no network.
    The prompt must demand brand-specific, presenter-led structures, because
    that is the entire justification for generating templates per profile.
    """

    def _capture(self, monkeypatch, reply):
        import ai_service
        captured = {}

        async def fake_chat_json(system_message, prompt, context, **kwargs):
            captured["system"] = system_message
            captured["prompt"] = prompt
            return reply

        monkeypatch.setattr(ai_service, "_chat_json", fake_chat_json)
        return captured

    def _reply(self, n):
        return [
            {
                "name": f"Brand Hook {i}",
                "category": "pain-point-question",
                "objective": "address_user_problem",
                "opening_structure": f"Open on pain {i}.",
                "hook_seconds": 3,
                "middle_structure": "Name the cost, then stop at the reach.",
                # Retired keys, left in deliberately: a model reading a cached
                # older prompt still emits them, and normalization must fold
                # them into the middle and refuse the CTA pattern rather than
                # storing a close this product does not generate.
                "continuation_structure": "Then the fix.",
                "cta_pattern": "Try it.",
                "visual_style": "Talking head.",
                "camera_pacing": "Steady.",
                "content_slots": {"app_feature": "Task timer", "cta": "Try it free"},
                "default_duration": 10,
            }
            for i in range(n)
        ]

    def test_generates_the_requested_count(self, monkeypatch):
        import asyncio
        import ai_service
        self._capture(monkeypatch, self._reply(10))
        result = asyncio.run(ai_service.generate_brand_templates(
            {"brand_name": "Taskly", "core_features": ["timer"], "target_audience": "Busy"},
            [{"kind": "problem_solution", "label": "L", "target_audience": "Busy",
              "user_problem": "P", "app_feature": "timer"}],
            count=3,
        ))
        assert len(result) == 3
        assert all(t["category"] == "pain-point-question" for t in result)
        assert all("cta_pattern" not in t for t in result)
        assert all(t["content_slots"].get("cta") is None for t in result)

    def test_prompt_demands_brand_specific_presenter_led_structures(self, monkeypatch):
        import asyncio
        import ai_service
        captured = self._capture(monkeypatch, self._reply(1))
        asyncio.run(ai_service.generate_brand_templates(
            {"brand_name": "Taskly", "core_features": ["timer"]}, [], count=1))
        prompt = captured["prompt"]
        assert "Pre-fill every content slot" in prompt
        assert "screenshots" in prompt
        assert "double-quote" in prompt
        assert "required_assets" not in prompt
        # The picker headline: tailored templates carry the same outcome line
        # as curated ones, or the regenerated set renders mechanics again.
        assert '"outcome"' in prompt

    def test_prompt_targets_the_selected_objective(self, monkeypatch):
        import asyncio
        import ai_service
        captured = self._capture(monkeypatch, self._reply(10))
        result = asyncio.run(ai_service.generate_brand_templates(
            {"brand_name": "Taskly", "core_features": ["timer"]}, [],
            count=10, objective="demonstrate_feature"))
        assert len(result) == 10
        assert "demonstrate_feature" in captured["prompt"]
        assert "must serve that objective" in captured["prompt"]

    def test_prompt_seeds_the_schema_example_at_the_full_length(self, monkeypatch):
        """
        The failure this closes: the schema example read "default_duration": 10,
        and the model copied the example, so every custom template landed at
        10s. With a 3s hook that is a 7s middle — a 105-character spoken budget
        — and plans written for the piece kept overflowing the render gate.
        The example is the strongest anchor in a JSON-schema prompt, so it has
        to show the ceiling, and the rule has to say why shorter is worse.
        """
        import asyncio
        import ai_service
        captured = self._capture(monkeypatch, self._reply(1))
        asyncio.run(ai_service.generate_brand_templates(
            {"brand_name": "Taskly", "core_features": ["timer"]}, [], count=1))
        prompt = captured["prompt"]
        assert '"default_duration": 15,' in prompt
        assert "Always set default_duration to 15 seconds" in prompt
        assert "silently cuts the payoff sentence" in prompt


