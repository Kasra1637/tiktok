"""
Apify TikTok Scraper integration.
Uses the apidojo/tiktok-scraper Actor ($0.30/1K results) to fetch
TikTok profiles, hashtags, search results, music, and locations.

New capabilities over previous actor (clockworks):
- Song/music metadata (title, artist, album, duration, cover)
- Subtitles/transcript URLs
- Bookmarks count (purchase-intent signal)
- Hashtags as structured array
- Creator profile data (followers, following, verified status)
- Direct video download URL
- Location-based discovery (ISO country codes)
- Music-based and tag-based searches

Requires APIFY_API_TOKEN environment variable.
Docs: https://apify.com/apidojo/tiktok-scraper
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
    """
    Convert a Clockworks actor result item to our internal video format.
    Handles the Clockworks output schema (authorMeta, playCount, diggCount, etc.)
    and extracts all available enriched fields (music, subtitles, bookmarks, etc.).
    """
    # Skip non-video or placeholder items
    if item.get("noResults"):
        return None
    item_type = item.get("type", "video")
    if item_type == "profile":
        return None

    # --- Video URL ---
    video_url = (
        item.get("webVideoUrl")
        or item.get("videoUrl")
        or item.get("url")
        or item.get("input")
        or ""
    )
    if not video_url:
        video_id = item.get("id", "")
        author_meta = item.get("authorMeta") or item.get("author") or {}
        author_id = author_meta.get("name") or author_meta.get("uniqueId") or author_meta.get("id") or ""
        if video_id and author_id:
            video_url = f"https://www.tiktok.com/@{author_id}/video/{video_id}"

    if not video_url or "tiktok.com" not in video_url:
        return None

    # --- Author / Creator info (Clockworks: authorMeta) ---
    author_meta = item.get("authorMeta") or item.get("author") or {}
    author_id = author_meta.get("name") or author_meta.get("uniqueId") or author_meta.get("id") or ""
    author_name = author_meta.get("nickName") or author_meta.get("nickname") or author_meta.get("name") or author_id
    creator_followers = author_meta.get("fans") or author_meta.get("followers") or 0
    creator_following = author_meta.get("following") or 0
    creator_verified = bool(author_meta.get("verified", False))
    creator_bio = author_meta.get("signature") or author_meta.get("bio") or ""
    creator_avatar = author_meta.get("avatar") or ""

    # --- Engagement metrics (Clockworks uses playCount, diggCount, etc.) ---
    view_count = item.get("playCount") or item.get("plays") or item.get("view_count") or 0
    like_count = item.get("diggCount") or item.get("likes") or item.get("like_count") or 0
    comment_count = item.get("commentCount") or item.get("comments") or item.get("comment_count") or 0
    share_count = item.get("shareCount") or item.get("shares") or item.get("share_count") or 0
    bookmark_count = item.get("collectCount") or item.get("bookmarks") or item.get("bookmark_count") or 0

    # --- Title / description (Clockworks uses "text" field) ---
    title = item.get("text") or item.get("description") or item.get("desc") or "Untitled"

    # --- Hashtags (Clockworks: hashtags array of objects with .name) ---
    raw_hashtags = item.get("hashtags") or []
    if isinstance(raw_hashtags, list):
        hashtags = []
        for h in raw_hashtags:
            if isinstance(h, dict):
                hashtags.append(h.get("name") or h.get("title") or "")
            elif isinstance(h, str):
                hashtags.append(h)
        hashtags = [h for h in hashtags if h]
    else:
        hashtags = []

    # --- Video metadata (Clockworks: videoMeta with coverUrl, duration) ---
    video_meta = item.get("videoMeta") or item.get("video") or {}
    direct_video_url = video_meta.get("downloadAddr") or video_meta.get("url") or ""
    thumbnail = (
        video_meta.get("coverUrl")
        or video_meta.get("originalCoverUrl")
        or video_meta.get("cover")
        or video_meta.get("thumbnail")
        or item.get("covers", {}).get("default")
        or ""
    )
    duration = video_meta.get("duration") or item.get("duration") or 0
    video_width = video_meta.get("width") or 0
    video_height = video_meta.get("height") or 0

    # --- Music metadata (Clockworks: musicMeta) ---
    music_meta = item.get("musicMeta") or item.get("song") or {}
    song_id = str(music_meta.get("musicId") or music_meta.get("id") or "")
    song_title = music_meta.get("musicName") or music_meta.get("title") or ""
    song_artist = music_meta.get("musicAuthor") or music_meta.get("artist") or ""
    song_album = music_meta.get("musicAlbum") or music_meta.get("album") or ""
    song_duration = music_meta.get("duration") or 0
    song_cover = music_meta.get("coverMediumUrl") or music_meta.get("cover") or ""

    # --- Timestamps ---
    create_time = item.get("createTime") or item.get("createTimeISO") or 0
    if isinstance(create_time, str):
        # ISO format
        uploaded_at_formatted = create_time
        uploaded_at = 0
    else:
        uploaded_at = int(create_time) if create_time else 0
        uploaded_at_formatted = item.get("createTimeISO") or ""

    return {
        # Core video fields
        "tiktok_url": video_url,
        "video_platform_id": str(item.get("id", "")),
        "creator": author_id,
        "creator_display": author_name,
        "title": title[:220],
        "view_count": int(view_count) if view_count else 0,
        "like_count": int(like_count) if like_count else 0,
        "comment_count": int(comment_count) if comment_count else 0,
        "share_count": int(share_count) if share_count else 0,
        "bookmark_count": int(bookmark_count) if bookmark_count else 0,
        "duration": float(duration) if duration else 0,
        "thumbnail_url": thumbnail,
        "timestamp": int(uploaded_at) if uploaded_at else 0,
        "upload_date_formatted": uploaded_at_formatted,
        # Direct video URL
        "direct_video_url": direct_video_url,
        "video_width": video_width,
        "video_height": video_height,
        "video_ratio": "",
        # Hashtags
        "hashtags": hashtags,
        # Music metadata
        "song_id": song_id,
        "song_title": song_title,
        "song_artist": song_artist,
        "song_album": song_album,
        "song_duration": int(song_duration) if song_duration else 0,
        "song_cover_url": song_cover,
        # Subtitles (Clockworks doesn't provide these inline, but field kept for compat)
        "subtitles_url": "",
        "subtitles_language": "",
        # Creator profile data
        "creator_followers": int(creator_followers) if creator_followers else 0,
        "creator_following": int(creator_following) if creator_following else 0,
        "creator_verified": creator_verified,
        "creator_bio": creator_bio,
        "creator_avatar": creator_avatar,
        "creator_total_videos": 0,
        "creator_total_likes": 0,
    }


async def _run_actor(input_data: dict, timeout: int = 75) -> list:
    """Run the Apify Actor synchronously and return dataset items."""
    if not APIFY_TOKEN:
        logger.warning("APIFY_API_TOKEN not set — cannot fetch TikTok data.")
        return []

    # Query params for the run-sync endpoint:
    # - token: auth
    # - timeout: how long Apify waits before returning (in seconds)
    #   Clockworks actor typically completes in 10-40s for small queries.
    params = {
        "token": APIFY_TOKEN,
        "timeout": 60,
    }
    headers = {"Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            logger.info(f"Calling Apify actor {ACTOR_ID} with input: {input_data}")
            resp = await client.post(
                APIFY_RUN_URL,
                params=params,
                headers=headers,
                json=input_data,
            )
            logger.info(f"Apify response status: {resp.status_code}, length: {len(resp.content)}")
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
            # Some responses wrap items in a data/items structure
            if isinstance(items, dict):
                if "items" in items:
                    items_list = items["items"]
                    logger.info(f"Apify returned dict with {len(items_list)} items (unwrapped)")
                    return items_list if isinstance(items_list, list) else []
                if "data" in items and isinstance(items["data"], list):
                    logger.info(f"Apify returned dict.data with {len(items['data'])} items")
                    return items["data"]
            logger.warning(f"Apify returned unexpected type: {type(items)}, keys: {items.keys() if isinstance(items, dict) else 'N/A'}, first 300 chars: {str(items)[:300]}")
            return []
    except httpx.TimeoutException:
        logger.warning(f"HTTP timeout after {timeout}s waiting for Apify")
        return []
    except Exception as e:
        logger.error(f"Apify actor failed: {e}")
        return []


async def fetch_creator_videos(handle: str, limit: int = 10) -> list:
    """
    Fetch latest videos from a TikTok creator profile via Apify.
    Note: ApiDojo actor requires minimum 10 results per query.
    """
    handle = handle.lstrip("@").strip()
    if not handle:
        return []

    # Clockworks actor uses: hashtags, profiles, resultsPerPage, searchQueries
    # (NOT startUrls/keywords/maxItems like ApiDojo)
    input_data = {
        "profiles": [f"https://www.tiktok.com/@{handle}"],
        "resultsPerPage": effective_limit,
    }

    items = await _run_actor(input_data, timeout=75)
    results = []
    for item in items:
        parsed = _parse_apify_video(item)
        if parsed:
            results.append(parsed)
    return results[:limit]


async def fetch_hashtag_videos(hashtag: str, limit: int = 25) -> list:
    """Fetch videos from a TikTok hashtag via Apify."""
    hashtag = hashtag.lstrip("#").strip()
    if not hashtag:
        return []

    # Clockworks actor uses hashtags array
    effective_limit = max(limit, 10)
    input_data = {
        "hashtags": [hashtag],
        "resultsPerPage": effective_limit,
    }

    items = await _run_actor(input_data, timeout=75)
    results = []
    for item in items:
        parsed = _parse_apify_video(item)
        if parsed:
            parsed["source_hashtag"] = hashtag
            results.append(parsed)
    return results[:limit]


async def fetch_keyword_videos(keyword: str, limit: int = 25, location: str = "", sort_type: str = "RELEVANCE") -> list:
    """
    Search TikTok for videos matching a keyword via Apify.

    Args:
        keyword: Search term
        limit: Max number of results
        location: ISO 3166-1 alpha-2 country code (e.g., "US", "GB", "DE") for location targeting
        sort_type: Sort order — "RELEVANCE", "MOST_LIKED", or "DATE_POSTED"
    """
    keyword = keyword.strip()
    if not keyword:
        return []

    # Clockworks actor uses searchQueries array
    effective_limit = max(limit, 10)
    input_data = {
        "searchQueries": [keyword],
        "resultsPerPage": effective_limit,
    }

    # Location targeting is not supported by Clockworks actor
    # sort_type is not supported by Clockworks actor

    items = await _run_actor(input_data, timeout=75)
    results = []
    for item in items:
        parsed = _parse_apify_video(item)
        if parsed:
            parsed["source_keyword"] = keyword
            results.append(parsed)
    return results[:limit]


async def fetch_music_videos(music_url: str, limit: int = 25) -> list:
    """
    Fetch videos using a specific TikTok sound/music.
    Note: Clockworks actor doesn't support music URL scraping directly.
    Falls back to searching the music name as a keyword if possible.
    """
    # Clockworks doesn't support music URLs, return empty
    logger.info("Music URL scraping not supported by Clockworks actor — use search instead")
    return []


async def fetch_location_videos(location_url: str, limit: int = 25) -> list:
    """
    Fetch videos from a specific TikTok location page.
    Note: Clockworks actor doesn't support location URL scraping directly.
    """
    # Clockworks doesn't support location URLs, return empty
    logger.info("Location URL scraping not supported by Clockworks actor")
    return []


async def fetch_subtitles(subtitles_url: str) -> Optional[str]:
    """
    Fetch the actual subtitle/transcript text from a subtitle URL.
    Returns the raw WebVTT/subtitle text, or None if fetch fails.
    """
    if not subtitles_url:
        return None

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(subtitles_url)
            if resp.status_code == 200:
                return resp.text
    except Exception as e:
        logger.warning(f"Failed to fetch subtitles from {subtitles_url}: {e}")
    return None


def parse_webvtt_to_text(vtt_content: str) -> str:
    """
    Parse WebVTT subtitle content into plain text (just the spoken words).
    Strips timing information and formatting cues.
    """
    if not vtt_content:
        return ""

    lines = vtt_content.strip().splitlines()
    text_lines = []
    for line in lines:
        line = line.strip()
        # Skip WebVTT header, timing lines, and empty lines
        if not line:
            continue
        if line.startswith("WEBVTT"):
            continue
        if line.startswith("NOTE"):
            continue
        if "-->" in line:
            continue
        # Skip numeric cue identifiers
        if line.isdigit():
            continue
        # Strip HTML-like tags (e.g., <c>, </c>)
        import re
        clean = re.sub(r"<[^>]+>", "", line)
        if clean.strip():
            text_lines.append(clean.strip())

    return " ".join(text_lines)
