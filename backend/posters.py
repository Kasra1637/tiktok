"""
Poster thumbnails for generation History.

Why this exists
---------------
History rows used `<video preload="metadata">` with no poster, so the
thumbnail WAS the video: every row fetched byte ranges of a multi-MB clip
just to decode its first frame. A missing local copy, an expired signed URL,
a slow R2 redirect, or an MP4 without `+faststart` (moov at end) all
rendered as a blank player instead of a thumbnail.

A poster is a tiny JPEG (~10-40KB) extracted once via ffmpeg and served as
an image: it loads instantly, needs no byte ranges, and displays even when
the video itself cannot play yet. The `<video poster>` then shows the
thumbnail without fetching any video bytes (`preload="none"`).

Where posters live
------------------
- Local: `{STORAGE_DIR}/posters/{job_id}.jpg` (alongside videos/, not inside
  it, so the video range route never confuses the two).
- Cloud: `{user_id}/{job_id}.jpg` in the same R2 bucket (durable across
  deploys, like videos).

No DB column: the poster URL is deterministic from the generation id
(`/api/media/posters/{id}.jpg`, signed on the way out like videos), and the
poster route lazily generates/restores on first hit. Old rows therefore heal
themselves without a backfill job.
"""
import logging
import subprocess
from pathlib import Path

import pipeline

logger = logging.getLogger(__name__)

POSTERS_DIR = pipeline.STORAGE_DIR / "posters"
POSTERS_DIR.mkdir(parents=True, exist_ok=True)


def poster_path(job_id: str) -> Path:
    """Local poster file for this generation id."""
    return POSTERS_DIR / f"{job_id}.jpg"


def video_path(job_id: str) -> Path:
    """Local video file for this generation id (canonical .mp4 name)."""
    return pipeline.VIDEOS_DIR / f"{job_id}.mp4"


def is_usable_poster(path: Path) -> bool:
    """A poster is a non-empty JPEG (magic bytes FF D8 FF)."""
    try:
        if not path.is_file() or path.stat().st_size < 512:
            return False
        with path.open("rb") as fh:
            head = fh.read(3)
        return head[:2] == b"\xff\xd8" and len(head) == 3
    except OSError:
        return False


def generate_poster(video: Path, poster: Path, width: int = 480) -> bool:
    """
    Extract one JPEG frame from `video` into `poster`.

    Frame at 0.5s (past a possible black first frame), scaled down to `width`
    px wide to keep History lists light. Best-effort: False on any failure,
    never raises. Runs ffmpeg synchronously; callers must thread it off the
    event loop.
    """
    try:
        if not video.is_file() or video.stat().st_size <= 0:
            return False
        poster.parent.mkdir(parents=True, exist_ok=True)
        tmp = poster.with_name(f".{poster.name}.{__import__('uuid').uuid4().hex}.jpg")
        proc = subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", "0.5", "-i", str(video),
                "-vframes", "1",
                "-vf", f"scale={int(width)}:-2",
                "-q:v", "4",
                str(tmp),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if proc.returncode != 0 or not is_usable_poster(tmp):
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            return False
        tmp.replace(poster)
        return True
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        logger.warning("Poster generation failed for %s (%s)", video.name, type(exc).__name__)
        return False
    except Exception as exc:  # ffmpeg missing etc: never break the save path
        logger.warning("Poster generation failed for %s (%s)", video.name, type(exc).__name__)
        return False


def ensure_poster(job_id: str) -> Path | None:
    """
    Return the local poster, generating it from the local video if needed.

    No R2 here (needs the owner's user_id); the server route handles the
    cloud fallback where the row supplies it. Used by eager hooks right after
    a save, when the video is known to be local.
    """
    poster = poster_path(job_id)
    if is_usable_poster(poster):
        return poster
    video = video_path(job_id)
    if generate_poster(video, poster):
        return poster
    return None
