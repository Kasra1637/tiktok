"""
Apify TikTok Scraper integration.
Uses the Clockworks TikTok Scraper Actor (compute-time billing) to fetch
TikTok profiles, hashtags, and search results.

Capabilities:
- Profile video scraping (latest videos from a creator)
- Hashtag video scraping (trending videos for a hashtag)
- Keyword search (search TikTok by keyword)
- Music metadata extraction (musicMeta: title, artist, album, duration)
- Engagement metrics (playCount, diggCount, shareCount, collectCount)
- Creator profile data (followers, verified status, bio)
- Hashtags as structured array
- Video thumbnails and direct download URLs
- Subtitle/transcript link extraction (subtitleLinks), when available
- Ad / sponsored post detection (isAd / isSponsored)

Requires APIFY_API_TOKEN environment variable.
Docs: https://apify.com/clockworks/tiktok-scraper
"""
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
ACTOR_ID = "clockworks~tiktok-scraper"
APIFY_RUN_URL = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"


def is_configured() -> bool:
    return bool(APIFY_TOKEN)


def _parse_apify_video(item: dict) -> Optional[dict]:
    """
    Convert a Clockworks actor result item to our internal video format.
    Handles the Clockworks output schema (authorMeta, playCount, diggCount,
    videoMeta, musicMeta, etc.) and extracts all available enriched fields.
    """
    # Skip placeholder items the actor returns when it can't find data
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

    # --- Author / Creator info (authorMeta) ---
    author_meta = item.get("authorMeta") or item.get("author") or {}
    author_id = author_meta.get("name") or author_meta.get("uniqueId") or author_meta.get("id") or ""
    author_name = author_meta.get("nickName") or author_meta.get("nickname") or author_meta.get("name") or author_id
    creator_followers = author_meta.get("fans") or author_meta.get("followers") or 0
    creator_following = author_meta.get("following") or 0
    creator_verified = bool(author_meta.get("verified", False))
    creator_bio = author_meta.get("signature") or author_meta.get("bio") or ""
    creator_avatar = author_meta.get("avatar") or ""

    # --- Engagement metrics (playCount, diggCount, shareCount, collectCount) ---
    view_count = item.get("playCount") or item.get("plays") or item.get("view_count") or 0
    like_count = item.get("diggCount") or item.get("likes") or item.get("like_count") or 0
    comment_count = item.get("commentCount") or item.get("comments") or item.get("comment_count") or 0
    share_count = item.get("shareCount") or item.get("shares") or item.get("share_count") or 0
    bookmark_count = item.get("collectCount") or item.get("bookmarks") or item.get("bookmark_count") or 0

    # --- Title / description ("text" field) ---
    title = item.get("text") or item.get("description") or item.get("desc") or "Untitled"

    # --- Hashtags (array of objects with .name) ---
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

    # --- Video metadata (videoMeta: coverUrl, duration, downloadAddr) ---
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

    # --- Music metadata (musicMeta: musicName, musicAuthor, musicId) ---
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
        uploaded_at_formatted = create_time
        uploaded_at = 0
    else:
        uploaded_at = int(create_time) if create_time else 0
        uploaded_at_formatted = item.get("createTimeISO") or ""

    # --- Subtitles / transcript link (subtitleLinks: array of {language, downloadLink, ...}) ---
    subtitles_url = ""
    subtitles_language = ""
    raw_subtitles = (
        item.get("subtitleLinks")
        or item.get("subtitleInfos")
        or item.get("subtitles")
        or []
    )
    if isinstance(raw_subtitles, list) and raw_subtitles:
        # Prefer a non-auto-generated / original-language track if that info is present,
        # otherwise just take the first available track.
        chosen = None
        for sub in raw_subtitles:
            if not isinstance(sub, dict):
                continue
            if sub.get("source") == "original" or sub.get("isOriginal"):
                chosen = sub
                break
        if not chosen:
            chosen = next((s for s in raw_subtitles if isinstance(s, dict)), None)
        if chosen:
            subtitles_url = (
                chosen.get("downloadLink")
                or chosen.get("url")
                or chosen.get("tiktokLink")
                or ""
            )
            subtitles_language = (
                chosen.get("language")
                or chosen.get("languageCode")
                or chosen.get("languageID")
                or ""
            )

    # --- Ad / sponsored post detection ---
    is_ad = bool(
        item.get("isAd")
        or item.get("is_ad")
        or item.get("isSponsored")
        or item.get("is_sponsored")
        or item.get("adAuthorName")
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
        "bookmark_count": int(bookmark_count) if bookmark_count else 0,
        "duration": float(duration) if duration else 0,
        "thumbnail_url": thumbnail,
        "timestamp": int(uploaded_at) if uploaded_at else 0,
        "upload_date_formatted": uploaded_at_formatted,
        "direct_video_url": direct_video_url,
        "video_width": video_width,
        "video_height": video_height,
        "hashtags": hashtags,
        "song_id": song_id,
        "song_title": song_title,
        "song_artist": song_artist,
        "song_album": song_album,
        "song_duration": int(song_duration) if song_duration else 0,
        "song_cover_url": song_cover,
        "subtitles_url": subtitles_url,
        "subtitles_language": subtitles_language,
        "is_ad": is_ad,
        "creator_followers": int(creator_followers) if creator_followers else 0,
        "creator_following": int(creator_following) if creator_following else 0,
        "creator_verified": creator_verified,
        "creator_bio": creator_bio,
        "creator_avatar": creator_avatar,
        "creator_total_videos": 0,
        "creator_total_likes": 0,
    }


async def _run_actor(input_data: dict, timeout: int = 75) -> list:
    """Run the Clockworks Apify Actor synchronously and return dataset items."""
    if not APIFY_TOKEN:
        logger.warning("APIFY_API_TOKEN not set — cannot fetch TikTok data.")
        return []

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
                logger.warning("Apify actor timed out (408) — no results yet")
                return []
            if resp.status_code != 200 and resp.status_code != 201:
                logger.error(f"Apify returned status {resp.status_code}: {resp.text[:500]}")
                return []
            items = resp.json()
            if isinstance(items, list):
                logger.info(f"Apify returned {len(items)} items")
                return items
            if isinstance(items, dict):
                if "items" in items:
                    items_list = items["items"]
                    logger.info(f"Apify returned dict with {len(items_list)} items (unwrapped)")
                    return items_list if isinstance(items_list, list) else []
                if "data" in items and isinstance(items["data"], list):
                    logger.info(f"Apify returned dict.data with {len(items['data'])} items")
                    return items["data"]
            logger.warning(f"Apify returned unexpected format: {str(items)[:300]}")
            return []
    except httpx.TimeoutException:
        logger.warning(f"HTTP timeout after {timeout}s waiting for Apify")
        return []
    except Exception as e:
        logger.error(f"Apify actor failed: {e}")
        return []


async def fetch_creator_videos(handle: str, limit: int = 10) -> list:
    """Fetch latest videos from a TikTok creator profile."""
    handle = handle.lstrip("@").strip()
    if not handle:
        return []

    effective_limit = max(limit, 10)
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
    """Fetch videos from a TikTok hashtag."""
    hashtag = hashtag.lstrip("#").strip()
    if not hashtag:
        return []

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


async def fetch_keyword_videos(keyword: str, limit: int = 25) -> list:
    """Search TikTok for videos matching a keyword."""
    keyword = keyword.strip()
    if not keyword:
        return []

    effective_limit = max(limit, 10)
    input_data = {
        "searchQueries": [keyword],
        "resultsPerPage": effective_limit,
    }

    items = await _run_actor(input_data, timeout=75)
    results = []
    for item in items:
        parsed = _parse_apify_video(item)
        if parsed:
            parsed["source_keyword"] = keyword
            results.append(parsed)
    return results[:limit]


async def fetch_subtitles(subtitles_url: str) -> Optional[str]:
    """
    Fetch subtitle/transcript text from a subtitle URL.
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

    import re
    lines = vtt_content.strip().splitlines()
    text_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("WEBVTT"):
            continue
        if line.startswith("NOTE"):
            continue
        if "-->" in line:
            continue
        if line.isdigit():
            continue
        clean = re.sub(r"<[^>]+>", "", line)
        if clean.strip():
            text_lines.append(clean.strip())

    return " ".join(text_lines)
