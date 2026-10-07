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
from pathlib import Path
from typing import Optional

import httpx

from face_crop import crop_face_from_path
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
    clamp_duration,
)
import feedback

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

logger = logging.getLogger(__name__)

# Models
VISION_MODEL = "openai/gpt-4o-mini"
IMAGE_GEN_MODEL = "google/gemini-2.5-flash-image"
FACE_SWAP_MODEL = "google/gemini-3.1-flash-image"  # Gemini 3.1 Flash Image — reliable face identity transfer, up to 14 input references, up to 4K
TEXT_MODEL = "openai/gpt-4o-mini"

# Video generation models.
# The template studio's providers. MiniMax H3 is the default: 2K picture,
# native audio, V2V motion transfer, up to 15s per pass. Hailuo 3 Max sits
# alongside it for comparison and gives up 2K for prompt adherence; see its
# entry below. A video is ONE render either way, so a request longer than
# the model's single-pass ceiling is refused rather than truncated.
VIDEO_MODELS = {
    "aleph-2": {
        "id": "runway/aleph-2",
        "name": "Runway Aleph 2.0",
        "description": (
            "In-context video EDITOR (not generation) — edits a supplied clip "
            "directly rather than generating from a prompt. Retained only for "
            "legacy records; not usable by the template studio."
        ),
        "max_duration": 30,
        "min_duration": 2,
        "supports_references": True,
        "supports_native_audio": False,
        "supports_v2v_motion": False,  # not motion transfer — direct video editing
        "resolution": "1080p",
        "is_video_editor": True,  # fundamentally different request shape — see generate_video()
    },
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
    # Grok Imagine Video: a prompt-to-video renderer that takes the founder's
    # photograph as the opening frame, in the same shape as the Hailuo entries.
    #
    # Facts below come from OpenRouter's own video model endpoint
    # (GET /api/v1/videos/models), which is a free read and states the
    # accepted fields per model. provider_capabilities.check_provider_drift
    # re-reads it at boot and warns if what we assert here stops matching.
    #
    # Three of its declared values drove this entry:
    #   supported_resolutions  480p, 720p  -> 720p, and nothing else. An
    #     unlisted resolution is a 400, which is the same constraint that shaped
    #     the H3 Max entry.
    #   supported_frame_images  first_frame only  -> the photo rides as the
    #     opening frame, never as a reference list.
    #   allowed_passthrough_parameters  []  -> no provider.options block, so
    #     there is no undocumented required field waiting to refuse a render.
    #
    # generate_audio is unlisted for this model, so supports_native_audio is
    # False and the studio omits the field entirely rather than sending an
    # unlisted parameter. Clips are therefore expected to be silent, the same
    # trade H3 Max already makes. If a real clip comes back with sound, that is
    # the flag to flip.
    #
    # Opt-in, not default: 720p rather than the 2K the default model gives,
    # with no native audio. At the 10-12s these templates render that is a
    # visibly softer clip, which is why Hailuo 3 stays the default and this is
    # the model to try a second script on. The downloads are scaled to the
    # 1080x1920 canvas on the way out.
    "grok-imagine-video": {
        "id": "x-ai/grok-imagine-video",
        "name": "Grok Imagine Video",
        "description": (
            "Prompt-to-video with your photo opening the clip as its first "
            "frame. 720p, 1-15s, no native audio. A softer, quieter take than "
            "the default. Opt-in."
        ),
        "max_duration": 15,
        "min_duration": 5,
        "supports_references": False,
        "supports_native_audio": False,  # generate_audio unlisted; omit the field
        "supports_v2v_motion": False,
        "resolution": "720p",
        "supports_combined_refs": False,
    },
    # Grok Imagine Video 1.5 Lite: the distilled, faster/cheaper sibling of
    # Grok Imagine Video, served on the same OpenRouter key and endpoint.
    # Same shape as its sibling (photo as opening frame, no native audio),
    # so it joins as a fourth opt-in for cheap drafts and second scripts.
    #
    # Facts below come from OpenRouter's own model page for
    # x-ai/grok-imagine-video-1.5-lite: 480p/720p/1080p, 1-15s clips,
    # first-frame image steering, vertical ratios included. Resolution is
    # 720p, not 1080p, on purpose: OpenRouter renders lite-1080p as upscaled
    # 720p at ~4.7x the per-second price, so 1080p buys cost without detail.
    # min_duration mirrors the sibling (5) rather than the provider floor (1)
    # until a first live render proves shorter renders work through the
    # studio's trim logic.
    #
    # generate_audio is unlisted for this model family, so
    # supports_native_audio is False and the studio omits the field. If a
    # real clip comes back with sound, that is the flag to flip.
    "grok-imagine-video-lite": {
        "id": "x-ai/grok-imagine-video-1.5-lite",
        "name": "Grok Imagine Video Lite",
        "description": (
            "Distilled Grok Imagine: faster, cheaper drafts with your photo "
            "opening the clip as its first frame. 720p, 1-15s, no native "
            "audio. For cheap drafts and second scripts. Opt-in."
        ),
        "max_duration": 15,
        "min_duration": 5,
        "supports_references": False,
        "supports_native_audio": False,  # generate_audio unlisted; omit the field
        "supports_v2v_motion": False,
        "resolution": "720p",
        "supports_combined_refs": False,
    },
    # HeyGen Video: general-purpose short-form business video (brand moments,
    # product demos) with synthesized audio in a single call — dialogue,
    # ambience and effects — from a prompt, a first-frame image, or
    # references. The first catalog entry besides Hailuo 3 with real audio.
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
    #   supported_frame_images  first_frame only  -> the photo rides as the
    #     opening frame, the same treatment as H3 Max and both Groks.
    #   generate_audio  false (accepted, defaults off), NOT null  -> the field
    #     is sendable, and the studio defaults to requesting audio whenever
    #     the provider offers it (server.py). If real clips come back silent
    #     or the field is ever refused, flip supports_native_audio to False.
    #
    # supports_references starts False on purpose despite the listing
    # accepting references in general: H3 Max taught that a listed field the
    # serving provider 400s is a paid failure, and only a live refs render
    # proves acceptance. Identity still flows via identity_via_first_frame,
    # so nothing about the founder's face is lost by starting here.
    #
    # Opt-in, default stays Hailuo 3: audio + 768p at a third of the listed
    # 2K price is a default-challenger on paper, but likeness is unproven
    # until the first renders. Promote only on evidence.
    "heygen-video-1": {
        "id": "heygen/heygen-video-1",
        "name": "HeyGen Video",
        "description": (
            "Business-video renderer with synthesized audio in one call — "
            "dialogue, ambience and effects — from your photo as the first "
            "frame. 768p, 5-15s. For talking-head hooks and demos. Opt-in."
        ),
        "max_duration": 15,
        "min_duration": 5,
        "supports_references": False,
        "supports_native_audio": True,  # listed as accepted; studio requests it by default
        "supports_v2v_motion": False,
        "resolution": "768p",
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

REQUIRED_BRAND_ANALYSIS_KEYS = {
    "brand_name", "brand_description", "niche",
    "target_audience", "ideal_customer_profile", "differentiation", "tone_voice",
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
    "icp_segments", "desired_outcomes", "differentiation", "competitors",
    "known_limitations", "must_not_show", "usage_moments", "proof_moment",
    "viewer_objections", "tone_voice", "claims_approved", "claims_review",
    "claims_banned",
}

# Phrase lists, which are lists of strings. viewer_objections is deliberately
# NOT here: it is a list of objects, so this normalizer would str() each one
# into an unreadable dict repr and the dedicated _normalize_objection_list below
# would then discard every entry as malformed — which is exactly what happened
# for as long as the key was included. It has its own normalizer, called after
# this loop.
APP_PROFILE_LIST_KEYS = (
    "platforms", "core_features", "primary_use_cases", "problems_solved",
    "icp_segments", "desired_outcomes", "competitors", "must_not_show",
    "usage_moments", "claims_approved",
    "claims_review", "claims_banned",
)


def _build_face_swap_prompt(customization_prompt: str = "") -> str:
    """Build the shared target-performance-first contract for image face swaps."""
    customization = customization_prompt.strip()
    customization_instruction = ""
    if customization:
        customization_instruction = (
            " CUSTOMIZATION: Apply this request only to the scene, clothing, environment, or visual "
            f"style: {customization}."
        )

    return (
        "TASK: This is a LOCAL EDIT of IMAGE 1, not a new photo. IMAGE 1 is the fixed base canvas — "
        "same pixels, same framing, same zoom level, same everything — EXCEPT the face region, which "
        "gets replaced with the identity from IMAGE 2. Do not regenerate the scene. Do not reframe, "
        "recrop, or zoom differently than IMAGE 1. Edit the face region only.\n\n"
        "This edit has TWO requirements that are EQUALLY MANDATORY. Both must be true in the output, "
        "with neither one allowed to weaken the other:\n\n"
        "REQUIREMENT A — IDENTITY COMES FROM IMAGE 2: The face in the output is IMAGE 2's face, not "
        "IMAGE 1's. Transfer from IMAGE 2: facial bone structure, jawline and chin shape, cheekbones, "
        "brow ridge, nose anatomy, intrinsic eye shape, eye color, intrinsic lip shape and fullness, "
        "skin tone, and hairstyle. FAIL CONDITION: the output is still recognizable as IMAGE 1's person.\n\n"
        "REQUIREMENT B — EXPRESSION, POSE, AND SCENE COME FROM IMAGE 1: Every other visual property "
        "must be copied from IMAGE 1 exactly, then rendered using IMAGE 2's facial anatomy from "
        "Requirement A. This includes: head orientation and tilt; gaze direction; eye openness and "
        "eyelid aperture; eyebrow position; MOUTH POSE — if IMAGE 1's mouth is closed, the output's "
        "mouth is closed; if IMAGE 1's mouth is open, the output's mouth is open at the same degree; "
        "jaw opening; reaction/emotion intensity; body pose and position; hand position and gestures; "
        "clothing; background and every object in it; lighting direction; camera angle; and framing/zoom "
        "level (do not crop tighter or wider than IMAGE 1). FAIL CONDITION: the mouth pose, head angle, "
        "gaze, framing, pose, or background differs from IMAGE 1, or IMAGE 2's own expression leaked "
        "into the output instead of being replaced by IMAGE 1's expression.\n\n"
        "Think of this as: IMAGE 2's person was standing exactly where IMAGE 1's person was standing, "
        "made exactly the same expression and gesture IMAGE 1's person was making, in the exact same "
        "room, at the exact same camera distance, and someone took IMAGE 1 at that instant instead.\n\n"
        "TEXT OVERLAYS: Remove ALL text overlays, captions, watermarks, and visual text elements that appear "
        "in the first image. The output must have a clean image with NO on-screen text, no subtitles, no "
        "branded overlays, no emoji overlays, and no caption graphics. "
        "HAIRSTYLE: Also replace the hairstyle from the first image with the hairstyle of the person in the "
        "second image — match its hair color, length, texture (straight, wavy, or curly), volume, and parting "
        "exactly as shown in the second image. Do not keep the hairstyle, hair color, or hair length that was "
        "originally in the first image. SKIN TONE CONSISTENCY (MANDATORY): The second image's face "
        "establishes the EXCLUSIVE skin color reference for the ENTIRE body. Every square centimeter of "
        "visible skin — face, neck, ears, chest, shoulders, upper arms, forearms, hands, fingers, legs, "
        "feet, and any other exposed area — MUST match the exact skin color and undertone from the second "
        "image's face. Do NOT retain the original body's skin tone from the first image anywhere. "
        "The skin must appear as one continuous, uniform tone across the whole person as if they were born "
        "with that skin color. There must be zero visible boundary, hard edge, or color shift at the "
        "jawline, neck, collar, shoulders, or any transition between face and body. Apply the scene's "
        "natural lighting and shadows on top of this matched skin tone, but the underlying base pigment "
        "must be identical everywhere — face, body, limbs, hands, all one person's natural skin color."
        f"{customization_instruction}"
        " Customization applies only to scene, clothing, environment, and visual style — it must never "
        "change the identity from IMAGE 2, and must never change the expression being re-performed "
        "from IMAGE 1.\n\n"
        "FINAL CHECK BEFORE OUTPUT — verify BOTH, neither is optional: "
        "(1) Is the face IMAGE 2's person, not IMAGE 1's? "
        "(2) Is everything else — mouth pose, head angle, gaze, pose, hand position, clothing, "
        "background, camera angle, and framing/zoom — an exact match to IMAGE 1, not to IMAGE 2 and "
        "not a new scene? "
        "If either check fails, discard the result and redo it. A result that passes (1) but fails (2) "
        "is just as wrong as a result that fails (1) — this is a local edit of IMAGE 1, not a new "
        "photograph of IMAGE 2's person."
    )


def _headers():
    return {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://hookforge.app",
        "X-Title": "HookForge",
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
    temperature: float = 0.4,
    max_tokens: int = 3000,
    attempts: int = 2,
    timeout: int = 120,
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
            "temperature": temperature,
            "max_tokens": budget,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{OPENROUTER_BASE}/chat/completions", headers=_headers(), json=payload
            )
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
        "temperature": 0.3,
        "max_tokens": 3000,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=_headers(), json=payload)
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


async def generate_customized_preview(
    reference_frame_path: Path,
    person_photo_path: Path,
    mode: str,
    customization_prompt: str,
    session_id: str,
) -> bytes:
    """Generate a customized face-swapped preview with the configured face-swap model.

    The scene reference is sent FIRST and framed as "the image to edit"; the
    cropped identity photo is sent SECOND as "the new face to use". This edit-
    style framing (vs. a generic "generate me in this scene" instruction) is
    what actually gets these image-editing models to replace the face instead
    of just reproducing the scene reference's original face — see git history
    (bcbf905, fe70420, 48c1082) for prior instances of this same failure mode
    across different underlying models.
    """
    # Crop the person photo to just the face region before sending to the model.
    cropped_person_path = crop_face_from_path(person_photo_path)

    # Use OpenRouter's dedicated Images API with explicit identity + scene references.
    payload = {
        "model": FACE_SWAP_MODEL,
        "prompt": _build_face_swap_prompt(
            customization_prompt if mode == "custom" else ""
        ),
        "input_references": [
            {"type": "image_url", "image_url": {"url": image_data_uri(reference_frame_path)}},
            {"type": "image_url", "image_url": {"url": image_data_uri(cropped_person_path)}},
        ],
        "resolution": "2K",
        "aspect_ratio": "9:16",
        "n": 1,
    }

    return await _call_image_generation_with_retry(
        payload=payload,
        context="Customized preview generation",
        max_retries=1,
        timeout=600,
    )


async def generate_face_swap(
    target_image_path: Path,
    source_face_path: Path,
    session_id: str,
    customization_prompt: str = "",
) -> bytes:
    """
    Standalone identity-preserving scene edit through OpenRouter's Images API.

    The target scene is sent FIRST and framed as "the image to edit"; the
    cropped source identity is sent SECOND as "the new face to use". Sending
    the scene as reference 1 with a generic "generate me in this scene"
    instruction (the previous approach) made these image-editing models treat
    the scene reference as authoritative and reproduce it — including its
    original face — largely ignoring the uploaded face. Framing this as a
    direct, local edit of image 1 using image 2's face is what actually
    swaps the identity. See git history (bcbf905, fe70420, 48c1082) for prior
    instances of this same failure mode across different underlying models.

    Optional customization_prompt lets the user request changes to clothing,
    environment, or other scene elements while keeping the identity swap intact.
    """
    # Crop the source face image to just the face region before sending to the model.
    cropped_source_path = crop_face_from_path(source_face_path)

    payload = {
        "model": FACE_SWAP_MODEL,
        "prompt": _build_face_swap_prompt(customization_prompt),
        "input_references": [
            {"type": "image_url", "image_url": {"url": image_data_uri(target_image_path)}},
            {"type": "image_url", "image_url": {"url": image_data_uri(cropped_source_path)}},
        ],
        "resolution": "2K",
        "aspect_ratio": "9:16",
        "n": 1,
    }

    return await _call_image_generation_with_retry(
        payload=payload,
        context="Face swap",
        max_retries=1,
        timeout=600,
    )


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
        "temperature": 0.5,
        "max_tokens": 3000,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=_headers(), json=payload)
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
        "temperature": 0.4,
        "max_tokens": 1500,
    }

    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=_headers(), json=payload)
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


async def _edit_video_with_aleph(
    prompt: str,
    source_video_url: Optional[str],
    face_anchor_path: Optional[Path],
    model_id: str,
    min_dur: int,
    max_dur: int,
) -> dict:
    """
    Submit a video EDIT job to Runway Aleph 2.0 via OpenRouter.

    Unlike generative models (MiniMax H3), Aleph does not synthesize
    a new scene — it takes the actual source video and applies ONLY the named
    edit, preserving every pixel it wasn't told to change (body movement,
    hand gestures, camera angle, clothing, background, timing). This is why
    it's used for the default "replicate this exact hook" flow instead of the
    generative models: there's no scene to regenerate, no motion to guess at.

    Request shape (best-effort mapping onto OpenRouter's normalized video
    schema, since Aleph is exposed as a video-output model there like any
    other): the video TO EDIT is sent as a video_url reference inside
    input_references (the only video-input slot in OpenRouter's schema), and
    the face-swapped still is sent as a frame_images entry pinned to
    frame_type="first_frame" so Aleph anchors the target identity to the
    opening frame and carries it through the rest of the clip. If OpenRouter's
    actual routing for Aleph differs from this, the resulting 400 error body
    will name the expected field — same iterative approach used to fix the
    Seedance 2.5 resolution and TaskTypeConstraint issues.

    Raises RuntimeError if no source video is available — Aleph has nothing
    to edit without one; callers should fall back to a generative model.
    """
    if not source_video_url:
        raise RuntimeError(
            "Runway Aleph 2.0 requires a source video to edit — no reference "
            "video is available for this generation. Fall back to MiniMax H3 instead."
        )

    payload = {
        "model": model_id,
        "prompt": prompt,
        "duration": max(min_dur, min(3, max_dur)),
        "resolution": "1080p",
        "aspect_ratio": "9:16",
        "input_references": [
            {
                "type": "video_url",
                "video_url": {"url": source_video_url},
            }
        ],
    }

    if face_anchor_path and face_anchor_path.exists():
        payload["frame_images"] = [
            {
                "type": "image_url",
                "image_url": {"url": image_data_uri(face_anchor_path)},
                "frame_type": "first_frame",
            }
        ]

    logger.info(
        f"Submitting video EDIT (Runway Aleph 2.0): duration={payload['duration']}s, "
        f"has_source_video=True, has_face_anchor={bool(payload.get('frame_images'))}, "
        f"model={model_id}"
    )

    async with httpx.AsyncClient(timeout=90) as client:
        last_error = None
        for attempt in range(2):
            try:
                resp = await client.post(f"{OPENROUTER_BASE}/videos", headers=_headers(), json=payload)
            except httpx.TimeoutException as e:
                last_error = RuntimeError(f"Video edit timed out: {e}")
                if attempt == 0:
                    logger.warning("Aleph video edit attempt 1 timed out, retrying...")
                    await asyncio.sleep(2)
                    continue
                raise last_error

            if resp.status_code in (502, 503, 429) and attempt == 0:
                logger.warning(
                    f"Aleph video edit attempt 1 got HTTP {resp.status_code}: "
                    f"{resp.text[:200]} — retrying..."
                )
                await asyncio.sleep(3)
                continue

            if resp.status_code >= 400:
                error_text = resp.text[:500]
                logger.error(f"Aleph video edit submission failed: HTTP {resp.status_code}: {error_text}")
                raise RuntimeError(f"Video edit failed (HTTP {resp.status_code}): {error_text}")
            break

        data = resp.json()
        job_id = data.get("id") or data.get("generation_id") or ""
        logger.info(
            f"Aleph video edit submitted: job_id={job_id}, status={data.get('status')}, "
            f"polling_url={data.get('polling_url')}"
        )
        if not job_id:
            logger.error(f"Aleph video edit returned no job ID. Full response: {resp.text[:1000]}")
            raise RuntimeError("Video edit returned no job ID.")
        data["id"] = job_id
        return data


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

    # === Runway Aleph 2.0: video EDITOR, not a generator ===
    # Aleph doesn't synthesize a new scene from a prompt — it edits the actual
    # source video pixel-for-pixel, changing only what the prompt names. This
    # requires reference_video_url (the real hook clip to edit) AND a face
    # anchor image. It has its own request/response handling below because
    # the semantics differ fundamentally from generative models.
    if model_config.get("is_video_editor"):
        return await _edit_video_with_aleph(
            prompt=prompt,
            source_video_url=reference_video_url,
            face_anchor_path=reference_image_path,
            model_id=model_id,
            min_dur=model_config.get("min_duration", 2),
            max_dur=max_dur,
        )

    payload = {
        "model": model_id,
        "prompt": prompt,
        "duration": max(min_dur, min(duration, max_dur)),
        "resolution": model_config.get("resolution", "1080p"),
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
                error_text = resp.text[:500]
                logger.error(f"Video generation submission failed: HTTP {resp.status_code}: {error_text}")
                human = describe_provider_refusal(error_text)
                if human:
                    raise RuntimeError(human)
                # Nothing here matched a known signature, so do not hand the
                # founder a wall of nested provider JSON: it names fields they
                # cannot set and offers no action. Describe the request we
                # actually sent instead — that is what makes the next step
                # obvious — and leave the provider's own words in the log above.
                raise RuntimeError(
                    f"The provider rejected this render before it started "
                    f"(HTTP {resp.status_code}), so no clip was produced. We sent "
                    f"{model_config.get('name', model_id)}, {payload['duration']}s, "
                    f"{payload['resolution']}, {payload['aspect_ratio']}, "
                    f"{'with' if payload.get('frame_images') else 'without'} your photo. "
                    f"The full provider response is in the server log."
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



async def analyze_brand_from_text(url: str, page_text: str) -> dict:
    """Extract structured brand information from a website's scraped text using OpenRouter."""
    system_message = (
        "You are an expert brand strategist and audience researcher. You read raw text scraped from a "
        "company's website and extract a clear, structured summary of the brand — including a deep read "
        "on their ideal customer and what makes them different from competitors — for use in short-form "
        "video scriptwriting. Respond with STRICT JSON only, no markdown fences, no extra commentary."
    )

    prompt = (
        f"Website URL: {url}\n\n"
        "Raw scraped page text:\n"
        f"\"\"\"\n{page_text}\n\"\"\"\n\n"
        "Based on the above, return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "brand_name": "the brand/company/channel name",\n'
        '  "brand_description": "1-3 sentence description of what the brand does",\n'
        '  "niche": "the brand\'s niche/category/industry",\n'
        '  "target_audience": "short label for who the brand is trying to reach (e.g. \'busy professionals 25-40\')",\n'
        '  "ideal_customer_profile": "Who are you trying to reach? A rich 2-4 sentence description of the '
        'ideal customer/viewer covering demographics (age range, gender skew, income/life-stage if inferable), '
        'interests, pain points this brand solves for them, and where they likely spend time online '
        '(e.g. TikTok, Instagram Reels, YouTube Shorts, specific communities/forums)",\n'
        '  "differentiation": "What Sets You Apart? A 2-4 sentence description of what makes this brand '
        'different from others in its space — standout strengths, unique selling propositions, or signature '
        'angles that competitors don\'t have",\n'
        '  "tone_voice": "a short description of the brand\'s tone/voice (e.g. playful, premium, no-nonsense)"\n'
        "}\n"
        "If any field cannot be determined from the text, make a reasonable best-effort guess based on "
        "context rather than leaving it empty. Return ONLY valid JSON."
    )

    payload = {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1500,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=_headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

    full_text = data["choices"][0]["message"]["content"]
    result = _parse_json_response(full_text, "Brand analysis")

    missing = REQUIRED_BRAND_ANALYSIS_KEYS - set(result.keys())
    if missing:
        logger.error(f"Brand analysis missing fields {missing}. Raw text: {full_text[:1500]!r}")
        raise RuntimeError(f"Brand analysis missing required fields: {missing}")

    return result


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
        '  "differentiation": "2-4 sentences on what sets this app apart",\n'
        '  "competitors": ["named competitor apps if inferable, else empty"],\n'
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
        "Keep every list to 8 items max. Return ONLY valid JSON."
    )

    payload = {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 3000,
    }

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=_headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

    full_text = data["choices"][0]["message"]["content"]
    result = _parse_json_response(full_text, "App profile")

    missing = REQUIRED_APP_PROFILE_KEYS - set(result.keys())
    if missing:
        logger.error(f"App profile missing fields {missing}. Raw text: {full_text[:1500]!r}")
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


async def generate_content_angles(profile: dict, max_angles: int = 8) -> list:
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
        "differentiators": profile.get("differentiation") or "(unstated)",
        "competitors": _list("competitors"),
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
        f"Propose up to {max_angles} DISTINCT content angles, ordered strongest first. "
        "Return ONLY a JSON array where each element is:\n"
        "{\n"
        '  "kind": "one of the kinds listed above",\n'
        '  "label": "short 3-6 word title",\n'
        '  "target_audience": "the audience segment, described functionally",\n'
        '  "user_problem": "the concrete problem this angle speaks to",\n'
        '  "hook_promise": "what the first 3 seconds promise",\n'
        '  "app_feature": "the app feature this angle demonstrates",\n'
        '  "desired_emotion": "the emotion the viewer should feel by the end",\n'
        '  "claims_to_respect": ["claims or limitations that bound this angle"]\n'
        "}\n"
        "Rules: use ONLY facts present in the profile. If an angle would require a "
        "claim from claims_needing_review, list that claim in claims_to_respect. Never "
        "promise guaranteed outcomes, invent testimonials or reviews, state any price or "
        "trial term, or imply a feature the profile does not list. Vary the "
        "kinds — do not return eight variations of the same angle. Return ONLY valid JSON."
    )

    payload = {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": 3000,
    }

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=_headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

    full_text = data["choices"][0]["message"]["content"]
    parsed = _parse_json_response(full_text, "Content angles")

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
    }


async def generate_brand_templates(
    profile: dict, angles: Optional[list] = None, count: int = BRAND_TEMPLATE_COUNT,
    objective: str = "",
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
        "differentiators": profile.get("differentiation") or "(unstated)",
        "competitors": _list("competitors"),
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
        '  "default_duration": 10\n'
        "}\n"
        "Rules: use ONLY facts present above. Never invent a feature, price, rating, "
        "review, testimonial, or guaranteed outcome. Never use a banned claim. Vary "
        "the categories and objectives — not ten variations of one idea. "
        f"hook_seconds is {MIN_HOOK_SECONDS}-{MAX_HOOK_SECONDS}; default_duration is one of "
        f"{', '.join(str(d) for d in SUPPORTED_DURATIONS)} seconds, and it is the length of the "
        "whole generated piece, not of a video the viewer finishes. "
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
    "demo_brief", "overlays", "voice_direction", "sound_direction",
}

# The two sections a plan's beat timeline is made of. Enforced, not suggested:
# a third label means the model has started planning footage this product does
# not generate.
PLAN_SECTION_LABELS = ("hook", "middle")


async def generate_creative_plan(
    profile: dict,
    template: dict,
    angle: Optional[dict] = None,
    objective: str = "",
    duration_seconds: int = 20,
    tone: str = "",
    brand_voice: str = "",
    profile_feedback: Optional[dict] = None,
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

    The prompt directs the model to render the full scene itself — environment,
    setting, props and on-screen context invented concretely from the verified
    facts — because nothing is composited over the footage except captions. On-
    screen text stays out of the model's hands (captions are added afterwards),
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
        "differentiators": profile.get("differentiation") or "(unstated)",
        # The plan prompt never saw the competitor list, while the strategy
        # prompt did -- so the one document the founder now reads and approves
        # before rendering was written by a model that could not see what this
        # app is up against, and the differentiation beat it asked for rested on
        # a comparison it could only guess at.
        "competitors": _list("competitors"),
        "known_limitations": profile.get("known_limitations") or "(none recorded)",
    }

    # The template's own opening length wins over the 3s default, so the beat
    # layout the model is asked for and the mechanism it was given agree. Clamped
    # here because this is the number the prompt states in seconds.
    hook_seconds = max(
        MIN_HOOK_SECONDS, min(MAX_HOOK_SECONDS, int(template.get("hook_seconds") or 3))
    )

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
        "audience": (angle or {}).get("target_audience") or profile.get("target_audience") or "(unstated)",
        "content_angle": (angle or {}).get("kind") or "(none)",
        "angle_hook_promise": (angle or {}).get("hook_promise") or "",
        "angle_feature": (angle or {}).get("app_feature") or "",
        "angle_emotion": (angle or {}).get("desired_emotion") or "",
        "duration_seconds": duration_seconds,
        "tone": tone or "(unstated)",
    }

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

    system_message = (
        "You are a short-form video creative director for mobile app promotions. "
        "You write concrete, filmable plans grounded ONLY in verified product facts. "
        "A plan covers exactly TWO generated sections — a HOOK in the first few seconds, "
        "then a MIDDLE that develops it — and stops at the moment the viewer would reach "
        "for the app. The product demo and the call to action are recorded and added by "
        "the founder separately, so you never plan either. "
        "Describe viewers by functional need, never by sensitive traits or diagnoses. "
        "Respond with STRICT JSON only, no markdown fences."
    )

    prompt = (
        f"VERIFIED APP FACTS:\n{json.dumps(facts, indent=2)}\n\n"
        f"TEMPLATE STRUCTURE:\n{json.dumps(structure, indent=2)}\n\n"
        f"CREATIVE BRIEF:\n{json.dumps(brief, indent=2)}\n\n"
        f"CLAIM RULES:\n{json.dumps(claims, indent=2)}\n"
        f"{feedback_context}\n"
        "Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "hook_line": "the single spoken/typed hook line, max 12 words",\n'
        '  "script": "the full spoken script for BOTH sections, plain text, no stage directions",\n'
        '  "beat_timeline": [{"start": 0, "end": 3, "label": "hook", "text": "what happens and what is said"}, {"start": 3, "end": 10, "label": "middle", "text": "what happens and what is said"}],\n'
        '  "visual_direction": "what the camera shows across both sections, as one paragraph",\n'
        '  "demo_brief": "ONE sentence telling the FOUNDER what to record for their own demo. This never reaches the generated video.",\n'
        '  "overlays": [{"start": 0, "end": 3, "text": "on-screen text, max 6 words"}],\n'
        '  "voice_direction": "delivery direction for the voiceover or on-camera talent",\n'
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
        f"and not one beat later. The generated piece is {duration_seconds} seconds; anything "
        "after it is the founder's own footage.\n"
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
        "- CRITICAL: nothing is composited over the footage except "
        "captions. Describe the full scene — environment, setting, props and any on-screen "
        "context — concretely from the verified facts above, and keep overlay text to "
        "short phrases. Never invent interface text, button labels, prices, ratings, "
        "logos, testimonials, or anything the viewer could read as a factual claim "
        "about the app. The generated scene is illustrative: the script must never claim "
        "it shows real app footage or a screen recording.\n"
        "- Use ONLY the features and claims present above, and only in the middle's framing of "
        "the situation. Never invent a feature, a rating, "
        "a review, a download count, or a user testimonial, and never state a price: no "
        "price is on record for this app, so a quote could not be checked.\n"
        # The reason competitors is in this prompt at all. Without the rule the
        # list is context the model may ignore, which is how it ended up in the
        # strategy prompt and missing here.
        "- If competitors are listed, the hook may open on the contrast between this app and "
        "the one a viewer would otherwise reach for, naming the specific difference. Do not "
        "state anything factual about a competitor: no features, prices, ratings or reviews "
        "may be attributed to another product, and never put a competitor's name, logo or "
        "interface on screen. Contrast this app's own verified facts against the viewer's "
        "default assumption, not against a competitor's record.\n"
        "- Never use anything in claims.never_use. If a claims.needs_review item would help, "
        "leave it out rather than using it.\n"
        "- Never promise a guaranteed outcome and never describe the viewer as having a "
        "condition. Describe what the app does instead.\n"
        "Return ONLY valid JSON."
    )

    payload = {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.5,
        "max_tokens": 3500,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=_headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

    full_text = data["choices"][0]["message"]["content"]
    result = _parse_json_response(full_text, "Creative plan")

    missing = REQUIRED_PLAN_KEYS - set(result.keys())
    if missing:
        logger.error(f"Creative plan missing fields {missing}. Raw: {full_text[:1500]!r}")
        raise RuntimeError(f"Creative plan missing required fields: {missing}")

    result["hook_line"] = (result.get("hook_line") or "").strip()[:200]
    result["script"] = (result.get("script") or "").strip()[:6000]
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
    result["overlays"] = _normalize_overlays(result.get("overlays"), duration_seconds)
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
    "primary_feature", "desired_outcome", "differentiation_beat",
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
            "desired_outcome", "differentiation_beat",
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
    result["segments"] = _normalize_sections(raw.get("segments"))
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

    Kept here rather than imported from research_abstraction so the strategy
    path does not pull in the Apify-facing modules; the format is a small
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
    plan: Optional[dict] = None,
    proved_hooks: Optional[dict] = None,
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
        "differentiators": profile.get("differentiation") or "(unstated)",
        "competitors": _list("competitors"),
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

    # Always emitted, even when empty. build_proved_hooks_section returns an
    # explicit no-signal sentence for a new app, and that sentence is the
    # instruction that matters: rely on the verified facts, assume nothing is
    # proven. Omitting the block instead would leave the model with no signal
    # and no acknowledgement of its absence.
    proved_context = (
        "\n\n"
        f"{feedback.build_proved_hooks_section(proved_hooks or {})}\n"
    )

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
        "testimonial. Respond with STRICT JSON only, no markdown fences."
    )

    prompt = (
        f"VERIFIED APP FACTS:\n{json.dumps(facts, indent=2)}\n\n"
        f"HOOK MECHANISM (the selected template must be honoured, not replaced):\n{json.dumps(mechanism, indent=2)}\n\n"
        f"CREATIVE BRIEF:\n{json.dumps(brief, indent=2)}\n\n"
        f"CLAIM RULES:\n{json.dumps(claim_rules, indent=2)}\n"
        f"{approved_plan_context}"
        f"{feedback_context}"
        f"{trend_context}"
        f"{proved_context}\n"
        "Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "strategy_summary": "2-3 sentences on the strategy for THIS app and why it fits THIS audience",\n'
        '  "audience_problem": "the concrete problem this viewer actually has, in their words",\n'
        '  "emotional_triggers": ["2-4 emotions this video should trigger, each tied to this app\'s use case"],\n'
        '  "hook_concept": "what the first seconds DO, visually and dramatically — not a slogan",\n'
        '  "hook_line": "the single spoken hook line, max 12 words",\n'
        '  "hook_promise": "what the hook promises the viewer in the next few seconds",\n'
        '  "hook_action": "the opening physical performance: ordered, timed beats across face, gaze, head, shoulders, hands and props, already moving in frame one",\n'
        '  "hook_dialogue": "the exact words spoken in the hook, or the delivery direction if none",\n'
        '  "messaging_pillars": ["2-4 things the video must land, derived from this app\'s real features"],\n'
        f'  "primary_feature": "the ONE feature this video shows, from the facts above",\n'
        '  "desired_outcome": "the viewer outcome, described as a change the app supports, never a guarantee",\n'
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
        f'    "voice_delivery": "tone, pace and energy of the voice",\n'
        '  },\n'
        '  "segments": [\n'
        f'    {{"index": 0, "role": "hook", "seconds": {hook_seconds}, "goal": "what these seconds must achieve",'
        ' "script": "words spoken in this segment", "action": "what they do in this segment"}'
        + _two_section_schema(plan_seconds)
        + '\n  ]\n'
        "}\n"
        "Rules:\n"
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
        "composited over the footage except captions, so what the camera "
        "must show has to be written here, in scene, segments and hook_action.\n"
        "- The generated scene is illustrative, never documentary: the script and captions "
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
        "- Never speak in the presenter's first person about using this app (I use this, I "
        "have used this for years, as a nurse I rely on this). The presenter is a stand-in "
        "and nothing is known about their real relationship to the product, so any personal "
        "claim would be invented.\n"
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
    # (openai/gpt-4o-mini caps output at 16384).
    raw = await _chat_json(
        system_message=system_message,
        prompt=prompt,
        context="Video strategy",
        temperature=0.5,
        max_tokens=8192,
        attempts=2,
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


def _normalize_overlays(overlays, duration: int) -> list:
    """Coerce overlays into {start, end, text} dicts bounded by the duration."""
    if not isinstance(overlays, list):
        return []
    out = []
    for item in overlays[:12]:
        if isinstance(item, str):
            text = item.strip()[:60]
            out.append({"start": 0, "end": duration, "text": text} if text else None)
            continue
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or "").strip()[:60]
        if not text:
            continue
        try:
            start = max(0.0, float(item.get("start", 0)))
            end = float(item.get("end", duration))
        except (TypeError, ValueError):
            start, end = 0.0, float(duration)
        if end <= start:
            end = start + 1
        out.append({
            "start": min(start, duration),
            "end": min(end, duration),
            "text": text,
        })
    return [o for o in out if o]


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
        "temperature": 0.5,
        "max_tokens": 3000,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=_headers(), json=payload)
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


async def remix_chat_turn(
    analysis: dict,
    video: dict,
    conversation_history: list,
    existing_brief: dict,
    session_id: str,
) -> dict:
    """
    One turn of the conversational "remix this video for my brand" chat.
    Acts like a creative strategist: it checks audience fit between the
    original hook's implied audience and the brand described so far, asks
    focused clarifying questions (one or two at a time, not a checklist
    dump), and incrementally builds a structured brief. `conversation_history`
    is a list of {"role": "user"|"assistant", "content": str} in chronological
    order (the latest user message is the last entry). `existing_brief`
    carries forward fields already captured in prior turns so the model only
    needs to fill in gaps or apply corrections, not restart from scratch.
    """
    system_message = (
        "You are an expert short-form video creative strategist helping a user remix a viral TikTok hook for "
        "their own brand/product. You already know exactly what makes the ORIGINAL video's hook work (given "
        "below) and who it likely targets. Your job, turn by turn, is to:\n"
        "1. Briefly acknowledge what the user is asking for.\n"
        "2. Proactively sanity-check AUDIENCE FIT between the original video's implied audience and the "
        "brand/product described so far - call out if it's a strong match, a stretch, or a mismatch, and why, "
        "in 2-4 sentences. Use a checkmark or note when the fit is good.\n"
        "3. Ask ONLY the 1-2 most important missing clarifying questions next (never a long checklist) - things "
        "like the specific goal (installs, awareness, sales), what's most unique/compelling about the offer, or "
        "who exactly the target customer is - whichever is least clear so far.\n"
        "4. Keep responses conversational, concise (under ~120 words), and genuinely helpful - never robotic or "
        "overly formal boilerplate.\n"
        "As you go, maintain a structured brief in the background with whatever the user has told you so far. "
        "Only set ready_to_generate=true once you have a reasonably clear sense of the brand/product, the goal, "
        "and the target audience (either stated or reasonably inferred) - or the user explicitly says to proceed/"
        "skip further questions. Respond with STRICT JSON only, no markdown fences, no extra commentary."
    )

    history_lines = []
    for turn in conversation_history:
        role_label = "User" if turn.get("role") == "user" else "Assistant"
        history_lines.append(f"{role_label}: {turn.get('content', '')}")
    history_text = "\n".join(history_lines) if history_lines else "(no messages yet)"

    prompt = (
        "Original viral video context:\n"
        f"- Title: {video.get('title') or '(unknown)'}\n"
        f"- Niche: {video.get('niche') or '(unknown)'}\n"
        f"- Hook summary: {analysis.get('hook_summary')}\n"
        f"- Replicable mechanics: {analysis.get('replicable_mechanics')}\n\n"
        "Brief captured so far from this conversation (empty strings/lists = not yet known):\n"
        f"{json.dumps(existing_brief, ensure_ascii=False)}\n\n"
        "Conversation so far (latest user message is last):\n"
        f"{history_text}\n\n"
        "Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "reply": "your conversational reply to the user for this turn, following the instructions above",\n'
        '  "brief": {\n'
        '    "brand_name": "string, best known brand/product name, or empty string",\n'
        '    "brand_goal": "string, the goal of the video (e.g. drive installs), or empty string",\n'
        '    "brand_details": "string, what the brand/product offers and what the video should communicate, or empty string",\n'
        '    "brand_overview": "string, 1-3 sentence overview of the brand, or empty string",\n'
        '    "unique_selling_propositions": ["short bullet", "..."] concrete USPs mentioned so far, or empty list,\n'
        '    "brand_voice_tone": "string describing desired voice/tone, or empty string",\n'
        '    "target_audience": "string describing the target audience, or empty string"\n'
        "  },\n"
        '  "ready_to_generate": boolean, true only once enough context exists to write a strong video prompt\n'
        "}\n"
        "Carry forward every field from the existing brief unless this conversation clearly updates it. "
        "Return ONLY valid JSON."
    )

    payload = {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.5,
        "max_tokens": 2000,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=_headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

    full_text = data["choices"][0]["message"]["content"]
    result = _parse_json_response(full_text, "Remix chat")

    missing = REQUIRED_REMIX_CHAT_KEYS - set(result.keys())
    if missing:
        logger.error(f"Remix chat missing fields {missing}. Raw text: {full_text[:1500]!r}")
        raise RuntimeError(f"Remix chat response missing required fields: {missing}")

    brief = result.get("brief") or {}
    if not isinstance(brief, dict):
        brief = {}
    merged_brief = empty_remix_brief()
    merged_brief.update(existing_brief or {})
    for key in REMIX_BRIEF_KEYS:
        if key in brief and brief[key]:
            merged_brief[key] = brief[key]
    if not isinstance(merged_brief.get("unique_selling_propositions"), list):
        merged_brief["unique_selling_propositions"] = (
            [str(merged_brief["unique_selling_propositions"])] if merged_brief.get("unique_selling_propositions") else []
        )
    result["brief"] = merged_brief

    return result


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
