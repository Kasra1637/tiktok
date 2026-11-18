"""The "Develops as" line is a complete sentence (ADR 0196).

Kasra's Nov 17 2026 screenshot: a template card's "Develops as"
read "develops the interruption by contrasting the slow typing
habit with speaking through racing thoughts at the orchard gate,
and it educates the viewer..." — lowercase, subject stripped,
starting mid-sentence. A Nov 14 card read "keeps the person at
the bus stop in the same held position while...". The assembly
layer did that on purpose for a clause reading: it lowercased
the first letter, stripped the terminal period, and regex-stripped
leading subjects ("The video", "The middle") because the card
label was meant to carry the sentence. The founder reads the
value as a sentence, so the value now IS one: subject kept (a
meta subject — "The middle" — becomes the video it describes),
capital start, terminal period.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import angle_scene


def _angle(problem, promise):
    return {
        "id": "a1",
        "kind": "problem_solution",
        "label": "x",
        "target_audience": "Anyone who cannot name what they feel",
        "user_problem": problem,
        "hook_promise": promise,
        "app_feature": "Voice-first journaling",
        "desired_emotion": "Less stuck",
        "viewer_outcome": "A clearer read on the day",
        "claims_to_respect": [],
    }


def _template(middle):
    return {
        "id": "t1",
        "name": "T",
        "category": "pain-point-question",
        "objective": "address_user_problem",
        "opening_structure": "ignored",
        "middle_structure": middle,
        "app_categories": [],
        "audiences": [],
        "required_assets": ["character_reference"],
        "review_status": "approved",
    }


ORCHARD_ANGLE = _angle(
    "On Monday morning at an orchard gate, the person feels thoughts "
    "outrun their hands and typing is too slow before the day starts",
    "The person at the orchard gate says the feeling out loud instead of typing it",
)
BUS_STOP_ANGLE = _angle(
    "At the bus stop on the way home, the person cannot name what they feel",
    "The person at the bus stop holds still and says the feeling out loud",
)
PLAIN_ANGLE = _angle(
    "On the back step at night, before sleep, you type a guess like happy "
    "and delete it because nothing fits",
    "The person on the back step types the word tired, deletes it, and says "
    "out loud that it is not it either",
)


class TestDevelopsAsIsASentence:
    def test_the_orchard_gate_screenshot_shape(self):
        development = angle_scene.opening_development(
            ORCHARD_ANGLE,
            _template(
                "The video develops the interruption by contrasting the slow "
                "typing habit with speaking through racing thoughts at the "
                "orchard gate, and it educates the viewer about naming "
                "feelings out loud."
            ),
        )
        assert development == (
            "The video develops the interruption by contrasting the slow "
            "typing habit with speaking through racing thoughts at the "
            "orchard gate, and it educates the viewer about naming "
            "feelings out loud."
        )

    def test_the_bus_stop_screenshot_shape(self):
        development = angle_scene.opening_development(
            BUS_STOP_ANGLE,
            _template(
                "The video keeps the person at the bus stop in the same "
                "held position while the traffic passes."
            ),
        )
        assert development == (
            "The video keeps the person at the bus stop in the same "
            "held position while the traffic passes."
        )

    def test_a_meta_subject_becomes_the_video(self):
        # "The middle names the cost" names the writing, not the video;
        # the sentence keeps a subject — the video itself.
        development = angle_scene.opening_development(
            PLAIN_ANGLE, _template("The middle names the cost of guessing.")
        )
        assert development == "The video names the cost of guessing."

    def test_a_then_opening_keeps_its_subject(self):
        development = angle_scene.opening_development(
            PLAIN_ANGLE, _template("Then the person names the gap out loud.")
        )
        assert development == "Then the person names the gap out loud."

    def test_a_lowercase_model_sentence_is_capitalized_not_stripped(self):
        development = angle_scene.opening_development(
            PLAIN_ANGLE, _template("the person names the gap out loud.")
        )
        assert development == "The person names the gap out loud."

    def test_the_handoff_echo_still_leaves_no_development(self):
        # A middle that was nothing but the writer's instruction echo is
        # still not a beat: the card keeps the opening alone.
        development = angle_scene.opening_development(
            PLAIN_ANGLE, _template("Then it stops at the reach for the phone.")
        )
        assert development == ""

    def test_an_approved_middle_is_a_sentence_with_its_period(self):
        development = angle_scene.opening_development(
            PLAIN_ANGLE,
            _template("ignored"),
            middle=(
                "On the porch step, I stopped waiting and just talked, "
                "messy and out of order. Afterward, the reflection helped "
                "me see what had happened inside me."
            ),
        )
        assert development == (
            "On the porch step, I stopped waiting and just talked, "
            "messy and out of order."
        )
