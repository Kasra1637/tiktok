"""Templates are generated from, checked against, and shown as the angle (ADR 0089).

Two failures are pinned here:

- a tailored card about a different problem than the one the founder picked;
- a card whose "Shape" and "In your video" lines describe two different
  openings.

Both are policy, not prompt hope: `check_template_relevance` drops the drifted
template, and `angle_scene.opening_shape` builds the one opening from the First
3 Seconds Promise.
"""
import angle_scene
from template_recommendations import (
    check_template_relevance,
    filter_relevant_templates,
    problem_anchors,
    score_template_for_angle,
)

# One angle, stated the way the wizard shows it: the Problem and the Promise
# name the same moment, and the promise is what the video opens on.
ANGLE = {
    "id": "a1",
    "kind": "problem_solution",
    "label": "Guessing a feeling before bed",
    "target_audience": "Anyone who cannot name what they feel",
    "user_problem": (
        "On the back step at night, before sleep, you type a guess like happy "
        "and delete it because nothing fits"
    ),
    "hook_promise": (
        "A woman on the back step types the word tired, deletes it, and says "
        "out loud that it is not it either"
    ),
    "app_feature": "Reflections",
    "desired_emotion": "Less stuck",
    "viewer_outcome": "A clearer read on the day",
    "claims_to_respect": [
        "Reflections are suggestions, not a verdict on anyone's inner life",
        "Do not claim the app replaces therapy or professional care",
    ],
}


def _template(name, opening, middle="Then it stops at the reach for the phone."):
    return {
        "id": name.lower().replace(" ", "-"),
        "name": name,
        "category": "pain-point-question",
        "objective": "address_user_problem",
        "opening_structure": opening,
        "middle_structure": middle,
        "app_categories": [],
        "audiences": [],
        "required_assets": ["character_reference"],
        "review_status": "approved",
    }


ON_TOPIC = _template(
    "Name the word that does not fit",
    "The person on the back step at night types the word tired, deletes it, and "
    "says out loud that it is not it either.",
)

# The exact drift the picker showed: templates about the app's general topic


class TestRelevance:
    def test_a_template_about_this_problem_passes(self):
        assert check_template_relevance(ON_TOPIC, ANGLE)["passes"]

    def test_a_template_about_another_problem_fails_with_a_reason(self):
        result = check_template_relevance(DRIFTED[1], ANGLE)
        assert not result["passes"]
        assert "different problem" in result["reason"]

    def test_the_whole_drifted_set_is_dropped(self):
        assert filter_relevant_templates(DRIFTED, ANGLE) == []

    def test_filtering_keeps_the_surviving_order(self):
        second = _template(
            "Say the feeling out loud",
            "The person deletes the word on the back step and says it is not it either.",
        )
        kept = filter_relevant_templates([DRIFTED[0], ON_TOPIC, second], ANGLE)
        assert [t["name"] for t in kept] == [ON_TOPIC["name"], second["name"]]

    def test_without_an_angle_nothing_is_dropped(self):
        # A caller with no angle (approval-time generation) has nothing to be
        # relevant to, so the check never invents a constraint.
        assert filter_relevant_templates(DRIFTED, None) == DRIFTED
        assert problem_anchors({}) == set()

    def test_identity_words_are_not_anchors(self):
        # Templates are written without a gender (ADR 0089), so "woman" could
        # never be shared and must not count against them.
        assert "woman" not in problem_anchors(ANGLE)
        assert "person" not in problem_anchors(ANGLE)


class TestOpeningShape:
    def test_shape_is_built_from_the_promise(self):
        shape = angle_scene.opening_shape(ANGLE)
        assert shape.startswith("The person on the back step types the word tired")
        assert shape.endswith(".")

    def test_shape_never_names_a_gender_or_a_role(self):
        shape = angle_scene.opening_shape(ANGLE)
        assert "woman" not in shape
        assert "founder" not in shape

    def test_shape_is_the_promise_and_nothing_else(self):
        # One character doing one thing: the shape may not carry a second
        # clause of its own, or the card describes two openings again.
        shape = angle_scene.opening_shape(
            ANGLE,
            _template("Name it", "Within the first 3 seconds the person holds both hands up."),
        )
        assert shape == (
            "The person on the back step types the word tired, deletes it, and says "
            "out loud that it is not it either."
        )

    def test_the_template_turn_is_its_own_line(self):
        development = angle_scene.opening_development(
            ANGLE, _template("Name it", "ignored", "Then the person names the gap out loud.")
        )
        assert development == "the person names the gap out loud"

    def test_a_middle_written_in_the_prompt_voice_keeps_its_action(self):
        # Model middles read like "The middle names the cost"; the card already
        # says "Develops as", so the label is dropped and the action stays.
        development = angle_scene.opening_development(
            ANGLE, _template("Name it", "ignored", "The middle names the cost of guessing.")
        )
        assert development == "names the cost of guessing"

    def test_a_middle_that_moves_the_video_is_not_used(self):
        # A middle that relocates the story is a second opening in disguise:
        # the card keeps the opening alone rather than showing both.
        template = _template("Name it", "ignored", "Then the person lies in bed at eleven at night.")
        assert angle_scene.opening_development(ANGLE, template) == ""
        assert "lies in bed" not in angle_scene.opening_shape(ANGLE, template)

    def test_a_template_never_states_its_own_opening_over_the_promise(self):
        shape = angle_scene.opening_shape(
            ANGLE,
            _template(
                "Journaling is not homework",
                "Within the first 3 seconds the founder says journaling is not homework.",
            ),
        )
        assert "journaling" not in shape
        assert "founder" not in shape

    def test_without_a_promise_the_template_opening_is_all_there_is(self):
        template = _template("Name it", "The founder holds both hands away from the keyboard.")
        assert angle_scene.opening_shape({}, template) == (
            "The person holds both hands away from the keyboard."
        )

    def test_an_approved_hook_line_is_the_shape_exactly_as_written(self):
        # ADR 0108: once a plan exists, the shape quotes what the video
        # actually opens with — never the promise's unspoken words.
        hook = "Waiting for the right words means the day goes unsaid."
        shape = angle_scene.opening_shape(ANGLE, _template("Name it", "ignored"), hook_line=hook)
        assert shape == hook
        assert "I will write it when they have the words" not in shape

    def test_an_approved_middle_is_the_development(self):
        development = angle_scene.opening_development(
            ANGLE,
            _template("Name it", "ignored",
                      "Then they pick up the phone and open the app."),
            middle=("On the porch step, I stopped waiting and just talked, "
                    "messy and out of order. Afterward, the reflection helped me see "
                    "what had happened inside me."),
        )
        assert development == "on the porch step, I stopped waiting and just talked, messy and out of order"
        assert "pick up the phone" not in development

    def test_the_scored_card_quotes_the_plan_when_one_exists(self):
        profile = {"id": "p1", "brand_name": "Vocolens", "app_category": "Health"}
        hook = "Waiting for the right words means the day goes unsaid."
        result = score_template_for_angle(
            ON_TOPIC, profile, ANGLE, "address_user_problem",
            hook_line=hook, middle="I talked and the day went unsaid.",
        )
        assert result["angle_scene"]["shape"] == hook
        assert result["angle_scene"]["development"] == "I talked and the day went unsaid"


class TestOpeningStaging:
    def test_staging_names_place_and_time_and_the_photo(self):
        staging = angle_scene.opening_staging(ANGLE)
        assert "Outdoors at night" in staging
        assert "photo you upload" in staging

    def test_staging_says_only_where_the_look_comes_from_with_no_place(self):
        staging = angle_scene.opening_staging({"hook_promise": "A hand reaches for the phone."})
        assert "photo you upload" in staging

    def test_no_promise_means_no_staging_line(self):
        assert angle_scene.opening_staging({}) == ""


class TestRecommendationPayload:
    def test_the_scored_card_carries_one_opening_and_the_relevance_verdict(self):
        profile = {"id": "p1", "brand_name": "Vocolens", "app_category": "Health"}
        result = score_template_for_angle(ON_TOPIC, profile, ANGLE, "address_user_problem")
        assert result["angle_scene"]["shape"].startswith("The person on the back step")
        assert "photo you upload" in result["angle_scene"]["staging"]
        assert result["relevance"]["passes"] is True
        assert "woman" not in result["angle_scene"]["moment"]

    def test_an_off_topic_card_says_why_on_the_card(self):
        # A tailored row for THIS profile that opens elsewhere is the failure
        # this check exists for, and the card says so in plain words.
        profile = {"id": "p1", "brand_name": "Vocolens", "app_category": "Health"}
        template = dict(DRIFTED[1], brand_profile_id="p1")
        result = score_template_for_angle(template, profile, ANGLE, "address_user_problem")
        assert result["relevance"]["passes"] is False
        assert result["limitations"][0] == result["relevance"]["reason"]

    def test_a_curated_shape_is_not_called_off_topic(self):
        # Curated rows are shapes the plan fills with this angle's problem, not
        # content about another one, so they keep a clean card and their score.
        profile = {"id": "p1", "brand_name": "Vocolens", "app_category": "Health"}
        result = score_template_for_angle(DRIFTED[1], profile, ANGLE, "address_user_problem")
        assert result["relevance"]["passes"] is False
        assert result["relevance"]["reason"] not in result["limitations"]

    def test_a_matching_outcome_cannot_rescue_an_off_topic_opening(self):
        # The payoff line and the visual notes describe the result and the
        # look; only what the viewer sees happen is evidence that this card is
        # about the founder's problem.
        template = dict(
            DRIFTED[1],
            outcome="Hears the exact moment a guessed word fails.",
            content_slots={"the_concrete_beat": "The word is not it either."},
            visual_style="Close on the back step at night.",
        )
        assert check_template_relevance(template, ANGLE)["passes"] is False

# (journaling) instead of the problem the founder picked.
DRIFTED = [
    _template("Journaling is not homework",
              "The viewer hears journaling described as schoolwork and feels permission to try again."),
    _template("The blank page stall",
              "The viewer recognizes the stall of an empty journal page and feels understood."),
    _template("Three reasons your journal keeps stalling",
              "The viewer hears the common reasons a journal stalls and picks the one they recognize."),
    _template("Who could pick up your phone",
              "The viewer hears their own hesitation about privacy named out loud."),
]
