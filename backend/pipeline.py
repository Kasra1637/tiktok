"""
Core media pipeline: TikTok video metadata/download via yt-dlp and
first-2-3-second frame extraction via ffmpeg. All subprocess calls are async
so they never block the FastAPI event loop.

MEMORY OFFLOADING (Modal): downloading a video + decoding frames is the most
memory-hungry part of this app and can exceed Render free tier's 512MB RAM
budget, causing OOM restarts. When MODAL_FRAME_EXTRACTOR_URL is set, that work
is delegated to a Modal serverless function (see backend/modal_worker.py)
which runs with its own dedicated RAM — this process only writes the bytes it
gets back to disk. When unset, everything runs locally exactly as before
(this is the default for local development).
"""
import asyncio
import base64
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

MODAL_FRAME_EXTRACTOR_URL = os.environ.get("MODAL_FRAME_EXTRACTOR_URL", "").strip()
MODAL_SHARED_SECRET = os.environ.get("MODAL_SHARED_SECRET", "").strip()


class ModalFrameDownloadError(RuntimeError):
    """The Modal worker could not obtain the TikTok source video."""


STORAGE_DIR = Path(__file__).parent / "storage"
VIDEOS_DIR = STORAGE_DIR / "videos"
FRAMES_DIR = STORAGE_DIR / "frames"
UPLOADS_DIR = STORAGE_DIR / "uploads"
GENERATED_DIR = STORAGE_DIR / "generated"
# Saved hook templates keep their own copy of the source clip (V2V motion
# reference) and key frame so a template stays reusable even after the
# original download or frame cache is cleaned up.
TEMPLATES_DIR = STORAGE_DIR / "templates"
# App-scoped library assets (screenshots, logos, screen recordings). Files
# live under a per-App-Profile subfolder so one app's media can never be
# resolved through another app's project.
ASSETS_DIR = STORAGE_DIR / "assets"
for _d in [VIDEOS_DIR, FRAMES_DIR, UPLOADS_DIR, GENERATED_DIR, TEMPLATES_DIR, ASSETS_DIR]:
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


async def download_and_extract_via_modal(
    tiktok_url: str, direct_video_url: str = "", num_frames: int = 8, duration: float = 3.0
) -> tuple:
    """
    Delegate video download + frame extraction to the Modal worker so the
    memory-heavy work never runs on this (RAM-constrained) process.

    Returns (video_path, frame_paths) written to the normal local
    directories, so every caller downstream works unmodified.
    """
    vhash = url_hash(tiktok_url)
    video_path = VIDEOS_DIR / f"{vhash}.mp4"
    frame_dir = FRAMES_DIR / vhash
    frame_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=170) as client:
        resp = await client.post(
            MODAL_FRAME_EXTRACTOR_URL,
            json={
                "tiktok_url": tiktok_url,
                "direct_video_url": direct_video_url,
                "num_frames": num_frames,
                "duration": duration,
                "secret": MODAL_SHARED_SECRET,
            },
        )
        if resp.status_code >= 400:
            message = f"Modal frame extraction failed (HTTP {resp.status_code}): {resp.text[:400]}"
            # The worker returns this specific 502 only after both its direct
            # CDN request and TikTok yt-dlp request fail. Other 502s can be
            # gateway/provider failures and must remain terminal.
            if resp.status_code == 502 and "Video download failed" in resp.text:
                raise ModalFrameDownloadError(message)
            raise RuntimeError(message)
        data = resp.json()

    video_bytes = base64.b64decode(data["video_b64"])
    video_path.write_bytes(video_bytes)

    frame_paths = []
    for frame in data["frames"]:
        fp = frame_dir / frame["filename"]
        fp.write_bytes(base64.b64decode(frame["data_b64"]))
        frame_paths.append(fp)

    if not frame_paths:
        raise RuntimeError("Modal returned no frames.")
    return video_path, sorted(frame_paths)


async def download_video(tiktok_url: str, direct_video_url: str = "") -> Path:
    """
    Download a TikTok video. Tries direct_video_url first (from Apify scraper),
    falls back to yt-dlp if direct URL is unavailable or fails.
    """
    vhash = url_hash(tiktok_url)
    out_path = VIDEOS_DIR / f"{vhash}.mp4"
    if out_path.exists() and out_path.stat().st_size > 0:
        return out_path

    # Try direct video URL first (faster, no yt-dlp dependency).
    # Streamed to disk in chunks — `resp.content` would buffer the entire
    # video in RAM at once, which is a meaningful chunk of a 512MB container's
    # budget when several requests overlap.
    if direct_video_url:
        try:
            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                async with client.stream("GET", direct_video_url, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://www.tiktok.com/",
                }) as resp:
                    if resp.status_code == 200:
                        total = 0
                        with open(out_path, "wb") as f:
                            async for chunk in resp.aiter_bytes(chunk_size=262144):
                                f.write(chunk)
                                total += len(chunk)
                        if total > 1000:
                            logger.info(f"Downloaded video via direct URL: {out_path} ({total} bytes)")
                            return out_path
                        out_path.unlink(missing_ok=True)
                        logger.warning("Direct video URL returned too little data, falling back to yt-dlp")
                    else:
                        logger.warning(f"Direct video URL returned status {resp.status_code}, falling back to yt-dlp")
        except Exception as e:
            out_path.unlink(missing_ok=True)
            logger.warning(f"Direct video download failed ({e}), falling back to yt-dlp")

    # Fallback: yt-dlp
    cmd = YTDLP_CMD + ["-f", "b[ext=mp4]/best", "--no-warnings", "-o", str(out_path), tiktok_url]
    rc, out, err = await run_cmd(cmd, timeout=100)
    if rc != 0 or not out_path.exists():
        raise RuntimeError(f"Video download failed: {err.strip()[-400:] or 'unknown error'}")
    return out_path


def _valid_frame_files(paths: list) -> list:
    """
    Filter out empty/corrupted frame files. ffmpeg can be killed mid-extraction
    under memory pressure (common on low-RAM hosts), leaving behind 0-byte or
    truncated .jpg files. Reusing those silently produces blank filmstrip
    thumbnails forever, since the cache-hit check only counted file names.
    """
    valid = []
    for p in paths:
        try:
            if p.stat().st_size > 1024:  # a real JPEG frame is always >1KB
                valid.append(p)
        except OSError:
            continue
    return valid


async def extract_hook_frames(video_path: Path, num_frames: int = 8, duration: float = 3.0) -> list:
    vhash = video_path.stem
    frame_dir = FRAMES_DIR / vhash
    frame_dir.mkdir(parents=True, exist_ok=True)
    existing = _valid_frame_files(sorted(frame_dir.glob("frame_*.jpg")))
    if len(existing) >= num_frames:
        return existing[:num_frames]

    # Clear out any stale/corrupted partial extraction before retrying —
    # otherwise ffmpeg's "-y" only overwrites files it regenerates, and any
    # leftover bad file beyond the new count would stick around.
    for stale in frame_dir.glob("frame_*.jpg"):
        stale.unlink(missing_ok=True)

    fps = num_frames / duration
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-t", str(duration),
        # Downscale before frame extraction and cap threads so ffmpeg doesn't
        # spike memory on low-RAM hosts (e.g. Render's 512MB free tier) —
        # a runaway/OOM-killed ffmpeg process is what produced empty frame
        # files in the first place.
        "-threads", "1",
        "-vf", f"fps={fps},scale=480:-1",
        "-q:v", "3",
        str(frame_dir / "frame_%03d.jpg"),
    ]
    rc, out, err = await run_cmd(cmd, timeout=60)
    frames = _valid_frame_files(sorted(frame_dir.glob("frame_*.jpg")))
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


async def trim_video_to_hook(video_path: Path, duration: float = 3.0) -> Optional[Path]:
    """
    Extract the first `duration` seconds of a video as a standalone clip.

    Used for V2V motion transfer: sending only the hook portion (first 3s)
    gives the video model a clean 1:1 timing reference that matches the
    generated video's length, rather than forcing the model to guess which
    segment of a longer clip to replicate.

    The trimmed clip is cached at storage/videos/{stem}_hook{duration}s.mp4
    so repeated generations from the same source video don't re-encode.

    Returns None (rather than raising) when trimming isn't possible, so the
    caller can fall back to the full video or skip the reference entirely.
    """
    if not video_path or not video_path.exists():
        return None

    # Cache the trimmed clip alongside the original
    cache_name = f"{video_path.stem}_hook{int(duration)}s.mp4"
    trimmed_path = video_path.parent / cache_name

    # Reuse cached trim if it already exists and is non-empty
    if trimmed_path.exists() and trimmed_path.stat().st_size > 0:
        return trimmed_path

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-t", str(duration),
        "-c:v", "copy",    # No re-encoding — fast, lossless copy
        "-c:a", "copy",
        "-threads", "1",
        str(trimmed_path),
    ]
    try:
        rc, _out, err = await run_cmd(cmd, timeout=30)
    except RuntimeError as e:
        logger.warning(f"Hook trim timed out for {video_path.name}: {e}")
        return None
    except (FileNotFoundError, OSError) as e:
        logger.warning(f"Hook trim unavailable (ffmpeg missing?) for {video_path.name}: {e}")
        return None

    if rc != 0 or not trimmed_path.exists() or trimmed_path.stat().st_size == 0:
        logger.warning(
            f"Hook trim failed for {video_path.name}: "
            f"{err.strip()[-300:] or 'unknown error'}"
        )
        trimmed_path.unlink(missing_ok=True)
        return None

    logger.info(f"Trimmed {video_path.name} to {duration}s hook clip: {trimmed_path.name}")
    return trimmed_path


async def concat_videos(paths: list, out_path: Path) -> Optional[Path]:
    """
    Join an ordered list of clips into ONE deliverable MP4.

    Used to turn an approved hook plus its approved extensions into a single
    file, which is what "one continuous video" has to mean to be downloadable
    and postable.

    The clips are re-encoded rather than stream-copied. Segments can come back
    from a provider with different resolution, frame rate or codec parameters,
    and the concat demuxer with `-c copy` produces a corrupt or unplayable file
    in that case rather than failing loudly. Re-encoding normalises every
    segment to the same parameters, which is also what makes the join seamless
    rather than a series of visible re-inits.

    Returns None (rather than raising) when the join is not possible, so the
    caller can fall back to the individual clips and say so.
    """
    sources = [Path(p) for p in (paths or []) if p and Path(p).is_file()]
    if not sources:
        logger.warning("concat_videos: no readable source clips.")
        return None
    if len(sources) == 1:
        # A single-segment video is already the deliverable; copying would
        # re-encode for nothing.
        return sources[0]

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    list_path = out_path.parent / f".{out_path.stem}_concat.txt"
    try:
        # The concat demuxer needs a file, and the paths can contain spaces or
        # drive letters, so each entry is quoted per its own spec.
        list_path.write_text(
            "\n".join(f"file '{str(p).replace(chr(39), chr(39) * 3)}'" for p in sources),
            encoding="utf-8",
        )
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            # Force identical timebase and frame rate so the join is a clean
            # cut with no duplicated or dropped frame at each boundary.
            "-r", "30",
            "-video_track_timescale", "30000",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "48000",
            "-ac", "2",
            "-movflags", "+faststart",
            str(out_path),
        ]
        try:
            rc, _stdout, err = await run_cmd(cmd, timeout=300)
        except FileNotFoundError:
            logger.warning("concat_videos: ffmpeg is not available on PATH.")
            return None
        except RuntimeError as e:
            logger.warning(f"concat_videos timed out: {e}")
            return None

        if rc != 0 or not out_path.exists() or out_path.stat().st_size == 0:
            logger.warning(
                f"concat_videos failed for {len(sources)} clips: "
                f"{err.strip()[-300:] or 'unknown error'}"
            )
            out_path.unlink(missing_ok=True)
            return None
    finally:
        list_path.unlink(missing_ok=True)

    logger.info(f"Concatenated {len(sources)} clips into {out_path.name}")
    return out_path
