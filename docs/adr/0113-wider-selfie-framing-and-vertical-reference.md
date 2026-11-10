# 0113 — Wider selfie framing and a vertical identity reference

- **Status:** accepted
- **Date:** 2026-11-10
- **Anchors:** `backend/generation_planning.py` (`HANDHELD_SELFIE_FRAMING`,
  `_SELFIE_CAMERA_MOVE`, floors); `backend/face_crop.py` (pads,
  `_expand_to_vertical`, `_pad_to_vertical`); `backend/ai_service.py` (strategy
  handheld paragraph); `backend/tests/test_selfie_framing.py`.

## Context

Renders came back with the forehead or chin cut off — the camera too close to
the face. Three causes stacked:

1. The handheld prompt asked for "upper chest up", a close-up, with only
   "headroom" as the margin and no named prohibition on cropping the head.
2. Processing bakes a centered 1.10x zoom into every handheld render (ADR
   0053), which crops 4.5% per edge — enough to take a close-up's small
   headroom off entirely.
3. The identity reference was a tight headshot (face ~42% of frame height) at
   a wider aspect than the 9:16 render, so on first-frame models (H3 Max,
   HeyGen) the video opened on a close-up and the provider's fit-crop cut the
   sides of the head on top of that.

## Decision

- Widen the handheld starting shot from upper-chest to mid-chest and forbid
  the crop by name: "never crop the forehead or chin". The selfie hold
  forbids tightening in both budget modes.
- Widen the face-crop pads (sides 0.6→0.9, top 1.0→1.4, bottom 0.4→0.9) and
  expand the crop box to 9:16 before cutting pixels, so the reference arrives
  vertical and no provider-side center-crop bites into the head. The
  face-dominates branch pads to 9:16 on a blurred cover-fill instead of
  returning a tight square/landscape upload as-is. Defocus still removes the
  room and garment the extra margin admits.
- Pay for the fixed text per ADR 0053: the selfie hold names the framing
  directly above it instead of restating the metre-away setup, so the full
  floor falls (4027→4019) and the condensed floor rises only by the framing
  (2238→2244). The strategy prompt carries the same never-crop rule.

## Consequences

- Handheld opens slightly wider than before; the tight-chest-up default is
  gone. Fixed camera is unchanged.
- First-frame openings start with headroom instead of a close-up; likeness is
  unchanged (the head is still returned untouched, only the margin grows).
- The saturated-prompt fit still converges with payoff/differentiation intact;
  the floors are re-pinned, not removed.

## Alternatives considered

- **Reduce or remove the 1.10x processing zoom:** rejected — the zoom is the
  hook-boundary beat (ADR 0053/0063); the failure was generation framing too
  tight to survive it, not the zoom itself.
- **Grow the fixed-text budget:** rejected — a +158 attempt pushed a realistic
  fixture past convergence and amputated payoff/differentiation; ADR 0053
  requires paying with redundancy instead.
- **Leave the reference tight and fix framing by prompt alone:** rejected —
  on first-frame models the reference IS the opening frame, so no prompt
  wording can widen an opening that starts as a close-up.
