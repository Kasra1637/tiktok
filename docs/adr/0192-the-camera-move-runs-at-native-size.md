# ADR 0192: The camera move runs at native size, before the one canvas encode

Status: accepted

Takes the speed lever ADR 0179 left open, at the founder's
direction. Kasra's order, Nov 17 2026: a finished 480p
HeyGen render sat at "Saving your finished video" for ten
minutes before the video appeared — the long-save notice
ADR 0179 added told the truth, but the wait itself is the
problem. His standard: a video should complete in a matter
of minutes. And his pushback when told the reorder should
help: measure every step first, fix whichever steps
actually cost minutes, and report any step that cannot be
brought down without hurting the video, with its number
attached.

## What the measurement found

One representative clip (15s, 480×854, 30fps, with audio —
the stuck render's own shape), timed step by step through
the pipeline's own helpers on this box class, hook 3s so
the zoom starts at 2.1s:

| Step | As it ran | Measured |
| --- | --- | --- |
| Head trim (0.2s, ADR 0181) | first | 3.2s |
| Canvas rescale (preset medium) | second | 29.5s |
| Camera move (geq at 1080×1920) | last | **553.7s** |
| **Whole save** | | **586.5s** |

The 586.5s is the founder's ten minutes, reproduced. One
step was the wait: the camera move's per-pixel geq remap,
run on the upscaled canvas — five times the pixels the
provider delivered (2,073,600 against 409,760 per frame).

| Step, reordered | Measured |
| --- | --- |
| Camera move at native 480×854 (medium) | 106.4s |
| Camera move at native 480×854 (veryfast) | 109.2s |
| Canvas rescale at medium | 39.7s |
| Canvas rescale at veryfast | 18.0s |
| Hook trim to 12s (when a provider overshoots) | 5.5s |
| **Whole save, reordered + veryfast rescale** | **116.0s** |

The last row is the shipped pipeline run end to end through
its own helpers (head trim 3.2s, move at native 100.2s,
rescale 12.5s), landing at 14.805s of finished video on the
1080×1920 canvas — the 15s render minus the 0.2s head cut,
at the platform's size.

## Decision

- **Order: head trim → hook trim → camera move → canvas
  rescale.** The move runs at the clip's native resolution;
  the rescale is the pipeline's only encode at canvas size
  and runs last. `build_camera_move_command` is
  byte-identical — the geq's coordinates are built from the
  frame's own W/H, so the zoom's geometry (centered, 1.10x
  total, 0.6s smoothstep ramp from 70% of the hook) is the
  same at any size. What changes is which pixels the zoom
  samples: it now samples the provider's native pixels, and
  the single upscale that follows carries them to the
  canvas. Final pixels therefore differ slightly from the
  old order (which zoomed an already-upscaled frame); the
  delivered canvas is unchanged at 1080×1920.
- **The exception that keeps the invariant:** a render that
  arrives ABOVE the canvas still rescales first, as it used
  to, so the geq never runs on more pixels than the canvas
  either way. Every current provider renders below the
  canvas; this is for the one that someday doesn't.
- **The move's own size guard is removed.** `apply_camera_
  move_sync` refused clips smaller than the canvas, on the
  recorded belief that its crop window was the canvas. The
  graph has no crop: with magnification ≥ 1 the inverse map
  samples a centered window inside the same frame, at any
  resolution. Left in place, the guard would have made the
  reorder silently strip the zoom from every sub-canvas
  render — exactly the renders this fix exists to speed up.
  A test now pins that a 720×1280 clip's move is attempted,
  and a real-encode test lands the move at 480×854.
- **The rescale encodes at veryfast, not medium.** The
  scale resamples and adds no detail (canvas_fit_chain's
  own recorded position), so the slower preset's extra
  analysis buys nothing a viewer can see on an upscale; it
  measured 39.7s against veryfast's 18.0s. CRF stays 20;
  the trims already encode at veryfast. The camera move's
  preset stays medium — measured, it makes no difference
  there (106.4s vs 109.2s), because the geq's per-pixel
  evaluation is the cost, not the encode.
- **Everything soft stays soft.** A failed move or rescale
  still delivers the clip, in either order; the
  fresh-download-only rule and the ADR 0181 head trim are
  untouched; a test pins the new order (move invoked before
  rescale) through the persist function's existing seams.

## The step that cannot come down further, with its number

The camera move at native size is 100.2s of the remaining
116.0s, and within the standing guardrails it does not go
lower: the geq expression is pixel-exact by recorded
decision (ADR 0179), every ffmpeg call is single-threaded
by the box's OOM rule, and the preset lever measured flat.
Merging the move and the rescale into one pass was
considered and rejected: it would save only the small
intermediate encode (~10s) while fusing two independent
soft failures into one. What would actually cut the 100s
— a cheaper zoom graph, or threaded ffmpeg — changes the
pixels or the box's memory contract, and is the founder's
call to make explicitly, not this fix's to take quietly.

## Consequences

The save of a 15s 480p render goes from ~9.8 minutes to
~1.9 minutes on this box class — a 5.1× improvement, and
inside the founder's "matter of minutes" standard. The
long-save notice (ADR 0179) will now rarely be seen, and
when it is, it is still true. The plain Download MP4 path
shares `build_upscale_command`, so downloads rescale at
veryfast too — same canvas, same CRF, faster file.
