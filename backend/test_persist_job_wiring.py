"""
Persist-a-completed-render rides the durable job queue (ADR 0120).

The gap this closes: poll_generation resolved a finished provider job by
persisting the clip inline. If the container died between the provider
finishing and the durable save landing, nothing recorded that the persist
was owed — the row sat at `generating` until the stranded sweep happened
to re-poll it. Now the completion branch enqueues a `persist_generation_clip`
job BEFORE attempting the work, claims it, and runs it; a restart leaves
the job in the table for the next process's sweep to drain.

These tests pin both halves with the persist itself stubbed (the pipeline
has its own suites): poll completes through the queue, and a job stranded
by a dead worker is drained by the sweep after its lease lapses.
"""
import asyncio
import importlib
import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

ANON = "anonymous"


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-persistjob-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(server.init_db())
    try:
        yield server
    finally:
        sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


async def _insert_generation(api, generation_id, status="generating"):
    await api._execute(
        "INSERT INTO generations (id, user_id, status, openrouter_job_id, "
        "duration, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (generation_id, ANON, status, "job-123", 10,
         "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
    )


class TestPollPersistsThroughTheQueue:
    def test_poll_enqueues_claims_and_completes_a_persist_job(self, api, monkeypatch):
        async def main():
            await _insert_generation(api, "gen-poll-1")

            calls = []

            async def fake_persist(row, user_id, video_url=""):
                calls.append((row["id"], user_id, video_url))
                return ("https://storage.example/gen-poll-1.mp4", None, 10)

            async def fake_poll(job_id):
                return {"status": "completed",
                        "unsigned_urls": ["https://provider.example/v.mp4"]}

            monkeypatch.setattr("server._persist_generation_clip", fake_persist)
            monkeypatch.setattr("server.poll_video_job", fake_poll)
            # Post kit runs inline when background_tasks is None; keep this
            # test about the queue, not the kit writer.
            async def no_kit(background_tasks, generation_id, user_id):
                return None

            monkeypatch.setattr("server._schedule_post_kit", no_kit)

            out = await api.poll_generation("gen-poll-1", user_id=ANON)
            assert out["status"] == "completed"
            assert calls == [("gen-poll-1", ANON, "https://provider.example/v.mp4")]

            jobs = await api._fetch_all(
                "SELECT * FROM jobs WHERE kind = 'persist_generation_clip'"
            )
            assert len(jobs) == 1
            assert jobs[0]["status"] == "completed"
            assert jobs[0]["dedupe_key"] == "persist:gen-poll-1"

        _run(main())


class TestSweepDrainsStrandedPersistJobs:
    def test_dead_workers_job_is_drained_after_its_lease_lapses(self, api, monkeypatch):
        async def main():
            await _insert_generation(api, "gen-stranded-1")

            # The completion was recorded, then the worker died mid-persist:
            # the job sits claimed under a lease that has already lapsed.
            job_id = await api._enqueue_persist_job(
                "gen-stranded-1", ANON, "https://provider.example/v.mp4"
            )
            claimed = await api._claim_job_by_id(job_id, "dead-worker", lease_seconds=0)
            assert claimed is not None

            async def fake_persist(row, user_id, video_url=""):
                return ("https://storage.example/gen-stranded-1.mp4", None, 10)

            monkeypatch.setattr("server._persist_generation_clip", fake_persist)

            async def no_kit(background_tasks, generation_id, user_id):
                return None

            monkeypatch.setattr("server._schedule_post_kit", no_kit)

            drained = await api._drain_pending_persist_jobs()
            assert drained == 1

            row = await api._fetch_one(
                "SELECT status, r2_url FROM generations WHERE id = 'gen-stranded-1'"
            )
            assert row["status"] == "completed"
            assert row["r2_url"] == "https://storage.example/gen-stranded-1.mp4"
            job = await api._fetch_job(job_id)
            assert job["status"] == "completed"
            assert job["attempts"] == 2  # the dead worker's claim + the drain's

        _run(main())
