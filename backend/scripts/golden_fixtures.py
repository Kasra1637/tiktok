"""Golden fixtures for the text-model benchmark.

Fifteen representative Hook + Story cases across the app's angles and
templates. Every fixture is a *known good* case: the expected plan output
passes the deterministic gates (spoken budget, one personal
pronoun, no screen narration, no forbidden result) and reads as a founder
would approve it. The benchmark runs each candidate model against the same
fixtures so a 0-10 rating is earned on identical inputs.

These are not founder projects. They are hand-written cases pinned to the
real `generate_content_angles`, `generate_creative_plan` and
`generate_video_strategy` signatures so the benchmark cannot drift from the
production prompts.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Every fixture carries the three inputs the text flows need: a profile, an
# angle, and a template. Angles vary across problem-solution, pain-point,
# transformation and contrarian kinds so the benchmark exercises statement,
# confession, observation and question hook forms.
PROFILE_SOCIAL = {
    "brand_name": "Vocolens",
    "brand_description": "Voice-first AI journal that helps you speak your day out loud.",
    "app_category": "Productivity",
    "core_features": [
        "One-tap voice journaling",
        "Weekly reflection",
        "Guided prompts",
        "Pattern surfacing",
    ],
    "problems_solved": [
        "blank-page journaling dread",
        "looping worry",
        "forgetting how the week felt",
    ],
    "icp_segments": ["busy professionals"],
    "desired_outcomes": ["name what happened without opening a notebook"],
    "target_audience": "busy professionals",
    "outcome_statements": [
        {
            "outcome": "say the day out loud instead of facing a blank page",
            "who_feels_it": "busy professionals",
            "from_feature": "One-tap voice journaling",
            "how_it_helps": "speaking skips the blank-page step entirely",
        }
    ],
    "known_limitations": "iOS and Android only.",
    "must_not_show": ["pending results"],
    "usage_moments": ["walking home"],
    "proof_moment": "one tap starts the journal",
    "viewer_objections": [
        {
            "objection": "typing at night is draining",
            "what_they_do_now": "type notes",
            "honest_answer": "speaking is the alternative here",
        }
    ],
}

ANGLE_BLANK_PAGE = {
    "kind": "problem_solution",
    "label": "The blank page",
    "target_audience": "busy professionals",
    "user_problem": "you never open the journal because the page stays blank",
    "hook_promise": "leaning on a park railing, speaking into the phone",
    "app_feature": "One-tap voice journaling",
    "viewer_outcome": "you name the day without opening a notebook",
    "desired_emotion": "relief",
    "claims_to_respect": [],
}

ANGLE_LOOPING_WORRY = {
    "kind": "pain_point",
    "label": "The looping worry",
    "target_audience": "busy professionals",
    "user_problem": "the same worry keeps coming back after a stressful call",
    "hook_promise": "leaning on a park railing, speaking the worry out loud",
    "app_feature": "One-tap voice journaling",
    "viewer_outcome": "you see the worry's shape across the week",
    "desired_emotion": "recognition",
    # Diagnosis bound: trends are shown, not diagnosed. A result claim
    # ("Now I know how long it's been there") must be rejected by the gates.
    "claims_to_respect": ["Trends are shown in the app, not diagnosed"],
}

ANGLE_FRIDAY_OFF = {
    "kind": "transformation",
    "label": "Friday evenings feel off",
    "target_audience": "busy professionals",
    "user_problem": "you cannot say why Friday evenings feel off",
    "hook_promise": "stepping onto a residential sidewalk at dusk, exhaling",
    "app_feature": "Weekly reflection",
    "viewer_outcome": "you notice the Friday pattern instead of going blank",
    "desired_emotion": "recognition",
    "claims_to_respect": ["Trends are shown in the app, not diagnosed"],
}

TEMPLATE_PARK = {
    "name": "The Public Confession",
    "category": "problem",
    "opening_structure": "State the problem as a public admission.",
    "hook_seconds": 3,
    "continuation_structure": "Describe the moment the viewer knows, then the shift.",
    "cta_pattern": "Try it",
    "visual_style": "Talking head.",
    "camera_pacing": "Steady.",
}

TEMPLATE_SIDEWALK = {
    "name": "The Evening Walk",
    "category": "transformation",
    "opening_structure": "Open on a moving moment, then name it.",
    "hook_seconds": 4,
    "continuation_structure": "One action, then one lingering thought.",
    "cta_pattern": "Try it",
    "visual_style": "Walking talking head.",
    "camera_pacing": "Walking pace.",
}

# Fifteen fixtures: five angles x three templates (or the closest pairing the
# suite needs). Each expected *input* is golden; the model output is
# unpinned — the benchmark rates what the model produces from it.
FIXTURES = [
    {"name": "blank-page/park", "profile": PROFILE_SOCIAL, "angle": ANGLE_BLANK_PAGE, "template": TEMPLATE_PARK, "duration": 20, "camera": "handheld"},
    {"name": "blank-page/sidewalk", "profile": PROFILE_SOCIAL, "angle": ANGLE_BLANK_PAGE, "template": TEMPLATE_SIDEWALK, "duration": 15, "camera": "handheld"},
    {"name": "looping-worry/park", "profile": PROFILE_SOCIAL, "angle": ANGLE_LOOPING_WORRY, "template": TEMPLATE_PARK, "duration": 20, "camera": "handheld"},
    {"name": "looping-worry/sidewalk", "profile": PROFILE_SOCIAL, "angle": ANGLE_LOOPING_WORRY, "template": TEMPLATE_SIDEWALK, "duration": 20, "camera": "fixed"},
    {"name": "friday-off/park", "profile": PROFILE_SOCIAL, "angle": ANGLE_FRIDAY_OFF, "template": TEMPLATE_PARK, "duration": 20, "camera": "handheld"},
    {"name": "friday-off/sidewalk", "profile": PROFILE_SOCIAL, "angle": ANGLE_FRIDAY_OFF, "template": TEMPLATE_SIDEWALK, "duration": 15, "camera": "handheld"},
    {"name": "blank-page/park-fixed", "profile": PROFILE_SOCIAL, "angle": ANGLE_BLANK_PAGE, "template": TEMPLATE_PARK, "duration": 15, "camera": "fixed"},
    {"name": "looping-worry/park-fixed", "profile": PROFILE_SOCIAL, "angle": ANGLE_LOOPING_WORRY, "template": TEMPLATE_PARK, "duration": 15, "camera": "fixed"},
    {"name": "friday-off/sidewalk-fixed", "profile": PROFILE_SOCIAL, "angle": ANGLE_FRIDAY_OFF, "template": TEMPLATE_SIDEWALK, "duration": 20, "camera": "fixed"},
    {"name": "blank-page/park-30", "profile": PROFILE_SOCIAL, "angle": ANGLE_BLANK_PAGE, "template": TEMPLATE_PARK, "duration": 30, "camera": "handheld"},
    {"name": "looping-worry/sidewalk-30", "profile": PROFILE_SOCIAL, "angle": ANGLE_LOOPING_WORRY, "template": TEMPLATE_SIDEWALK, "duration": 30, "camera": "handheld"},
    {"name": "friday-off/park-30", "profile": PROFILE_SOCIAL, "angle": ANGLE_FRIDAY_OFF, "template": TEMPLATE_PARK, "duration": 30, "camera": "handheld"},
    {"name": "blank-page/sidewalk-fixed", "profile": PROFILE_SOCIAL, "angle": ANGLE_BLANK_PAGE, "template": TEMPLATE_SIDEWALK, "duration": 20, "camera": "fixed"},
    {"name": "looping-worry/park-15", "profile": PROFILE_SOCIAL, "angle": ANGLE_LOOPING_WORRY, "template": TEMPLATE_PARK, "duration": 15, "camera": "handheld"},
    {"name": "friday-off/sidewalk-15", "profile": PROFILE_SOCIAL, "angle": ANGLE_FRIDAY_OFF, "template": TEMPLATE_SIDEWALK, "duration": 15, "camera": "handheld"},
]
