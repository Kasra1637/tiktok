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
    mode: str,
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

    if mode == "custom" and customization_prompt.strip():
        scene_instruction = (
            f"Apply the following customization to the environment/background/clothing: {customization_prompt}. "
        )
    else:
        scene_instruction = (
            "Keep the environment, background, lighting, clothing, camera framing, angle, and every other "
            "visual detail EXACTLY as shown in Image 1 - do not change anything about the scene, placement, "
            "or styling. "
        )

    prompt = (
        "Image 1 is a reference frame from a video showing a person's exact pose, facial expression, and hand "
        "gesture during a viral hook moment (e.g. lying on a bed, a hand touching the mouth, wide eyes, an open "
        "mouth, etc). Image 2 is a photo of a different person. Generate a new photorealistic image that keeps "
        "the EXACT pose, facial expression, hand gesture, and body placement from Image 1 permanently unchanged, "
        "but replaces the person's face/identity with the person from Image 2. "
        f"{scene_instruction}"
        "Preserve the core hook mechanic (the expression + gesture + body position + placement) exactly - this "
        "is the most important constraint and must never be altered."
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


REQUIRED_BRAND_ANALYSIS_KEYS = {
    "brand_name", "brand_overview", "unique_selling_propositions",
    "brand_voice_tone", "target_audience",
}


async def analyze_brand_website(site: dict, session_id: str) -> dict:
    """
    Derive structured brand context (overview, USPs, voice/tone, target
    audience) from a brand's own website content. `site` is the dict
    returned by brand_analysis.fetch_website_text().
    """
    from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

    system_message = (
        "You are an expert brand strategist and copywriter. Given the raw text scraped from a brand's "
        "website, you distill it into a concise, actionable brand brief for a short-form video creative team. "
        "Be specific and concrete - avoid generic marketing filler. If the site text does not clearly support "
        "a field, make a reasonable best-effort inference from context rather than leaving it empty. "
        "Respond with STRICT JSON only, no markdown fences, no extra commentary."
    )

    prompt = (
        f"Website URL: {site.get('url')}\n"
        f"Page title: {site.get('title') or '(none)'}\n"
        f"Meta description: {site.get('meta_description') or '(none)'}\n\n"
        "Extracted page text:\n"
        f"{site.get('text')}\n\n"
        "Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "brand_name": "the brand/company name",\n'
        '  "brand_overview": "2-4 sentence plain-English summary of what the brand does, who it serves, and what it sells",\n'
        '  "unique_selling_propositions": ["short bullet", "short bullet", "..."] list of 3-5 concrete USPs / differentiators,\n'
        '  "brand_voice_tone": "short description of the brand\'s voice and tone (e.g. playful and irreverent, premium and minimal, warm and reassuring)",\n'
        '  "target_audience": "short description of the primary target audience/customer persona"\n'
        "}\n"
        "Return ONLY valid JSON."
    )

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=system_message,
    ).with_model("openai", "gpt-5.4")

    full_text = ""
    async for event in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(event, TextDelta):
            full_text += event.content
        elif isinstance(event, StreamDone):
            break

    full_text = _clean_json_text(full_text)
    try:
        result = json.loads(full_text)
    except json.JSONDecodeError:
        start = full_text.find("{")
        end = full_text.rfind("}")
        if start == -1 or end == -1:
            raise RuntimeError("Brand analysis model did not return valid JSON")
        result = json.loads(full_text[start:end + 1])

    missing = REQUIRED_BRAND_ANALYSIS_KEYS - set(result.keys())
    if missing:
        raise RuntimeError(f"Brand website analysis missing required fields: {missing}")

    if not isinstance(result.get("unique_selling_propositions"), list):
        result["unique_selling_propositions"] = [str(result["unique_selling_propositions"])]

    return result


REQUIRED_VIDEO_PROMPT_KEYS = {
    "content", "camera_angle", "view_position", "character_behavior",
    "scene_details", "brand_narrative", "full_video_prompt", "suggested_duration_seconds",
}


async def generate_video_prompt(analysis: dict, brand_context: dict, target_duration: int, session_id: str) -> dict:
    """Auto-generate a production-ready video prompt from the hook analysis + brand context."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

    system_message = (
        "You are an expert short-form video creative director who writes precise, production-ready prompts for "
        "AI image-to-video generation models. You take the analyzed 'hook' (the juicy emotional/attention-grabbing "
        "moment) of a viral video and a brand's context, and produce a full video generation prompt that recreates "
        "the same content, camera angle, view position, character behavior, and scene details from the hook, then "
        "extends the narrative to serve the brand's goal. Respond with STRICT JSON only, no markdown fences."
    )

    prompt = (
        "Hook analysis of the original viral video's first 2-3 seconds (the 'juicy' emotional hook):\n"
        f"- Facial expressions/micro-expressions: {analysis.get('facial_expressions')}\n"
        f"- Body language & gestures: {analysis.get('body_language_gestures')}\n"
        f"- Pacing & cuts: {analysis.get('pacing_cuts')}\n"
        f"- Text overlays & timing: {analysis.get('text_overlays_timing')}\n"
        f"- Audio cues (inferred): {analysis.get('audio_cues_inferred')}\n"
        f"- Hook summary: {analysis.get('hook_summary')}\n"
        f"- Replicable mechanics: {analysis.get('replicable_mechanics')}\n\n"
        "Brand context to weave into the rest of the video:\n"
        f"- Brand name: {brand_context.get('brand_name') or '(not provided)'}\n"
        f"- Brand goal: {brand_context.get('brand_goal') or '(not provided)'}\n"
        f"- Brand details: {brand_context.get('brand_details') or '(not provided)'}\n"
        f"- Brand overview: {brand_context.get('brand_overview') or '(not provided)'}\n"
        f"- Unique selling propositions: {brand_context.get('unique_selling_propositions') or '(not provided)'}\n"
        f"- Brand voice & tone: {brand_context.get('brand_voice_tone') or '(not provided)'}\n"
        f"- Target audience: {brand_context.get('target_audience') or '(not provided)'}\n\n"
        f"Target video duration: up to {target_duration} seconds.\n\n"
        "Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "content": "what happens in the video, moment by moment, starting from the exact hook moment",\n'
        '  "camera_angle": "camera angle(s), matching the original hook then evolving naturally",\n'
        '  "view_position": "framing/view position (close-up, POV, etc.), matching the original hook",\n'
        '  "character_behavior": "how the character behaves/moves, preserving the original hook mechanics (pose, gesture, expression) at the start",\n'
        '  "scene_details": "environment/background/lighting/props details, consistent with the reference image(s)",\n'
        '  "brand_narrative": "how the video narrative ties into the brand goal, message, unique selling propositions, and target audience after the hook, written in the brand\'s voice & tone if provided",\n'
        '  "full_video_prompt": "a single, cohesive, production-ready prompt string (150-300 words) combining all of the above, ready to feed directly into an image-to-video AI model",\n'
        '  "suggested_duration_seconds": integer up to ' + str(target_duration) + "\n"
        "}\n"
        "Return ONLY valid JSON."
    )

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=system_message,
    ).with_model("openai", "gpt-5.4")

    full_text = ""
    async for event in chat.stream_message(UserMessage(text=prompt)):
        if isinstance(event, TextDelta):
            full_text += event.content
        elif isinstance(event, StreamDone):
            break

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
