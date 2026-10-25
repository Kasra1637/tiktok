"""TikTok posted link: one nullable text column on the generation row.

Seam: set link -> get/detail/list/history. No stats, no TikTok API.
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
LINK = "https://www.tiktok.com/@founder/video/7345678901234567890"


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-link-")
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


def _set_link(api, generation_id, url, user_id=ANON):
    from models import TikTokLinkRequest

    return _run(api.set_generation_tiktok_link(
        generation_id, TikTokLinkRequest(tiktok_url=url), user_id))


class TestTikTokLink:
    def test_unset_link_reads_as_not_posted_everywhere(self, api):
        generation_id = _insert_generation(api)
        assert _run(api.get_generation(generation_id, ANON)).get("tiktok_url") is None
        history = _run(api.generation_history(user_id=ANON))["generations"]
        row = next(g for g in history if g["id"] == generation_id)
        assert row.get("tiktok_url") is None

    def test_setting_a_link_marks_the_render_posted(self, api):
        generation_id = _insert_generation(api)
        updated = _set_link(api, generation_id, LINK)
        assert updated.get("tiktok_url") == LINK
        assert _run(api.get_generation(generation_id, ANON)).get("tiktok_url") == LINK
        history = _run(api.generation_history(user_id=ANON))["generations"]
        row = next(g for g in history if g["id"] == generation_id)
        assert row.get("tiktok_url") == LINK

    def test_non_tiktok_urls_are_refused_not_stored(self, api):
        generation_id = _insert_generation(api)
        for bad in ["https://example.com/video/123", "not a url", "ftp://tiktok.com/x"]:
            with pytest.raises(HTTPException) as exc:
                _set_link(api, generation_id, bad)
            assert exc.value.status_code == 400
        assert _run(api.get_generation(generation_id, ANON)).get("tiktok_url") is None

    def test_empty_string_clears_the_link(self, api):
        generation_id = _insert_generation(api)
        _set_link(api, generation_id, LINK)
        cleared = _set_link(api, generation_id, "")
        assert cleared.get("tiktok_url") is None

    def test_another_users_render_is_not_found(self, api):
        generation_id = _insert_generation(api)
        with pytest.raises(HTTPException) as exc:
            _set_link(api, generation_id, LINK, user_id="someone-else")
        assert exc.value.status_code == 404
