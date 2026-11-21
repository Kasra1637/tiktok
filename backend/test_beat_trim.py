"""
Tests for the beat trim (ADR 0239, re-homed by ADR 0244).

The claim under test: an exact-duration submit whose pick sits below
the provider floor (both catalog models floor at 5 seconds) renders
at the floor, and the persist cuts the saved file's tail to exactly
the pick — the line is budgeted to the short beat, so the cut takes
only the quiet tail. ADR 0239 built this for story frames and keyed
it on the project's kind; ADR 0244 re-homes the rule on the
generation row itself: a trim is a beat cut when the render was
requested AT the cut length (requested_duration == trim_to_seconds),
which is exactly what an exact-duration submit records — for a Hook
+ CTA hook now, and for the legacy story rows already in the data.
A legacy hook row is the other shape: its trim target is the hook's
seconds against a full-length request, so its cut stays a deviation
that writes its "Cut down to Xs." note, exactly as before.
"""
import asyncio
import importlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
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
    tmpdir = tempfile.mkdtemp(prefix="tiktok-beattrim-")
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


def _hook_cta_project(api, name):
    from models import CreateHookCtaProjectRequest
    profile = _profile(api, name)
    return _run(api.create_hook_cta_project(payload=CreateHookCtaProjectRequest(
        brand_profile_id=profile["id"],
    ), user_id=ANON))


def _story_project(api, name):
    """A legacy story row, the way the retired page left it (ADR 0243)."""
    from models import CreateStudioProjectRequest
    profile = _profile(api, name)
    return _run(api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"], kind="story"), user_id=ANON))


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
             requested: int = 0, render_seconds: int = 5):
    """Run the real persist pipeline for one fresh provider download
    whose render came back at the provider floor (5s). `trim_to` and
    `requested` are what the submit recorded on the row: for an
    exact-duration beat the two are the same number (the pick); for a
    legacy hook row the request is the full piece and the trim target
    is the hook's seconds alone."""
    source = _make_clip(tmp / f"{generation_id}-source.mp4", render_seconds)
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
class TestBeatTrim:
    def test_four_second_hook_is_cut_to_four(self, api, monkeypatch, tmp_path):
        project = _hook_cta_project(api, "Beat Four")
        calls = _spy_trims(api, monkeypatch)
        canonical, stored_url, storage_error, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-hook-4", project["id"],
            target=4, model="minimax-h3-max", trim_to=4, requested=4)
        assert stored_url == "https://storage.example/gen-hook-4.mp4"
        # The cut is the requested outcome, not a deviation: no note
        # rides the storage_error slot for a beat cut (ADR 0239).
        assert not storage_error
        assert [seconds for _path, seconds in calls] == [4]
        assert abs(_duration(canonical) - 4.0) < 0.06, _duration(canonical)
        assert delivered == 4

    def test_five_second_hook_is_not_recut(self, api, monkeypatch, tmp_path):
        project = _hook_cta_project(api, "Beat Five")
        calls = _spy_trims(api, monkeypatch)
        canonical, _stored, storage_error, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-hook-5", project["id"],
            target=5, model="minimax-h3-max", trim_to=0, requested=5)
        assert not storage_error
        # Already at its length: the trim never runs.
        assert calls == []
        assert abs(_duration(canonical) - 5.0) < 0.06, _duration(canonical)
        assert delivered == 5

    def test_legacy_story_beat_is_still_cut_without_a_note(
            self, api, monkeypatch, tmp_path):
        """A story row recorded before the removal keeps its beat
        behavior exactly (ADR 0243's preservation): requested == trim
        is the shape its submits recorded too."""
        project = _story_project(api, "Beat Legacy Story")
        canonical, _stored, storage_error, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-story-3", project["id"],
            target=3, model="minimax-h3-max", trim_to=3, requested=3)
        assert not storage_error
        assert abs(_duration(canonical) - 3.0) < 0.06, _duration(canonical)
        assert delivered == 3

    def test_legacy_hook_trim_keeps_its_note(self, api, monkeypatch, tmp_path):
        """The pre-single-pass hook shape: the request was the full
        piece (15s), the trim target the hook's seconds (3s) — a
        deviation, so the note is written exactly as before."""
        project = _video_project(api, "Beat Legacy Hook")
        canonical, _stored, storage_error, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-legacy-hook", project["id"],
            target=15, model="minimax-h3-max", trim_to=3, requested=15,
            render_seconds=15)
        assert storage_error == "Cut down to 3s."
        assert abs(_duration(canonical) - 3.0) < 0.06, _duration(canonical)
        assert delivered == 3

    def test_heygen_hook_head_cut_and_tail_cut_compose(
            self, api, monkeypatch, tmp_path):
        """A HeyGen hook takes both cuts: the 0.2s blurry head (ADR
        0181) and the tail down to the pick, landing on exactly the
        pick's seconds."""
        project = _hook_cta_project(api, "Beat HeyGen")
        canonical, _stored, storage_error, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-hook-heygen", project["id"],
            target=4, model="heygen-video-1", trim_to=4, requested=4)
        assert not storage_error
        assert abs(_duration(canonical) - 4.0) < 0.06, _duration(canonical)
        assert delivered == 4

    def test_failed_hook_cut_delivers_the_full_render_and_says_so(
            self, api, monkeypatch, tmp_path):
        project = _hook_cta_project(api, "Beat Failure")

        async def no_trim(path, seconds):
            return None

        monkeypatch.setattr(api.pipeline, "replace_with_trimmed", no_trim)
        canonical, _stored, storage_error, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-hook-fail", project["id"],
            target=4, model="minimax-h3-max", trim_to=4, requested=4)
        # The render is kept, the deviation is named for the hook, and
        # the recorded length is the floor length the founder gets.
        assert storage_error and "hook" in storage_error and "4s" in storage_error
        assert abs(_duration(canonical) - 5.0) < 0.06, _duration(canonical)
        assert delivered == 5

    def test_failed_legacy_story_cut_still_names_the_story(
            self, api, monkeypatch, tmp_path):
        project = _story_project(api, "Beat Story Failure")

        async def no_trim(path, seconds):
            return None

        monkeypatch.setattr(api.pipeline, "replace_with_trimmed", no_trim)
        canonical, _stored, storage_error, delivered = _persist(
            api, monkeypatch, tmp_path, "gen-story-fail", project["id"],
            target=3, model="minimax-h3-max", trim_to=3, requested=3)
        assert storage_error and "story" in storage_error and "3s" in storage_error
        assert abs(_duration(canonical) - 5.0) < 0.06, _duration(canonical)
        assert delivered == 5
