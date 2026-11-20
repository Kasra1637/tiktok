"""
Tests for the story tail trim (ADR 0239).

The claim under test: ADR 0238 made story frames 3, 4 or 5 seconds
and budgeted their spoken lines to fit, but both catalog models
declare a 5-second provider floor, so a 3- or 4-second frame renders
at 5. Kasra's ruling: render at the floor, then cut the saved file's
tail to the frame's exact length — the line is written to fit the
short beat, so the cut takes only the quiet tail. The cut lives in
the one persist pipeline beside the head cut (ADR 0181), applies to
story-kind generations only, and a 5-second story — already at its
length — is not re-cut. Hook videos are untouched.
"""
import asyncio
import importlib
import os
import re
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
    tmpdir = tempfile.mkdtemp(prefix="tiktok-storytrim-")
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


def _profile(api, name):
    from models import ApproveAppProfileRequest, BrandProfileCreateRequest
    profile = _run(api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=name, app_category="Wellness",
        brand_description="Speak your journal entry instead of writing it.",
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


def _story_project(api, name):
    from models import CreateStoryProjectRequest
    profile = _profile(api, name)
    return _run(api.create_story_project(payload=CreateStoryProjectRequest(
        brand_profile_id=profile["id"], story_type="question_poll",
    ), user_id=ANON))


def _video_project(api, name):
    from models import CreateStudioProjectRequest
    profile = _profile(api, name)
    return _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"]), user_id=ANON))


def _make_clip(path: Path, seconds: int = 5) -> Path:
    """A plain rendered clip of `seconds`, as the provider floor delivers."""
    subprocess.run([
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"color=c=blue:size=360x640:rate=30:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency=880:duration={seconds}:sample_rate=48000",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(path),
    ], check=True, capture_output=True)
    return path


def _persist(api, monkeypatch, tmp: Path, generation_id: str,
             project_id: str, target: int, model: str, trim_to: int = 0,
             render_seconds: int = 5):
    """Run the real persist pipeline for one fresh provider download
    whose render came back at the provider floor (5s). `trim_to` is
    what the submit recorded on the row for this frame (ADR 0239):
    the frame's own seconds for a sub-floor story, 0 at the floor
    and for every hook video."""
    source = _make_clip(tmp / f"{generation_id}-source.mp4", render_seconds)
    row = {
        "id": generation_id,
        "model": model,
        "duration": target,
        "trim_to_seconds": trim_to,
        "video_url": "https://provider.example/render.mp4",
        "openrouter_job_id": f"job-{generation_id}",
        "r2_url": "",
        "studio_project_id": project_id,
        "camera_setup": "fixed",
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


def _spy_trims(api, monkeypatch):
    """Record every in-place length trim the persist attempts."""
    calls = []
    real = api.pipeline.replace_with_trimmed

    async def spy(path, seconds):
        calls.append((Path(path), seconds))
        return await real(path, seconds)

    monkeypatch.setattr(api.pipeline, "replace_with_trimmed", spy)
    return calls


@needs_ffmpeg
class TestStoryTailTrim:
    def test_three_second_story_is_cut_to_three(self, api, monkeypatch, tmp_path):
        project = _story_project(api, "Tail Three")
        calls = _spy_trims(api, monkeypatch)
        canonical, stored_url, storage_error, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-story-3", project["id"],
            target=3, model="minimax-h3-max", trim_to=3)
        assert stored_url == "https://storage.example/gen-story-3.mp4"
        assert not storage_error
        assert [seconds for _path, seconds in calls] == [3]
        assert abs(_duration(canonical) - 3.0) < 0.06, _duration(canonical)
        assert delivered == 3

    def test_four_second_story_is_cut_to_four(self, api, monkeypatch, tmp_path):
        project = _story_project(api, "Tail Four")
        canonical, _stored, storage_error, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-story-4", project["id"],
            target=4, model="minimax-h3-max", trim_to=4)
        assert not storage_error
        assert abs(_duration(canonical) - 4.0) < 0.06, _duration(canonical)
        assert delivered == 4

    def test_five_second_story_is_not_recut(self, api, monkeypatch, tmp_path):
        project = _story_project(api, "Tail Five")
        calls = _spy_trims(api, monkeypatch)
        canonical, _stored, storage_error, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-story-5", project["id"],
            target=5, model="minimax-h3-max", trim_to=0)
        assert not storage_error
        # Already at its length: the trim never runs, so the save does
        # not spend a re-encode rewriting a file that is already right.
        assert calls == []
        assert abs(_duration(canonical) - 5.0) < 0.06, _duration(canonical)
        assert delivered == 5

    def test_hook_video_is_never_tail_cut(self, api, monkeypatch, tmp_path):
        """The gate is the project's kind, not the numbers: a hook-video
        row carrying a story-like length still saves untrimmed. (The
        row is synthetic — a real hook row's length is its plan's —
        built to isolate the kind gate.)"""
        project = _video_project(api, "Tail Video")
        calls = _spy_trims(api, monkeypatch)
        canonical, _stored, _err, _delivered = _persist(
            api, monkeypatch, tmp_path, "gen-video-3", project["id"],
            target=3, model="minimax-h3-max", trim_to=0)
        assert calls == []
        assert abs(_duration(canonical) - 5.0) < 0.06, _duration(canonical)

    def test_heygen_story_head_cut_and_tail_cut_compose(
            self, api, monkeypatch, tmp_path):
        """A HeyGen story takes both cuts: the 0.2s blurry head (ADR
        0181) and the tail down to the frame's length, landing on
        exactly the story's seconds."""
        project = _story_project(api, "Tail HeyGen")
        canonical, _stored, storage_error, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-story-heygen", project["id"],
            target=3, model="heygen-video-1", trim_to=3)
        assert not storage_error
        assert abs(_duration(canonical) - 3.0) < 0.06, _duration(canonical)
        assert delivered == 3

    def test_failed_cut_delivers_the_full_render_and_says_so(
            self, api, monkeypatch, tmp_path):
        project = _story_project(api, "Tail Failure")

        async def no_trim(path, seconds):
            return None

        monkeypatch.setattr(api.pipeline, "replace_with_trimmed", no_trim)
        canonical, _stored, storage_error, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-story-fail", project["id"],
            target=3, model="minimax-h3-max", trim_to=3)
        # The render is kept, the deviation is named, and the recorded
        # length is the length the founder actually gets.
        assert storage_error and "3s" in storage_error
        assert abs(_duration(canonical) - 5.0) < 0.06, _duration(canonical)
        assert delivered == 5
