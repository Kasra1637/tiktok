"""Shared helpers and Pydantic request models."""
import json
from datetime import datetime, timezone
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, StrictInt


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_to_dict(row, columns: list) -> dict:
    """Convert an sqlite3.Row to a dict, parsing JSON fields."""
    JSON_FIELDS = {
        "frames", "generation_spec", "generated_images", "prompt_breakdown",
        "reference_image_ids", "selected_image_ids", "replicable_mechanics",
        "products_services", "messages", "brief", "hashtags", "sound_reference",
        # App Profile (brand_profiles) structured fields
        "support_urls", "platforms", "core_features", "primary_use_cases",
        "problems_solved", "icp_segments", "desired_outcomes",
        "must_not_show", "usage_moments", "viewer_objections",
        "outcome_statements",
        "claims_approved", "claims_review", "claims_banned",
        "ctas", "video_themes", "research_sources", "pending_research",
        # Hook Template Library (hook_templates) structured fields
        "app_categories", "audiences", "required_assets", "content_slots",
        "claims_to_respect", "evidence", "trend_evidence",
        # Studio projects (structured plan fields)
        "beat_timeline", "overlays", "assets", "safety_report",
        # App-specific influencer strategy + per-generation continuity record
        "strategy", "continuity",
        # Generation lineage and refinement history
        "variation_params", "adjustments",
        # Overlay compositions
        "spec", "applied",
    }
    d = {}
    for i, col in enumerate(columns):
        val = row[i]
        if col in JSON_FIELDS and isinstance(val, str):
            try:
                val = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
        d[col] = val
    return d


class OpeningMessagesRequest(BaseModel):
    profile_id: Optional[str] = None
    previous: List[str] = Field(default_factory=list, max_length=20)


class CustomizeRequest(BaseModel):
    environment: Optional[str] = ""
    background: Optional[str] = ""
    clothing: Optional[str] = ""
    custom_instructions: Optional[str] = ""


class BrandContextRequest(BaseModel):
    brand_name: str = ""
    brand_goal: str = ""
    brand_details: str = ""
    duration_seconds: int = 30
    use_original_sound: bool = False


class AppProfileResearchRequest(BaseModel):
    """
    Research a mobile app from its store listings and generate a draft App Profile.

    An App Store URL, a Google Play URL, or both are required — store listings
    are the only creation path. support_urls is capped server-side; notes
    are founder-supplied context passed straight to the research prompt.
    """
    appstore_url: Optional[str] = None
    play_url: Optional[str] = None
    support_urls: Optional[List[str]] = None
    notes: Optional[str] = ""


class ApproveAppProfileRequest(BaseModel):
    """
    Approve an App Profile. When a refresh proposal is pending, it is applied
    to the live fields by default (apply_pending=True) and the version bumps.
    Pass apply_pending=False to approve the current fields as-is and keep the
    pending proposal for later review.
    """
    apply_pending: Optional[bool] = True


# Fields shared by App Profile create/update payloads.
#
# Lists of plain phrases. They serialize to JSON text columns, and the API
# accepts either a list or a comma-separated string.
APP_PROFILE_LIST_FIELDS = (
    "support_urls", "platforms", "core_features", "primary_use_cases",
    "problems_solved", "icp_segments", "desired_outcomes",
    "must_not_show", "usage_moments", "claims_approved",
    "claims_review", "claims_banned",
)

# Lists of objects. Same JSON text column, but the members cannot go through
# _normalize_str_list: that flattens a dict to its "label"/"name" key, which
# these triples do not have, so every entry would serialize to "".
APP_PROFILE_OBJECT_LIST_FIELDS = ("viewer_objections", "outcome_statements")

APP_PROFILE_TEXT_FIELDS = (
    "website_url", "appstore_url", "play_url", "notes", "brand_name",
    "brand_description", "niche", "app_category", "target_audience",
    "ideal_customer_profile", "differentiation", "tone_voice",
    "known_limitations", "proof_moment", "raw_extracted_text",
)

APP_PROFILE_EDITABLE_FIELDS = (
    APP_PROFILE_TEXT_FIELDS + APP_PROFILE_LIST_FIELDS + APP_PROFILE_OBJECT_LIST_FIELDS
)


class ViewerObjection(BaseModel):
    """
    One reason this viewer would not download, and the honest reply.

    `what_they_do_now` is the field that makes it usable: an objection without
    the current alternative has nothing to turn against, so the beat can only
    restate the feature.
    """
    objection: str = ""
    what_they_do_now: str = ""
    honest_answer: str = ""


class OutcomeStatement(BaseModel):
    """
    One feature translated into its resulting benefit, linked to its source.

    `from_feature` is the field that makes the layer usable downstream: an
    outcome without its source feature leaves every prompt guessing the
    mapping, which is how pitches decay into feature lists. `how_it_helps`
    feeds the mechanism moment (benefit-framed how-it-works); `outcome`
    feeds the payoff moment (the benefit stated directly).
    """
    outcome: str = ""
    who_feels_it: str = ""
    from_feature: str = ""
    how_it_helps: str = ""


class BrandProfileCreateRequest(BaseModel):
    """
    Create a brand profile from manually entered fields.

    The website-analysis path is optional — users without a scrapeable site
    (or whose site fails to fetch) need to be able to fill this in by hand.
    """
    website_url: Optional[str] = None
    brand_name: str
    brand_description: Optional[str] = ""
    niche: Optional[str] = ""
    target_audience: Optional[str] = ""
    ideal_customer_profile: Optional[str] = ""
    differentiation: Optional[str] = ""
    tone_voice: Optional[str] = ""
    # App Profile extensions — all optional so legacy brand creation is unaffected.
    appstore_url: Optional[str] = None
    play_url: Optional[str] = None
    support_urls: Optional[List[str]] = None
    notes: Optional[str] = ""
    app_category: Optional[str] = ""
    platforms: Optional[List[str]] = None
    core_features: Optional[List[str]] = None
    primary_use_cases: Optional[List[str]] = None
    problems_solved: Optional[List[str]] = None
    icp_segments: Optional[List[str]] = None
    desired_outcomes: Optional[List[str]] = None
    known_limitations: Optional[str] = ""
    # Enforced in the video prompt. known_limitations is advisory context for
    # the plan and strategy; this one is attached to the render that could
    # violate it, on every segment.
    must_not_show: Optional[List[str]] = None
    usage_moments: Optional[List[str]] = None
    proof_moment: Optional[str] = ""
    viewer_objections: Optional[List[ViewerObjection]] = None
    outcome_statements: Optional[List[OutcomeStatement]] = None
    claims_approved: Optional[List[str]] = None
    claims_review: Optional[List[str]] = None
    claims_banned: Optional[List[str]] = None


class BrandProfileUpdateRequest(BaseModel):
    website_url: Optional[str] = None
    brand_name: Optional[str] = None
    brand_description: Optional[str] = None
    niche: Optional[str] = None
    target_audience: Optional[str] = None
    ideal_customer_profile: Optional[str] = None
    differentiation: Optional[str] = None
    tone_voice: Optional[str] = None
    raw_extracted_text: Optional[str] = None
    # App Profile extensions (same semantics as create).
    appstore_url: Optional[str] = None
    play_url: Optional[str] = None
    support_urls: Optional[List[str]] = None
    notes: Optional[str] = None
    app_category: Optional[str] = None
    platforms: Optional[List[str]] = None
    core_features: Optional[List[str]] = None
    primary_use_cases: Optional[List[str]] = None
    problems_solved: Optional[List[str]] = None
    icp_segments: Optional[List[str]] = None
    desired_outcomes: Optional[List[str]] = None
    known_limitations: Optional[str] = None
    must_not_show: Optional[List[str]] = None
    usage_moments: Optional[List[str]] = None
    proof_moment: Optional[str] = None
    viewer_objections: Optional[List[ViewerObjection]] = None
    outcome_statements: Optional[List[OutcomeStatement]] = None
    claims_approved: Optional[List[str]] = None
    claims_review: Optional[List[str]] = None
    claims_banned: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Hook Template Library
# ---------------------------------------------------------------------------
# Templates are code-owned (template_library.py), research-produced, or
# brand-tailored per profile + objective; there is no hand-edit path, so no
# create/update request models exist. The picker reads curated rows through
# list/recommendations, and research drafts are approved through the publish
# endpoint.


class ObjectiveTemplatesRequest(BaseModel):
    """Tailored template set for one profile and one selected objective."""
    objective: str = ""
    regenerate: bool = False


# ---------------------------------------------------------------------------
# Content angles
# ---------------------------------------------------------------------------
# `recommended_cta` used to be on both angle requests. It is gone: an angle is
# material for a hook and a middle, and a generated piece has no closing beat.
# The column stays in SQLite for rows written before this, and nothing reads or
# writes it.
class CreateContentAngleRequest(BaseModel):
    """Add one hand-written content angle to an App Profile."""
    kind: str = "problem_solution"
    label: Optional[str] = ""
    target_audience: Optional[str] = ""
    user_problem: Optional[str] = ""
    hook_promise: Optional[str] = ""
    app_feature: Optional[str] = ""
    desired_emotion: Optional[str] = ""
    claims_to_respect: Optional[List[str]] = None


class UpdateContentAngleRequest(BaseModel):
    kind: Optional[str] = None
    label: Optional[str] = None
    target_audience: Optional[str] = None
    user_problem: Optional[str] = None
    hook_promise: Optional[str] = None
    app_feature: Optional[str] = None
    desired_emotion: Optional[str] = None
    claims_to_respect: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Studio projects (the guided creation workflow)
# ---------------------------------------------------------------------------
STUDIO_TEXT_FIELDS = (
    "audience", "tone", "hook_line", "script", "visual_direction",
    "demo_brief", "voice_direction", "sound_direction",
)
# `cta` and `feature_emphasis` used to be here. Neither is any more: a call to
# action is the founder's own, added in their editor after the demo they
# record, and a feature instruction in an editable field is a product demo being
# planned. `demo_brief` replaces the second — the founder still needs to know
# what to record, so the plan works it out, but it is deliberately never passed
# to the render.
#
# The columns themselves stay in the schema. SQLite cannot cheaply drop a
# column across every deployment, and leaving two unused TEXT columns costs
# nothing next to rewriting existing rows to match a shape they were never in.

# `overlays` was here too, while burned-in captions were composited onto Hook
# + Story clips. The column stays (see above); the field is no longer writable
# because there is no renderer left to read it.
STUDIO_EDITABLE_FIELDS = STUDIO_TEXT_FIELDS + (
    "content_angle_id", "template_id", "objective", "duration_seconds",
    "beat_timeline", "assets", "strategy", "hook_seconds", "camera_setup",
)


class CreateStudioProjectRequest(BaseModel):
    """
    Start a creation draft.

    Only brand_profile_id is required: the founder can pick an angle, objective,
    and template later, and the plan step will refuse to run without them.

    hook_seconds is the opening segment's length, NOT the total video length —
    that is duration_seconds. 0 means "decide from the template".
    """
    brand_profile_id: str
    camera_setup: Literal["handheld", "fixed"] = "handheld"
    content_angle_id: Optional[str] = ""
    template_id: Optional[str] = ""
    objective: Optional[str] = ""
    duration_seconds: Optional[int] = None
    hook_seconds: Optional[int] = 0
    # `extend_intent` used to be here — "hook only" versus "extend into a full
    # video". There is one render now, so the video is always a hook and a
    # middle and the question cannot be asked. Accepted so an old client is not
    # rejected with a validation error, and written nowhere.
    tone: Optional[str] = ""
    audience: Optional[str] = ""


class UpdateStudioProjectRequest(BaseModel):
    """Edit any draft field. Every field optional; only set fields change."""
    camera_setup: Literal["handheld", "fixed"] = "handheld"
    content_angle_id: Optional[str] = None
    template_id: Optional[str] = None
    objective: Optional[str] = None
    duration_seconds: Optional[int] = None
    hook_seconds: Optional[int] = None
    tone: Optional[str] = None
    audience: Optional[str] = None
    hook_line: Optional[str] = None
    script: Optional[str] = None
    beat_timeline: Optional[List[dict]] = None
    visual_direction: Optional[str] = None
    # `demo_brief` replaced `feature_emphasis` here as well as on the plan. The
    # plan writes it and STUDIO_TEXT_FIELDS counts it as content, so a founder
    # editing the review step could not have corrected the one field that tells
    # them what to record for their own demo.
    demo_brief: Optional[str] = None
    voice_direction: Optional[str] = None
    sound_direction: Optional[str] = None
    assets: Optional[List[dict]] = None
    # The app-specific strategy is editable so a founder can correct the hook
    # line or tighten the locked persona without paying to regenerate. Edits
    # bump strategy_version, which invalidates any unapproved segment built
    # against the old one.
    strategy: Optional[dict] = None


class GeneratePlanRequest(BaseModel):
    """
    Optional overrides for a plan regeneration.

    Empty means "reuse what the project already has", which is what a
    regenerate-after-review flow wants.
    """
    objective: Optional[str] = None
    duration_seconds: Optional[int] = None
    tone: Optional[str] = None
    audience: Optional[str] = None


class GenerateStrategyRequest(BaseModel):
    """
    Optional overrides for the app-specific video strategy.

    hook_seconds defaults to the project's own hook length and is clamped to
    2-4 seconds: the whole window a hook has to land in. That is the boundary
    between the hook and the middle within the single render, not a render
    length — nothing is rendered for exactly this many seconds.
    """
    objective: Optional[str] = None
    duration_seconds: Optional[int] = None
    tone: Optional[str] = None
    hook_seconds: Optional[int] = None


# GenerateHookRequest, ApproveSegmentRequest and AssembleChainRequest are gone.
# They described submitting a hook as its own job, approving it, and joining an
# approved chain — a segmented workflow in which a video was several renders.
# A video is one render of a hook and a middle now, so there is nothing to
# submit separately, approve between renders, or join.
# AssembleChainRequest follows below and is the same story.


class StudioGenerationRequest(BaseModel):
    """
    Render the generated piece: one hook and one middle, in one job.

    duration_seconds is the whole piece. It must fit one pass on the chosen
    model; a longer request is refused rather than split or shortened, because
    the founder's own demo and call to action are what make a longer video now.

    model: optional provider key. When omitted the configured default is
        used. An unknown key is refused with a 400 rather than quietly rendered
        on the default, which would bill a model the founder did not choose. A
        known but unusable key (an editor, or one outside the allowlist) still
        falls back with a stated reason, because that is a configuration
        outcome the studio already reports, not a typo.
    duration_seconds: the length of the whole generated piece. A value beyond
        the provider's single-pass limit is REFUSED with a 400 naming the
        ceiling — it is not shortened, and not split into a second job. A
        shorter-than-one-pass video is not a thing this workflow can finish.
    generate_audio: request native audio where the provider supports it.
    idempotency_key: optional caller-supplied key identifying ONE intent to
        render. A repeat of the same key returns the generation already created
        for it instead of submitting a second job. The studio sends a key
        that survives a retried request but is fresh for "Generate another", so
        a double-tap or a network retry cannot run it twice while a deliberate
        re-roll still can. Omitted by any other caller, which is the same
        one-key-one-render behaviour as before.
    resolution: optional render resolution. Only models that list
        supported_resolutions accept one (heygen-video-1: 480p for testing,
        768p default); anything else is refused with a 400 naming the
        allowed values. Omitted means the model's catalog default.
    """
    model: Optional[str] = None
    duration_seconds: Optional[int] = None
    generate_audio: Optional[bool] = None
    idempotency_key: Optional[str] = None
    resolution: Optional[str] = None


class UpdateAssetRequest(BaseModel):
    """Edit asset metadata. The file itself is immutable once uploaded."""
    kind: Optional[str] = None
    name: Optional[str] = None
    label: Optional[str] = None
    notes: Optional[str] = None
    rights_confirmed: Optional[bool] = None
    status: Optional[str] = None


class AttachAssetRequest(BaseModel):
    """Attach an existing library asset to a studio project, with timing."""
    asset_id: str
    start: Optional[float] = None
    end: Optional[float] = None
    position: Optional[str] = None
    scale: Optional[float] = None
    audio_role: Optional[str] = None
    audio_gain: Optional[float] = None


class TikTokLinkRequest(BaseModel):
    """Mark a render as posted by attaching its live TikTok URL.

    Empty string clears the link. A set link is the posted half of a real
    winner; the other half is a thumbs up on the render itself.
    """
    tiktok_url: str = ""


class TikTokViewsRequest(BaseModel):
    """Views pasted back from the posted TikTok, read by hand.

    Manual until any TikTok API: the founder reads the count off the live
    video and pastes it here. None clears it. Out-of-range values are
    refused at the endpoint, not coerced, so a typo never becomes data.
    """
    tiktok_views: Optional[StrictInt] = None


class FeedbackRequest(BaseModel):
    """
    Structured feedback captured at the moment something happened.

    Exactly one of `signal` (an automatic, factual trigger) or `reason` (an
    explicit judgment) is required, and both may be supplied together.

    A reason must be one of the codes permitted for the event. A signal must
    be a known trigger and must belong to the same event. Neither is ever
    inferred from the other, because a guessed reason would corrupt the
    "common regeneration reasons" aggregate.
    """
    event: str
    signal: Optional[str] = ""
    reason: Optional[str] = ""
    detail: Optional[str] = ""
    step: Optional[str] = ""
    brand_profile_id: Optional[str] = ""
    studio_project_id: Optional[str] = ""
    generation_id: Optional[str] = ""
    template_id: Optional[str] = ""


class DemoCtaUploadCompleteRequest(BaseModel):
    """Finish a chunked Demo + CTA save: join the staged parts."

    The browser slices files past 8 MB so no single request trips the
    host's 32 MB ceiling. `total` must match the count every part
    declared, or the join is refused rather than guessed.
    """
    generation_id: Optional[str] = None
    filename: str = "demo-cta.mp4"
    total: int
