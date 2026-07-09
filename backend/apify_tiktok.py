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
ACTOR_ID = "apidojo~tiktok-scraper"
# Use the synchronous endpoint with a timeout parameter so Apify returns within Render's limits
APIFY_RUN_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"


def is_configured() -> bool:
    return bool(APIFY_TOKEN)


def _parse_apify_video(item: dict) -> Optional[dict]:
    """
    Convert an ApiDojo result item to our internal video format.
    Extracts all available fields including music, subtitles, bookmarks,
    hashtags array, channel/profile data, and direct video URL.
    """
    # Skip non-video items
    if not item.get("id") and not item.get("title") and not item.get("postPage"):
        return None

    # --- Video URL ---
    video_url = (
        item.get("postPage")
        or item.get("webVideoUrl")
        or item.get("url")
        or ""
    )
    if not video_url:
        video_id = item.get("id", "")
        channel = item.get("channel") or {}
        author_username = channel.get("username", "")
        if video_id and author_username:
            video_url = f"https://www.tiktok.com/@{author_username}/video/{video_id}"

    if not video_url or "tiktok.com" not in video_url:
        return None

    # --- Channel / Creator info ---
    channel = item.get("channel") or {}
    author_id = channel.get("username") or channel.get("name") or ""
    author_name = channel.get("name") or channel.get("username") or author_id
    creator_followers = channel.get("followers") or 0
    creator_following = channel.get("following") or 0
    creator_verified = bool(channel.get("verified", False))
    creator_bio = channel.get("bio") or ""
    creator_avatar = channel.get("avatar") or ""
    creator_total_videos = channel.get("videos") or 0
    creator_total_likes = channel.get("likes") or 0

    # --- Engagement metrics ---
    view_count = item.get("views") or 0
    like_count = item.get("likes") or 0
    comment_count = item.get("comments") or 0
    share_count = item.get("shares") or 0
    bookmark_count = item.get("bookmarks") or 0

    # --- Title / description ---
    title = item.get("title") or item.get("description") or "Untitled"

    # --- Hashtags as structured array ---
    hashtags = item.get("hashtags") or []
    if isinstance(hashtags, list):
        hashtags = [str(h) for h in hashtags]
    else:
        hashtags = []

    # --- Video metadata (direct URL, cover, dimensions, duration) ---
    video_meta = item.get("video") or {}
    direct_video_url = video_meta.get("url") or ""
    thumbnail = (
        video_meta.get("cover")
        or video_meta.get("thumbnail")
        or ""
    )
    video_width = video_meta.get("width") or 0
    video_height = video_meta.get("height") or 0
    video_ratio = video_meta.get("ratio") or ""
    duration = video_meta.get("duration") or item.get("duration") or 0

    # --- Song / Music metadata ---
    song_data = item.get("song") or {}
    song_id = song_data.get("id") or ""
    song_title = song_data.get("title") or ""
    song_artist = song_data.get("artist") or ""
    song_album = song_data.get("album") or ""
    song_duration = song_data.get("duration") or 0
    song_cover = song_data.get("cover") or ""

    # --- Subtitles / Transcript ---
    subtitle_info = item.get("subtitleInformation") or []
    subtitles_url = ""
    subtitles_language = ""
    if isinstance(subtitle_info, list) and subtitle_info:
        # Pick the first available subtitle (prefer original captions)
        for sub in subtitle_info:
            if sub.get("is_original_caption"):
                subtitles_url = sub.get("url") or ""
                subtitles_language = sub.get("language_code") or sub.get("lang") or ""
                break
        if not subtitles_url and subtitle_info:
            subtitles_url = subtitle_info[0].get("url") or ""
            subtitles_language = subtitle_info[0].get("language_code") or subtitle_info[0].get("lang") or ""

    # --- Timestamps ---
    uploaded_at = item.get("uploadedAt") or 0  # Unix timestamp
    uploaded_at_formatted = item.get("uploadedAtFormatted") or ""

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
        # Direct video URL for download fallback
        "direct_video_url": direct_video_url,
        "video_width": video_width,
        "video_height": video_height,
        "video_ratio": video_ratio,
        # Hashtags as structured array
        "hashtags": hashtags,
        # Song / Music metadata
        "song_id": str(song_id) if song_id else "",
        "song_title": song_title,
        "song_artist": song_artist,
        "song_album": song_album,
        "song_duration": int(song_duration) if song_duration else 0,
        "song_cover_url": song_cover,
        # Subtitles / Transcript
        "subtitles_url": subtitles_url,
        "subtitles_language": subtitles_language,
        # Creator / Channel profile data
        "creator_followers": int(creator_followers) if creator_followers else 0,
        "creator_following": int(creator_following) if creator_following else 0,
        "creator_verified": creator_verified,
        "creator_bio": creator_bio,
        "creator_avatar": creator_avatar,
        "creator_total_videos": int(creator_total_videos) if creator_total_videos else 0,
        "creator_total_likes": int(creator_total_likes) if creator_total_likes else 0,
    }


async def _run_actor(input_data: dict, timeout: int = 45) -> list:
    """Run the Apify Actor synchronously and return dataset items."""
    if not APIFY_TOKEN:
        logger.warning("APIFY_API_TOKEN not set — cannot fetch TikTok data.")
        return []

    # Query params for the run-sync endpoint:
    # - token: auth
    # - timeout: how long Apify waits before returning (in seconds)
    #   Keep this SHORT (30s) — the actor is fast (460 posts/sec) so 25 items
    #   should complete in seconds, but actor startup adds overhead.
    # - clean: skip empty items
    params = {
        "token": APIFY_TOKEN,
        "timeout": 30,
        "clean": "true",
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

    # ApiDojo uses startUrls with profile URLs
    effective_limit = max(limit, 10)  # Enforce minimum 10 per ApiDojo requirements
    input_data = {
        "startUrls": [f"https://www.tiktok.com/@{handle}"],
        "maxItems": effective_limit,
    }

    items = await _run_actor(input_data, timeout=45)
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

    # ApiDojo uses startUrls with hashtag URLs
    effective_limit = max(limit, 10)  # Enforce minimum 10
    input_data = {
        "startUrls": [f"https://www.tiktok.com/tag/{hashtag}"],
        "maxItems": effective_limit,
    }

    items = await _run_actor(input_data, timeout=45)
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

    # ApiDojo uses keywords array for search
    effective_limit = max(limit, 10)  # Enforce minimum 10
    input_data = {
        "keywords": [keyword],
        "maxItems": effective_limit,
    }

    # Add location targeting if specified
    if location and location.strip():
        input_data["location"] = location.strip().upper()

    # Add sort type if not default
    if sort_type and sort_type.strip().upper() in ("RELEVANCE", "MOST_LIKED", "DATE_POSTED"):
        input_data["sortType"] = sort_type.strip().upper()

    items = await _run_actor(input_data, timeout=45)
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

    Args:
        music_url: Full TikTok music page URL (e.g., https://www.tiktok.com/music/...)
    """
    music_url = music_url.strip()
    if not music_url or "tiktok.com" not in music_url:
        return []

    effective_limit = max(limit, 10)
    input_data = {
        "startUrls": [music_url],
        "maxItems": effective_limit,
    }

    items = await _run_actor(input_data, timeout=45)
    results = []
    for item in items:
        parsed = _parse_apify_video(item)
        if parsed:
            parsed["source_music_url"] = music_url
            results.append(parsed)
    return results[:limit]


async def fetch_location_videos(location_url: str, limit: int = 25) -> list:
    """
    Fetch videos from a specific TikTok location page.

    Args:
        location_url: Full TikTok location page URL
    """
    location_url = location_url.strip()
    if not location_url or "tiktok.com" not in location_url:
        return []

    effective_limit = max(limit, 10)
    input_data = {
        "startUrls": [location_url],
        "maxItems": effective_limit,
    }

    items = await _run_actor(input_data, timeout=45)
    results = []
    for item in items:
        parsed = _parse_apify_video(item)
        if parsed:
            parsed["source_location_url"] = location_url
            results.append(parsed)
    return results[:limit]


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
