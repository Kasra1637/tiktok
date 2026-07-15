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

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

logger = logging.getLogger(__name__)

# Models
VISION_MODEL = "google/gemini-2.5-flash"
IMAGE_GEN_MODEL = "google/gemini-2.5-flash-image"
FACE_SWAP_MODEL = "x-ai/grok-imagine-image-quality"  # Grok Imagine — strong identity preservation, no content filter issues, 2K
TEXT_MODEL = "google/gemini-2.5-flash"

# Video generation models (user-selectable)
VIDEO_MODELS = {
    "seedance-2.0": {
        "id": "bytedance/seedance-2.0",
        "name": "Seedance 2.0",
        "description": "Best quality. Character consistency, native audio, cinematic camera.",
        "max_duration": 15,
    },
    "seedance-2.0-fast": {
        "id": "bytedance/seedance-2.0-fast",
        "name": "Seedance 2.0 Fast",
        "description": "Faster generation, lower cost. Good for previews.",
        "max_duration": 15,
    },
    "wan-2.7": {
        "id": "alibaba/wan-2.7",
        "name": "Wan 2.7",
        "description": "Strong image-to-video. Reference style preservation.",
        "max_duration": 15,
    },
}
DEFAULT_VIDEO_MODEL = "seedance-2.0"
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
        "first 2-3 seconds of a video (given as a sequence of frames in chronological order) "
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
    """Generate a customized face-swapped preview with Gemini 3.1 Flash Image.

    The source photo is cropped to the identity region before being sent as the
    first reference; the original scene remains the second reference.
    """
    if mode == "custom" and customization_prompt.strip():
        scene_instruction = (
            f" Additionally, apply these customizations to the scene: {customization_prompt}."
        )
    else:
        scene_instruction = ""

    ref_b64 = image_to_base64(reference_frame_path)

    # Crop the person photo to just the face region before sending to the model.
    cropped_person_path = crop_face_from_path(person_photo_path)
    person_b64 = image_to_base64(cropped_person_path)

    # Use OpenRouter's dedicated Images API with explicit identity + scene references.
    payload = {
        "model": FACE_SWAP_MODEL,
        "prompt": (
            "I am a content creator. Reference image 1 is my headshot. Reference image 2 is a scene. "
            "Generate a new image of me (from reference 1) placed into the exact scene from reference 2. "
            "Keep my face, hair, and features from reference 1. Match the pose, outfit, background, "
            "lighting, and camera angle from reference 2."
            f"{scene_instruction}"
        ),
        "input_references": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{person_b64}"}},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{ref_b64}"}},
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
) -> bytes:
    """
    Standalone identity-preserving scene edit through OpenRouter's Images API.

    The cropped source identity is reference 1 and the complete target scene is
    reference 2. Gemini 3.1 Flash Image receives both references in one call.
    """
    target_b64 = image_to_base64(target_image_path)

    # Crop the source face image to just the face region before sending to the model.
    cropped_source_path = crop_face_from_path(source_face_path)
    source_b64 = image_to_base64(cropped_source_path)

    payload = {
        "model": FACE_SWAP_MODEL,
        "prompt": (
            "I am a content creator. Reference image 1 is my headshot. Reference image 2 is a scene. "
            "Generate a new image of me (from reference 1) placed into the exact scene from reference 2. "
            "Keep my face, hair, and features from reference 1. Match the pose, outfit, background, "
            "lighting, and camera angle from reference 2."
        ),
        "input_references": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{source_b64}"}},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{target_b64}"}},
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
        "Hook analysis of the original viral video's first 2-3 seconds:\n"
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
        "about to happen — then describe how to animate this into a 5-second silent hook video. "
        "Respond with STRICT JSON only, no markdown fences, no extra commentary."
    )

    prompt = (
        "Here is a still image that will be the first frame of a 5-second TikTok hook video. "
        "Analyze what's in this image and describe how to animate it into an attention-grabbing "
        "silent hook. Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "facial_expressions": "describe the expression visible and how it should evolve over 5 seconds",\n'
        '  "body_language_gestures": "describe the pose/gesture visible and what movement should follow",\n'
        '  "pacing_cuts": "describe the ideal pacing and camera movement for a 5s hook starting from this frame",\n'
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


async def generate_video(prompt: str, reference_image_path: Path = None, duration: int = 5, model: str = None, generate_audio: bool = False) -> dict:
    """Submit a video generation job to OpenRouter. Returns job info for polling.

    Args:
        generate_audio: Whether to generate audio. Defaults to False for hook videos
                       (silent movement-based hooks). Set True for extended videos with voiceover.
    """
    # Resolve model
    if model and model in VIDEO_MODELS:
        model_id = VIDEO_MODELS[model]["id"]
        max_dur = VIDEO_MODELS[model]["max_duration"]
    else:
        model_id = VIDEO_MODELS[DEFAULT_VIDEO_MODEL]["id"]
        max_dur = VIDEO_MODELS[DEFAULT_VIDEO_MODEL]["max_duration"]

    payload = {
        "model": model_id,
        "prompt": prompt,
        "duration": min(duration, max_dur),
        "resolution": "720p",
        "aspect_ratio": "9:16",
        "generate_audio": generate_audio,
    }

    if reference_image_path and reference_image_path.exists():
        b64 = image_to_base64(reference_image_path)
        mime = "image/png"
        payload["frame_images"] = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
                "frame_type": "first_frame",
            }
        ]

    logger.info(
        f"Submitting video generation: model={model_id}, duration={payload['duration']}s, "
        f"has_frame_image={bool(payload.get('frame_images'))}, audio={generate_audio}"
    )

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(f"{OPENROUTER_BASE}/videos", headers=_headers(), json=payload)
        if resp.status_code >= 400:
            error_text = resp.text[:500]
            logger.error(f"Video generation submission failed: HTTP {resp.status_code}: {error_text}")
            raise RuntimeError(f"Video generation failed (HTTP {resp.status_code}): {error_text}")
        return resp.json()


async def poll_video_job(job_id: str) -> dict:
    """Poll a video generation job status."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{OPENROUTER_BASE}/videos/{job_id}",
            headers=_headers(),
        )
        resp.raise_for_status()
        return resp.json()



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
        "Hook analysis of the original viral video's first 2-3 seconds:\n"
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
