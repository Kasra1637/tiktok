"""
Production durability fails loud (ADR 0120, extending ADR 0083).

ADR 0083 covered a CONFIGURED Turso being unreachable: refuse local
fallback. The gap left over was the unconfigured case in a production
environment: no TURSO_DATABASE_URL on a hosted process quietly served from
ephemeral local SQLite, and health reported that as a plain `local-sqlite`.
These tests pin the extension, using the same hosted-environment signal as
the auth boot guard (auth._hosted_without_auth): Render markers, or
ENVIRONMENT/APP_ENV=production. Local/dev and test defaults are unchanged.
"""
import asyncio
import importlib
import logging
import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import auth
from routers.health import health_database_report

HOSTED_VARS = ("RENDER", "RENDER_SERVICE_NAME", "ENVIRONMENT", "APP_ENV")


@pytest.fixture(autouse=True)
def _clean_hosted_env(monkeypatch):
    for var in HOSTED_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-failloud-")
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


class TestHostedSignal:
    def test_no_signals_is_not_hosted(self):
        assert auth.hosted_environment() is False

    def test_render_marker_is_hosted(self, monkeypatch):
        monkeypatch.setenv("RENDER", "true")
        assert auth.hosted_environment() is True

    def test_environment_production_is_hosted(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        assert auth.hosted_environment() is True

    def test_environment_development_is_not_hosted(self, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        assert auth.hosted_environment() is False

    def test_hosted_without_auth_still_uses_the_signal(self, monkeypatch):
        # The boot guard's behaviour is unchanged by the extraction: hosted
        # + no Clerk key is hosted-without-auth; a key answers it.
        monkeypatch.setenv("RENDER", "true")
        monkeypatch.delenv("CLERK_JWKS_URL", raising=False)
        assert auth._hosted_without_auth() is True
        monkeypatch.setenv("CLERK_JWKS_URL", "https://example.clerk.accounts.dev/.well-known/jwks.json")
        assert auth._hosted_without_auth() is False


class TestHealthReport:
    def test_dev_labels_unchanged(self):
        for backend, durable in (
            ("turso", True),
            ("local-sqlite", False),
            ("local-ephemeral-fallback", False),
            ("unavailable", False),
        ):
            out = health_database_report(backend)
            assert out["database"] == backend
            assert out["durable"] is durable

    def test_production_without_turso_reports_unavailable(self):
        out = health_database_report(
            "local-sqlite", production=True, turso_configured=False
        )
        assert out["database"] == "unavailable"
        assert out["durable"] is False
        assert "TURSO_DATABASE_URL" in out["database_detail"]

    def test_production_with_turso_configured_keeps_the_label(self):
        out = health_database_report(
            "local-sqlite", production=True, turso_configured=True
        )
        assert out["database"] == "local-sqlite"

    def test_production_on_turso_is_durable(self):
        out = health_database_report("turso", production=True, turso_configured=True)
        assert out["database"] == "turso"
        assert out["durable"] is True


class TestStartupReporting:
    def test_production_local_db_logs_critical(self, api, monkeypatch, caplog):
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setattr("server.TURSO_DATABASE_URL", "")
        monkeypatch.setattr("server._ACTIVE_BACKEND", "local-sqlite")
        with caplog.at_level(logging.INFO, logger="server"):
            api._log_database_backend()
        critical = [r for r in caplog.records if r.levelno >= logging.CRITICAL]
        assert critical, "production without Turso must be a CRITICAL startup line"
        assert any("TURSO_DATABASE_URL" in r.message for r in critical)

    def test_local_dev_stays_info(self, api, monkeypatch, caplog):
        monkeypatch.setattr("server.TURSO_DATABASE_URL", "")
        monkeypatch.setattr("server._ACTIVE_BACKEND", "local-sqlite")
        with caplog.at_level(logging.INFO, logger="server"):
            api._log_database_backend()
        assert not [r for r in caplog.records if r.levelno >= logging.CRITICAL]

    def test_production_without_r2_logs_critical(self, api, monkeypatch, caplog):
        monkeypatch.setenv("RENDER", "true")
        monkeypatch.setattr(api.storage_service, "is_configured", lambda: False)
        with caplog.at_level(logging.INFO, logger="server"):
            api._log_storage_durability()
        critical = [r for r in caplog.records if r.levelno >= logging.CRITICAL]
        assert critical, "production without R2 must be a CRITICAL startup line"
        assert any("R2" in r.message for r in critical)

    def test_no_r2_alarm_in_dev_or_when_configured(self, api, monkeypatch, caplog):
        monkeypatch.setattr(api.storage_service, "is_configured", lambda: False)
        with caplog.at_level(logging.INFO, logger="server"):
            api._log_storage_durability()
        assert not [r for r in caplog.records if r.levelno >= logging.CRITICAL]

        monkeypatch.setenv("RENDER", "true")
        monkeypatch.setattr(api.storage_service, "is_configured", lambda: True)
        with caplog.at_level(logging.INFO, logger="server"):
            api._log_storage_durability()
        assert not [r for r in caplog.records if r.levelno >= logging.CRITICAL]


class TestHealthEndpointFields:
    def test_dev_health_shape_is_unchanged(self, api, monkeypatch):
        monkeypatch.setattr("server._ACTIVE_BACKEND", "local-sqlite")
        monkeypatch.setattr(api.storage_service, "is_configured", lambda: False)
        out = _run(api.health(user_id="anonymous"))
        assert out["database"] == "local-sqlite"
        assert out["durable"] is False
        assert out["media_durable"] is False
        assert "media_warning" not in out

    def test_production_health_reports_unavailable_and_warns(self, api, monkeypatch):
        monkeypatch.setenv("RENDER", "true")
        monkeypatch.setattr("server.TURSO_DATABASE_URL", "")
        monkeypatch.setattr("server._ACTIVE_BACKEND", "local-sqlite")
        monkeypatch.setattr(api.storage_service, "is_configured", lambda: False)
        out = _run(api.health(user_id="anonymous"))
        assert out["database"] == "unavailable"
        assert out["durable"] is False
        assert out["media_durable"] is False
        assert "media_warning" in out
