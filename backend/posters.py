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
import threading
import uuid
from pathlib import Path

import pipeline

logger = logging.getLogger(__name__)

POSTERS_DIR = pipeline.STORAGE_DIR / "posters"
POSTERS_DIR.mkdir(parents=True, exist_ok=True)

# One poster encode at a time, process-wide.
#
# The 512MB host budgets in pipeline.py / overlays.py all cap ffmpeg at
# "-threads 1" because per-thread decode buffers are the largest single
# allocator — and an uncapped, overlapping poster encode is what OOM-killed the
# container. This lock plus the thread cap below are what keep one History
# page view (dozens of poster requests) from becoming dozens of ffmpegs.
_FFMPEG_LOCK = threading.Lock()

# Per-job single-flight: concurrent requests for the same poster share one
# encode instead of queueing identical ones behind the lock above.
_IN_FLIGHT: dict[str, threading.Event] = {}
_IN_FLIGHT_LOCK = threading.Lock()


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


def _poster_argv(video: Path, poster_tmp: Path, width: int) -> list:
    """
    The poster ffmpeg command as data, so the memory budget is assertable.

    `-threads 1` is the load-bearing flag: every other ffmpeg call in this
    repo carries it for the 512MB host, and its absence here is what let a
    poster encode spike the container. `test_posters.py` pins it.
    """
    return [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-threads", "1",
        "-ss", "0.5", "-i", str(video),
        "-vframes", "1",
        "-vf", f"scale={int(width)}:-2",
        "-q:v", "4",
        str(poster_tmp),
    ]


def generate_poster(video: Path, poster: Path, width: int = 480) -> bool:
    """
    Extract one JPEG frame from `video` into `poster`.

    Frame at 0.5s (past a possible black first frame), scaled down to `width`
    px wide to keep History lists light. Best-effort: False on any failure,
    never raises. Runs ffmpeg synchronously under a process-wide lock — one
    encode at a time — and callers must additionally thread it off the event
    loop.
    """
    try:
        if not video.is_file() or video.stat().st_size <= 0:
            return False
        poster.parent.mkdir(parents=True, exist_ok=True)
        tmp = poster.with_name(f".{poster.name}.{uuid.uuid4().hex}.jpg")
        with _FFMPEG_LOCK:
            proc = subprocess.run(
                _poster_argv(video, tmp, width),
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

    Single-flight per job: concurrent callers share one encode rather than
    queueing identical ones. No R2 here (needs the owner's user_id); the
    server route handles the cloud fallback where the row supplies it. Used
    by eager hooks after a save, when the video is known to be local.

    Called from worker threads (asyncio.to_thread), so blocking on the
    in-flight event is safe.
    """
    poster = poster_path(job_id)
    if is_usable_poster(poster):
        return poster
    with _IN_FLIGHT_LOCK:
        if is_usable_poster(poster):
            return poster
        event = _IN_FLIGHT.get(job_id)
        if event is None:
            event = threading.Event()
            _IN_FLIGHT[job_id] = event
            owner = True
        else:
            owner = False
    if not owner:
        event.wait(timeout=120)
        return poster if is_usable_poster(poster) else None
    try:
        video = video_path(job_id)
        if generate_poster(video, poster):
            return poster
        return None
    finally:
        with _IN_FLIGHT_LOCK:
            _IN_FLIGHT.pop(job_id, None)
        event.set()
