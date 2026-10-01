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
    normalize_angle_kind,
    normalize_objective,
)
import feedback

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

logger = logging.getLogger(__name__)

# Models
VISION_MODEL = "google/gemini-2.5-flash"
IMAGE_GEN_MODEL = "google/gemini-2.5-flash-image"
FACE_SWAP_MODEL = "google/gemini-3.1-flash-image"  # Gemini 3.1 Flash Image — reliable face identity transfer, up to 14 input references, up to 4K
TEXT_MODEL = "google/gemini-2.5-flash"

# Video generation models.
# MiniMax H3 is the template studio's only provider: 2K picture, native
# audio, V2V motion transfer, up to 15s per pass. Anything longer needs a
# second job, which the studio plans for rather than truncating.
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
}
# Default for new template-studio generations. The provider remains
# configurable through VIDEO_MODEL_DEFAULT and VIDEO_MODEL_ALLOWLIST, but
# MiniMax H3 is currently the only studio-eligible provider: anything else
# configured resolves back here with a logged reason.
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
    "brand_name", "brand_description", "niche", "products_or_services",
    "target_audience", "ideal_customer_profile", "differentiation", "tone_voice",
}

# Full App Profile schema produced by analyze_app_profile(). List fields come
# back as JSON arrays of short strings; icp_segments entries are "Segment
# label — needs / hook promise" one-liners so they stay editable text.
REQUIRED_APP_PROFILE_KEYS = {
    "brand_name", "brand_description", "app_category", "niche", "platforms",
    "pricing_trial", "core_features", "primary_use_cases", "problems_solved",
    "products_or_services", "target_audience", "ideal_customer_profile",
    "icp_segments", "desired_outcomes", "differentiation", "competitors",
    "known_limitations", "tone_voice", "claims_approved", "claims_review",
    "claims_banned", "ctas", "video_themes",
}

APP_PROFILE_LIST_KEYS = (
    "platforms", "core_features", "primary_use_cases", "problems_solved",
    "products_or_services", "icp_segments", "desired_outcomes", "competitors",
    "claims_approved", "claims_review", "claims_banned", "ctas", "video_themes",
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
    token budget — goes unquestioned. Gemini 2.5 Flash is a thinking model, and
    thought tokens are drawn from the same completion budget, so a large JSON
    schema can exhaust max_tokens before the closing brace is ever written.
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
    if generate_audio:
        payload["generate_audio"] = True

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

    logger.info(
        f"Submitting video generation ({model_config['name']}): duration={payload['duration']}s, "
        f"resolution={payload['resolution']}, has_frame_image={bool(payload.get('frame_images'))}, "
        f"continuity_frame={bool(bridge_frame)}, v2v_mode={use_v2v_mode}, audio={generate_audio}, "
        f"num_references={len(payload.get('input_references', []))}, "
        f"has_v2v_motion={bool(reference_video_url)}, model={model_id}"
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
                raise RuntimeError(human or f"Video generation failed (HTTP {resp.status_code}): {error_text}")
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
        '  "products_or_services": ["short list of specific products or services offered"],\n'
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

    if not isinstance(result.get("products_or_services"), list):
        raw = result.get("products_or_services")
        result["products_or_services"] = [raw] if raw else []

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
        '  "pricing_trial": "pricing and trial info exactly as stated, or empty string if unstated",\n'
        '  "core_features": ["concrete features evidenced by the sources"],\n'
        '  "primary_use_cases": ["top jobs the app helps users do"],\n'
        '  "problems_solved": ["user problems the app removes"],\n'
        '  "products_or_services": ["tiers or offerings, e.g. Free, Pro yearly"],\n'
        '  "target_audience": "short label for the primary audience",\n'
        '  "ideal_customer_profile": "2-4 sentences: who they are, what they struggle with, where they spend time online",\n'
        '  "icp_segments": ["2-4 segments as one-liners: label, functional need, hook promise"],\n'
        '  "desired_outcomes": ["outcomes users want from the app"],\n'
        '  "differentiation": "2-4 sentences on what sets this app apart",\n'
        '  "competitors": ["named competitor apps if inferable, else empty"],\n'
        '  "known_limitations": "material limitations a promo must not contradict (platforms, trial terms, feature gaps)",\n'
        '  "tone_voice": "short description of the brand voice",\n'
        '  "claims_approved": ["factual claims safe to use in promos"],\n'
        '  "claims_review": ["claims that need verification before use (ratings, counts, pricing, results)"],\n'
        '  "claims_banned": ["claims promos must never make (guaranteed outcomes, fake reviews, medical/financial promises)"],\n'
        '  "ctas": ["suitable calls to action, e.g. Try it free, Get it on the App Store"],\n'
        '  "video_themes": ["4-8 suggested short-form video themes for this app"]\n'
        "}\n"
        "Rules: use ONLY functionality evidenced by the sources or notes; never invent "
        "ratings, download counts, prices, or features. Put anything uncertain in "
        "claims_review, never in claims_approved. Keep every list to 8 items max. "
        "Return ONLY valid JSON."
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

    return result


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
      - No guaranteed outcomes, no testimonials, no invented pricing.

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
        "pricing_trial": profile.get("pricing_trial") or "(unstated)",
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
        "ctas": _list("ctas"),
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
        '  "recommended_cta": "one suitable call to action",\n'
        '  "claims_to_respect": ["claims or limitations that bound this angle"]\n'
        "}\n"
        "Rules: use ONLY facts present in the profile. If an angle would require a "
        "claim from claims_needing_review, list that claim in claims_to_respect. Never "
        "promise guaranteed outcomes, invent testimonials or reviews, state pricing that "
        "is not in the profile, or imply a feature the profile does not list. Vary the "
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
            "recommended_cta": (item.get("recommended_cta") or "").strip()[:200],
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


REQUIRED_PLAN_KEYS = {
    "hook_line", "script", "beat_timeline", "visual_direction",
    "feature_emphasis", "overlays", "voice_direction", "sound_direction", "cta",
}


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

    Timeline shape follows the product spec: 0-3s hook, 3-8s problem or
    transition, 8-20s demonstration or payoff, final seconds CTA. Beats are
    scaled to the requested duration rather than hardcoded.

    The prompt directs the model to render the full scene itself — environment,
    setting, props and on-screen context invented concretely from the verified
    facts — because nothing is composited over the footage except captions and
    the end card. On-screen text stays out of the model's hands (captions are
    added afterwards), and anything the viewer could read as a factual claim
    about the app must come from verified facts or stay out of frame.

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
        "pricing_trial": profile.get("pricing_trial") or "(unstated)",
        "features": _list("core_features"),
        "use_cases": _list("primary_use_cases"),
        "problems": _list("problems_solved"),
        "desired_outcomes": _list("desired_outcomes"),
        "differentiators": profile.get("differentiation") or "(unstated)",
        "known_limitations": profile.get("known_limitations") or "(none recorded)",
    }

    structure = {
        "template_name": template.get("name") or "(no template)",
        "hook_category": template.get("category") or "(unstated)",
        "opening_structure": template.get("opening_structure") or "(unstated)",
        "hook_seconds": template.get("hook_seconds") or 3,
        "continuation_structure": template.get("continuation_structure") or "(unstated)",
        "cta_pattern": template.get("cta_pattern") or "(unstated)",
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
        "angle_cta": (angle or {}).get("recommended_cta") or "",
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
        '  "script": "the full spoken script, plain text, no stage directions",\n'
        '  "beat_timeline": [{"start": 0, "end": 3, "label": "hook", "text": "what happens and what is said"}],\n'
        '  "visual_direction": "what the camera shows, as one paragraph",\n'
        '  "feature_emphasis": "the single app feature this video demonstrates and where it appears",\n'
        '  "overlays": [{"start": 0, "end": 3, "text": "on-screen text, max 6 words"}],\n'
        '  "voice_direction": "delivery direction for the voiceover or on-camera talent",\n'
        '  "sound_direction": "sound and music direction, rights-safe (no named commercial tracks)",\n'
        '  "cta": "the single call to action",\n'
        '  "claims_used": ["exact strings from claims.approved that appear in the script"]\n'
        "}\n"
        "Rules:\n"
        f"- beat_timeline MUST follow 0-3s hook, 3-8s problem/transition, 8-{max(8, duration_seconds - 3)}s "
        "demonstration or payoff, and the final seconds CTA. Scale the beats to "
        f"{duration_seconds} seconds total; the hook stays under 3 seconds.\n"
        "- Fill every content_slot in the template with a concrete value for THIS app.\n"
        "- CRITICAL: nothing is composited over the footage except captions and the end "
        "card. Describe the full scene — environment, setting, props and any on-screen "
        "context — concretely from the verified facts above, and keep overlay text to "
        "short phrases. Never invent interface text, button labels, prices, ratings, "
        "logos, testimonials, or anything the viewer could read as a factual claim "
        "about the app. The generated scene is illustrative: the script and CTA must "
        "never claim it shows real app footage or a screen recording.\n"
        "- Use ONLY features, pricing, and claims present above. Never invent a feature, a "
        "price, a rating, a review, a download count, or a user testimonial.\n"
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
        "visual_direction", "feature_emphasis", "voice_direction",
        "sound_direction", "cta",
    ):
        result[key] = (result.get(key) or "").strip()[:1200]

    result["beat_timeline"] = _normalize_beats(result.get("beat_timeline"), duration_seconds)
    result["overlays"] = _normalize_overlays(result.get("overlays"), duration_seconds)
    result["claims_used"] = [str(c).strip() for c in (result.get("claims_used") or []) if str(c).strip()][:8]
    result["duration_seconds"] = duration_seconds
    return result


REQUIRED_STRATEGY_KEYS = {
    "strategy_summary", "audience_problem", "emotional_triggers", "hook_concept",
    "hook_line", "hook_promise", "hook_action", "messaging_pillars",
    "primary_feature", "desired_outcome", "differentiation_beat", "cta_strategy",
    "scene", "performance", "segments", "continuity_contract",
}
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
#
# Seven continuations (eight segments, the normalize cap) is comfortably more
# than the product needs: the longest total is 30s and a single "extend to
# target" costs one or two segments, so the arc is exhausted only by a founder
# deliberately padding the video with minimum-length segments.
CONTINUATION_BEATS = 7


def _continuation_segment_schema(plan_seconds: int) -> str:
    """
    Emit the planned continuation segments as JSON schema text.

    Each beat is a distinct point in the story, not a restatement: the last one
    always lands the CTA so the arc is complete at any stopping point, which is
    what makes stopping early a legitimate choice rather than a truncated video.
    """
    parts = []
    for index in range(1, CONTINUATION_BEATS + 1):
        role = "cta" if index == CONTINUATION_BEATS else "continuation"
        parts.append(
            f',\n    {{"index": {index}, "role": "{role}", "seconds": {plan_seconds}, '
            f'"goal": "what this beat must achieve", '
            f'"script": "the words spoken in THIS beat - different from every other beat", '
            f'"action": "what they do in THIS beat"}}'
        )
    return "".join(parts)

# The sub-objects are where continuity actually lives, so each one is required
# with its own field list rather than being trusted as a free-form blob.
#
# There is deliberately no STRATEGY_CHARACTER_FIELDS. The on-camera person is
# copied from the founder's uploaded character reference image, so a written
# description of their face, hair, age, build or wardrobe is not a fallback —
# it is a fabrication, and it was being sent to the model alongside the
# photograph as a "locked" value. The two disagreed, and the model was told
# both were authoritative, which is how a founder's own face came back as
# somebody else's. The scene and performance directions are plan-level and do
# not conflict with a photograph, so those stay.
STRATEGY_SCENE_FIELDS = (
    "camera_angle", "framing", "lighting", "environment", "background",
    "setting", "visual_style", "character_positioning", "props", "color_palette",
)
STRATEGY_PERFORMANCE_FIELDS = ("movement", "voice_delivery")
STRATEGY_CONTRACT_FIELDS = ("established", "must_not_change", "do_not_repeat")

_STRATEGY_TEXT_LIMITS = {
    "strategy_summary": 900,
    "audience_problem": 700,
    "hook_concept": 700,
    "hook_line": 200,
    "hook_promise": 300,
    "hook_action": 400,
    "hook_dialogue": 400,
    "primary_feature": 400,
    "desired_outcome": 400,
    "differentiation_beat": 400,
    "cta_strategy": 400,
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
            "desired_outcome", "differentiation_beat", "cta_strategy",
        )
    }
    result["emotional_triggers"] = _clean_strategy_list(raw.get("emotional_triggers"), 200)
    result["messaging_pillars"] = _clean_strategy_list(raw.get("messaging_pillars"), 300)

    # No "character" section: see STRATEGY_SCENE_FIELDS for why. An existing
    # project may still carry one from before this change, so it is dropped here
    # rather than trusted — an old fabrication must not reach a new prompt.
    result["scene"] = _normalize_strategy_section(raw.get("scene"), STRATEGY_SCENE_FIELDS)
    result["performance"] = _normalize_strategy_section(raw.get("performance"), STRATEGY_PERFORMANCE_FIELDS)

    contract = raw.get("continuity_contract") if isinstance(raw.get("continuity_contract"), dict) else {}
    result["continuity_contract"] = {
        field: _clean_strategy_list(contract.get(field), 260, cap=8)
        for field in STRATEGY_CONTRACT_FIELDS
    }

    segments = []
    for index, item in enumerate(raw.get("segments") or []):
        if not isinstance(item, dict):
            continue
        try:
            seconds = int(item.get("seconds") or 0)
        except (TypeError, ValueError):
            seconds = 0
        role = _clean_strategy_text(item.get("role") or ("hook" if index == 0 else "continuation"), 40)
        segments.append({
            "index": index,
            "role": role,
            "seconds": max(1, min(seconds or 0, 30)),
            "goal": _clean_strategy_text(item.get("goal"), 400),
            "script": _clean_strategy_text(item.get("script"), 900),
            "action": _clean_strategy_text(item.get("action"), 400),
        })
        if len(segments) >= 8:
            break
    if not segments:
        segments = [{"index": 0, "role": "hook", "seconds": 4, "goal": "", "script": "", "action": ""}]
    result["segments"] = segments
    return result


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
) -> dict:
    """
    Turn an App Profile into a video strategy specific to THIS app.

    This is the step that stops the influencer workflow from producing a
    generic talking-head video with an app name stapled on. It decides the
    hook concept, the messaging, the words, the action and the whole look of
    the scene BEFORE any video is generated, and it writes
    a continuity contract that every later segment is held to.

    The scene section is the continuity contract in concrete form: once the
    first segment locks a background, a light, a camera angle and the
    delivery, the same values are restated for every extension so the
    provider is told what must not change rather than asked to keep it in
    mind. The face is never described anywhere in the strategy — it comes
    from the founder's photograph, which rides along as a model input.

    Returns a normalized strategy dict (see normalize_strategy). Never invents
    features, prices, ratings or outcomes; uncertain claims are pushed to the
    profile's own review tier instead.
    """
    def _list(name):
        val = profile.get(name)
        if isinstance(val, list):
            return [str(v) for v in val if str(v).strip()]
        if val:
            return [str(val)]
        return []

    # A planning hint for how long each continuation beat is expected to run.
    # It is a HINT, not the render length: the founder picks the real length per
    # extension, and a beat's own `seconds` only describes the shape of the
    # arc. Spread across the planned beats so a 20s total with a 4s hook does
    # not plan two-second beats.
    _remaining = max(0, int(total_duration or 0) - int(hook_seconds or 0))
    plan_seconds = (
        max(1, round(_remaining / CONTINUATION_BEATS)) if _remaining else int(hook_seconds or 4)
    )

    facts = {
        "app_name": profile.get("brand_name") or "(unnamed app)",
        "category": profile.get("app_category") or profile.get("niche") or "(unstated)",
        "description": profile.get("brand_description") or "(unstated)",
        "platforms": _list("platforms"),
        "pricing_trial": profile.get("pricing_trial") or "(unstated)",
        "features": _list("core_features"),
        "use_cases": _list("primary_use_cases"),
        "problems": _list("problems_solved"),
        "audience": profile.get("target_audience") or "(unstated)",
        "icp_segments": _list("icp_segments"),
        "outcomes": _list("desired_outcomes"),
        "differentiators": profile.get("differentiation") or "(unstated)",
        "competitors": _list("competitors"),
        "limitations": profile.get("known_limitations") or "(none recorded)",
    }

    mechanism = {
        "template_name": template.get("name") or "(no template)",
        "hook_category": template.get("category") or "(unstated)",
        "objective": objective or "(unstated)",
        "opening_structure": template.get("opening_structure") or "(unstated)",
        "hook_seconds": hook_seconds,
        "continuation_structure": template.get("continuation_structure") or "(unstated)",
        "cta_pattern": template.get("cta_pattern") or "(unstated)",
        "visual_style": template.get("visual_style") or "(unstated)",
        "camera_pacing": template.get("camera_pacing") or "(unstated)",
        "required_assets": _list_of(template, "required_assets"),
        "content_slots": template.get("content_slots") or {},
    }

    brief = {
        "angle_kind": (angle or {}).get("kind") or "(none)",
        "angle_label": (angle or {}).get("label") or "",
        "angle_audience": (angle or {}).get("target_audience") or profile.get("target_audience") or "",
        "angle_problem": (angle or {}).get("user_problem") or "",
        "angle_hook_promise": (angle or {}).get("hook_promise") or "",
        "angle_feature": (angle or {}).get("app_feature") or "",
        "angle_emotion": (angle or {}).get("desired_emotion") or "",
        "angle_cta": (angle or {}).get("recommended_cta") or "",
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

    feedback_context = ""
    if profile_feedback:
        feedback_context = (
            "\n\nPAST FEEDBACK FOR THIS APP (counts and fixed reason codes only):\n"
            f"{feedback.build_profile_feedback_section(profile_feedback)}\n"
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
        f"{feedback_context}\n"
        "Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "strategy_summary": "2-3 sentences on the strategy for THIS app and why it fits THIS audience",\n'
        '  "audience_problem": "the concrete problem this viewer actually has, in their words",\n'
        '  "emotional_triggers": ["2-4 emotions this video should trigger, each tied to this app\'s use case"],\n'
        '  "hook_concept": "what the first seconds DO, visually and dramatically — not a slogan",\n'
        '  "hook_line": "the single spoken hook line, max 12 words",\n'
        '  "hook_promise": "what the hook promises the viewer in the next few seconds",\n'
        '  "hook_action": "the physical action the on-camera person performs during the hook",\n'
        '  "hook_dialogue": "the exact words spoken in the hook, or the delivery direction if none",\n'
        '  "messaging_pillars": ["2-4 things the video must land, derived from this app\'s real features"],\n'
        f'  "primary_feature": "the ONE feature this video shows, from the facts above",\n'
        '  "desired_outcome": "the viewer outcome, described as a change the app supports, never a guarantee",\n'
        '  "differentiation_beat": "how to use this app\'s stated differentiation against its competitors",\n'
        '  "cta_strategy": "the single next action, and why it suits this audience",\n'
        '  "scene": {\n'
        f'    "camera_angle": "the exact camera position and angle, e.g. eye-level handheld 1m away",\n'
        f'    "framing": "framing and shot size, e.g. medium close-up, head and shoulders",\n'
        f'    "lighting": "light direction, quality and colour temperature",\n'
        f'    "environment": "the physical place, named concretely",\n'
        f'    "background": "what is behind them, concretely and unchanging",\n'
        f'    "setting": "time of day and situational context",\n'
        f'    "visual_style": "the overall look — documentary, polished UGC, cinematic",\n'
        f'    "character_positioning": "where they stand or sit in frame",\n'
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
        + _continuation_segment_schema(plan_seconds)
        + '\n  ],\n'
        '  "continuity_contract": {\n'
        '    "established": ["what the opening segment fixes for the rest of the video — 4-6 items. '
        'Setting, lighting, framing, props and action only. Never the presenter\'s face, hair, '
        'skin, age, build, wardrobe or styling: those come from the founder\'s photograph, not '
        'from anything written here."],\n'
        '    "must_not_change": ["setting, lighting, framing, props and wardrobe-that-is-'
        'already-on-screen-in-the-photograph that every later segment must reproduce exactly. '
        'Do NOT list the person\'s face, hair, age, build or styling -- an invented description '
        'of them here contradicts the photograph they are supposed to match."],\n'
        '    "do_not_repeat": ["what the opening already said or showed, so later segments do not say it again"]\n'
        '  }\n'
        "}\n"
        "Rules:\n"
        f"- The opening segment lasts {hook_seconds} seconds and must be the strongest {hook_seconds} seconds "
        f"for THIS app. Write a real hook for this app's real audience, not a generic influencer opening with "
        "the app name dropped in.\n"
        "- The hook must serve the selected hook mechanism. If the mechanism is a question, the hook is a "
        "question; if it is a contrarian correction, the hook corrects something.\n"
        f"- After the hook, plan {CONTINUATION_BEATS} further beats. The founder decides where to stop, so the "
        "beats must work as a sequence AND the last one must land the call to action on its own — a viewer "
        "who sees only the hook and the final beat still gets a complete video.\n"
        "- Give every beat a genuinely different goal, script and action. Beat 1 is not beat 2 restated, and "
        "no two beats may share a script. A repeated beat is worse than a missing one, because it plays the "
        "same clip twice.\n"
        "- Fill every content_slot in the hook mechanism with a concrete value for THIS app, "
        "drawn from the verified facts and the brief above — the feature slot names an actual "
        "feature from core_features, the problem slot the actual audience problem. An unfilled "
        "slot is a generic video.\n"
        "- There is no \"character\" key in this schema and none is wanted: do not add one, "
        "and do not describe the presenter's face, hair, age, build, wardrobe or styling in "
        "any field — not in strategy_summary, not in hook_concept, nowhere. The on-camera "
        "person is copied from the founder's photograph; write about the audience, the "
        "problem, the app and the action instead.\n"
        "- Invent the environment, setting, props and on-screen context concretely from the "
        "verified facts (features, use cases, problems, audience, platforms) — a kitchen "
        "counter at 7am for an evening-reflection app, not \"a nice room\". Nothing is "
        "composited over the footage except captions and the end card, so what the camera "
        "must show has to be written here, in scene, segments and hook_action.\n"
        "- The generated scene is illustrative, never documentary: the script, captions and "
        "CTA must never claim it shows real app footage or a screen recording. Anything the "
        "viewer could read as a factual claim about the app — interface text, button labels, "
        "prices, ratings, logos — must come from the verified facts or stay out of frame.\n"
        "- Make the scene so specific that a second video with the same strategy would be "
        "recognisably the same place. The person's sameness is the photograph's job, not the "
        "text's — never describe them to achieve it. Vague terms like \"casual\" or \"a nice "
        "room\" are not acceptable.\n"
        "- must_not_change must cover the background, the lighting, the framing, the props "
        "and the delivery — the scene attributes a video model will otherwise silently "
        "reinvent. Never the face, hair, age, build or styling: those come from the "
        "founder's photograph, not from anything written here.\n"
        "- Every segment must be satisfiable using only the verified facts above. Put anything that would need a "
        "claim from needs_review into do_not_repeat or omit it entirely.\n"
        "- Never promise a guaranteed outcome, never invent a testimonial, a rating or a review, and never state "
        "pricing that is not in the facts.\n"
        "- Use only approved claims. Never use anything in never_use.\n"
        # Length discipline. This object is large, and an over-long value here
        # is what pushes the reply past the completion budget and gets it cut
        # off mid-object. Concision costs nothing here: the fields are read as
        # locked values restated into a prompt, not as prose.
        "- Keep EVERY string value under 25 words and each list to 2-4 short items. Be specific, not lengthy. "
        "A long value helps nothing and risks the whole object being cut off.\n"
        "- Never use double-quote characters inside any string value: write hook lines and dialogue "
        "without quotation marks. A stray quote breaks the JSON and fails the whole strategy.\n"
        "- Return ONE complete JSON object and nothing else: no prose before or after it, no markdown fence."
    )

    # This is the largest JSON schema in the codebase: ~45 values across five
    # nested objects, several of them prose. Gemini 2.5 Flash is a thinking
    # model and its thought tokens come out of the SAME completion budget, so a
    # budget that looks generous on paper can be exhausted before the closing
    # brace is written. 8192 is the floor that reliably fits this schema.
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


async def abstract_template_drafts(observations: list, app_context: str = "") -> list:
    """
    Ask the model for reusable hook mechanics distilled from public observation.

    Returns the RAW parsed list; research_abstraction.parse_drafts applies the
    identity guard and normalises the result. The prompt lives in
    research_abstraction so the wording sits beside the rules that enforce it.
    """
    import research_abstraction as ra

    prompt = ra.build_abstract_prompt(observations, app_context)
    payload = {
        "model": TEXT_MODEL,
        "messages": [
            {"role": "system", "content": (
                "You extract reusable short-form video mechanics from public trend data. "
                "You describe patterns, never people: no creator identity, no gestures, "
                "no voice, no copyrighted audio, no copied captions. Respond with STRICT "
                "JSON only."
            )},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": 3000,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=_headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

    full_text = data["choices"][0]["message"]["content"]
    return _parse_json_response(full_text, "Template drafts")


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
