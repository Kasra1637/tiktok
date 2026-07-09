"""
Viral/trending video detection engine.

Provides hashtag-based and keyword-based TikTok video discovery via yt-dlp,
plus a virality scoring algorithm that ranks videos by engagement velocity,
engagement rate, recency, and raw scale.
"""
import asyncio
import json
import logging
import math
import sys
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Same pattern as pipeline.py - use the current interpreter's yt_dlp module.
YTDLP_CMD = [sys.executable, "-m", "yt_dlp"]


async def run_cmd(cmd: list, timeout: int = 60):
    """Run a subprocess command asynchronously, returning (returncode, stdout, stderr)."""
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        raise RuntimeError(f"Command timed out after {timeout}s: {' '.join(cmd[:3])}...")
    return proc.returncode, stdout.decode(errors="ignore"), stderr.decode(errors="ignore")


def _pick_thumbnail(data: dict):
    """Extract best thumbnail URL from yt-dlp metadata."""
    thumbs = data.get("thumbnails") or []
    if thumbs:
        for t in thumbs:
            if t.get("id") == "cover":
                return t.get("url")
        return thumbs[0].get("url")
    return data.get("thumbnail")


def _parse_video_entry(data: dict) -> dict:
    """Normalize a single yt-dlp JSON entry into our standard video metadata dict."""
    upload_date_str = data.get("upload_date") or ""
    timestamp = data.get("timestamp")

    return {
        "video_platform_id": data.get("id"),
        "tiktok_url": data.get("webpage_url") or data.get("url") or "",
        "creator": data.get("uploader") or data.get("channel") or "",
        "creator_display": data.get("channel") or data.get("uploader") or "",
        "title": (data.get("title") or data.get("description") or "Untitled video")[:220],
        "description": (data.get("description") or "")[:500],
        "view_count": data.get("view_count") or 0,
        "like_count": data.get("like_count") or 0,
        "comment_count": data.get("comment_count") or 0,
        "share_count": data.get("repost_count") or data.get("share_count") or 0,
        "duration": data.get("duration") or 0,
        "upload_date": upload_date_str,
        "timestamp": timestamp,
        "thumbnail_url": _pick_thumbnail(data),
    }


async def fetch_hashtag_videos(hashtag: str, limit: int = 25) -> list:
    """
    Fetch videos from a TikTok hashtag. Uses Apify if configured, else yt-dlp.
    """
    import apify_tiktok
    if apify_tiktok.is_configured():
        videos = await apify_tiktok.fetch_hashtag_videos(hashtag, limit)
        # Add virality score to each video
        for v in videos:
            v["virality_score"] = compute_virality_score(v)
        return videos

    # Fallback: yt-dlp (may be unreliable)
    # Strip leading '#' if present
    hashtag = hashtag.lstrip("#").strip()
    if not hashtag:
        return []

    url = f"https://www.tiktok.com/tag/{hashtag}"
    cmd = YTDLP_CMD + [
        "--flat-playlist",
        "--playlist-end", str(limit),
        "-j",
        "--no-warnings",
        url,
    ]

    results = []
    try:
        rc, out, err = await run_cmd(cmd, timeout=45)
    except RuntimeError as e:
        logger.warning(f"Timed out fetching hashtag #{hashtag}: {e}")
        return results

    if rc != 0 or not out.strip():
        logger.warning(f"Failed fetching hashtag #{hashtag}: {err.strip()[-300:]}")
        return results

    for line in out.strip().splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        entry = _parse_video_entry(data)
        entry["source_hashtag"] = hashtag
        results.append(entry)

    return results


async def fetch_keyword_videos(keyword: str, limit: int = 25) -> list:
    """
    Search TikTok for videos matching a keyword. Uses Apify if configured, else yt-dlp.
    """
    import apify_tiktok
    if apify_tiktok.is_configured():
        videos = await apify_tiktok.fetch_keyword_videos(keyword, limit)
        for v in videos:
            v["virality_score"] = compute_virality_score(v)
        return videos

    # Fallback: yt-dlp (may be unreliable)
    keyword = keyword.strip()
    if not keyword:
        return []

    # yt-dlp supports TikTok search via URL pattern
    search_url = f"https://www.tiktok.com/search?q={keyword}"
    cmd = YTDLP_CMD + [
        "--flat-playlist",
        "--playlist-end", str(limit),
        "-j",
        "--no-warnings",
        search_url,
    ]

    results = []
    try:
        rc, out, err = await run_cmd(cmd, timeout=45)
    except RuntimeError as e:
        logger.warning(f"Timed out searching keyword '{keyword}': {e}")
        return results

    if rc != 0 or not out.strip():
        logger.warning(f"Failed searching keyword '{keyword}': {err.strip()[-300:]}")
        return results

    for line in out.strip().splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        entry = _parse_video_entry(data)
        entry["source_keyword"] = keyword
        results.append(entry)

    return results


def compute_virality_score(video_meta: dict) -> float:
    """
    Calculate a 0-100 virality score for a video based on:
    - engagement_rate (25%): (likes + comments + shares + bookmarks) / views
    - velocity (35%): views / age_in_hours
    - recency_boost (15%): exponential decay favoring videos < 48 hours old
    - raw_scale (10%): log-scaled view count
    - save_intent (15%): bookmarks-to-views ratio (high bookmarks = purchase/save intent)

    Returns a float between 0 and 100.
    """
    views = max(video_meta.get("view_count") or 0, 0)
    likes = max(video_meta.get("like_count") or 0, 0)
    comments = max(video_meta.get("comment_count") or 0, 0)
    shares = max(video_meta.get("share_count") or 0, 0)
    bookmarks = max(video_meta.get("bookmark_count") or 0, 0)

    # -- Calculate age in hours --
    age_hours = _compute_age_hours(video_meta)

    # -- Engagement Rate Component (25%) --
    # Now includes bookmarks as an engagement signal
    if views > 0:
        engagement_rate = (likes + comments + shares + bookmarks) / views
    else:
        engagement_rate = 0.0
    # Typical viral TikTok: 5-15% engagement. Cap at ~25% for scoring.
    # Normalize: 0.10 engagement = perfect score
    engagement_score = min(engagement_rate / 0.10, 1.0) * 100

    # -- Velocity Component (35%) --
    # Views per hour. A viral video might get 100k+ views/hour.
    if age_hours > 0:
        velocity = views / age_hours
    else:
        # Very new video (< 1 hour), give it benefit of the doubt
        velocity = views  # treat as 1-hour velocity

    # Log-scale velocity: 1000 views/hr = decent, 100000 views/hr = amazing
    if velocity > 0:
        velocity_score = min(math.log10(velocity + 1) / math.log10(100000), 1.0) * 100
    else:
        velocity_score = 0.0

    # -- Recency Boost (15%) --
    # Exponential decay: full score at 0 hours, half-life of 24 hours
    # After 48 hours, the boost is minimal.
    half_life = 24.0
    recency_score = math.exp(-0.693 * age_hours / half_life) * 100

    # -- Raw Scale Component (10%) --
    # Log-scaled view count. 1M views = high score, 10k = moderate.
    if views > 0:
        raw_scale_score = min(math.log10(views) / 7.0, 1.0) * 100  # 10M = 7 on log scale
    else:
        raw_scale_score = 0.0

    # -- Save Intent / Bookmarks Component (15%) --
    # Bookmarks indicate "I want to come back to this" — strong purchase/conversion intent.
    # A bookmark-to-view ratio of 0.05 (5%) is exceptional on TikTok.
    if views > 0 and bookmarks > 0:
        bookmark_ratio = bookmarks / views
        save_intent_score = min(bookmark_ratio / 0.05, 1.0) * 100
    else:
        save_intent_score = 0.0

    # -- Weighted sum --
    final_score = (
        engagement_score * 0.25
        + velocity_score * 0.35
        + recency_score * 0.15
        + raw_scale_score * 0.10
        + save_intent_score * 0.15
    )

    # Clamp to 0-100
    return round(max(0.0, min(100.0, final_score)), 1)


def _compute_age_hours(video_meta: dict) -> float:
    """Determine the age of a video in hours from its metadata."""
    now = datetime.now(timezone.utc)

    # Try timestamp field first (Unix epoch)
    ts = video_meta.get("timestamp")
    if ts and isinstance(ts, (int, float)) and ts > 0:
        upload_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        age = (now - upload_dt).total_seconds() / 3600.0
        return max(age, 0.1)

    # Try upload_date string (YYYYMMDD format from yt-dlp)
    upload_date_str = video_meta.get("upload_date", "")
    if upload_date_str and len(upload_date_str) == 8:
        try:
            upload_dt = datetime.strptime(upload_date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
            age = (now - upload_dt).total_seconds() / 3600.0
            return max(age, 0.1)
        except ValueError:
            pass

    # Default: assume 48 hours old (moderate recency)
    return 48.0


def rank_videos(videos_list: list) -> list:
    """
    Score each video with compute_virality_score and sort descending.
    Adds 'virality_score' field to each video dict.
    Returns a new sorted list (does not mutate the input).
    """
    scored = []
    for video in videos_list:
        video_copy = dict(video)
        video_copy["virality_score"] = compute_virality_score(video_copy)
        scored.append(video_copy)

    scored.sort(key=lambda v: v["virality_score"], reverse=True)
    return scored
