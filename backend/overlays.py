"""
Canvas and camera utilities for finished renders.

Every generated clip is vertical; these helpers fit one onto the 1080x1920
canvas and bake the hook-boundary camera move into the canonical file during
finalize, so the preview and the download carry it. Both are pure ffmpeg argv
plus soft-fail executors: a clip that cannot be resized or reframed is still a
watchable video, so losing either must never lose the generation.

Burned-in captions were removed from the Hook + Story path, and the
text/image/audio composition machinery went with them. Nothing here draws
anymore.
"""
import asyncio
import logging
import math
import subprocess
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# Portrait canvas. Every generated clip is vertical; the canvas fit is applied
# against this frame so geometry is predictable.
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920

# Processing owns exactly one centered zoom. The generated footage alone owns
# the orbit and actor gesture; there is no crop-based arc or face-following pan.
TRANSITION_MAGNIFICATION = 1.10  # Total, not an additive zoom percentage.
TRANSITION_RAMP_SECONDS = 0.6
TRANSITION_EDGE_MARGIN = 0.6
CAMERA_BEAT_FRACTION = 0.7


def camera_beat_seconds(hook_seconds, strategy: dict = None) -> float:
    """Zoom START time: 70% of hook_seconds, completing about 0.6s later.

    The unused strategy argument is accepted for legacy callers, but a saved
    camera_beat.at never overrides the ratio. The model is asked to orbit only
    'when the story begins', not at a timestamp or on a particular spoken word.
    """
    try:
        hook = float(hook_seconds or 0)
    except (TypeError, ValueError):
        return 0.0
    return round(CAMERA_BEAT_FRACTION * hook, 3) if math.isfinite(hook) and hook > 0 else 0.0


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

    Lanczos, not bilinear. Most studio renders arrive BELOW this canvas (Grok
    at 720p, H3 Max and HeyGen at 768p) and are therefore scaled up, and
    bilinear is visibly mushier there. Lanczos resolves those edges materially
    better for a cost that is lost next to the x264 encode that follows, and it
    also cleans the down-scale direction when a 2K render is brought down to the
    canvas.

    It still adds no detail: it resamples, it does not super-resolve, and
    nothing here should be described to a founder as sharpening their video.
    """
    return [
        f"[{source_label}]scale={CANVAS_WIDTH}:{CANVAS_HEIGHT}:"
        f"force_original_aspect_ratio=decrease:flags=lanczos[scaled_{out_label}]",
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


def build_camera_move_command(
    source: Path,
    output_path: Path,
    at_seconds: float,
    duration: float,
    magnification: float = TRANSITION_MAGNIFICATION,
) -> list:
    """Apply one straight centered zoom, starting at at_seconds.

    Magnification is the TOTAL setting (1.08–1.12, default exactly 1.10), with
    no extra scale for sideways travel. Smoothstep reaches it 0.6s after the
    start and holds to the end. Center remains fixed; there is no pan, face
    repositioning or synthetic orbit. One inverse-coordinate resampling keeps
    fractional crop coordinates and the exact setting, without integer scale
    rounding or dynamic-scale/crop reconfiguration shifting the crop origin.

    The generated shot must keep head/chin/phone inside the central 88% so the
    centered crop preserves them. Processing cannot recover already-missing
    pixels or guarantee safe framing for arbitrary older source clips.
    """
    magnification = float(magnification)
    if not 1.08 <= magnification <= 1.12:
        raise ValueError("Camera zoom must be a total magnification from 1.08 to 1.12.")
    cut_at = float(at_seconds)
    # Smoothstep starts with zero velocity and ends with zero velocity.
    # Time is relative to the post-start half, not the original file clock.
    ramp = f"min(max(T/{TRANSITION_RAMP_SECONDS},0),1)"
    ease = f"({ramp})*({ramp})*(3-2*({ramp}))"
    grow = f"(1+({magnification!r}-1)*{ease})"
    # Map every destination pixel back into a centered source window. W/H
    # refer to each plane, so chroma follows exactly the same geometry as luma.
    # No lateral offset, extra magnification, face anchor or integer crop step.
    coordinates = f"(X-W/2)/{grow}+W/2,(Y-H/2)/{grow}+H/2"
    graph = ";".join([
        "[0:v]split=2[pre0][post0]",
        f"[pre0]trim=end={cut_at:.3f},setpts=PTS-STARTPTS[pre]",
        f"[post0]trim=start={cut_at:.3f},setpts=PTS-STARTPTS,"
        f"geq=lum='lum({coordinates})':cb='cb({coordinates})'"
        f":cr='cr({coordinates})':interpolation=bilinear[post]",
        "[pre][post]concat=n=2:v=1:a=0,format=yuv420p[outv]",
    ])
    return [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        # Single-threaded for the same reason as every other call site here:
        # per-thread decode buffers are the largest thing ffmpeg allocates on a
        # small host, and a slower finalize beats an OOM restart.
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


def apply_camera_move_sync(
    video_path: Path,
    at_seconds: float,
    timeout: int = 600,
) -> tuple:
    """
    Bake the single centered zoom into one clip in place.

    Returns (path_or_None, warnings). Soft by design, like the canvas resize: an
    unmoved clip is still a watchable video, so losing the move must never lose
    the generation. Skipped (not failed) when the boundary has no room on either
    side for the ramp.

    Written to a sibling temp file and swapped, because ffmpeg cannot read and
    write the same path in one pass.
    """
    source = Path(video_path)
    if not source.is_file():
        return None, ["Source clip is missing; the camera move was skipped."]
    duration = probe_duration(source)
    if duration <= 0:
        return None, ["Could not read the base clip's duration; the camera move was skipped."]
    # The crop window is the canvas size throughout the ramp, so the frame
    # being moved must already be at least that big -- in the finalize path the
    # canvas resize runs first for exactly this reason. Moving a smaller
    # frame would crop outside it and fail the render.
    width, height = probe_video_dims(source)
    if width and height and (width < CANVAS_WIDTH or height < CANVAS_HEIGHT):
        return None, ["Clip is smaller than the canvas; the camera move was skipped."]
    try:
        cut_at = float(at_seconds or 0)
    except (TypeError, ValueError):
        cut_at = 0
    latest = duration - TRANSITION_EDGE_MARGIN
    if not (TRANSITION_EDGE_MARGIN < cut_at < latest):
        return None, []
    temp = source.with_name(f".{source.stem}_move_{uuid.uuid4().hex}{source.suffix}")
    try:
        argv = build_camera_move_command(
            source, temp, cut_at, duration,
        )
        try:
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, [f"Camera move timed out after {timeout}s."]
        except FileNotFoundError as e:
            return None, [f"ffmpeg is not available: {e}"]
        if proc.returncode != 0 or not temp.exists():
            detail = (proc.stderr or "").strip().splitlines()
            tail = detail[-1] if detail else "unknown error"
            logger.warning("Camera move failed: %s", tail)
            return None, [f"ffmpeg failed while applying the camera move: {tail[:200]}"]
        temp.replace(source)
        return source, []
    finally:
        temp.unlink(missing_ok=True)


async def apply_camera_move(
    video_path: Path,
    at_seconds: float,
    timeout: int = 600,
) -> tuple:
    """Async wrapper so the poll path can await this alongside its other work."""
    return await asyncio.to_thread(
        apply_camera_move_sync, video_path, at_seconds, timeout,
    )
