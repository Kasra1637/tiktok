# 0013 — Eye-catching motion catalog expansion

- **Status:** partially superseded by 0014 (picker retires underline, spotlight)
- **Date:** 2026-10-23
- **Anchors:** `frontend/src/demoCta/constants.js:42` (`ANIMATIONS`);
  `frontend/src/demoCta/constants.js:118` (`OVERLAY_ANIMS`);
  `frontend/src/demoCta/overlays.js:43` (`overlayIntro`);
  `frontend/src/demoCta/DemoCtaEditor.jsx:1421` (new background branches through
  the `meteor` branch); the Output group removal at
  `frontend/src/demoCta/DemoCtaEditor.jsx` (`SECTION_ORDER` + Advanced comment)

## Context

The motion catalogs were small and calm: six background/phone animations and
ten overlay entrances. Founders asked for more eye-catching options, and for
TikTok the hook text and the in-card end-card text to offer the same motion —
both pick from the one shared `OVERLAY_ANIMS` catalog already, so any addition
there lands on both. Separately, the Output settings group had become a static
specimen card: one upload-ready TikTok format means nothing to choose, and the
spec already rides on the Export button title and the result card.

## Decision

- **Ten new background motions** (`surge`, `embers`, `cascade`, `vortex`,
  `grid`, `comet`, `tide`, `prism`, `bloom`, `meteor`), each a branch on
  video time `t` in the preview loop, in the established style (modest
  `globalAlpha`, palette-derived gradients, `save`/`restore` pairs).
  Particles hash from their index, never `Math.random`, so the encoded export
  matches the preview.
- **Ten new overlay entrances** (`whip`, `backslide`, `slam`, `bounce`,
  `flicker`, `glitch`, `spotlight`, `wipe`, `sway`, `thud`) in `overlayIntro`,
  keeping the pure-function-of-video-time contract: flicker and glitch
  quantize overlay-local time instead of reading randomness or wall-clock.
- **Shared channels only for new entrances** (alpha, dxEm, dyEm, rise01,
  reveal01, glow01): `scale`/`wobble` are hook-only painter features, so an
  entrance built on them would not look the same on the end card.
- **Defaults unchanged** (`float`, `punch`, `rise`): existing renders and the
  long-standing-look checks do not move.
- **The Output group is removed** rather than left as a selector with one
  option. The bitrate detail line goes with it; dimensions, frame rate and
  container stay on the Export action and the result card, which is where the
  decision and the artifact are.

## Consequences

- **Gain:** sixteen background motions and twenty entrances, identical on hook
  and end card, with export fidelity by construction (same canvas paints
  preview and recording).
- **Cost:** ~250 lines of canvas branches to maintain; each new style must
  stay inside the shared channels and the determinism rule, which the logic
  gate now asserts per entrance.

## Alternatives considered

- **Per-overlay custom curves (e.g. scale entrances for the hook).**
  Rejected: the hook and end card must offer the same motion, and the end
  card painter does not read scale — the entrance would silently differ.
- **Keeping Output as an informational group.** Rejected: a fifth stop on a
  one-clip panel to restate what the Export button already says; the spec
  survives where it is acted on.
