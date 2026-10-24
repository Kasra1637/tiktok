# 0028 — Each sequence clip picks its own presentation

Status: accepted (extends 0027)

## Context

0027 fixed the delivery as base-then-upload with both soundtracks, but kept
one global view style: the second clip had no presentation of its own, and
picking a phone mode silently dropped it from preview and export. The request
corrects that: the base and the added clip each choose floating phone,
hand-held, or real video independently.

## Decision

- The base keeps the existing `viewMode` picker (first-clip style); the added
  clip gets its own `appendMode` picker with the same three options, defaulting
  to real video. The sequence exists whenever an added clip is attached,
  regardless of either mode.
- Preview and export paint each segment in its own presentation through the
  same shared painter: per-segment mode selects the hand / full-bleed / phone
  branch, with segment-local overlay timing (added-segment overlays stay
  opt-in, base default unchanged).
- Phone-only controls (backgrounds, animation, environments, hand framing)
  appear when either segment uses them; they remain shared settings applied by
  the painter per segment.
- Export always joins both blobs with the joined 48 kHz stereo AAC track
  whenever an added clip is attached; hand-view assets load when either
  segment needs them. Single-source behavior (no added clip) is byte-for-byte
  the old path.

Anchors: `frontend/src/demoCta/DemoCtaEditor.jsx` (`viewMode` / `appendMode`),
`frontend/src/demoCta/usePreviewLoop.js` (per-segment painter mode),
`frontend/src/demoCta/exportFlow.js` (unconditional join),
`frontend/scripts/check-render-smoke.cjs` (per-segment sequence test).

## Alternatives rejected

- Global style for the whole sequence: reintroduces the original complaint —
  one presentation forced on both clips.
- Separate settings per segment (own backgrounds/zooms): doubles the panel
  for a case the painter already shares; deferred until asked for.

## Consequences

Two segments can now mix presentations (e.g. full-bleed base, floating-phone
upload) in one export. Zoom locks stay timeline-keyed and shared; a lock taken
on a real-video added segment is refused because that segment uses fixed
framing.
