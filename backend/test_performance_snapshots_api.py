"""Dated performance snapshots for a posted clip (ADR 0117).

Seam: save a snapshot -> generation detail -> history list. A snapshot is
one dated reading of the numbers TikTok shows for the posted video — views,
3-second retention, average watch, saves, shares — pasted by hand, like the
view count before it. Snapshots accumulate; the latest reading is the one
reads show, and its views keep the legacy single view count current so
every existing surface keeps working.
"""
import asyncio
import importlib
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

ANON = "anonymous"


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-snapshots-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    os.environ.pop("VIDEO_MODEL_DEFAULT", None)
    os.environ.pop("VIDEO_MODEL_ALLOWLIST", None)

    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    original_dirs = (server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR)
    server.pipeline.VIDEOS_DIR = Path(tmpdir) / "videos"
    server.pipeline.GENERATED_DIR = Path(tmpdir) / "generated"
    server.pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    server.pipeline.GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    asyncio.run(server.init_db())
    try:
        yield server
    finally:
        server.pipeline.VIDEOS_DIR, server.pipeline.GENERATED_DIR = original_dirs
        sys.modules.pop("server", None)


def _run(coro):
    return asyncio.run(coro)


def _insert_generation(api, user_id=ANON):
    from models import now_iso

    generation_id = str(uuid.uuid4())
    now = now_iso()
    _run(api._execute(
        "INSERT INTO generations (id, user_id, status, created_at, updated_at)"
        " VALUES (?, ?, 'completed', ?, ?)",
        (generation_id, user_id, now, now),
    ))
    return generation_id


def _save_snapshot(api, generation_id, user_id=ANON, **metrics):
    from models import PerformanceSnapshotRequest

    return _run(api.set_generation_performance_snapshot(
        generation_id, PerformanceSnapshotRequest(**metrics), user_id))


def _history_row(api, generation_id):
    history = _run(api.generation_history(user_id=ANON))["generations"]
    return next(g for g in history if g["id"] == generation_id)


class TestPerformanceSnapshots:
    def test_no_snapshot_reads_as_none(self, api):
        generation_id = _insert_generation(api)
        assert _run(api.get_generation(generation_id, ANON)).get("performance_snapshot") is None
        assert _history_row(api, generation_id).get("performance_snapshot") is None

    def test_snapshot_round_trips_to_detail_and_history(self, api):
        generation_id = _insert_generation(api)
        updated = _save_snapshot(
            api, generation_id, views=1000, retention_3s_pct=63,
            avg_watch_pct=41, saves=30, shares=12)
        snap = updated["performance_snapshot"]
        assert snap["views"] == 1000
        assert snap["retention_3s_pct"] == 63
        assert snap["avg_watch_pct"] == 41
        assert snap["saves"] == 30
        assert snap["shares"] == 12
        assert snap["recorded_at"]
        detail = _run(api.get_generation(generation_id, ANON))
        assert detail["performance_snapshot"] == snap
        assert _history_row(api, generation_id)["performance_snapshot"] == snap

    def test_latest_snapshot_wins_and_its_views_update_the_legacy_count(self, api):
        generation_id = _insert_generation(api)
        _save_snapshot(api, generation_id, views=1000, saves=30)
        updated = _save_snapshot(api, generation_id, views=2500)
        snap = updated["performance_snapshot"]
        assert snap["views"] == 2500
        # A snapshot is one dated reading, not a merge: fields the new
        # reading does not carry read as absent, not as last week's numbers.
        assert snap["saves"] is None
        detail = _run(api.get_generation(generation_id, ANON))
        assert detail["tiktok_views"] == 2500
        assert detail["tiktok_views_at"] == snap["recorded_at"]
        rows = _run(api._fetch_all(
            "SELECT * FROM performance_snapshots WHERE generation_id = ?",
            (generation_id,)))
        assert len(rows) == 2

    def test_snapshot_without_views_leaves_the_legacy_count_alone(self, api):
        from models import TikTokViewsRequest

        generation_id = _insert_generation(api)
        _run(api.set_generation_tiktok_views(
            generation_id, TikTokViewsRequest(tiktok_views=500), ANON))
        _save_snapshot(api, generation_id, saves=5)
        detail = _run(api.get_generation(generation_id, ANON))
        assert detail["tiktok_views"] == 500
        assert detail["performance_snapshot"]["saves"] == 5
        # The snapshot inherits the stored count, so the dated record of
        # that day is complete rather than missing its views.
        assert detail["performance_snapshot"]["views"] == 500

    def test_empty_snapshot_is_refused(self, api):
        generation_id = _insert_generation(api)
        with pytest.raises(HTTPException) as exc:
            _save_snapshot(api, generation_id)
        assert exc.value.status_code == 400
        assert _run(api.get_generation(generation_id, ANON))["performance_snapshot"] is None

    @pytest.mark.parametrize("metrics", [
        {"retention_3s_pct": 101},
        {"retention_3s_pct": -1},
        {"avg_watch_pct": 101},
        {"saves": -1},
        {"shares": -3},
        {"views": -1},
        {"views": 10_000_000_001},
    ])
    def test_out_of_range_metrics_are_refused_not_stored(self, api, metrics):
        generation_id = _insert_generation(api)
        with pytest.raises(HTTPException) as exc:
            _save_snapshot(api, generation_id, **metrics)
        assert exc.value.status_code == 400
        assert _run(api.get_generation(generation_id, ANON))["performance_snapshot"] is None

    def test_percentage_boundaries_are_saved(self, api):
        generation_id = _insert_generation(api)
        updated = _save_snapshot(api, generation_id, retention_3s_pct=0, avg_watch_pct=100)
        assert updated["performance_snapshot"]["retention_3s_pct"] == 0
        assert updated["performance_snapshot"]["avg_watch_pct"] == 100

    @pytest.mark.parametrize("metrics", [
        {"views": "123"},
        {"views": 1.5},
        {"retention_3s_pct": "high"},
        {"avg_watch_pct": True},
        {"saves": "many"},
    ])
    def test_http_refuses_coercion(self, api, metrics):
        import httpx

        generation_id = _insert_generation(api)

        async def request():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=api.app), base_url="http://test"
            ) as client:
                return await client.post(
                    f"/api/generations/{generation_id}/performance-snapshot",
                    json=metrics,
                )

        assert _run(request()).status_code == 422
        assert _run(api.get_generation(generation_id, ANON))["performance_snapshot"] is None

    def test_another_users_render_is_not_found(self, api):
        generation_id = _insert_generation(api)
        with pytest.raises(HTTPException) as exc:
            _save_snapshot(api, generation_id, user_id="someone-else", views=10)
        assert exc.value.status_code == 404
