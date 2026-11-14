"""
Hashtag volume research for the post kit (ADR 0139): research first,
then select.

The kit used to take the model's 4 to 6 hashtags on wording alone. The
founder's rule: the model proposes a wider pool of niche candidates for
the clip (12 to 15, ordered most relevant first — relevance is a hard
requirement, never generic popular tags), each candidate's TikTok post
count is looked up best-effort, and exactly five are selected by size:
three small (roughly 10k-50k posts) and two larger (roughly 100k-500k),
nothing at a million-plus posts, where a small account's clip is buried
before it starts.

There is no official hashtag-volume API. The default fetcher targets
TikTok's Creative Center radar API — the canonical public source for
hashtag post counts — but at build time every public source checked was
closed from a server context (the radar API answered 40101 "no
permission", the challenge detail API and tag pages carry no count, the
public proxies returned nothing). So the lookup is built to be wrong
safely: it sits behind an injectable fetcher seam, caches what it learns
for days, and ANY failure — timeout, refusal, unusable payload, dead
cache — degrades to "no counts", which sends selection back to the
wording-only fallback in generate_post_kit. A finished video must never
lose its post copy over a research outage.
"""
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

import db

logger = logging.getLogger(__name__)

# The mix, as named data so it can be tuned in one place: exactly five
# tags — three in the small band, two in the large band, and nothing at
# or over the million-plus cap.
HASHTAG_TARGET_COUNT = 5
HASHTAG_MIX = {"small": 3, "large": 2}
SMALL_BAND = (10_000, 50_000)
LARGE_BAND = (100_000, 500_000)
HASHTAG_MAX_POSTS = 1_000_000

# Widening, tried in order when a band cannot be filled from the pool:
# the nearest neighbouring range first, and only then any researched tag
# under the cap. Widening never invents an unchecked tag and never
# crosses the million-plus cap.
SMALL_BAND_WIDENED = (5_000, 100_000)
LARGE_BAND_WIDENED = (50_000, 1_000_000)

# Researched counts are approximate and drift slowly; a week is fresh
# enough for band selection and keeps a niche from being re-researched
# on every render.
CACHE_TTL = timedelta(days=7)

# The whole research for one kit is capped well inside the post-kit's
# own budgets: a slow source must degrade to the fallback, not stall it.
LOOKUP_TIMEOUT_SECONDS = 4.0
LOOKUP_DEADLINE_SECONDS = 20.0

_RADAR_URL = (
    "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"
)
_RADAR_COUNT_KEYS = ("video_count", "post_count", "videoCount", "postCount",
                     "videos", "posts", "count")


def _tag_body(tag) -> str:
    return str(tag or "").strip().lstrip("#").lower()


def select_hashtags_by_volume(candidates, counts):
    """
    Choose the kit's five from the candidate pool by researched size.

    `candidates` is the model's pool in relevance order; `counts` maps a
    candidate (as written in the pool) to its post count. Returns exactly
    HASHTAG_TARGET_COUNT tags in pool order, or None when the research
    cannot honestly fill the mix — fewer than five researched candidates
    under the cap — so the caller falls back to wording alone rather
    than padding the set with unchecked tags.
    """
    known = []
    for tag in candidates or []:
        count = (counts or {}).get(tag)
        if isinstance(count, bool) or not isinstance(count, (int, float)):
            continue
        count = int(count)
        if 0 <= count < HASHTAG_MAX_POSTS:
            known.append((tag, count))
    if len(known) < HASHTAG_TARGET_COUNT:
        return None

    picked = []

    def fill(band, want):
        for tag, count in known:
            if want <= 0:
                break
            if tag in picked:
                continue
            if band[0] <= count <= band[1]:
                picked.append(tag)
                want -= 1
        return want

    small_owed = fill(SMALL_BAND, HASHTAG_MIX["small"])
    large_owed = fill(LARGE_BAND, HASHTAG_MIX["large"])
    if small_owed:
        small_owed = fill(SMALL_BAND_WIDENED, small_owed)
    if large_owed:
        large_owed = fill(LARGE_BAND_WIDENED, large_owed)
    if small_owed or large_owed:
        fill((0, HASHTAG_MAX_POSTS - 1), small_owed + large_owed)
    if len(picked) != HASHTAG_TARGET_COUNT:
        return None
    order = {tag: i for i, tag in enumerate(candidates)}
    return sorted(picked, key=lambda tag: order[tag])


def _extract_radar_count(node, body):
    """Walk a radar payload for the named hashtag's count, or None.

    The radar response shape is not a contract — it has moved before —
    so this accepts any nesting that pairs the tag's name with one of
    the known count fields, and nothing else.
    """
    if isinstance(node, dict):
        name = node.get("hashtag_name") or node.get("name") or node.get("title")
        if isinstance(name, str) and _tag_body(name) == body:
            for key in _RADAR_COUNT_KEYS:
                value = node.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return int(value)
        for value in node.values():
            found = _extract_radar_count(value, body)
            if found is not None:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _extract_radar_count(item, body)
            if found is not None:
                return found
    return None


async def _fetch_counts_from_creative_center(tags):
    """
    The default volume source: TikTok Creative Center's radar API.

    Best-effort by design (ADR 0139): it answered 40101 "no permission"
    from every environment checked at build time — it expects a Creative
    Center session in most postures — so a non-200, a timeout, or a
    payload without the tag's count simply yields no count for that tag.
    """
    counts = {}
    deadline = time.monotonic() + LOOKUP_DEADLINE_SECONDS
    async with httpx.AsyncClient(timeout=LOOKUP_TIMEOUT_SECONDS) as client:
        for tag in tags:
            if time.monotonic() > deadline:
                break
            body = _tag_body(tag)
            if not body:
                continue
            try:
                resp = await client.get(
                    _RADAR_URL,
                    params={"page": 1, "limit": 10, "period": 30,
                            "keyword": body},
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 (X11; Linux x86_64) "
                            "AppleWebKit/537.36"
                        )
                    },
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
            except Exception:
                continue
            count = _extract_radar_count(data, body)
            if count is not None:
                counts[tag] = count
    return counts


async def _read_cache(bodies, now):
    """Fresh cached counts for the given tag bodies; {} on any failure."""
    if not bodies:
        return {}
    placeholders = ", ".join("?" for _ in bodies)
    rows = await db._fetch_all(
        f"SELECT tag, post_count, fetched_at FROM hashtag_volume_cache "
        f"WHERE tag IN ({placeholders})",
        tuple(bodies),
    )
    fresh = {}
    for row in rows or []:
        try:
            fetched_at = datetime.fromisoformat(row["fetched_at"])
        except (TypeError, ValueError):
            continue
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        if now - fetched_at < CACHE_TTL:
            fresh[row["tag"]] = int(row["post_count"])
    return fresh


async def _write_cache(counts_by_body, now):
    for body, count in counts_by_body.items():
        await db._execute(
            "INSERT OR REPLACE INTO hashtag_volume_cache "
            "(tag, post_count, fetched_at) VALUES (?, ?, ?)",
            (body, int(count), now.isoformat()),
        )


async def lookup_hashtag_counts(tags, *, fetcher=None, now=None):
    """
    Post counts for the given tags ('#tag' or bare), keyed as passed in.

    Cache first (CACHE_TTL), the fetcher for the rest; fetched counts are
    written back to the cache. NEVER raises: any failure anywhere —
    cache, network, payload — returns whatever counts are known,
    possibly none, and the caller treats "no counts" as a research
    outage and falls back to wording alone.
    """
    try:
        return await _lookup(tags, fetcher=fetcher, now=now)
    except Exception as e:
        logger.warning("Hashtag volume lookup failed (%s); counts unknown", e)
        return {}


async def _lookup(tags, *, fetcher, now):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    wanted = {}
    for tag in tags or []:
        body = _tag_body(tag)
        if body:
            wanted.setdefault(body, tag)
    if not wanted:
        return {}

    try:
        cached = await _read_cache(list(wanted), now)
    except Exception:
        cached = {}
    counts = {wanted[body]: count for body, count in cached.items()}

    missing = [tag for body, tag in wanted.items() if body not in cached]
    if missing:
        fetch = fetcher or _fetch_counts_from_creative_center
        try:
            fetched = await fetch(missing)
        except Exception:
            fetched = {}
        fresh = {}
        for tag, count in (fetched or {}).items():
            if isinstance(count, bool) or not isinstance(count, (int, float)):
                continue
            counts[tag] = int(count)
            body = _tag_body(tag)
            if body:
                fresh[body] = int(count)
        if fresh:
            try:
                await _write_cache(fresh, now)
            except Exception:
                pass  # an unwritten cache costs a re-lookup, never a kit
    return counts
