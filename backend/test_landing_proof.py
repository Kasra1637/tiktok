"""
GET /api/landing-proof: the landing hero pill's evidence (ADR 0260).

The pill above the hero headline quotes three numbers — plans drafted,
approved app profiles, curated hook structures — so every one of them has
to be a real count at request time, never a marketing figure. These tests
pin the response shape, that the counts match the rows actually in the
database, and that the deterministic baseline (what the pill renders on
first paint, before the fetch lands) is exactly the floor the endpoint
documents: zero for the two database counts, the curated catalog's size
for the structures.
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
    tmpdir = tempfile.mkdtemp(prefix="tiktok-landing-proof-")
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


class TestLandingProof:
    def test_shape_and_baseline(self, api):
        import template_library

        out = _run(api.landing_proof())
        assert out["live"] is True
        assert out["hook_structures"] == len(template_library.CURATED_TEMPLATES)
        assert out["baseline"] == {
            "plans_drafted": 0,
            "profiles_approved": 0,
            "hook_structures": len(template_library.CURATED_TEMPLATES),
        }
        assert isinstance(out["plans_drafted"], int)
        assert isinstance(out["profiles_approved"], int)

    def test_counts_match_seeded_rows(self, api):
        # Three profiles, two of them approved; two studio projects. The
        # endpoint counts across all accounts — it is public evidence
        # about the studio, not one founder's inventory (that is /api/health).
        for i, status in enumerate(["approved", "approved", "draft"]):
            _run(api._execute(
                "INSERT INTO brand_profiles (id, brand_name, status, user_id) "
                "VALUES (?, ?, ?, ?)",
                (f"lp-brand-{i}", f"Proof {i}", status, "anonymous"),
            ))
        for i in range(2):
            _run(api._execute(
                "INSERT INTO studio_projects (id, user_id) VALUES (?, ?)",
                (f"lp-project-{i}", "anonymous"),
            ))
        out = _run(api.landing_proof())
        assert out["profiles_approved"] == 2
        assert out["plans_drafted"] == 2

    def test_baseline_is_deterministic(self, api):
        from routers.health import landing_proof_baseline

        assert landing_proof_baseline() == landing_proof_baseline()
        out = _run(api.landing_proof())
        assert out["baseline"] == landing_proof_baseline()
