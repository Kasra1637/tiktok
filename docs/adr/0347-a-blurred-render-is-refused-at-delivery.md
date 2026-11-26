# ADR 0347: A blurred render is refused at delivery

## Status

Accepted, Nov 25 2026 — Kasra's order after a finished
render reached him blurred end to end: the whole video
blurry, not just the first frame — "fix so this never
occurs."

## Context

The render's post-processing chain was audited for a blur
source — the photo defocus mask, the head trim, the canvas
upscale — and no single upstream step could be proven to
blur a whole clip; the defocus cannot reach a face through
its own mask by construction, and a sharpness guard built
on that theory failed its own test and was reverted. What
could be guaranteed regardless of cause is the delivery
side: a blurred clip can be MEASURED before it is handed
over, and a measurement does not care which step softened
it.

## Decision

When a render completes, the persist pipeline measures the
finished clip's sharpness — Laplacian variance over frames
sampled at a quarter, a half and three quarters of its
length, after every trim and the canvas rescale, before
upload (`pipeline.clip_sharpness`). The sampling runs
through the clip because the reported blur did too; a
single opening frame could neither condemn nor clear a
render. Under the floor (`pipeline.BLUR_FLOOR`, 25 —
calibrated on synthetic clips measured through the same
function: sharp ~289, the app's own downscale-then-upscale
path ~172, a wall-to-wall blur ~2), the persist returns
the refusal and `_apply_persist_outcome` writes the
generation as FAILED with the plain message and
retryable=1, instead of completing it. No automatic
re-spend: the founder's retry renders anew. A clip that
cannot be measured (no duration, no frames) is delivered
as before — a measurement failure must never strand a
finished render. A frame carrying no scene at all (a flat
color, luminance std ~0 against a blurred scene's ~62)
gives no verdict either: blur is judged only where a scene
exists to be blurred. The floor is a catastrophe gate, not
a quality judge: it refuses wall-to-wall blur and nothing
else.

## Consequences

The blurred render a founder already paid for once can
still be produced by the provider — the spend is not
recoverable — but it can no longer be DELIVERED as a
finished video; it surfaces as a named failure with a
working retry. Pinned by backend tests: sharp above the
floor, blurred below it, unmeasurable reads as no verdict,
a blurred render is refused before upload, a sharp one
delivers unchanged, and the blur outcome fails the row.
