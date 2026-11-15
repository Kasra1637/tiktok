"""
A claimed persist execution is bounded (ADR 0148).

The freeze this closes: the detached runner heartbeated the persist
job's 300s lease every 60s for as long as the save ran, with no overall
bound. A save that hung — a stalled download, a stuck upload — held its
lease forever: every later poll was answered "generating" against the
live claim, the startup sweep could never claim the job, and the row
never moved. Kasra met it live: a finished render sat at the stitching
stage for 7:28 and counting, in the panel and in History alike.

These tests pin the bound with the persist itself stubbed (the pipeline
has its own suites): a hung save is cut off and the row lands in the
recoverable state the storage retry serves; the sweep's drain is
bounded the same way; and a save that is merely slow completes under
the heartbeat's protection, ADR 0138's contract intact.

The classes live in their own file on purpose: the wiring suite's
module database is shared per worker process under xdist, and its poll
test counts the jobs table — these tests enqueue jobs of their own, so
they keep their own database.
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
    tmpdir = tempfile.mkdtemp(prefix="tiktok-persistbound-")
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


class TestHungPersistIsBounded:
    def test_hung_save_is_cut_off_and_the_row_lands_recoverable(self, api, monkeypatch):
        async def main():
            await _insert_generation(api, "gen-hung-1")

            never = asyncio.Event()

            async def hung_persist(row, user_id, video_url=""):
                await never.wait()
                return (None, None, 0)  # never reached

            monkeypatch.setattr("server._persist_generation_clip", hung_persist)
            # raising=False: on the unfixed code the constant does not
            # exist yet, and the failure this test wants is the behavioral
            # one — the detached run below never returns.
            monkeypatch.setattr(
                "server._PERSIST_EXECUTION_LIMIT_SECONDS", 0.2, raising=False
            )

            async def no_kit(background_tasks, generation_id, user_id):
                return None

            monkeypatch.setattr("server._schedule_post_kit", no_kit)

            job_id = await api._enqueue_persist_job(
                "gen-hung-1", ANON, "https://provider.example/v.mp4"
            )
            job = await api._claim_job_by_id(job_id, api._JOB_WORKER)
            assert job is not None

            # Kasra's freeze, reproduced end to end (ADR 0148): the save
            # never returns, and before the bound nothing could cut it
            # off — the heartbeat kept the lease alive, every poll was
            # answered "generating", and the row never moved.
            await asyncio.wait_for(
                api._run_detached_persist(
                    job, "gen-hung-1", ANON, "https://provider.example/v.mp4", 10
                ),
                timeout=10,
            )

            # The row leaves `generating` for the recoverable state the
            # storage retry already serves: completed, with the failure
            # named on it.
            row = await api._fetch_one(
                "SELECT status, storage_error FROM generations WHERE id = 'gen-hung-1'"
            )
            assert row["status"] == "completed"
            assert row["storage_error"] and "timed out" in row["storage_error"]

            # The job is released, never left claimed under a heartbeat:
            # requeued for the retry machinery, worker let go.
            job_after = await api._fetch_job(job_id)
            assert job_after["status"] == "pending"
            assert job_after["worker"] is None

            # Recovery rides the existing machinery: once the pipeline
            # answers again, the requeued job drains and the row heals.
            async def healed_persist(row, user_id, video_url=""):
                return ("https://storage.example/gen-hung-1.mp4", None, 10)

            monkeypatch.setattr("server._persist_generation_clip", healed_persist)
            drained = await api._drain_pending_persist_jobs()
            assert drained == 1
            row = await api._fetch_one(
                "SELECT status, storage_error, r2_url FROM generations "
                "WHERE id = 'gen-hung-1'"
            )
            assert row["status"] == "completed"
            assert row["r2_url"] == "https://storage.example/gen-hung-1.mp4"
            assert not row["storage_error"]

        _run(main())

    def test_hung_job_does_not_strand_the_drain(self, api, monkeypatch):
        async def main():
            await _insert_generation(api, "gen-drain-hung-1")

            never = asyncio.Event()

            async def hung_persist(row, user_id, video_url=""):
                await never.wait()
                return (None, None, 0)  # never reached

            monkeypatch.setattr("server._persist_generation_clip", hung_persist)
            monkeypatch.setattr(
                "server._PERSIST_EXECUTION_LIMIT_SECONDS", 0.2, raising=False
            )

            async def no_kit(background_tasks, generation_id, user_id):
                return None

            monkeypatch.setattr("server._schedule_post_kit", no_kit)

            job_id = await api._enqueue_persist_job(
                "gen-drain-hung-1", ANON, "https://provider.example/v.mp4"
            )

            # The startup sweep's drain is bounded the same way: it
            # returns instead of hanging on the one job, and the job is
            # never left claimed.
            drained = await asyncio.wait_for(
                api._drain_pending_persist_jobs(), timeout=10
            )
            assert drained == 0
            job_after = await api._fetch_job(job_id)
            assert job_after["status"] in ("pending", "failed")

            # Once the pipeline answers again, a later poll enqueues
            # afresh (a parked job no longer dedupes) and the row heals.
            async def healed_persist(row, user_id, video_url=""):
                return ("https://storage.example/gen-drain-hung-1.mp4", None, 10)

            monkeypatch.setattr("server._persist_generation_clip", healed_persist)
            outcome = await api._persist_via_queue(
                "gen-drain-hung-1", ANON, "https://provider.example/v.mp4"
            )
            assert outcome is not None
            row = await api._fetch_one(
                "SELECT status, r2_url FROM generations WHERE id = 'gen-drain-hung-1'"
            )
            assert row["status"] == "completed"
            assert row["r2_url"] == "https://storage.example/gen-drain-hung-1.mp4"

        _run(main())


class TestSlowPersistUnderTheBound:
    def test_slow_save_completes_and_its_lease_is_heartbeated(self, api, monkeypatch):
        async def main():
            await _insert_generation(api, "gen-slow-1")

            async def slow_persist(row, user_id, video_url=""):
                await asyncio.sleep(0.5)
                return ("https://storage.example/gen-slow-1.mp4", None, 10)

            monkeypatch.setattr("server._persist_generation_clip", slow_persist)
            monkeypatch.setattr(
                "server._PERSIST_EXECUTION_LIMIT_SECONDS", 30, raising=False
            )
            monkeypatch.setattr(
                "server._PERSIST_HEARTBEAT_SECONDS", 0.05, raising=False
            )

            async def no_kit(background_tasks, generation_id, user_id):
                return None

            monkeypatch.setattr("server._schedule_post_kit", no_kit)

            job_id = await api._enqueue_persist_job(
                "gen-slow-1", ANON, "https://provider.example/v.mp4"
            )
            job = await api._claim_job_by_id(job_id, api._JOB_WORKER)
            assert job is not None

            # ADR 0138's contract, intact under the bound: a save that is
            # merely slow — nowhere near the limit — is protected by the
            # heartbeat (its lease keeps moving, so nothing re-claims it
            # mid-flight) and completes normally.
            running = asyncio.create_task(
                api._run_detached_persist(
                    job, "gen-slow-1", ANON, "https://provider.example/v.mp4", 10
                )
            )
            leases = set()
            while not running.done():
                current = await api._fetch_job(job_id)
                if current and current["lease_expires_at"]:
                    leases.add(current["lease_expires_at"])
                await asyncio.sleep(0.02)
            await running
            assert len(leases) >= 2, "the heartbeat never extended the lease"

            row = await api._fetch_one(
                "SELECT status, storage_error, r2_url FROM generations "
                "WHERE id = 'gen-slow-1'"
            )
            assert row["status"] == "completed"
            assert row["r2_url"] == "https://storage.example/gen-slow-1.mp4"
            assert not row["storage_error"]
            job_after = await api._fetch_job(job_id)
            assert job_after["status"] == "completed"

        _run(main())


