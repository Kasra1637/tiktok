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
import subprocess
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Portrait canvas. Every generated clip is vertical; the canvas fit is applied
# against this frame so geometry is predictable.
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920

# The hook-boundary camera move.
#
# One render covers the whole piece, so there is no edit point to cut at -- but a
# piece that never changes angle reads as one static shot, and the beat where
# the hook's line lands is where attention needs re-hooking. What is baked here
# is a selfie lean-in: the camera pushes in AND arcs to one three-quarter angle,
# so she grows toward the lens and settles off-axis rather than merely filling
# the frame, and that framing then holds for the rest of the piece.
# Time-based (t), not frame-based (n), so it lands identically at any fps.
#
# Done here rather than in the prompt for the same reason anything
# frame-exact is: the model cannot be trusted with timing, and a prompt asking
# for "a move at 1.4 seconds" drifts. ffmpeg lands it on the frame.
TRANSITION_RAMP_SECONDS = 0.6

# How much tighter the shot ends up, as a fraction of frame size. Kept small
# because it is NOT the only cost of the move: see TRANSITION_MAGNIFICATION --
# lateral travel is paid for in magnification, and the zoom is only the part of
# that budget a founder perceives as a push-in.
TRANSITION_ZOOM = 0.07

# How far she travels across the frame, as a fraction of frame WIDTH.
# Canvas-relative on purpose. This used to be a fraction of the slack the zoom
# created, which made the reframe a rounding error: the canvas fit leaves the
# frame exactly canvas-sized, so at the boundary there is no spare width at all
# and every pixel of lateral travel had to be borrowed from the zoom. On a 1080
# frame that produced 27 pixels -- 2.5% of width, invisible on a phone -- which
# is why a piece built around this transition read as "it only zooms".
TRANSITION_ARC = 0.09

# Total magnification at the end of the ramp.
#
# Lateral travel is not free in a flat reframe. There are no pixels outside the
# canvas to reveal -- no parallax, no new perspective, no way to synthesize a
# viewpoint that was never rendered -- so a camera move is a crop, and a crop
# can only move by sliding a window inside a larger frame. Sliding it by ARC
# needs half the width-slack on the chosen side, which is (M-1)/2; the extra
# ZOOM is what pays for looking tighter. M = 1 + 2*ARC + ZOOM keeps both visible
# without silently eating one to fund the other.
TRANSITION_MAGNIFICATION = 1 + 2 * TRANSITION_ARC + TRANSITION_ZOOM

# Where her face ends up vertically, as a fraction of frame height. Just above
# centre, which is where a person leaning into a phone camera actually lands:
# close enough to the lens that her head breaks the top edge, still holding her
# eyes above the horizontal centre line where they read as into-camera.
TRANSITION_FACE_REST_Y = 0.45

# A boundary needs room on both sides for the ramp. Closer to either end than
# this, the move would start before the first frame or finish past the last
# one, so the transition is skipped instead of rendered half. Held equal to the
# ramp on purpose: the old 0.3 was thinner than the 0.25 ramp it was guarding,
# and a 0.6s move needs its own length in front of it.
TRANSITION_EDGE_MARGIN = 0.6

# Where inside the hook the move lands, as a fraction of the hook's own length.
#
# Not the hook/middle boundary itself. A lean-in that fires exactly where the
# hook ends is the same instant the spoken line lands, so the two read as one
# event and the viewer registers a cut rather than a beat. Landing at 70% puts
# the move under the last words of the hook line, on the beat, which is what
# makes it read as her moving rather than as a filter being applied.
CAMERA_BEAT_FRACTION = 0.7


def camera_beat_seconds(hook_seconds, strategy: dict = None) -> float:
    """
    The second the camera move lands on, or 0.0 when there is no beat to land on.

    Read from the strategy's `camera_beat`, which is written back with the exact
    same number the render prompt is given, so the model is asked to perform a
    lean at a second and ffmpeg reframes at that second rather than each
    re-deriving it and disagreeing. A beat after the hook is not a beat in the
    hook, so a stored value is clamped into it; a strategy saved before this
    field existed, or one whose model omitted it, gets the fraction applied here
    -- the identical value the writer would have stored.

    This is the closest thing to "on the beat" that is honestly available. There
    is no per-phrase speech timing in this system (beat_timeline is exactly two
    intervals, forced), and no usable audio to find one in: two of the three
    providers return no audio at all and the third defaults its own off, so a
    beat has to be committed to in advance rather than detected.
    """
    try:
        hook = max(0.0, float(hook_seconds or 0))
    except (TypeError, ValueError):
        hook = 0.0
    beat = (strategy or {}).get("camera_beat")
    try:
        at = float(beat.get("at")) if isinstance(beat, dict) else 0.0
    except (TypeError, ValueError):
        at = 0.0
    if at <= 0 or at > hook:
        at = CAMERA_BEAT_FRACTION * hook
    return round(at, 3)


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


def detect_face_center(video_path: Path, at_seconds: float) -> Optional[tuple]:
    """
    Where her face is in one frame of the clip, as fractions of frame size.

    Returns (x, y) each in 0..1, or None when no face can be found. This is the
    pivot the camera move is built around, and it is the whole difference
    between a move that reads as a person leaning into the lens and one that
    reads as a crop sliding across a picture: the zoom has to grow AROUND HER,
    not around the middle of the frame. The canvas fit guarantees the middle of
    the frame is only the middle of the frame.

    Sampled before the boundary, not after: this is where she is when the move
    starts, which is the framing the move then has to preserve.

    The detector is the same YuNet model the identity reference already uses
    (see face_crop), vendored in this repo, so this costs no new dependency and
    no new model file. Imported lazily because a missing model must never fail
    a render, and because the move is skipped entirely on most boundaries.
    """
    source = Path(video_path)
    if not source.is_file():
        return None
    try:
        from PIL import Image
        import numpy as np
        from face_crop import _detect_face
    except Exception as e:
        logger.warning("Face pivot unavailable (%s); framing on the frame.", e)
        return None

    temp = source.with_name(f".{source.stem}_pivot_{uuid.uuid4().hex}.png")
    try:
        try:
            proc = subprocess.run(
                [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-threads", "1",
                    # Seek ahead of the input so this decodes one frame rather
                    # than everything up to the boundary.
                    "-ss", f"{max(0.0, float(at_seconds)):.3f}",
                    "-i", str(source),
                    "-frames:v", "1", str(temp),
                ],
                capture_output=True, text=True, timeout=120,
            )
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning("Pivot frame extraction failed (%s); framing on the frame.", e)
            return None
        if proc.returncode != 0 or not temp.exists():
            logger.info("No pivot frame at %.2fs; framing the move on the frame.", at_seconds)
            return None
        try:
            frame = np.array(Image.open(temp).convert("RGB"))
        except Exception as e:
            logger.warning("Pivot frame unreadable (%s); framing on the frame.", e)
            return None
        height, width = frame.shape[:2]
        if width < 2 or height < 2:
            return None
        box = _detect_face(frame)
        if box is None:
            return None
        fx, fy, fw, fh, _confidence = box
        return (
            min(1.0, max(0.0, (fx + fw / 2.0) / width)),
            min(1.0, max(0.0, (fy + fh / 2.0) / height)),
        )
    finally:
        temp.unlink(missing_ok=True)


def crop_target(face_x: float, face_y: float, direction: int = 1) -> tuple:
    """
    The crop window's resting offset, in pixels, for a face-anchored move.

    `face_x`/`face_y` are fractions of the frame. `direction` is +1 to arc so
    she travels right across the frame, -1 for left.

    Solved rather than interpolated, because what is being specified is HER
    output position, not the window's slide: at full magnification she sits at
    M*face and the window's centre at x + width/2, so travelling by ARC*WIDTH
    means x = M*face_x - face_x - direction*ARC*WIDTH. Vertically the same, with
    her face coming to rest just above centre.

    Both are clamped to the slack. A subject already hard against one edge, or a
    centre fallback, must not push the window off its own frame. ffmpeg clamps
    too, but only after the ramp has been following a target it cannot reach,
    which shows as the move sticking to the edge and then catching up.
    """
    magnification = TRANSITION_MAGNIFICATION
    slack_x = (magnification - 1) * CANVAS_WIDTH
    slack_y = (magnification - 1) * CANVAS_HEIGHT
    face_px_x = face_x * CANVAS_WIDTH
    face_px_y = face_y * CANVAS_HEIGHT
    want_x = face_px_x * (magnification - 1) - direction * TRANSITION_ARC * CANVAS_WIDTH
    want_y = magnification * face_px_y - TRANSITION_FACE_REST_Y * CANVAS_HEIGHT
    return (
        round(min(slack_x, max(0.0, want_x)), 3),
        round(min(slack_y, max(0.0, want_y)), 3),
    )


def build_camera_move_command(
    source: Path,
    output_path: Path,
    at_seconds: float,
    duration: float,
    face_x: float = 0.5,
    face_y: float = 0.5,
    direction: int = 1,
) -> list:
    """
    ffmpeg argv that bakes the hook-boundary camera move into one clip.

    A selfie lean-in over TRANSITION_RAMP_SECONDS at `at_seconds`: a push-in plus
    a lateral arc to one three-quarter angle, pivoted on her detected face so she
    grows toward the lens instead of the frame closing up around its own middle.
    The framing reached is held for the rest of the piece, because a piece that
    wobbles back to centre reads as an effect rather than as a shot that
    changed. The render prompt asks for the same lean (see
    generation_planning._CAMERA_MOVE), and this pass is what lands it on the
    frame whether or not the model honoured it.

    `face_x`/`face_y` place the subject in the frame as fractions; the caller
    gets them from detect_face_center and falls back to dead centre when no face
    is found. `direction` is +1 or -1 and picks which side she arcs to.

    Time-based (t), not frame-based (n), so it lands identically at any fps.
    Audio is copied untouched; only the picture is reframed.
    """
    cut_at = float(at_seconds)
    crop_x, crop_y = crop_target(face_x, face_y, 1 if direction >= 0 else -1)
    # Smoothstep, not a linear ramp. The ramp used to slide at a constant rate
    # and stop dead, which is part of why the move read as post-processing: a
    # real head gesture accelerates into the lean and settles out of it, and a
    # curve with zero velocity at both ends is the cheapest way to say so.
    ramp = f"min(max(t/{TRANSITION_RAMP_SECONDS},0),1)"
    ease = f"({ramp})*({ramp})*(3-2*({ramp}))"
    grow = f"(1+{TRANSITION_MAGNIFICATION - 1:.4f}*{ease})"
    graph = ";".join([
        "[0:v]split=2[pre0][post0]",
        f"[pre0]trim=end={cut_at:.3f},setpts=PTS-STARTPTS[pre]",
        f"[post0]trim=start={cut_at:.3f},setpts=PTS-STARTPTS,"
        f"scale=w='trunc(iw*{grow}/2)*2'"
        f":h='trunc(ih*{grow}/2)*2'"
        f":eval=frame,"
        f"crop={CANVAS_WIDTH}:{CANVAS_HEIGHT}"
        f":x='{crop_x}*{ease}'"
        f":y='{crop_y}*{ease}'[post]",
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
    direction: int = 1,
    timeout: int = 600,
) -> tuple:
    """
    Bake the hook-boundary camera move into one clip in place.

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
    pivot = detect_face_center(source, max(0.0, cut_at - 0.15))
    if pivot is None:
        logger.info(
            "No face pivot for %s; framing the camera move on the frame centre.", source.name,
        )
        face_x = face_y = 0.5
    else:
        face_x, face_y = pivot
    temp = source.with_name(f".{source.stem}_move_{uuid.uuid4().hex}{source.suffix}")
    try:
        argv = build_camera_move_command(
            source, temp, cut_at, duration, face_x, face_y, direction,
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
    direction: int = 1,
    timeout: int = 600,
) -> tuple:
    """Async wrapper so the poll path can await this alongside its other work."""
    return await asyncio.to_thread(
        apply_camera_move_sync, video_path, at_seconds, direction, timeout,
    )


def move_direction_for(generation_id: str) -> int:
    """
    Which way this generation's move arcs: +1 (she travels right) or -1 (left).

    Derived from the generation id, so it is not random: the same generation
    always gets the same direction, which is what keeps the move reproducible
    and lets a founder who dislikes one video regenerate it and get a different
    one rather than an identical reroll. Every render leaning the identical way
    is what made the arc read as a template rather than as a shot.
    """
    text = str(generation_id or "")
    if not text:
        return 1
    return 1 if sum(ord(char) for char in text) % 2 == 0 else -1


