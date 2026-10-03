"""
Virality scoring engine.

Ranks videos by engagement velocity, engagement rate, recency, and raw scale.
Fetching (hashtag/keyword discovery) lived here for the Discover feed and left
with it; the Trend Research scan fetches through apify_tiktok directly and
only ranks here.
"""
import logging
import math
from datetime import datetime, timezone

logger = logging.getLogger(__name__)












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
