"""
Durable-save repairs: one at a time, and never sharing a scratch file.

Two ways a retry could make things worse than doing nothing, both found while
chasing an edge 502 on "Retry durable save":

  Overlap. The client gives up after 10 minutes; the server can legitimately
  take closer to 22 (3 download attempts of 240s, plus a 600s ffmpeg pass). A
  founder who clicks again after a timeout therefore starts a SECOND repair of
  the same clip rather than replacing a failed one, and the two fight over the
  same local file.

  Scratch-file collision. Both ffmpeg steps wrote to a FIXED sibling temp name
  -- `.<stem>_trim.mp4` and `.<stem>_canvas.mp4`. Two concurrent repairs of one
  generation wrote the same files, so one ffmpeg clobbered the other's output or
  died mid-swap. The download temp already carried a uuid; these two did not.

Also covered here: ffmpeg is asked for a single thread, because it runs inside
the web process on a 512MB host where Render has been OOM-killing the container.
"""

import asyncio
import importlib
import os
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import mp4_samples  # noqa: E402
import overlays  # noqa: E402
import pipeline  # noqa: E402

pytestmark = pytest.mark.skipif(
    not mp4_samples.ffmpeg_available(),
    reason="the trim command is built around ffmpeg",
)


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-repair-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # VIDEOS_DIR moves with STORAGE_DIR so served_media_path() still derives a
    # path, matching the other backend fixtures.
    server.pipeline.STORAGE_DIR = Path(tmpdir) / "storage"
    server.pipeline.VIDEOS_DIR = server.pipeline.STORAGE_DIR / "videos"
    server.pipeline.ASSETS_DIR = server.pipeline.STORAGE_DIR / "assets"
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    server.pipeline.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    asyncio.run(server.init_db())
    yield server
    sys.modules.pop("server", None)


class TestScratchFilesAreUnique:
    def test_two_trims_never_share_a_temp_file(self, tmp_path):
        """
        The collision itself. Two repairs of one clip reach this at the same
        time and used to pick the same path, so one ffmpeg overwrote the other.
        """
        source = tmp_path / "clip.mp4"
        source.write_bytes(mp4_samples.real_mp4())
        stem, suffix = source.stem, source.suffix

        async def capture(n):
            seen = {}
            real = pipeline.trim_video_exact

            async def spy(video_path, seconds, out_path):
                seen["out"] = Path(out_path)
                return None  # never actually run ffmpeg

            pipeline.trim_video_exact = spy
            try:
                await pipeline.replace_with_trimmed(source, 1.0)
            finally:
                pipeline.trim_video_exact = real
            return seen["out"]

        first, second = asyncio.run(capture(1)), asyncio.run(capture(2))
        assert first != second, "two repairs would write the same scratch file"
        # Still recognisable, still hidden, still beside the source.
        for path in (first, second):
            assert path.parent == source.parent
            assert path.name.startswith(f".{stem}_trim_")
            assert path.name.endswith(suffix)

    def test_two_rescales_never_share_a_temp_file(self, tmp_path):
        source = tmp_path / "clip.mp4"
        source.write_bytes(mp4_samples.real_mp4())
        stem, suffix = source.stem, source.suffix
        captured = []

        class FakeProc:
            returncode = 0
            stderr = ""

            def __init__(self, *args, **kwargs):
                pass

        def fake_run(argv, **kwargs):
            captured.append(argv[-1])
            Path(argv[-1]).write_bytes(b"x")
            return FakeProc()

        real_run = overlays.subprocess.run
        overlays.subprocess.run = fake_run
        try:
            overlays.rescale_to_canvas_sync(source)
            overlays.rescale_to_canvas_sync(source)
        finally:
            overlays.subprocess.run = real_run

        assert len(captured) == 2
        assert captured[0] != captured[1], "two repairs would write the same scratch file"
        for name in captured:
            assert Path(name).parent == source.parent
            assert Path(name).name.startswith(f".{stem}_canvas_")
            assert Path(name).name.endswith(suffix)


class TestFfmpegIsBounded:
    """
    This runs inside the web process on Render's free tier, which is capped at
    512MB shared with Python, Uvicorn and the DB connection. libx264's
    frame-level threads are the largest allocator involved, and an OOM kill
    takes the whole instance down rather than failing one save.
    """

    def test_the_upscale_asks_for_one_thread(self, tmp_path):
        argv = overlays.build_upscale_command(tmp_path / "in.mp4", tmp_path / "out.mp4")
        assert argv[argv.index("-threads") + 1] == "1"

    def test_the_trim_asks_for_one_thread(self, tmp_path):
        """trim_video_exact builds its argv inline, so read it back off disk."""
        source = tmp_path / "clip.mp4"
        source.write_bytes(mp4_samples.real_mp4())
        seen = {}

        async def fake_run_cmd(cmd, timeout=None):
            seen["cmd"] = cmd
            raise RuntimeError("stop before ffmpeg runs")

        real = pipeline.run_cmd
        pipeline.run_cmd = fake_run_cmd
        try:
            asyncio.run(pipeline.trim_video_exact(source, 2.0, tmp_path / "out.mp4"))
        finally:
            pipeline.run_cmd = real
        cmd = seen["cmd"]
        assert cmd[cmd.index("-threads") + 1] == "1"

    def test_bounding_threads_does_not_change_the_output_contract(self, tmp_path):
        """
        The encode settings are load-bearing -- they are chosen so a trimmed
        hook and an untrimmed extension join without a visible re-init. The
        thread count must not have disturbed them.
        """
        argv = overlays.build_upscale_command(tmp_path / "in.mp4", tmp_path / "out.mp4")
        assert "libx264" in argv
        assert argv[argv.index("-crf") + 1] == "20"
        assert "+faststart" in " ".join(argv)


class TestSingleFlight:
    def test_a_second_repair_is_refused_while_one_runs(self, api, monkeypatch):
        """
        The guard is a plain set, checked and populated without an await
        between -- which is what makes it safe on a single event loop. Populated
        here to stand in for a repair already in progress.

        The row is stubbed because the guard deliberately sits AFTER the
        ownership and status checks: a request for a generation that is not this
        founder's, or not finished, is a 404/409 on its own terms and must not be
        answerable by anything as transient as "a repair is running".
        """
        gen_id = "gen-already-running"
        row = {"id": gen_id, "user_id": "anonymous", "status": "completed"}

        async def fake_fetch_one(query, params=None):
            return row

        monkeypatch.setattr(api, "_fetch_one", fake_fetch_one)
        api._storage_repairs_in_flight.add(gen_id)
        try:
            with pytest.raises(HTTPException) as caught:
                _run(api.retry_generation_storage(gen_id, "anonymous"))
            assert caught.value.status_code == 409
            assert "already running" in caught.value.detail
        finally:
            api._storage_repairs_in_flight.discard(gen_id)

    def test_the_guard_is_released_after_a_repair(self, api, monkeypatch):
        """
        A guard that leaks would turn every later repair into a 409, which reads
        as "this render is broken" rather than "the code is wrong".
        """
        gen_id = "gen-guard-release"
        row = {"id": gen_id, "user_id": "anonymous", "status": "completed"}

        async def fake_one(*args, **kwargs):
            # Assert the guard is held WHILE the work runs, not before or after.
            assert gen_id in api._storage_repairs_in_flight
            return {"id": gen_id, "r2_url": "https://example.invalid/x.mp4"}

        async def fake_fetch_one(query, params=None):
            return row

        monkeypatch.setattr(api, "_fetch_one", fake_fetch_one)
        monkeypatch.setattr(api, "_run_storage_repair", fake_one)
        result = _run(api.retry_generation_storage(gen_id, "anonymous"))
        assert result["id"] == gen_id
        assert gen_id not in api._storage_repairs_in_flight, "the guard leaked"

    def test_the_guard_is_released_even_when_the_repair_raises(self, api, monkeypatch):
        gen_id = "gen-guard-raises"
        row = {"id": gen_id, "user_id": "anonymous", "status": "completed"}

        async def boom(*args, **kwargs):
            raise HTTPException(status_code=502, detail="nope")

        async def fake_fetch_one(query, params=None):
            return row

        monkeypatch.setattr(api, "_fetch_one", fake_fetch_one)
        monkeypatch.setattr(api, "_run_storage_repair", boom)
        with pytest.raises(HTTPException):
            _run(api.retry_generation_storage(gen_id, "anonymous"))
        assert gen_id not in api._storage_repairs_in_flight, "the guard leaked on failure"


def _run(coro):
    return asyncio.run(coro)
