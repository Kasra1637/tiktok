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
import os
from pathlib import Path
from typing import Optional

import httpx

from face_crop import crop_face_from_path
from template_library import CONTENT_ANGLE_KINDS, normalize_angle_kind

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

logger = logging.getLogger(__name__)

# Models
VISION_MODEL = "google/gemini-2.5-flash"
IMAGE_GEN_MODEL = "google/gemini-2.5-flash-image"
FACE_SWAP_MODEL = "google/gemini-3.1-flash-image"  # Gemini 3.1 Flash Image — reliable face identity transfer, up to 14 input references, up to 4K
TEXT_MODEL = "google/gemini-2.5-flash"

# Video generation models.
# Seedance 2.5 is the default for hook replication (V2V motion transfer).
# It supports up to 50 multimodal references (30 images, 10 videos, 10 audio),
# allowing the motion reference (video) and identity reference (face image) to
# coexist without the frame_images/input_references conflict that MiniMax H3 has.
# Built by ByteDance (TikTok's parent), it's designed specifically for short-form
# hook-style content with precise motion/gesture/camera replication from a source clip.
VIDEO_MODELS = {
    "aleph-2": {
        "id": "runway/aleph-2",
        "name": "Runway Aleph 2.0",
        "description": (
            "In-context video EDITING (not generation) — edits the original hook video "
            "directly, preserving body movement, gestures, camera, clothing, and framing "
            "pixel-for-pixel, changing only the face. The closest thing to exact hook "
            "replication available: it never regenerates the scene."
        ),
        "max_duration": 30,
        "min_duration": 2,
        "supports_references": True,
        "supports_native_audio": False,
        "supports_v2v_motion": False,  # not motion transfer — direct video editing
        "resolution": "1080p",
        "is_video_editor": True,  # fundamentally different request shape — see generate_video()
    },
    "seedance-2.5": {
        "id": "bytedance/seedance-2.5",
        "name": "Seedance 2.5",
        "description": "30s one-pass video with motion reference control. Up to 50 multimodal refs, native audio.",
        "max_duration": 30,
        "min_duration": 4,
        "supports_references": True,
        "supports_native_audio": True,
        "supports_v2v_motion": True,
        "resolution": "720p",
        "supports_combined_refs": True,  # Can use frame_images + input_references together
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
# Generative fallback used when there's no source video to edit, or the user
# customized the hook (style/prompt/template) — Aleph cannot text-generate,
# it can only edit footage that already exists.
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
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    candidate = _extract_balanced_object(cleaned)
    if candidate:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    logger.error(
        f"{context}: model did not return valid JSON. Raw response (first 1500 chars): "
        f"{full_text[:1500]!r}"
    )
    raise RuntimeError(f"{context} did not return valid JSON")


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
        b64 = image_to_base64(fp)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
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
    ref_b64 = image_to_base64(reference_frame_path)

    # Crop the person photo to just the face region before sending to the model.
    cropped_person_path = crop_face_from_path(person_photo_path)
    person_b64 = image_to_base64(cropped_person_path)

    # Use OpenRouter's dedicated Images API with explicit identity + scene references.
    payload = {
        "model": FACE_SWAP_MODEL,
        "prompt": _build_face_swap_prompt(
            customization_prompt if mode == "custom" else ""
        ),
        "input_references": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{ref_b64}"}},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{person_b64}"}},
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
    target_b64 = image_to_base64(target_image_path)

    # Crop the source face image to just the face region before sending to the model.
    cropped_source_path = crop_face_from_path(source_face_path)
    source_b64 = image_to_base64(cropped_source_path)

    payload = {
        "model": FACE_SWAP_MODEL,
        "prompt": _build_face_swap_prompt(customization_prompt),
        "input_references": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{target_b64}"}},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{source_b64}"}},
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
    b64 = image_to_base64(image_path)

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
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
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

    Unlike generative models (Seedance, MiniMax H3), Aleph does not synthesize
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
            "video is available for this generation. Fall back to a generative "
            "model (Seedance 2.5 or MiniMax H3) instead."
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
        b64 = image_to_base64(face_anchor_path)
        payload["frame_images"] = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
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
                          V2V motion transfer mode. For Seedance 2.5, both the face
                          image (as first_frame) and the video motion reference can
                          coexist in the same request. For MiniMax H3, the face image
                          is moved to input_references (as identity guide) since H3
                          cannot combine frame_images with input_references.
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
    # Both Seedance 2.5 and MiniMax H3 via OpenRouter CANNOT combine frame_images
    # with input_references (BytePlus returns TaskTypeConstraint error, MiniMax
    # returns a 400). The strategy for V2V mode is the same for both:
    #   - Face image → input_references (as image ref for identity guidance)
    #   - Video → input_references (as video ref for motion replication)
    #   Both coexist in input_references without conflict.
    #
    # When NOT in V2V mode (no reference video):
    #   - Face image → frame_images (first_frame) for hard identity anchor
    #   - No input_references needed

    # First frame: the face-swapped image anchors identity throughout the video.
    # In V2V mode, we skip frame_images and put the image in input_references instead.
    if reference_image_path and reference_image_path.exists() and not use_v2v_mode:
        b64 = image_to_base64(reference_image_path)
        mime = "image/png"
        payload["frame_images"] = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
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

    # Safety: if frame_images is set AND refs exist, drop refs to avoid the
    # TaskTypeConstraint error. This shouldn't happen with the logic above
    # (frame_images is only set when NOT in V2V mode), but guard against it.
    if payload.get("frame_images") and refs:
        logger.warning(
            f"Cannot combine frame_images + input_references — "
            f"dropping {len(refs)} reference(s) to keep first-frame identity anchor."
        )
        refs = []

    if refs:
        payload["input_references"] = refs

    logger.info(
        f"Submitting video generation ({model_config['name']}): duration={payload['duration']}s, "
        f"resolution={payload['resolution']}, has_frame_image={bool(payload.get('frame_images'))}, "
        f"v2v_mode={use_v2v_mode}, audio={generate_audio}, "
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
                raise RuntimeError(f"Video generation failed (HTTP {resp.status_code}): {error_text}")
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
