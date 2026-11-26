# ADR 0354: An uploaded image sits still by default

## Status

Accepted, Nov 25 2026 — Kasra's order on a voice call:
images uploaded to the Demo + CTA area get a zooming
animation automatically today; the default must be NO
animation on uploaded images, the zoom becomes an
option only, and several other animation options are
added alongside it.

## Context

Uploaded images live in the Demo + CTA editor's second
slot as a sequence (ADR 0237) — a single uploaded image
is a sequence of one. ADR 0237 composed every still
with a gentle push-in across its hold, unconditionally:
`composeImageFrame` in `frontend/src/demoCta/imageSequence.js`
applied `pushInScale` to the current still and to the
crossfade's incoming still, in the preview (through the
image player) and in the export (`exportTikTok.js`)
alike. There was no stored choice and no control: a
founder who wanted a still screenshot to read as a
still could not have one, short of the system-wide
reduced-motion setting, which also cuts the joins.

## Decision

Motion is a per-image pick, stored on the sequence
entry beside its hold (`motion`, next to `seconds`),
and resolved in exactly one place — `imageMotionAt`
in `imageSequence.js` — which both the preview and the
export already compose through, so the demoCta
invariant (export matches preview, ADR 0007) holds by
construction. The catalog is None plus six animations:
**None**, **Zoom in**, **Zoom out**, **Pan right**,
**Pan left**, **Pan up**, **Pan down**. None is the
default: a fresh upload is created carrying it
(`DEFAULT_IMAGE_MOTION`), and a stored entry with no
pick — every draft saved before this decision —
resolves to None through `normalizeImageMotion`, so
old drafts open with their images still instead of
silently changing behavior the other way. Zoom in is
ADR 0237's push-in verbatim (the same ease-out cubic,
the same +8%), kept as a choice; Zoom out runs that
curve backwards and settles on the still; the four
Pans hold the push-in's overscan scale and drift one
of the frame's anchors across the hold, eased at both
ends. The crossfade's incoming still enters at its own
pick's first frame. Reduced motion still parks every
pick, as it parked the push-in.

The pick rides the document like the hold does: the
whole `appendImages` array is the draft snapshot, the
export edit key carries each entry's resolved motion
(so a changed pick retires a stale export, the way a
changed hold does), and `exportFlow.js` passes the
normalized pick into the export's image set — the one
place a field can be dropped on the way to the
encoder, now pinned by the frontend logic gate. The
control stands on each image row under its "Show for"
slider: the seven entries stand in the app-drawn
dropdown (`AppSelect`), per the app's control rule
(two or three options stand side by side as buttons;
four or more take the dropdown). Nothing generates or
changes on navigation — only the founder's pick
changes a still's motion.

## Consequences

An uploaded image now reads as the screenshot it is
unless the founder animates it on purpose, and the
six animations are per-image: a sequence can hold one
still, push into the next, and pan across a wide
screen. ADR 0237's composition contract is unchanged —
pure in sequence time, preview and export identical —
with its automatic push-in narrowed to the Zoom in
pick. Pinned by the frontend logic gate (the default
resolves to None, each pick's transform, the draft
round-trip, the editor's default-on-upload, the
export key and the export set carrying the pick) and
by the module's Jest tests (the composed frame under
each pick).
