"""
Deterministic overlay composition.

The point of this module: the generative model must never be trusted to draw
an app interface, a price, a rating, or a logo. It produces a person, a
scene, and movement; everything factual is composited here with ffmpeg, from
real assets and verified text, so the result is pixel-exact and cannot drift.

build_filter_graph() is a pure function from a composition spec to an ffmpeg
filter graph. It performs no I/O, which is what makes the geometry testable
without rendering anything. compose() is the executor that runs ffmpeg.

Only text that already passed claim_safety should reach this module: overlay
text is on screen and is read by viewers, so it is subject to the same rules
as the spoken script.
"""
import asyncio
import logging
import os
import shlex
import subprocess
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Brand palette, matching the site/app identity.
BRAND_PRIMARY = "#9370DB"
BRAND_DEEP = "#6A3FC0"

# Portrait canvas. Every generated clip is vertical; overlays are positioned
# against this frame so geometry is predictable.
CANVAS_WIDTH = 1080
CANVAS_HEIGHT = 1920

# Safe areas as a fraction of the frame, leaving room for platform UI.
SAFE_MARGIN_X = 0.08
SAFE_MARGIN_Y = 0.10

VIDEO_KINDS = ("screen_recording", "background_video")
IMAGE_KINDS = (
    "screenshot", "logo", "product_image", "character_reference",
    "creator_photo", "background_image",
)
AUDIO_KINDS = ("audio",)
AUDIO_ROLES = ("background", "voiceover")
# A background bed stays underneath generated speech; a voiceover is meant to
# be heard as the primary audio for its window.
AUDIO_DEFAULT_GAINS = {"background": 0.25, "voiceover": 1.0}

# Fonts that exist on a stock Windows install. Resolved once, at build time,
# so a missing font fails loudly rather than producing blank text.
_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)


def resolve_font() -> Optional[str]:
    """First available font file, or None so the caller can refuse cleanly."""
    override = (os.environ.get("OVERLAY_FONT") or "").strip()
    candidates = ([override] if override else []) + list(_FONT_CANDIDATES)
    for path in candidates:
        if path and Path(path).is_file():
            return path
    return None


def _caption_coords(position: str) -> tuple:
    """
    x/y EXPRESSIONS for a caption, letting ffmpeg measure the text itself.

    Computing pixel offsets requires estimating glyph width, which is wrong
    for any string the estimate did not anticipate -- a long caption then
    overflows the frame edge. drawtext exposes text_w/text_h, so centring and
    right-alignment are exact regardless of the copy.
    """
    margin_x = int(CANVAS_WIDTH * SAFE_MARGIN_X)
    margin_y = int(CANVAS_HEIGHT * SAFE_MARGIN_Y)
    preset = (position or "bottom").lower()

    if preset in ("top", "center", "bottom"):
        x = "(w-text_w)/2"
    elif preset in ("top_left", "bottom_left"):
        x = str(margin_x)
    else:  # right-aligned variants
        x = f"w-text_w-{margin_x}"

    if preset == "top":
        y = str(margin_y)
    elif preset == "bottom":
        y = f"h-text_h-{margin_y}"
    else:
        y = "(h-text_h)/2"
    return x, y


def _escape_filter_path(path: str) -> str:
    """
    Make a filesystem path safe to embed in an ffmpeg filter description.

    Two problems bite here. ':' separates options in filter syntax, so a
    Windows drive letter ("C:\\Windows\\...") is read as an option boundary
    and the graph fails to parse. '\\' is the filter escape character. The
    fix is to use forward slashes and escape the colon; quoting alone is not
    enough because the colon is special inside the quoted value too.
    """
    text = str(path or "").replace("\\", "/")
    text = text.replace(":", "\\:")
    return f"'{text}'"


def _escape_drawtext(text: str) -> str:
    """
    Escape caption text for a drawtext filter description.

    The depths are not uniform, which is the trap here. ':' ',' ';' and
    brackets are filter-syntax separators, consumed by the filtergraph parser,
    so ONE backslash is correct. '%' is interpreted by drawtext's own text
    parser one level deeper, so the filtergraph parser eats a single backslash
    first and drawtext needs to see '\\%' -- meaning TWO backslashes in the
    description. Verified against ffmpeg 9.0.2: '100\\% off' renders, '100\\% off'
    does not.

    Getting this wrong is how a "100% off" caption silently becomes a render
    failure, or worse, a wrong number on screen.

    Order matters: backslashes are escaped first so the escapes added for the
    other characters are not themselves re-escaped.
    """
    out = str(text or "")
    out = out.replace("\\", "\\\\")   # literal backslash in the caption
    out = out.replace("'", "")        # a quote would close the argument
    out = out.replace("%", "\\\\%")    # drawtext expansion token (double)
    out = out.replace(":", "\\:")
    out = out.replace(",", "\\,")
    out = out.replace(";", "\\;")
    out = out.replace("[", "\\[").replace("]", "\\]")
    out = out.replace("=", "\\=")
    return out


def _position_coords(position: str, box_w: int, box_h: int) -> tuple:
    """
    Top-left corner for a box of box_w x box_h at a named position.

    Positions are expressed in pixels against CANVAS dimensions so a caption
    lands in the same place on every clip regardless of the footage's own
    resolution.
    """
    usable_w = CANVAS_WIDTH * (1 - SAFE_MARGIN_X * 2)
    usable_h = CANVAS_HEIGHT * (1 - SAFE_MARGIN_Y * 2)

    def x_for(fraction):
        return int(CANVAS_WIDTH * SAFE_MARGIN_X + usable_w * fraction)

    def y_for(fraction):
        return int(CANVAS_HEIGHT * SAFE_MARGIN_Y + usable_h * fraction)

    presets = {
        "top": (x_for(0.5) - box_w // 2, y_for(0.0)),
        "top_left": (x_for(0.0), y_for(0.0)),
        "top_right": (x_for(1.0) - box_w, y_for(0.0)),
        "center": (x_for(0.5) - box_w // 2, y_for(0.5) - box_h // 2),
        "bottom": (x_for(0.5) - box_w // 2, y_for(1.0) - box_h),
        "bottom_left": (x_for(0.0), y_for(1.0) - box_h),
        "bottom_right": (x_for(1.0) - box_w, y_for(1.0) - box_h),
    }
    return presets.get((position or "center").lower(), presets["center"])


def _clamp_window(start, end, duration) -> tuple:
    """Clamp a timed window to the clip, keeping at least one frame."""
    try:
        s = max(0.0, float(start))
    except (TypeError, ValueError):
        s = 0.0
    try:
        e = float(end)
    except (TypeError, ValueError):
        e = s + 1.0
    if e <= s:
        e = s + 1.0
    ceiling = float(duration) if duration else e
    s = min(s, max(0.0, ceiling - 0.1))
    e = min(e, ceiling)
    if e <= s:
        e = s + 0.1
    return round(s, 3), round(e, 3)


def has_audio_stream(path) -> bool:
    """Whether a media file exposes an audio stream."""
    try:
        proc = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "a:0",
                "-show_entries", "stream=index",
                "-of", "csv=p=0", str(path),
            ],
            capture_output=True, text=True, timeout=30,
        )
    except Exception as e:
        logger.warning("ffprobe audio check failed for %s: %s", path, e)
        return False
    return bool((proc.stdout or "").strip())


def build_audio_filter(spec: dict, duration: float, first_audio_index: int, base_has_audio: bool) -> tuple:
    """
    Build deterministic audio mixing for authorized operator audio.

    Args:
        spec: {"audios": [{"path","start","end","role","gain"}]}.
        duration: base clip length in seconds.
        first_audio_index: ffmpeg input number of the first audio file.
        base_has_audio: whether input 0 exposes an audio stream.

    Returns:
        (audio_inputs, audio_graph, warnings, output_label)

    Semantics are intentionally narrow and rights-safe:

    - background: the generated clip remains primary; operator audio is a bed.
    - voiceover: generated audio is muted inside that track's window and the
      operator file becomes primary there.
    - every track is trimmed to its attached window, delayed into place, and
      padded to the base duration so the output length cannot drift.
    """
    spec = spec or {}
    duration = float(duration or 0)
    warnings: list = []
    inputs: list = []
    segments: list = []
    tracks = []

    for item in (spec.get("audios") or []):
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or "").strip()
        if not path or not Path(path).is_file():
            warnings.append(f"Audio track skipped, file not found: {path or '(no path)'}")
            continue
        role = str(item.get("role") or "background").lower()
        if role not in AUDIO_ROLES:
            warnings.append(f"Audio track skipped, unknown role: {role or '(none)'}")
            continue
        try:
            gain = float(item.get("gain", AUDIO_DEFAULT_GAINS[role]))
        except (TypeError, ValueError):
            gain = AUDIO_DEFAULT_GAINS[role]
        gain = min(max(gain, 0.0), 2.0)
        start, end = _clamp_window(item.get("start", 0), item.get("end", duration), duration)
        length = max(0.1, round(end - start, 3))
        fade = round(min(0.1, length / 2), 3)
        tracks.append({
            "path": path,
            "role": role,
            "gain": gain,
            "start": start,
            "length": length,
            "fade": fade,
        })

    if not tracks or duration <= 0:
        return [], "", warnings, ""

    for offset, track in enumerate(tracks):
        stream = first_audio_index + offset
        inputs.append(track["path"])
        label = f"aud{offset}"
        delay_ms = int(round(track["start"] * 1000))
        segments.append(
            f"[{stream}:a]atrim=0:{track['length']},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={track['fade']},"
            f"afade=t=out:st={round(track['length'] - track['fade'], 3)}:d={track['fade']},"
            f"volume={track['gain']},adelay={delay_ms}|{delay_ms},"
            f"apad=whole_dur={duration}[{label}]"
        )

    if base_has_audio:
        segments.append("[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[basea]")
        current = "basea"
    else:
        segments.append(
            f"aevalsrc=0:d={duration}:s=44100[basea]"
        )
        current = "basea"

    # Voiceover owns its window. Muting is chained one window at a time so
    # overlapping or adjacent windows combine without leaving base audio
    # audible underneath the authorized replacement.
    for offset, track in enumerate(tracks):
        if track["role"] != "voiceover":
            continue
        end = round(track["start"] + track["length"], 3)
        segments.append(
            f"[{current}]volume=0:enable='between(t,{track['start']},{end})'[basev{offset}]"
        )
        current = f"basev{offset}"

    mix_inputs = "".join([f"[{current}]"] + [f"[aud{offset}]" for offset in range(len(tracks))])
    segments.append(
        f"{mix_inputs}amix=inputs={len(tracks) + 1}:duration=first:"
        f"dropout_transition=0:normalize=0[mix]"
    )
    segments.append(
        "[mix]aresample=44100,aformat=channel_layouts=stereo,"
        f"apad=whole_dur={duration},atrim=0:{duration}[outa]"
    )
    return inputs, ";".join(segments), warnings, "outa"


def canvas_fit_chain(source_label: str, out_label: str) -> list:
    """
    Filter fragments that fit a clip onto the 1080x1920 canvas, letterboxed.

    Shared by the caption compositor and the plain-download rescale so both
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

    Used for the plain "Download MP4" path, which has no captions and so would
    otherwise hand the founder the provider's native size — 720p for Grok,
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

def build_filter_graph(spec: dict, duration: float, font_path: Optional[str] = None) -> tuple:
    """
    Build the ffmpeg filter graph for a composition spec.

    Args:
        spec: {
            "captions": [{"start","end","text","position","size","color"}],
            "images":    [{"path","start","end","position","scale","opacity","rounded"}],
            "videos":    [{"path","start","end","position","scale"}],
            "end_card":  {"start","end","text","subtext","color"},
        }
        duration: base clip length in seconds; windows are clamped to it.
        font_path: resolved font file. When None and captions or an end card
            are requested, an error is returned instead of a broken graph.

    Returns:
        (filter_graph_or_None, input_args, warnings)
        input_args are the extra -i flags the graph expects, in order.
    """
    spec = spec or {}
    warnings: list = []
    inputs: list = []
    graph: list = []

    # Escaped once and reused for every text layer in the graph.
    font_expr_path = _escape_filter_path(font_path) if font_path else ""

    duration = float(duration or 0) or None

    captions = spec.get("captions") or []
    end_card = spec.get("end_card") or None
    needs_font = bool(captions) or bool(end_card and (end_card.get("text") or end_card.get("subtext")))
    if needs_font and not font_path:
        return None, [], [
            "No usable font file found. Set OVERLAY_FONT to a .ttf path; "
            "text overlays were skipped rather than rendered wrong."
        ]

    # 0 is the base clip. Everything else is layered on top. Fitted onto the
    # canvas by the shared helper so the captioned and plain downloads agree on
    # frame size.
    graph += canvas_fit_chain("0:v", "bg0")
    current = "bg0"

    # ---- Image layers (screenshots, logos, product shots) ----
    for index, item in enumerate(spec.get("images") or []):
        path = str(item.get("path") or "").strip()
        if not path or not Path(path).is_file():
            warnings.append(f"Image layer skipped, file not found: {path or '(no path)'}")
            continue
        kind = str(item.get("kind") or "screenshot").lower()
        start, end = _clamp_window(item.get("start", 0), item.get("end", duration), duration)
        # Per-kind defaults applied HERE as well as in build_spec_from_plan, so
        # a logo is small whether the spec came from the planner or was written
        # by hand. Defaulting everything to 0.8 would blow a logo up to fill
        # the frame.
        default_scale = 0.14 if kind == "logo" else 0.8
        try:
            scale = float(item.get("scale", default_scale))
        except (TypeError, ValueError):
            scale = default_scale
        scale = min(max(scale, 0.05), 1.0)
        try:
            opacity = float(item.get("opacity", 1.0))
        except (TypeError, ValueError):
            opacity = 1.0
        opacity = min(max(opacity, 0.0), 1.0)

        target_w = int(CANVAS_WIDTH * scale)
        position = item.get("position")
        if not position:
            # A logo belongs out of the way; a screenshot is the subject.
            position = "top_right" if kind == "logo" else "center"
        box_h = int(target_w * 1.9) if kind in ("screenshot", "product_image") else int(target_w)
        pos_x, pos_y = _position_coords(position, target_w, box_h)

        inputs.append(path)
        label = f"img{index}"
        enable = f"between(t,{start},{end})"
        graph.append(
            f"[{index + 1}:v]scale={target_w}:-1,format=rgba,"
            f"colorchannelmixer=aa={opacity}[{label}]"
        )
        graph.append(
            f"[{current}][{label}]overlay={pos_x}:{pos_y}:enable='{enable}'[ov{index}]"
        )
        current = f"ov{index}"

    # ---- Video layers (screen recordings) ----
    for index, item in enumerate(spec.get("videos") or []):
        path = str(item.get("path") or "").strip()
        if not path or not Path(path).is_file():
            warnings.append(f"Video layer skipped, file not found: {path or '(no path)'}")
            continue
        start, end = _clamp_window(item.get("start", 0), item.get("end", duration), duration)
        try:
            scale = float(item.get("scale", 0.85))
        except (TypeError, ValueError):
            scale = 0.85
        scale = min(max(scale, 0.05), 1.0)
        target_w = int(CANVAS_WIDTH * scale)
        pos_x, pos_y = _position_coords(item.get("position") or "center", target_w, int(target_w * 1.9))
        enable = f"between(t,{start},{end})"
        # Declared as an ffmpeg input here, in the same order the graph
        # indexes it. A video layer referenced in the graph but never given
        # an -i fails the whole render, which would break screen recordings --
        # the main thing this feature exists to composite.
        inputs.append(path)
        graph.append(
            f"[{index + 1 + len(spec.get('images') or [])}:v]scale={target_w}:-1,format=rgba[v{index}]"
        )
        graph.append(
            f"[{current}][v{index}]overlay={pos_x}:{pos_y}:"
            f"enable='{enable}'[ovv{index}]"
        )
        current = f"ovv{index}"

    # ---- Text overlays (verified copy) ----
    for index, cap in enumerate(captions[:12]):
        text = str(cap.get("text") or "").strip()
        if not text:
            continue
        start, end = _clamp_window(cap.get("start", 0), cap.get("end", duration), duration)
        try:
            size = int(cap.get("size", 64))
        except (TypeError, ValueError):
            size = 64
        size = min(max(size, 12), 200)
        color = str(cap.get("color") or "white")
        # A dark box behind text keeps it readable over any footage.
        box = int(cap.get("box", 1))
        box_arg = (
            f":box=1:boxcolor={BRAND_DEEP}@0.55:boxborderw=18" if box else ""
        )
        font_expr = (
            f"text='{_escape_drawtext(text)}'"
            f":fontfile={font_expr_path}:fontsize={size}:fontcolor={color}{box_arg}"
        )
        # Let drawtext measure the text, so long copy cannot overflow.
        pos_x, pos_y = _caption_coords(cap.get("position") or "bottom")
        graph.append(
            f"[{current}]drawtext={font_expr}:x={pos_x}:y={pos_y}"
            f":enable='between(t,{start},{end})'[txt{index}]"
        )
        current = f"txt{index}"

    # ---- End card ----
    if end_card and (end_card.get("text") or end_card.get("subtext")):
        start, end = _clamp_window(
            end_card.get("start", max(0.0, (duration or 0) - 3)),
            end_card.get("end", duration),
            duration,
        )
        color = str(end_card.get("color") or BRAND_PRIMARY)
        draw = ""
        heading = str(end_card.get("text") or "").strip()
        subtext = str(end_card.get("subtext") or "").strip()
        if heading:
            draw += (
                f"drawtext=text='{_escape_drawtext(heading)}':fontfile={font_expr_path}"
                f":fontsize=96:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2-40"
                f":enable='between(t,{start},{end})'"
            )
        if subtext:
            draw += (
                ("," if draw else "")
                + f"drawtext=text='{_escape_drawtext(subtext)}':fontfile={font_expr_path}"
                f":fontsize=52:fontcolor=white@0.92:x=(w-text_h)/2:y=(h/2+40)"
                f":enable='between(t,{start},{end})'"
            )
        if draw:
            graph.append(f"[{current}]{draw}[endcard]")
            current = "endcard"

    graph.append(f"[{current}]format=yuv420p[outv]")
    return ";".join(graph), inputs, warnings


def build_ffmpeg_command(
    base_video: Path,
    output_path: Path,
    spec: dict,
    duration: float,
    font_path: Optional[str] = None,
) -> tuple:
    """
    Full ffmpeg argv for one composition.

    Returns (argv, warnings). Raises ValueError when the graph cannot be
    built, so the caller reports a real reason instead of running a broken
    command.
    """
    graph, inputs, warnings = build_filter_graph(spec, duration, font_path)
    if graph is None:
        raise ValueError("; ".join(warnings) or "Could not build an overlay filter graph.")
    audio_inputs, audio_graph, audio_warnings, audio_output = build_audio_filter(
        spec, duration, 1 + len(inputs), has_audio_stream(base_video)
    )
    warnings = list(warnings) + list(audio_warnings)
    if audio_graph:
        graph = f"{graph};{audio_graph}"

    image_count = len(spec.get("images") or [])
    # One thread, on purpose: per-thread decode buffers are the largest thing
    # ffmpeg allocates, and an uncapped overlay encode overlapping a save is
    # what OOM-killed the 512MB host. Same budget as every other call site.
    argv = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-threads", "1"]
    argv += ["-i", str(base_video)]
    # Each overlay input is declared exactly once, in the same order the
    # filter graph indexes them. Images are looped so a still overlay covers
    # its whole window; videos must not be looped.
    for index, path in enumerate(inputs):
        if index < image_count:
            argv += ["-loop", "1", "-t", str(int(float(duration) + 1))]
        argv += ["-i", str(path)]
    # Authorized audio inputs follow all visual overlay inputs, matching the
    # absolute indexes used by build_audio_filter.
    for path in audio_inputs:
        argv += ["-i", str(path)]
    argv += ["-filter_complex", graph, "-map", "[outv]", "-c:v", "libx264"]
    argv += ["-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p"]
    # -t pins the output to the BASE clip's length. This is not optional: a
    # looped still image keeps the filter chain producing frames long after the
    # base clip ends, and without an explicit stop the "composed" video comes
    # out minutes long. -shortest is not a substitute, because it only
    # anchors when an audio stream exists to anchor to.
    argv += ["-t", str(float(duration))]
    if audio_output:
        # Operator audio is part of the deterministic mix. Copy audio when the
        # base clip has it; overlay layers are silent.
        argv += ["-map", f"[{audio_output}]"]
    else:
        # Copy audio when the base clip has it; overlay layers are silent.
        argv += ["-map", "0:a?"]
    argv += ["-c:a", "aac", "-shortest", str(output_path)]
    return argv, warnings


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


def compose(
    base_video: Path,
    output_path: Path,
    spec: dict,
    font_path: Optional[str] = None,
    timeout: int = 600,
) -> tuple:
    """
    Render a composition with ffmpeg.

    Returns (output_path_or_None, warnings). The caller is expected to treat a
    None result as a soft failure: the un-composited clip is still a usable
    video, so losing overlays must not lose the generation.
    """
    duration = probe_duration(base_video)
    if duration <= 0:
        return None, ["Could not read the base clip's duration; overlays skipped."]

    resolved_font = font_path or resolve_font()
    try:
        argv, warnings = build_ffmpeg_command(base_video, output_path, spec, duration, resolved_font)
    except ValueError as e:
        return None, [str(e)]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, [f"Overlay render timed out after {timeout}s."]
    except FileNotFoundError as e:
        return None, [f"ffmpeg is not available: {e}"]

    if proc.returncode != 0 or not output_path.exists():
        detail = (proc.stderr or "").strip().splitlines()
        tail = detail[-1] if detail else "unknown error"
        logger.error("Overlay render failed: %s", tail)
        return None, warnings + [f"ffmpeg failed: {tail[:200]}"]

    return output_path, warnings


def describe_command(argv: list) -> str:
    """Shell-safe rendering of an ffmpeg command, for logs and debugging."""
    return " ".join(shlex.quote(str(a)) for a in argv)


def build_spec_from_plan(plan: dict) -> dict:
    """
    Turn a reviewed plan into a composition spec.

    Deliberately conservative: text comes only from the plan's already
    claim-checked overlays. No new copy is invented here, because anything
    written at this stage would never have passed the claim check.

    There is no end card, and that is structural rather than a missing feature.
    A call to action is added by the founder in their own editor, after the
    product demo they record themselves. The generated piece is a hook and a
    middle, and it is meant to stop at the moment the viewer reaches for the
    app — so a three-second card closing the file would overwrite exactly the
    frame that hands off to their footage. The `cta` and `duration` parameters
    this function used to take are gone rather than ignored: a caller passing
    them would otherwise believe it was still compositing a close.

    Face-only product: attached assets never enter the spec. The character
    reference rides to the video model as an input reference, never as an
    overlay — pasting the founder's photograph onto the footage would be a
    picture-in-picture stranger, not identity. Retired uploads are refused
    upstream before composition, so images, videos and audios are always
    empty here; the layer renderers below stay for unit-tested geometry, not
    for live traffic.
    """
    spec = {
        "captions": [],
        "images": [],
        "videos": [],
        "audios": [],
        "end_card": None,
    }

    for overlay in (plan.get("overlays") or [])[:12]:
        if not isinstance(overlay, dict):
            continue
        text = str(overlay.get("text") or "").strip()
        if not text:
            continue
        spec["captions"].append({
            "start": overlay.get("start", 0),
            "end": overlay.get("end", 0),
            "text": text[:60],
            "position": overlay.get("position") or "bottom",
            "size": 64,
            "color": "white",
        })

    return spec
