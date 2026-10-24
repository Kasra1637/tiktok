"""Boot guard: hosted without a Clerk key refuses; local dev and tests pass.

Anonymous mode exists so a laptop and the test suite run without keys — it
must never serve production, where every request as 'anonymous' would merge
all users' data. These tests drive auth.ensure_auth_configured directly with
monkeypatched env (it reads the environment fresh, not the import-time
constant); no server import, so the guard itself can't break the suite.
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import auth


@pytest.fixture(autouse=True)
def _clean_hosted_signals(monkeypatch):
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("RENDER_SERVICE_NAME", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)


def _without_key(monkeypatch):
    monkeypatch.setenv("CLERK_JWKS_URL", "")


def test_missing_key_on_render_refuses(monkeypatch):
    _without_key(monkeypatch)
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(RuntimeError, match="CLERK_JWKS_URL"):
        auth.ensure_auth_configured()


def test_missing_key_on_render_service_name_refuses(monkeypatch):
    _without_key(monkeypatch)
    monkeypatch.setenv("RENDER_SERVICE_NAME", "hookforge")
    with pytest.raises(RuntimeError, match="CLERK_JWKS_URL"):
        auth.ensure_auth_configured()


def test_missing_key_in_production_env_refuses(monkeypatch):
    _without_key(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="CLERK_JWKS_URL"):
        auth.ensure_auth_configured()


def test_missing_key_local_dev_allowed(monkeypatch):
    _without_key(monkeypatch)
    assert auth.ensure_auth_configured() is None


def test_key_set_on_render_allowed(monkeypatch):
    monkeypatch.setenv("CLERK_JWKS_URL", "https://example.invalid/.well-known/jwks.json")
    monkeypatch.setenv("RENDER", "true")
    assert auth.ensure_auth_configured() is None
