"""
ADR 0347: a blurred render is refused at delivery.

Kasra's order, after a finished render reached him blurred end
to end: fix it so this never occurs. The persist pipeline
measures the finished clip's sharpness through its length —
not just its first frame — and a measured wall-to-wall blur
fails the generation with a plain message instead of
delivering a blurred video as a finished one. No automatic
re-spend: the founder's retry renders anew. A clip that
cannot be measured is delivered as before.

The floor is calibrated, not guessed: a sharp synthetic
render measures ~289 through this function, the app's own
downscale-then-upscale path ~172, a wall-to-wall blur ~2.
"""

import asyncio
import importlib
import os
import shutil
import subprocess
import sys
import tempfile
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
    tmpdir = tempfile.mkdtemp(prefix="tiktok-blurgate-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""

    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    original = (
        server.pipeline.VIDEOS_DIR,
        server.pipeline.GENERATED_DIR,
        server.pipeline.FRAMES_DIR,
    )
    server.pipeline.VIDEOS_DIR = Path(tmpdir) / "videos"
    server.pipeline.GENERATED_DIR = Path(tmpdir) / "generated"
    server.pipeline.FRAMES_DIR = Path(tmpdir) / "frames"
    for d in (
        server.pipeline.VIDEOS_DIR,
        server.pipeline.GENERATED_DIR,
        server.pipeline.FRAMES_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)

    asyncio.run(server.init_db())
    try:
        yield server
    finally:
        (
            server.pipeline.VIDEOS_DIR,
            server.pipeline.GENERATED_DIR,
            server.pipeline.FRAMES_DIR,
        ) = original
        sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


def _make_clip(path: Path, blurred: bool) -> Path:
    """A 3s detailed synthetic clip, optionally blurred wall to wall."""
    vf = ["-vf", "boxblur=8:2"] if blurred else []
    subprocess.run(
        [
            FFMPEG, "-y", "-v", "error",
            "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=10:duration=3",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            *vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-shortest", str(path),
        ],
        check=True, capture_output=True,
    )
    return path


@needs_ffmpeg
class TestClipSharpness:
    def test_a_sharp_clip_measures_above_the_floor(self, api, tmp_path):
        import pipeline
        sharp = _run(pipeline.clip_sharpness(_make_clip(tmp_path / "s.mp4", False)))
        assert sharp is not None and sharp > pipeline.BLUR_FLOOR, sharp

    def test_a_blurred_clip_measures_under_the_floor(self, api, tmp_path):
        import pipeline
        blurred = _run(pipeline.clip_sharpness(_make_clip(tmp_path / "b.mp4", True)))
        assert blurred is not None and blurred < pipeline.BLUR_FLOOR, blurred

    def test_an_unmeasurable_clip_reads_as_none(self, api, tmp_path):
        import pipeline
        assert _run(pipeline.clip_sharpness(tmp_path / "nope.mp4")) is None

    def test_a_flat_color_clip_is_unmeasurable_not_blurred(self, api, tmp_path):
        """A frame with no scene in it gives no verdict: the trim
        suites' flat-color clips must deliver exactly as before —
        only a blurred SCENE is refused."""
        import pipeline
        flat = tmp_path / "flat.mp4"
        subprocess.run(
            [FFMPEG, "-y", "-v", "error", "-f", "lavfi",
             "-i", "color=c=blue:size=360x640:rate=10:duration=3",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(flat)],
            check=True, capture_output=True,
        )
        assert _run(pipeline.clip_sharpness(flat)) is None


@needs_ffmpeg
class TestDeliveryGate:
    def _persist(self, api, monkeypatch, tmp: Path, generation_id: str, blurred: bool):
        source = _make_clip(tmp / f"{generation_id}-source.mp4", blurred)
        row = {
            "id": generation_id,
            "model": "heygen-video-1",
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

        uploads = []
        monkeypatch.setattr("server._download_generation_video", fake_download)
        monkeypatch.setattr(
            "server.storage_service.upload_video",
            lambda user_id, gid, path: uploads.append(gid)
            or f"https://storage.example/{gid}.mp4",
        )
        outcome = _run(
            api._persist_generation_clip(row, ANON, "https://provider.example/render.mp4")
        )
        return outcome, uploads

    def test_a_blurred_render_is_refused_before_upload(
        self, api, monkeypatch, tmp_path
    ):
        (stored_url, storage_error, _delivered), uploads = self._persist(
            api, monkeypatch, tmp_path, "blur-refused", blurred=True
        )
        assert stored_url is None
        assert storage_error == api._BLURRED_RENDER_ERROR
        assert uploads == [], "a refused render is never uploaded"

    def test_a_sharp_render_still_delivers(self, api, monkeypatch, tmp_path):
        (stored_url, storage_error, _delivered), uploads = self._persist(
            api, monkeypatch, tmp_path, "sharp-delivers", blurred=False
        )
        assert stored_url == "https://storage.example/sharp-delivers.mp4"
        assert storage_error != api._BLURRED_RENDER_ERROR
        assert uploads == ["sharp-delivers"]

    def test_the_blur_outcome_fails_the_generation_row(self, api):
        generation_id = "blur-row-fails"
        _run(api._execute(
            "INSERT INTO generations (id, user_id, status, created_at, updated_at) "
            "VALUES (?, ?, 'generating', ?, ?)",
            (generation_id, ANON, api.now_iso(), api.now_iso()),
        ))
        _run(api._apply_persist_outcome(
            generation_id, ANON, "https://provider.example/render.mp4",
            None, api._BLURRED_RENDER_ERROR, 3, None,
        ))
        row = _run(api._fetch_one(
            "SELECT status, error, retryable FROM generations WHERE id = ?",
            (generation_id,),
        ))
        assert row["status"] == "failed"
        assert row["error"] == api._BLURRED_RENDER_ERROR
        assert row["retryable"] == 1
