"""
The health endpoint: where user data actually is, and how much of it there is.

This exists to settle a specific report that kept arriving as "the app deleted
my profile and videos". When Turso is configured but unreachable, `get_db`
falls back to local SQLite so the app keeps serving — and on Render that file is
on an ephemeral disk, so it starts EMPTY. Every list renders as "no profiles",
which is indistinguishable from deletion by looking at the UI.

What these tests pin is that the endpoint reports the store it is ACTUALLY
connected to rather than the one it was configured with, because those two have
already diverged once: a previous version logged "Turso cloud" from config
while the connection had fallen back to ephemeral, which is backwards.

The fallback path is also what would let a founder recover their data safely, so
it is worth being able to assert the label without reaching a real cloud
database.
"""
import asyncio
import importlib
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

ANON = "anonymous"


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-health-")
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


class TestHealthEndpoint:
    def _brand(self, api, name):
        from models import BrandProfileCreateRequest

        return _run(api.create_brand(payload=BrandProfileCreateRequest(
            brand_name=name,
            brand_description="A profile that exists.",
            core_features=["One feature"],
            primary_use_cases=["Testing"],
        ), user_id=ANON))

    def test_reports_the_backend_actually_in_use_not_the_configured_one(self, api):
        """
        The load-bearing assertion. `TURSO_DATABASE_URL` is empty in this
        process, so the configured answer is "local-sqlite" — but what a caller
        needs is the store this process will really read and write, which is
        what _ACTIVE_BACKEND records after the first connection.
        """
        # Open a connection so the active backend is established, as it is
        # after any real request.
        _run(api.list_brands(user_id=ANON))
        out = _run(api.health(user_id=ANON))
        assert out["status"] == "ok"
        # Whichever it is, it must be one of the three known labels, and it
        # must agree with the module's own view of itself.
        assert out["database"] in ("turso", "local-ephemeral-fallback", "local-sqlite")
        assert out["database"] == (api._ACTIVE_BACKEND or api._database_backend())

    def test_local_sqlite_is_reported_as_not_durable(self, api):
        """
        `durable` is the field a deploy should be judged by: anything but
        "turso" means writes die with the next restart. Reporting it as true
        here would be the one genuinely dangerous lie this endpoint could tell.
        """
        _run(api.list_brands(user_id=ANON))
        out = _run(api.health(user_id=ANON))
        assert out["durable"] is (out["database"] == "turso")
        assert out["durable"] is False

    def test_counts_the_callers_own_rows(self, api):
        """
        A founder needs to tell "ephemeral and empty" from "ephemeral and
        holding 40 generations" — different responses — and only the numbers
        distinguish them.
        """
        before = _run(api.health(user_id=ANON))
        assert before["your_rows"]["brand_profiles"] == 0
        assert before["your_rows"]["generations"] == 0

        self._brand(api, "Counted")

        after = _run(api.health(user_id=ANON))
        assert after["your_rows"]["brand_profiles"] == 1

    def test_counts_do_not_leak_another_users_rows(self, api):
        """
        The counts are inventory, so they are scoped to the caller. A global
        count would let one founder size up another's account, and this
        endpoint is reachable by anyone holding a valid token.
        """
        self._brand(api, "Mine")
        mine = _run(api.health(user_id=ANON))
        theirs = _run(api.health(user_id=f"other-{uuid.uuid4().hex}"))
        assert theirs["your_rows"]["brand_profiles"] == 0
        assert mine["your_rows"]["brand_profiles"] >= 1

    def test_an_ephemeral_fallback_is_named_rather_than_reported_as_turso(self, api):
        """
        The configuration this endpoint was written for. A previous version
        logged the CONFIGURED backend and so claimed cloud persistence while
        running on an ephemeral file — precisely backwards, and invisible until
        someone lost data.
        """
        out = api.health_database_report("local-ephemeral-fallback")
        assert out["database"] == "local-ephemeral-fallback"
        assert out["durable"] is False

    def test_turso_is_reported_as_durable(self, api):
        out = api.health_database_report("turso")
        assert out["database"] == "turso"
        assert out["durable"] is True

    def test_an_unopened_connection_is_not_claimed_as_cloud(self, api):
        """
        No backend yet must not read as the best case. `None` falls back to the
        local label, so the worst outcome is a redundant warning rather than a
        false all-clear.
        """
        out = api.health_database_report(None)
        assert out["database"] == "local-sqlite"
        assert out["durable"] is False

    def test_the_endpoint_reports_the_store_this_request_used(self, api):
        """
        `get_db` re-establishes _ACTIVE_BACKEND on every connection, so the
        endpoint reads it after its own queries: what matters is the store the
        request just read from, not a stale value from the previous one.
        """
        out = _run(api.health(user_id=ANON))
        assert out["database"] == api._ACTIVE_BACKEND