"""
Curated Hook Template Library — the creative structures that drive generation.

A template is an ABSTRACT creative structure: an opening mechanic, a middle
shape, and the assets a generation needs. It is deliberately NOT a recording of
a specific creator's clip. Nothing here requires, references, or reproduces a
source video, and no template needs a source video to be used.

WHAT A GENERATED VIDEO IS
-------------------------
Every video this product makes is TWO generated sections and nothing else:

    HOOK  (the first ~4s)  ->  MIDDLE (the rest)

The MIDDLE develops the hook and the situation it sets up. It stops at the
moment the viewer wants the app in their hand. The product demo and the call to
action are NOT generated — the founder records the demo and adds the CTA in
their own editor, so templates describe a video that deliberately ends before
the payoff.

That is why there is no CTA field and no "paid off by 15s" beat here any more.
A template that promised a closing action would be describing footage this
product does not make.

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
#
# "demo" and "tutorial" stay in the vocabulary but describe the OPENING only —
# a hook can promise a demonstration without the generated footage containing
# one. "The five things this app does" is a fine opening for a video whose demo
# the founder attaches later; what the generated middle must not do is deliver
# that demonstration itself. See the plan and strategy prompts, which is where
# the boundary is enforced.
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
#
# These describe what the WHOLE video is for, including the demo and CTA the
# founder attaches. "demonstrate_feature" is therefore still a legitimate
# goal: the generated sections earn the viewer's attention for a demonstration
# that happens after the generated footage ends. The generated sections are
# never asked to perform the demonstration.
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

# The single asset kind the product accepts. Drives the studio's asset picker
# and the facets endpoint. There used to be nine (screenshots, recordings,
# logos, photos, audio...); every video is now generated from the founder's
# photograph plus App Profile facts, so the character reference stands alone.
ASSET_KINDS = [
    "character_reference",
]

# The honest evidence note for templates that have no measured performance yet.
_DEFAULT_EVIDENCE_NOTE = (
    "Curated from recurring high-performing hook mechanics. No internal "
    "performance data for this template yet."
)

# The length of ONE generated piece. A video is a single render covering a
# hook and a middle; it is no longer assembled from a chain of segments, so
# these are the only lengths that exist.
#
# The ceiling is 15s because that is the longest single pass the only
# studio-eligible model can produce. The founder no longer picks a length — a
# template declares one for its mechanic and the strategy may settle lower, but
# never higher. See `clamp_duration`.
SUPPORTED_DURATIONS = [8, 10, 12, 15]
DEFAULT_DURATION = 10

# The longest piece any supported model can produce in one pass. 15s is
# minimax-h3's real ceiling, and a piece is one render — so this is a hard
# product limit rather than the top of a menu. A project saved before the
# one-render change can still carry 20s or 30s, and those are not longer
# videos: they are unrenderable, so they are brought down to this on read.
MAX_SUPPORTED_DURATION = max(SUPPORTED_DURATIONS)

# The opening beat of a piece. DIRECTORIAL, not a render length: nothing is
# rendered for exactly this many seconds. The whole piece is one render, and
# this is how much of the opening the hook has to land in.
#
# 4s is the ceiling. A hook that needs longer to land is not a hook, and the
# first four seconds are the only window a viewer decides in.
MAX_HOOK_SECONDS = 4
MIN_HOOK_SECONDS = 2


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
            "resolve it into the product question by ~2s."
        ),
        "hook_seconds": 2,
        "middle_structure": (
            "The unexpected beat resolves into the situation it came from, and the "
            "presenter is visibly in it — the problem they have right now, at the moment "
            "they would first reach for the app. End on them picking the phone up. The "
            "app is never shown working."
        ),
        "visual_style": "fast_cuts_high_contrast",
        "camera_pacing": "quick handheld, hard cut on the beat, no slow build",
        "required_assets": ["character_reference"],
        "default_duration": 10,
        "content_slots": {
            "pattern_beat": "the unexpected visual beat",
            "situation": "the situation the beat came from",
            "moment": "the point where they reach for the app",
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
        "middle_structure": (
            "Answer the question with the reality rather than the app: what the problem "
            "actually feels like, and what it costs to keep ignoring it. The presenter "
            "shows the friction, then the small decision to do something about it. Stop "
            "before the payoff."
        ),
        "visual_style": "talking_head_with_broll",
        "camera_pacing": "steady, eye-level, hold on the presenter's face for the cost",
        "required_assets": ["character_reference"],
        "default_duration": 12,
        "content_slots": {
            "question": "the pain-point question",
            "cost": "what it actually costs to ignore",
            "moment": "the decision to do something about it",
        },
    },
    {
        "name": "Stop Doing This",
        "category": "contrarian",
        "app_categories": [],
        "audiences": ["cold_audience", "scrollers"],
        "objective": "create_curiosity",
        "opening_structure": (
            "Tell the viewer to stop doing the thing they are currently doing, in under "
            "3 seconds, flatly enough to be worth arguing with."
        ),
        "hook_seconds": 2,
        "middle_structure": (
            "Justify the instruction by naming what the habit actually costs, and let the "
            "presenter be caught inside it rather than describing it. Build to the moment "
            "they would notice a better way. No correction is delivered on camera."
        ),
        "visual_style": "direct_to_camera_hard_cut",
        "camera_pacing": "still frame, one hard cut, no build",
        "required_assets": ["character_reference"],
        "default_duration": 10,
        "content_slots": {
            "instruction": "the thing to stop doing",
            "cost": "what the habit actually costs",
            "moment": "where they would notice a better way",
        },
    },
    {
        "name": "I Wish I Knew This Earlier",
        "category": "curiosity-gap",
        "app_categories": [],
        "audiences": ["targeted_audience", "existing_users"],
        "objective": "create_curiosity",
        "opening_structure": (
            "Regret-shaped opener that withholds the answer: 'I wish I'd known this "
            "earlier' with the reason held back."
        ),
        "hook_seconds": 3,
        "middle_structure": (
            "Stay inside the regret rather than resolving it. Show the version of the "
            "presenter's day that came before, and the specific thing that was harder "
            "then. The gap stays open: the answer is what the attached demo is for."
        ),
        "visual_style": "talking_head_intimate",
        "camera_pacing": "hold the beat, slow push, no cut on a reveal that isn't coming",
        "required_assets": ["character_reference"],
        "default_duration": 12,
        "content_slots": {
            "regret": "the regret framing",
            "before": "the harder version of their day",
            "moment": "the exact thing that used to be difficult",
        },
    },
    {
        "name": "Three Mistakes",
        "category": "listicle",
        "app_categories": [],
        "audiences": ["cold_audience", "targeted_audience"],
        "objective": "educate_viewers",
        "opening_structure": (
            "Promise a specific count in the first 3 seconds: three mistakes, named, and "
            "specific enough to be uncomfortable."
        ),
        "hook_seconds": 3,
        "middle_structure": (
            "Land the first mistake as a recognition — the presenter makes it, or admits "
            "to it. The count is never completed: the generated piece stops after the "
            "mistake lands, and the remaining beats belong to whatever the founder "
            "attaches."
        ),
        "visual_style": "talking_head_counted_on_screen_space",
        "camera_pacing": "one beat per cut, hold each mistake a beat longer than feels right",
        "required_assets": ["character_reference"],
        "default_duration": 10,
        "content_slots": {
            "count": "how many, stated in the hook",
            "first_mistake": "the mistake that lands in the middle",
            "moment": "where the presenter admits it",
        },
    },
    {
        "name": "POV Scenario",
        "category": "pov",
        "app_categories": [],
        "audiences": ["cold_audience", "scrollers"],
        "objective": "address_user_problem",
        "opening_structure": (
            "Drop the viewer into second person mid-scenario, in under 3 seconds, with no "
            "setup and no introduction."
        ),
        "hook_seconds": 3,
        "middle_structure": (
            "Play the scenario out from inside it rather than describing it afterwards. "
            "The presenter is the viewer, hitting the specific friction the app exists to "
            "remove. The piece ends mid-scenario, at the moment the alternative is obvious "
            "but not yet taken."
        ),
        "visual_style": "first_person_vlog",
        "camera_pacing": "handheld, continuous, no establishing shot",
        "required_assets": ["character_reference"],
        "default_duration": 12,
        "content_slots": {
            "scenario": "the second-person situation",
            "friction": "the specific thing that goes wrong in it",
            "moment": "where the alternative becomes obvious",
        },
    },
    {
        "name": "Curiosity Gap",
        "category": "curiosity-gap",
        "app_categories": [],
        "audiences": ["cold_audience", "scrollers"],
        "objective": "create_curiosity",
        "opening_structure": (
            "Open on a claim the video will not support, stated flatly enough that the "
            "viewer needs to see what happens next. The gap must be answerable by what "
            "comes AFTER this generated piece."
        ),
        "hook_seconds": 3,
        "middle_structure": (
            "Add pressure to the claim instead of resolving it — show the presenter living "
            "the thing that makes the claim doubtful. The gap stays deliberately open at "
            "the cut. The generated footage is not permitted to pay it off."
        ),
        "visual_style": "tight_talking_head",
        "camera_pacing": "no cuts, one long take, framing gets tighter",
        "required_assets": ["character_reference"],
        "default_duration": 10,
        "content_slots": {
            "claim": "the unsupported claim",
            "pressure": "what makes it doubtful",
            "moment": "the point the viewer needs answered",
        },
    },
    {
        "name": "Contrarian Statement",
        "category": "contrarian",
        "app_categories": [],
        "audiences": ["cold_audience", "scrollers"],
        "objective": "create_curiosity",
        "opening_structure": (
            "State a position the viewer's default assumption contradicts, in under 3 "
            "seconds, without hedging it."
        ),
        "hook_seconds": 3,
        "middle_structure": (
            "Justify the position with the presenter's own experience rather than the "
            "app's feature list, and name the honest counterargument out loud. The piece "
            "stops while the counterargument is still standing, so the demo that follows "
            "has something left to answer."
        ),
        "visual_style": "direct_to_camera",
        "camera_pacing": "locked frame, one cut, no music swell",
        "required_assets": ["character_reference"],
        "default_duration": 12,
        "content_slots": {
            "position": "the contradicted position",
            "justification": "the presenter's own experience of it",
            "counterargument": "the honest objection left standing",
        },
    },
    {
        "name": "Short Transformation Story",
        "category": "before-after",
        "app_categories": [],
        "audiences": ["targeted_audience", "existing_users"],
        "objective": "address_user_problem",
        "opening_structure": (
            "Open on the present-day presenter and name what changed, in under 3 seconds, "
            "with the before deliberately withheld."
        ),
        "hook_seconds": 3,
        "middle_structure": (
            "Go back to the friction: the specific before, filmed as the presenter "
            "remembers it rather than reconstructed. The after is stated as something "
            "they will go and do, and the piece ends on the reach for the phone. The "
            "transformation itself is never shown on camera."
        ),
        "visual_style": "present_day_then_memory",
        "camera_pacing": "clean present-tense, then one soft cut back",
        "required_assets": ["character_reference"],
        "default_duration": 12,
        "content_slots": {
            "changed": "what changed, stated in the hook",
            "before": "the specific before",
            "moment": "the reach for the phone",
        },
    },
    {
        "name": "Day in the Life",
        "category": "story",
        "app_categories": [],
        "audiences": ["targeted_audience", "existing_users"],
        "objective": "build_awareness",
        "opening_structure": (
            "Drop into an ordinary moment with no setup, in under 3 seconds. Mundane "
            "specificity is the hook."
        ),
        "hook_seconds": 3,
        "middle_structure": (
            "Stay in the routine and let it accumulate — two ordinary moments, filmed as "
            "they actually happen, with the friction building quietly across them. Stop "
            "at the moment the routine would be interrupted by something better."
        ),
        "visual_style": "daylight_documentary",
        "camera_pacing": "natural, unpolished, chronological",
        "required_assets": ["character_reference"],
        "default_duration": 15,
        "content_slots": {
            "moment": "the ordinary opening moment",
            "routine": "the second moment that shows it repeating",
            "moment_two": "where the routine breaks",
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
    """
    Map free-form kind input onto the controlled vocabulary.

    Face-only library: anything that is not the character reference
    normalizes to "". Callers treat "" as absent — the upload endpoint
    refuses it, the list filter matches nothing — so a retired or mistyped
    kind can never silently become a screenshot overlay the way the old
    "screenshot" fallback allowed.
    """
    k = (kind or "").strip().lower().replace("-", "_").replace(" ", "_")
    return k if k in ASSET_KINDS else ""


def clamp_duration(seconds, model_max: int = 0) -> int:
    """
    Clamp a requested piece length to what the model can actually produce in one pass.

    Never returns a value above `model_max`: asking for more than the provider
    can render in a single pass silently produces a broken file rather than a
    clear error, so the clamp happens here and the caller reports the
    adjustment.

    `model_max` defaults to 0, meaning "ask the model". Callers that have not
    loaded provider capability would otherwise fall back to a 30s ceiling this
    product can no longer reach — a video is now one render, not a chain, so
    exceeding a single pass is not a longer video but a failed one.
    """
    if not model_max:
        # Imported here rather than at module scope: video_providers imports
        # nothing from this module, and a top-level import would make the
        # curated-content module depend on provider config just to seed tests.
        import video_providers

        model_max = int(video_providers.capability().get("max_duration") or 15)
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
