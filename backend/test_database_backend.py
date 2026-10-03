"""
Which database the app is actually writing to, and that it says so.

Two production incidents share one shape: the process boots against a store
that does not survive the host, and nothing in the logs says so until a user
reports vanished data. These tests pin both halves — the Turso replica pulls
cloud state on first connect (a fresh container starts with an empty replica
file), and a local-SQLite boot on Render logs it as the data-loss
configuration it is.
"""
import asyncio
import importlib
import logging
import os
import sys
import tempfile
import types
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))


class _FakeCursor:
    def fetchall(self):
        return []

    def fetchone(self):
        return None


class _FakeLibsqlConnection:
    """Stand-in for a libsql embedded-replica connection."""
    instances = []

    def __init__(self, *args, **kwargs):
        self.sync_calls = 0
        self.statements = []
        self.closed = False
        _FakeLibsqlConnection.instances.append(self)

    def execute(self, sql, params=()):
        self.statements.append(sql)
        return _FakeCursor()

    def sync(self):
        self.sync_calls += 1

    def commit(self):
        pass

    def close(self):
        self.closed = True


def _install_fake_libsql(monkeypatch, connect=None):
    """Route `import libsql_experimental` inside server.get_db to the fake."""
    module = types.ModuleType("libsql_experimental")
    if connect is None:
        module.connect = lambda *a, **k: _FakeLibsqlConnection(*a, **k)
    else:
        module.connect = connect
    monkeypatch.setitem(sys.modules, "libsql_experimental", module)
    return module


@pytest.fixture(scope="module")
def api():
    """server imported with a Turso URL configured, like production should be."""
    tmpdir = tempfile.mkdtemp(prefix="tiktok-dbbackend-")
    os.environ["TURSO_DATABASE_URL"] = "libsql://prod-123.turso.io"
    os.environ["TURSO_AUTH_TOKEN"] = "test-token-not-real"
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    _FakeLibsqlConnection.instances.clear()

    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    yield server
    for var in ("TURSO_DATABASE_URL", "TURSO_AUTH_TOKEN"):
        os.environ.pop(var, None)
    sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


class TestTursoBootPull:
    def test_first_connection_pulls_cloud_state(self, api, monkeypatch):
        """
        A freshly deployed container starts with an empty replica file. Without
        a pull before the first read, every profile lookup sees nothing — which
        is indistinguishable from "the deploy deleted everything" even when the
        cloud copy is intact.
        """
        _install_fake_libsql(monkeypatch)
        api._TURSO_BOOT_SYNC_DONE = False
        _FakeLibsqlConnection.instances.clear()

        async def use():
            async with api.get_db():
                pass
        _run(use())

        assert len(_FakeLibsqlConnection.instances) == 1
        assert _FakeLibsqlConnection.instances[0].sync_calls == 1

    def test_no_pragma_on_the_turso_branch(self, api, monkeypatch):
        """
        PRAGMA journal_mode=WAL is a local-SQLite concern; on a libsql
        embedded replica the statement is unsupported, and issuing it took down
        the whole Turso branch — every boot fell back to ephemeral storage
        while the config said "Turso cloud". The branch must issue no PRAGMA
        at all.
        """
        _install_fake_libsql(monkeypatch)
        api._TURSO_BOOT_SYNC_DONE = False
        api._ACTIVE_BACKEND = None
        _FakeLibsqlConnection.instances.clear()

        async def use():
            async with api.get_db():
                pass
        _run(use())

        assert len(_FakeLibsqlConnection.instances) == 1
        assert _FakeLibsqlConnection.instances[0].sync_calls == 1
        pragmas = [s for c in _FakeLibsqlConnection.instances
                   for s in c.statements if "PRAGMA" in str(s).upper()]
        assert pragmas == [], pragmas
        assert api._ACTIVE_BACKEND == "turso"

    def test_pragma_rejection_no_longer_kills_turso(self, api, monkeypatch):
        """
        The production failure exactly: a connection whose execute() rejects
        PRAGMA with "unsupported statement" (what libsql raises on a replica)
        must still establish the Turso branch, because nothing issues one.
        """
        def connect_picky(*a, **k):
            conn = _FakeLibsqlConnection(*a, **k)
            real_execute = conn.execute

            def execute(sql, params=()):
                if "PRAGMA" in str(sql).upper():
                    raise RuntimeError("unsupported statement")
                return real_execute(sql, params)
            conn.execute = execute
            return conn
        _install_fake_libsql(monkeypatch, connect=connect_picky)
        api._TURSO_BOOT_SYNC_DONE = False
        api._ACTIVE_BACKEND = None

        async def use():
            async with api.get_db():
                pass
        _run(use())  # must not raise, must not fall back
        assert api._ACTIVE_BACKEND == "turso"

    def test_pull_happens_once_per_process(self, api, monkeypatch):
        """The pull is a boot concern, not a per-request tax."""
        _install_fake_libsql(monkeypatch)
        api._TURSO_BOOT_SYNC_DONE = False
        api._ACTIVE_BACKEND = None
        _FakeLibsqlConnection.instances.clear()

        async def use_twice():
            async with api.get_db():
                pass
            async with api.get_db():
                pass
        _run(use_twice())

        total_syncs = sum(c.sync_calls for c in _FakeLibsqlConnection.instances)
        assert total_syncs == 1

    def test_failed_pull_falls_back_loudly_not_silently_unsynced(self, api, monkeypatch, caplog):
        """
        A failed pull used to warn and continue on an UNSYNCED replica — which
        is operationally identical to local SQLite while reporting as Turso.
        Now it falls back like a connect failure: loud, ephemeral, and retrying
        on the next connection (the flag stays False).
        """
        def boom(*a, **k):
            conn = _FakeLibsqlConnection(*a, **k)

            def fail_sync():
                raise RuntimeError("network down")
            conn.sync = fail_sync
            return conn
        _install_fake_libsql(monkeypatch, connect=boom)
        api._TURSO_BOOT_SYNC_DONE = False
        api._ACTIVE_BACKEND = None

        async def use():
            async with api.get_db() as conn:
                await conn.execute("SELECT 1")  # served, from the fallback
        with caplog.at_level(logging.ERROR, logger="server"):
            _run(use())  # must not raise
        assert api._TURSO_BOOT_SYNC_DONE is False
        assert api._ACTIVE_BACKEND == "local-ephemeral-fallback"
        assert any("EPHEMERAL" in r.message for r in caplog.records)

    def test_broken_turso_falls_back_to_local_and_says_so(self, api, monkeypatch, caplog):
        """
        If Turso is configured but unreachable, the app keeps serving on local
        SQLite — but that fallback is ephemeral, so it must read as an error in
        the logs, never as a routine warning.
        """
        def boom(*a, **k):
            raise RuntimeError("connection refused")
        _install_fake_libsql(monkeypatch, connect=boom)
        api._TURSO_BOOT_SYNC_DONE = False
        api._ACTIVE_BACKEND = None

        async def use():
            async with api.get_db() as conn:
                await conn.execute("SELECT 1")
        with caplog.at_level(logging.ERROR, logger="server"):
            _run(use())
        assert api._ACTIVE_BACKEND == "local-ephemeral-fallback"
        assert any("EPHEMERAL" in r.message for r in caplog.records), \
            [r.message for r in caplog.records]


class TestBackendDisclosure:
    """
    _log_database_backend reports the ACTUAL backend get_db established, not
    the configured one. A previous version logged "Turso cloud" from config
    while the connection had in fact fallen back to ephemeral — precisely
    backwards, and visible in a real deploy log.
    """

    def _server_with(self, monkeypatch, turso_url, actual=None):
        monkeypatch.setattr("server.TURSO_DATABASE_URL", turso_url or "")
        monkeypatch.setattr("server._ACTIVE_BACKEND", actual)

    def test_local_dev_is_info_not_alarm(self, api, monkeypatch, caplog):
        monkeypatch.delenv("RENDER", raising=False)
        monkeypatch.delenv("RENDER_SERVICE_NAME", raising=False)
        self._server_with(monkeypatch, "", None)
        with caplog.at_level(logging.INFO, logger="server"):
            api._log_database_backend()
        assert not [r for r in caplog.records if r.levelno >= logging.CRITICAL]
        assert any("local SQLite" in r.message for r in caplog.records)

    def test_local_on_render_is_critical(self, api, monkeypatch, caplog):
        """
        Local SQLite on Render's ephemeral filesystem loses every profile on
        every deploy. When the process can tell it is on Render, booting that
        way must be a CRITICAL log line naming the fix — not something the
        next data-loss report discovers.
        """
        monkeypatch.setenv("RENDER", "true")
        self._server_with(monkeypatch, "", None)
        with caplog.at_level(logging.INFO, logger="server"):
            api._log_database_backend()
        critical = [r for r in caplog.records if r.levelno >= logging.CRITICAL]
        assert critical, "expected a CRITICAL line for ephemeral production storage"
        assert any("TURSO_DATABASE_URL" in r.message for r in critical)

    def test_turso_reports_cloud(self, api, monkeypatch, caplog):
        monkeypatch.delenv("RENDER", raising=False)
        monkeypatch.delenv("RENDER_SERVICE_NAME", raising=False)
        self._server_with(monkeypatch, "libsql://prod-123.turso.io", "turso")
        with caplog.at_level(logging.INFO, logger="server"):
            api._log_database_backend()
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("Turso cloud" in r.message for r in caplog.records)

    def test_actual_beats_configured(self, api, monkeypatch, caplog):
        """
        The production case that motivated this: TURSO_DATABASE_URL configured
        (so config says "turso") while the connection fell back to ephemeral.
        The log must report the fallback, never the config.
        """
        monkeypatch.delenv("RENDER", raising=False)
        monkeypatch.delenv("RENDER_SERVICE_NAME", raising=False)
        self._server_with(monkeypatch, "libsql://prod-123.turso.io",
                          "local-ephemeral-fallback")
        with caplog.at_level(logging.INFO, logger="server"):
            api._log_database_backend()
        assert any("EPHEMERAL" in r.message for r in caplog.records)
        assert not any("Turso cloud" in r.message for r in caplog.records)

    def test_fallback_on_render_is_critical(self, api, monkeypatch, caplog):
        monkeypatch.setenv("RENDER", "true")
        self._server_with(monkeypatch, "libsql://prod-123.turso.io",
                          "local-ephemeral-fallback")
        with caplog.at_level(logging.INFO, logger="server"):
            api._log_database_backend()
        critical = [r for r in caplog.records if r.levelno >= logging.CRITICAL]
        assert critical
        assert any("EPHEMERAL" in r.message for r in critical)

    def test_database_backend_helper(self, api, monkeypatch):
        self._server_with(monkeypatch, "", None)
        assert api._database_backend() == "local-sqlite"
        self._server_with(monkeypatch, "libsql://x.turso.io", None)
        assert api._database_backend() == "turso"
