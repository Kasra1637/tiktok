"""
Tests for the HeyGen head trim (ADR 0181).

The claim under test: a render from the HeyGen Video model
(heygen-video-1) opens with a blurry dissolve of about 0.2s — the
model's own conversion artifact, seen frame by frame on the founder's
mural render — and the durable save cuts exactly that head off, audio
and picture together, so the founder never hand-edits it out again.
Every other model's save is the current behavior, untouched, and the
delivered duration the row records is the trimmed length.
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
    tmpdir = tempfile.mkdtemp(prefix="tiktok-headtrim-")
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


def _duration(path: Path) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(re.search(r"[\d.]+", out.stdout).group())


def _stream_duration(path: Path, kind: str) -> float:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-select_streams", kind,
         "-show_entries", "stream=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(re.search(r"[\d.]+", out.stdout).group())


def _make_marked_clip(path: Path, seconds: int = 3) -> Path:
    """
    A clip whose first 0.2s is marked in BOTH streams: red frames and
    silence. Past 0.2s: blue frames and a loud 880Hz tone. A head cut
    at the right offset — and only a cut of both streams together —
    leaves a clip that starts blue and loud.
    """
    head = 0.2
    tail = seconds - head
    subprocess.run([
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"color=c=red:size=360x640:rate=30:duration={head}",
        "-f", "lavfi", "-i", f"color=c=blue:size=360x640:rate=30:duration={tail}",
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=48000",
        "-f", "lavfi", "-i", f"sine=frequency=880:duration={tail}:sample_rate=48000",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[vv];"
                           "[2:a]atrim=duration=0.2[ha];"
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
    # The delivered canvas is 1080x1920; the source is 360x640. Read the
    # frame's own dimensions from ffprobe rather than assuming either.
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


def _persist(api, monkeypatch, tmp: Path, generation_id: str, model: str):
    """Run the real persist pipeline for one fresh provider download."""
    source = _make_marked_clip(tmp / f"{generation_id}-source.mp4", 3)
    row = {
        "id": generation_id,
        "model": model,
        "duration": 3,
        "trim_to_seconds": 0,
        "video_url": "https://provider.example/render.mp4",
        "openrouter_job_id": f"job-{generation_id}",
        "r2_url": "",
        "studio_project_id": "",
        "camera_setup": "fixed",
    }

    async def fake_download(url, gid):
        target = api.pipeline.VIDEOS_DIR / f"{gid}.mp4"
        shutil.copyfile(source, target)
        return target, None

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
class TestHeadTrimHelper:
    def test_head_cut_is_frame_exact(self, tmp_path):
        """4s in, 3.8s out: the cut lands on the offset, not a keyframe."""
        import pipeline
        src = _make_marked_clip(tmp_path / "src.mp4", 4)
        out = tmp_path / "out.mp4"
        cut = _run(pipeline.trim_head_exact(src, 0.2, out))
        assert cut is not None
        assert abs(_duration(cut) - 3.8) < 0.03, _duration(cut)

    def test_in_place_replace_leaves_the_cut_file_canonical(self, tmp_path):
        import pipeline
        canonical = _make_marked_clip(tmp_path / "canonical.mp4", 4)
        result = _run(pipeline.replace_with_head_trimmed(canonical, 0.2))
        assert result == canonical
        assert abs(_duration(canonical) - 3.8) < 0.03
        assert not [p for p in tmp_path.iterdir() if p.name.startswith(".")]

    def test_failed_cut_leaves_the_original_untouched(self, tmp_path):
        import pipeline
        src = _make_marked_clip(tmp_path / "keep.mp4", 4)
        assert _run(pipeline.replace_with_head_trimmed(src, 0)) is None
        assert abs(_duration(src) - 4.0) < 0.05
        assert _run(pipeline.replace_with_head_trimmed(tmp_path / "nope.mp4", 0.2)) is None


@needs_ffmpeg
class TestPersistHeadTrim:
    def test_heygen_persist_cuts_the_marked_head_audio_and_picture_together(
            self, api, monkeypatch, tmp_path):
        canonical, stored_url, _err, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-head-1", "heygen-video-1")
        assert stored_url == "https://storage.example/gen-head-1.mp4"
        # ~0.2s gone from the whole file…
        assert abs(_duration(canonical) - 2.8) < 0.06, _duration(canonical)
        # …from both streams together (their lengths still agree)…
        v_len = _stream_duration(canonical, "v:0")
        a_len = _stream_duration(canonical, "a:0")
        assert abs(v_len - a_len) < 0.1, (v_len, a_len)
        # …the picture starts on the post-dissolve content (blue, not red)…
        r, g, b = _first_frame_rgb(canonical)
        assert b > 120 and r < 90, (r, g, b)
        # …and the audio starts loud — the silent head went with the cut,
        # so the tone that began at 0.2s is the first thing heard.
        assert _opening_audio_rms(canonical) > 1000

    def test_other_model_persist_is_untouched(self, api, monkeypatch, tmp_path):
        canonical, _stored, _err, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-head-2", "minimax-h3")
        assert abs(_duration(canonical) - 3.0) < 0.06, _duration(canonical)
        r, g, b = _first_frame_rgb(canonical)
        assert r > 120 and b < 90, (r, g, b)
        assert _opening_audio_rms(canonical) < 100
        assert delivered == 3

    def test_delivered_seconds_record_the_trimmed_length(
            self, api, monkeypatch, tmp_path):
        _canonical, _stored, _err, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-head-3", "heygen-video-1")
        # The row records the length the founder will actually get: the
        # 3s render minus the 0.2s head, in the accounting's whole
        # seconds — never more than the file holds.
        assert delivered == int(3 - 0.2)
