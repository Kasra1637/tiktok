"""
The durable job queue in the db layer (ADR 0120).

The queue exists so work that must survive a container restart — starting
with persisting a completed render — is recorded before it is attempted and
can be picked up by a later process. These tests pin the lease contract the
server wiring relies on:

- a claimed job is exclusively held until its lease expires;
- an expired lease makes the job claimable again (the restart case);
- attempts are counted at claim time, and failing a job requeues it until
  max_attempts, then parks it as failed;
- a dedupe key returns the already-active job instead of a second copy.
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


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-jobs-")
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


class TestJobQueue:
    def test_enqueue_claim_complete(self, api):
        async def main():
            job_id = await api._enqueue_job("kind_a", {"n": 1})
            job = await api._claim_job("worker-1", kind="kind_a")
            assert job is not None and job["id"] == job_id
            assert job["status"] == "claimed"
            assert job["attempts"] == 1
            assert await api._complete_job(job_id, "worker-1", result={"ok": True})
            done = await api._fetch_job(job_id)
            assert done["status"] == "completed"

        _run(main())

    def test_claim_is_exclusive_until_lease_expires(self, api):
        async def main():
            job_id = await api._enqueue_job("kind_b", {})
            first = await api._claim_job("worker-1", kind="kind_b", lease_seconds=600)
            assert first is not None and first["id"] == job_id
            # Held: another worker gets nothing, even by id.
            assert await api._claim_job("worker-2", kind="kind_b") is None
            assert await api._claim_job_by_id(job_id, "worker-2") is None
            # The restart case: the holder died, and by the time a later
            # process looks, the lease has lapsed — model that moment
            # directly by moving the expiry into the past.
            await api._execute(
                "UPDATE jobs SET lease_expires_at = '2000-01-01T00:00:00+00:00' "
                "WHERE id = ?",
                (job_id,),
            )
            second = await api._claim_job("worker-2", kind="kind_b")
            assert second is not None and second["id"] == job_id
            assert second["attempts"] == 2

        _run(main())

    def test_heartbeat_extends_only_for_the_holder(self, api):
        async def main():
            job_id = await api._enqueue_job("kind_c", {})
            job = await api._claim_job("worker-1", kind="kind_c", lease_seconds=0)
            assert job is not None
            assert await api._heartbeat_job(job_id, "worker-2") is False
            assert await api._heartbeat_job(job_id, "worker-1", lease_seconds=600)
            # Lease is live again: nobody else can take it.
            assert await api._claim_job("worker-2", kind="kind_c") is None

        _run(main())

    def test_failure_requeues_until_max_attempts(self, api):
        async def main():
            job_id = await api._enqueue_job("kind_d", {}, max_attempts=2)
            job = await api._claim_job("worker-1", kind="kind_d")
            assert job["attempts"] == 1
            assert await api._fail_job(job_id, "worker-1", "boom") == "pending"

            job = await api._claim_job("worker-1", kind="kind_d")
            assert job["attempts"] == 2
            assert await api._fail_job(job_id, "worker-1", "boom again") == "failed"

            done = await api._fetch_job(job_id)
            assert done["status"] == "failed"
            assert "boom again" in (done["last_error"] or "")
            # Parked: no longer claimable.
            assert await api._claim_job("worker-1", kind="kind_d") is None

        _run(main())

    def test_dedupe_returns_the_active_job(self, api):
        async def main():
            first = await api._enqueue_job("kind_e", {"g": 1}, dedupe_key="k-1")
            second = await api._enqueue_job("kind_e", {"g": 1}, dedupe_key="k-1")
            assert first == second
            job = await api._claim_job("worker-1", kind="kind_e")
            assert job["id"] == first
            await api._complete_job(first, "worker-1")
            # Completed jobs do not block a fresh enqueue under the same key.
            third = await api._enqueue_job("kind_e", {"g": 1}, dedupe_key="k-1")
            assert third != first

        _run(main())
