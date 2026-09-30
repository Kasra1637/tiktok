"""
Curated Hook Template Library — the creative structures that drive generation.

A template is an ABSTRACT creative structure: an opening mechanic, a
continuation shape, a CTA pattern, and the assets a generation needs. It is
deliberately NOT a recording of a specific creator's clip. Nothing here
requires, references, or reproduces a source video, and no template needs a
source video to be used.

Deliberate wording rule: templates are "curated" and "based on recurring
high-performing hook mechanics". Nothing is called "proven" because no
internal performance data exists yet — `evidence_note` says so explicitly
until a template accumulates real results in this app's own history.

Kept separate from server.py for the same reason niches_config.py is: this is
curated content, not request handling. Seeding reads it; tests assert it.
"""

from typing import Optional

# ---------------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------------

# Hook categories. These are MECHANISMS (what stops the scroll), not genres.
HOOK_CATEGORIES = [
    "pattern-interrupt",
    "pain-point-question",
    "contrarian",
    "curiosity-gap",
    "before-after",
    "reveal",
    "demo",
    "tutorial",
    "story",
    "pov",
    "listicle",
    "social-proof",
    "other",
]

# Campaign objectives a founder can pick for a video.
VIDEO_OBJECTIVES = [
    "explain_app",
    "demonstrate_feature",
    "create_curiosity",
    "address_user_problem",
    "compare_alternative",
    "introduce_new_app",
    "promote_free_trial",
    "encourage_app_store_visit",
    "build_awareness",
    "educate_viewers",
]

# Content angles, per the product spec. Angles are app-specific and get
# generated per App Profile; this list is the controlled set of kinds.
CONTENT_ANGLE_KINDS = [
    "problem_solution",
    "before_after",
    "competitor_alternative",
    "feature_demonstration",
    "common_mistake",
    "fast_tutorial",
    "unexpected_benefit",
    "founder_story",
    "daily_life_use_case",
    "product_comparison",
    "objection_handling",
    "privacy_pricing_differentiation",
]

# Where a template row came from. `curated` rows ship with the app; a
# `research_draft` comes out of Trend Research and must be reviewed before it
# can be used; `custom` was created by an operator.
TEMPLATE_ORIGINS = ["curated", "research_draft", "custom"]

# Asset kinds a template can require. Drives the studio's asset picker and
# the Phase 6 deterministic overlay pass.
ASSET_KINDS = [
    "screenshot",
    "screen_recording",
    "logo",
    "product_image",
    "character_reference",
    "creator_photo",
    "background_image",
    "background_video",
    "audio",
]

# The honest evidence note for templates that have no measured performance yet.
_DEFAULT_EVIDENCE_NOTE = (
    "Curated from recurring high-performing hook mechanics. No internal "
    "performance data for this template yet."
)

# Minimum honest duration for each supported generation length. The studio
# clamps a request to the model's real capability rather than pretending.
SUPPORTED_DURATIONS = [10, 15, 20, 30]
DEFAULT_DURATION = 20


# ---------------------------------------------------------------------------
# Curated template seeds
# ---------------------------------------------------------------------------
# Each entry is abstract. `content_slots` are the fill-in points the creative
# plan fills for a specific app; `required_assets` is always exactly
# ["character_reference"] — the face that anchors every video. Nothing else
# is ever uploaded, attached, or composited.
CURATED_TEMPLATES = [
    {
        "name": "Pattern Interrupt",
        "category": "pattern-interrupt",
        "app_categories": [],
        "audiences": ["cold_audience", "scrollers"],
        "objective": "create_curiosity",
        "opening_structure": (
            "Open mid-motion on something visually unexpected in the first frame, then "
            "resolve it into the product question by ~1.5s."
        ),
        "hook_seconds": 2,
        "continuation_structure": (
            "Cut to the problem the product solves (2-5s), then the presenter living "
            "the solved state (5s-end), closing on the CTA."
        ),
        "cta_pattern": "soft_cta",
        "visual_style": "fast_cuts_high_contrast",
        "camera_pacing": "quick handheld, hard cut on the beat, no slow build",
        "required_assets": ["character_reference"],
        "default_duration": 15,
        "content_slots": {
            "pattern_beat": "the unexpected visual beat",
            "problem": "the pain the viewer recognises",
            "app_feature": "what the app does about it",
            "cta": "the single next action",
        },
    },
    {
        "name": "Pain-Point Question",
        "category": "pain-point-question",
        "app_categories": [],
        "audiences": ["cold_audience", "targeted_audience"],
        "objective": "address_user_problem",
        "opening_structure": (
            "Ask the viewer's problem out loud as a question in the first 2 seconds. "
            "It must be specific enough that the viewer recognises themselves."
        ),
        "hook_seconds": 3,
        "continuation_structure": (
            "Name the cost of leaving it unfixed (3-8s), show the resolved state "
            "on camera (8-16s), CTA (final seconds)."
        ),
        "cta_pattern": "problem_to_solution_cta",
        "visual_style": "talking_head_with_broll",
        "camera_pacing": "steady, eye-level, cut to broll on the answer",
        "required_assets": ["character_reference"],
        "default_duration": 20,
        "content_slots": {
            "question": "the pain-point question",
            "cost": "what it costs to ignore",
            "app_feature": "the feature that fixes it",
            "cta": "the single next action",
        },
    },
    {
        "name": "Stop Doing This",
        "category": "contrarian",
        "app_categories": [],
        "audiences": ["cold_audience", "power_users"],
        "objective": "address_user_problem",
        "opening_structure": (
            "Direct second-person confrontation: 'Stop doing X.' Deliver it as a "
            "correction, not a complaint."
        ),
        "hook_seconds": 2,
        "continuation_structure": (
            "Offer the correct approach and introduce the app as the tool that makes "
            "it easy, then CTA."
        ),
        "cta_pattern": "correction_cta",
        "visual_style": "talking_head_direct_address",
        "camera_pacing": "static, slight push-in for emphasis",
        "required_assets": ["character_reference"],
        "default_duration": 15,
        "content_slots": {
            "mistake": "the behaviour to stop",
            "correction": "what to do instead",
            "app_feature": "how the app helps",
            "cta": "the single next action",
        },
    },
    {
        "name": "I Wish I Knew This Earlier",
        "category": "curiosity-gap",
        "app_categories": [],
        "audiences": ["targeted_audience", "existing_users"],
        "objective": "create_curiosity",
        "opening_structure": (
            "Regret-shaped opener that withholds the payoff: 'I wish I'd known this "
            "earlier' with the reason held back for a beat."
        ),
        "hook_seconds": 3,
        "continuation_structure": (
            "Reveal the thing (3-6s), show it working in the presenter's world "
            "(6-16s), CTA."
        ),
        "cta_pattern": "reveal_cta",
        "visual_style": "talking_head_then_demo",
        "camera_pacing": "hold the reveal beat, then cut on the reveal",
        "required_assets": ["character_reference"],
        "default_duration": 20,
        "content_slots": {
            "regret": "the regret framing",
            "reveal": "what was revealed",
            "app_feature": "the feature being shown",
            "cta": "the single next action",
        },
    },
    {
        "name": "Three Mistakes",
        "category": "listicle",
        "app_categories": [],
        "audiences": ["targeted_audience", "power_users"],
        "objective": "educate_viewers",
        "opening_structure": (
            "Promise a specific count up front ('3 mistakes') and commit to delivering "
            "all three. No padding."
        ),
        "hook_seconds": 3,
        "continuation_structure": (
            "Mistake 1 (3-8s), 2 (8-13s), 3 (13-18s) with the app as the fix, CTA."
        ),
        "cta_pattern": "listicle_cta",
        "visual_style": "presenter_led_listicle",
        "camera_pacing": "one clear beat per item, count on camera",
        "required_assets": ["character_reference"],
        "default_duration": 20,
        "content_slots": {
            "promise": "the numbered promise",
            "mistakes": "the three mistakes, one per line",
            "app_feature": "the feature that fixes them",
            "cta": "the single next action",
        },
    },
    {
        "name": "POV Scenario",
        "category": "pov",
        "app_categories": [],
        "audiences": ["cold_audience", "niche_enthusiasts"],
        "objective": "build_awareness",
        "opening_structure": (
            "'POV: you're the person who [specific situation].' Put the viewer inside a "
            "recognisable moment immediately."
        ),
        "hook_seconds": 3,
        "continuation_structure": (
            "Run the scenario (3-10s), reveal the outcome the app made possible "
            "(10-16s), CTA."
        ),
        "cta_pattern": "scenario_cta",
        "visual_style": "presenter_led_scenario",
        "camera_pacing": "immersive, handheld, scene-first",
        "required_assets": ["character_reference"],
        "default_duration": 15,
        "content_slots": {
            "scenario": "the POV situation",
            "turn": "the turn that makes it work",
            "app_feature": "the app's role",
            "cta": "the single next action",
        },
    },
    {
        "name": "Curiosity Gap",
        "category": "curiosity-gap",
        "app_categories": [],
        "audiences": ["cold_audience", "scrollers"],
        "objective": "create_curiosity",
        "opening_structure": (
            "Show a partial result or a withheld detail and let the gap do the work. "
            "The gap must be resolvable inside the video."
        ),
        "hook_seconds": 3,
        "continuation_structure": (
            "Pay off the gap early (3-7s), then earn the rest of the watch with the "
            "presenter, CTA."
        ),
        "cta_pattern": "reveal_cta",
        "visual_style": "withheld_then_revealed",
        "camera_pacing": "hold the gap, reveal on a clean cut",
        "required_assets": ["character_reference"],
        "default_duration": 15,
        "content_slots": {
            "withheld": "what is deliberately not shown",
            "reveal": "the payoff",
            "app_feature": "how the app produced it",
            "cta": "the single next action",
        },
    },
    {
        "name": "Contrarian Statement",
        "category": "contrarian",
        "app_categories": [],
        "audiences": ["cold_audience", "skeptical_viewers"],
        "objective": "build_awareness",
        "opening_structure": (
            "State a position the category consensus disagrees with, and be specific "
            "enough to be falsifiable."
        ),
        "hook_seconds": 3,
        "continuation_structure": (
            "Justify the position with the product's actual behaviour (3-10s), "
            "acknowledge the honest counterargument (10-15s), CTA."
        ),
        "cta_pattern": "agreement_cta",
        "visual_style": "talking_head_with_evidence",
        "camera_pacing": "steady, cut to illustrative evidence on the justification",
        "required_assets": ["character_reference"],
        "default_duration": 20,
        "content_slots": {
            "contrarian_claim": "the disputed position",
            "justification": "why the product supports it",
            "concession": "the honest counterargument",
            "cta": "the single next action",
        },
    },
    {
        "name": "Short Transformation Story",
        "category": "story",
        "app_categories": [],
        "audiences": ["cold_audience", "targeted_audience"],
        "objective": "build_awareness",
        "opening_structure": (
            "Open on the turning point, not the setup. 'The thing that changed everything "
            "was...' — a first-person narrative beat."
        ),
        "hook_seconds": 3,
        "continuation_structure": (
            "Flash back the friction (3-8s), the app's role (8-15s), the present-day "
            "result (15-18s), CTA."
        ),
        "cta_pattern": "story_cta",
        "visual_style": "presenter_led_story",
        "camera_pacing": "measured, cut on the narrative beats",
        "required_assets": ["character_reference"],
        "default_duration": 20,
        "content_slots": {
            "turning_point": "the opening turn",
            "friction": "what was hard before",
            "app_role": "what the app did",
            "cta": "the single next action",
        },
    },
    {
        "name": "Day in the Life",
        "category": "story",
        "app_categories": [],
        "audiences": ["targeted_audience", "existing_users"],
        "objective": "build_awareness",
        "opening_structure": (
            "Drop into a normal moment with the app already in the routine. Mundane "
            "specificity is the hook."
        ),
        "hook_seconds": 3,
        "continuation_structure": (
            "Two or three routine moments (3-14s), show the cumulative effect, CTA."
        ),
        "cta_pattern": "routine_cta",
        "visual_style": "daylight_documentary",
        "camera_pacing": "natural, unpolished, chronological",
        "required_assets": ["character_reference"],
        "default_duration": 20,
        "content_slots": {
            "moment": "the routine moment",
            "app_moment": "where the app fits into it",
            "cumulative": "what the routine adds up to",
            "cta": "the single next action",
        },
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEMPLATE_NAME_MAX = 80
TEMPLATE_NOTES_MAX = 500


def normalize_category(category: Optional[str]) -> str:
    """Map free-form category input onto the controlled vocabulary."""
    c = (category or "").strip().lower().replace("_", "-").replace(" ", "-")
    return c if c in HOOK_CATEGORIES else "other"


def normalize_objective(objective: Optional[str]) -> str:
    o = (objective or "").strip().lower().replace("-", "_").replace(" ", "_")
    return o if o in VIDEO_OBJECTIVES else ""


def normalize_angle_kind(kind: Optional[str]) -> str:
    k = (kind or "").strip().lower().replace("-", "_").replace(" ", "_")
    return k if k in CONTENT_ANGLE_KINDS else "problem_solution"


def normalize_asset_kind(kind: Optional[str]) -> str:
    k = (kind or "").strip().lower().replace("-", "_").replace(" ", "_")
    return k if k in ASSET_KINDS else "screenshot"


def clamp_duration(seconds, model_max: int = 30) -> int:
    """
    Clamp a requested duration to the nearest supported value the model can do.

    Never returns a value above `model_max`: asking for 30s on a model capped
    at 15s silently produces a broken file rather than a clear error, so the
    clamp happens here and the caller reports the adjustment.
    """
    try:
        want = int(seconds)
    except (TypeError, ValueError):
        want = DEFAULT_DURATION
    ceiling = min(max(int(model_max), 1), max(SUPPORTED_DURATIONS))
    eligible = [d for d in SUPPORTED_DURATIONS if d <= ceiling]
    if not eligible:
        return min(ceiling, SUPPORTED_DURATIONS[-1])
    if want in eligible:
        return want
    lower = [d for d in eligible if d < want]
    if lower:
        return max(lower)
    return eligible[0]


def curated_template_rows() -> list:
    """
    Curated templates as insert-ready dicts.

    Every curated row gets `evidence_note` set to the honest default so no
    template can be described as proven without measured data.
    """
    rows = []
    for t in CURATED_TEMPLATES:
        row = dict(t)
        row.setdefault("evidence_note", _DEFAULT_EVIDENCE_NOTE)
        row.setdefault("is_favorite", 0)
        row.setdefault("archived", 0)
        row.setdefault("version", 1)
        row.setdefault("origin", "curated")
        row.setdefault("review_status", "approved")
        row.setdefault("audiences", [])
        row.setdefault("app_categories", [])
        row.setdefault("required_assets", [])
        rows.append(row)
    return rows


def find_curated_by_name(name: str) -> Optional[dict]:
    for t in CURATED_TEMPLATES:
        if t["name"].lower() == (name or "").strip().lower():
            return t
    return None
