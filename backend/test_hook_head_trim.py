"""
Tests for the hook head trim and the hook opening direction (ADR 0250).

The claims under test:
  * A Hook + CTA hook render opens with the model's blurry dissolve
    for longer than the 0.2s the regular head trim (ADR 0181) cuts —
    Kasra's live 4s hook still showed it. A hook-surface render whose
    beat sits below the provider floor (the shape that records a
    tail trim) now takes a 0.5s head cut on BOTH models, composed
    with the beat tail cut so the delivered length is still exactly
    the pick. The 0.5s value is derived from the codebase's own
    precedent — posters.py takes the poster frame at 0.5s, "past a
    possible black first frame" — not measured from Kasra's file,
    which is hosted elsewhere and cannot be read from here.
  * The regular renders' head trim is untouched: HeyGen 0.2s, every
    other model none — the 0.2 vs 0.25 question for long renders is
    Kasra's open call, not this change's.
  * A hook rendered AT the floor (a 5s pick, no tail trim recorded)
    keeps its exact length: there is no tail to give the head cut
    back, and the page's promise is the picked length (ADR 0244).
  * The hook's render direction chain names the opening a PHYSICAL
    action: generate_hook_line's hook_action instruction refuses a
    face-only change as the opening beat, the stored strategy
    positions the presenter waist-up with hands and body in frame,
    and the assembled render prompt for a hook-surface plan carries
    the physical-opening requirement and the real-scene requirement
    (a plain or white backdrop is a failed render). A regular plan's
    prompt carries neither — its text is unchanged.
"""
import asyncio
import importlib
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

ANON = "anonymous"

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
needs_ffmpeg = pytest.mark.skipif(
    not (FFMPEG and FFPROBE), reason="ffmpeg/ffprobe not on PATH"
)


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-hookhead-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""

    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    original = (server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR)
    server.pipeline.VIDEOS_DIR = Path(tmpdir) / "videos"
    server.pipeline.GENERATED_DIR = Path(tmpdir) / "generated"
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    server.pipeline.GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    asyncio.run(server.init_db())
    try:
        yield server
    finally:
        server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR = original
        sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


def _profile(api, name):
    from models import ApproveAppProfileRequest, BrandProfileCreateRequest
    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name, app_category="Wellness",
        brand_description="Speak your journal entry instead of writing it.",
        target_audience="people too tired to write at night",
        core_features=["Voice entries"],
        usage_moments=["Winding down after work"],
        outcome_statements=[{
            "outcome": "Clearing the day's thoughts out loud",
            "who_feels_it": "people too tired to write",
            "from_feature": "Voice entries",
            "how_it_helps": "Talking replaces writing the entry",
        }],
    ), user_id=ANON))
    _run(api.approve_app_profile(
        profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON))
    return profile


def _hook_cta_project(api, name):
    from models import CreateHookCtaProjectRequest
    profile = _profile(api, name)
    return _run(api.create_hook_cta_project(payload=CreateHookCtaProjectRequest(
        brand_profile_id=profile["id"],
    ), user_id=ANON))


def _video_project(api, name):
    from models import CreateStudioProjectRequest
    profile = _profile(api, name)
    return _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"]), user_id=ANON))


def _duration(path: Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(re.search(r"[\d.]+", out.stdout).group())


def _make_marked_clip(path: Path, seconds: int = 5, head: float = 0.5) -> Path:
    """
    A clip whose first `head` seconds are marked in BOTH streams:
    red frames and silence. Past the head: blue frames and a loud
    880Hz tone. A head cut at the right offset — and only a cut of
    both streams together — leaves a clip that starts blue and loud.
    The head here is 0.5s, the dissolve length ADR 0250 derives.
    """
    tail = seconds - head
    subprocess.run([
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"color=c=red:size=360x640:rate=30:duration={head}",
        "-f", "lavfi", "-i", f"color=c=blue:size=360x640:rate=30:duration={tail}",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-f", "lavfi", "-i", f"sine=frequency=880:duration={tail}:sample_rate=48000",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[vv];"
                           f"[2:a]atrim=duration={head}[ha];"
                           "[ha][3:a]concat=n=2:v=0:a=1[aa]",
        "-map", "[vv]", "-map", "[aa]",
        "-c:v", "libx264", "-g", "60", "-keyint_min", "60", "-sc_threshold", "0",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path),
    ], check=True, capture_output=True)
    return path


def _first_frame_rgb(path: Path) -> tuple:
    """The center pixel of the frame at 0.05s, as (r, g, b)."""
    out = subprocess.run(
        [FFMPEG, "-v", "error", "-ss", "0.05", "-i", str(path),
         "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    )
    probe = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    width, height = [int(x) for x in probe.stdout.strip().split(",")[:2]]
    frame = out.stdout
    center = ((height // 2) * width + (width // 2)) * 3
    return tuple(frame[center:center + 3])


def _opening_audio_rms(path: Path, seconds: float = 0.15) -> float:
    """RMS amplitude of the clip's first `seconds` of audio (0 = silence)."""
    tmp = path.with_suffix(".head.wav")
    subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-i", str(path), "-t", str(seconds),
         "-ac", "1", "-ar", "48000", str(tmp)],
        check=True, capture_output=True,
    )
    with wave.open(str(tmp), "rb") as wav:
        frames = wav.readframes(wav.getnframes())
    samples = struct.unpack(f"<{len(frames) // 2}h", frames)
    if not samples:
        return 0.0
    return (sum(s * s for s in samples) / len(samples)) ** 0.5


def _persist(api, monkeypatch, tmp: Path, generation_id: str,
             project_id: str, target: int, model: str, trim_to: int = 0,
             requested: int = 0, render_seconds: int = 5):
    """Run the real persist pipeline for one fresh provider download
    of a marked clip (0.5s red/silent head, blue/loud after)."""
    source = _make_marked_clip(tmp / f"{generation_id}-source.mp4", render_seconds)
    row = {
        "id": generation_id,
        "model": model,
        "duration": target,
        "requested_duration": requested,
        "trim_to_seconds": trim_to,
        "video_url": "https://provider.example/render.mp4",
        "openrouter_job_id": f"job-{generation_id}",
        "r2_url": "",
        "studio_project_id": project_id,
        "camera_setup": "handheld",
    }

    async def fake_download(url, gid):
        target_path = api.pipeline.VIDEOS_DIR / f"{gid}.mp4"
        shutil.copyfile(source, target_path)
        return target_path, None

    monkeypatch.setattr("server._download_generation_video", fake_download)
    monkeypatch.setattr(
        "server.storage_service.upload_video",
        lambda user_id, gid, path: f"https://storage.example/{gid}.mp4",
    )
    stored_url, storage_error, delivered = _run(
        api._persist_generation_clip(row, ANON, "https://provider.example/render.mp4")
    )
    canonical = api.pipeline.VIDEOS_DIR / f"{generation_id}.mp4"
    return canonical, stored_url, storage_error, delivered


@needs_ffmpeg
class TestHookHeadTrimPersist:
    def test_minimax_hook_opens_past_the_dissolve(self, api, monkeypatch, tmp_path):
        """MiniMax H3 Max has no entry in the regular head-trim table
        at all: before ADR 0250 a 4s hook from it kept the whole
        dissolve. Now the hook head cut takes the full 0.5s marked
        head, and the beat tail cut still lands the pick exactly."""
        project = _hook_cta_project(api, "Hook Head MiniMax")
        canonical, stored_url, storage_error, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-hook-head-mm", project["id"],
            target=4, model="minimax-h3-max", trim_to=4, requested=4)
        assert stored_url == "https://storage.example/gen-hook-head-mm.mp4"
        assert not storage_error
        assert abs(_duration(canonical) - 4.0) < 0.06, _duration(canonical)
        r, g, b = _first_frame_rgb(canonical)
        assert b > 120 and r < 90, (r, g, b)
        assert _opening_audio_rms(canonical) > 1000
        assert delivered == 4

    def test_heygen_hook_opens_past_the_dissolve(self, api, monkeypatch, tmp_path):
        """The regular 0.2s cut leaves 0.3s of the marked head in
        frame; the hook cut takes the whole dissolve on HeyGen too."""
        project = _hook_cta_project(api, "Hook Head HeyGen")
        canonical, _stored, storage_error, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-hook-head-hg", project["id"],
            target=4, model="heygen-video-1", trim_to=4, requested=4)
        assert not storage_error
        assert abs(_duration(canonical) - 4.0) < 0.06, _duration(canonical)
        r, g, b = _first_frame_rgb(canonical)
        assert b > 120 and r < 90, (r, g, b)
        assert _opening_audio_rms(canonical) > 1000
        assert delivered == 4

    def test_the_hook_value_and_the_regular_table(self, api):
        """The hook value is its own constant, and the regular table
        is byte-for-byte ADR 0181's: the long renders' 0.2s is not
        this change's to move."""
        assert api._HOOK_HEAD_TRIM_SECONDS == 0.5
        assert api._MODEL_HEAD_TRIM_SECONDS == {"heygen-video-1": 0.2}

    def test_five_second_hook_at_the_floor_keeps_its_exact_length(
            self, api, monkeypatch, tmp_path):
        """A 5s pick renders at the models' 5s floor, so no tail
        trim is recorded and there is no tail to give a head cut
        back: the delivered length stays the pick, exactly (the
        page's promise, ADR 0244), rather than landing at 4.5s."""
        project = _hook_cta_project(api, "Hook Head Floor")
        canonical, _stored, storage_error, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-hook-head-floor", project["id"],
            target=5, model="minimax-h3-max", trim_to=0, requested=5)
        assert not storage_error
        assert abs(_duration(canonical) - 5.0) < 0.06, _duration(canonical)
        assert delivered == 5

    def test_a_regular_render_keeps_the_old_head(self, api, monkeypatch, tmp_path):
        """A wizard render (no hook surface) on HeyGen still takes
        only ADR 0181's 0.2s: at 0.05s into the delivered file the
        marked head (0.5s long) is still in frame, and the file is
        the render minus 0.2s — the hook's longer cut does not leak
        into the regular path."""
        project = _video_project(api, "Hook Head Regular")
        canonical, _stored, _err, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-hook-head-regular", project["id"],
            target=5, model="heygen-video-1", trim_to=0, requested=5)
        assert abs(_duration(canonical) - 4.8) < 0.06, _duration(canonical)
        r, g, b = _first_frame_rgb(canonical)
        assert r > 120 and b < 90, (r, g, b)
        assert delivered == int(5 - 0.2)


# ------------------------------------------------------------ the prompt

HOOK_STRATEGY = {
    "hook_concept": "I'm trying to journal tonight and I keep stalling.",
    "hook_promise": "",
    "strategy_summary": "",
    "audience_problem": "",
    "segments": [
        {
            "index": 0, "role": "hook", "seconds": 4,
            "goal": "Open on the goal",
            "script": "I'm trying to journal tonight and I keep stalling.",
            "action": "Hand already moving, pen scratching across the notebook page.",
        },
        {
            "index": 1, "role": "middle", "seconds": 1,
            "goal": "Hold the moment for the demo",
            "script": "",
            "action": "Looks up from the page, pen still in hand.",
        },
    ],
    "scene": {
        "location": "A tidy desk with a notebook",
        "camera_angle": "", "framing": "", "lighting": "",
        "visual_style": "", "character_positioning": "",
        "wardrobe": "Comfortable cream knit top",
        "props": "", "color_palette": "",
    },
    "camera_setup": "handheld",
}


def _hook_prompt(plan_extra, budget):
    import generation_planning as gp
    plan = {
        "hook_seconds": 4,
        "location": "A tidy desk with a notebook",
        "duration_seconds": 4,
        "camera_setup": "handheld",
    }
    plan.update(plan_extra)
    return gp.build_segment_prompt(
        strategy=HOOK_STRATEGY, profile={"brand_name": "Vocolens"},
        template={}, duration=4, plan=plan, prompt_budget=budget)


class TestHookPromptDirection:
    def test_a_hook_prompt_requires_the_physical_opening(self):
        full = _hook_prompt({"surface": "hook_cta"}, 6800)
        assert "does NOT satisfy the opening beat" in full
        tight = _hook_prompt({"surface": "hook_cta"}, 4090)
        assert "does not open this hook" in tight

    def test_a_hook_prompt_requires_the_real_scene(self):
        full = _hook_prompt({"surface": "hook_cta"}, 6800)
        assert "A plain, empty or white background is a failed render" in full
        tight = _hook_prompt({"surface": "hook_cta"}, 4090)
        assert "white backdrop is a failed render" in tight

    def test_a_regular_prompt_carries_neither_requirement(self):
        """The two sections are the hook surface's alone: a plan
        with no surface marker builds the prompt it always built."""
        full = _hook_prompt({}, 6800)
        assert "does NOT satisfy the opening beat" not in full
        assert "A plain, empty or white background" not in full
        tight = _hook_prompt({}, 4090)
        assert "does not open this hook" not in tight
        assert "white backdrop is a failed render" not in tight


# ------------------------------------------------- the hook line's words

PROFILE_FACTS = {
    "name": "Vocolens",
    "category": "Wellness",
    "description": "Speak your journal entry instead of writing it.",
    "platforms": [],
    "features": ["Voice entries"],
    "use_cases": ["Winding down after work"],
    "problems": [],
    "desired_outcomes": ["Clearing the day's thoughts out loud"],
    "outcome_statements": [],
    "differentiators": "",
    "known_limitations": "",
}

HOOK_REPLY = {
    "hook_line": "I'm trying to clear my head before bed but my thoughts race.",
    "hook_action": "Jerks upright, both hands flying up as the thought lands.",
    "closing_action": "Leans in, holding the look straight at the camera.",
    "location": "A quiet bedroom in the evening",
}


def _stub_chat(monkeypatch, replies):
    import ai_service
    queue = list(replies)
    calls = []

    async def fake_chat(**kwargs):
        calls.append(kwargs)
        return queue.pop(0) if queue else {}

    monkeypatch.setattr(ai_service, "_chat_json", fake_chat)
    return calls


class TestHookLineInstruction:
    def test_the_hook_action_instruction_refuses_a_face_only_opening(
            self, monkeypatch):
        import ai_service
        calls = _stub_chat(monkeypatch, [HOOK_REPLY])
        project = {
            "id": "hook-cta-1", "kind": "video", "surface": "hook_cta",
            "duration_seconds": 5, "camera_setup": "handheld",
            "location": "", "visual_direction": "",
        }
        out = _run(ai_service.generate_hook_line(project, PROFILE_FACTS))
        assert out["hook_line"] == HOOK_REPLY["hook_line"]
        prompt = calls[0]["prompt"]
        assert "face-only change" in prompt
        assert "never counts as the opening beat" in prompt

    def test_the_stored_strategy_positions_the_presenter_for_the_action(
            self, api, monkeypatch):
        """The strategy the hook endpoint stores (the render's
        direction) seats the presenter waist-up with hands and body
        in frame, so the scene lock carries the physical opening
        into every hook render."""
        from models import GenerateHookLineRequest
        project = _hook_cta_project(api, "Hook Head Strategy")

        async def fake_hook_line(project_arg, profile):
            return dict(HOOK_REPLY)

        monkeypatch.setattr(api.ai_service, "generate_hook_line", fake_hook_line)
        out = _run(api.generate_hook_cta_hook(
            project["id"], GenerateHookLineRequest(), ANON))
        positioning = out["strategy"]["scene"]["character_positioning"]
        assert "hands and body in frame" in positioning
        assert "physical action" in positioning
