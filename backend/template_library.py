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

Kept separate from server.py: this is curated content, not request handling.
Seeding reads it; tests assert it.
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
    "build_awareness",
    "educate_viewers",
    "achieve_desired_outcome",
    "overcome_viewer_doubt",
    "ease_daily_moment",
    "avoid_common_mistake",
    "feel_seen_and_understood",
]

# Six featured goals for each selected audience angle. The picker offers only
# these suggestions; existing saved goals and the full objective vocabulary
# remain valid for recommendations, persisted projects, and generation prompts.
# Order is the UI ranking; every recognized angle kind has exactly six goals.
ANGLE_GOAL_RECOMMENDATIONS = {
    "problem_solution": ("address_user_problem", "feel_seen_and_understood", "avoid_common_mistake", "create_curiosity", "ease_daily_moment", "educate_viewers"),
    "before_after": ("achieve_desired_outcome", "address_user_problem", "create_curiosity", "feel_seen_and_understood", "demonstrate_feature", "ease_daily_moment"),
    "competitor_alternative": ("compare_alternative", "overcome_viewer_doubt", "explain_app", "build_awareness", "demonstrate_feature", "achieve_desired_outcome"),
    "feature_demonstration": ("demonstrate_feature", "explain_app", "achieve_desired_outcome", "educate_viewers", "create_curiosity", "ease_daily_moment"),
    "common_mistake": ("avoid_common_mistake", "educate_viewers", "address_user_problem", "create_curiosity", "feel_seen_and_understood", "achieve_desired_outcome"),
    "fast_tutorial": ("educate_viewers", "demonstrate_feature", "explain_app", "achieve_desired_outcome", "create_curiosity", "avoid_common_mistake"),
    "unexpected_benefit": ("achieve_desired_outcome", "create_curiosity", "ease_daily_moment", "build_awareness", "explain_app", "feel_seen_and_understood"),
    "founder_story": ("build_awareness", "introduce_new_app", "feel_seen_and_understood", "overcome_viewer_doubt", "create_curiosity", "address_user_problem"),
    "daily_life_use_case": ("ease_daily_moment", "feel_seen_and_understood", "achieve_desired_outcome", "build_awareness", "demonstrate_feature", "address_user_problem"),
    "product_comparison": ("compare_alternative", "overcome_viewer_doubt", "explain_app", "build_awareness", "demonstrate_feature", "achieve_desired_outcome"),
    "objection_handling": ("overcome_viewer_doubt", "feel_seen_and_understood", "compare_alternative", "address_user_problem", "explain_app", "educate_viewers"),
    "privacy_pricing_differentiation": ("overcome_viewer_doubt", "compare_alternative", "explain_app", "build_awareness", "create_curiosity", "educate_viewers"),
}

# What each campaign objective leaves the viewer with, in the viewer's terms.
#
# This is what the recommender says when a template serves an objective: the
# outcome, not the taxonomy. Each clause describes what the footage DOES —
# where it leaves the person watching — never what it will earn. No reach,
# no conversion, no performance claim of any kind, which is the same honesty
# rule the evidence note follows. Keyed to VIDEO_OBJECTIVES above; the
# scorer falls back to a neutral clause for anything outside the vocabulary.
OBJECTIVE_OUTCOMES = {
    "explain_app": "walks them into what the app is without a feature list",
    "demonstrate_feature": "keeps them watching long enough to see it work",
    "create_curiosity": "leaves them wanting the answer",
    "address_user_problem": "gets them naming the problem out loud",
    "compare_alternative": "puts the choice in front of them honestly",
    "introduce_new_app": "gets them to recognise it and remember it",
    "build_awareness": "puts the app in their head as familiar",
    "educate_viewers": "leaves them with one thing they got wrong",
    "achieve_desired_outcome": "shows the outcome as reachable",
    "overcome_viewer_doubt": "takes the doubt seriously instead of dismissing it",
    "ease_daily_moment": "makes the daily moment feel lighter",
    "avoid_common_mistake": "catches them before the mistake",
    "feel_seen_and_understood": "makes them feel described, not sold to",
}

# Why each suggested goal fits the angle it was suggested for, in plain words.
#
# OBJECTIVE_OUTCOMES above says what a goal DOES in general; this says why
# that goal suits THIS angle kind. The picker shows it as optional explanatory
# text under the outcome so founders can choose among the six suggestions. It
# changes nothing about selection, ranking, or saving: every angle kind maps
# exactly its six ANGLE_GOAL_RECOMMENDATIONS entries, and anything outside
# the vocabulary simply has no fit line.
#
# Same honesty rule as the outcomes: each line describes the structural fit
# between the angle's mechanic and the goal — never reach, conversion, or any
# performance claim.
ANGLE_GOAL_FIT_REASONS = {
    "problem_solution": {
        "address_user_problem": "Fits because this angle starts from the problem itself.",
        "feel_seen_and_understood": "Fits because naming the problem makes viewers feel described.",
        "avoid_common_mistake": "Fits because the problem often comes from a repeated habit.",
        "create_curiosity": "Fits because the problem opens a gap the answer can fill.",
        "ease_daily_moment": "Fits because the problem shows up in an ordinary moment.",
        "educate_viewers": "Fits because the problem lets one correction land.",
    },
    "before_after": {
        "achieve_desired_outcome": "Fits because this angle is built around the change.",
        "address_user_problem": "Fits because the before names the starting problem.",
        "create_curiosity": "Fits because the gap between before and after invites a look.",
        "feel_seen_and_understood": "Fits because the before mirrors what viewers live now.",
        "demonstrate_feature": "Fits because the change needs something to explain it.",
        "ease_daily_moment": "Fits because the after lightens the same daily moment.",
    },
    "competitor_alternative": {
        "compare_alternative": "Fits because this angle puts the choice side by side.",
        "overcome_viewer_doubt": "Fits because switching raises doubts worth answering.",
        "explain_app": "Fits because a new option needs a plain introduction.",
        "build_awareness": "Fits because the alternative only helps if remembered.",
        "demonstrate_feature": "Fits because the difference is easier watched than told.",
        "achieve_desired_outcome": "Fits because the comparison ends on what changes.",
    },
    "feature_demonstration": {
        "demonstrate_feature": "Fits because this angle centers on one thing working.",
        "explain_app": "Fits because the feature needs its context named.",
        "achieve_desired_outcome": "Fits because the demo points at what it makes possible.",
        "educate_viewers": "Fits because watching corrects how it is usually done.",
        "create_curiosity": "Fits because a glimpse leaves the rest wanted.",
        "ease_daily_moment": "Fits because the feature lives in a daily routine.",
    },
    "common_mistake": {
        "avoid_common_mistake": "Fits because this angle names the mistake directly.",
        "educate_viewers": "Fits because the mistake is a chance to correct one belief.",
        "address_user_problem": "Fits because the mistake explains the ongoing problem.",
        "create_curiosity": "Fits because naming a mistake makes viewers check themselves.",
        "feel_seen_and_understood": "Fits because admitting the mistake feels familiar.",
        "achieve_desired_outcome": "Fits because avoiding it points at what opens up.",
    },
    "fast_tutorial": {
        "educate_viewers": "Fits because this angle teaches one quick thing.",
        "demonstrate_feature": "Fits because the lesson is easier shown than described.",
        "explain_app": "Fits because a quick how-to still needs what it is for.",
        "achieve_desired_outcome": "Fits because the tutorial ends on what they can now do.",
        "create_curiosity": "Fits because a first step hints at the next ones.",
        "avoid_common_mistake": "Fits because quick lessons can head off the usual error.",
    },
    "unexpected_benefit": {
        "achieve_desired_outcome": "Fits because the surprise is a reachable outcome.",
        "create_curiosity": "Fits because an unexpected claim invites a second look.",
        "ease_daily_moment": "Fits because the benefit lands in an ordinary moment.",
        "build_awareness": "Fits because a surprise makes the app memorable.",
        "explain_app": "Fits because the surprise needs its context named.",
        "feel_seen_and_understood": "Fits because the benefit names something viewers wanted.",
    },
    "founder_story": {
        "build_awareness": "Fits because the origin story makes the app familiar.",
        "introduce_new_app": "Fits because a new app needs its name and reason stated.",
        "feel_seen_and_understood": "Fits because the story shares the viewers frustration.",
        "overcome_viewer_doubt": "Fits because a personal story answers quiet skepticism.",
        "create_curiosity": "Fits because an origin leaves viewers wanting what came next.",
        "address_user_problem": "Fits because the story starts from the problem that prompted it.",
    },
    "daily_life_use_case": {
        "ease_daily_moment": "Fits because this angle lives inside the routine.",
        "feel_seen_and_understood": "Fits because the routine mirrors the viewers day.",
        "achieve_desired_outcome": "Fits because the routine shows the outcome as ordinary.",
        "build_awareness": "Fits because a familiar setting makes the app familiar.",
        "demonstrate_feature": "Fits because the moment is easier shown in place.",
        "address_user_problem": "Fits because the routine is where the friction shows.",
    },
    "product_comparison": {
        "compare_alternative": "Fits because this angle lays the options out honestly.",
        "overcome_viewer_doubt": "Fits because choosing raises doubts worth answering.",
        "explain_app": "Fits because comparison needs each side plainly stated.",
        "build_awareness": "Fits because being compared keeps the app in mind.",
        "demonstrate_feature": "Fits because the difference reads clearest when shown.",
        "achieve_desired_outcome": "Fits because the comparison ends on what each delivers.",
    },
    "objection_handling": {
        "overcome_viewer_doubt": "Fits because this angle takes the doubt head-on.",
        "feel_seen_and_understood": "Fits because voicing the doubt makes viewers feel heard.",
        "compare_alternative": "Fits because doubts often compare against the old way.",
        "address_user_problem": "Fits because the doubt points back to the real problem.",
        "explain_app": "Fits because answering needs the app stated plainly.",
        "educate_viewers": "Fits because the doubt rests on one correctable belief.",
    },
    "privacy_pricing_differentiation": {
        "overcome_viewer_doubt": "Fits because cost and privacy worries need answering.",
        "compare_alternative": "Fits because trust and price invite direct comparison.",
        "explain_app": "Fits because what it costs and keeps private needs stating.",
        "build_awareness": "Fits because a clear stance makes the app memorable.",
        "create_curiosity": "Fits because a different stance invites a closer look.",
        "educate_viewers": "Fits because pricing and privacy rest on one misunderstanding.",
    },
}


def angle_goal_fit_reason(kind: Optional[str], goal: Optional[str]) -> str:
    """Return the angle-specific fit line for one kind + goal, or "" when none."""
    return ANGLE_GOAL_FIT_REASONS.get((kind or "").strip(), {}).get((goal or "").strip(), "")

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
# `research_draft` is a legacy category retained for existing rows; `custom`
# was created by the wizard or an operator.
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
DEFAULT_DURATION = 15

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
        # Viewer-facing, not structural: what the person watching ends up
        # with. Every curated template carries one so the picker can lead
        # with the result instead of the mechanic. No performance claims --
        # the evidence-note rule applies here too.
        "outcome": "Stops mid-scroll on something they can't explain, then stays to work out what it meant.",
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
        "default_duration": 15,
        "content_slots": {
            "pattern_beat": "the unexpected visual beat",
            "situation": "the situation the beat came from",
            "moment": "the point where they reach for the app",
        },
    },
    {
        "name": "Pain-Point Question",
        "category": "pain-point-question",
        "outcome": "Hears their own frustration said out loud by someone else, and stops pretending it's manageable.",
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
        "default_duration": 15,
        "content_slots": {
            "question": "the pain-point question",
            "cost": "what it actually costs to ignore",
            "moment": "the decision to do something about it",
        },
    },
    {
        "name": "Stop Doing This",
        "category": "contrarian",
        "outcome": "Gets told, flatly, that what they're doing is costing them — and can't argue with it.",
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
        "default_duration": 15,
        "content_slots": {
            "instruction": "the thing to stop doing",
            "cost": "what the habit actually costs",
            "moment": "where they would notice a better way",
        },
    },
    {
        "name": "I Wish I Knew This Earlier",
        "category": "curiosity-gap",
        "outcome": "Recognises a version of their own past they'd rather not relive.",
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
        "default_duration": 15,
        "content_slots": {
            "regret": "the regret framing",
            "before": "the harder version of their day",
            "moment": "the exact thing that used to be difficult",
        },
    },
    {
        "name": "Three Mistakes",
        "category": "listicle",
        "outcome": "Catches themselves making the first mistake, before the second one is even named.",
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
        "default_duration": 15,
        "content_slots": {
            "count": "how many, stated in the hook",
            "first_mistake": "the mistake that lands in the middle",
            "moment": "where the presenter admits it",
        },
    },
    {
        "name": "POV Scenario",
        "category": "pov",
        "outcome": "Is inside their own worst-case day and sees the exact moment it turns around.",
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
        "default_duration": 15,
        "content_slots": {
            "scenario": "the second-person situation",
            "friction": "the specific thing that goes wrong in it",
            "moment": "where the alternative becomes obvious",
        },
    },
    {
        "name": "Curiosity Gap",
        "category": "curiosity-gap",
        "outcome": "Left holding an unanswered claim, still thinking about it after the scroll.",
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
        "default_duration": 15,
        "content_slots": {
            "claim": "the unsupported claim",
            "pressure": "what makes it doubtful",
            "moment": "the point the viewer needs answered",
        },
    },
    {
        "name": "Contrarian Statement",
        "category": "contrarian",
        "outcome": "Takes a side against what they assumed, and owes the video a watch to defend it.",
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
        "default_duration": 15,
        "content_slots": {
            "position": "the contradicted position",
            "justification": "the presenter's own experience of it",
            "counterargument": "the honest objection left standing",
        },
    },
    {
        "name": "Short Transformation Story",
        "category": "before-after",
        "outcome": "Sees the version of themselves they've outgrown, and what made the difference.",
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
        "default_duration": 15,
        "content_slots": {
            "changed": "what changed, stated in the hook",
            "before": "the specific before",
            "moment": "the reach for the phone",
        },
    },
    {
        "name": "Day in the Life",
        "category": "story",
        "outcome": "Recognises their own ordinary day as worth watching, and the one moment it could go better.",
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
