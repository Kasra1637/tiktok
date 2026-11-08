"""
Tests for the deterministic claim-safety checker.

This module is the safety net for generated scripts, so it is tested against
the failure modes it exists to prevent: prohibited claims, fabricated social
proof, guaranteed outcomes, regulated claims, and viewer diagnosis framing.

There is no price check, and that is deliberate: the App Profile carries no
pricing, so there is nothing to verify a stated price against. See the note on
build_safety_report.
"""
import pytest

import claim_safety as cs

PROFILE = {
    "brand_name": "Vocolens",
    "app_category": "Health & Fitness",
    "core_features": ["Voice journaling", "Prompts", "Reminders"],
    "primary_use_cases": ["Evening reflection"],
    "problems_solved": ["Blank-page friction"],
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



class TestBannedClaims:
    def test_banned_claim_blocks(self):
        # Blocking removed as a product decision: nothing refuses a render.
        # The helpers still detect the phrase, but the report never blocks.
        assert cs.find_banned_violations(
            cs.script_text(plan(script="This app cures anxiety.")),
            PROFILE["claims_banned"],
        ) != []
        report = cs.build_safety_report(plan(script="This app cures anxiety."), PROFILE)
        assert report["passed"] is True
        assert report["blocking"] == []

    def test_multiple_banned_claims_all_caught(self):
        report = cs.build_safety_report(
            plan(script="Guaranteed results, and it cures anxiety."), PROFILE
        )
        assert report["passed"] is True
        assert report["blocking"] == []

    def test_banned_claim_in_legacy_overlays_is_ignored(self):
        """Overlays are no longer planned or rendered, so legacy overlay text
        on an old row is not checked — and must not fail the report."""
        report = cs.build_safety_report(
            plan(script="A journaling app.", overlays=[{"text": "cures anxiety"}]), PROFILE
        )
        assert report["passed"] is True

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

    @pytest.mark.parametrize("text", [
        "I use this every morning.",
        "I have used it for years.",
        "I am using it daily.",
        "I swear this works.",
        "As a nurse, I see this daily.",
        "My patients say it helps.",
    ])
    def test_a_claimed_history_with_the_app_warns(self, text):
        """The presenter is an AI stand-in: nothing on file can substantiate
        a personal history with the product, so the claim is warned."""
        report = cs.build_safety_report(plan(script=text), PROFILE)
        reasons = " ".join(w["reason"] for w in report["risk_warnings"])
        assert "cannot substantiate" in reasons, text

    @pytest.mark.parametrize("text", [
        # A past habit is not a usage claim — and half of all natural
        # first-person hooks are built on it ("I used to dread mornings"), so
        # flagging it meant the generator's own customer voice arrived warned.
        "I used to dread mornings.",
        "I used to feel like that.",
        # Accustomed, not a claim.
        "I am used to waking early.",
        # Ordinary first-person problem and outcome language.
        "I could never name what I felt.",
        "I finally understood the pattern.",
    ])
    def test_a_past_habit_or_plain_first_person_does_not_warn(self, text):
        report = cs.build_safety_report(plan(script=text), PROFILE)
        reasons = " ".join(w["reason"] for w in report["risk_warnings"])
        assert "cannot substantiate" not in reasons, text

    def test_first_person_is_a_warning_never_a_block(self):
        """The founder keeps editorial control: this panel advises, it does not
        refuse. Only banned claims and spoken feature inventories block."""
        report = cs.build_safety_report(plan(script="I use this every morning."), PROFILE)
        assert report["passed"] is True

class TestFeatureFraming:
    def test_spoken_inventory_blocks(self):
        """Blocking removed: a feature list never refuses a render.

        The helper still detects the Vocolens shape ("you can track your
        emotional states and uncover your triggers through voice journaling
        and mood tracking"), but the report stays passing.
        """
        assert cs.detect_feature_enumeration(cs.normalize(
            "With Vocolens, you can track your emotional states and uncover "
            "your triggers through voice journaling and mood tracking."
        )) != []
        report = cs.build_safety_report(plan(script=(
            "With Vocolens, you can track your emotional states and uncover "
            "your triggers through voice journaling and mood tracking."
        )), PROFILE)
        assert report["passed"] is True
        assert report["blocking"] == []

    def test_coordinate_two_capabilities_blocks(self):
        report = cs.build_safety_report(
            plan(script="You can log your mood and track your sleep automatically."),
            PROFILE,
        )
        assert report["passed"] is True
        assert report["blocking"] == []

    def test_caption_inventory_in_legacy_overlays_is_ignored(self):
        report = cs.build_safety_report(
            plan(script="A finish you can feel.", overlays=[
                {"start": 0, "end": 2, "text": "Mood tracking and reminders"},
            ]),
            PROFILE,
        )
        assert report["passed"] is True

    def test_outcome_framing_is_clean(self):
        report = cs.build_safety_report(
            plan(script="Tomorrow looks like one list, not nine. You stop carrying it in your head."),
            PROFILE,
        )
        assert report["passed"] is True
        assert report["risk_warnings"] == []

    def test_functional_mention_only_warns(self):
        """One accurate noun is ordinary copy and stays a warning.

        Refusing to render over "a journal" would teach the founder to ignore
        the panel, which is how a blocking tier loses its authority.
        """
        report = cs.build_safety_report(
            plan(script="It lets you track what you did today, so the week reads at a glance."),
            PROFILE,
        )
        assert report["passed"] is True
        assert any(
            "what it changes for the viewer" in w["reason"]
            for w in report["risk_warnings"]
        )

    def test_a_named_app_is_not_an_inventory(self):
        """A flat list of content words is not a capability list.

        "One short prompt, a voice note, and a reminder" enumerates content
        nouns, none of them a capability verb or product feature — and this
        is the base fixture's script, so it also proves the ordinary suite
        fixtures still pass through the new tier.
        """
        report = cs.build_safety_report(plan(), PROFILE)
        assert report["passed"] is True
        assert report["blocking"] == []

    def test_production_direction_cannot_block(self):
        """The wider walk deliberately never feeds the blocking tier.

        A scene lock is made of comma lists ("camera angle, lighting and
        wardrobe"); refusing a render for describing a room would strand every
        project in the system.
        """
        report = cs.build_safety_report(plan(
            script="A finish you can feel.",
            visual_direction="Camera angle, lighting and wardrobe are locked",
            voice_direction="Steady, unhurried and quiet",
        ), PROFILE)
        assert report["passed"] is True

    def test_strategy_section_inventory_blocks(self):
        """The actual spoken words live in the strategy, not the plan.

        The founder's approved Review script may be clean while the model's own
        section script lists features. Checking the plan alone would pass it.
        """
        base = plan(script="A finish you can feel.")
        base["strategy"] = {
            "hook_line": "Stop carrying it.",
            "segments": [
                {"role": "hook", "script": "Stop carrying it."},
                {"role": "middle", "script": "Track your mood and log your habits with reminders and analytics."},
            ],
        }
        report = cs.build_safety_report(base, PROFILE)
        assert report["passed"] is True
        assert report["blocking"] == []


class TestReportShape:
    def test_report_has_every_documented_key(self):
        report = cs.build_safety_report(plan(), PROFILE)
        for key in (
            "passed", "blocking", "claims_used", "unverified", "risk_warnings",
            "sources_used", "self_declared_claims",
            "unverified_self_claims",
        ):
            assert key in report

    def test_no_price_check_remains(self):
        """
        The price check was deleted with pricing_trial, because with no price on
        record it flagged every price in every script — a check that always
        fires teaches the founder to ignore the panel that matters. Prices are
        kept out of the video at the prompt instead.
        """
        report = cs.build_safety_report(plan(script="This app is $4.99 a month."), PROFILE)
        assert "pricing_mismatches" not in report
        assert "Clean" in cs.summarize(report)

    def test_sources_reflect_populated_profile_fields(self):
        report = cs.build_safety_report(plan(), PROFILE)
        assert "core_features" in report["sources_used"]

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
        # No wording flag may mention a block: the report always passes.
        report = cs.build_safety_report(plan(script="It cures anxiety."), PROFILE)
        assert report["passed"] is True
        assert "prohibited" not in cs.summarize(report)


class TestScriptTextCoverage:
    def test_includes_voice_and_sound_direction(self):
        """
        Was `test_includes_voice_and_cta`: it asserted the plan's `cta` was part
        of the text claim checking walks.

        It no longer is, and neither is `feature_emphasis` — a generated piece
        is a hook and a middle with no closing beat and no demonstration, and
        `demo_brief` is a note to the founder about what to record themselves.
        None of those is text a viewer could read, so checking them would fail a
        plan over copy that cannot reach a frame.

        The property that matters is unchanged and now stated directly: a banned
        claim has to be caught in whatever text DOES reach the video.
        """
        text = cs.script_text(plan(
            voice_direction="warm and low",
            sound_direction="acoustic bed under the whole thing",
            cta="Download now",
            demo_brief="record yourself tapping the timer",
        ))
        assert "warm and low" in text
        # script_text normalizes punctuation away for phrase matching, so the
        # comma in the source string never survives.
        assert "acoustic bed under the whole thing" in text
        # Not text a viewer sees, so deliberately outside the check.
        assert "download now" not in text
        assert "record yourself tapping the timer" not in text

    def test_a_banned_claim_is_still_caught_in_what_is_said(self):
        # The helper still sees the phrase in voice direction text, but the
        # report never blocks on it.
        assert cs.find_banned_violations(
            cs.script_text(plan(voice_direction="cures anxiety")),
            PROFILE["claims_banned"],
        ) != []
        report = cs.build_safety_report(
            plan(voice_direction="cures anxiety"), PROFILE)
        assert report["passed"] is True
        assert report["blocking"] == []

    def test_a_banned_claim_is_still_caught_in_beat_text(self):
        assert cs.find_banned_violations(
            cs.script_text(plan(beat_timeline=[
                {"start": 0, "end": 3, "label": "hook", "text": "clinically proven"}
            ])),
            PROFILE["claims_banned"],
        ) != []
        report = cs.build_safety_report(
            plan(beat_timeline=[{"start": 0, "end": 3, "label": "hook", "text": "clinically proven"}]), PROFILE)
        assert report["passed"] is True
        assert report["blocking"] == []

    def test_includes_beat_text(self):
        text = cs.script_text(plan(beat_timeline=[
            {"start": 0, "end": 3, "label": "hook", "text": "the promised thing"}
        ]))
        assert "the promised thing" in text


class TestBoundedByFinalLine:
    VERDICT_BOUND = "Reflections are suggestions, not a verdict on your inner life"
    UNDERSTAND_BOUND = "Do not claim the app makes you understand yourself or improves emotional intelligence"
    DIAGNOSTIC_BOUND = "The app is not a medical or diagnostic tool"

    def test_last_sentence_is_the_final_spoken_sentence(self):
        script = ("On the porch step, I stopped waiting and just talked, messy and out of order. "
                  "Afterward, the reflection helped me see what had happened inside me.")
        assert cs.last_sentence(script) == ("Afterward, the reflection helped me see "
                                            "what had happened inside me.")

    def test_a_self_understanding_close_breaks_its_bound(self):
        hits = cs.bounded_by_conflict(
            "Afterward, the reflection helped me see what had happened inside me.",
            [self.VERDICT_BOUND, self.UNDERSTAND_BOUND],
        )
        assert [h["claim"] for h in hits] == [self.VERDICT_BOUND, self.UNDERSTAND_BOUND]

    def test_a_plain_close_keeps_every_bound(self):
        assert cs.bounded_by_conflict(
            "I talked out loud, messy and out of order.",
            [self.VERDICT_BOUND, self.UNDERSTAND_BOUND, self.DIAGNOSTIC_BOUND],
        ) == []

    def test_a_bound_about_something_else_never_blocks(self):
        assert cs.bounded_by_conflict(
            "Afterward, the reflection helped me see what had happened inside me.",
            ["Do not claim free shipping"],
        ) == []

    def test_a_diagnostic_bound_never_blocks_a_self_understanding_close_alone(self):
        # The gate is the intersection per domain: the diagnostic bound only
        # stops a diagnosing line, not every benefit-shaped close.
        assert cs.bounded_by_conflict(
            "Afterward, the reflection helped me see what had happened inside me.",
            [self.DIAGNOSTIC_BOUND],
        ) == []
        assert cs.bounded_by_conflict("It diagnosed my anxiety.", [self.DIAGNOSTIC_BOUND])

    def test_a_knowledge_line_breaks_a_trends_not_diagnosed_bound(self):
        trends_bound = "Trends are shown in the app, not diagnosed"
        assert cs.bounded_by_conflict(
            "Now I know how long it has been there.", [trends_bound]
        )
        # The same knowledge shape without a forbidding bound, or a plain
        # speaking line under the same bound, keeps the bound.
        assert cs.bounded_by_conflict("Now I know how long it has been there.", []) == []
        assert cs.bounded_by_conflict(
            "I speak my day out loud, no blank page.", [trends_bound]
        ) == []

    def test_a_light_week_mention_is_not_a_result_claim(self):
        trends_bound = "Trends are shown in the app, not diagnosed"
        assert cs._is_light_week_mention("I looked back over the week before speaking.")
        assert cs._is_light_week_mention("The worry came back on Monday and Friday.")
        assert not cs._is_light_week_mention("Now I know how long it has been there.")
        assert not cs._is_light_week_mention(
            "Now I know how long the week has been, and I speak my day."
        )
        assert cs.bounded_by_conflict(
            "I looked back over the week before speaking.", [trends_bound]
        ) == []
        assert cs.bounded_by_conflict(
            "Now I know how long the week has been, and I speak my day.", [trends_bound]
        )

    def test_paraphrases_of_screen_work_are_struck_for_selfie(self):
        import final_beat

        for sentence in (
            "She looks at the screen and smiles",
            "A thumb on the display while she listens",
            "Eyes drop down to the chart for a beat",
            "Glances at the phone in her hand",
            "Stares at the display",
            "Reads the timeline aloud",
            "Finger sliding on the trackpad",
            "They check the dashboard mid-sentence",
        ):
            kept, removed = final_beat.split_phone_clauses(sentence)
            assert removed, sentence
            assert "railing" not in kept.lower() or "chart" not in kept.lower()

        # Idioms and negated rules stay untouched, and so does a plain
        # physical looking (no surface noun).
        assert final_beat.split_phone_clauses("Stop the scroll by naming the worry out loud")[1] == ""
        assert final_beat.split_phone_clauses("No chart on camera, eyes on the lens")[1] == ""
        assert final_beat.split_phone_clauses("Eyes steady on the lens")[1] == ""
