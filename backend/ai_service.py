"""
AI service layer using OpenRouter API.
- Vision-based hook analysis via chat/completions
- Face-swap image generation via /images endpoint (Nano Banana)
- Video prompt generation via chat/completions
- Video generation via /videos endpoint (HappyHorse)
"""
import base64
import json
import logging
import os
from pathlib import Path

import httpx

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE = "https://openrouter.ai/api/v1"

logger = logging.getLogger(__name__)

# Models
VISION_MODEL = "google/gemini-2.5-flash"
IMAGE_GEN_MODEL = "google/gemini-2.5-flash-preview-image-generation"
TEXT_MODEL = "google/gemini-2.5-flash"
VIDEO_MODEL = "alibaba/happyhorse-1.1"

REQUIRED_ANALYSIS_KEYS = {
    "facial_expressions", "body_language_gestures", "pacing_cuts",
    "text_overlays_timing", "audio_cues_inferred", "hook_summary",
    "effectiveness_score", "key_hook_frame_index", "replicable_mechanics",
}

REQUIRED_VIDEO_PROMPT_KEYS = {
    "content", "camera_angle", "view_position", "character_behavior",
    "scene_details", "brand_narrative", "full_video_prompt", "suggested_duration_seconds",
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


async def analyze_hook(frame_paths: list, session_id: str) -> dict:
    """Analyze hook frames using OpenRouter vision model."""
    system_message = (
        "You are an expert short-form video (TikTok/Reels) hook analyst. You examine the "
        "first 2-3 seconds of a video (given as a sequence of frames in chronological order) "
        "and identify exactly what makes the hook effective at grabbing attention. "
        "Respond with STRICT JSON only, no markdown fences, no extra commentary."
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
        '  "audio_cues_inferred": "string inferring likely audio cues based on visual context",\n'
        '  "hook_summary": "1-2 sentence summary of why this hook works",\n'
        '  "effectiveness_score": integer 1-10,\n'
        '  "key_hook_frame_index": integer index (1-based) of the single frame that best represents the peak hook moment,\n'
        '  "replicable_mechanics": ["short bullet", "..."] list of concrete mechanics to preserve when recreating this hook\n'
        "}\n"
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
        "max_tokens": 2000,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{OPENROUTER_BASE}/chat/completions", headers=_headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

    full_text = data["choices"][0]["message"]["content"]
    full_text = _clean_json_text(full_text)

    try:
        analysis = json.loads(full_text)
    except json.JSONDecodeError:
        start = full_text.find("{")
        end = full_text.rfind("}")
        if start == -1 or end == -1:
            raise RuntimeError("Hook analysis model did not return valid JSON")
        analysis = json.loads(full_text[start:end + 1])

    missing = REQUIRED_ANALYSIS_KEYS - set(analysis.keys())
    if missing:
        raise RuntimeError(f"Hook analysis missing required fields: {missing}")

    return analysis


async def generate_customized_preview(
    reference_frame_path: Path,
    person_photo_path: Path,
    mode: str,
    customization_prompt: str,
    session_id: str,
) -> bytes:
    """Generate face-swapped preview image using OpenRouter Image API (Nano Banana)."""
    if mode == "custom" and customization_prompt.strip():
        scene_instruction = f"Apply the following customization: {customization_prompt}. "
    else:
        scene_instruction = (
            "Keep the environment, background, lighting, clothing, camera framing, angle, and every other "
            "visual detail EXACTLY as shown in the reference frame. "
        )

    prompt = (
        "Generate a new photorealistic image that keeps the EXACT pose, facial expression, hand gesture, "
        "and body placement from the first reference image (a viral hook frame), but replaces the person's "
        "face/identity with the person from the second reference image. "
        f"{scene_instruction}"
        "Preserve the core hook mechanic (expression + gesture + body position) exactly."
    )

    ref_b64 = image_to_base64(reference_frame_path)
    person_b64 = image_to_base64(person_photo_path)

    payload = {
        "model": IMAGE_GEN_MODEL,
        "prompt": prompt,
        "input_references": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{ref_b64}"}},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{person_b64}"}},
        ],
        "aspect_ratio": "9:16",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{OPENROUTER_BASE}/images", headers=_headers(), json=payload)
        resp.raise_for_status()
        data = resp.json()

    if not data.get("data") or not data["data"][0].get("b64_json"):
        raise RuntimeError("No image returned from generation model.")

    return base64.b64decode(data["data"][0]["b64_json"])


async def generate_video_prompt(analysis: dict, brand_context: dict, target_duration: int, session_id: str) -> dict:
    """Auto-generate a production-ready video prompt from hook analysis + brand context."""
    system_message = (
        "You are an expert short-form video creative director who writes precise, production-ready prompts for "
        "AI video generation models. You take the analyzed 'hook' of a viral video and a brand's context, and "
        "produce a full video generation prompt. Respond with STRICT JSON only, no markdown fences."
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
        "Brand context:\n"
        f"- Brand name: {brand_context.get('brand_name') or '(not provided)'}\n"
        f"- Brand goal: {brand_context.get('brand_goal') or '(not provided)'}\n"
        f"- Brand details: {brand_context.get('brand_details') or '(not provided)'}\n\n"
        f"Target video duration: up to {target_duration} seconds.\n\n"
        "Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "content": "what happens in the video moment by moment",\n'
        '  "camera_angle": "camera angles matching the original hook",\n'
        '  "view_position": "framing/view position",\n'
        '  "character_behavior": "how the character behaves/moves",\n'
        '  "scene_details": "environment/background/lighting/props",\n'
        '  "brand_narrative": "how the video ties into the brand",\n'
        '  "full_video_prompt": "cohesive production-ready prompt (150-300 words)",\n'
        '  "suggested_duration_seconds": integer up to ' + str(target_duration) + "\n"
        "}\n"
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
    full_text = _clean_json_text(full_text)

    try:
        result = json.loads(full_text)
    except json.JSONDecodeError:
        start = full_text.find("{")
        end = full_text.rfind("}")
        if start == -1 or end == -1:
            raise RuntimeError("Video prompt model did not return valid JSON")
        result = json.loads(full_text[start:end + 1])

    missing = REQUIRED_VIDEO_PROMPT_KEYS - set(result.keys())
    if missing:
        raise RuntimeError(f"Video prompt generation missing required fields: {missing}")

    return result


async def generate_video(prompt: str, reference_image_path: Path = None, duration: int = 10) -> dict:
    """Submit a video generation job to OpenRouter (HappyHorse). Returns job info for polling."""
    payload = {
        "model": VIDEO_MODEL,
        "prompt": prompt,
        "duration": min(duration, 15),
        "resolution": "1080p",
        "aspect_ratio": "9:16",
    }

    if reference_image_path and reference_image_path.exists():
        b64 = image_to_base64(reference_image_path)
        payload["frame_images"] = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
                "frame_type": "first_frame",
            }
        ]

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(f"{OPENROUTER_BASE}/videos", headers=_headers(), json=payload)
        resp.raise_for_status()
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
