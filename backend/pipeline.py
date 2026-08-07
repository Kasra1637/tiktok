"""
Core media pipeline: TikTok video metadata/download via yt-dlp and
first-2-3-second frame extraction via ffmpeg. All subprocess calls are async
so they never block the FastAPI event loop.
"""
import asyncio
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

STORAGE_DIR = Path(__file__).parent / "storage"
VIDEOS_DIR = STORAGE_DIR / "videos"
FRAMES_DIR = STORAGE_DIR / "frames"
UPLOADS_DIR = STORAGE_DIR / "uploads"
GENERATED_DIR = STORAGE_DIR / "generated"
# Saved hook templates keep their own copy of the source clip (V2V motion
# reference) and key frame so a template stays reusable even after the
# original download or frame cache is cleaned up.
TEMPLATES_DIR = STORAGE_DIR / "templates"
for _d in [VIDEOS_DIR, FRAMES_DIR, UPLOADS_DIR, GENERATED_DIR, TEMPLATES_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

# Use `python -m yt_dlp` (same interpreter/venv as this process) instead of relying
# on the `yt-dlp` console script being present on PATH for the supervisor process.
YTDLP_CMD = [sys.executable, "-m", "yt_dlp"]


def url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().encode()).hexdigest()[:16]


async def run_cmd(cmd: list, timeout: int = 60):
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
        raise RuntimeError(f"Command timed out after {timeout}s: {' '.join(cmd[:2])}...")
    return proc.returncode, stdout.decode(errors="ignore"), stderr.decode(errors="ignore")


def _pick_thumbnail(data: dict):
    thumbs = data.get("thumbnails") or []
    if thumbs:
        for t in thumbs:
            if t.get("id") == "cover":
                return t.get("url")
        return thumbs[0].get("url")
    return data.get("thumbnail")


async def fetch_video_metadata(tiktok_url: str) -> dict:
    """Fetch real metadata for a single TikTok video without downloading it."""
    cmd = YTDLP_CMD + ["-j", "--no-warnings", tiktok_url]
    rc, out, err = await run_cmd(cmd, timeout=30)
    if rc != 0 or not out.strip():
        raise RuntimeError(f"Failed to fetch video metadata: {err.strip()[-400:] or 'unknown error'}")
    data = json.loads(out.strip().splitlines()[0])
    return {
        "video_platform_id": data.get("id"),
        "creator": data.get("uploader"),
        "creator_display": data.get("channel") or data.get("uploader"),
        "title": (data.get("title") or data.get("description") or "Untitled video")[:220],
        "description": (data.get("description") or "")[:500],
        "view_count": data.get("view_count") or 0,
        "like_count": data.get("like_count") or 0,
        "comment_count": data.get("comment_count") or 0,
        "share_count": data.get("repost_count") or 0,
        "bookmark_count": 0,
        "duration": data.get("duration") or 0,
        "thumbnail_url": _pick_thumbnail(data),
        "timestamp": data.get("timestamp") or 0,
        # Defaults for fields only available via Apify
        "direct_video_url": "",
        "hashtags": [],
        "song_id": "",
        "song_title": "",
        "song_artist": "",
        "song_album": "",
        "song_duration": 0,
        "song_cover_url": "",
        "subtitles_url": "",
        "subtitles_language": "",
        "is_ad": False,
        "creator_followers": 0,
        "creator_following": 0,
        "creator_verified": False,
        "creator_bio": "",
        "creator_avatar": "",
        "creator_total_videos": 0,
        "creator_total_likes": 0,
    }


async def fetch_creator_videos(handle: str, limit: int = 10) -> list:
    """Fetch the latest `limit` videos for a creator handle. Uses Apify if configured, else yt-dlp."""
    import apify_tiktok
    if apify_tiktok.is_configured():
        return await apify_tiktok.fetch_creator_videos(handle, limit)

    # Fallback: yt-dlp (may be unreliable)
    cmd = YTDLP_CMD + [
        "--flat-playlist", "--playlist-end", str(limit),
        "-j", "--no-warnings", f"https://www.tiktok.com/@{handle}",
    ]
    results = []
    try:
        rc, out, err = await run_cmd(cmd, timeout=25)
    except RuntimeError as e:
        logger.warning(f"Timed out fetching creator {handle}: {e}")
        return results
    if rc != 0 or not out.strip():
        logger.warning(f"Failed fetching creator {handle}: {err.strip()[-300:]}")
        return results
    for line in out.strip().splitlines():
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        results.append({
            "tiktok_url": data.get("webpage_url") or data.get("url"),
            "video_platform_id": data.get("id"),
            "creator": data.get("uploader") or handle,
            "creator_display": data.get("channel") or data.get("uploader") or handle,
            "title": (data.get("title") or data.get("description") or "Untitled video")[:220],
            "view_count": data.get("view_count") or 0,
            "like_count": data.get("like_count") or 0,
            "comment_count": data.get("comment_count") or 0,
            "share_count": data.get("repost_count") or 0,
            "bookmark_count": 0,
            "duration": data.get("duration") or 0,
            "thumbnail_url": _pick_thumbnail(data),
            "timestamp": data.get("timestamp") or 0,
            # These fields are only available via Apify; set defaults for yt-dlp fallback
            "direct_video_url": "",
            "hashtags": [],
            "song_id": "",
            "song_title": "",
            "song_artist": "",
            "song_album": "",
            "song_duration": 0,
            "song_cover_url": "",
            "subtitles_url": "",
            "subtitles_language": "",
            "is_ad": False,
            "creator_followers": 0,
            "creator_following": 0,
            "creator_verified": False,
            "creator_bio": "",
            "creator_avatar": "",
            "creator_total_videos": 0,
            "creator_total_likes": 0,
        })
    return results


async def download_video(tiktok_url: str, direct_video_url: str = "") -> Path:
    """
    Download a TikTok video. Tries direct_video_url first (from Apify scraper),
    falls back to yt-dlp if direct URL is unavailable or fails.
    """
    vhash = url_hash(tiktok_url)
    out_path = VIDEOS_DIR / f"{vhash}.mp4"
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    # Try direct video URL first (faster, no yt-dlp dependency)
    if direct_video_url:
        try:
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                resp = await client.get(direct_video_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.tiktok.com/",
                })
                if resp.status_code == 200 and len(resp.content) > 1000:
                    with open(out_path, "wb") as f:
                        f.write(resp.content)
                    logger.info(f"Downloaded video via direct URL: {out_path} ({out_path.stat().st_size} bytes)")
                    return out_path
                else:
                    logger.warning(f"Direct video URL returned status {resp.status_code} or too small, falling back to yt-dlp")
        except Exception as e:
            logger.warning(f"Direct video download failed ({e}), falling back to yt-dlp")

    # Fallback: yt-dlp
    cmd = YTDLP_CMD + ["-f", "b[ext=mp4]/best", "--no-warnings", "-o", str(out_path), tiktok_url]
    rc, out, err = await run_cmd(cmd, timeout=100)
    if rc != 0 or not out_path.exists():
        raise RuntimeError(f"Video download failed: {err.strip()[-400:] or 'unknown error'}")
    return out_path


async def extract_hook_frames(video_path: Path, num_frames: int = 8, duration: float = 3.0) -> list:
    vhash = video_path.stem
    frame_dir = FRAMES_DIR / vhash
    frame_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(frame_dir.glob("frame_*.jpg"))
    if len(existing) >= num_frames:
        return existing[:num_frames]
    fps = num_frames / duration
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-t", str(duration),
        "-vf", f"fps={fps},scale=480:-1",
        "-q:v", "3",
        str(frame_dir / "frame_%03d.jpg"),
    ]
    rc, out, err = await run_cmd(cmd, timeout=60)
    frames = sorted(frame_dir.glob("frame_*.jpg"))
    if rc != 0 or not frames:
        raise RuntimeError(f"Frame extraction failed: {err.strip()[-400:] or 'unknown error'}")
    return frames


async def extract_last_frame(video_path: Path, out_path: Path) -> Optional[Path]:
    """
    Extract the final frame of a video as an image.

    Used to bridge a generated hook clip into its continuation: feeding the
    hook's LAST frame as the first frame of the next generation makes the two
    clips read as one continuous take, instead of the continuation restarting
    from the same opening pose the hook already used.

    Returns None (rather than raising) when extraction isn't possible, so
    callers can fall back to the original still image.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # -sseof seeks relative to end-of-file; -update 1 keeps overwriting the same
    # output file while decoding, so the frame left on disk is the final one.
    cmd = [
        "ffmpeg", "-y",
        "-sseof", "-1",
        "-i", str(video_path),
        "-update", "1",
        "-q:v", "2",
        str(out_path),
    ]
    try:
        rc, _out, err = await run_cmd(cmd, timeout=45)
    except RuntimeError as e:
        logger.warning(f"Last-frame extraction timed out for {video_path.name}: {e}")
        return None
    if rc != 0 or not out_path.exists() or out_path.stat().st_size == 0:
        logger.warning(
            f"Last-frame extraction failed for {video_path.name}: "
            f"{err.strip()[-300:] or 'unknown error'}"
        )
        return None
    return out_path
