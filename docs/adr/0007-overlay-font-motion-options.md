# 0007 — Caption/CTA overlays get selectable fonts, animations, and size

- **Status:** accepted
- **Date:** 2026-10-15
- **Anchors:** `frontend/src/demoCta/overlays.js` (`overlayIntro`, `revealLines`);
  `frontend/src/demoCta/constants.js` (`OVERLAY_FONTS`, `OVERLAY_ANIMS`);
  `frontend/public/fonts/` (11 vendored faces)

## Context

Caption and end-card text had exactly one face (Anton), one size each (derived
from canvas width), and one fixed entrance each. Founders asked for choice:
readable faces, motion options, and size control.

## Decision

- **Faces are vendored, never linked.** Canvas paints from locally available
  fonts, so every selectable face ships as a latin 400 woff2 under
  `public/fonts/` with an `@font-face` rule. 400 only: the painters request no
  bold weight. Eleven options, Anton first as the unchanged default.
- **Motion is a pure function of video time.** Each of the ten styles is
  computed from overlay-local time in `overlayIntro`, with no wall-clock read
  anywhere on the path — so the `captureStream` export matches the preview
  frame for frame. Punch and rise reproduce the two pre-existing behaviours
  formula for formula.
- **Size is a 0.7–1.3 multiplier** on the existing cw-derived sizes, so faces
  and presets keep scaling together and wrapping still contains lines inside
  the TikTok safe area.
- Unknown font ids fall back to Anton and unknown animation ids to punch;
  a missing file can never render tofu or throw on the paint path.

## Consequences

- **Gain:** founder-chosen typography and motion with export fidelity by
  construction (same canvas paints preview and recording).
- **Cost:** ~160KB of vendored faces in the repo; each new face must be added
  in three places (woff2, `@font-face`, `OVERLAY_FONTS`) or the logic check
  fails the build-gate.

## Alternatives considered

- **System font stacks, no vendoring.** Rejected: zero bytes, but rendering
  varies by device and a face missing on the founder's machine silently
  substitutes — the exact failure vendoring exists to prevent.
- **Remote webfonts.** Rejected: a blocked or slow fetch degrades the export,
  not just the page (see the constants.js header).
- **Per-overlay freeform size input.** Rejected: exact pixels can leave the
  safe area on narrow presets; the bounded multiplier cannot.
