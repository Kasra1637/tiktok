"""
Poster memory budget: one capped encode at a time, never inside a request.

An uncapped, overlapping poster ffmpeg is what OOM-killed the 512MB
container, so these pin the three properties that prevent a recurrence:
the thread cap on the ffmpeg command, single-flight sharing of one encode
across concurrent callers, and deferral of poster work to BackgroundTasks.
"""
import asyncio
import importlib
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import posters


class FakeTasks:
    """Stands in for Starlette BackgroundTasks, recording scheduled work."""

    def __init__(self):
        self.tasks = []

    def add_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))


def test_poster_ffmpeg_is_thread_capped(tmp_path):
    """
    The poster encode must carry -threads 1 like every other ffmpeg call in
    this repo. Per-thread decode buffers are the largest single allocator on
    the 512MB host; an uncapped poster encode spiked it into an OOM kill.
    """
    argv = posters._poster_argv(tmp_path / "in.mp4", tmp_path / "out.jpg", 480)
    assert argv[0] == "ffmpeg"
    assert argv[argv.index("-threads") + 1] == "1"


def test_concurrent_ensure_poster_shares_one_encode(tmp_path, monkeypatch):
    """
    N concurrent callers for one job must trigger exactly one encode: without
    single-flight, one History page view becomes dozens of ffmpegs.
    """
    monkeypatch.setattr(posters, "poster_path", lambda job_id: tmp_path / f"{job_id}.jpg")
    monkeypatch.setattr(posters, "video_path", lambda job_id: tmp_path / f"{job_id}.mp4")
    calls = []
    release = threading.Event()

    def slow_fake(video, poster, width=480):
        calls.append((str(video), str(poster)))
        assert release.wait(timeout=30), "encode was never released"
        Path(poster).write_bytes(b"\xff\xd8" + b"\x00" * 1024)
        return True

    monkeypatch.setattr(posters, "generate_poster", slow_fake)
    results = []
    threads = [
        threading.Thread(target=lambda: results.append(posters.ensure_poster("job-1")))
        for _ in range(8)
    ]
    for t in threads:
        t.start()
    time.sleep(0.5)
    release.set()
    for t in threads:
        t.join(timeout=30)
        assert not t.is_alive(), "a caller never returned"
    assert len(calls) == 1, f"expected one shared encode, got {len(calls)}"
    assert all(r is not None for r in results)


def test_ensure_poster_fails_fast_with_no_video(tmp_path, monkeypatch):
    """
    Rows with no video must cost zero subprocesses: missing-copy rows are
    common after a wipe, and each one spawning ffmpeg to fail would be pure
    memory churn. The real generate_poster is used; only the spawn itself is
    observed.
    """
    monkeypatch.setattr(posters, "poster_path", lambda job_id: tmp_path / f"{job_id}.jpg")
    monkeypatch.setattr(posters, "video_path", lambda job_id: tmp_path / "absent.mp4")
    spawns = []
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: (spawns.append(a), (_ for _ in ()).throw(AssertionError("ffmpeg spawned")))[0],
    )
    assert posters.ensure_poster("gone") is None
    assert spawns == []


def _load_server():
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    tmpdir = tempfile.mkdtemp(prefix="tiktok-posters-sched-")
    server.DB_PATH = Path(tmpdir) / "test.db"
    return server


def test_poster_work_is_scheduled_not_awaited():
    """
    On HTTP the save must return before poster work runs: awaiting the encode
    inline stacks a second ffmpeg on top of the save's own trim/rescale.
    """
    server = _load_server()
    try:
        tasks = FakeTasks()
        ran = []
        asyncio.run(server._schedule_poster(tasks, "gen-1", "user-1"))
        assert len(tasks.tasks) == 1
        assert tasks.tasks[0][0] is server._eager_poster
        assert ran == [], "poster work must not run inside the request"
    finally:
        sys.modules.pop("server", None)


def test_poster_work_runs_inline_without_tasks():
    """
    Direct (non-HTTP) callers such as tests pass no BackgroundTasks and get
    the real inline path, so they keep asserting actual poster behaviour.
    """
    server = _load_server()
    try:
        ran = []
        real = server._eager_poster

        async def fake_eager(generation_id, user_id):
            ran.append((generation_id, user_id))

        server._eager_poster = fake_eager
        try:
            asyncio.run(server._schedule_poster(None, "gen-2", "user-2"))
        finally:
            server._eager_poster = real
        assert ran == [("gen-2", "user-2")]
    finally:
        sys.modules.pop("server", None)
