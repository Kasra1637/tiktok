"""
AI service layer using OpenRouter API.
- Vision-based hook analysis via chat/completions
- Face-swap image generation via the dedicated /images API
- Video prompt generation via chat/completions
- Video generation via /videos endpoint
"""
import asyncio
import base64
import json
import logging
import mimetypes
import os
import re
from pathlib import Path
from typing import Optional

import httpx

from face_crop import crop_face_from_path
# For the one camera constant the strategy prompt has to state: the second the
# hook-boundary move lands on. Read from the camera module rather than restated
# here, because this prompt and the finalize pass have to be given the identical
# number or the lean and the reframe become two separate events.
from overlays import camera_beat_seconds
from template_library import (
    CONTENT_ANGLE_KINDS,
    HOOK_CATEGORIES,
    SUPPORTED_DURATIONS,
    DEFAULT_DURATION,
    MAX_HOOK_SECONDS,
    MIN_HOOK_SECONDS,
    TEMPLATE_NAME_MAX,
    normalize_angle_kind,
    normalize_category,
    normalize_objective,
    OBJECTIVE_OUTCOMES,
    clamp_duration,
)
import feedback
from claim_safety import FIRST_PERSON_PATTERNS, find_banned_violations, find_risk_patterns

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

logger = logging.getLogger(__name__)

# Models
#
# Both chat models default to Claude Haiku 5.5: Anthropic's small, fast,
# cost-sensitive tier, multimodal (text+image in) with structured-output
# support. It replaces GPT-5 Mini, which it beats on every axis this service
# cares about — cheaper ($0.10/$0.50 vs $0.25/$2.00 per 1M), a larger context
# (1M vs 400K) and a much higher intelligence index (~43 vs ~17).
#
# Both slugs are overridable from the environment so a model swap is a config
# change rather than a code change, the same way the video provider already
# works (see video_providers.default_model_key). An override is taken as given:
# the request shape is guarded by _temperature_param below, not by validating
# the slug here.
#
# Consequences that travel with the shipped default everywhere below:
# - temperature is NOT sent to it. Claude accepts temperature on Anthropic's
#   own API, but this model runs adaptive thinking by default and whether a
#   non-default temperature is accepted alongside that is UNVERIFIED, so it
#   stays behind the guard in _temperature_param until a live call proves it.
# - max_tokens is accepted via OpenRouter (it maps to the provider field), and
#   thinking tokens are billed against the same budget, so small budgets can
#   return empty content with finish_reason=length — which _chat_json already
#   treats as truncation and retries with a doubled budget.
# - structured outputs (strict json_schema) are supported on Anthropic (Haiku
#   4.5 and 5.5) and are compatible with thinking; the local parse-and-retry in
#   _chat_json stays as defense-in-depth for endpoints that treat the schema as
#   a hint rather than a guarantee.
DEFAULT_TEXT_MODEL = "anthropic/claude-haiku-5.5"
DEFAULT_VISION_MODEL = "anthropic/claude-haiku-5.5"


def _model_from_env(var: str, default: str) -> str:
    """Model slug from the environment, falling back to the shipped default."""
    return (os.environ.get(var) or "").strip() or default


TEXT_MODEL = _model_from_env("AI_TEXT_MODEL", DEFAULT_TEXT_MODEL)
VISION_MODEL = _model_from_env("AI_VISION_MODEL", DEFAULT_VISION_MODEL)
# Image generation model for opening scene stills. Uses a dedicated image model
# rather than a video model, since the opening frame is a single still image.

# Video generation models.
# The template studio's providers. MiniMax H3 is the default: 2K picture,
# native audio, V2V motion transfer, up to 15s per pass. Hailuo 3 Max sits
# alongside it for comparison and gives up 2K for prompt adherence; see its
# entry below. A video is ONE render either way, so a request longer than
# the model's single-pass ceiling is refused rather than truncated.
VIDEO_MODELS = {
    "minimax-h3": {
        "id": "minimax/hailuo-3",
        "name": "MiniMax H3",
        "description": "Omni-modal video generation. Native audio, V2V motion transfer, 2K resolution, up to 15s.",
        "max_duration": 15,
        "min_duration": 5,  # Confirmed via API: "Supported durations: 5, 6, 7, 8, 9, ..."
        "supports_references": True,
        "supports_native_audio": True,
        "supports_v2v_motion": True,
        "resolution": "2K",
        "supports_combined_refs": False,  # Cannot combine frame_images with input_references
    },
    # Hailuo 3 Max: H3 post-trained by fal.ai for speed and prompt adherence,
    # served on the same OpenRouter key and the same /videos endpoint. Kept
    # alongside H3 rather than replacing it so the two can be compared on the
    # same script; H3 stays the default (DEFAULT_VIDEO_MODEL below).
    #
    # The one field that must NOT be copied from the H3 entry is resolution.
    # OpenRouter lists H3 Max as "768p" | "480p" only and rejects an unlisted
    # value, so a verbatim copy would 400 on every render. 2K is the one thing
    # this model gives up; 768x1366 is still above TikTok's 720x1280 floor, but
    # it is a visible downgrade once the founder attaches their demo and
    # re-exports at 1080x1920.
    #
    # supports_native_audio is False because OpenRouter does NOT list
    # generate_audio among H3 Max's accepted fields, and an unlisted field is a
    # 400. False makes the studio omit the field entirely and let the provider
    # apply its own default. If a real clip comes back silent, that is the flag
    # to flip.
    "minimax-h3-max": {
        "id": "minimax/hailuo-3-max",
        "name": "MiniMax H3 Max",
        "description": (
            "Hailuo 3 Max: Hailuo 3 post-trained by fal.ai for speed and prompt "
            "adherence. Up to 15s, 768p (not 2K). Opt-in: the studio defaults to "
            "Hailuo 3."
        ),
        "max_duration": 15,
        "min_duration": 5,
        # "References" here means image conditioning in general, not the
        # input_references field specifically: the serving provider refuses
        # input_references outright (proven live with a 400), so the studio
        # carries the founder's photo as the opening frame instead (see
        # video_providers.identity_via_first_frame). Flipping this to False
        # would read as "Max cannot do identity at all", which is wrong.
        "supports_references": True,
        "supports_native_audio": False,  # generate_audio unlisted for this model
        "supports_v2v_motion": False,  # not documented for H3 Max on OpenRouter
        "resolution": "768p",
        "supports_combined_refs": False,
    },
# HeyGen Video: general-purpose short-form business video (brand moments,
    # product demos) with synthesized audio in a single call — dialogue,
    # ambience and effects — from a prompt and the founder's photo as an
    # identity reference. The first catalog entry besides Hailuo 3 with real
    # audio.
    #
    # Facts below come from OpenRouter's own video model endpoint
    # (GET /api/v1/videos/models), verified live at entry time:
    #   supported_resolutions  480p, 768p, 2K  -> 768p. Deliberately not 2K:
    #     the live price SKUs charge 2K at 3x 768p ($0.09/s vs $0.03/s) for
    #     detail no render has proven real, and 480p sits below TikTok's
    #     720x1280 floor. 768p is the cheapest credible tier; revisit 2K only
    #     on render evidence.
    #   supported_durations  5-15  -> min 5 / max 15, exactly the studio's
    #     floor and ceiling, so no new trim edge cases.
    #   supported_frame_images  first_frame  -> listed, and deliberately NOT
    #     sent. A first frame pins the opening to the uploaded photograph: the
    #     render began on that photo's own room, light and framing, and only
    #     reached the planned scene once it had morphed away from it. Identity
    #     rides as an input_references image instead (video_providers:
    #     max_reference_images=1 with no identity_via_first_frame), so every
    #     frame of the clip comes from the plan.
    #   generate_audio  false (accepted, defaults off), NOT null  -> the field
    #     is sendable, and the studio defaults to requesting audio whenever
    #     the provider offers it (server.py). If real clips come back silent
    #     or the field is ever refused, flip supports_native_audio to False.
    #
    # supports_references is True because the founder's photo does ride as an
    # input_references image for this model. The field is listed but not yet
    # proven live — H3 Max taught that a listed field can still 400 — so the
    # first render on this model is what settles it. If it is refused, the
    # submit fails with the provider's words in the log rather than silently
    # falling back to pinning the opening on the photograph.
    #
    # Opt-in, default stays Hailuo 3: audio + 768p at a third of the listed
    # 2K price is a default-challenger on paper, but likeness is unproven
    # until the first renders. Promote only on evidence.
    "heygen-video-1": {
        "id": "heygen/heygen-video-1",
        "name": "HeyGen Video",
        "description": (
            "Business-video renderer with synthesized audio in one call — "
            "dialogue, ambience and effects. The cropped founder photo rides "
            "as an identity reference, so the whole clip is generated from "
            "the plan. 768p, 5-15s. For talking-head hooks and demos. Opt-in."
        ),
        "max_duration": 15,
        "min_duration": 5,
        "supports_references": True,
        "supports_native_audio": True,  # listed as accepted; studio requests it by default
        "supports_v2v_motion": False,
        "resolution": "768p",
        # 480p is offered as an explicit test choice (kept out of the default:
        # below TikTok's 720x1280 floor, so the finalize upscale carries it and
        # the picture is softer). 2K stays unlisted: ~3x the 768p price.
        "supported_resolutions": ["480p", "768p"],
        "supports_combined_refs": False,
    },
}
# Default for new template-studio generations. The provider remains
# configurable through VIDEO_MODEL_DEFAULT and VIDEO_MODEL_ALLOWLIST, but
# MiniMax H3 stays the default: it is the only model here that renders 2K with
# native audio. Anything else configured resolves back to it with a reason.
DEFAULT_VIDEO_MODEL = "minimax-h3"
# Legacy fallback
VIDEO_MODEL = VIDEO_MODELS[DEFAULT_VIDEO_MODEL]["id"]

REQUIRED_ANALYSIS_KEYS = {
    "facial_expressions", "body_language_gestures", "pacing_cuts",
    "text_overlays_timing", "audio_cues_inferred", "hook_summary",
    "effectiveness_score", "key_hook_frame_index", "replicable_mechanics",
}

REQUIRED_VIDEO_PROMPT_KEYS = {
    "content", "camera_angle", "view_position", "character_behavior",
    "scene_details", "brand_narrative", "full_video_prompt", "suggested_duration_seconds",
}

# Full App Profile schema produced by analyze_app_profile(). List fields come
# back as JSON arrays of short strings; icp_segments entries are "Segment
# label — needs / hook promise" one-liners so they stay editable text.
#
# products_or_services, ctas and video_themes were removed. video_themes was
# never read by anything -- the model produced 4-8 themes per profile and no
# generator, scorer or claim rule ever consumed them. The other two reached
# only the legacy remix paths, which no UI route reaches.
REQUIRED_APP_PROFILE_KEYS = {
    "brand_name", "brand_description", "app_category", "niche", "platforms",
    "core_features", "primary_use_cases", "problems_solved",
    "target_audience", "ideal_customer_profile",
    "icp_segments", "desired_outcomes", "outcome_statements",
    "differentiation",
    "known_limitations", "must_not_show", "usage_moments", "proof_moment",
    "viewer_objections", "tone_voice", "claims_approved", "claims_review",
    "claims_banned",
}

# Phrase lists, which are lists of strings. viewer_objections and
# outcome_statements are deliberately NOT here: they are lists of objects, so
# this normalizer would str() each one into an unreadable dict repr and the
# dedicated normalizers below would then discard every entry as malformed —
# which is exactly what happened for as long as viewer_objections was
# included. Each has its own normalizer, called after this loop.
APP_PROFILE_LIST_KEYS = (
    "platforms", "core_features", "primary_use_cases", "problems_solved",
    "icp_segments", "desired_outcomes", "must_not_show",
    "usage_moments", "claims_approved",
    "claims_review", "claims_banned",
)




def _headers():
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://hookforge.app",
        "X-Title": "HookForge",
    }


# The sampling temperature sent to the chat models. 0.4 is low enough that
# structured output stays stable and high enough that the copy does not read as
# templated. Flows that want a different value still pass one explicitly.
CHAT_TEMPERATURE = 0.4

# Whether an endpoint accepts a `temperature` field is a MEASURED fact, not a
# property of the model family, and it moves: every Claude 5.x and GPT-5/6
# endpoint declares no temperature, while Gemini, Qwen, GLM and DeepSeek all
# declare it — and older models inside those same families differ again. A
# hand-maintained prefix list cannot be right for all of them, so the decision
# is read from OpenRouter's per-endpoint declaration (supported_parameters) and
# cached. See refresh_temperature_support().
#
# The prefix list below is only the OFFLINE fallback, for when that listing has
# not been fetched: a cold process, a network failure, the test suite. The retry
# in _post_chat covers whatever it gets wrong, so a bad fallback costs one round
# trip and never a call.
_TEMPERATURE_OMITTED_PREFIXES = ("gpt-5", "gpt-6", "claude", "o1", "o3", "o4")

# {normalized slug: True when EVERY declared endpoint accepts a temperature}.
# Empty until refresh_temperature_support() runs.
_TEMPERATURE_SUPPORT: dict = {}


def _is_family(model: str, prefixes: tuple) -> bool:
    """Whether a model slug belongs to one of the given families."""
    name = (model or "").strip().lower().split("/")[-1]
    return name.startswith(prefixes)


def _normalize_slug(model: str) -> str:
    return (model or "").strip().lower()


def temperature_support(model: str):
    """
    What the provider declares for this model: True, False, or None (unknown).

    None means the listing has not been read — NOT that the model refuses the
    field. Callers must treat it as "use the fallback", never as "no".
    """
    return _TEMPERATURE_SUPPORT.get(_normalize_slug(model))


async def refresh_temperature_support(models) -> dict:
    """
    Read each model's declared parameters from OpenRouter and cache the answer.

    Best-effort and never raises: a failure leaves the cache empty, which sends
    _temperature_param to the offline prefix list rather than taking the boot
    path down. Unauthenticated and free, like the video capability check.

    A model counts as accepting temperature only when EVERY endpoint it is
    served from declares the field. OpenRouter routes a request to one of them,
    so a partial listing would be a coin flip; the conservative reading is the
    one that cannot 400.
    """
    for slug in sorted({_normalize_slug(m) for m in models if m}):
        if "/" not in slug:
            continue
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{OPENROUTER_BASE}/models/{slug}/endpoints")
            if resp.status_code != 200:
                logger.warning(
                    "Temperature lookup for %s: HTTP %s; keeping the fallback.",
                    slug, resp.status_code,
                )
                continue
            endpoints = (resp.json().get("data") or {}).get("endpoints") or []
            if not endpoints:
                logger.warning(
                    "Temperature lookup for %s: no endpoints listed; keeping the fallback.",
                    slug,
                )
                continue
            declared = all(
                "temperature" in (e.get("supported_parameters") or [])
                for e in endpoints
            )
            _TEMPERATURE_SUPPORT[slug] = declared
            logger.info(
                "Temperature for %s: %s (%d endpoint(s)).",
                slug, "declared" if declared else "not declared", len(endpoints),
            )
        except Exception as e:
            logger.warning("Temperature lookup for %s failed: %s", slug, e)
    return dict(_TEMPERATURE_SUPPORT)


def _temperature_param(model: str, temperature: float) -> dict:
    """
    {"temperature": t} for endpoints that accept it, else {} (never raises).

    Precedence is the declared data over the offline fallback, so pointing the
    service at a model that takes a temperature needs no code change, and
    pointing it at one that does not needs no discovery-by-400.
    """
    declared = temperature_support(model)
    if declared is not None:
        return {"temperature": temperature} if declared else {}
    if _is_family(model, _TEMPERATURE_OMITTED_PREFIXES):
        return {}
    return {"temperature": temperature}


def _temperature_refused(resp) -> bool:
    """
    Whether a 4xx response is specifically about the temperature field.

    Read from the body rather than assumed from the status code: a 400 can be
    many things, and only a refusal that NAMES temperature is safe to retry
    without it. A 5xx or a transport error is not this.
    """
    if not (400 <= getattr(resp, "status_code", 0) < 500):
        return False
    try:
        body = json.dumps(resp.json())
    except Exception:
        body = getattr(resp, "text", "") or ""
    return "temperature" in body.lower()


async def _post_chat(client, payload: dict):
    """
    POST one chat completion, dropping the temperature field once if the
    provider refuses it.

    Sending a temperature is a preference; getting the answer back is the job.
    The declared capability data decides whether the field is sent at all (see
    refresh_temperature_support); this is the net under BOTH that data and the
    offline fallback, because OpenRouter has listed a parameter a provider then
    refused. A refusal that names the field costs the field and not the call:
    the identical request is retried without it exactly once. Any other failure
    is left to the caller's raise_for_status.
    """
    resp = await client.post(
        f"{OPENROUTER_BASE}/chat/completions", headers=_headers(), json=payload
    )
    if "temperature" in payload and _temperature_refused(resp):
        logger.warning(
            "%s refused temperature=%s; retrying the same request without it.",
            payload.get("model"), payload.get("temperature"),
        )
        retry = {k: v for k, v in payload.items() if k != "temperature"}
        resp = await client.post(
            f"{OPENROUTER_BASE}/chat/completions", headers=_headers(), json=retry
        )
    return resp


def _response_format(name: str, schema: dict, strict: bool = True) -> dict:
    """
    OpenRouter structured-outputs envelope for one JSON Schema.

    Strict mode makes the provider conform to the schema instead of the model
    improvising shape; the local parse-and-retry stays because providers can
    still error, refuse, or truncate. Non-strict is the fallback for shapes
    strict mode cannot express (free-form maps like content_slots).
    """
    slug = "".join(
        c.lower() if c.isalnum() else "_" for c in str(name or "response")
    ).strip("_") or "response"
    while "__" in slug:
        slug = slug.replace("__", "_")
    return {
        "type": "json_schema",
        "json_schema": {"name": slug[:64], "strict": strict, "schema": schema},
    }


# ---------------------------------------------------------------------------
# Structured-output schemas (OpenRouter response_format, strict JSON Schema).
#
# These mirror the prompt-embedded schemas and the REQUIRED_* key sets field
# for field: the provider enforces the shape, while the prompts keep asking
# for it in words (cheap, and the only thing working when a provider ignores
# response_format) and the normalizers keep coercing whatever arrives.
# Descriptions are omitted on purpose — every word here is billed as input
# tokens on every call, and the prompts already carry the guidance.
# ---------------------------------------------------------------------------

def _str_prop() -> dict:
    return {"type": "string"}


def _str_array_prop() -> dict:
    return {"type": "array", "items": {"type": "string"}}


def _strict_object(properties: dict) -> dict:
    """One strict object: every property required, nothing else admitted."""
    return {
        "type": "object",
        "properties": properties,
        "required": sorted(properties),
        "additionalProperties": False,
    }


APP_PROFILE_JSON_SCHEMA = _strict_object({
    "brand_name": _str_prop(),
    "brand_description": _str_prop(),
    "app_category": _str_prop(),
    "niche": _str_prop(),
    "platforms": _str_array_prop(),
    "core_features": _str_array_prop(),
    "primary_use_cases": _str_array_prop(),
    "problems_solved": _str_array_prop(),
    "target_audience": _str_prop(),
    "ideal_customer_profile": _str_prop(),
    "icp_segments": _str_array_prop(),
    "desired_outcomes": _str_array_prop(),
    "outcome_statements": {
        "type": "array",
        "items": _strict_object({
            "outcome": _str_prop(),
            "who_feels_it": _str_prop(),
            "from_feature": _str_prop(),
            "how_it_helps": _str_prop(),
        }),
    },
    "differentiation": _str_prop(),
    "known_limitations": _str_prop(),
    "must_not_show": _str_array_prop(),
    "usage_moments": _str_array_prop(),
    "proof_moment": _str_prop(),
    "viewer_objections": {
        "type": "array",
        "items": _strict_object({
            "objection": _str_prop(),
            "what_they_do_now": _str_prop(),
            "honest_answer": _str_prop(),
        }),
    },
    "tone_voice": _str_prop(),
    "claims_approved": _str_array_prop(),
    "claims_review": _str_array_prop(),
    "claims_banned": _str_array_prop(),
})
# Mirrors REQUIRED_APP_PROFILE_KEYS above. Deliberately no overlays/cta keys:
# anything the normalizers drop, the schema must not invite.


ANGLE_JSON_SCHEMA = _strict_object({
    "kind": _str_prop(),
    "label": _str_prop(),
    "target_audience": _str_prop(),
    "user_problem": _str_prop(),
    "hook_promise": _str_prop(),
    "app_feature": _str_prop(),
    "desired_emotion": _str_prop(),
    "claims_to_respect": _str_array_prop(),
})

ANGLES_JSON_SCHEMA = _strict_object({"angles": {"type": "array", "items": ANGLE_JSON_SCHEMA}})
# Object wrapper, not a bare array: strict mode requires an object at the
# root. The list-or-dict parse below stays — a provider that ignores
# response_format can still answer either way.


PLAN_BEAT_JSON_SCHEMA = _strict_object({
    "start": {"type": "number"},
    "end": {"type": "number"},
    "label": _str_prop(),
    "text": _str_prop(),
})

PLAN_JSON_SCHEMA = _strict_object({
    "hook_line": _str_prop(),
    "script": _str_prop(),
    "beat_timeline": {"type": "array", "items": PLAN_BEAT_JSON_SCHEMA},
    "visual_direction": _str_prop(),
    "demo_brief": _str_prop(),
    "voice_direction": _str_prop(),
    "sound_direction": _str_prop(),
    "claims_used": _str_array_prop(),
})
# Mirrors REQUIRED_PLAN_KEYS. No overlays key: the normalizer pops anything
# volunteered, so the schema must not ask for it.


STRATEGY_SEGMENT_JSON_SCHEMA = _strict_object({
    "index": {"type": "integer"},
    "role": _str_prop(),
    "seconds": {"type": "integer"},
    "goal": _str_prop(),
    "script": _str_prop(),
    "action": _str_prop(),
})

# The beat the hook-boundary camera move lands on.
#
# `at` is NOT the model's to choose: the finalize pass reframes on an exact
# second and the render prompt is told the same one, so the lean the model
# performs and the reframe ffmpeg applies are a single event rather than two
# that happen to be nearby. It is stamped by the strategy endpoint from
# hook_seconds and read back by both. Only `gesture` is the model's, and it is
# what makes the lean specific to this video instead of a generic push.
STRATEGY_CAMERA_BEAT_JSON_SCHEMA = _strict_object({
    "at": {"type": "number"},
    "gesture": _str_prop(),
})

STRATEGY_JSON_SCHEMA = _strict_object({
    "strategy_summary": _str_prop(),
    "audience_problem": _str_prop(),
    "hook_concept": _str_prop(),
    "hook_line": _str_prop(),
    "hook_promise": _str_prop(),
    "hook_action": _str_prop(),
    "hook_dialogue": _str_prop(),
    "primary_feature": _str_prop(),
    "desired_outcome": _str_prop(),
    "mechanism_beat": _str_prop(),
    "payoff_beat": _str_prop(),
    "differentiation_beat": _str_prop(),
    "emotional_triggers": _str_array_prop(),
    "messaging_pillars": _str_array_prop(),
    "scene": _strict_object({
        "camera_angle": _str_prop(),
        "framing": _str_prop(),
        "lighting": _str_prop(),
        "environment": _str_prop(),
        "background": _str_prop(),
        "setting": _str_prop(),
        "visual_style": _str_prop(),
        "character_positioning": _str_prop(),
        "wardrobe": _str_prop(),
        "props": _str_prop(),
        "color_palette": _str_prop(),
    }),
    "performance": _strict_object({
        "movement": _str_prop(),
        "voice_delivery": _str_prop(),
    }),
    "segments": {"type": "array", "items": STRATEGY_SEGMENT_JSON_SCHEMA},
    "camera_beat": STRATEGY_CAMERA_BEAT_JSON_SCHEMA,
})
# Mirrors normalize_strategy: every key it keeps is listed, retired keys
# (character, cta_strategy) are absent so the model cannot emit them.


TEMPLATE_JSON_SCHEMA = {
    # NOT strict: content_slots is a free-form string map, which strict mode
    # cannot express (arbitrary keys). Best-effort shape guidance instead;
    # normalize_brand_template still drops anything unusable.
    "type": "object",
    "properties": {
        "name": _str_prop(),
        "category": _str_prop(),
        "objective": _str_prop(),
        "opening_structure": _str_prop(),
        "hook_seconds": {"type": "integer"},
        "middle_structure": _str_prop(),
        "visual_style": _str_prop(),
        "camera_pacing": _str_prop(),
        "content_slots": {"type": "object"},
        "default_duration": {"type": "integer"},
        "outcome": _str_prop(),
    },
    "required": [
        "name", "category", "objective", "opening_structure", "hook_seconds",
        "middle_structure", "visual_style", "camera_pacing", "content_slots",
        "default_duration", "outcome",
    ],
    "additionalProperties": False,
}

TEMPLATES_JSON_SCHEMA = {
    # Same non-strict wrapper for the same reason; the list-or-dict parse
    # below stays for providers that ignore response_format.
    "type": "object",
    "properties": {
        "templates": {"type": "array", "items": TEMPLATE_JSON_SCHEMA},
    },
    "required": ["templates"],
    "additionalProperties": False,
}


def video_content_url(job_id: str) -> str:
    """
    The stable download URL for a finished video job.

    OpenRouter's poll response normally hands back this exact URL in
    `unsigned_urls`, but the field is optional -- a completed job can arrive
    with no list at all. Their cookbook treats the content endpoint as the
    direct path precisely because it is derivable from the job id we already
    hold, so it works as a fallback when the response omits it.
    """
    if not job_id:
        return ""
    return f"{OPENROUTER_BASE}/videos/{job_id}/content?index=0"


def provider_download_headers(url: str) -> dict:
    """
    Auth for downloading a finished clip, and ONLY for our own endpoints.

    `unsigned_urls` is a misleading name: those URLs are NOT presigned. When
    one points back at the OpenRouter API -- which is the normal case, and is
    what the content endpoint returns -- the request must carry the same
    bearer token as the poll itself or OpenRouter answers 401. That is the
    whole reason this function exists: the studio's download was sending
    browser-like headers only, and every completed render came back
    "Unauthorized" at exactly the point where the durable copy was being
    taken.

    Scoped to the OpenRouter origin on purpose. The same field can carry a
    third-party storage URL instead ("https://storage.example.com/video.mp4"
    appears in their own docs), and forwarding our bearer token to an
    arbitrary host would hand the account key to that host. No token, no
    problem: those URLs are genuinely unsigned.
    """
    if not url:
        return {}
    if not url.startswith(f"{OPENROUTER_BASE}/"):
        return {}
    if not OPENROUTER_API_KEY:
        return {}
    return {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}


def image_to_base64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# The formats the upload path accepts (server.ASSET_ALLOWED_EXT["image"]).
# face_crop saves with the source file's own suffix, so a cropped face derived
# from a .jpg upload is still a JPEG.
_IMAGE_MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def image_mime_type(path: Path) -> str:
    """The MIME type that actually matches the file's bytes.

    Every reference used to be labelled `image/png` regardless of what it was,
    so a .jpg phone photo went out as `data:image/png;base64,<JPEG bytes>`. A
    mislabelled data URI is invalid, which image_testing.md calls out by name.
    The tests never caught it because every fixture is a .png.
    """
    suffix = Path(path).suffix.lower()
    if suffix in _IMAGE_MIME_BY_SUFFIX:
        return _IMAGE_MIME_BY_SUFFIX[suffix]
    guessed, _encoding = mimetypes.guess_type(str(path))
    return guessed or "image/png"


def image_data_uri(path: Path) -> str:
    """A base64 data URI whose declared MIME matches the encoded bytes."""
    return f"data:{image_mime_type(path)};base64,{image_to_base64(path)}"


def _clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return text.strip()


def _extract_balanced_object(text: str) -> Optional[str]:
    """
    Scan text for the first balanced {...} object, correctly handling nested
    braces and braces inside string literals. More robust than find('{')/rfind('}')
    which breaks when the model adds trailing prose or the JSON contains nested
    objects/arrays with braces of their own.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _parse_json_response(full_text: str, context: str) -> dict:
    """
    Robustly parse a JSON object out of an LLM response. Tries, in order:
    1. Direct json.loads on the cleaned text
    2. A balanced-brace scan to isolate the JSON object even if the model
       added leading/trailing commentary or the object contains nested braces
    On total failure, logs the raw text (truncated) so the actual model output
    is visible in server logs instead of a bare "invalid JSON" error.
    """
    cleaned = _clean_json_text(full_text)
    try:
        return json.loads(cleaned, strict=False)
    except json.JSONDecodeError:
        pass

    candidate = _extract_balanced_object(cleaned)
    if candidate:
        try:
            # strict=False permits literal newlines/tabs inside strings — the
            # most common model formatting slip, and semantically neutral
            # (unlike trailing commas or quote repairs, which guess at
            # meaning). A truly truncated object still fails here.
            return json.loads(candidate, strict=False)
        except json.JSONDecodeError:
            pass

    logger.error(
        f"{context}: model did not return valid JSON. Raw response (first 1500 chars): "
        f"{full_text[:1500]!r}"
    )
    raise RuntimeError(f"{context} did not return valid JSON")


class ModelRefusal(RuntimeError):
    """
    The model answered in prose instead of JSON — typically a safety refusal
    ("I can't help with...") rather than a formatting slip.

    Worth its own exception: without it a refusal surfaces as "did not return
    valid JSON", which sends everyone hunting for a parser or budget problem
    while the real cause is the model declining the prompt. Retrying the
    identical prompt sometimes works (temperature), but a repeated refusal
    means the prompt's topic trips the provider's filter, and the fix is the
    wording, not the plumbing.
    """


class TruncatedResponse(RuntimeError):
    """
    The model stopped because it hit max_tokens, not because it finished.

    Worth its own exception: truncated JSON fails the parser in exactly the
    same way as a model that wrapped its answer in prose, so without this the
    only clue is "did not return valid JSON" and the real cause — a too-small
    token budget — goes unquestioned. A thinking model spends thought tokens
    from the same completion budget, so a large JSON schema can exhaust
    max_tokens before the closing brace is ever written; the headroom this
    retry adds covers that failure mode whatever model serves the call.
    """


def _is_refusal_finish_reason(finish_reason) -> bool:
    """
    Whether the provider stopped the reply on safety grounds rather than
    length or completion. Matched loosely because providers name it
    differently (content_filter, SAFETY, blocked) — this only ever compares
    the finish_reason enum, never message text, so loose matching cannot
    misfire on ordinary prose.
    """
    text = str(finish_reason or "").lower()
    return any(marker in text for marker in ("filter", "safety", "blocked", "refus"))


async def _chat_json(
    system_message: str,
    prompt: str,
    context: str,
    temperature: float = CHAT_TEMPERATURE,
    max_tokens: int = 3000,
    attempts: int = 2,
    timeout: int = 120,
    json_schema: Optional[dict] = None,
    strict: bool = True,
) -> dict:
    """
    One chat completion that must come back as a JSON object.

    Handles the two ways that actually goes wrong, which a bare json.loads does
    not:

    - Truncation (finish_reason == "length") is detected and retried with a
      larger budget AND a request for shorter values, because repeating the
      same request at the same size will be truncated identically.
    - A formatting slip (prose around the JSON, a fence, a stray comma) is
      retried once with an explicit JSON-only reminder, which fixes it far
      more often than it recurs.

    Only after the retries are exhausted does it raise.

    `temperature` is sent to models that take it (GPT-5 Mini does not; Claude
    Haiku 5.5 does), and a provider that refuses the field costs the field
    rather than the call — see _post_chat; `json_schema`, when given, is sent as
    OpenRouter structured output (strict JSON Schema) while the parse-and-retry
    below stays as defense-in-depth for provider errors, refusals and truncation.
    """
    last_error = None

    for attempt in range(1, attempts + 1):
        # A retry gets a bigger budget and a nudge to be more economical.
        budget = max_tokens if attempt == 1 else max_tokens * 2
        attempt_prompt = prompt
        if attempt > 1:
            attempt_prompt = (
                prompt
                + "\n\nIMPORTANT: Your previous reply was cut off or was not parseable. "
                "Reply with ONE complete JSON object and nothing else - no prose, no "
                "markdown fence, no trailing commentary. Keep every string value to "
                "under 25 words so the whole object fits."
            )

        payload = {
            "model": TEXT_MODEL,
            "messages": [
                {"role": "system", "content": system_message},
                {"role": "user", "content": attempt_prompt},
            ],
            **_temperature_param(TEXT_MODEL, temperature),
            "max_tokens": budget,
        }
        if json_schema is not None:
            payload["response_format"] = _response_format(context, json_schema, strict)

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await _post_chat(client, payload)
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices") or []
        if not choices:
            logger.error(
                f"{context}: no choices in response: {json.dumps(data)[:1000]}"
            )
            raise RuntimeError(f"{context}: model returned no response")

        choice = choices[0]
        finish_reason = choice.get("finish_reason")
        full_text = choice.get("message", {}).get("content", "") or ""

        if not full_text:
            logger.error(
                f"{context}: empty content, finish_reason={finish_reason}, "
                f"budget={budget}, response: {json.dumps(data)[:1000]}"
            )
            last_error = TruncatedResponse(
                f"{context}: model returned no content (finish_reason={finish_reason})"
            )
            continue

        if _is_refusal_finish_reason(finish_reason):
            # The provider filtered the reply. Retrying the identical prompt
            # can occasionally work, but name it either way: without this the
            # failure below reports "did not return valid JSON" and the real
            # cause — the filter, not the format — goes unquestioned.
            logger.error(
                f"{context}: model refused (finish_reason={finish_reason}). "
                f"Raw head: {full_text[:300]!r}"
            )
            last_error = ModelRefusal(
                f"{context} was refused by the model (finish_reason={finish_reason})"
            )
            if attempt < attempts:
                continue
            raise last_error

        if finish_reason == "length":
            # The JSON was cut mid-object, so the parser cannot see it. Say so.
            logger.error(
                f"{context}: response truncated by max_tokens (budget={budget}). "
                f"Raw tail: {full_text[-400:]!r}"
            )
            last_error = TruncatedResponse(
                f"{context} was cut off after {budget} tokens "
                f"(finish_reason=length) before the JSON closed"
            )
            continue

        try:
            return _parse_json_response(full_text, context)
        except RuntimeError as e:
            if "{" not in full_text:
                # Prose with no JSON object at all — typically a refusal or
                # apology the finish_reason did not label. Report it as one:
                # "invalid JSON" would send everyone hunting for a parser or
                # budget problem while the model simply declined the prompt.
                logger.error(
                    f"{context}: reply contained no JSON object. "
                    f"Raw response: {full_text[:500]!r}"
                )
                last_error = ModelRefusal(
                    f"{context} returned no JSON object — the model replied "
                    f"in prose, which usually means it declined the prompt"
                )
            else:
                last_error = e
            if attempt < attempts:
                logger.warning(
                    f"{context}: attempt {attempt} returned unparseable JSON, retrying "
                    f"with a stricter instruction. Raw head: {full_text[:300]!r}"
                )
                continue
            raise last_error

    if last_error:
        raise last_error
    raise RuntimeError(f"{context}: model returned no usable response")


def _decode_image_base64(value: str, context: str) -> bytes:
    """Decode image bytes returned by OpenRouter's dedicated Images API."""
    if not value:
        raise RuntimeError(f"No image returned from {context} model.")
    encoded = value.split(",", 1)[1] if value.startswith("data:") and "," in value else value
    try:
        return base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise RuntimeError(f"{context} returned invalid image data.") from exc


def _extract_image_bytes_from_image_response(data: dict, context: str) -> bytes:
    """Extract the first image from a buffered OpenRouter Images API response."""
    images = data.get("data") or []
    for image in images:
        if isinstance(image, dict) and image.get("b64_json"):
            return _decode_image_base64(image["b64_json"], context)
    logger.error(f"{context}: no image in Images API response: {json.dumps(data)[:1000]}")
    raise RuntimeError(f"No image returned from {context} model.")


async def _call_image_generation_with_retry(
    payload: dict,
    context: str,
    max_retries: int = 2,
    timeout: int = 600,
) -> bytes:
    """
    Generate an image through OpenRouter's dedicated Images API.

    Uses a buffered (non-streaming) request because OpenRouter does not support
    streaming for image-to-image (edit) requests with input_references.
    Retries on transient failures (429, 500, 502, 503).
    """
    last_error = None
    request_timeout = httpx.Timeout(connect=30, read=timeout, write=60, pool=30)

    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=request_timeout) as client:
                resp = await client.post(
                    f"{OPENROUTER_BASE}/images",
                    headers=_headers(),
                    json=payload,
                )
                if resp.status_code >= 400:
                    error_text = resp.text[:500]
                    logger.warning(
                        f"{context}: HTTP {resp.status_code} on attempt "
                        f"{attempt}/{max_retries}: {error_text}"
                    )
                    # Don't retry on 400 client errors (bad request / content filter)
                    if resp.status_code == 400:
                        raise RuntimeError(f"HTTP {resp.status_code}: {error_text}")
                    # Retry on server-side / rate limit errors
                    raise RuntimeError(f"HTTP {resp.status_code}: {error_text}")

                data = resp.json()
                return _extract_image_bytes_from_image_response(data, context)

        except Exception as exc:
            last_error = exc if isinstance(exc, RuntimeError) else RuntimeError(str(exc))
            is_retryable = "429" in str(last_error) or "500" in str(last_error) or "502" in str(last_error) or "503" in str(last_error)
            if attempt < max_retries and is_retryable:
                wait_time = attempt * 3
                logger.warning(
                    f"{context}: attempt {attempt}/{max_retries} failed ({last_error}). "
                    f"Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"{context}: generation failed: {last_error}")
                break

    raise last_error or RuntimeError(f"{context} failed after {max_retries} attempts.")

    raise last_error or RuntimeError(f"{context} failed after {max_retries} attempts.")

    raise last_error or RuntimeError(f"{context} failed after {max_retries} attempts.")




async def analyze_hook(frame_paths: list, session_id: str, music_context: dict = None, transcript_text: str = "") -> dict:
    """
    Analyze hook frames using OpenRouter vision model.
    
    Enhanced with actual music/audio context and transcript when available,
    instead of purely inferring audio from visuals.
    
    Args:
        frame_paths: List of Path objects pointing to extracted video frames
        session_id: Unique session identifier for logging
        music_context: Dict with song metadata (song_title, song_artist, song_album, song_duration)
        transcript_text: Plain text transcript of the video's spoken words (from subtitles)
    """
    # Build audio context string from actual data when available
    audio_context_parts = []
    if music_context:
        song_title = music_context.get("song_title") or ""
        song_artist = music_context.get("song_artist") or ""
        if song_title or song_artist:
            audio_context_parts.append(
                f"The video uses the sound/music: \"{song_title}\" by {song_artist}."
            )
            if music_context.get("song_duration"):
                audio_context_parts.append(f"Sound duration: {music_context['song_duration']}s.")
    if transcript_text:
        # Limit transcript to first ~500 chars (hook is first 3 seconds)
        truncated_transcript = transcript_text[:500]
        audio_context_parts.append(
            f"Transcript/spoken words in the video: \"{truncated_transcript}\""
        )

    audio_context_str = " ".join(audio_context_parts) if audio_context_parts else ""

    system_message = (
        "You are an expert short-form video (TikTok/Reels) hook analyst. You examine the "
        "first 3 seconds of a video (given as a sequence of frames in chronological order) "
        "and identify exactly what makes the hook effective at grabbing attention. "
        "Respond with STRICT JSON only, no markdown fences, no extra commentary."
    )

    # Build prompt with actual audio/music context when available
    audio_instruction = ""
    if audio_context_str:
        audio_instruction = (
            f"\n\nIMPORTANT AUDIO CONTEXT (actual data from the video, not inferred):\n"
            f"{audio_context_str}\n"
            "Use this real audio/music information to inform your analysis of audio_cues_inferred "
            "and how the sound contributes to the hook's effectiveness."
        )

    prompt = (
        "Here are sequential frames from the first ~3 seconds of a short-form video "
        "(frame_001 is earliest). Analyze the hook and return ONLY a JSON object with this "
        "exact schema:\n"
        "{\n"
        '  "facial_expressions": "string describing facial expressions/micro-expressions observed",\n'
        '  "body_language_gestures": "string describing body language and hand gestures",\n'
        '  "pacing_cuts": "string describing pacing and cut speed/escalation across the frames",\n'
        '  "text_overlays_timing": "string describing any on-screen text/elements and when they appear",\n'
        '  "audio_cues_inferred": "string describing the audio/music and how it contributes to the hook",\n'
        '  "hook_summary": "1-2 sentence summary of why this hook works",\n'
        '  "effectiveness_score": integer 1-10,\n'
        '  "key_hook_frame_index": integer index (1-based) of the single frame that best represents the peak hook moment,\n'
        '  "replicable_mechanics": ["short bullet", "..."] list of concrete mechanics to preserve when recreating this hook\n'
        "}\n"
        f"{audio_instruction}\n"
        "Return ONLY valid JSON."
    )

    # Build content array with images
    content = [{"type": "text", "text": prompt}]
    for fp in frame_paths:
        content.append({
            "type": "image_url",
            "image_url": {"url": image_data_uri(fp)}
        })

    payload = {
        "model": VISION_MODEL,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": content},
        ],
        **_temperature_param(VISION_MODEL, 0.3),
        "max_tokens": 3000,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await _post_chat(client, payload)
        resp.raise_for_status()
        data = resp.json()

    choices = data.get("choices") or []
    if not choices:
        logger.error(f"Hook analysis: no choices in response: {json.dumps(data)[:1000]}")
        raise RuntimeError("Hook analysis model returned no response")

    finish_reason = choices[0].get("finish_reason")
    full_text = choices[0].get("message", {}).get("content", "")
    if not full_text:
        logger.error(f"Hook analysis: empty content, finish_reason={finish_reason}, full response: {json.dumps(data)[:1000]}")
        raise RuntimeError(
            f"Hook analysis model returned empty content (finish_reason={finish_reason})"
        )
    if finish_reason == "length":
        logger.warning(f"Hook analysis: response was truncated by max_tokens. Raw text: {full_text[:1500]!r}")

    analysis = _parse_json_response(full_text, "Hook analysis")

    missing = REQUIRED_ANALYSIS_KEYS - set(analysis.keys())
    if missing:
        logger.error(f"Hook analysis missing fields {missing}. Raw text: {full_text[:1500]!r}")
        raise RuntimeError(f"Hook analysis missing required fields: {missing}")

    return analysis






async def generate_video_prompt(analysis: dict, brand_context: dict, target_duration: int, session_id: str, music_context: dict = None, transcript_text: str = "", use_original_sound: bool = False) -> dict:
    """Auto-generate a production-ready video prompt from hook analysis + brand context.
    
    Enhanced with actual music/audio context and transcript when available.

    Args:
        use_original_sound: If True and music_context has a song, instructs the model to
            write the prompt assuming the ORIGINAL sound/music will be reused verbatim
            (e.g. lean on visuals/captions instead of new spoken dialogue that would clash).
    """
    system_message = (
        "You are an expert short-form video creative director who writes precise, production-ready prompts for "
        "AI video generation models. You take the analyzed 'hook' of a viral video and a brand's context, and "
        "produce a full video generation prompt. Respond with STRICT JSON only, no markdown fences."
    )

    # Build audio context from actual data
    audio_context_parts = []
    song_title = ""
    song_artist = ""
    if music_context:
        song_title = music_context.get("song_title") or ""
        song_artist = music_context.get("song_artist") or ""
        if song_title or song_artist:
            audio_context_parts.append(f"Original sound: \"{song_title}\" by {song_artist}")
    if transcript_text:
        audio_context_parts.append(f"Original transcript: \"{transcript_text[:500]}\"")
    audio_context_str = "; ".join(audio_context_parts) if audio_context_parts else "(not available)"

    sound_instruction = ""
    has_sound_to_reuse = use_original_sound and (song_title or song_artist)
    if has_sound_to_reuse:
        sound_instruction = (
            f"\n\nIMPORTANT: The user wants to REUSE the exact original sound/music (\"{song_title}\" by "
            f"{song_artist}) in their remixed video instead of a new voiceover or different track. Write the "
            "video prompt assuming this original audio track will play underneath — favor visual storytelling, "
            "on-screen text captions, and movement/lip-sync timed to the original sound rather than describing "
            "new spoken dialogue that would conflict with it. Do not suggest a different sound."
        )
    elif use_original_sound:
        sound_instruction = (
            "\n\nNote: The user asked to reuse the original sound, but no sound metadata is available for "
            "this video — proceed as normal without an explicit audio plan."
        )

    prompt = (
        "Hook analysis of the original viral video's first 3 seconds:\n"
        f"- Facial expressions: {analysis.get('facial_expressions')}\n"
        f"- Body language & gestures: {analysis.get('body_language_gestures')}\n"
        f"- Pacing & cuts: {analysis.get('pacing_cuts')}\n"
        f"- Text overlays & timing: {analysis.get('text_overlays_timing')}\n"
        f"- Audio cues (inferred): {analysis.get('audio_cues_inferred')}\n"
        f"- Hook summary: {analysis.get('hook_summary')}\n"
        f"- Replicable mechanics: {analysis.get('replicable_mechanics')}\n\n"
        f"Actual audio/music context: {audio_context_str}\n"
        f"{sound_instruction}\n\n"
        "Brand context:\n"
        f"- Brand name: {brand_context.get('brand_name') or '(not provided)'}\n"
        f"- Brand goal: {brand_context.get('brand_goal') or '(not provided)'}\n"
        f"- Brand details: {brand_context.get('brand_details') or '(not provided)'}\n\n"
        f"Target video duration: EXACTLY {target_duration} seconds. This is critical — pace all content, "
        f"transitions, and delivery to fill exactly {target_duration} seconds. A {target_duration}-second "
        f"video {'is very short — every beat must be punchy and immediate, no wasted time' if target_duration <= 7 else 'needs tight pacing with clear beats' if target_duration <= 12 else 'allows for a setup-payoff arc with breathing room' if target_duration <= 20 else 'should have a full narrative arc with intro, development, and strong CTA'}.\n\n"
        "Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "content": "what happens in the video SECOND BY SECOND — explicitly reference timestamps (e.g. 0-2s: hook, 2-5s: reveal, etc.)",\n'
        '  "camera_angle": "camera angles matching the original hook",\n'
        '  "view_position": "framing/view position",\n'
        '  "character_behavior": "how the character behaves/moves",\n'
        '  "scene_details": "environment/background/lighting/props",\n'
        '  "brand_narrative": "how the video ties into the brand",\n'
        '  "audio_recommendation": "the audio/sound approach for this video",\n'
        '  "full_video_prompt": "cohesive production-ready prompt (150-300 words) that EXPLICITLY states the video is ' + str(target_duration) + ' seconds and paces content accordingly",\n'
        '  "suggested_duration_seconds": ' + str(target_duration) + "\n"
        "}\n"
        "IMPORTANT: The full_video_prompt MUST explicitly mention it is a " + str(target_duration) + "-second video and structure content timing to match.\n"
        "Return ONLY valid JSON."
    )

    payload = {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        **_temperature_param(TEXT_MODEL, 0.5),
        "max_tokens": 3000,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await _post_chat(client, payload)
        resp.raise_for_status()
        data = resp.json()

    full_text = data["choices"][0]["message"]["content"]
    result = _parse_json_response(full_text, "Video prompt generation")

    missing = REQUIRED_VIDEO_PROMPT_KEYS - set(result.keys())
    if missing:
        logger.error(f"Video prompt generation missing fields {missing}. Raw text: {full_text[:1500]!r}")
        raise RuntimeError(f"Video prompt generation missing required fields: {missing}")

    # Deterministic safety net: guarantee the audio plan reflects the user's choice
    # regardless of what the model produced, so the UI can trust this field.
    if has_sound_to_reuse:
        result["audio_recommendation"] = f'Keep the original sound: "{song_title}" by {song_artist}'

    return result


async def analyze_image_for_hook(image_path: Path, session_id: str) -> dict:
    """
    Analyze a single image (uploaded target or face-swapped result) to extract
    hook-relevant movement and expression cues for video generation.

    Unlike analyze_hook() which works on multiple video frames, this works on a
    SINGLE still image — inferring what movement/expression is captured and what
    natural continuation would make an effective hook video.

    Returns a dict with the same keys as a hook analysis so it can be used
    interchangeably by the video generation prompt.
    """
    system_message = (
        "You are an expert short-form video (TikTok/Reels) hook strategist. You examine a single "
        "still image of a person and determine what attention-grabbing movement is happening or "
        "about to happen — then describe how to animate this into a 3-second silent hook video. "
        "Respond with STRICT JSON only, no markdown fences, no extra commentary."
    )

    prompt = (
        "Here is a still image that will be the first frame of a 3-second TikTok hook video. "
        "Analyze what's in this image and describe how to animate it into an attention-grabbing "
        "silent hook. Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "facial_expressions": "describe the expression visible and how it should evolve over 3 seconds",\n'
        '  "body_language_gestures": "describe the pose/gesture visible and what movement should follow",\n'
        '  "pacing_cuts": "describe the ideal pacing and camera movement for a 3s hook starting from this frame",\n'
        '  "hook_summary": "1-2 sentence description of the hook concept that would work from this image",\n'
        '  "replicable_mechanics": ["list", "of", "specific", "movements", "to", "animate"]\n'
        "}\n"
        "Focus on: what movement from THIS starting pose would create maximum curiosity in 2-3 seconds? "
        "Think about what the viewer would want to see happen next. The video will be SILENT (no voice, "
        "no text) so all attention must come from physical movement and expression change.\n"
        "Return ONLY valid JSON."
    )

    content = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_data_uri(image_path)}},
    ]

    payload = {
        "model": VISION_MODEL,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": content},
        ],
        **_temperature_param(VISION_MODEL, 0.4),
        "max_tokens": 1500,
    }

    async with httpx.AsyncClient(timeout=45) as client:
        resp = await _post_chat(client, payload)
        resp.raise_for_status()
        data = resp.json()

    choices = data.get("choices") or []
    if not choices:
        logger.warning(f"Image hook analysis: no choices returned")
        return {}

    full_text = choices[0].get("message", {}).get("content", "")
    if not full_text:
        return {}

    try:
        result = _parse_json_response(full_text, "Image hook analysis")
        return result
    except Exception as e:
        logger.warning(f"Image hook analysis failed to parse: {e}")
        return {}




# Provider error signatures that mean "this input will never be accepted".
# Kept in sync with the permanent markers in
# generation_planning.is_recoverable_error: anything listed here must also
# read as permanent there, or a refusal becomes a retry that burns money and
# always fails the same way.
_PROVIDER_REFUSAL_MARKERS = (
    "sensitive",
    "privacy",
    "contentdetect",
    "content_detect",
    "contentfilter",
    "content_filter",
    "policy_violation",
    "policyviolation",
    "inputimage",
    "input_image",
)

def _extract_provider_message(error_text: str, limit: int = 500) -> str:
    """Short founder-readable excerpt of a raw provider error body.

    The body is usually nested JSON ({"error": {"code": ..., "message": ...}}).
    Raw JSON names fields the founder cannot set, so prefer the innermost
    message/code and fall back to whitespace-collapsed text. Never raises:
    an unparseable body still returns something useful rather than a second
    exception on the submit path.
    """
    if not error_text:
        return ""
    try:
        parsed = json.loads(error_text)
    except Exception:
        parsed = None
    candidate = ""
    if isinstance(parsed, dict):
        node = parsed.get("error") if isinstance(parsed.get("error"), dict) else parsed
        if isinstance(node, dict):
            # Prefer the provider's own message, then code; some bodies nest
            # one more level ({"error": {"error": {...}}}).
            inner = node.get("error") if isinstance(node.get("error"), dict) else node
            if isinstance(inner, dict):
                candidate = str(inner.get("message") or inner.get("code") or "")
            if not candidate:
                candidate = str(node.get("message") or node.get("code") or "")
        if not candidate:
            candidate = str(parsed.get("message") or parsed.get("error") or "")
    if not candidate:
        candidate = str(error_text)
    candidate = re.sub(r"\s+", " ", candidate).strip()
    if len(candidate) > limit:
        candidate = candidate[:limit].rstrip() + "…"
    return candidate


def describe_provider_refusal(error_text: str) -> Optional[str]:
    """
    Founder-facing message for a provider content refusal, or None when the
    payload is anything else.

    The raw provider body is a nested JSON dump ("HTTP 400: {\"error\":
    {\"code\": ...}}") that names a filter code and nothing actionable. On a
    hook there is no bridge frame, so the refused input is the character
    reference photo itself — and retrying it can never succeed, so the
    message says what to change instead of inviting another attempt.
    """
    lowered = (error_text or "").lower()
    if not any(marker in lowered for marker in _PROVIDER_REFUSAL_MARKERS):
        return None
    return (
        "The provider refused the reference photo (privacy filter) — retrying "
        "won't help. Use a different photo: face forward, plain background, "
        "no other people or readable text."
    )


async def generate_video(
    prompt: str,
    reference_image_path: Path = None,
    duration: int = 5,
    model: str = None,
    generate_audio: bool = False,
    reference_video_url: str = None,
    reference_audio_url: str = None,
    input_references: list = None,
    prefer_v2v_motion: bool = False,
    continuity_frame_path: Path = None,
    continuity_video_url: str = None,
    resolution: str = None,
) -> dict:
    """Submit a video generation job to OpenRouter using MiniMax H3.

    MiniMax H3 capabilities leveraged:
    - Omni-reference inputs: up to 9 images + 3 video clips + 3 audio files in one call
    - Native stereo audio: generated in the same pass as video (dialogue, foley, music synced)
    - V2V motion transfer: feed original viral video as motion/timing reference
    - 2K resolution output
    - Up to 15 seconds per generation

    Args:
        prompt: Text prompt describing the video to generate.
        reference_image_path: Face-swapped image used as first_frame (identity anchor)
                             AND/OR as an image reference for identity guidance.
        duration: Target duration in seconds.
        model: Model key from VIDEO_MODELS (defaults to DEFAULT_VIDEO_MODEL).
        generate_audio: Whether to generate native audio. Defaults to False for hooks
                       (creators attach trending sounds in TikTok's editor).
        reference_video_url: Optional public HTTPS URL to the original viral video for
                            V2V motion transfer — the model will replicate the timing,
                            camera movement, gestures, and performance rhythm from this
                            video. MUST be a real HTTPS URL: OpenRouter's video API
                            rejects base64 data URIs for video_url references.
        reference_audio_url: Optional URL to an audio file to use as voice/music reference.
        input_references: Optional pre-built list of reference objects to pass directly.
                         Each item should follow OpenRouter's input_references schema.
        prefer_v2v_motion: When True AND a reference_video_url is provided, enables
                         V2V motion transfer mode. The face image is moved to
                         input_references (as identity guide) since the provider
                         cannot combine frame_images with input_references.
        continuity_frame_path: The previous segment's final frame, to be used as this
                          segment's first frame. This is the strongest continuity
                          mechanism available: it pins the exact pose, framing,
                          lighting, wardrobe and face at the seam, so the two clips
                          read as one take. Takes precedence over reference_image_path
                          for the frame slot and does NOT trigger V2V mode — the
                          bridge frame is the anchor, the identity reference rides
                          alongside it in input_references when the provider can
                          combine them.
        continuity_video_url: Public HTTPS URL of the previous segment's clip, passed as
                          a video reference so the model can read the motion and
                          performance rhythm leading into the seam. Attached only when
                          the provider supports combining a first frame with
                          references, because the seam frame is the stronger anchor and
                          a provider that can only take one must keep it.
    """
    # Resolve which model to use
    model_key = model if model and model in VIDEO_MODELS else DEFAULT_VIDEO_MODEL
    model_config = VIDEO_MODELS[model_key]
    model_id = model_config["id"]
    max_dur = model_config["max_duration"]
    min_dur = model_config.get("min_duration", 1)
    supports_combined = model_config.get("supports_combined_refs", False)

    payload = {
        "model": model_id,
        "prompt": prompt,
        "duration": max(min_dur, min(duration, max_dur)),
        # A per-render override is only honored when the model offers it: an
        # unlisted value falls back to the catalog default rather than reaching
        # the provider, where it is a 400 after billing the attempt. The studio
        # endpoint refuses unknown values first with the allowed list, so this
        # fallback only fires for direct callers.
        "resolution": (
            resolution
            if resolution in (model_config.get("supported_resolutions") or [])
            else model_config.get("resolution", "1080p")
        ),
        "aspect_ratio": "9:16",
    }

    # Only include generate_audio when explicitly requested. Sending False for
    # models that don't support the parameter causes a 400. Omitting it lets
    # the provider use its own default.
    #
    # The request is also gated on the model documenting the field, not just on
    # the caller asking. OpenRouter omits generate_audio from the accepted
    # parameters for some models (Hailuo 3 Max), and an unlisted parameter is a
    # 400 — so a caller asking for audio on such a model is refused its audio
    # rather than its whole render. This is what lets the studio default the
    # flag off from capability and still survive a caller that asks directly.
    if generate_audio:
        if model_config.get("supports_native_audio", False):
            payload["generate_audio"] = True
        else:
            logger.warning(
                f"{model_config['name']} does not document generate_audio; sending the "
                f"request without it so the provider applies its own audio default."
            )

    # Determine whether to use V2V motion mode.
    use_v2v_mode = prefer_v2v_motion and reference_video_url and reference_image_path and reference_image_path.exists()

    # === Reference Strategy ===
    # MiniMax H3 via OpenRouter cannot combine frame_images with
    # input_references (MiniMax returns a 400). The strategy is therefore:
    #   - Face image → input_references (as image ref for identity guidance)
    #   - Video → input_references (as video ref for motion replication)
    #   Both coexist in input_references without conflict.
    #
    # When NOT in V2V mode (no reference video):
    #   - Face image → frame_images (first_frame) for hard identity anchor
    #   - No input_references needed

    # First frame: the face-swapped image anchors identity throughout the video.
    # In V2V mode, we skip frame_images and put the image in input_references instead.
    #
    # A continuity_frame_path takes this slot with priority. It is the previous
    # segment's final frame, so the new segment starts from where the last one
    # actually stopped. It deliberately does NOT switch the request into V2V mode:
    # V2V moves the image out of frame_images, which would discard the very frame
    # that makes the seam work.
    bridge_frame = (
        continuity_frame_path
        if continuity_frame_path and Path(continuity_frame_path).exists()
        else None
    )
    if bridge_frame and reference_video_url and not prefer_v2v_motion:
        logger.info(
            "Continuity mode: sending the previous segment's final frame as the first "
            "frame and the previous clip as a reference. V2V motion mode is skipped so "
            "the seam frame is not displaced."
        )
    if reference_image_path and reference_image_path.exists() and not use_v2v_mode and not bridge_frame:
        payload["frame_images"] = [
            {
                "type": "image_url",
                "image_url": {"url": image_data_uri(reference_image_path)},
                "frame_type": "first_frame",
            }
        ]

    if bridge_frame:
        payload["frame_images"] = [
            {
                "type": "image_url",
                "image_url": {"url": image_data_uri(bridge_frame)},
                "frame_type": "first_frame",
            }
        ]

    # Build input_references for V2V mode
    refs = list(input_references) if input_references else []

    # V2V mode: put the face-swap image as an image reference so the model uses
    # it for identity guidance while also accepting the video motion reference.
    if use_v2v_mode:
        b64 = image_to_base64(reference_image_path)
        mime = "image/png"
        refs.insert(0, {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        })

    # V2V motion transfer: feed the original viral video so the model replicates
    # its timing, camera language, performance rhythm, and editing pace.
    if reference_video_url:
        refs.append({
            "type": "video_url",
            "video_url": {"url": reference_video_url},
        })

    # Audio reference
    if reference_audio_url:
        refs.append({
            "type": "audio_url",
            "audio_url": {"url": reference_audio_url},
        })

    # A provider that cannot carry a first frame AND references together would
    # reject the request outright (BytePlus returns TaskTypeConstraint, MiniMax
    # returns a 400), so exactly one visual anchor survives. The seam frame wins
    # because it carries the face AND the scene in a single image, whereas a
    # bare face reference says who the person is but not where the last shot
    # ended. This used to drop references unconditionally; it is now
    # capability-aware, so a provider that can combine frame and references
    # keeps both. None does today, but the branch stays for one that does.
    #
    # Whatever is dropped is reported back, never silently discarded.
    dropped_anchors = []
    if payload.get("frame_images") and refs:
        if supports_combined:
            logger.info(
                f"{model_config['name']} supports a first frame alongside references; "
                f"sending {len(refs)} reference(s) with the continuity frame."
            )
        else:
            dropped_anchors = [
                "clip" if r.get("type") == "video_url" else
                ("audio" if r.get("type") == "audio_url" else "identity")
                for r in refs
            ]
            logger.warning(
                f"Cannot combine frame_images + input_references on "
                f"{model_config['name']} — dropping {len(refs)} reference(s) "
                f"({', '.join(sorted(set(dropped_anchors)))}) to keep the continuity "
                f"frame, which pins the scene and the face together."
            )
            refs = []

    if refs:
        payload["input_references"] = refs

    # Size the request before sending it. A provider 400 usually names a
    # parameter, but the two limits we can actually hit here — prompt
    # characters and encoded body bytes — are ours, not theirs, and neither is
    # visible in the request or in anything the founder is shown. Logging them
    # here is what makes a size-related refusal answerable from our own logs
    # instead of inferred after the fact.
    _encoded_bytes = 0
    for _frame in payload.get("frame_images") or []:
        _encoded_bytes += len(str((_frame.get("image_url") or {}).get("url") or ""))
    for _ref in payload.get("input_references") or []:
        _encoded_bytes += len(str((_ref.get("image_url") or {}).get("url") or ""))

    logger.info(
        f"Submitting video generation ({model_config['name']}): duration={payload['duration']}s, "
        f"resolution={payload['resolution']}, has_frame_image={bool(payload.get('frame_images'))}, "
        f"continuity_frame={bool(bridge_frame)}, v2v_mode={use_v2v_mode}, audio={generate_audio}, "
        f"num_references={len(payload.get('input_references', []))}, "
        f"has_v2v_motion={bool(reference_video_url)}, model={model_id}, "
        f"prompt_chars={len(prompt)}, prompt_limit={model_config.get('prompt_char_limit')}, "
        f"image_data_kb={_encoded_bytes // 1024}"
    )

    async with httpx.AsyncClient(timeout=90) as client:
        # Retry once on transient failures (502/503/429/timeout) from OpenRouter.
        last_error = None
        for attempt in range(2):
            try:
                resp = await client.post(f"{OPENROUTER_BASE}/videos", headers=_headers(), json=payload)
            except httpx.TimeoutException as e:
                last_error = RuntimeError(f"Video generation timed out: {e}")
                if attempt == 0:
                    logger.warning(f"Video generation attempt 1 timed out, retrying...")
                    await asyncio.sleep(2)
                    continue
                raise last_error

            if resp.status_code in (502, 503, 429) and attempt == 0:
                error_text = resp.text[:200]
                logger.warning(
                    f"Video generation attempt 1 got HTTP {resp.status_code}: {error_text} — retrying..."
                )
                await asyncio.sleep(3)
                continue

            if resp.status_code >= 400:
                error_text = resp.text[:2000]
                logger.error(f"Video generation submission failed: HTTP {resp.status_code}: {error_text[:500]}")
                human = describe_provider_refusal(error_text)
                if human:
                    raise RuntimeError(human)
                # Nothing here matched a known signature, so describe the request
                # we actually sent AND quote the provider's own words. The old
                # message ended with "The full provider response is in the
                # server log" — true, but the founder never sees that log, so a
                # Grok 400 arrived as a cut-off sentence ("The full p…") after
                # server.py truncated it to 200 chars. Fail loudly instead: no
                # silent fallback to another model (founder decision), and the
                # excerpt below is what makes the next step obvious.
                #
                # Where the photo went is part of that description, and it is
                # read from the payload rather than assumed: keying off
                # frame_images alone reported "without your photo" on every
                # reference-image render, which is false and sends the founder
                # to re-upload a file that did reach the provider.
                if payload.get("frame_images"):
                    photo_route = "with your photo as the opening frame"
                elif any(
                    ref.get("type") == "image_url"
                    for ref in (payload.get("input_references") or [])
                ):
                    photo_route = "with your photo attached as a reference image"
                else:
                    photo_route = "without your photo"
                provider_excerpt = _extract_provider_message(error_text)
                raise RuntimeError(
                    f"The provider rejected this render before it started "
                    f"(HTTP {resp.status_code}), so no clip was produced and nothing "
                    f"was charged. We sent "
                    f"{model_config.get('name', model_id)}, {payload['duration']}s, "
                    f"{payload['resolution']}, {payload['aspect_ratio']}, "
                    f"{photo_route}. "
                    f"Provider said: {provider_excerpt or 'no detail returned'}. "
                    f"Try the default model or another resolution, or retry unchanged "
                    f"to confirm — retrying the identical request is safe because "
                    f"nothing was produced."
                )
            break

        data = resp.json()
        job_id = data.get("id") or data.get("generation_id") or ""
        logger.info(
            f"Video generation submitted: job_id={job_id}, status={data.get('status')}, "
            f"polling_url={data.get('polling_url')}, keys={list(data.keys())}"
        )
        if not job_id:
            logger.error(f"Video generation returned no job ID. Full response: {resp.text[:1000]}")
            raise RuntimeError("Video generation returned no job ID.")
        # Normalize: ensure 'id' key is always present
        data["id"] = job_id
        # Report what was ACTUALLY attached, so the caller never claims a
        # continuity guarantee the request does not deliver.
        data["continuity"] = {
            "has_continuity_frame": bool(bridge_frame),
            "has_frame_images": bool(payload.get("frame_images")),
            "reference_types": [r.get("type") for r in payload.get("input_references", [])],
            "dropped_anchors": sorted(set(dropped_anchors)),
        }
        return data


async def poll_video_job(job_id: str) -> dict:
    """Poll a video generation job status."""
    if not job_id:
        raise RuntimeError("No video job ID to poll.")
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{OPENROUTER_BASE}/videos/{job_id}",
            headers=_headers(),
        )
        if resp.status_code == 404:
            raise RuntimeError(f"Video job {job_id} not found (404). It may have expired.")
        resp.raise_for_status()
        data = resp.json()
        logger.info(f"Poll video {job_id}: status={data.get('status')}, has_urls={bool(data.get('unsigned_urls'))}")
        return data



async def analyze_app_profile(sources: dict, notes: str = "") -> dict:
    """Research a mobile app from its public pages and draft an App Profile.

    Args:
        sources: mapping of source label -> extracted page text, e.g.
            {"website": "...", "app_store": "...", "google_play": "..."}.
            Labels are free-form; each is capped by the caller.
        notes: founder-supplied context (positioning, pricing, constraints).

    Returns a dict matching REQUIRED_APP_PROFILE_KEYS. List values are always
    normalized to lists of non-empty strings. Never invents store ratings,
    download counts, or pricing — uncertain claims go in claims_review.
    """
    system_message = (
        "You are a mobile-app strategist and short-form video creative director. "
        "You read public app pages (website, App Store, Google Play) plus founder "
        "notes and draft an App Profile used to brief promotional video scripts. "
        "Describe functional needs and use cases — never infer sensitive personal "
        "traits about viewers, and for health-adjacent apps describe product "
        "functionality (e.g. low-friction journaling with prompts and reminders), "
        "never viewer diagnoses. Respond with STRICT JSON only, no markdown "
        "fences, no extra commentary."
    )

    parts = []
    for label, text in (sources or {}).items():
        text = (text or "").strip()
        if text:
            parts.append(f"--- {label} ---\n{text}")
    sources_block = "\n\n".join(parts) or "(no page text could be extracted)"
    founder_block = (notes or "").strip() or "(no founder notes provided)"

    prompt = (
        "Public page extracts for one mobile app:\n\n"
        f'"""\n{sources_block}\n"""\n\n'
        f"Founder notes:\n{founder_block}\n\n"
        "Draft the App Profile. Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "brand_name": "app name",\n'
        '  "brand_description": "1-3 sentence description of what the app does",\n'
        '  "app_category": "app category (e.g. Health & Fitness, Productivity)",\n'
        '  "niche": "same as app_category unless the positioning is narrower",\n'
        '  "platforms": ["iOS", "Android"] (only platforms evidenced by the sources),\n'
        '  "core_features": ["concrete features evidenced by the sources"],\n'
        '  "primary_use_cases": ["top jobs the app helps users do"],\n'
        '  "problems_solved": ["user problems the app removes"],\n'
        '  "target_audience": "short label for the primary audience",\n'
        '  "ideal_customer_profile": "2-4 sentences: who they are, what they struggle with, where they spend time online",\n'
        '  "icp_segments": ["2-4 segments as one-liners: label, functional need, hook promise"],\n'
        '  "desired_outcomes": ["outcomes users want from the app"],\n'
        # Objects rather than phrases, because a pitch needs the feature an
        # outcome comes from: "fall asleep without checking your phone" only
        # converts when the script knows it belongs to the sleep timer rather
        # than to a generic bedtime claim. Flat desired_outcomes stays as the
        # fallback list; these triples are the beat-level material.
        '  "outcome_statements": [{"outcome": "the resulting benefit, phrased as what '
        'changes in the user\'s life or how they feel after using it (e.g. helps you fall '
        'asleep without checking your phone -- never the feature spec itself, e.g. never '
        'has a sleep timer)", "who_feels_it": "who gets this outcome, functional need '
        'only, never a sensitive trait or diagnosis", "from_feature": "the core_features '
        'entry this outcome comes from, named verbatim", "how_it_helps": "how the solution '
        'works, framed as the resulting benefit rather than the mechanism (e.g. the wind-down '
        'starts itself so there is no reason to pick the phone back up -- never a spec, '
        'never a guarantee)"}],\n'
        '  "differentiation": "2-4 sentences on what sets this app apart",\n'
        '  "known_limitations": "material limitations a promo must not contradict (platforms, feature gaps)",\n'
        '  "must_not_show": ["concrete things a promo must never show or imply, each a short '
        'phrase a camera could actually depict: a specific setting, a demographic stereotype, a '
        'competitor product, a document or screen, a body part, a place this app has nothing to '
        'do with. Empty list if none apply"],\n'
        '  "usage_moments": ["the specific situations when this app is actually reached for, '
        'each a concrete moment with a time and a trigger: end of a night shift, 7am before the '
        'house wakes up, payday, the 3pm slump. Not categories -- moments. 3-5, or empty"],\n'
        '  "proof_moment": "the ONE thing a camera can film that makes this app\'s main claim '
        'believable -- the moment the user sees the result happen. One sentence, present tense, '
        'filmmable: \'the envelope splits the moment the transfer lands\'. Empty string if the '
        'sources do not state one",\n'
        # Objects rather than phrases, because an objection without the current
        # alternative is not answerable: "it's another subscription" only
        # converts if you know they already pay for three.
        '  "viewer_objections": [{"objection": "the reason this viewer would NOT '
        'download, in their words", "what_they_do_now": "the alternative they use today, '
        'including doing nothing", "honest_answer": "what is true that addresses it, '
        'without a guarantee or an invented claim"}],\n'
        '  "tone_voice": "short description of the brand voice",\n'
        '  "claims_approved": ["factual claims safe to use in promos"],\n'
        '  "claims_review": ["claims that need verification before use (ratings, counts, results)"],\n'
        '  "claims_banned": ["claims promos must never make (guaranteed outcomes, fake reviews, medical/financial promises)"]\n'
        "}\n"
        "Rules: use ONLY functionality evidenced by the sources or notes; never invent "
        "ratings, download counts, or features. Do NOT report pricing, plan names or trial "
        "terms — the App Profile deliberately carries no price, and no generated video may "
        "state one. Put anything uncertain in claims_review, never in claims_approved. "
        # The outcome layer is what lets every later prompt pitch benefits
        # instead of listing features, so it has its own completeness bar:
        # one statement per core feature the sources actually evidence, each
        # benefit-phrased and tied with from_feature. An outcome no feature
        # supports is an invented claim, not an outcome.
        "Write 3-6 outcome_statements, one per evidenced core feature. Each outcome and "
        "how_it_helps must be benefit phrasing a viewer would recognise from their own "
        "life, never a restatement of the feature spec, never a guaranteed result, and "
        "never a banned claim. from_feature must name a core_features entry verbatim. "
        "Keep every list to 8 items max. Return ONLY valid JSON."
    )

    # Routed through _chat_json (not a bare post): 4000 tokens proved too
    # small once reasoning tokens and the full strict schema share the
    # budget — the reply truncated mid-object and surfaced as "did not
    # return valid JSON". 8000 starts with headroom, and truncation is now
    # detected and retried doubled instead of misreported.
    result = await _chat_json(
        system_message=system_message,
        prompt=prompt,
        context="App profile",
        max_tokens=8000,
        timeout=90,
        json_schema=APP_PROFILE_JSON_SCHEMA,
    )

    missing = REQUIRED_APP_PROFILE_KEYS - set(result.keys())
    if missing:
        logger.error(f"App profile missing fields {missing}.")
        raise RuntimeError(f"App profile missing required fields: {missing}")

    for key in APP_PROFILE_LIST_KEYS:
        val = result.get(key)
        if isinstance(val, str):
            val = [val] if val.strip() else []
        if not isinstance(val, list):
            val = []
        result[key] = [str(v).strip() for v in val if str(v).strip()][:8]

    # viewer_objections is a list of objects and is NOT in
    # APP_PROFILE_LIST_KEYS above, so its entries are still dicts by the time we
    # get here. Normalized separately and, unlike the phrase lists, a malformed
    # entry is dropped whole rather than kept as a half-answer: an objection
    # with a missing honest_answer is worse than no objection, because the arc
    # has nothing to aim at.
    _normalize_objection_list(result)

    # Same treatment for the outcome layer: an outcome without its source
    # feature is exactly the unlinked benefit phrasing the flat list already
    # carries, and a how_it_helps that restates the spec is a feature wearing
    # benefit clothes. Both are dropped rather than repaired.
    _normalize_outcome_statements(result)

    return result


def _normalize_objection_list(result: dict) -> None:
    """
    Coerce the model reply's viewer_objections into usable triples.

    The founder's schema and the database store this as a JSON list of objects,
    so everything downstream -- the prompt, the detail page -- can rely on the
    three keys being present and non-empty rather than re-checking at each read.
    """
    raw = result.get("viewer_objections")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            raw = []
    if not isinstance(raw, list):
        result["viewer_objections"] = []
        return
    kept = []
    for item in raw[:6]:
        if not isinstance(item, dict):
            continue
        triple = {
            "objection": str(item.get("objection") or "").strip()[:200],
            "what_they_do_now": str(item.get("what_they_do_now") or "").strip()[:200],
            "honest_answer": str(item.get("honest_answer") or "").strip()[:300],
        }
        if not triple["objection"] or not triple["honest_answer"]:
            # No current alternative, or no answer: nothing the arc can use.
            continue
        kept.append(triple)
    result["viewer_objections"] = kept


def _normalize_outcome_statements(result: dict) -> None:
    """
    Coerce the model reply's outcome_statements into usable linked entries.

    The founder's schema and the database store this as a JSON list of objects,
    so everything downstream — angles, brand templates, plan, strategy — can
    rely on the outcome-to-feature link being present rather than re-deriving
    it from two flat lists at each read.

    A malformed entry is dropped whole: an outcome with no source feature
    cannot be traced back to anything evidenced, and a how_it_helps that only
    restates the spec would pitch the feature list the whole layer exists to
    replace. Guilt by association is avoided the other way too — entries are
    never repaired into guesses.
    """
    raw = result.get("outcome_statements")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            raw = []
    if not isinstance(raw, list):
        result["outcome_statements"] = []
        return
    kept = []
    for item in raw[:6]:
        if not isinstance(item, dict):
            continue
        entry = {
            "outcome": str(item.get("outcome") or "").strip()[:300],
            "who_feels_it": str(item.get("who_feels_it") or "").strip()[:200],
            "from_feature": str(item.get("from_feature") or "").strip()[:200],
            "how_it_helps": str(item.get("how_it_helps") or "").strip()[:300],
        }
        if not entry["outcome"] or not entry["from_feature"]:
            continue
        kept.append(entry)
    result["outcome_statements"] = kept


async def generate_content_angles(profile: dict, max_angles: int = 6,
                                  angle_feedback: Optional[dict] = None) -> list:
    """
    Generate content angles for an approved App Profile.

    Each angle carries the planning fields the studio needs: audience, problem,
    hook promise, feature, desired emotion, CTA, and the claims to respect.

    Guardrails enforced in the prompt:
      - Functional framing only. Never infer sensitive personal traits about
        viewers; for health-adjacent apps describe product functionality
        ("low-friction journaling with short prompts and reminders"), never a
        viewer diagnosis.
      - Every angle must be satisfiable using only the profile's verified
        fields. Anything speculative is pushed to claims_to_respect.
      - No guaranteed outcomes, no testimonials. Never state a price, plan name or
        trial term: the App Profile carries none, and a video that quotes one
        cannot be verified.

    Args:
        profile: an App Profile row (brand_profiles) with fields already
            parsed into Python values by row_to_dict.
        max_angles: hard cap on returned angles.
        angle_feedback: Goal thumbs attributed to angle kinds and
            objectives (feedback.summarize_angle_feedback). Counts only;
            rendered into the prompt, or a stated none-yet when empty.
    """
    def _list(name):
        val = profile.get(name)
        if isinstance(val, list):
            return [str(v) for v in val if str(v).strip()]
        if val:
            return [str(val)]
        return []

    context = {
        "app_name": profile.get("brand_name") or "(unnamed app)",
        "category": profile.get("app_category") or profile.get("niche") or "(unstated)",
        "description": profile.get("brand_description") or "(unstated)",
        "platforms": _list("platforms"),
        "features": _list("core_features"),
        "use_cases": _list("primary_use_cases"),
        "problems": _list("problems_solved"),
        "audience": profile.get("target_audience") or "(unstated)",
        "icp_segments": _list("icp_segments"),
        "outcomes": _list("desired_outcomes"),
        # Kept linked so an angle's app_feature choice can stay on the
        # evidenced outcome pair instead of re-deriving it.
        "outcome_statements": profile.get("outcome_statements") or [],
        "differentiators": profile.get("differentiation") or "(unstated)",
        "limitations": profile.get("known_limitations") or "(none recorded)",
        "voice": profile.get("tone_voice") or "(unstated)",
        "approved_claims": _list("claims_approved"),
        "claims_needing_review": _list("claims_review"),
        "banned_claims": _list("claims_banned"),
    }

    kinds = ", ".join(CONTENT_ANGLE_KINDS)

    system_message = (
        "You are a short-form video strategist for mobile apps. You propose content "
        "angles that a founder can actually film, each grounded strictly in verified "
        "product facts. Describe viewers by FUNCTIONAL need and use case only — never "
        "infer sensitive personal traits (health diagnoses, mental-health labels, "
        "finances, religion, sexuality, political leaning). For health-adjacent apps, "
        "describe the product's functionality, never a condition the viewer may have. "
        "Respond with STRICT JSON only, no markdown fences."
    )

    prompt = (
        f"VERIFIED APP PROFILE:\n{json.dumps(context, indent=2)}\n\n"
        f"Choose from these angle kinds: {kinds}\n\n"
        f"Propose exactly {max_angles} DISTINCT content angles, ordered strongest first. "
        "Return ONLY a JSON array where each element is:\n"
        "{\n"
        '  "kind": "one of the kinds listed above",\n'
        '  "label": "short 3-6 word title",\n'
        '  "target_audience": "The audience segment, described functionally",\n'
        '  "user_problem": "The concrete problem this angle speaks to",\n'
        '  "hook_promise": "What the first 3 seconds promise",\n'
        '  "app_feature": "The app feature this angle demonstrates",\n'
        '  "desired_emotion": "The emotion the viewer should feel by the end",\n'
        '  "claims_to_respect": ["Claims or limitations that bound this angle"]\n'
        "}\n"
        "Rules: use ONLY facts present in the profile. Every text field is a "
        "sentence that starts with a capital letter -- write the examples above as "
        "sentences, not as lowercase fragments, or the angle renders with a typo. "
        "If an angle would require a "
        "claim from claims_needing_review, list that claim in claims_to_respect. Never "
        "promise guaranteed outcomes, invent testimonials or reviews, state any price or "
         "trial term, or imply a feature the profile does not list. Vary the "
         "kinds — do not return six variations of the same angle. Return ONLY valid JSON."
    )

    # Goal thumbs, when any exist. Counts and fixed kind/objective names
    # only — the same rule as every other prompt layer. Rendered always, so
    # an empty record reads as "no evidence yet" rather than as silence the
    # model could fill with an invented best performer.
    if angle_feedback is not None:
        prompt += f"\n\n{feedback.build_angle_feedback_section(angle_feedback)}"


    # Routed through _chat_json so truncation is detected and retried
    # doubled instead of surfacing as unparseable JSON. The list-or-dict
    # handling below stays: a provider that ignores response_format can
    # still answer either way.
    parsed = await _chat_json(
        system_message=system_message,
        prompt=prompt,
        context="Content angles",
        max_tokens=3000,
        timeout=90,
        json_schema=ANGLES_JSON_SCHEMA,
    )

    if isinstance(parsed, dict):
        parsed = parsed.get("angles") or parsed.get("content_angles") or []
    if not isinstance(parsed, list):
        raise RuntimeError("Content angles response was not a list.")

    angles = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        normalized = {
            "kind": normalize_angle_kind(item.get("kind")),
            "label": (item.get("label") or "").strip()[:120],
            "target_audience": (item.get("target_audience") or "").strip()[:400],
            "user_problem": (item.get("user_problem") or "").strip()[:600],
            "hook_promise": (item.get("hook_promise") or "").strip()[:300],
            "app_feature": (item.get("app_feature") or "").strip()[:300],
            "desired_emotion": (item.get("desired_emotion") or "").strip()[:200],
            "claims_to_respect": [],
        }
        raw_claims = item.get("claims_to_respect")
        if isinstance(raw_claims, str):
            raw_claims = [raw_claims]
        if isinstance(raw_claims, list):
            normalized["claims_to_respect"] = [
                str(c).strip()[:200] for c in raw_claims if str(c).strip()
            ][:6]
        # An angle with no audience or no problem is not actionable downstream.
        if not normalized["target_audience"] or not normalized["user_problem"]:
            continue
        angles.append(normalized)
        if len(angles) >= max_angles:
            break

    if not angles:
        raise RuntimeError("Content angles response contained no usable angles.")
    return angles


POST_KIT_JSON_SCHEMA = _strict_object({
    "caption": _str_prop(),
    "hashtags": {"type": "array", "items": _str_prop()},
    "cover_text": _str_prop(),
})


async def generate_post_kit(project: dict, profile: dict) -> dict:
    """
    Post kit for one render: 1 caption, a hashtag set, cover text.

    Grounded strictly in this render's own hook, script, and CTA plus the
    profile's verified facts. Anything outside that fails loudly instead of
    shipping as post copy: banned claims raise, guarantee language raises,
    and unmentioned prices/plans/outcomes are forbidden with clamped lengths.
    """
    def _list(name):
        val = profile.get(name)
        if isinstance(val, list):
            return [str(v) for v in val if str(v).strip()]
        if val:
            return [str(val)]
        return []

    hook = str((project or {}).get("hook_line") or "").strip()
    script = str((project or {}).get("script") or "").strip()
    cta = str((project or {}).get("cta") or "").strip()
    if not hook or not script:
        raise RuntimeError("Post kit needs the render's approved hook and script.")

    context = {
        "app_name": profile.get("brand_name") or "(unnamed app)",
        "description": profile.get("brand_description") or "(unstated)",
        "audience": profile.get("target_audience") or "(unstated)",
        "voice": profile.get("tone_voice") or "(unstated)",
        "hook_line": hook,
        "script": script,
        "call_to_action": cta or "(none)",
        "approved_claims": _list("claims_approved"),
        "banned_claims": _list("claims_banned"),
    }

    system_message = (
        "You write TikTok post copy for a mobile app's finished clip. Every "
        "word must be grounded in the render material and profile facts "
        "below — restate, compress, and rephrase them, never add to them. "
        "Never state a price, plan name, trial term, follower count, ranking, "
        "or outcome the inputs do not state. Never promise guaranteed results "
        "or invent testimonials. Respond with STRICT JSON only, no markdown "
        "fences."
    )
    prompt = (
        f"RENDER MATERIAL:\n{json.dumps(context, indent=2)}\n\n"
        "Write the post kit for THIS clip only. Return ONLY a JSON object:\n"
        "{\n"
        '  "caption": ["one TikTok caption under 50 words: open with the hook idea in the "\n'
        '    viewer\u2019s words, then state what the app does plainly, then end with "\n'
        '    a short question"],\n'
        '  "hashtags": ["4 to 7 tags, #AppName first, then niche and functional tags"],\n'
        '  "cover_text": "under 8 words for the cover, from the hook line only"\n'
        "}\n"
        "Rules: use ONLY the hook, script, CTA, and profile facts above. No "
        "banned claim may appear. No guaranteed outcomes. Return ONLY valid JSON."
    )
    parsed = await _chat_json(
        system_message=system_message,
        prompt=prompt,
        context="Post kit",
        max_tokens=1500,
        timeout=90,
        json_schema=POST_KIT_JSON_SCHEMA,
    )
    if not isinstance(parsed, dict):
        raise RuntimeError("Post kit response was not an object.")

    raw_caption = parsed.get("caption")
    if isinstance(raw_caption, list):
        raw_caption = " ".join(str(c) for c in raw_caption)
    caption = str(raw_caption or "").strip()[:300]
    raw_tags = parsed.get("hashtags")
    if isinstance(raw_tags, str):
        raw_tags = raw_tags.split()
    hashtags = [str(t).strip()[:60] for t in (raw_tags or []) if str(t).strip()][:7]
    cover_text = str(parsed.get("cover_text") or "").strip()[:100]
    if not caption or len(hashtags) < 4 or not cover_text:
        raise RuntimeError("Post kit response was missing caption, hashtags, or cover text.")

    # Grounded means verifiable: a banned claim or a guarantee in post copy
    # is a bug, not a nuance — the render gate holds the video to this, so
    # the words posted beside it are held to it too.
    banned = _list("claims_banned")
    for text in [caption, cover_text]:
        hits = find_banned_violations(text, banned)
        if hits:
            raise RuntimeError(
                "Post kit used a banned claim: " + hits[0]["claim"]
            )
        risks = find_risk_patterns(text)
        if risks:
            raise RuntimeError(
                "Post kit used guarantee language: " + str(risks[0].get("claim", ""))
            )
    return {"caption": caption, "hashtags": hashtags, "cover_text": cover_text}


# How many tailored structures each approved profile gets. Ten is a full
# picker page without clutter; the picker ranks them against curated rows,
# so a weak tenth still loses honestly rather than filling a quota.
BRAND_TEMPLATE_COUNT = 10


def normalize_brand_template(raw: dict) -> Optional[dict]:
    """
    Coerce one model-drafted brand template into row-ready shape, or None
    when it is unusable. Invalid items are dropped, never repaired into
    something the model did not write — except required_assets, which is
    forced face-only by the product rule rather than requested and trusted.
    """
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "").strip()[:TEMPLATE_NAME_MAX]
    opening = str(raw.get("opening_structure") or "").strip()
    if not name or not opening:
        return None
    slots = raw.get("content_slots")
    if isinstance(slots, dict):
        slots = {
            str(k).strip(): str(v).strip()[:300]
            for k, v in slots.items()
            if str(k).strip() and str(v).strip()
        } or {}
    else:
        slots = {}
    # Directorial, not a render length. A hook that needs more than four seconds
    # to land is not a hook, and the first four seconds are the only window a
    # viewer decides in.
    try:
        hook_seconds = max(
            MIN_HOOK_SECONDS, min(MAX_HOOK_SECONDS, int(raw.get("hook_seconds") or 3))
        )
    except (TypeError, ValueError):
        hook_seconds = 3
    duration = clamp_duration(raw.get("default_duration"))
    # A "cta" content slot is meaningless now: the CTA is added by the founder in
    # their own editor, so a template that asks for one is describing footage
    # this product does not make. Dropped rather than relabelled — a model asked
    # for a slot it can only fill with a call to action will invent one.
    slots.pop("cta", None)
    slots.pop("call_to_action", None)
    slots.pop("next_action", None)
    # Viewer-facing outcome line for the picker card. Optional: a template
    # without one is still usable, so a missing field degrades to no headline
    # rather than invented copy. Never repaired — same rule as everything else.
    outcome = str(raw.get("outcome") or "").strip()[:300]
    return {
        "name": name,
        "category": normalize_category(raw.get("category")),
        "objective": normalize_objective(raw.get("objective")),
        "opening_structure": opening,
        "hook_seconds": hook_seconds,
        "middle_structure": str(
            raw.get("middle_structure") or raw.get("continuation_structure") or ""
        ).strip()[:1200],
        "visual_style": str(raw.get("visual_style") or "").strip()[:300],
        "camera_pacing": str(raw.get("camera_pacing") or "").strip()[:300],
        "content_slots": slots,
        "default_duration": duration,
        "outcome": outcome,
    }


def _component_feedback_block(component_feedback: Optional[dict], component: str) -> str:
    """This stage's own thumbs as a prompt block; other components are never read."""
    if not component_feedback or component not in component_feedback:
        return ""
    section = feedback.build_component_feedback_section(
        {component: component_feedback[component]}, component)
    return f"\n\n{section}\n\n" if section else ""


async def generate_brand_templates(
    profile: dict, angles: Optional[list] = None, count: int = BRAND_TEMPLATE_COUNT,
    objective: str = "",
    component_feedback: Optional[dict] = None,
) -> list:
    """
    Draft tailored hook structures for one approved App Profile AND one
    selected objective.

    The objective is caller-supplied (the founder picked it in the wizard),
    never model-chosen: every returned structure serves that goal, which is
    what makes the set worth generating per objective rather than once per
    profile. This is the brand-URL-to-template link: the profile researched
    from the founder's links produces structures no generic library can —
    hooks shaped around THIS app's features, audience language, and voice.
    Every video stars the founder on camera, so structures are designed for
    a single on-camera presenter, never for screenshots, recordings, or app
    footage.

    Guardrails enforced in the prompt: functional framing only (never a
    viewer diagnosis), every structure satisfiable from verified profile
    facts, no invented features/prices/ratings/testimonials, no guaranteed
    outcomes. required_assets is not requested at all — the caller forces
    face-only, so the model cannot get it wrong.
    """
    def _list(name):
        val = profile.get(name)
        if isinstance(val, list):
            return [str(v) for v in val if str(v).strip()]
        if val:
            return [str(val)]
        return []

    context = {
        "app_name": profile.get("brand_name") or "(unnamed app)",
        "category": profile.get("app_category") or profile.get("niche") or "(unstated)",
        "description": profile.get("brand_description") or "(unstated)",
        "features": _list("core_features"),
        "use_cases": _list("primary_use_cases"),
        "problems": _list("problems_solved"),
        "audience": profile.get("target_audience") or "(unstated)",
        "icp_segments": _list("icp_segments"),
        "outcomes": _list("desired_outcomes"),
        "outcome_statements": profile.get("outcome_statements") or [],
        "differentiators": profile.get("differentiation") or "(unstated)",
        "voice": profile.get("tone_voice") or "(unstated)",
        "approved_claims": _list("claims_approved"),
        "banned_claims": _list("claims_banned"),
    }
    angle_briefs = []
    for angle in (angles or [])[:8]:
        if not isinstance(angle, dict):
            continue
        angle_briefs.append({
            "kind": angle.get("kind") or "",
            "label": angle.get("label") or "",
            "audience": angle.get("target_audience") or "",
            "problem": angle.get("user_problem") or "",
            "feature": angle.get("app_feature") or "",
        })
    categories = ", ".join(HOOK_CATEGORIES)
    want_objective = normalize_objective(objective)
    if want_objective:
        brief_line = (
            f"Design exactly {count} DISTINCT hook structures for THIS app AND this objective: "
            f"{want_objective}. Every structure below must serve that objective; a structure "
            f"serving any other goal is a wrong answer no matter how good it reads. "
        )
    else:
        # Defensive only: the endpoint refuses an empty objective, so this
        # path means a direct caller. Spread rather than fail.
        brief_line = f"Design exactly {count} DISTINCT hook structures for THIS app. "

    system_message = (
        "You are a short-form video strategist for mobile apps. You design hook "
        "structures tailored to ONE specific app, grounded strictly in its verified "
        "profile facts. Describe viewers by FUNCTIONAL need and use case only — never "
        "infer sensitive personal traits (health diagnoses, mental-health labels, "
        "finances, religion, sexuality, political leaning). Respond with STRICT JSON "
        "only, no markdown fences."
    )

    prompt = (
        f"VERIFIED APP PROFILE:\n{json.dumps(context, indent=2)}\n\n"
        f"CONTENT ANGLES:\n{json.dumps(angle_briefs, indent=2)}\n\n"
        f"Categories (use only these): {categories}\n\n"
        f"{brief_line}"
        f"{_component_feedback_block(component_feedback, 'template')}"
        "A generated video is exactly TWO sections and nothing else: a HOOK in the first "
        "4 seconds, then a MIDDLE that develops it. The middle develops the situation, the "
        "friction or the reaction, and ends at the moment the viewer would reach for the app. "
        "Design nothing past that moment. The product demo is recorded by the founder and "
        "attached separately, and the call to action is added by them in their own editor — "
        "so a structure that pays off, demonstrates the app in use, or closes on an action is "
        "a wrong answer no matter how well it reads. "
        "Presenter-led throughout: every video stars the founder on camera, so never design around "
        "screenshots, recordings, app footage, or any uploaded asset. Pre-fill every "
        "content slot with this app's concrete specifics, not placeholders. "
        "Return ONLY a JSON array where each element is:\n"
        "{\n"
        '  "name": "short specific title naming this app\'s angle on the mechanic",\n'
        '  "category": "one of the categories listed above",\n'
        '  "objective": "address_user_problem | create_curiosity | demonstrate_feature | build_awareness | educate_viewers | achieve_desired_outcome | overcome_viewer_doubt | ease_daily_moment | avoid_common_mistake | feel_seen_and_understood",\n'
        '  "opening_structure": "what the first 4 seconds do, concretely for THIS app",\n'
        '  "hook_seconds": 3,\n'
        '  "middle_structure": "how the rest of the GENERATED piece develops that hook, concretely for THIS app. It must stop at the moment the viewer would reach for the app.",\n'
        '  "visual_style": "the look, presenter-led",\n'
        '  "camera_pacing": "camera behaviour",\n'
        '  "content_slots": {"the_concrete_beat": "the concrete beat this structure turns on", "the_moment": "where the viewer would reach for the app"},\n'
        '  "default_duration": 15,\n'
        '  "outcome": "what the viewer ends up with from this structure, one sentence, viewer-facing (e.g. hears their own frustration said out loud) -- never the mechanic, never a guaranteed result",\n'
        "}\n"
        "Rules: use ONLY facts present above. Every text field is a "
        "sentence that starts with a capital letter -- write the examples above as "
        "sentences, not as lowercase fragments, or the template renders with a typo. "
        "Never invent a feature, price, rating, "
        "review, testimonial, or guaranteed outcome. Never use a banned claim. Vary "
        "the categories and objectives — not ten variations of one idea. "
        f"hook_seconds is {MIN_HOOK_SECONDS}-{MAX_HOOK_SECONDS}; default_duration is one of "
        f"{', '.join(str(d) for d in SUPPORTED_DURATIONS)} seconds, and it is the length of the "
        "whole generated piece, not of a video the viewer finishes. Always set "
        f"default_duration to {max(SUPPORTED_DURATIONS)} seconds: a shorter piece has a "
        "smaller middle, and the plan's spoken words are budgeted to what that middle can "
        "speak, so a shorter template silently cuts the payoff sentence. Only when this "
        "structure's mechanic physically cannot hold a longer piece (for example a single "
        "visual beat with nothing to develop) may a lower value be used. "
        "Never use double-quote characters inside any string value. Return ONLY valid JSON."
    )

    # ~10 structures x ~12 short values is roughly triple the strategy
    # schema, so the budget is tripled rather than reused.
    raw = await _chat_json(
        system_message=system_message,
        prompt=prompt,
        context="Brand templates",
        temperature=0.5,
        max_tokens=16384,
        attempts=2,
        json_schema=TEMPLATES_JSON_SCHEMA,
        strict=False,
    )
    if isinstance(raw, dict):
        raw = raw.get("templates") or []
    if not isinstance(raw, list):
        raise RuntimeError("Brand templates response was not a list.")

    templates = []
    for item in raw:
        normalized = normalize_brand_template(item)
        if normalized is None:
            continue
        templates.append(normalized)
        if len(templates) >= count:
            break

    if not templates:
        raise RuntimeError("Brand templates response contained no usable templates.")
    return templates


# The plan covers two generated sections and nothing else. `demo_brief` replaces
# the old `feature_emphasis`: the founder needs to know what to record for their
# own demo, so the plan still works it out — but it is a note FOR THE FOUNDER and
# is deliberately excluded from every video prompt. A feature instruction that
# reaches the render is a product demo being generated, which is the one thing
# this workflow does not do.
REQUIRED_PLAN_KEYS = {
    "hook_line", "script", "beat_timeline", "visual_direction",
    "demo_brief", "voice_direction", "sound_direction",
}

# The two sections a plan's beat timeline is made of. Enforced, not suggested:
# a third label means the model has started planning footage this product does
# not generate.
PLAN_SECTION_LABELS = ("hook", "middle")


# Phrases that make a spoken line a promotion, a hype reel or an AI draft rather
# than a person talking. Matched as whole phrases against normalized text, so
# "I couldn't get started" and "I look forward to writing" never trip them.
#
# Deliberately narrow. A check that fires on a genuine customer line is worse
# than no check: the retry below raises after its third attempt, so a false
# positive turns a good plan into "could not produce complete spoken
# sentences" and the founder gets no plan at all. So only phrases that are
# unarguably promotion, unarguably exaggerated, or unarguably machine-written
# belong here; judgement calls stay in the prompt's own rules.
_PROMOTION_MARKERS = (
    "you won t believe", "you wont believe", "mind blown", "mind blowing",
    "this changed everything", "changed my life", "life changing",
    "shocking", "shockingly", "game changer",
    "no one talks about", "nobody talks about", "little did i know",
    "guaranteed", "miracle", "cured", "cure for",
    "download", "install it", "install the app", "sign up", "try it free",
    "try the app", "get the app", "our app", "our product", "we built",
    "as the founder", "as the developer", "link in bio", "follow for more",
    "hit the follow", "smash that", "comment below", "tag a friend",
)
_AI_FLUFF_MARKERS = (
    "in today s fast paced world", "fast paced world", "digital age",
    "ever evolving", "ever changing", "let s dive in", "lets dive in",
    "dive into", "diving into", "unlock the power", "unleash the",
    "supercharge", "to the next level", "imagine a world where",
    "the best part", "look no further", "here s the thing",
)


def _spoken_marker_hit(text: str, markers: tuple) -> str:
    """The first phrase from `markers` that appears in `text`, else "".

    Normalized the same way the other spoken checks normalize: lowercased with
    punctuation gone, so "It's a GAME-CHANGER!" and "game changer" match.
    """
    normalized = _normalize_spoken(text)
    for marker in markers:
        if marker in normalized:
            return marker
    return ""


def _spoken_line_rules_block() -> str:
    """
    How a real customer talks, for both spoken lines in every prompt.

    The plan and the strategy each already had fragments of this scattered
    through their own rule lists — customer voice in the plan, a pattern
    interrupt in the strategy — and neither prompt said the rest. Now one block
    states the whole craft for both, so the two cannot drift apart and the
    strategy's own words are held to the plan's rules when it writes without an
    approved plan to bind to.

    Kept to five lines on purpose: the strategy prompt already carries its own
    demo/CTA bans and its own one-story rule, so this complements them rather
    than repeating them, and a strategy prompt over its token ceiling truncates
    into a 502 the founder cannot fix.
    """
    return (
        "SPOKEN LINE CRAFT (both spoken lines, every draft):\n"
        "- HOOK: open on a relatable question, a curiosity gap, or a frustration "
        "this viewer recognises, in first person. Plain power words are fine "
        "(never, still, every time). No clickbait, hype or exaggeration.\n"
        "- EXTENSION: the script continues the hook — it answers, finishes or "
        "develops it. One person, one story, one thought: no new problem, no "
        "second hook, no hook said again.\n"
        "- OUTCOMES, NOT FEATURES: say what the speaker noticed, discovered, "
        "understood or ended up doing. Describe the change in their life, never "
        "a feature or a screen.\n"
        "- CONVERSATIONAL: words you would actually say out loud, in short spoken "
        "sentences. No corporate language, jargon or filler, and none of the "
        "AI-sounding openers: 'in today's fast-paced world', 'imagine a world "
        "where', 'the best part?', 'take it to the next level'.\n"
        "- NO PROMOTION: never name the app, the brand or the founder, never say "
        "'we' or 'our app', never claim a personal history with it (no 'I use', "
        "'I have been using', 'my patients'), and never ask for anything — no "
        "download, install, sign-up, follow or 'try it'. A customer telling "
        "what happened is the whole piece.\n"
    )


def _angle_goal_block(angle: Optional[dict], objective: str, audience: str = "") -> str:
    """
    The audience, problem and goal rule shared by the plan and the strategy.

    The hook and the script are the only words a viewer hears, so each must be
    built from the selected angle (whose problem, for whom) and the selected
    goal (what those words have to do). Both prompts state it as the same hard
    constraint, so neither can drift back to a soft "reconcile" note.

    `audience` is the founder's own words for this render, when they have written
    them, and they outrank the angle's: the alternative is one prompt naming two
    different viewers, where the WHO line sends the hook at the angle's audience
    and the brief sends it at theirs. With no override the angle's audience wins,
    which is the behaviour the angle's own selection implies.
    """
    a = angle or {}

    def _text(key: str) -> str:
        return str(a.get(key) or "").strip()

    audience = str(audience or "").strip() or _text("target_audience") or "the viewer described in VERIFIED APP FACTS"
    lines = [
        "ANGLE + GOAL RULE (hard constraints for the hook_line and every spoken line):",
        f"- WHO: say it to this viewer only: {audience}.",
    ]
    if _text("user_problem"):
        lines.append(f"- PROBLEM: the hook names this exact problem in the viewer's words: {_text('user_problem')}. The script develops and resolves it.")
    if _text("hook_promise"):
        lines.append(f"- PROMISE: the hook opens on this promise: {_text('hook_promise')}.")
    if _text("app_feature"):
        lines.append(f"- SOLUTION: the middle resolves the problem through {_text('app_feature')}, as a change in the viewer's life, never a feature list.")
    if _text("desired_emotion"):
        lines.append(f"- FEELING: the viewer should feel {_text('desired_emotion')}.")
    goal = normalize_objective(objective)
    job = OBJECTIVE_OUTCOMES.get(goal, "")
    if goal and job:
        lines.append(f"- GOAL: '{goal}' means: {job}. The hook and script do that job for this viewer. The founder's later demo/CTA is not spoken here: NEVER include a product demonstration or a call to action.")
    lines.append("- TEMPLATE: the template sets the hook's SHAPE only; fill it with this angle's problem and facts, never its example wording.")
    lines.append("- CONFLICT: if the goal and angle clash, keep this viewer and problem; the goal shapes how the script moves them forward.")
    return "\n".join(lines) + "\n"


async def generate_creative_plan(
    profile: dict,
    template: dict,
    angle: Optional[dict] = None,
    objective: str = "",
    duration_seconds: int = 20,
    tone: str = "",
    brand_voice: str = "",
    audience: str = "",
    visual_direction: str = "",
    profile_feedback: Optional[dict] = None,
    component_feedback: Optional[dict] = None,
) -> dict:
    """
    Generate an editable creative plan from an approved App Profile + template.

    The plan is what the founder reviews and edits BEFORE any video generation
    is submitted, so nothing here costs a video call.

    Timeline shape is exactly two sections: a hook occupying the opening
    seconds, then a middle that develops it and ends at the moment the viewer
    would reach for the app. There is no demonstration beat and no closing beat.
    The demo is recorded by the founder and attached afterwards; the call to
    action is added in their own editor.

    `audience` and `visual_direction` are the founder's own words, already on
    the project they are regenerating from. A regeneration used to ignore both
    and could come back with a different audience or a different look than the
    one they had chosen, which is the plan overwriting a decision rather than
    drafting the words. Both are passed through: a stated audience beats the
    angle's, and a stated visual direction is one the returned visual_direction
    must describe rather than replace.

    The prompt directs the model to render the full scene itself — environment,
    setting, props and on-screen context invented concretely from the verified
    facts — because nothing is composited over the footage and no text appears
    on screen at all. On-screen text stays out of the model's hands entirely,
    and anything the viewer could read as a factual claim about the app must
    come from verified facts or stay out of frame.

    Returns a dict matching REQUIRED_PLAN_KEYS plus `claims_used` (the model's
    own account of which approved claims it used, reconciled by claim_safety).
    """
    def _list(name):
        val = profile.get(name)
        if isinstance(val, list):
            return [str(v) for v in val if str(v).strip()]
        if val:
            return [str(val)]
        return []

    facts = {
        "app_name": profile.get("brand_name") or "(unnamed app)",
        "category": profile.get("app_category") or profile.get("niche") or "(unstated)",
        "description": profile.get("brand_description") or "(unstated)",
        "platforms": _list("platforms"),
        "features": _list("core_features"),
        "use_cases": _list("primary_use_cases"),
        "problems": _list("problems_solved"),
        "desired_outcomes": _list("desired_outcomes"),
        # Objects, kept linked: the middle's closing beat voices one of these
        # outcomes directly, and the from_feature link is what keeps it tied
        # to something evidenced rather than floating as a generic benefit.
        "outcome_statements": profile.get("outcome_statements") or [],
        "differentiators": profile.get("differentiation") or "(unstated)",
        "known_limitations": profile.get("known_limitations") or "(none recorded)",
    }

    # The template's own opening length wins over the 3s default, so the beat
    # layout the model is asked for and the mechanism it was given agree. Clamped
    # here because this is the number the prompt states in seconds.
    hook_seconds = max(
        MIN_HOOK_SECONDS, min(MAX_HOOK_SECONDS, int(template.get("hook_seconds") or 3))
    )

    # The words are budgeted to the piece's seconds, at the same natural pace
    # the render gate and the Review step use. Stating the number in the prompt
    # is what makes the script the founder approves the script that renders:
    # the gate that refuses an over-length script downstream names this same
    # budget, so asking for less here is the fix at its cause rather than a
    # trim the founder keeps getting sent back to do.
    middle_seconds = max(1, int(duration_seconds or 0) - int(hook_seconds or 0))
    # What each line is asked to AIM at, and the ceiling its seconds impose.
    # See the SPOKEN WORDS rule below: the target is what makes the hook an
    # opening line rather than a paragraph. One source for all four numbers,
    # so the prompt and the render cannot disagree about them.
    targets = spoken_targets(hook_seconds, duration_seconds)
    hook_budget = targets["hook"]["ceiling"]
    middle_budget = targets["script"]["ceiling"]
    hook_target = targets["hook"]["target"]
    script_target = targets["script"]["target"]
    # Character targets guide pacing, not grammar: a word-count floor made
    # the writer pad short thoughts while the character ceiling cut them back.
    # Prefer a complete shorter opening to conflicting minimum/maximum quotas.

    structure = {
        "template_name": template.get("name") or "(no template)",
        "hook_category": template.get("category") or "(unstated)",
        "opening_structure": template.get("opening_structure") or "(unstated)",
        "hook_seconds": hook_seconds,
        "middle_structure": template.get("middle_structure") or "(unstated)",
        "visual_style": template.get("visual_style") or "(unstated)",
        "camera_pacing": template.get("camera_pacing") or "(unstated)",
        "content_slots": template.get("content_slots") or {},
        "required_assets": template.get("required_assets") or [],
    }

    brief = {
        "objective": objective or "(unstated)",
        # The founder's own audience wins: it is the one they typed on the
        # project, so it is the decision this regeneration is meant to serve.
        "audience": (
            (audience or "").strip()
            or (angle or {}).get("target_audience")
            or profile.get("target_audience")
            or "(unstated)"
        ),
        "content_angle": (angle or {}).get("kind") or "(none)",
        "angle_label": (angle or {}).get("label") or "",
        "angle_user_problem": (angle or {}).get("user_problem") or "",
        "angle_hook_promise": (angle or {}).get("hook_promise") or "",
        "angle_feature": (angle or {}).get("app_feature") or "",
        "angle_emotion": (angle or {}).get("desired_emotion") or "",
        "duration_seconds": duration_seconds,
        "tone": tone or "(unstated)",
    }
    if (visual_direction or "").strip():
        # Their look, not the model's: the returned visual_direction describes
        # this instead of inventing a competing one.
        brief["visual_direction"] = (visual_direction or "").strip()

    claims = {
        "approved": _list("claims_approved"),
        "needs_review": _list("claims_review"),
        "never_use": _list("claims_banned"),
        "brand_voice": brand_voice or profile.get("tone_voice") or "(unstated)",
    }
    feedback_context = ""
    if profile_feedback:
        feedback_context = (
            "\n\nPROFILE FEEDBACK:\n"
            f"{feedback.build_profile_feedback_section(profile_feedback)}\n"
        )
    feedback_context += _component_feedback_block(component_feedback, "plan")

    # The founder's audience, when they wrote one, is the WHO line's audience
    # too -- not just the brief's. One prompt naming two viewers is a model
    # free to pick either.
    angle_goal_block = _angle_goal_block(angle, objective, audience)
    system_message = (
        "You are a short-form video creative director for mobile app promotions. "
        "You write concrete, filmable plans grounded ONLY in verified product facts. "
        "A plan covers exactly TWO generated sections — a HOOK in the first few seconds, "
        "then a MIDDLE that develops it — and stops at the moment the viewer would reach "
        "for the app. The product demo and the call to action are recorded and added by "
        "the founder separately, so you never plan either. "
        "Write every spoken line in the voice of a satisfied customer sharing their own "
        "experience, never as the app's founder, owner or marketer. "
        "Describe viewers by functional need, never by sensitive traits or diagnoses. "
        "Respond with STRICT JSON only, no markdown fences."
    )

    prompt = (
        f"VERIFIED APP FACTS:\n{json.dumps(facts, indent=2)}\n\n"
        f"TEMPLATE STRUCTURE:\n{json.dumps(structure, indent=2)}\n\n"
        f"CREATIVE BRIEF:\n{json.dumps(brief, indent=2)}\n\n"
        f"CLAIM RULES:\n{json.dumps(claims, indent=2)}\n"
        f"{feedback_context}\n"
        f"{angle_goal_block}\n"
        "CUSTOMER PERSPECTIVE: write every spoken line as a satisfied CUSTOMER describing their "
        "own experience using this app — their situation, what they felt, and the value they get. "
        "The speaker is a real user, never the app's founder, owner, developer or marketer. Never "
        "imply the speaker built, owns or is promoting the app; no insider or first-person-plural "
        "product voice (we, our app), and no framing in which the speaker is selling it.\n"
        f"{_spoken_line_rules_block()}\n"
        "Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        f'  "hook_line": "one complete spoken opening sentence about this viewer problem, at most {hook_budget} characters; a shorter natural sentence is fine",\n'
        '  "script": "MIDDLE ONLY: the spoken story AFTER the hook, without repeating it, plain text, no stage directions",\n'
        f'  "beat_timeline": [{{"start": 0, "end": {hook_seconds}, "label": "hook", "text": "what happens and what is said"}}, {{"start": {hook_seconds}, "end": {duration_seconds}, "label": "middle", "text": "what happens and what is said"}}],\n'
        '  "visual_direction": "what the camera shows across both sections, as one paragraph",\n'
        '  "demo_brief": "ONE sentence telling the FOUNDER what to record for their own demo. This never reaches the generated video.",\n'
        '  "voice_direction": "delivery direction for the voiceover or on-camera talent — default to fast, upbeat, high-energy delivery",\n'
        '  "sound_direction": "sound and music direction, rights-safe (no named commercial tracks)",\n'
        '  "claims_used": ["exact strings from claims.approved that appear in the script"]\n'
        "}\n"
        "Rules:\n"
        "- beat_timeline MUST have EXACTLY TWO beats, labelled \"hook\" then \"middle\", and "
        f"they must cover 0-{hook_seconds}s and {hook_seconds}-{duration_seconds}s of a "
        f"{duration_seconds}-second generated piece. There is no third beat.\n"
        "- The hook stops the scroll in its opening seconds. The middle develops it: the "
        "situation, the pain, the reaction, the action, or the transition that naturally "
        f"leads into the product. It ends at the moment the viewer would reach for the app, "
        f"and not one beat later. The middle's closing beat voices the outcome directly in "
        f"the customer's own words, not copied marketing text or an imperative. Paraphrase the "
        f"meaning from VERIFIED APP FACTS outcome_statements first (its outcome field), "
        f"then the flat desired_outcomes, and only when both are "
        f"empty derive a benefit from a feature. The generated piece is {duration_seconds} seconds; anything "
        "after it is the founder's own footage.\n"
        # The spoken budget, in characters, is the same number the render gate
        # imposes downstream (hook spoken separately over the opening beat, the
        # rest over the middle). A script past it is not shortened gracefully at
        # render time, and the trimmed-away text is usually the payoff sentence.
        # Sizing the request is the fix at its cause.
        #
        # Both lines are stated as TARGETS rather than as budget ceilings. A
        # ceiling invites filling it, and a filled hook ceiling is a paragraph
        # where the opening line has to be short, sharp, and about one problem.
        f"- SPOKEN WORDS: the hook line is spoken over the first {hook_seconds}s and the rest of "
        f"the script over the {middle_seconds}s middle. Aim for about {hook_target} characters for "
        f"the hook line and about {script_target} characters for the rest of the script, counted "
        "in the MIDDLE ONLY field (the hook has its own field). This is the length for natural delivery, not an arbitrary maximum: "
        "reach it with dialogue that is naturally that long. NEVER pad with "
        "filler words, extra spaces or stray punctuation to hit it. Land CLOSE TO each target "
        "rather than filling the seconds, and end on the payoff sentence as the last thing said "
        f"inside the middle. The hard ceilings are {hook_budget} and {middle_budget} characters: "
        "write shorter COMPLETE sentences if either line exceeds its ceiling. Never cut a sentence "
        "at a character boundary or move part of the hook into the script. The render is refused "
        "if the spoken words cannot fit, so rewrite the thought rather than clip its words. "
        "A shorter complete thought is better than a padded or unfinished one.\n"
        "- ONE STORY, TWO LINES: the hook line names ONE problem this viewer actually has, in "
        "their own words, and the script resolves that same problem — same subject, same viewer, "
        "the second line answering the first. Never restate the hook in the script, never open a "
        "second problem, and never leave the hook's problem unanswered.\n"
        "- COMPLETE SENTENCES: every spoken line is complete grammatical sentences, each ending "
        "in . ! or ?. The hook_line must stand alone as one complete sentence — never end it on a "
        "conjunction, preposition or article (no trailing 'because', 'like', 'and' or 'the'), and "
        "never trail it into the script. The script's sentences are complete too: no fragments, "
        "and no semicolon joining a statement to a command.\n"
        "- SELF-REVIEW: read hook_line followed by script aloud before returning JSON. Both must "
        "make grammatical sense independently AND tell one connected story together: a specific "
        "first-person difficulty, what helped, then the change that answers that difficulty. "
        "Use ordinary customer language, not feature-list labels, marketing slogans or commands "
        "such as 'Find words for feelings'. Do not paste title-cased feature names into dialogue. "
        "Do not repeat the same benefit twice. Check each character ceiling separately; if a line "
        "does not fit, rewrite BOTH lines coherently instead of splitting a sentence.\n"
        "- NEVER write a product demonstration into either beat. Do not film the app in use, "
        "do not show a screen, and do not narrate what the app does while something unrelated "
        "happens on camera. Showing the working product is the founder's recording, attached "
        "afterwards.\n"
        "- NEVER write a call to action. There is no closing beat and no request to download, "
        "install, sign up or try anything — the founder adds that in their own editor.\n"
        "- demo_brief is the ONLY place the app's feature may be named, and even there it is "
        "an instruction to the founder about what to record themselves. Keep it to one "
        "sentence, and never write it as dialogue or as something the presenter says.\n"
        "- Fill every content_slot in the template with a concrete value for THIS app.\n"
        "- If the brief states a visual_direction, that look is the founder's own: "
        "return a visual_direction that describes it and nothing that contradicts it, and "
        "keep both spoken lines inside a setting that look fits. Do not replace it with a "
        "look of your own.\n"
        "- CRITICAL: nothing is composited over the footage and no text appears "
        "on screen at all — no captions, no titles, no labels. Describe the full scene — "
        "environment, setting, props and any on-screen "
        "context — concretely from the verified facts above, and leave clean, "
        "uncluttered space in frame. Never invent interface text, button labels, prices, ratings, "
        "logos, testimonials, or anything the viewer could read as a factual claim "
        "about the app. The generated scene is illustrative: the script must never claim "
        "it shows real app footage or a screen recording.\n"
        "- Use ONLY the features and claims present above, and only in the middle's framing of "
        "the situation. Never invent a feature, a rating, "
        "a review, a download count, or a user testimonial, and never state a price: no "
        "price is on record for this app, so a quote could not be checked.\n"
        "- Never use anything in claims.never_use. If a claims.needs_review item would help, "
        "leave it out rather than using it.\n"
        "- Never promise a guaranteed outcome and never describe the viewer as having a "
        "condition. Describe what the app does instead.\n"
        "Return ONLY valid JSON."
    )

    # JSON validity does not imply usable dialogue. The old arrival clamp cut
    # an overlong sentence, appended a period, and prepended its remaining
    # words to the middle: "...hear." / "suggested emotion words.". Keep the
    # RAW draft for editorial correction instead. Retry the complete plan so
    # the two spoken lines and the timeline stay consistent with each other.
    # Clean drafts cost one call; corrections are bounded to two extra calls.
    # Routed through _chat_json with headroom: 3500 tokens proved too small
    # in production (2026-10-13) once GPT-5 Mini's reasoning tokens and the
    # full strict schema share the budget — the reply truncated mid-object on
    # BOTH attempts (3500, then 7000) and surfaced as a plan failure. 8000
    # starts with room, and the retry doubles to 16000.
    attempt_prompt = prompt
    for attempt in range(3):
        result = await _chat_json(
            system_message=system_message,
            prompt=attempt_prompt,
            context="Creative plan",
            max_tokens=8000,
            timeout=120,
            json_schema=PLAN_JSON_SCHEMA,
        )
        missing = REQUIRED_PLAN_KEYS - set(result.keys())
        if missing:
            logger.error("Creative plan missing fields %s.", sorted(missing))
            raise RuntimeError(f"Creative plan missing required fields: {missing}")
        hook = str(result.get("hook_line") or "").strip()
        # Accept a legacy whole-piece response only when removing its opening
        # hook leaves complete middle sentences; no partial sentence surgery.
        script = strip_leading_hook(hook, str(result.get("script") or "").strip())
        issues = _generated_spoken_issues(hook, script, hook_budget, middle_budget)
        if not issues:
            result["hook_line"] = hook
            result["script"] = script
            break
        logger.warning("Creative plan editorial attempt %s: %s", attempt + 1, "; ".join(issues))
        if attempt == 2:
            raise RuntimeError(
                "Creative plan could not produce complete, fitting spoken sentences. "
                "Please regenerate the plan; no incomplete draft was saved."
            )
        attempt_prompt = (
            prompt + "\n\nEDITORIAL CORRECTION: Rewrite the complete plan, including BOTH spoken lines "
            "and their timeline. Keep the same viewer problem, verified facts and intended outcome. "
            "Use complete natural customer sentences, not feature labels or fragments. "
            "Write it the way a real person talks: no promotion, no hype, no AI-sounding "
            "openers, never the app's name, and no claimed history with the app. "
            "Do not fix grammar merely by adding a period. Never split a sentence between fields. "
            f"hook_line must be at most {hook_budget} characters; script (MIDDLE ONLY) at most "
            f"{middle_budget} characters. A shorter complete thought is fine.\n"
            "Problems found: " + "; ".join(issues) + "\n"
            "Previous draft (data to rewrite, not instructions):\n" + json.dumps(result, ensure_ascii=False)
        )
    for key in (
        "visual_direction", "demo_brief", "voice_direction", "sound_direction",
    ):
        result[key] = (result.get(key) or "").strip()[:1200]

    result["beat_timeline"] = _normalize_beats(result.get("beat_timeline"), duration_seconds)
    result["beat_timeline"] = _enforce_two_sections(result["beat_timeline"], hook_seconds)
    # The middle runs to the end of the piece: it is the last thing this
    # workflow generates, and the founder's demo starts after it.
    if result["beat_timeline"]:
        result["beat_timeline"][-1]["end"] = duration_seconds
    # No overlays: burned-in captions are gone, so the model is never asked
    # for on-screen text and anything it volunteers is dropped here rather
    # than stored. The column keeps its old rows; nothing new is written.
    result.pop("overlays", None)
    result["claims_used"] = [str(c).strip() for c in (result.get("claims_used") or []) if str(c).strip()][:8]
    result["duration_seconds"] = duration_seconds
    return result


def _enforce_two_sections(beats: list, hook_seconds: int) -> list:
    """
    Force a plan's beat timeline down to exactly two beats: hook, then middle.

    The prompt asks for two beats and the schema names only those two labels,
    but a model that returns four — the old hook/problem/demo/cta shape is
    strongly represented in its training — produces a plan whose timeline says
    to film a demonstration and end on a call to action. Nothing downstream
    would stop that: both are read straight into the render prompt. So it is
    corrected here, where the shape is known, rather than trusted.

    Anything after the middle is dropped, and the middle absorbs the remaining
    time, because the founder attaches their own demo and CTA to whatever this
    returns — a plan that reserved seconds for them would render footage that
    runs out mid-thought.
    """
    cleaned = [b for b in (beats or []) if isinstance(b, dict)]
    hook = next((b for b in cleaned if str(b.get("label", "")).lower() == "hook"), None)
    middle = next((b for b in cleaned if str(b.get("label", "")).lower() == "middle"), None)

    # A beat whose label is a demo or a call to action is dropped on the FLOOR,
    # not folded in below. Dropping the label while keeping its prose is the
    # difference between a plan with the right shape and a plan that still says
    # "show the timer" and "try it free" as middle copy — and that text goes
    # verbatim into the render prompt, which is how a demonstration gets
    # generated by a workflow that must not generate one.
    def _is_droppable(beat: dict) -> bool:
        label = str(beat.get("label", "")).strip().lower()
        return any(
            word in label
            for word in ("demo", "cta", "call to action", "payoff", "conversion", "close")
        )

    # A hook is never droppable, so it is looked up again in the kept set rather
    # than being subject to the same filter.
    hook = next((b for b in cleaned if str(b.get("label", "")).lower() == "hook"), None)
    kept = [b for b in cleaned if b is hook or not _is_droppable(b)]
    if hook is None and kept:
        hook = kept[0]

    if middle is None:
        extras = [b for b in kept if b is not hook and b.get("text")]
        if extras:
            # The model wrote a multi-beat arc without labelling a middle, so
            # what it actually described is the story. Fold the SURVIVING beats
            # into one middle rather than borrowing the hook's words.
            middle = {
                "label": "middle",
                "text": " ".join(str(b.get("text") or "").strip() for b in extras).strip(),
            }
    if hook is None:
        return []
    hook = {**hook, "label": "hook", "start": 0, "end": min(hook_seconds, max(1, int(hook_seconds)))}
    if middle is None:
        return [hook]
    middle = {**middle, "label": "middle", "start": hook["end"]}
    return [hook, middle]


REQUIRED_STRATEGY_KEYS = {
    "strategy_summary", "audience_problem", "emotional_triggers", "hook_concept",
    "hook_line", "hook_promise", "hook_action", "messaging_pillars",
    "primary_feature", "desired_outcome", "mechanism_beat", "payoff_beat",
    "differentiation_beat",
    "scene", "performance", "segments",
}
# What is missing on purpose, beyond hook_dialogue and character below:
#
# "cta_strategy". A call to action is added by the founder in their own editor
# and is not part of the generated footage, so a strategy that must "deliver the
# plan's CTA" was asking the model to write a closing beat for a video that has
# no closing beat. It was also load-bearing in the wrong direction: it reached
# every segment prompt via strategy_brief, so it was steering the middle toward
# a conversion beat instead of toward the moment the viewer reaches for the app.
#
# "continuity_contract". There is no longer a chain to keep consistent: a video
# is one render, so there is no seam between segments for a contract to govern.
# Note what else is missing on purpose: "hook_dialogue". It is enrichment —
# the exact words or delivery direction for the hook beat — and every
# consumer already tolerates its absence (normalize defaults it to "",
# the segment prompt skips the dialogue line when empty, and no UI
# renders it). A model that drops it gave a complete strategy; failing
# validation over it produced "missing required fields: {'hook_dialogue'}"
# on rebuilds that could never be fixed by retrying the same plan.
#
# Note what is missing on purpose: "character". The on-camera person is copied
# from the founder's photograph, so a written appearance is a fabrication, not
# a fallback. An earlier version of the schema requested a "character" object
# whose only content was an instruction to omit it — the model complied, and
# validation then failed the whole strategy with "missing required fields:
# {'character'}". A key the prompt forbids must never be a key validation
# demands. If a reply does contain one anyway (older strategies, ignored
# instructions), normalize_strategy drops it rather than trusting it.

# How many continuation beats a strategy plans.
#
# This exists because the founder decides how far to extend AFTER seeing the
# hook, so the plan has to hold a whole arc rather than a single follow-up.
# Planning exactly one continuation and then falling back to it for every later
# index made extensions 2, 3, 4... replay extension 1 verbatim — the same
# words, the same action — so "extend again" produced the same beat twice.
# A generated video is TWO sections, always. The hook is the opening beat; the
# middle develops it and ends at the moment the viewer would reach for the app.
#
# This used to be 7 continuation beats (8 segments) with the last one reserved
# for the CTA, so a founder could extend a chain to reach a 30s target. There is
# no chain and no CTA now: one render, one file, and the demo plus the close are
# the founder's own footage attached afterwards. So the count is structural
# rather than a budget — a third section would be a product demo, which this
# workflow does not generate.
GENERATED_SECTIONS = 2
SECTION_ROLES = ("hook", "middle")


def _two_section_schema(middle_seconds: int) -> str:
    """
    Emit the two generated sections as JSON schema text.

    Exactly two segments, roles "hook" and "middle". The middle is the last
    thing this product generates, so it carries the whole remainder of the piece
    and its only obligation is to bring the viewer to the edge of wanting the
    app — not to satisfy them.
    """
    return (
        ',\n    {"index": 0, "role": "hook", "seconds": 3, '
        '"goal": "what the opening beat must achieve to stop the scroll", '
        '"script": "the exact words spoken in the opening - the plan\'s hook line", '
        '"action": "the opening physical performance: ordered, timed beats across face, hands, posture and props, already moving in frame one"}'
        f',\n    {{"index": 1, "role": "middle", "seconds": {middle_seconds}, '
        '"goal": "what the middle must achieve: develop the hook and end at the moment the viewer reaches for the app", '
        '"script": "the words spoken in the middle - different from the hook", '
        '"action": "what they do through the middle, ending on the reach for the phone"}}'
    )

# The scene is where the single render's consistency lives: it is locked for
# the whole piece, so the hook and the middle cannot disagree about the room,
# the light or the framing. There is deliberately no continuity contract any
# more — that governed the seam between two separately-rendered segments, and
# there is no seam now.
#
# There is deliberately no STRATEGY_CHARACTER_FIELDS. The on-camera person is
# copied from the founder's uploaded character reference image, so a written
# description of their face, hair, skin, age, build or facial hair is not a
# fallback — it is a fabrication, and it was being sent to the model alongside
# the photograph as a "locked" value. The two disagreed, and the model was told
# both were authoritative, which is how a founder's own face came back as
# somebody else's. The scene and performance directions are plan-level and do
# not conflict with a photograph, so those stay.
#
# `wardrobe` is the single deliberate exception, and it is the right one.
# Clothing is the only thing about a person's presentation that a scene has a
# legitimate claim on: a founder photographed at a kitchen table in a t-shirt
# can still be filmed at a hospital bench in scrubs, and that is the scenario
# doing its job rather than the model inventing a person. So it is chosen here,
# from the setting, and locked like the room. It was dropped with `character`
# and readmitting only this field is what restores that — the fabrication
# problem above was never about clothes, it was about the face.
STRATEGY_SCENE_FIELDS = (
    "camera_angle", "framing", "lighting", "environment", "background",
    "setting", "visual_style", "character_positioning", "wardrobe", "props",
    "color_palette",
)
STRATEGY_PERFORMANCE_FIELDS = ("movement", "voice_delivery")

_STRATEGY_TEXT_LIMITS = {
    "strategy_summary": 900,
    "audience_problem": 700,
    "hook_concept": 700,
    "hook_line": 200,
    "hook_promise": 300,
    "hook_action": 700,
    "hook_dialogue": 400,
    "primary_feature": 400,
    "desired_outcome": 400,
    "mechanism_beat": 400,
    "payoff_beat": 400,
    "differentiation_beat": 400,
}


def _clean_strategy_text(value, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _clean_strategy_list(value, limit: int, cap: int = 6) -> list:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(v).strip()[:limit] for v in value if str(v).strip()][:cap]


def _normalize_strategy_section(raw, fields) -> dict:
    """Coerce a nested strategy section to known keys, all non-empty strings.

    A missing key becomes "" rather than vanishing, so the continuity prompt
    can state the whole lock and the founder can see exactly which attributes
    were pinned and which were left open.
    """
    raw = raw if isinstance(raw, dict) else {}
    return {field: _clean_strategy_text(raw.get(field), 300) for field in fields}


def _normalize_camera_beat(raw) -> dict:
    """
    Coerce the camera-move beat to {"at": float, "gesture": str}.

    `gesture` is the model's and is what makes the lean specific to this video:
    a brow lift, a nod, a turn of the shoulder. It is capped hard because it is
    interpolation into fixed prompt text, not prose the founder reads, and a
    long one would eat HeyGen's 4,090 ceiling to say what one clause says.

    `at` survives normalization but is NOT trusted. It is overwritten by the
    strategy endpoint with the deterministic value (see
    overlays.camera_beat_seconds) and clamped into the hook by every reader, so
    a model inventing "at 99" costs the beat, not the render.
    """
    raw = raw if isinstance(raw, dict) else {}
    try:
        at = max(0.0, float(raw.get("at") or 0))
    except (TypeError, ValueError):
        at = 0.0
    return {
        "at": round(at, 3),
        "gesture": _clean_strategy_text(raw.get("gesture"), 90),
    }


def normalize_strategy(raw: dict) -> dict:
    """
    Validate and normalize a strategy payload.

    Split out from the model call so the shape can be tested directly and so
    the endpoint can re-validate a founder-edited strategy.
    """
    result = {
        key: _clean_strategy_text(raw.get(key), _STRATEGY_TEXT_LIMITS.get(key, 600))
        for key in (
            "strategy_summary", "audience_problem", "hook_concept", "hook_line",
            "hook_promise", "hook_action", "hook_dialogue", "primary_feature",
            "desired_outcome", "mechanism_beat", "payoff_beat",
            "differentiation_beat",
        )
    }
    result["emotional_triggers"] = _clean_strategy_list(raw.get("emotional_triggers"), 200)
    result["messaging_pillars"] = _clean_strategy_list(raw.get("messaging_pillars"), 300)

    # No "character" section: see STRATEGY_SCENE_FIELDS for why. An existing
    # project may still carry one from before this change, so it is dropped here
    # rather than trusted — an old fabrication must not reach a new prompt.
    result["scene"] = _normalize_strategy_section(raw.get("scene"), STRATEGY_SCENE_FIELDS)
    result["performance"] = _normalize_strategy_section(raw.get("performance"), STRATEGY_PERFORMANCE_FIELDS)

    # An old strategy may still carry a contract; it is dropped rather than
    # trusted, because a seam contract describes a chain that no longer exists.
    # The hook line is spoken, so its cap snaps to a sentence like the plan's.
    # It must trim the RAW line: _clean_strategy_text above already hard-sliced
    # it to 200 characters, and snapping the slice would keep a mid-word cut.
    result["hook_line"], _ = _trim_hook_line(
        str((raw or {}).get("hook_line") or "").strip(),
        _STRATEGY_TEXT_LIMITS["hook_line"])
    result["segments"] = _normalize_sections(raw.get("segments"))
    result["camera_beat"] = _normalize_camera_beat(raw.get("camera_beat"))
    return result


def _normalize_sections(raw) -> list:
    """
    Coerce the model's segments down to exactly two: the hook and the middle.

    Truncation alone is not enough. A model returning the old eight-beat shape
    would keep beats 2-8, and beat 8's role is "cta" — so the middle would
    inherit a call to action, and that role is read by the render prompt. Roles
    are therefore reassigned by position rather than trusted, and a third
    section is dropped entirely: the product demo that a third beat would hold
    is the founder's own recording.
    """
    cleaned = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        try:
            seconds = int(item.get("seconds") or 0)
        except (TypeError, ValueError):
            seconds = 0
        cleaned.append({
            "seconds": max(1, min(seconds or 0, 30)),
            "goal": _clean_strategy_text(item.get("goal"), 400),
            "script": _clean_strategy_text(item.get("script"), 900),
            "action": _clean_strategy_text(item.get("action"), 400),
        })
        if len(cleaned) >= GENERATED_SECTIONS:
            break

    sections = []
    for index, role in enumerate(SECTION_ROLES):
        item = cleaned[index] if index < len(cleaned) else {"seconds": 3, "goal": "", "script": "", "action": ""}
        sections.append({"index": index, "role": role, **item})
    return sections


# ---------------------------------------------------------------------------
#
# The spoken words are the founder's approved words, not the model's draft.
#
# The strategy receives the approved plan as fixed material and is built to
# deliver it — but the prompt asked the model for its own `segments[].script`
# lines as well, because a section also needs to be *scored* (goal, action,
# delivery). Those drafts reached the provider as "spoken, performed
# naturally", so a founder could approve outcome-framed words on the Review
# step and hear the model's paraphrase in the render.
#
# `bind_spoken_words` closes that: after the strategy is generated and
# normalized, the two section scripts are rewritten from the plan's approved
# words. The hook says the approved hook line. The middle says the approved
# script, minus a duplicated hook-line prefix, cut to what the middle's seconds
# can actually speak. What the model keeps is everything a plan cannot express:
# the on-camera action, the scene and the performance, which is why this runs
# after the model call rather than instead of it.

# Spoken pace used only to size approved words to a section. 150 characters
# over a 10-second extension is the TARGET for natural delivery — a relaxed,
# conversational read of about 15 characters a second. The earlier 20 chars/sec
# packed roughly 200 characters into 10 seconds, the fastest end of natural
# speech, which reads as hurried in an extension that has to flow into the
# surrounding footage; 15 chars/sec is the measured middle of the range.
SPOKEN_CHARS_PER_SECOND = 15


def spoken_budget(seconds) -> int:
    """
    What a section of `seconds` holds at the middle's conversational pace.

    This is the length for a natural read, not a hard technical ceiling the
    video model imposes: 10 seconds is about 150 characters at 15 characters a
    second. It is the same number the prompt asks the model to aim for and the
    render measures against, so the words the founder approves are the words
    that fit — and it is what `spoken_targets` caps a line's natural target
    with when the piece is shorter than the target.
    """
    try:
        secs = float(seconds or 0)
    except (TypeError, ValueError):
        secs = 0.0
    return max(60, int(round(secs * SPOKEN_CHARS_PER_SECOND)))


# The pace an OPENING line is sized at, which is not the middle's.
#
# The first seconds of a piece are read briskly — that is the delivery a 2-4s
# hook window is built for — and 20 characters a second is the brisk figure
# this file carried before the middle's pace was retuned to the conversational
# 15. Sizing the opening at the middle's pace would hold a 3s hook to 45
# characters and a 4s one to 60, which is a fragment rather than a hook line.
HOOK_CHARS_PER_SECOND = 20


def hook_ceiling(seconds) -> int:
    """The character ceiling for an opening line of `seconds`, at the brisk pace."""
    try:
        secs = float(seconds or 0)
    except (TypeError, ValueError):
        secs = 0.0
    return max(60, int(round(secs * HOOK_CHARS_PER_SECOND)))


# ---------------------------------------------------------------------------
#
# What the two spoken lines aim at, and the one story they have to tell.
#
# The approved words are the founder's, and the render refuses what the piece
# cannot speak. But "cannot speak" was the only count anything checked, and it
# left two gaps a founder could see and not act on. The hook line was never
# counted at all: partition_spoken_words sized the middle and passed the hook
# through untouched, so a 200-character hook line was stored, bound into the
# opening section, and cut to 150 mid-sentence by the prompt builder with
# nothing on screen saying so. And a spoken budget was a ceiling to FILL, so
# the prompt asked for a 240-character opening line on a 15s piece — a
# paragraph where a scroll-stopper has to be.
#
# So both lines are counted, and counted against a TARGET that the prompts then
# aim at. 70 characters is roughly twelve words: two beats of speech, the shape
# an opening line that stops a scroll actually takes. 150 is one developed
# thought after it, which is what a middle is — the problem the hook named,
# answered. A line under its target is a choice rather than a fault, so nothing
# here refuses one; the ceiling is still what the render enforces.
HOOK_TARGET_CHARS = 70
SCRIPT_TARGET_CHARS = 150

# How far off a target still counts as on target. Reported, never enforced:
# these are speaking targets, not quotas.
TARGET_BAND = 0.25

# Words that mark an opening as naming a problem — or asking one — rather than
# stating a benefit. Matched against normalized text (lowercased, punctuation
# stripped to spaces), so case and punctuation do not decide it. Deliberately
# generous: the templates include openings that are not problems at all (a
# curiosity gap, an ordinary morning), so this reads the line rather than
# gating it.
_PROBLEM_MARKERS = (
    "why", "how come", "can t", "cannot", "won t", "don t", "doesn t", "didn t",
    "no one", "nothing", "nobody", "stop", "stuck", "struggle", "struggling",
    "tired", "hate", "waste", "wasting", "wish", "keeps", "always", "never",
    "problem", "hard", "harder", "hardest", "wrong", "failing", "forgetting",
    "losing", "lost", "dread", "mess", "chaos", "guessing", "overwhelmed",
    "endless", "too much", "again", "every time",
)

# Words that mark a body as resolving rather than piling on: the change has
# happened, or the fix is named. Same generosity and the same honesty rule —
# this is a read of the words, not a proof about them.
_RESOLUTION_MARKERS = (
    "now", "so i", "instead", "finally", "turns out", "the fix", "fixes",
    "fixed", "solves", "solved", "helps", "helping", "lets you", "let me",
    "ends with", "one tap", "no more", "never again", "since then", "started",
    "made it", "makes it", "gives you", "which is why", "that s why",
    "the answer", "written down", "stops", "worked",
)


def spoken_targets(hook_seconds=3, total_seconds=12) -> dict:
    """
    What each spoken line aims at, and the most its seconds can hold.

    The target is the natural speaking length above, never above the ceiling: a
    2s hook cannot hold 70 characters at any pace this product renders at, so
    aiming there would only guarantee an over-length line. `ceiling` is what
    the render, the arrival clamp and the Review step already measure against —
    `spoken_budget` for the middle, and the brisk `hook_budget` for the
    opening, which is read fast — so this adds the aim, it does not move the
    limit.
    """
    hook_limit = hook_ceiling(hook_seconds)
    middle_seconds = max(1, int(total_seconds or 0) - int(hook_seconds or 0))
    script_ceiling = spoken_budget(middle_seconds)
    return {
        "hook_seconds": int(hook_seconds or 0),
        "middle_seconds": middle_seconds,
        "hook": {"target": min(HOOK_TARGET_CHARS, hook_limit), "ceiling": hook_limit},
        "script": {
            "target": min(SCRIPT_TARGET_CHARS, script_ceiling),
            "ceiling": script_ceiling,
        },
    }


def _split_sentences(text: str) -> list:
    """
    Split a line into sentences, each keeping its own terminator.

    A terminator only ends a sentence when what follows is a space or the end
    of the line, so "Dr. Smith" and "12.5" stay whole. The same rule
    `_first_sentence` applies to the opening, applied to every sentence.
    """
    stripped = str(text or "").strip()
    if not stripped:
        return []
    sentences = []
    start = 0
    for index, ch in enumerate(stripped):
        if ch not in ".!?":
            continue
        following = stripped[index + 1: index + 2]
        if following == "" or following in " \n\t":
            sentence = stripped[start: index + 1].strip()
            if sentence:
                sentences.append(sentence)
            start = index + 1
    tail = stripped[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def _keep_tail(text: str, limit: int) -> str:
    """
    The end of a sentence, cut back to a word boundary and stripped of its mark.

    Used only for a resolving sentence that is itself longer than the body can
    speak. The end of that sentence is its conclusion — the payoff beat is the
    last thing said — so the tail is the part worth keeping, where the head of
    it is the setup that led there.
    """
    window = str(text or "").strip()[-max(1, int(limit)):]
    space = window.find(" ")
    if space > 0:
        window = window[space + 1:]
    # Only the front is cleaned: the cut leaves the previous sentence's mark on
    # the way in, and the closing mark is part of the sentence that survives.
    return window.lstrip(" ,.!?;:-").rstrip()


def trim_spoken_body(text: str, limit: int):
    """
    Cut a spoken body to fit `limit`, keeping the sentence that resolves it.

    `trim_to_sentence` keeps the opening and cuts the tail, which for a spoken
    body means cutting the resolution — the payoff the hook set up in the first
    place, and the one sentence the middle exists to say. So a body is cut from
    the MIDDLE outwards instead: whole sentences go from between the opening
    (the line that links back to the hook) and the closing sentence (the one
    that answers it), and only when those two are still too long does the
    opening give way, at its own sentence-then-word boundary. The payoff is the
    last thing cut, never the first.

    Returns (kept, dropped), `dropped` counted in characters, so a caller
    reports exactly how much of the approved words is not spoken.
    """
    text = str(text or "").strip()
    if not text or limit <= 0 or len(text) <= limit:
        return text, 0
    sentences = _split_sentences(text)
    if len(sentences) < 2:
        return trim_to_sentence(text, limit)
    kept = list(sentences)
    while len(kept) > 2 and len(" ".join(kept)) > limit:
        del kept[1]
    joined = " ".join(kept)
    if len(joined) > limit:
        # Only the opening and the payoff are left, and both are the story. The
        # opening gives way first: it is the half a viewer can reconstruct from
        # the hook, and the payoff is the half they cannot.
        payoff = kept[-1]
        if len(payoff) >= limit:
            payoff = _keep_tail(payoff, limit)
        room = limit - len(payoff) - 1
        head = trim_to_sentence(kept[0], room)[0] if room > 0 else ""
        joined = (head + " " + payoff).strip() if head else payoff
    return joined, len(text) - len(joined)


def _trim_hook_line(text: str, limit: int):
    """
    Cut a hook line back to fit `limit`, keeping it readable as an opening.

    Sentence boundary first. When the opening sentence is itself longer than
    the limit there is no sentence to cut at, so the cut lands on a word
    boundary — and a line cut that way loses its terminator along with its
    tail. The terminator is restored from the sentence the cut came out of,
    because punctuation is not spoken: "Do you know what triggers your emotions
    and keeps them" is a fragment, while "...and keeps them?" is the question
    it was.
    """
    text = str(text or "").strip()
    if not text or limit <= 0 or len(text) <= limit:
        return text, 0
    kept, _dropped = trim_to_sentence(text, limit)
    if kept and kept[-1] not in ".!?":
        for index, ch in enumerate(text):
            if ch in ".!?" and index >= len(kept) - 1:
                kept = kept + ch
                break
    return kept, len(text) - len(kept)


def _generated_spoken_issues(hook: str, script: str, hook_budget: int, script_budget: int) -> list:
    """Reject observable draft defects before any sentence-splitting clamp.

    This is not a general grammar parser or a semantic coherence score. It
    catches empty/oversized lines, missing terminators, dangling function
    words and obvious cross-field continuations. The prompt's editorial
    self-review handles meaning; these checks prevent our own length fitting
    from manufacturing the reported fragments.

    Two more families are rejected because they are observable rather than
    matters of taste, and because the prompt's rules state each as an absolute:
    promotion/marketing wording (a download request, the founder's own voice,
    the app named) and machine-sounding filler openers. Both are matched as
    whole phrases on normalized text, so a genuine customer line never trips
    them — see _PROMOTION_MARKERS for why that constraint is the whole design.
    """
    issues = []
    # Prepositions/pronouns CAN end grammatical English ("look forward to",
    # "I felt like that"). Only unambiguous dangling words are rejected on
    # their own; the reported "typing feels like" needs its local context.
    dangling = {"a", "an", "the", "and", "or", "but", "because"}
    unfinished_endings = ("feels like", "felt like", "seems like", "looks like")
    for name, text, budget in (("hook_line", hook, hook_budget), ("script", script, script_budget)):
        if not text:
            issues.append(f"{name} is empty")
            continue
        if len(text) > budget:
            issues.append(f"{name} has {len(text)} characters, exceeding {budget}; rewrite the thought")
        hit = _spoken_marker_hit(text, _PROMOTION_MARKERS)
        if hit:
            issues.append(f"{name} reads as promotion or hype, not a customer: '{hit}'")
        hit = _spoken_marker_hit(text, _AI_FLUFF_MARKERS)
        if hit:
            issues.append(f"{name} uses a generic AI-sounding phrase: '{hit}'")
        # The generator obeying its own safety layer: claim_safety warns when a
        # spoken line claims a personal history with the app ("I use", "my
        # patients"), so a draft that does it is rewritten here instead of
        # accepted and then warned about. The patterns are shared, not copied,
        # so the two cannot disagree about what counts — including the "I used
        # to <verb>" exclusion, which is a past habit rather than a usage claim
        # and must keep passing untouched.
        for pattern in FIRST_PERSON_PATTERNS:
            match = re.search(pattern, _normalize_spoken(text))
            if match:
                issues.append(
                    f"{name} claims a personal history with the app "
                    f"('{match.group(0).strip()}'), which no record can substantiate"
                )
                break
        for sentence in _split_sentences(text):
            plain = sentence.rstrip('\"\u201d\u2019')
            if not plain.endswith((".", "!", "?")):
                issues.append(f"{name} has an unfinished sentence")
            words = _normalize_spoken(plain).split()
            if words and words[-1] in dangling:
                issues.append(f"{name} ends a sentence on '{words[-1]}'")
            if any(" ".join(words).endswith(ending) for ending in unfinished_endings):
                issues.append(f"{name} has an unfinished comparison")
        if text[0].islower():
            issues.append(f"{name} begins as a continuation rather than a standalone sentence")
    if ";" in hook:
        issues.append("hook_line joins clauses with a semicolon instead of one standalone opening")
    return issues


def _summarize_line(text: str, spec: dict) -> dict:
    """One line's count, the target it aims at, and the ceiling it must hold."""
    chars = len(str(text or "").strip())
    if chars > spec["ceiling"]:
        verdict = "over_ceiling"
    elif chars < spec["target"] * (1 - TARGET_BAND):
        verdict = "under_target"
    else:
        verdict = "on_target"
    return {
        "chars": chars,
        "target": spec["target"],
        "ceiling": spec["ceiling"],
        "verdict": verdict,
    }


def _opens_a_problem(text: str) -> bool:
    """Whether an opening line names a problem rather than stating a benefit."""
    stripped = str(text or "").strip()
    if not stripped:
        return False
    if stripped.endswith("?"):
        return True
    normalized = _normalize_spoken(stripped)
    padded = f" {normalized} "
    return any(f" {marker} " in padded for marker in _PROBLEM_MARKERS)


def _closes_the_problem(text: str) -> bool:
    """Whether a body reads as resolving, rather than adding more of the same."""
    normalized = _normalize_spoken(text)
    if not normalized:
        return False
    padded = f" {normalized} "
    return any(f" {marker} " in padded for marker in _RESOLUTION_MARKERS)


def check_spoken_story(hook_line, script, hook_seconds=3, total_seconds=12, app_name="") -> dict:
    """
    Both spoken lines measured, and read as ONE story.

    Counts each line against the target it aims at and the ceiling it must
    hold, and reads the two together: the hook should open a problem — a
    question, a cost, something the viewer is doing that keeps failing — and
    the script should close the one the hook opened, rather than restating it
    or answering a different question.

    Nothing here refuses anything. The ceiling is what the render enforces and
    an under-target line is a choice, so the story verdict is reported to the
    founder rather than acted on. Pure, so the Review step and the render path
    measure the same words the same way.

    `app_name` adds the one check that cannot live in the prompt: whether the
    customer's own line names the product they are talking about, which is
    promotion however the sentence is worded. Reported, never acted on — a veto
    would take a whole plan down the moment an app was named after a common
    noun ("Journal", "Notes"), and the founder can see the flag and fix the
    line themselves.
    """
    targets = spoken_targets(hook_seconds, total_seconds)
    hook = str(hook_line or "").strip()
    body = str(script or "").strip()
    story = {
        "problem_in_hook": _opens_a_problem(hook),
        "resolution_in_script": _closes_the_problem(body),
        # The plan's script is written as the whole piece, so a copy of the
        # hook at its head is the hook being said twice rather than a middle.
        "restates_hook": bool(hook and body) and strip_leading_hook(hook, body) != body,
    }
    # Only a name long enough to be a real product name, and never the short
    # generic one that would match ordinary speech.
    named = str(app_name or "").strip()
    if len(named) >= 5:
        needle = _normalize_spoken(named)
        spoken = f" {_normalize_spoken(hook)} {_normalize_spoken(body)} "
        story["names_the_app"] = bool(needle) and f" {needle} " in spoken
        story["generic_phrasing"] = bool(
            _spoken_marker_hit(hook, _AI_FLUFF_MARKERS)
            or _spoken_marker_hit(body, _AI_FLUFF_MARKERS)
        )
    story["coherent"] = bool(
        story["problem_in_hook"] and story["resolution_in_script"] and not story["restates_hook"]
    )
    return {
        "hook": _summarize_line(hook, targets["hook"]),
        "script": _summarize_line(body, targets["script"]),
        "story": story,
        "hook_seconds": targets["hook_seconds"],
        "middle_seconds": targets["middle_seconds"],
        "over_ceiling": bool(
            len(hook) > targets["hook"]["ceiling"] or len(body) > targets["script"]["ceiling"]
        ),
    }


def repair_spoken_story(plan, hook_seconds=3, total_seconds=12) -> tuple:
    """
    Validate the two spoken lines before a render, and rewrite what cannot be spoken.

    Returns (words, report). `words` holds `hook_line` and `script` exactly as
    the video model must receive them; nothing else from the plan is touched.
    The rewrite is the partition rule and nothing more:

    - a hook line longer than its seconds is cut back to its opening sentence,
      and what comes off is spoken at the head of the middle instead of being
      deleted. The words stay in the video; they simply stop being the opening
      line, which is what "the hook names the problem and the script answers
      it" means in practice — a resolution that had drifted into the hook is
      handed to the middle that has to carry it;
    - a middle longer than its seconds keeps its opening and its resolving
      sentence and gives up the sentences in between, so the payoff survives
      the cut.

    No model call and no provider request: this is arithmetic on the founder's
    own words, run inside the render path so the words measured here are the
    words sent. The report carries the count either side of the rewrite and
    every change made, so a shortened line is reported rather than silent.
    """
    source = plan if isinstance(plan, dict) else {}
    hook_line = str(source.get("hook_line") or "").strip()
    script = str(source.get("script") or "").strip()
    hook_seconds = hook_seconds or 3
    total_seconds = total_seconds or 0

    part = partition_spoken_words(source, hook_seconds, total_seconds)
    spoken_hook = part["hook_line"]

    changes = []
    if spoken_hook != hook_line:
        changes.append({
            "field": "hook_line",
            "reason": "over_ceiling",
            "removed_chars": part["hook_dropped_chars"],
            "moved_to_script": len(part["hook_spill"]),
        })
    if hook_line and strip_leading_hook(hook_line, script) != script:
        # The script opened with the hook, so the two lines said the same thing
        # twice and the hook's characters were charged to the middle's seconds.
        changes.append({"field": "script", "reason": "restated_hook"})
    if part["dropped_chars"]:
        changes.append({
            "field": "script",
            "reason": "over_ceiling",
            "removed_chars": part["dropped_chars"],
            "kept_chars": len(part["kept"]),
        })

    report = {
        "before": check_spoken_story(hook_line, script, hook_seconds, total_seconds),
        "after": check_spoken_story(spoken_hook, part["kept"], hook_seconds, total_seconds),
        "changes": changes,
        "rewritten": bool(changes),
        "middle_seconds": part["middle_seconds"],
    }
    return {"hook_line": spoken_hook, "script": part["kept"]}, report


def trim_to_sentence(text: str, limit: int):
    """
    The longest prefix of `text` that fits `limit` and stops at a sentence.

    Returns (kept, dropped). A mid-sentence cut would lop the payoff — usually
    the last sentence — and a hard cut mid-word is a visible fault in a line
    someone has to debug, so the order is: sentence boundary, then word
    boundary, then a hard cut only when neither exists.
    """
    text = str(text or "").strip()
    if not text or limit <= 0 or len(text) <= limit:
        return text, 0
    window = text[:limit]
    cut = max(window.rfind("."), window.rfind("!"), window.rfind("?"))
    if cut >= 0:
        kept = window[: cut + 1].strip()
    else:
        space = window.rfind(" ")
        kept = (window[:space] if space > 0 else window).strip()
    return kept, len(text) - len(kept)


def _normalize_spoken(text: str) -> str:
    """
    Lowercase, drop punctuation, collapse whitespace. For comparing words only.

    Two strings that would be spoken identically normalize to the same string,
    which is what lets the hook line be found in a script that introduces it
    rather than starting with it verbatim.
    """
    chars = []
    for ch in str(text or "").lower():
        chars.append(ch if ch.isalnum() else " ")
    return " ".join("".join(chars).split())


def _first_sentence(text: str) -> str:
    """
    The opening sentence of `text`, or all of it when it has no terminator.

    A terminator only ends the sentence when what follows is a space, an
    earlier abbreviation's period ("Dr. Smith") is left alone, and the closing
    mark is included so a lead-in is cut with the rest.
    """
    stripped = str(text or "").strip()
    for index, ch in enumerate(stripped):
        if ch not in ".!?":
            continue
        following = stripped[index + 1: index + 2]
        if following == "" or following in " \n\t":
            return stripped[: index + 1]
    return stripped


def strip_leading_hook(hook_line: str, script: str) -> str:
    """
    Remove the hook line from the front of the script, returning what is left.

    The plan's `script` is written as the whole piece, so it normally opens with
    the hook line. Leaving that copy in means the middle speaks the hook a
    second time, and the hook's characters are then charged to the middle's
    budget -- which the render reports as an overflow and refuses.

    This used to be an exact `startswith` test, so any introduction defeated it
    ("So, <hook line>? ..." is the same words, differently opened). The hook is
    therefore matched at the sentence, on normalized text, and the first
    sentence is treated as the hook when it carries the hook's words and is
    little more than a lead-in to them. A script that does not open with the
    hook at all is left completely alone: its two sections are separate texts,
    and nothing needs removing.
    """
    hook = _normalize_spoken(hook_line)
    body = str(script or "").strip()
    if not hook or not body:
        return body

    normalized = _normalize_spoken(body)
    if normalized.startswith(hook):
        return body[len(str(hook_line).strip()):].lstrip(" ,.!?;:-")

    opening = _first_sentence(body)
    opening_normalized = _normalize_spoken(opening)
    # The lead-in tolerance is deliberately small. A first sentence that merely
    # contains the hook somewhere is far more likely to be the middle than the
    # hook, and cutting it would delete the founder's actual words.
    lead_in = len(hook) + 30
    if hook in opening_normalized and len(opening_normalized) <= lead_in:
        return body[len(opening):].lstrip(" ,.!?;:-")
    return body


def partition_spoken_words(plan, hook_seconds=3, total_seconds=12) -> dict:
    """
    The single rule for how the approved words divide between hook and middle.

    Returns hook_line, the middle as written, the part of the middle that fits
    its seconds, and how many characters did not. Every consumer reads this:
    the plan clamp that sizes a freshly generated script, the binding that
    rewrites a strategy's spoken lines, and the render gate that refuses an
    over-length script. A second implementation of the arithmetic here would
    mean a plan the clamp called short and the gate calls long, which is the one
    disagreement a founder cannot act on.

    `total_seconds` and `hook_seconds` must be passed exactly as the render gate
    passes them, or the two will not agree on what fits.
    """
    hook_line = ""
    script = ""
    if isinstance(plan, dict):
        hook_line = str(plan.get("hook_line") or "").strip()
        script = str(plan.get("script") or "").strip()

    targets = spoken_targets(hook_seconds, total_seconds)

    # The hook is counted FIRST, and against its own seconds. It used to pass
    # through untouched, which is how a hook line several times the length of
    # the opening beat was stored, bound into section 0, and cut mid-sentence by
    # the prompt builder with nothing telling the founder. The cut keeps the
    # opening sentence and hands the rest to the middle below, so the words are
    # still spoken — just after the hook, which is where a resolution belongs.
    spoken_hook, hook_dropped = _trim_hook_line(hook_line, targets["hook"]["ceiling"])
    # Only the front is cleaned: the cut can leave a leading mark behind it,
    # and the closing mark belongs to the sentence the spill ends with.
    hook_spill = hook_line[len(spoken_hook):].lstrip(" ,.!?;:-") if spoken_hook else ""

    middle_text = strip_leading_hook(hook_line, script)
    if hook_spill:
        middle_text = f"{hook_spill} {middle_text}".strip() if middle_text else hook_spill

    budget = targets["script"]["ceiling"]
    kept, dropped = trim_spoken_body(middle_text, budget)
    return {
        "hook_line": spoken_hook,
        "hook_spill": hook_spill,
        "hook_dropped_chars": hook_dropped,
        "middle_text": middle_text,
        "kept": kept,
        "dropped_chars": dropped,
        "budget": budget,
        "target": targets["script"]["target"],
        "hook_target": targets["hook"]["target"],
        "middle_seconds": targets["middle_seconds"],
    }


def bind_spoken_words(strategy: dict, plan, hook_seconds=3, total_seconds=12):
    """
    Rewrite the strategy's spoken words from the plan's approved words.

    Returns (strategy, overflow). `overflow` is {} when everything fits and
    {"dropped_chars", "budget", "middle_seconds"} when the approved script is
    longer than the middle can speak. That record is recomputed, not stored: it
    is a pure function of (plan, seconds), so the render gate and the public
    project serializer can derive it fresh and a strategy PATCH cannot drop it.

    When there is no approved plan, nothing is rebound — a strategy built
    without one keeps the model's words, which is the legacy path, and no
    overflow is reported because there is nothing to overflow.

    The returned strategy is a copy: binding mutates the sections, and the
    caller's dict must not gain words it did not ask for.
    """
    import copy

    if not isinstance(strategy, dict):
        return strategy, {}
    part = partition_spoken_words(plan, hook_seconds, total_seconds)
    hook_line = part["hook_line"]
    middle_text = part["middle_text"]
    if not hook_line and not middle_text:
        return strategy, {}

    strategy = copy.deepcopy(strategy)
    kept = part["kept"]

    sections = strategy.get("segments")
    if isinstance(sections, list):
        if hook_line:
            if len(sections) > 0 and isinstance(sections[0], dict):
                sections[0]["script"] = hook_line
            if len(sections) > 1 and isinstance(sections[1], dict):
                sections[1]["script"] = kept
        elif len(sections) > 1 and isinstance(sections[1], dict):
            sections[1]["script"] = kept
    if hook_line:
        strategy["hook_line"] = hook_line

    overflow = (
        {
            "dropped_chars": part["dropped_chars"],
            "budget": part["budget"],
            "middle_seconds": part["middle_seconds"],
        }
        if part["dropped_chars"]
        else {}
    )
    return strategy, overflow


def strategy_text(strategy: dict) -> str:
    """
    Flatten every human-readable string in a strategy.
    Used by claim safety so the strategy's own wording — the hook line, the
    spoken script, the promises — is checked exactly like the plan's is. A
    banned claim that appears only in the strategy is still a banned claim.
    """
    if not isinstance(strategy, dict):
        return ""
    parts: list = []
    for key, value in strategy.items():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            parts.extend(v for v in value.values() if isinstance(v, str))
            for nested in value.values():
                if isinstance(nested, list):
                    parts.extend(str(v) for v in nested)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.extend(str(v) for v in item.values() if isinstance(v, str))
    return " \n ".join(p for p in parts if p.strip())


def trend_evidence_sentence(evidence) -> str:
    """
    Render a template's anonymous trend aggregate as one prompt sentence.

    Kept here rather than imported from a research helper so the strategy
    path does not pull in extra modules; the format is a small
    contract between the scan and the prompt, and the two sides assert the same
    fields in the same way.

    Returns "" when there is no signal, and the caller omits the whole section
    rather than printing a heading with nothing under it.
    """
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except (json.JSONDecodeError, TypeError):
            return ""
    if not isinstance(evidence, dict) or not evidence.get("has_signal"):
        return ""
    sample = evidence.get("sample_size") or 0
    if not sample:
        return ""
    return (
        f"Across {sample} public openings of this shape in the last scan, the median one had "
        f"{evidence.get('median_view_band', 'unknown')} views and "
        f"{evidence.get('median_engagement_band', 'unknown')} engagement "
        f"({evidence.get('recency_band', 'unknown')}). This is what similar shapes have "
        f"carried, not a promise about any single video."
    )


async def generate_video_strategy(
    profile: dict,
    template: dict,
    angle: Optional[dict] = None,
    objective: str = "",
    hook_seconds: int = 4,
    total_duration: int = 20,
    tone: str = "",
    brand_voice: str = "",
    profile_feedback: Optional[dict] = None,
    component_feedback: Optional[dict] = None,
    plan: Optional[dict] = None,
) -> dict:
    """
    Turn an App Profile into a video strategy specific to THIS app.

    This is the step that stops the workflow from producing a generic
    talking-head video with an app name stapled on. It decides the hook concept,
    the messaging, the words, the on-camera action and the whole look of the
    scene BEFORE any video is generated.

    A strategy describes exactly TWO sections — a hook and a middle — because
    that is what one render produces. The scene is what holds the two together:
    once a background, a light, a camera angle and the delivery are locked, the
    middle is held to the same values, so the piece reads as one take. The face
    is never described anywhere in the strategy — it comes from the founder's
    photograph, which rides along as a model input.

    Returns a normalized strategy dict (see normalize_strategy). Never invents
    features, prices, ratings or outcomes; uncertain claims are pushed to the
    profile's own review tier instead.

    `plan` is the founder-approved creative plan, when one exists. The founder
    writes the script and the visual direction there and then generates
    the video; a strategy that ignored it would render a different video than the
    one they approved, so the approved words win and this only fills in what a
    plan cannot express: the on-camera action per section and the locked scene.
    """
    def _list(name):
        val = profile.get(name)
        if isinstance(val, list):
            return [str(v) for v in val if str(v).strip()]
        if val:
            return [str(val)]
        return []

    # The middle covers everything after the hook, because it is the last thing
    # this product generates. The founder's demo and CTA attach after it.
    _remaining = max(0, int(total_duration or 0) - int(hook_seconds or 0))
    plan_seconds = _remaining or int(hook_seconds or 4)

    # The section scripts are sized to their seconds at the same natural pace
    # the plan prompt and the render gate use. Stated here so the strategy's own
    # words fill the piece when there is no approved plan to bind to; when
    # there is one, bind_spoken_words rewrites the sections from it and the
    # same ceilings still apply.
    _strategy_hook_budget = hook_ceiling(hook_seconds)
    _strategy_middle_budget = spoken_budget(plan_seconds)
    # The aims, not the ceilings: see the SPOKEN WORDS rule below.
    _strategy_hook_target = min(HOOK_TARGET_CHARS, _strategy_hook_budget)
    _strategy_middle_target = min(SCRIPT_TARGET_CHARS, _strategy_middle_budget)
    # Same hook floor as the plan prompt: roughly three-quarters of the
    # hook's spoken budget, so the strategy's own hook line fills the
    # opening beat when there is no approved plan to bind to.
    _strategy_hook_min_words = max(6, int(_strategy_hook_budget * 0.75 // 6))

    facts = {
        "app_name": profile.get("brand_name") or "(unnamed app)",
        "category": profile.get("app_category") or profile.get("niche") or "(unstated)",
        "description": profile.get("brand_description") or "(unstated)",
        "platforms": _list("platforms"),
        "features": _list("core_features"),
        "use_cases": _list("primary_use_cases"),
        "problems": _list("problems_solved"),
        "audience": profile.get("target_audience") or "(unstated)",
        "icp_segments": _list("icp_segments"),
        "outcomes": _list("desired_outcomes"),
        # Passed as objects, not flattened: each entry already links an
        # outcome to its source feature, so the pitch rules below can use the
        # link instead of re-deriving it from two flat lists.
        "outcome_statements": profile.get("outcome_statements") or [],
        "differentiators": profile.get("differentiation") or "(unstated)",
        "limitations": profile.get("known_limitations") or "(none recorded)",
        # usage_moments exists because the schema asks for a scene and a hook
        # action, and without it the model invents a setting (a kitchen at 7am,
        # regardless of the app). It now does more: the middle develops towards
        # one of these moments and stops there, which is the seam the founder's
        # own demo continues from.
        "usage_moments": _list("usage_moments"),
        # proof_moment is DELIBERATELY NOT PASSED. It is the one moment the
        # camera must film to make the claim believable, which is the product
        # demo — and the demo is recorded by the founder and attached after this
        # footage. It stays on the App Profile as a brief for that recording.
        # Supplying it here was the route by which "show this happening" reached
        # a prompt that is not allowed to show the app happening.
        #
        # viewer_objections are the middle's material. With one section to work
        # in, an objection is answered by the situation shown rather than by
        # another feature: each entry is why this viewer would not download,
        # what they use instead, and the honest reply.
        "viewer_objections": profile.get("viewer_objections") or [],
    }

    mechanism = {
        "template_name": template.get("name") or "(no template)",
        "hook_category": template.get("category") or "(unstated)",
        "objective": objective or "(unstated)",
        "opening_structure": template.get("opening_structure") or "(unstated)",
        "hook_seconds": hook_seconds,
        # `middle_structure` replaced `continuation_structure` + `cta_pattern`
        # when a video became one render with a hook and a middle. Reading the
        # retired names here meant this block printed
        # "continuation_structure": "(unstated)" and "cta_pattern": "(unstated)"
        # for EVERY strategy: the curated middle never reached the prompt at all,
        # and the one field still being asked for described a closing beat the
        # rules below this one forbid. The retired key is read as a fallback so a
        # template row written before the migration still says something.
        "middle_structure": (
            template.get("middle_structure") or template.get("continuation_structure")
            or "(unstated)"
        ),
        "visual_style": template.get("visual_style") or "(unstated)",
        "camera_pacing": template.get("camera_pacing") or "(unstated)",
        "required_assets": _list_of(template, "required_assets"),
        "content_slots": template.get("content_slots") or {},
    }

    # `angle_cta` used to sit in this brief, carrying the angle's
    # `recommended_cta` straight from the research step. It was a contradiction
    # rather than a hint: the same prompt goes on to forbid a call to action
    # outright, so the brief was handing the model a closing beat and then
    # telling it not to write one — and the founder's own close, which happens
    # after the render, is the only close there is. Nothing fills this gap now,
    # and nothing should: if a prompt needs the ending spelled out, that is the
    # `demo_brief` handoff, not a CTA.
    brief = {
        "angle_kind": (angle or {}).get("kind") or "(none)",
        "angle_label": (angle or {}).get("label") or "",
        "angle_audience": (angle or {}).get("target_audience") or profile.get("target_audience") or "",
        "angle_problem": (angle or {}).get("user_problem") or "",
        "angle_hook_promise": (angle or {}).get("hook_promise") or "",
        "angle_feature": (angle or {}).get("app_feature") or "",
        "angle_emotion": (angle or {}).get("desired_emotion") or "",
        "claims_to_respect": _list_of(angle, "claims_to_respect"),
        "hook_seconds": hook_seconds,
        "total_duration": total_duration,
        "tone": tone or "(unstated)",
        "brand_voice": brand_voice or profile.get("tone_voice") or "(unstated)",
    }

    claim_rules = {
        "approved": _list("claims_approved"),
        "needs_review": _list("claims_review"),
        "never_use": _list("claims_banned"),
    }

    # The founder-approved creative plan, when there is one. Its words are
    # already committed — the founder read and edited them before the first
    # render — so they are handed over as fixed material and the strategy is
    # built to deliver them. A beat's own text is the plan's, not a fresh line.
    approved_plan = {}
    if isinstance(plan, dict):
        beats = plan.get("beat_timeline")
        approved_plan = {
            "hook_line": str(plan.get("hook_line") or "").strip(),
            "visual_direction": str(plan.get("visual_direction") or "").strip(),
            "voice_direction": str(plan.get("voice_direction") or "").strip(),
            "sound_direction": str(plan.get("sound_direction") or "").strip(),
            "beats": [
                {
                    "label": str(b.get("label") or "").strip(),
                    "start": b.get("start"),
                    "end": b.get("end"),
                    "text": str(b.get("beat") or b.get("text") or "").strip(),
                }
                for b in (beats if isinstance(beats, list) else [])
                if isinstance(b, dict)
            ][:4],
        }
        # The plan's full script is the spine of the video. It is not echoed
        # here: the beats above already carry its content beat by beat, and
        # repeating it would crowd the prompt the strategy has to fit in.
        #
        # Note what is NOT passed: `demo_brief`. It exists so the founder knows
        # what to record for their own demo, and handing it to the strategy
        # would be the route by which a feature instruction reached the render.
        if not any(approved_plan[k] for k in ("hook_line",)) and not approved_plan["beats"]:
            approved_plan = {}

    approved_plan_context = ""
    if approved_plan:
        approved_plan_context = (
            "\n\nAPPROVED CREATIVE PLAN (the founder wrote and signed off on this BEFORE any "
            "video was generated — the strategy must produce THIS video, not a different one):\n"
            f"{json.dumps(approved_plan, indent=2)}\n"
        )

    feedback_context = ""
    if profile_feedback:
        feedback_context = (
            "\n\nPAST FEEDBACK FOR THIS APP (counts and fixed reason codes only):\n"
            f"{feedback.build_profile_feedback_section(profile_feedback)}\n"
        )
    feedback_context += _component_feedback_block(component_feedback, "script")

    # The one route by which real performance data reaches generation, and
    # deliberately anonymous: bands and a sample size, no source video, creator,
    # caption or retention. Omitted entirely when a template carries none, so a
    # curated template does not carry an empty evidence heading implying a
    # search was run and found nothing.
    trend_context = ""
    evidence_sentence = trend_evidence_sentence(template.get("trend_evidence"))
    if evidence_sentence:
        trend_context = (
            "\n\nWHAT OPENINGS OF THIS SHAPE HAVE ACTUALLY CARRIED "
            "(public trend data, aggregated across a sample; no single video is "
            "referenced and this is an observation about similar shapes, never a "
            "promise about yours):\n"
            f"{evidence_sentence}\n"
        )

    angle_goal_block = _angle_goal_block(angle, objective)
    system_message = (
        "You are the creative director for a short-form video campaign promoting one "
        "specific mobile app. You produce an app-specific video strategy: the hook "
        "concept, the exact words, what the on-camera person does, and a locked "
        "description of the scene they stand in. The person's appearance is never "
        "described anywhere in your response — it comes from the founder's "
        "photograph, and any written description of them would contradict it. "
        "Describe viewers by FUNCTIONAL need and use case only — never infer sensitive "
        "personal traits (health diagnoses, mental-health labels, finances, religion, "
        "sexuality, political leaning). For health-adjacent apps, describe the product's "
        "functionality, never a condition the viewer may have. Use ONLY facts supplied "
        "below; never invent a feature, price, rating, review, download count or "
        "testimonial. Write every spoken line in the voice of a satisfied customer sharing their "
        "own experience, never as the app's founder, owner or marketer. "
        "Respond with STRICT JSON only, no markdown fences."
    )

    prompt = (
        f"VERIFIED APP FACTS:\n{json.dumps(facts, indent=2)}\n\n"
        f"HOOK MECHANISM (the selected template must be honoured, not replaced):\n{json.dumps(mechanism, indent=2)}\n\n"
        f"CREATIVE BRIEF:\n{json.dumps(brief, indent=2)}\n\n"
        f"CLAIM RULES:\n{json.dumps(claim_rules, indent=2)}\n"
        f"{angle_goal_block}\n"
        f"{approved_plan_context}"
        f"{feedback_context}"
        f"{trend_context}\n"
        f"{_spoken_line_rules_block()}\n"
        "Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "strategy_summary": "2-3 sentences on the strategy for THIS app and why it fits THIS audience",\n'
        '  "audience_problem": "the concrete problem this viewer actually has, in their words",\n'
        '  "emotional_triggers": ["2-4 emotions this video should trigger, each tied to this app\'s use case"],\n'
        '  "hook_concept": "what the first seconds DO, visually and dramatically — not a slogan",\n'
        f'  "hook_line": "the single spoken hook line, said to this viewer about this problem, {_strategy_hook_min_words}-12 words (about {hook_seconds}s of speech — long enough to fill the hook beat, never a short fragment)",\n'
        '  "hook_promise": "what the hook promises the viewer in the next few seconds",\n'
        '  "hook_action": "the opening physical performance: ordered, timed beats across face, gaze, head, shoulders, hands and props, already moving in frame one",\n'
        '  "hook_dialogue": "the exact words spoken in the hook, or the delivery direction if none",\n'
        '  "messaging_pillars": ["2-4 viewer outcomes/benefits the video must land, each translated from a real feature -- what changes in the viewer\'s life or how they feel after using it, never the feature spec itself"],\n'
        f'  "primary_feature": "the ONE feature this video shows, from the facts above",\n'
        '  "desired_outcome": "the viewer outcome, described as a change the app supports, never a guarantee",\n'
        '  "mechanism_beat": "how this app\'s solution works, framed entirely as the resulting benefit to the viewer (draw on the outcome_statements how_it_helps above) -- never a spec, never filmed working",\n'
        '  "payoff_beat": "the outcome stated directly in the viewer\'s own terms (draw on the outcome_statements outcome above) -- the last thing said before the reach for the phone",\n'
        '  "differentiation_beat": "how this app differs from what the viewer would otherwise reach for",\n'
        '  "scene": {\n'
        f'    "camera_angle": "the exact camera position and angle, e.g. eye-level handheld 1m away",\n'
        f'    "framing": "framing and shot size, e.g. medium close-up, head and shoulders",\n'
        f'    "lighting": "light direction, quality and colour temperature",\n'
        f'    "environment": "the physical place, named concretely",\n'
        f'    "background": "what is behind them, concretely and unchanging",\n'
        f'    "setting": "time of day and situational context",\n'
        f'    "visual_style": "the overall look — documentary, polished UGC, cinematic",\n'
        f'    "character_positioning": "where they stand or sit in frame",\n'
        f'    "wardrobe": "what they are wearing, chosen to suit the setting — the ONE thing about '
        f'their appearance this render may change",\n'
        f'    "props": "objects in shot, or explicitly none",\n'
        f'    "color_palette": "the colour palette of the scene",\n'
        '  },\n'
        '  "performance": {\n'
        f'    "movement": "how they move and what they do with their hands and face",\n'
        f'    "voice_delivery": "tone, pace and energy of the voice — default to fast, upbeat, high-energy delivery unless the plan says otherwise",\n'
        '  },\n'
        '  "segments": [\n'
        f'    {{"index": 0, "role": "hook", "seconds": {hook_seconds}, "goal": "what these seconds must achieve",'
        ' "script": "words spoken in this segment", "action": "what they do in this segment"}'
        + _two_section_schema(plan_seconds)
        + '\n  ],\n'
        + f'  "camera_beat": {{"at": {round(camera_beat_seconds(hook_seconds), 2)}, '
        '"gesture": "the specific visible beat the BODY makes as the move lands on the hook '
        "line finishing -- brows lifting, a nod on the last word, chin dipping as they turn "
        "into the lean. Name what they do, never the camera move itself, never a wave, and "
        'never anything that turns their eyes off the lens"},\n'
        "}\n"
        "Rules:\n"
        + "- Every text field is a sentence that starts with a capital letter -- write "
        "the examples above as sentences, not as lowercase fragments, or the strategy "
        "renders with a typo.\n"
        + (
            "- An APPROVED CREATIVE PLAN is supplied above. The founder wrote it and reviewed it "
            "before this video cost anything, so it is the video: hook_line must be that hook line, "
            "and the two sections must deliver the plan's two beats in that order. Do not "
            "improve on it, do not reorder it, and do not replace its words with a different hook "
            "just because you would have written it differently. What you add is what a plan cannot "
            "express: the on-camera action for each section, the scene, and the performance.\n"
            if approved_plan
            else ""
        )
        + "- There are exactly TWO sections and they are the whole video. Segment 0 is the hook. "
        f"Segment 1 is the middle and runs {plan_seconds} seconds to the end. Never return a third "
        "section.\n"
        + f"- SPOKEN WORDS: the hook section speaks for {hook_seconds}s and the middle for "
        f"{plan_seconds}s — aim for about {_strategy_hook_target} characters of hook dialogue and "
        f"about {_strategy_middle_target} characters of middle script. This is the length for a "
        "natural read, not an arbitrary maximum: reach it with dialogue that is naturally that "
        "long. NEVER pad with filler words, extra spaces or stray punctuation to hit it. Land "
        "CLOSE TO each target rather than filling the seconds, and end on the payoff beat as the "
        f"last thing said inside the middle. The hard ceilings are {_strategy_hook_budget} and "
        f"{_strategy_middle_budget} characters: a line past its ceiling is cut back or the render "
        "is refused. A script far under its target leaves dead air the video has to stretch "
        "across the full duration.\n"
        "- ONE STORY, TWO LINES: the hook's script names ONE problem this viewer actually has, in "
        "their own words, and the middle's script resolves that same problem — same subject, same "
        "viewer, the second answering the first. If the two sections would not read as one "
        "thought, rewrite the middle until they do.\n"
        "- The middle develops the hook — the situation, the pain, the reaction, the action, the "
        "transition — and its job is to end at the moment the viewer would reach for the app. It "
        "does NOT satisfy them, and it does not continue past that point.\n"
        "- NEVER put a product demonstration in either section. Do not film the app being used, do "
        "not show a screen, do not describe the app working while something unrelated happens on "
        "camera. The founder records the demo themselves and attaches it after this footage ends.\n"
        "- NEVER write a call to action, a request to download, or any closing beat. The founder "
        "adds the call to action in their own editor. There is no ending to write towards beyond "
        "the moment they reach for the phone.\n"
        +         f"- The opening section lasts {hook_seconds} seconds and must be the strongest {hook_seconds} seconds "
        f"for THIS app. Write a real hook for this app's real audience, not a generic influencer opening with "
        "the app name dropped in.\n"
        "- THE OPENING IS A PATTERN INTERRUPT, not an introduction: the viewer is "
        "mid-scroll, so the first frame must already be moving and "
        "the first half-second must hold ONE unmistakable physical beat. Never a neutral "
        "pose, a fade, a slow push-in standing in for action, or a greeting.\n"
        "- Break the expected pattern on purpose, then escalate: two or three actions "
        f"inside the {hook_seconds}-second opening, each bigger or stranger than the "
        "last, ending on the strongest, aimed at the lens.\n"
        "- Write them as ordered, timed action: posture and shoulders, torso, arms and "
        "hands and the exact gesture, head movement, gaze target, any prop grabbed or "
        "moved, and the face change (brows lifting, eyes widening, jaw dropping "
        "open). Ambiguity is the enemy: name the brow, the eye, the second.\n"
        "- Every beat above comes out of THIS video's own situation — its props, place, "
        "problem, or what the middle develops — not a gesture the rest must apologise "
        "for. Leave one question open that only the middle closes: what they grabbed, "
        "what happened, what happens next.\n"
        "- An expression is an ACTION inside the opening, never a description of who "
        "they are: describe no appearance and never contradict the founder's "
        "photograph. Say what the face does, never what the face is.\n"
        "- The hook must serve the selected hook mechanism. If the mechanism is a question, the hook is a "
        "question; if it is a contrarian correction, the hook corrects something.\n"
        "- The two sections must do genuinely different work. The hook earns attention; the middle "
        "is not the hook restated with more words. If the middle could be cut without losing the "
        "hook, it is not doing its job.\n"
        "- Fill every content_slot in the hook mechanism with a concrete value for THIS app, "
        "drawn from the verified facts and the brief above. A slot that names a specific "
        "feature of THIS app still describes it rather than filming it: what the middle "
        "shows is the situation that feature belongs to, not the feature working. An "
        "unfilled slot is a generic video.\n"
        "- There is no \"character\" key in this schema and none is wanted: do not add one, "
        "and do not describe the presenter's face, hair, hair colour, hairstyle, skin, age, "
        "build, facial hair or body in any field — not in strategy_summary, not in "
        "hook_concept, nowhere. The on-camera person is copied from the founder's "
        "photograph and nothing written here may contradict it; write about the audience, "
        "the problem, the app and the action instead.\n"
        "- scene.wardrobe is the ONE exception, and it is required. Fill it with what they "
        "are wearing, chosen to suit scene.setting and the usage moment — a coat and a "
        "scarf for a cold walk, scrubs for a hospital bench, a jumper for a desk. It is "
        "the only thing about their appearance the render may change, and it must be "
        "concrete: \"a grey knit jumper\" not \"something casual\". If the founder's own "
        "clothes already suit the scene, repeat them. Never describe their body, face or "
        "hair here, even to justify the clothes.\n"
        "- Invent the environment, setting, props and on-screen context concretely from the "
        "verified facts (features, use cases, problems, audience, platforms) — a kitchen "
        "counter at 7am for an evening-reflection app, not \"a nice room\". Nothing is "
        "composited over the footage and no text appears on screen, so what the camera "
        "must show has to be written here, in scene, segments and hook_action.\n"
        "- The generated scene is illustrative, never documentary: the script "
        "must never claim it shows real app footage or a screen recording. Anything the "
        "viewer could read as a factual claim about the app — interface text, button labels, "
        "prices, ratings, logos — must come from the verified facts or stay out of frame.\n"
        "- Make the scene so specific that a second video with the same strategy would be "
        "recognisably the same place. The person's sameness is the photograph's job, not the "
        "text's — never describe them to achieve it. Vague terms like \"casual\" or \"a nice "
        "room\" are not acceptable.\n"
        "- The scene must hold for BOTH sections. The hook and the middle are one render, so "
        "the background, lighting, framing, wardrobe, props and delivery it locks apply to the "
        "whole piece — and they hold for the clothing too: they change once, here, never "
        "mid-video. Never the face, hair, skin, age, build or facial hair, which come from "
        "the founder's photograph rather than from anything written here.\n"
        "- Every section must be satisfiable using only the verified facts above. Put anything "
        "that would need a claim from needs_review nowhere, or omit it entirely.\n"
        # The one field that closes the gap the schema otherwise leaves to
        # invention, now doing double duty. Phrased as an obligation, not a
        # suggestion: a field the model may use or ignore is the same as no
        # field at all.
        #
        # usage_moments sets the middle's setting AND is where the piece ends:
        # the app is reached for at a specific moment, so the middle develops
        # towards that moment and stops there. That stop is the seam the
        # founder's own demo picks up from.
        "- scene.setting must come from usage_moments. Those are the specific moments this app "
        "is reached for, and they are the only evidence of when and where a viewer would use "
        "it. Do not default to a generic kitchen, desk or morning routine. If usage_moments is "
        "empty, state that the moment is unspecified in the setting rather than inventing a "
        "plausible one.\n"
        "- The middle must end AT the usage moment from usage_moments — the presenter reaching "
        "for the app, not using it. The demo is the founder's own recording, attached after "
        "this footage, so the last frame of your video should be the moment before it.\n"
        # proof_moment is deliberately NOT a generation input any more. It is the one moment
        # the camera must film to make the claim believable — which is the product demo, and
        # the demo is recorded by the founder. It stays on the App Profile as a brief for that
        # recording; passing it here was how a "show the app working" instruction reached a
        # prompt that is not allowed to show the app working.
        #
        # viewer_objections now shape the middle rather than a chain of beats. With one
        # section to work in, an objection is answered by the situation being shown, not by
        # a feature list.
        "- viewer_objections are what the middle has to answer. Each is an objection, what the "
        "viewer does today instead, and an honest answer that is true from the verified facts. "
        "Weave the objections that matter into the middle in the viewer's own terms: show the "
        "alternative they are living with or the cost of doing nothing, so the objection is "
        "answered by the situation on screen rather than by a list of features. Two sections "
        "cannot carry every objection, so use the ones this audience would actually have.\n"
        # Outcome-framed pitch. The middle earns the download by describing
        # what changes for the viewer, not what the app contains — so the
        # pitch moments translate each feature into its resulting benefit
        # BEFORE writing. Stated as an ordered procedure rather than a vibe,
        # because a model told only to "focus on benefits" keeps the feature
        # list and appends adjectives.
        "- Translate every feature this video touches into its resulting benefit before "
        "writing a word of the middle: what changes in the viewer's life, or how they "
        "feel after using it. Instead of has a sleep timer, write helps you fall asleep "
        "without checking your phone. messaging_pillars, mechanism_beat and payoff_beat "
        "carry benefits only — the feature spec itself appears nowhere in them.\n"
        "- The middle has two pitch moments, in this order, and the hook has neither. "
        "The MECHANISM moment frames how the solution works as the resulting "
        "benefit (use the outcome_statements how_it_helps): never a spec, never the app "
        "filmed working. The PAYOFF moment states the outcome directly in the viewer's "
        "own terms (use the outcome_statements outcome) and is the last thing said "
        "before the reach for the phone. "
        "The hook stays attention-only: no outcome and no feature language in the opening.\n"
        # Source precedence. The profile already links outcomes to features,
        # so the only honest order is linked statements first, flat list
        # second, derivation last — and derivation is still derivation, never
        # invention.
        "- Take each outcome from VERIFIED APP FACTS outcome_statements first, via its "
        "from_feature link. Only when outcome_statements is empty use the flat outcomes "
        "list, and only when that is empty too derive a benefit from core_features. "
        "Never invent an outcome no source supports. "
        "Benefits, not promises: the no-guaranteed-outcome rule below governs every one "
        "of these lines.\n"
        # The trend section, when present. Phrased as a bias toward a shape the
        # data supports, never as a target: a view count is an observation about
        # someone else's video, and a model told to "beat 500K" will pad.
        "- If WHAT OPENINGS OF THIS SHAPE HAVE ACTUALLY CARRIED is present, let it bias the "
        "opening toward the shape that carried: a fast first line and a direct second. Do not "
        "chase the number itself, do not pad the hook to fill time, and do not "
        "state or imply a view, like or follower count. It describes what similar shapes have "
        "done, not what yours will do.\n"
        "- An honest_answer may not promise a result, a saving, or a guarantee, and may not "
        "claim a rating, count or price. Answer with what the app demonstrably does. If a "
        "recorded objection has no answer the facts support, leave it out rather than "
        "inventing one — the middle is better short than dishonest.\n"
        "- Never promise a guaranteed outcome, never invent a testimonial, a rating or a "
        "review, and never state a price, plan name or trial term — the App Profile carries "
        "none, so nothing could verify it.\n"
        "- Write every spoken line from the perspective of a satisfied customer sharing their "
        "own experience: their situation, how it felt, and the value they get from using the app. "
        "The speaker is a real user, never the app's founder, owner, developer or marketer — never "
        "imply they built, own or promote it, and never use an insider or first-person-plural "
        "product voice (we, our app). Keep the experience honest and generic: no invented personal "
        "specifics such as years of use, a profession, a diagnosis, or a hard result.\n"
        "- Use only approved claims. Never use anything in never_use.\n"
        # Length discipline. This object is large, and an over-long value here
        # is what pushes the reply past the completion budget and gets it cut
        # off mid-object. Concision costs nothing here: the fields are read as
        # locked values restated into a prompt, not as prose.
        "- Keep every string value under 25 words and each list to 2-4 short items. Be specific, not lengthy. "
        "A long value helps nothing and risks the whole object being cut off. The ONE exception is "
        "hook_action and the opening section's action: the opening's physical beats, which may run to about 45 words.\n"
        "- Never use double-quote characters inside any string value: write hook lines and dialogue "
        "without quotation marks. A stray quote breaks the JSON and fails the whole strategy.\n"
        "- Return ONE complete JSON object and nothing else: no prose before or after it, no markdown fence."
    )

    # This is the largest JSON schema in the codebase: ~45 values across five
    # nested objects, several of them prose. Thinking models spend thought
    # tokens from the SAME completion budget, so a budget that looks generous
    # on paper can be exhausted before the closing brace is written. 8192
    # stays the floor: it fits this schema and sits inside the provider
    # output ceiling of the models this service can be pointed at
    # (Claude Haiku 5.5's output ceiling is far above the 8192 used here).
    raw = await _chat_json(
        system_message=system_message,
        prompt=prompt,
        context="Video strategy",
        temperature=0.5,
        max_tokens=8192,
        attempts=2,
        json_schema=STRATEGY_JSON_SCHEMA,
    )
    if isinstance(raw.get("strategy"), dict):
        raw = raw["strategy"]

    missing = REQUIRED_STRATEGY_KEYS - set(raw.keys())
    if missing:
        logger.error(
            f"Video strategy missing fields {missing}. Keys returned: {sorted(raw.keys())}"
        )
        raise RuntimeError(f"Video strategy missing required fields: {missing}")

    strategy = normalize_strategy(raw)
    strategy["duration_seconds"] = int(total_duration or 0)
    strategy["hook_seconds"] = int(hook_seconds or 0)
    strategy["objective"] = normalize_objective(objective)
    strategy["template_id"] = str(template.get("id") or "")
    strategy["template_name"] = str(template.get("name") or "")
    strategy["template_version"] = int(template.get("version") or 1)
    strategy["content_angle_id"] = str((angle or {}).get("id") or "")
    strategy["brand_profile_id"] = str(profile.get("id") or "")
    return strategy


def _list_of(source, name: str) -> list:
    """Coerce a possibly-JSON value on a row into a list of strings."""
    val = (source or {}).get(name)
    if isinstance(val, list):
        return [str(v) for v in val if str(v).strip()]
    if val:
        return [str(val)]
    return []


def _normalize_beats(beats, duration: int) -> list:
    """
    Coerce the beat list into ordered {start, end, label, text} dicts.

    The timeline shape is a product requirement, so out-of-order or malformed
    beats are repaired by clamping to the requested duration rather than
    trusted straight through.
    """
    if not isinstance(beats, list):
        return []
    out = []
    for i, beat in enumerate(beats[:12]):
        if not isinstance(beat, dict):
            continue
        try:
            start = max(0.0, float(beat.get("start", 0)))
            end = float(beat.get("end", start + 1))
        except (TypeError, ValueError):
            continue
        if end <= start:
            end = start + 1
        start = min(start, duration)
        end = min(end, duration)
        label = str(beat.get("label") or f"beat-{i + 1}").strip()[:40]
        text = str(beat.get("text") or "").strip()[:400]
        if not text:
            continue
        out.append({"start": start, "end": end, "label": label, "text": text})
    out.sort(key=lambda b: b["start"])
    return out


async def generate_remix_script(analysis: dict, brand_profile: dict, target_duration: int, session_id: str, music_context: dict = None, transcript_text: str = "", hashtags: list = None, use_original_sound: bool = False) -> dict:
    """
    Auto-generate a production-ready video prompt ("Content Remixer") from hook analysis +
    a structured brand profile (niche, products/services, target audience, tone/voice).
    The resulting script is explicitly adapted to weave in the brand's actual niche and
    product/service, rather than generic brand copy.

    Enhanced with actual music/audio context, transcript, and hashtag data when available
    for more accurate remix scripts.

    Args:
        use_original_sound: If True and music_context has a song, the remix script is written
            to explicitly reuse that exact sound rather than suggesting a new one.
    """
    system_message = (
        "You are an expert short-form video creative director and brand scriptwriter. You take the "
        "analyzed 'hook' of a viral video and a brand's structured profile, and remix/adapt that hook "
        "into a new, production-ready video prompt that explicitly promotes the brand's real "
        "niche/products/services in a natural, on-brand way — not generic copy. Respond with STRICT "
        "JSON only, no markdown fences."
    )

    products = brand_profile.get("products_services") or []
    if isinstance(products, list):
        products_str = ", ".join(str(p) for p in products) or "(not specified)"
    else:
        products_str = str(products) or "(not specified)"

    # Build enhanced audio/music context
    audio_context_parts = []
    song_title = ""
    song_artist = ""
    if music_context:
        song_title = music_context.get("song_title") or ""
        song_artist = music_context.get("song_artist") or ""
        if song_title or song_artist:
            audio_context_parts.append(
                f"Original sound/music used: \"{song_title}\" by {song_artist}"
            )
    if transcript_text:
        truncated = transcript_text[:800]
        audio_context_parts.append(f"Original spoken script/transcript: \"{truncated}\"")

    audio_context_str = "\n".join(audio_context_parts) if audio_context_parts else "(not available)"

    # Build hashtags context
    hashtags_str = ""
    if hashtags and isinstance(hashtags, list) and len(hashtags) > 0:
        hashtags_str = f"Original video hashtags: #{', #'.join(hashtags[:10])}"

    has_sound_to_reuse = use_original_sound and (song_title or song_artist)
    sound_instruction = ""
    if has_sound_to_reuse:
        sound_instruction = (
            f"\n\nIMPORTANT: The user explicitly wants to REUSE the exact original sound/music "
            f"(\"{song_title}\" by {song_artist}) in the remixed video rather than a new voiceover or "
            "different track. Set audio_recommendation to keeping this exact original sound, and write "
            "the script to lean on visuals, on-screen text/captions, and movement/lip-sync timed to that "
            "original audio instead of new spoken dialogue that would clash with it."
        )
    elif use_original_sound:
        sound_instruction = (
            "\n\nNote: The user asked to reuse the original sound, but no sound metadata is available "
            "for this video — proceed with your best audio recommendation as normal."
        )

    prompt = (
        "Hook analysis of the original viral video's first 3 seconds:\n"
        f"- Facial expressions: {analysis.get('facial_expressions')}\n"
        f"- Body language & gestures: {analysis.get('body_language_gestures')}\n"
        f"- Pacing & cuts: {analysis.get('pacing_cuts')}\n"
        f"- Text overlays & timing: {analysis.get('text_overlays_timing')}\n"
        f"- Audio cues (inferred): {analysis.get('audio_cues_inferred')}\n"
        f"- Hook summary: {analysis.get('hook_summary')}\n"
        f"- Replicable mechanics: {analysis.get('replicable_mechanics')}\n\n"
        "Audio & music context from the original video:\n"
        f"{audio_context_str}\n"
        f"{hashtags_str}\n"
        f"{sound_instruction}\n\n"
        "Brand profile to remix this hook for:\n"
        f"- Brand name: {brand_profile.get('brand_name') or '(not provided)'}\n"
        f"- Brand description: {brand_profile.get('brand_description') or '(not provided)'}\n"
        f"- Niche: {brand_profile.get('niche') or '(not provided)'}\n"
        f"- Products/services: {products_str}\n"
        f"- Target audience: {brand_profile.get('target_audience') or '(not provided)'}\n"
        f"- Ideal customer profile (demographics, interests, pain points, where they spend time online): "
        f"{brand_profile.get('ideal_customer_profile') or '(not provided)'}\n"
        f"- What sets this brand apart (standout strengths / USPs / signature angle): "
        f"{brand_profile.get('differentiation') or '(not provided)'}\n"
        f"- Tone/voice: {brand_profile.get('tone_voice') or '(not provided)'}\n\n"
        f"Target video duration: EXACTLY {target_duration} seconds. This is critical — pace all content, "
        f"transitions, and delivery to fill exactly {target_duration} seconds. A {target_duration}-second "
        f"video {'is very short — every beat must be punchy and immediate, no wasted time' if target_duration <= 7 else 'needs tight pacing with clear beats' if target_duration <= 12 else 'allows for a setup-payoff arc with breathing room' if target_duration <= 20 else 'should have a full narrative arc with intro, development, and strong CTA'}.\n\n"
        "Remix the original hook's mechanics into a new script that naturally features this brand's "
        "specific product(s)/service(s) — e.g. if the brand sells fitness supplements, the narrative should "
        "naturally weave in that specific product, not generic brand copy. Speak directly to the ideal "
        "customer profile's pain points and where they spend time online, and lean into the brand's stated "
        "differentiation/USP as the emotional payoff or twist of the remixed script. "
        "If the original video uses a trending sound, suggest whether to keep the same sound or recommend "
        "a similar audio approach for the remix. Return ONLY a JSON "
        "object with this exact schema:\n"
        "{\n"
        '  "content": "what happens in the video SECOND BY SECOND — explicitly reference timestamps (e.g. 0-2s: hook, 2-5s: reveal, etc.)",\n'
        '  "camera_angle": "camera angles matching the original hook",\n'
        '  "view_position": "framing/view position",\n'
        '  "character_behavior": "how the character behaves/moves",\n'
        '  "scene_details": "environment/background/lighting/props",\n'
        '  "brand_narrative": "how the video ties into the brand\'s specific niche/products/services/tone",\n'
        '  "audio_recommendation": "suggested sound/music approach for the remix (keep original sound, use similar style, or voiceover)",\n'
        '  "full_video_prompt": "cohesive production-ready prompt (150-300 words) that EXPLICITLY states the video is ' + str(target_duration) + ' seconds and paces content accordingly",\n'
        '  "suggested_duration_seconds": ' + str(target_duration) + "\n"
        "}\n"
        "IMPORTANT: The full_video_prompt MUST explicitly mention it is a " + str(target_duration) + "-second video and structure content timing to match.\n"
        "Return ONLY valid JSON."
    )

    payload = {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        **_temperature_param(TEXT_MODEL, 0.5),
        "max_tokens": 3000,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await _post_chat(client, payload)
        resp.raise_for_status()
        data = resp.json()

    full_text = data["choices"][0]["message"]["content"]
    result = _parse_json_response(full_text, "Remix script generation")

    missing = REQUIRED_VIDEO_PROMPT_KEYS - set(result.keys())
    if missing:
        logger.error(f"Remix script generation missing fields {missing}. Raw text: {full_text[:1500]!r}")
        raise RuntimeError(f"Remix script generation missing required fields: {missing}")

    # Deterministic safety net: guarantee the audio plan reflects the user's choice
    # regardless of what the model produced, so the UI can trust this field.
    if has_sound_to_reuse:
        result["audio_recommendation"] = f'Keep the original sound: "{song_title}" by {song_artist}'

    return result


REQUIRED_REMIX_CHAT_KEYS = {"reply", "brief", "ready_to_generate"}
REMIX_BRIEF_KEYS = {
    "brand_name", "brand_goal", "brand_details", "brand_overview",
    "unique_selling_propositions", "brand_voice_tone", "target_audience",
}


def empty_remix_brief() -> dict:
    return {
        "brand_name": "",
        "brand_goal": "",
        "brand_details": "",
        "brand_overview": "",
        "unique_selling_propositions": [],
        "brand_voice_tone": "",
        "target_audience": "",
    }




def strip_html_to_text(html: str) -> str:
    """Basic regex-based HTML-to-text stripper (no external HTML parsing dependency)."""
    import re

    # Remove script/style/head blocks entirely (including their content)
    text = re.sub(r"(?is)<(script|style|head|noscript)[^>]*>.*?</\1>", " ", html)
    # Replace common block-level tags with newlines to preserve some structure
    text = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6]|/tr)\s*/?>", "\n", text)
    # Strip all remaining tags
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    # Unescape common HTML entities
    entities = {
        "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&quot;": '"', "&#39;": "'", "&rsquo;": "'", "&ldquo;": '"', "&rdquo;": '"',
    }
    for ent, repl in entities.items():
        text = text.replace(ent, repl)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _html_meta_descriptions(html: str) -> list:
    """
    content= of description/og:description/twitter:description meta tags.

    Parsed per-tag so attribute order does not matter (content-first tags
    are common on store listings). Returns [] on any markup surprise rather
    than half a tag.
    """
    found = []
    for tag in re.findall(r"(?is)<meta\b[^>]*>", html or ""):
        attrs = dict(
            (k.lower(), v)
            for k, v in re.findall(r"""(\w+)\s*=\s*["'](.*?)["']""", tag)
        )
        name = (attrs.get("name") or attrs.get("property") or "").strip().lower()
        if name in ("description", "og:description", "twitter:description"):
            content = (attrs.get("content") or "").strip()
            if content:
                found.append(content)
    return found


def _html_json_ld_strings(html: str, limit: int = 20) -> list:
    """
    Every string value inside JSON-LD blocks, in document order.

    Store listings and business sites carry their real description here even
    when the visible body is a client-rendered shell. Malformed blocks are
    skipped: one bad script tag must not poison the rest.
    """
    found = []
    for block in re.findall(
        r'''(?is)<script\b[^>]*type\s*=\s*["']application/ld\+json["'][^>]*>(.*?)</script>''',
        html or "",
    ):
        try:
            data = json.loads(block)
        except (ValueError, TypeError):
            continue
        stack = [data]
        while stack and len(found) < limit:
            node = stack.pop()
            if isinstance(node, dict):
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, str) and node.strip():
                found.append(node.strip())
    return found[:limit]


def _html_title(html: str) -> str:
    """The page <title>: stripped with <head> today, yet often the only words
    a script-rendered page serves to a plain fetch."""
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html or "")
    if not match:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", match.group(1))).strip()


def page_text_with_metadata(html: str) -> str:
    """
    Body text plus high-signal head metadata, highest-signal first.

    The plain stripper drops <head> entirely, so a store listing whose body
    is a client-rendered shell used to research as one heading plus nav —
    while its title, meta description and JSON-LD carried the actual product
    facts. This keeps the body primary (it stays the bulk) and prepends only
    what the body lacks: title, meta descriptions, JSON-LD strings, each
    once. A pure JS shell still yields almost nothing — honestly thin, and
    reported as such by the caller — rather than invented text.
    """
    import re

    body = strip_html_to_text(html)
    blocks = []
    title = _html_title(html)
    if title:
        blocks.append(title)
    blocks.extend(_html_meta_descriptions(html))
    blocks.extend(_html_json_ld_strings(html))
    if body.strip():
        blocks.append(body.strip())
    # Meta and JSON-LD routinely repeat the body's first paragraph; exact
    # duplicates would burn prompt budget twice for the same words.
    seen = set()
    unique = []
    for block in blocks:
        if block not in seen:
            seen.add(block)
            unique.append(block)
    return "\n\n".join(unique).strip()
