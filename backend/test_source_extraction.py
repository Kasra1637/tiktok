"""
Source extraction quality: store listings, JS shells, and fetch reporting.

Research reads whatever a plain HTTP fetch returns for a URL. Two page
shapes matter here and behave very differently:

- Store listings (App Store / Play) serve meta descriptions and JSON-LD
  with the real product facts even when the visible body is a
  client-rendered shell. The old stripper dropped <head> entirely, so those
  facts never reached research.
- JS-heavy shells serve almost nothing (a title, a root div, script tags).
  No regex improvement can render JavaScript, so those stay honestly thin —
  and the per-source report marks them by their character count rather than
  inventing text.

No network in these tests: fixtures are small but shape-faithful page
samples, and the fetch layer is faked. A browser renderer is deliberately
NOT added: these tests are the evidence gate for it, and they show the
honest-failure path covers what enrichment cannot.
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

import ai_service


def _run(coro):
    return asyncio.run(coro)


STORE_HTML = """<!doctype html><html lang="en"><head>
<title>Taskly \u2013 Focus Timer on the App Store</title>
<meta name="description" content="Taskly is a focus timer that starts in one tap, with reminders that keep you on track.">
<meta property="og:description" content="Stop stalling on setup. Start tasks in one tap.">
<script type="application/ld+json">{"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "Taskly", "applicationCategory": "Productivity", "description": "A focus timer for people who stall on starting."}</script>
</head><body>
<header><nav>App Store Preview</nav></header>
<h1>Taskly</h1>
<div id="app-content"></div>
<script src="/assets/bundle.min.js"></script>
</body></html>"""

PLAY_HTML = """<html><head>
<meta content="Block spam calls automatically with live screening." name="description">
<script type="application/ld+json">[{"@type": "SoftwareApplication", "name": "TrueCall", "description": "Call filter with live screening."}]</script>
<script type="application/ld+json">not json at all{{{</script>
<title>TrueCall - Apps on Google Play</title>
</head><body><h1>TrueCall</h1><div id="root"></div><script src="/x.js"></script></body></html>"""

JS_SHELL_HTML = """<html><head><title>SomeApp \u2013 Do Things Faster</title>
<script src="/static/js/main.abc123.js"></script></head>
<body><div id="root"></div><noscript>Enable JavaScript to run this app</noscript></body></html>"""


class TestStoreListingExtraction:
    def test_app_store_facts_survive_without_body_text(self):
        """
        The visible body here is one heading plus nav: the product facts live
        in meta and JSON-LD, which the old head-stripping extractor dropped.
        """
        out = ai_service.page_text_with_metadata(STORE_HTML)
        assert "starts in one tap" in out
        assert "reminders that keep you on track" in out
        assert "stall on starting" in out

    def test_content_first_meta_order_and_broken_json_ld(self):
        """
        Store pages put content= before name=, and ship several JSON-LD
        blocks. The parser must not depend on attribute order, and one
        malformed block must not poison the rest.
        """
        out = ai_service.page_text_with_metadata(PLAY_HTML)
        assert "Block spam calls automatically with live screening" in out
        assert "Call filter with live screening" in out
        assert "not json at all" not in out

    def test_body_stays_primary(self):
        out = ai_service.page_text_with_metadata(STORE_HTML)
        assert "App Store Preview" in out
        assert "Taskly" in out

    def test_exact_duplicate_blocks_appear_once(self):
        html = (
            '<html><head><meta name="description" content="Same words here.">'
            "<title>T</title></head><body><p>Same words here.</p></body></html>"
        )
        assert ai_service.page_text_with_metadata(html).count("Same words here.") == 1

    def test_plain_body_is_unchanged(self):
        """
        Pages with no metadata get exactly what the old extractor gave:
        enrichment adds, never rewrites.
        """
        assert ai_service.page_text_with_metadata(
            "<html><body><p>Just body text.</p></body></html>") == "Just body text."


class TestJsShellBoundary:
    def test_a_script_rendered_shell_yields_only_its_title(self):
        """
        The evidence gate for a browser renderer: no regex can execute
        JavaScript, so a shell honestly yields its title and nothing else.
        The per-source report (chars) is what marks it thin downstream —
        not invented text here.
        """
        out = ai_service.page_text_with_metadata(JS_SHELL_HTML)
        assert "SomeApp" in out
        assert len(out) < 100


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-srcext-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    asyncio.run(server.init_db())
    yield server
    sys.modules.pop("server", None)


class TestConcurrentFetchReport:
    def test_sources_fetch_concurrently_with_per_source_report(self, api, monkeypatch):
        """
        Three labeled fetches must overlap (each waits for all three to have
        started — sequential code deadlocks here), and the report must say
        per source what was read and what failed.
        """
        started = []
        release = asyncio.Event()

        async def fake_fetch(url, cap):
            started.append(url)
            if len(started) == 3:
                release.set()
            await asyncio.wait_for(release.wait(), timeout=5)
            return {"https://a.example": "aaa", "https://b.example": "",
                    "https://c.example": "ccc"}[url]

        monkeypatch.setattr(api, "_fetch_url_text", fake_fetch)
        existing = {"website_url": "https://a.example",
                    "appstore_url": "https://b.example",
                    "support_urls": ["https://c.example"]}
        sources, report = _run(api._research_profile_sources(existing))
        assert sorted(started) == ["https://a.example", "https://b.example",
                                   "https://c.example"]
        assert sources == {"website": "aaa", "app_store": "",
                           "support_1 (https://c.example)": "ccc"}
        assert [(r["label"], r["url"], r["chars"], r["ok"]) for r in report] == [
            ("website", "https://a.example", 3, True),
            ("app_store", "https://b.example", 0, False),
            ("support_1 (https://c.example)", "https://c.example", 3, True),
        ]

    def test_an_empty_run_raises_without_calling_the_model(self, api, monkeypatch):
        from fastapi import HTTPException

        async def fake_fetch(url, cap):
            return ""

        monkeypatch.setattr(api, "_fetch_url_text", fake_fetch)
        with pytest.raises(HTTPException) as err:
            _run(api._research_profile_sources({"website_url": "https://a.example"}))
        assert err.value.status_code == 400

    def test_no_urls_raises_before_any_fetch(self, api, monkeypatch):
        from fastapi import HTTPException
        calls = []

        async def fake_fetch(url, cap):
            calls.append(url)
            return "text"

        monkeypatch.setattr(api, "_fetch_url_text", fake_fetch)
        with pytest.raises(HTTPException) as err:
            _run(api._research_profile_sources({}))
        assert err.value.status_code == 400
        assert calls == []
