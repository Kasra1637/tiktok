"""
Apify TikTok Scraper integration.
Uses the dami_studio/tiktok-scraper Actor ($0.25/1K results) to fetch
TikTok profiles, hashtags, and search results without yt-dlp.

Requires APIFY_API_TOKEN environment variable.
Docs: https://apify.com/dami_studio/tiktok-scraper
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
ACTOR_ID = "clockworks~tiktok-scraper"
# Use the synchronous endpoint with a timeout parameter so Apify returns within Render's limits
APIFY_RUN_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"


def is_configured() -> bool:
    return bool(APIFY_TOKEN)


def _parse_apify_video(item: dict) -> Optional[dict]:
    """Convert an Apify result item to our internal video format. Handles multiple Actor output formats."""
    # Skip non-video items (profiles, etc.)
    item_type = item.get("type", "video")
    if item_type == "profile":
        return None

    # Try to extract video URL (different Actors use different field names)
    video_url = (
        item.get("webVideoUrl")
        or item.get("videoUrl")
        or item.get("url")
        or item.get("input")
        or ""
    )
    if not video_url:
        video_id = item.get("id", "")
        author_id = ""
        if isinstance(item.get("author"), dict):
            author_id = item["author"].get("uniqueId", "") or item["author"].get("id", "")
        elif item.get("authorMeta") and isinstance(item["authorMeta"], dict):
            author_id = item["authorMeta"].get("name", "") or item["authorMeta"].get("id", "")
        if video_id and author_id:
            video_url = f"https://www.tiktok.com/@{author_id}/video/{video_id}"

    if not video_url or "tiktok.com" not in video_url:
        return None

    # Extract author info (different formats)
    author = item.get("author") or item.get("authorMeta") or {}
    author_id = author.get("uniqueId") or author.get("name") or author.get("id") or ""
    author_name = author.get("nickname") or author.get("name") or author_id

    # Extract video metadata
    video_meta = item.get("video") or item.get("videoMeta") or {}

    # Extract counts (different field names across Actors)
    view_count = item.get("playCount") or item.get("plays") or item.get("view_count") or 0
    like_count = item.get("diggCount") or item.get("likes") or item.get("like_count") or 0
    comment_count = item.get("commentCount") or item.get("comments") or item.get("comment_count") or 0
    share_count = item.get("shareCount") or item.get("shares") or item.get("share_count") or 0

    # Extract text/title
    title = item.get("text") or item.get("description") or item.get("desc") or "Untitled"

    # Extract thumbnail
    thumbnail = (
        video_meta.get("cover")
        or video_meta.get("thumbnail")
        or item.get("covers", {}).get("default")
        or item.get("thumbnail_url")
        or ""
    )

    return {
        "tiktok_url": video_url,
        "video_platform_id": str(item.get("id", "")),
        "creator": author_id,
        "creator_display": author_name,
        "title": title[:220],
        "view_count": int(view_count) if view_count else 0,
        "like_count": int(like_count) if like_count else 0,
        "comment_count": int(comment_count) if comment_count else 0,
        "share_count": int(share_count) if share_count else 0,
        "duration": video_meta.get("duration") or item.get("duration") or 0,
        "thumbnail_url": thumbnail,
    }


async def _run_actor(input_data: dict, timeout: int = 120) -> list:
    """Run the Apify Actor synchronously and return dataset items."""
    if not APIFY_TOKEN:
        logger.warning("APIFY_API_TOKEN not set — cannot fetch TikTok data.")
        return []

    # timeout param tells Apify to wait up to this many seconds before returning
    params = {"token": APIFY_TOKEN, "timeout": 90}
    headers = {"Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            logger.info(f"Calling Apify actor with input: {input_data}")
            resp = await client.post(
                APIFY_RUN_URL,
                params=params,
                headers=headers,
                json=input_data,
            )
            if resp.status_code == 408:
                # Apify timeout — actor didn't finish in time but may have partial results
                logger.warning("Apify actor timed out (408) — no results yet")
                return []
            if resp.status_code != 200 and resp.status_code != 201:
                logger.error(f"Apify returned status {resp.status_code}: {resp.text[:500]}")
                return []
            items = resp.json()
            if isinstance(items, list):
                logger.info(f"Apify returned {len(items)} items")
                return items
            logger.warning(f"Apify returned non-list: {type(items)}")
            return []
    except httpx.TimeoutException:
        logger.warning(f"HTTP timeout after {timeout}s waiting for Apify")
        return []
    except Exception as e:
        logger.error(f"Apify actor failed: {e}")
        return []


async def fetch_creator_videos(handle: str, limit: int = 5) -> list:
    """Fetch latest videos from a TikTok creator profile via Apify."""
    handle = handle.lstrip("@").strip()
    if not handle:
        return []

    input_data = {
        "profiles": [f"https://www.tiktok.com/@{handle}"],
        "resultsPerPage": min(limit, 5),
    }

    items = await _run_actor(input_data, timeout=120)
    results = []
    for item in items:
        parsed = _parse_apify_video(item)
        if parsed:
            results.append(parsed)
    return results[:limit]


async def fetch_hashtag_videos(hashtag: str, limit: int = 20) -> list:
    """Fetch videos from a TikTok hashtag via Apify."""
    hashtag = hashtag.lstrip("#").strip()
    if not hashtag:
        return []

    input_data = {
        "hashtags": [hashtag],
        "resultsPerPage": min(limit, 10),
    }

    items = await _run_actor(input_data, timeout=120)
    results = []
    for item in items:
        parsed = _parse_apify_video(item)
        if parsed:
            parsed["source_hashtag"] = hashtag
            results.append(parsed)
    return results[:limit]


async def fetch_keyword_videos(keyword: str, limit: int = 20) -> list:
    """Search TikTok for videos matching a keyword via Apify."""
    keyword = keyword.strip()
    if not keyword:
        return []

    input_data = {
        "searchQueries": [keyword],
        "resultsPerPage": min(limit, 10),
    }

    items = await _run_actor(input_data, timeout=120)
    results = []
    for item in items:
        parsed = _parse_apify_video(item)
        if parsed:
            results.append(parsed)
    return results[:limit]
