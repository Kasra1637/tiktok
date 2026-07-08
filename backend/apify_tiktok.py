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
ACTOR_ID = "dami_studio/tiktok-scraper"
APIFY_RUN_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"


def is_configured() -> bool:
    return bool(APIFY_TOKEN)


def _parse_apify_video(item: dict) -> Optional[dict]:
    """Convert an Apify result item to our internal video format."""
    if item.get("type") != "video":
        return None

    video_url = item.get("webVideoUrl") or ""
    if not video_url:
        video_id = item.get("id", "")
        author_id = (item.get("author") or {}).get("uniqueId", "")
        if video_id and author_id:
            video_url = f"https://www.tiktok.com/@{author_id}/video/{video_id}"

    if not video_url:
        return None

    author = item.get("author") or {}
    video_meta = item.get("video") or {}

    return {
        "tiktok_url": video_url,
        "video_platform_id": str(item.get("id", "")),
        "creator": author.get("uniqueId", ""),
        "creator_display": author.get("nickname", "") or author.get("uniqueId", ""),
        "title": (item.get("text") or "Untitled")[:220],
        "view_count": item.get("playCount") or 0,
        "like_count": item.get("diggCount") or 0,
        "comment_count": item.get("commentCount") or 0,
        "share_count": item.get("shareCount") or 0,
        "duration": video_meta.get("duration") or 0,
        "thumbnail_url": video_meta.get("cover") or "",
    }


async def _run_actor(input_data: dict, timeout: int = 60) -> list:
    """Run the Apify Actor synchronously and return dataset items."""
    if not APIFY_TOKEN:
        logger.warning("APIFY_API_TOKEN not set — cannot fetch TikTok data.")
        return []

    params = {"token": APIFY_TOKEN}
    headers = {"Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                APIFY_RUN_URL,
                params=params,
                headers=headers,
                json=input_data,
            )
            resp.raise_for_status()
            items = resp.json()
            if isinstance(items, list):
                return items
            return []
    except httpx.TimeoutException:
        logger.warning(f"Apify actor timed out after {timeout}s")
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
        "profiles": [handle],
        "resultsPerPage": limit,
    }

    items = await _run_actor(input_data, timeout=45)
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
        "resultsPerPage": limit,
    }

    items = await _run_actor(input_data, timeout=45)
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
        "resultsPerPage": limit,
    }

    items = await _run_actor(input_data, timeout=45)
    results = []
    for item in items:
        parsed = _parse_apify_video(item)
        if parsed:
            results.append(parsed)
    return results[:limit]
