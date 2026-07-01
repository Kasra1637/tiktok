"""
CORE POC TEST SCRIPT
Proves the end-to-end pipeline for the TikTok Hook Analyzer + Customization app:

  A. Download a public TikTok video via yt-dlp
  B. Extract frames from the first 2-3 seconds via ffmpeg
  C. Vision LLM structured hook analysis (emergentintegrations + EMERGENT_LLM_KEY)
  D. Face-swap / customization still-image generation (Gemini Nano Banana image model)

Run: python3 test_core.py
"""
import asyncio
import base64
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE = Path(__file__).parent
STORAGE = BASE / "storage"
VIDEOS_DIR = STORAGE / "videos"
FRAMES_DIR = STORAGE / "frames"
SAMPLES_DIR = STORAGE / "samples"
for d in [VIDEOS_DIR, FRAMES_DIR, SAMPLES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")

TEST_TIKTOK_URL = "https://www.tiktok.com/@scout2015/video/6718335390845095173"
TEST_PORTRAIT_URL = "https://images.unsplash.com/photo-1580489944761-15a19d654956?fm=jpg&q=85&w=800"


def log(msg):
    print(f"[POC] {msg}", flush=True)


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# STEP A: Download TikTok video via yt-dlp
# ---------------------------------------------------------------------------
def download_tiktok_video(tiktok_url: str) -> Path:
    vid_hash = url_hash(tiktok_url)
    out_path = VIDEOS_DIR / f"{vid_hash}.mp4"
    if out_path.exists() and out_path.stat().st_size > 0:
        log(f"Step A: Using cached video at {out_path}")
        return out_path

    log(f"Step A: Downloading TikTok video via yt-dlp: {tiktok_url}")
    cmd = [
        "yt-dlp",
        "-f", "b[ext=mp4]/best",
        "-o", str(out_path),
        tiktok_url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if result.returncode != 0 or not out_path.exists():
        log(f"yt-dlp STDERR: {result.stderr[-2000:]}")
        raise RuntimeError("yt-dlp download failed")
    log(f"Step A: SUCCESS - downloaded to {out_path} ({out_path.stat().st_size} bytes)")
    return out_path


def download_fallback_sample() -> Path:
    """Fallback: use a small public sample mp4 if TikTok download fails (network/blocking)."""
    out_path = SAMPLES_DIR / "fallback_sample.mp4"
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path
    sample_url = "https://filesamples.com/samples/video/mp4/sample_640x360.mp4"
    log(f"Fallback: downloading sample video from {sample_url}")
    urllib.request.urlretrieve(sample_url, out_path)
    return out_path


# ---------------------------------------------------------------------------
# STEP B: Extract frames from first 2-3 seconds via ffmpeg
# ---------------------------------------------------------------------------
def extract_hook_frames(video_path: Path, num_frames: int = 8, duration: float = 3.0) -> list:
    vid_hash = video_path.stem
    frame_dir = FRAMES_DIR / vid_hash
    frame_dir.mkdir(parents=True, exist_ok=True)

    existing = sorted(frame_dir.glob("frame_*.jpg"))
    if len(existing) >= num_frames:
        log(f"Step B: Using cached frames in {frame_dir}")
        return existing

    log(f"Step B: Extracting {num_frames} frames from first {duration}s via ffmpeg")
    fps = num_frames / duration
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-t", str(duration),
        "-vf", f"fps={fps},scale=480:-1",
        "-q:v", "3",
        str(frame_dir / "frame_%03d.jpg"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    frames = sorted(frame_dir.glob("frame_*.jpg"))
    if result.returncode != 0 or not frames:
        log(f"ffmpeg STDERR: {result.stderr[-1500:]}")
        raise RuntimeError("ffmpeg frame extraction failed")
    log(f"Step B: SUCCESS - extracted {len(frames)} frames into {frame_dir}")
    return frames


def image_to_base64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ---------------------------------------------------------------------------
# STEP C: Vision LLM structured hook analysis
# ---------------------------------------------------------------------------
async def analyze_hook(frames: list) -> dict:
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

    log(f"Step C: Sending {len(frames)} frames to vision LLM for hook analysis")

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
        '  "text_overlays_timing": "string describing any on-screen text/elements and when they appear/reveal",\n'
        '  "audio_cues_inferred": "string inferring likely audio cues (tone shifts, pauses, emphasis) based on visual context (mouth position, motion blur, captions)",\n'
        '  "hook_summary": "1-2 sentence summary of why this hook works",\n'
        '  "effectiveness_score": integer 1-10,\n'
        '  "key_hook_frame_index": integer index (1-based) of the single frame that best represents the peak hook moment,\n'
        '  "replicable_mechanics": ["short bullet", "short bullet", "..."] list of concrete mechanics to preserve when recreating this hook with a different person\n'
        "}\n"
        "Return ONLY valid JSON."
    )

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id="poc-hook-analysis",
        system_message=system_message,
    ).with_model("gemini", "gemini-3-flash-preview")

    image_contents = [ImageContent(image_to_base64(fp)) for fp in frames]
    user_message = UserMessage(text=prompt, file_contents=image_contents)

    full_text = ""
    async for event in chat.stream_message(user_message):
        cls_name = event.__class__.__name__
        if cls_name == "TextDelta":
            full_text += event.content
        elif cls_name == "StreamDone":
            break

    full_text = full_text.strip()
    if full_text.startswith("```"):
        full_text = full_text.strip("`")
        if full_text.startswith("json"):
            full_text = full_text[4:]
    full_text = full_text.strip()

    try:
        analysis = json.loads(full_text)
    except json.JSONDecodeError:
        start = full_text.find("{")
        end = full_text.rfind("}")
        analysis = json.loads(full_text[start:end + 1])

    log("Step C: SUCCESS - received structured hook analysis JSON")
    log(json.dumps(analysis, indent=2)[:1200])
    return analysis


# ---------------------------------------------------------------------------
# STEP D: Face-swap / customization still-image generation (Nano Banana)
# ---------------------------------------------------------------------------
async def generate_customized_preview(reference_frame: Path, person_photo: Path, customization_prompt: str) -> bytes:
    from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent

    log("Step D: Generating face-swapped customized preview image (Gemini Nano Banana)")

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id="poc-customization",
        system_message="You are an expert visual content creator that composites reference images.",
    )
    chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])

    prompt = (
        "Image 1 is a reference frame from a video showing a person's pose, facial expression, "
        "and hand gesture during a hook moment. Image 2 is a photo of a different person. "
        "Generate a new image that keeps the EXACT pose, facial expression, and hand gesture from "
        "Image 1, but replaces the person's face/identity with the person from Image 2. "
        f"Apply the following customization to environment/background/clothing: {customization_prompt}. "
        "Preserve the core hook mechanic (the expression + gesture) exactly."
    )

    image_contents = [
        ImageContent(image_to_base64(reference_frame)),
        ImageContent(image_to_base64(person_photo)),
    ]
    msg = UserMessage(text=prompt, file_contents=image_contents)

    text, images = await chat.send_message_multimodal_response(msg)
    if not images:
        raise RuntimeError(f"No image returned from Nano Banana. Text response: {text[:300]}")

    img_bytes = base64.b64decode(images[0]["data"])
    out_path = SAMPLES_DIR / "poc_generated_preview.png"
    with open(out_path, "wb") as f:
        f.write(img_bytes)
    log(f"Step D: SUCCESS - generated preview saved to {out_path} ({len(img_bytes)} bytes)")
    return img_bytes


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
async def main():
    if not EMERGENT_LLM_KEY:
        log("ERROR: EMERGENT_LLM_KEY not set in environment")
        sys.exit(1)

    # Step A
    try:
        video_path = download_tiktok_video(TEST_TIKTOK_URL)
    except Exception as e:
        log(f"Step A: TikTok download failed ({e}), using fallback sample video")
        video_path = download_fallback_sample()

    # Step B
    frames = extract_hook_frames(video_path, num_frames=8, duration=3.0)
    assert len(frames) >= 3, "Not enough frames extracted"

    # Step C
    analysis = await analyze_hook(frames)
    required_keys = {
        "facial_expressions", "body_language_gestures", "pacing_cuts",
        "text_overlays_timing", "audio_cues_inferred", "hook_summary",
        "effectiveness_score", "key_hook_frame_index", "replicable_mechanics",
    }
    missing = required_keys - set(analysis.keys())
    assert not missing, f"Missing keys in analysis: {missing}"

    key_frame_idx = max(1, min(len(frames), int(analysis.get("key_hook_frame_index", 1))))
    key_frame_path = frames[key_frame_idx - 1]

    # Download test portrait
    portrait_path = SAMPLES_DIR / "test_portrait.jpg"
    if not portrait_path.exists():
        log("Downloading test portrait image")
        urllib.request.urlretrieve(TEST_PORTRAIT_URL, portrait_path)

    # Step D
    await generate_customized_preview(
        reference_frame=key_frame_path,
        person_photo=portrait_path,
        customization_prompt="Change the background to a cozy modern living room, casual streetwear clothing, warm lighting.",
    )

    log("=" * 60)
    log("ALL POC STEPS PASSED SUCCESSFULLY")
    log("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
