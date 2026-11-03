"""The on-screen person is never given a gender, a role or an identity (ADR 0089).

The founder uploads the photo of whoever is on camera, so a line that says "a
woman" or "the founder" invents an identity the image never had. These pin the
rewrite that every video-facing text field passes through.
"""
import character_policy as cp


class TestNeutralize:
    def test_gendered_noun_becomes_the_person(self):
        assert cp.neutralize(
            "A woman on a back step types the word tired and deletes it"
        ) == "The person on a back step types the word tired and deletes it"

    def test_role_label_becomes_the_person(self):
        assert cp.neutralize(
            "Within the first 3 seconds the founder says journaling is not homework."
        ) == "Within the first 3 seconds the person says journaling is not homework."

    def test_presenter_is_a_role_label_too(self):
        assert "presenter" not in cp.neutralize("The presenter looks into the lens.")

    def test_plural_noun_becomes_people(self):
        assert cp.neutralize("Two women compare notes.") == "Two people compare notes."

    def test_possessive_noun_keeps_the_possessive(self):
        assert cp.neutralize("The woman\u2019s own phone is in another room.") == (
            "The person's own phone is in another room."
        )

    def test_pronouns_keep_singular_agreement(self):
        # "the person" rather than "they": the verb after it stays correct.
        assert cp.neutralize("She deletes the guess her hand wrote.") == (
            "The person deletes the guess their hand wrote."
        )

    def test_object_pronoun_becomes_them(self):
        assert cp.neutralize("He tells her to breathe.") == "The person tells them to breathe."

    def test_an_owned_thing_stays_possessive(self):
        # "tells her friend" owns a friend; "told her" takes an object.
        assert cp.neutralize("He tells her friend.") == "The person tells their friend."

    def test_text_with_no_claim_is_untouched(self):
        text = "The person types the word tired and deletes it."
        assert cp.neutralize(text) == text

    def test_reflexive_and_possessive_pronouns(self):
        assert cp.neutralize("He asks himself, then checks hers.") == (
            "The person asks themselves, then checks theirs."
        )


class TestIdentityTerms:
    def test_reports_what_is_still_a_claim(self):
        assert cp.identity_terms("A woman and the founder") == ["A woman", "the founder"]

    def test_neutral_text_has_no_terms(self):
        assert cp.identity_terms(cp.neutralize("A woman tells the founder")) == []

    def test_is_neutral_agrees_with_the_rewrite(self):
        assert not cp.is_neutral("the man on the step")
        assert cp.is_neutral(cp.neutralize("the man on the step"))


class TestNeutralizeFields:
    def test_only_the_named_fields_are_rewritten(self):
        row = {"opening_structure": "The founder waves.", "demo_brief": "Record the founder."}
        out = cp.neutralize_fields(row, ("opening_structure",))
        assert out["opening_structure"] == "The person waves."
        # demo_brief addresses the founder themselves, so it keeps the word.
        assert out["demo_brief"] == "Record the founder."

    def test_the_source_record_is_not_mutated(self):
        row = {"name": "The founder's shape"}
        cp.neutralize_fields(row, ("name",))
        assert row["name"] == "The founder's shape"
