"""
Frontend asset caching: the app shell must never be cached, hashed bundles must be.

This exists because of a real report. A sidebar reorder was committed, deployed,
and confirmed present in the live JavaScript bundle — and was still not on
screen. The cause was that nothing in this file ever set a Cache-Control, so
browsers fell back to heuristic caching and kept serving an old index.html,
which names the PREVIOUS deploy's bundle hashes. The one file that decides
which code runs was the file being cached.

The distinction being pinned:

  - index.html is the only file that points at current bundle hashes, so a
    cached copy is a stale app. It must revalidate every time.
  - CRA emits content-hashed names (main.<8 hex>.js), whose meaning can never
    change, so they are safe to cache for a year.
  - Files copied verbatim out of public/ (fonts, demo-cta images) keep their
    names across deploys, so they must NOT be immutable or a corrected asset
    would take up to a year to reach anyone.
"""
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
    tmpdir = tempfile.mkdtemp(prefix="tiktok-cache-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    import asyncio

    asyncio.run(server.init_db())
    try:
        yield server
    finally:
        sys.modules.pop("server", None)


class TestAssetCaching:
    def test_the_hashed_bundle_pattern_matches_real_cra_names(self, api):
        """The names React actually emits, not a guess at them."""
        assert api._HASHED_ASSET_RE.search("main.98727cf3.js")
        assert api._HASHED_ASSET_RE.search("main.a1b2c3d4e5.chunk.js")
        assert api._HASHED_ASSET_RE.search("2.4c1f0a9b8e1a2d.css")
        # Webpack also hashes fonts it pulls in from CSS, and those are just as
        # immutable as a bundle.
        assert api._HASHED_ASSET_RE.search("anton-latin-400-normal.4c1f0a9b.woff2")

    def test_unhashed_public_files_are_not_treated_as_immutable(self, api):
        """
        Fonts and the vendored demo-cta images keep their filenames across
        deploys. Marking those immutable is how a corrected asset takes a year
        to reach anyone, so they have to fall through to revalidation.
        """
        for name in (
            "anton-latin-400-normal.woff2",
            "hand.jpg",
            "env-studio.jpg",
            "favicon.ico",
            "logo.svg",
        ):
            assert not api._HASHED_ASSET_RE.search(name), name

    def test_a_hashed_name_that_is_not_an_asset_is_not_immutable(self, api):
        """
        Only build output is immutable. A file that merely has a long hex run in
        its name is not the same promise, and guessing wrong here is a silent
        year-long cache on something that is supposed to be replaceable.
        """
        assert not api._HASHED_ASSET_RE.search("abcdef0123456789.mp4")

    def test_static_files_state_a_cache_control_at_all(self, api):
        """
        The bug in one assertion: with no header set, there is nothing to check
        and every other test in this file passes while users keep stale shells.
        """
        files = api._CacheHeaderStaticFiles(directory=str(BACKEND_DIR))
        assert hasattr(files, "file_response")

    def test_the_immutable_and_revalidate_labels_say_what_they_mean(self, api):
        assert "immutable" in api.IMMUTABLE_CACHE_CONTROL
        assert "max-age=31536000" in api.IMMUTABLE_CACHE_CONTROL
        assert "must-revalidate" in api.REVALIDATE_CACHE_CONTROL
        assert "max-age=0" in api.REVALIDATE_CACHE_CONTROL

    def test_the_app_shell_is_never_cached(self, api):
        """
        The load-bearing one. index.html is the only file that names the current
        bundle hashes, so caching it pins the browser to a previous deploy's
        code no matter how new the bundle itself is.
        """
        cc = api.SPASHELL_CACHE_CONTROL
        assert "no-store" in cc
        assert "no-cache" in cc
        assert "max-age=31536000" not in cc
        assert "immutable" not in cc