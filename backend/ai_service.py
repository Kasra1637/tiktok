"""
AI service layer: vision-LLM hook analysis and Gemini Nano Banana
face-swap/customization still-image generation. Both use the Emergent
universal LLM key via the `emergentintegrations` library.
"""
import base64
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
logger = logging.getLogger(__name__)

HOOK_ANALYSIS_MODEL = ("gemini", "gemini-3-flash-preview")
IMAGE_GEN_MODEL = ("gemini", "gemini-3.1-flash-image-preview")

REQUIRED_ANALYSIS_KEYS = {
    "facial_expressions", "body_language_gestures", "pacing_cuts",
    "text_overlays_timing", "audio_cues_inferred", "hook_summary",
    "effectiveness_score", "key_hook_frame_index", "replicable_mechanics",
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
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent, TextDelta, StreamDone

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
        '  "facial_expressions": "string describing facial expressions/micro-expressions observed (surprise, delight, confusion etc)",\n'
        '  "body_language_gestures": "string describing body language and hand gestures (pointing, touching face, sudden movements)",\n'
        '  "pacing_cuts": "string describing pacing and cut speed/escalation across the frames",\n'
        '  "text_overlays_timing": "string describing any on-screen text/elements and when they appear/reveal (or note if none)",\n'
        '  "audio_cues_inferred": "string inferring likely audio cues (tone shifts, pauses, emphasis) based on visual context",\n'
        '  "hook_summary": "1-2 sentence summary of why this hook works",\n'
        '  "effectiveness_score": integer 1-10,\n'
        '  "key_hook_frame_index": integer index (1-based) of the single frame that best represents the peak hook moment,\n'
        '  "replicable_mechanics": ["short bullet", "short bullet", "..."] list of concrete mechanics to preserve when recreating this hook with a different person\n'
        "}\n"
        "Return ONLY valid JSON."
    )

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=system_message,
    ).with_model(*HOOK_ANALYSIS_MODEL)

    image_contents = [ImageContent(image_to_base64(fp)) for fp in frame_paths]
    user_message = UserMessage(text=prompt, file_contents=image_contents)

    full_text = ""
    async for event in chat.stream_message(user_message):
        if isinstance(event, TextDelta):
            full_text += event.content
        elif isinstance(event, StreamDone):
            break

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
    customization_prompt: str,
    session_id: str,
) -> bytes:
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message="You are an expert visual content creator that composites reference images into new photorealistic scenes.",
    )
    chat.with_model(*IMAGE_GEN_MODEL).with_params(modalities=["image", "text"])

    prompt = (
        "Image 1 is a reference frame from a video showing a person's pose, facial expression, "
        "and hand gesture during a viral hook moment. Image 2 is a photo of a different person. "
        "Generate a new photorealistic image that keeps the EXACT pose, facial expression, and hand "
        "gesture from Image 1, but replaces the person's face/identity with the person from Image 2. "
        f"Apply the following customization to environment/background/clothing: {customization_prompt}. "
        "Preserve the core hook mechanic (the expression + gesture) exactly - this is the most "
        "important constraint."
    )

    image_contents = [
        ImageContent(image_to_base64(reference_frame_path)),
        ImageContent(image_to_base64(person_photo_path)),
    ]
    msg = UserMessage(text=prompt, file_contents=image_contents)

    text, images = await chat.send_message_multimodal_response(msg)
    if not images:
        raise RuntimeError(f"No image returned from generation model. {(text or '')[:200]}")

    return base64.b64decode(images[0]["data"])
