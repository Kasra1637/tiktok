"""
Canvas and camera utilities for finished renders.

Every generated clip is vertical; these helpers fit one onto the 1080x1920
canvas and bake the hook-to-middle zoom-punch into the canonical file during
finalize, so the preview and the download carry it. Both are pure ffmpeg argv
plus soft-fail executors: a clip that cannot be resized or cut is still a
watchable video, so losing either must never lose the generation.

Burned-in captions were removed from the Hook + Story path, and the
text/image/audio composition machinery went with them. Nothing here draws
anymore.
"""
import asyncio
import logging
import subprocess
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Portrait canvas. Every generated clip is vertical; the canvas fit is applied
# against this frame so geometry is predictable.
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920

# The hook-to-middle cut. One render covers the whole piece, so there is no
# edit point to cut at -- but a piece that never changes angle reads as one
# static shot, and the hook-to-middle boundary is where attention needs
# re-hooking. This is a deterministic zoom-punch with a lateral reframe,
# ramped over a quarter second at the boundary and held for the rest of the
# piece: a sudden cut to a tighter, reframed angle, not a wobble that returns.
# Time-based (t), not frame-based (n), so it lands identically at any fps.
#
# Done here rather than in the prompt for the same reason anything
# frame-exact is: the model cannot be trusted with timing, and a prompt asking
# for "a cut at 3 seconds" drifts. ffmpeg lands it on the frame.
TRANSITION_RAMP_SECONDS = 0.25
TRANSITION_ZOOM = 0.17
TRANSITION_SHIFT = 0.35
# A boundary needs room on both sides for the ramp. Closer to either end than
# this, the move would start before the first frame or finish past the last
# one, so the transition is skipped instead of rendered half.
TRANSITION_EDGE_MARGIN = 0.3


def canvas_fit_chain(source_label: str, out_label: str) -> list:
    """
    Filter fragments that fit a clip onto the 1080x1920 canvas, letterboxed.

    Shared by the finalize rescale and the plain-download rescale so both
    produce the same frame size. The studio's cheaper providers render below
    this canvas (Grok at 720p), and a founder posting to TikTok wants the
    platform's own 1080x1920 rather than whatever the model emitted.

    The scale and pad MUST be chained through explicit labels. Chaining two
    filters off the same source label leaves the first one's output dangling
    and unconnected, so pad re-reads the raw input and everything downstream is
    silently orphaned — ffmpeg still exits 0 and writes a file.

    Note this is a plain bilinear scale: it meets the platform's pixel
    dimensions without adding detail. It is not super-resolution, and nothing
    here should be described to a founder as sharpening their video.
    """
    return [
        f"[{source_label}]scale={CANVAS_WIDTH}:{CANVAS_HEIGHT}:"
        f"force_original_aspect_ratio=decrease[scaled_{out_label}]",
        f"[scaled_{out_label}]pad={CANVAS_WIDTH}:{CANVAS_HEIGHT}:"
        f"(ow-iw)/2:(oh-ih)/2:color=black[{out_label}]",
    ]


def build_upscale_command(source: Path, output_path: Path) -> list:
    """
    ffmpeg argv that re-encodes one clip onto the canvas with no overlays.

    Used for the plain "Download MP4" path, which would otherwise hand the
    founder the provider's native size — 720p for Grok,
    which is below what the platform expects.

    Audio is copied when present and dropped when absent, because the providers
    here differ: Hailuo 3 returns a native audio track and Grok does not. A
    graph referencing a stream that isn't there fails, so 0:a? is the only form
    that works for both.
    """
    graph = ";".join(canvas_fit_chain("0:v", "outv"))

    return [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        # Single-threaded for the same reason as trim_video_exact: this runs in
        # the web process on a 512MB host, and per-thread decode buffers are the
        # biggest thing ffmpeg allocates. A slower save beats an OOM restart.
        "-threads", "1",
        "-i", str(source),
        "-filter_complex", graph,
        "-map", "[outv]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "aac",
        # +faststart moves the moov atom to the front of the file. Without it
        # the index sits at the end, so a player must fetch the whole clip
        # before it can seek or report a duration — which is what made these
        # clips show 0:00 and refuse to scrub. It is a container-level move, not
        # a re-encode: no quality is touched and it costs a fraction of a second
        # on a file that was just re-encoded anyway.
        "-movflags", "+faststart",
        str(output_path),
    ]

def probe_duration(path: Path) -> float:
    """Duration in seconds via ffprobe, or 0.0 when unavailable."""
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        return round(float((proc.stdout or "0").strip()), 3)
    except Exception as e:
        logger.warning("ffprobe failed for %s: %s", path, e)
        return 0.0


def probe_video_dims(path: Path) -> tuple:
    """(width, height) of the first video stream, or (0, 0) when unavailable."""
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=p=0", str(path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        parts = (proc.stdout or "").strip().split(",")
        return int(parts[0]), int(parts[1])
    except Exception as e:
        logger.warning("ffprobe dims failed for %s: %s", path, e)
        return 0, 0


def rescale_to_canvas_sync(video_path: Path, timeout: int = 600) -> tuple:
    """
    Re-encode one clip onto the 1080x1920 canvas in place.

    Returns (path_or_None, warnings). A failure is soft and always says so: the
    un-rescaled clip is still a watchable video, so losing the canvas resize
    must never lose the generation.

    Written to a sibling temp file and swapped, because ffmpeg cannot read and
    write the same path in one pass — the same reason replace_with_trimmed does
    it that way.
    """
    source = Path(video_path)
    if not source.is_file():
        return None, ["Source clip is missing; the canvas resize was skipped."]
    temp = source.with_name(f".{source.stem}_canvas_{uuid.uuid4().hex}{source.suffix}")
    try:
        argv = build_upscale_command(source, temp)
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, [f"Canvas resize timed out after {timeout}s."]
        except FileNotFoundError as e:
            return None, [f"ffmpeg is not available: {e}"]
        if proc.returncode != 0 or not temp.exists():
            detail = (proc.stderr or "").strip().splitlines()
            tail = detail[-1] if detail else "unknown error"
            logger.warning("Canvas resize failed: %s", tail)
            return None, [f"ffmpeg failed while resizing to the canvas: {tail[:200]}"]
        temp.replace(source)
        return source, []
    finally:
        temp.unlink(missing_ok=True)


async def rescale_to_canvas(video_path: Path, timeout: int = 600) -> tuple:
    """Async wrapper so the poll path can await this alongside its other work."""
    return await asyncio.to_thread(rescale_to_canvas_sync, video_path, timeout)


def build_camera_cut_command(source: Path, output_path: Path, at_seconds: float, duration: float) -> list:
    """
    ffmpeg argv that bakes the hook-to-middle zoom-punch into one clip.

    The same deterministic cut the retired composition used to apply: a
    quarter-second ramp at `at_seconds` into a tighter, laterally reframed
    angle, held for the rest of the piece. Extracted here because the cut now
    belongs to every finished render — the raw preview and
    download never passed through the composition, so the cut was invisible
    there at any magnitude.

    Time-based (t), not frame-based (n), so it lands identically at any fps.
    Audio is copied untouched; only the picture is reframed.
    """
    cut_at = float(at_seconds)
    ramp = f"min(max(t/{TRANSITION_RAMP_SECONDS},0),1)"
    graph = ";".join([
        "[0:v]split=2[pre0][post0]",
        f"[pre0]trim=end={cut_at:.3f},setpts=PTS-STARTPTS[pre]",
        f"[post0]trim=start={cut_at:.3f},setpts=PTS-STARTPTS,"
        f"scale=w='trunc(iw*(1+{TRANSITION_ZOOM}*{ramp})/2)*2'"
        f":h='trunc(ih*(1+{TRANSITION_ZOOM}*{ramp})/2)*2'"
        f":eval=frame,"
        f"crop={CANVAS_WIDTH}:{CANVAS_HEIGHT}"
        f":x='(in_w-out_w)/2-{ramp}*(in_w-out_w)*{TRANSITION_SHIFT}'"
        f":y='(in_h-out_h)/2'[post]",
        "[pre][post]concat=n=2:v=1:a=0,format=yuv420p[outv]",
    ])
    return [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        # Single-threaded for the same reason as every other call site here:
        # per-thread decode buffers are the largest thing ffmpeg allocates on
        # a small host, and a slower finalize beats an OOM restart.
        "-threads", "1",
        "-i", str(source),
        "-filter_complex", graph,
        "-map", "[outv]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-t", str(float(duration)),
        "-c:a", "aac",
        "-movflags", "+faststart",
        str(output_path),
    ]


def apply_camera_cut_sync(video_path: Path, at_seconds: float, timeout: int = 600) -> tuple:
    """
    Bake the hook-to-middle cut into one clip in place.

    Returns (path_or_None, warnings). Soft by design, like the canvas resize:
    an uncut clip is still a watchable video, so losing the cut must never
    lose the generation. Skipped (not failed) when the boundary has no room
    on either side for the ramp.

    Written to a sibling temp file and swapped, because ffmpeg cannot read
    and write the same path in one pass.
    """
    source = Path(video_path)
    if not source.is_file():
        return None, ["Source clip is missing; the camera cut was skipped."]
    duration = probe_duration(source)
    if duration <= 0:
        return None, ["Could not read the base clip's duration; the camera cut was skipped."]
    # The crop window is the canvas size throughout the ramp, so the frame
    # being cut must already be at least that big — in the finalize path the
    # canvas resize runs first for exactly this reason. Cutting a smaller
    # frame would crop outside it and fail the render.
    width, height = probe_video_dims(source)
    if width and height and (width < CANVAS_WIDTH or height < CANVAS_HEIGHT):
        return None, ["Clip is smaller than the canvas; the camera cut was skipped."]
    try:
        cut_at = float(at_seconds or 0)
    except (TypeError, ValueError):
        cut_at = 0
    latest = duration - TRANSITION_EDGE_MARGIN
    if not (TRANSITION_EDGE_MARGIN < cut_at < latest):
        return None, []
    temp = source.with_name(f".{source.stem}_cut_{uuid.uuid4().hex}{source.suffix}")
    try:
        argv = build_camera_cut_command(source, temp, cut_at, duration)
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, [f"Camera cut timed out after {timeout}s."]
        except FileNotFoundError as e:
            return None, [f"ffmpeg is not available: {e}"]
        if proc.returncode != 0 or not temp.exists():
            detail = (proc.stderr or "").strip().splitlines()
            tail = detail[-1] if detail else "unknown error"
            logger.warning("Camera cut failed: %s", tail)
            return None, [f"ffmpeg failed while applying the camera cut: {tail[:200]}"]
        temp.replace(source)
        return source, []
    finally:
        temp.unlink(missing_ok=True)


async def apply_camera_cut(video_path: Path, at_seconds: float, timeout: int = 600) -> tuple:
    """Async wrapper so the poll path can await this alongside its other work."""
    return await asyncio.to_thread(apply_camera_cut_sync, video_path, at_seconds, timeout)


