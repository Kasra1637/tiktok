"""
Hashtag volume research (ADR 0139): research first, then select.

Pins the selection mix (three small, two larger, nothing at a
million-plus posts), the stepwise widening when a band is short, the
persisted cache (a hit avoids a second lookup; an expired entry is
researched again), and the mandatory fallback: any research outage
leaves generate_post_kit producing the kit from wording alone.

Everything runs offline — the volume source is an injected fake
fetcher, which is the seam the production lookup is built behind.
"""
import asyncio
import importlib
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import ai_service
import hashtag_volume


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-hashtags-")
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


POOL = [
    "#focus",           # the million-plus trap: most "relevant", never picked
    "#doomscrolling",   # small
    "#unresearched1",
    "#listchaos",       # small
    "#productivity",    # large
    "#phonehabits",     # small
    "#unresearched2",
    "#deepwork",        # large
    "#appcategory",
    "#nicheone",
    "#nichetwo",
    "#focusapp",
    "#smallwin",
]

COUNTS = {
    "#focus": 2_400_000,
    "#doomscrolling": 22_000,
    "#listchaos": 41_000,
    "#productivity": 320_000,
    "#phonehabits": 18_000,
    "#deepwork": 160_000,
    "#appcategory": 900_000,
    "#smallwin": 12_000,
}


class TestSelection:
    def test_three_small_two_large_and_never_million_plus(self):
        picked = hashtag_volume.select_hashtags_by_volume(POOL, COUNTS)
        # Pool order is preserved in the answer; the million-plus tag and
        # the over-band extras (#appcategory is past the large band but
        # legitimately fillable — the mix fills exactly first) stay out:
        # 3 small (doomscrolling, listchaos, phonehabits) + 2 large
        # (productivity, deepwork) is the mix, exactly.
        assert picked == [
            "#doomscrolling",
            "#listchaos",
            "#productivity",
            "#phonehabits",
            "#deepwork",
        ]
        counts = [COUNTS[t] for t in picked]
        assert sum(1 for c in counts if 10_000 <= c <= 50_000) == 3
        assert sum(1 for c in counts if 100_000 <= c <= 500_000) == 2
        assert all(c < 1_000_000 for c in counts)

    def test_widening_fills_a_short_band_from_the_nearest_range(self):
        pool = ["#a", "#b", "#c", "#d", "#e", "#f", "#g"]
        counts = {
            "#a": 20_000,    # small
            "#b": 30_000,    # small
            "#c": 75_000,    # small, widened range only
            "#d": 200_000,   # large
            "#e": 800_000,   # large, widened range only (still under cap)
            "#f": 15_000,    # another true small — band order beats widening
            "#g": 5_000_000, # never
        }
        picked = hashtag_volume.select_hashtags_by_volume(pool, counts)
        assert picked == ["#a", "#b", "#c", "#d", "#f"]
        # The third small slot went to #f, a true-band tag later in the
        # pool, before any widened candidate; the second large slot,
        # unfilled in-band, went to the nearest researched tag under the
        # cap (#c at 75k) rather than the 800k tag near the cap (#e).

    def test_thin_research_selects_nothing(self):
        # Only four researched tags under the cap: padding the set with
        # an unchecked tag is exactly what the rule forbids.
        counts = {"#a": 20_000, "#b": 200_000, "#c": 30_000, "#d": 150_000}
        assert hashtag_volume.select_hashtags_by_volume(
            ["#a", "#b", "#c", "#d", "#e"], counts) is None
        assert hashtag_volume.select_hashtags_by_volume(POOL, {}) is None

    def test_million_plus_is_never_a_fill(self):
        pool = ["#a", "#b", "#c", "#d", "#e", "#f"]
        counts = {
            "#a": 20_000, "#b": 30_000, "#c": 200_000,
            "#d": 2_000_000, "#e": 3_000_000, "#f": 40_000,
        }
        # Eligible researched tags: a, b, c, f — four. Not five, and the
        # two giants must not become the fifth.
        assert hashtag_volume.select_hashtags_by_volume(pool, counts) is None


class TestLookupCache:
    def test_second_lookup_is_a_cache_hit(self, api):
        async def main():
            calls = []

            async def fetcher(tags):
                calls.append(list(tags))
                return {t: 25_000 for t in tags}

            tags = ["#cachealpha", "#cachebeta", "#cachegamma"]
            first = await hashtag_volume.lookup_hashtag_counts(
                tags, fetcher=fetcher)
            assert first == {t: 25_000 for t in tags}
            assert len(calls) == 1

            second = await hashtag_volume.lookup_hashtag_counts(
                tags, fetcher=fetcher)
            assert second == first
            assert len(calls) == 1  # no second research for the same niche

        _run(main())

    def test_expired_cache_is_researched_again(self, api):
        async def main():
            t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

            async def fetcher_a(tags):
                return {t: 11_000 for t in tags}

            async def fetcher_b(tags):
                return {t: 99_000 for t in tags}

            tags = ["#ttlalpha"]
            got = await hashtag_volume.lookup_hashtag_counts(
                tags, fetcher=fetcher_a, now=t0)
            assert got == {"#ttlalpha": 11_000}
            got = await hashtag_volume.lookup_hashtag_counts(
                tags, fetcher=fetcher_b, now=t0 + timedelta(days=8))
            assert got == {"#ttlalpha": 99_000}

        _run(main())

    def test_partial_counts_are_cached_and_only_misses_refetch(self, api):
        async def main():
            calls = []

            async def fetcher(tags):
                calls.append(list(tags))
                return {tags[0]: 33_000} if tags else {}

            tags = ["#partone", "#parttwo"]
            first = await hashtag_volume.lookup_hashtag_counts(
                tags, fetcher=fetcher)
            assert first == {"#partone": 33_000}
            await hashtag_volume.lookup_hashtag_counts(tags, fetcher=fetcher)
            # The cached tag was not re-researched; the miss was retried.
            assert calls[1] == ["#parttwo"]

        _run(main())

    def test_fetcher_failure_returns_no_counts_and_never_raises(self, api):
        async def main():
            async def boom(tags):
                raise RuntimeError("source is down")

            assert await hashtag_volume.lookup_hashtag_counts(
                ["#downalpha"], fetcher=boom) == {}

        _run(main())


PROJECT = {
    "hook_line": "You do not have a focus problem.",
    "script": "You have too many lists, and every one of them asks for you.",
    "cta": "Clear one list by hand today.",
    "objective": "address_user_problem",
    "audience": "people with too many lists",
}
PROFILE = {
    "id": "app-1",
    "brand_name": "FocusTimer",
    "status": "approved",
    "brand_description": "One list, not eleven.",
    "app_category": "productivity",
    "target_audience": ["people with too many lists"],
    "claims_banned": ["cures ADHD"],
}
CAPTION = "I stopped fighting my phone and cleared one list instead — you?"


def _kit_payload(tags):
    return {"caption": CAPTION, "hashtags": tags,
            "cover_text": "One list, not eleven"}


class TestGeneratePostKitResearch:
    def test_the_five_are_chosen_by_volume(self, api, monkeypatch):
        # The cache is real in this file (the api fixture's database):
        # start from empty so the research, not a neighbour test's
        # leftovers, drives the choice.
        _run(api._execute("DELETE FROM hashtag_volume_cache"))
        monkeypatch.setattr(
            ai_service, "_chat_json",
            AsyncMock(return_value=_kit_payload(POOL)))

        async def fetcher(tags):
            return {t: COUNTS[t] for t in tags if t in COUNTS}

        monkeypatch.setattr(
            hashtag_volume, "_fetch_counts_from_creative_center", fetcher)
        out = asyncio.run(ai_service.generate_post_kit(PROJECT, PROFILE))
        assert out["hashtags"] == [
            "#doomscrolling",
            "#listchaos",
            "#productivity",
            "#phonehabits",
            "#deepwork",
        ]

    def test_research_outage_falls_back_to_wording(self, api, monkeypatch):
        _run(api._execute("DELETE FROM hashtag_volume_cache"))
        monkeypatch.setattr(
            ai_service, "_chat_json",
            AsyncMock(return_value=_kit_payload(POOL)))

        async def boom(tags):
            raise RuntimeError("no volume source today")

        monkeypatch.setattr(
            hashtag_volume, "_fetch_counts_from_creative_center", boom)
        out = asyncio.run(ai_service.generate_post_kit(PROJECT, PROFILE))
        # The kit still ships, with the model's first five on wording
        # alone — a finished video never loses its post copy to research.
        assert out["hashtags"] == POOL[:5]
        assert out["caption"] == CAPTION
