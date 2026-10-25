"""TikTok pasted-back views: one nullable integer column on the generation row.

Seam: set views -> get/detail/list/history. Manual paste until any TikTok
API. Views never decide a winner; only thumbs up plus a link does.
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
    tmpdir = tempfile.mkdtemp(prefix="tiktok-views-")
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


def _set_views(api, generation_id, views, user_id=ANON):
    from models import TikTokViewsRequest

    return _run(api.set_generation_tiktok_views(
        generation_id, TikTokViewsRequest(tiktok_views=views), user_id))


class TestTikTokViews:
    def test_unset_views_read_as_null_everywhere(self, api):
        generation_id = _insert_generation(api)
        assert _run(api.get_generation(generation_id, ANON)).get("tiktok_views") is None
        history = _run(api.generation_history(user_id=ANON))["generations"]
        row = next(g for g in history if g["id"] == generation_id)
        assert row.get("tiktok_views") is None

    def test_setting_views_round_trips_everywhere(self, api):
        generation_id = _insert_generation(api)
        updated = _set_views(api, generation_id, 12400)
        assert updated.get("tiktok_views") == 12400
        assert _run(api.get_generation(generation_id, ANON)).get("tiktok_views") == 12400
        history = _run(api.generation_history(user_id=ANON))["generations"]
        row = next(g for g in history if g["id"] == generation_id)
        assert row.get("tiktok_views") == 12400

    def test_zero_is_a_count_not_a_clear(self, api):
        generation_id = _insert_generation(api)
        assert _set_views(api, generation_id, 0).get("tiktok_views") == 0

    def test_none_clears_the_count(self, api):
        generation_id = _insert_generation(api)
        _set_views(api, generation_id, 12400)
        assert _set_views(api, generation_id, None).get("tiktok_views") is None

    def test_negative_and_absurd_counts_are_refused_not_stored(self, api):
        generation_id = _insert_generation(api)
        for bad in [-1, -999, 10_000_000_001]:
            with pytest.raises(HTTPException) as exc:
                _set_views(api, generation_id, bad)
            assert exc.value.status_code == 400
        assert _run(api.get_generation(generation_id, ANON)).get("tiktok_views") is None

    @pytest.mark.parametrize("bad", [True, False, 1.5, 12.0, "123", "garbage"])
    def test_http_refuses_coercion_without_changing_saved_views(self, api, bad):
        import httpx

        generation_id = _insert_generation(api)
        _set_views(api, generation_id, 42)

        async def request():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=api.app), base_url="http://test"
            ) as client:
                return await client.post(
                    f"/api/generations/{generation_id}/tiktok-views",
                    json={"tiktok_views": bad},
                )

        assert _run(request()).status_code == 422
        assert _run(api.get_generation(generation_id, ANON))["tiktok_views"] == 42

    def test_upper_boundary_is_saved(self, api):
        generation_id = _insert_generation(api)
        assert _set_views(api, generation_id, 10_000_000_000)["tiktok_views"] == 10_000_000_000

    def test_another_users_render_is_not_found(self, api):
        generation_id = _insert_generation(api)
        with pytest.raises(HTTPException) as exc:
            _set_views(api, generation_id, 10, user_id="someone-else")
        assert exc.value.status_code == 404
