# 0049 — Flash and fade replace swipe in the joint-transition catalog

- **Status:** superseded by 0050
- **Date:** 2026-10-26
- **Anchors:** `frontend/src/demoCta/transitions.js` (`TRANSITIONS`), `frontend/src/demoCta/usePreviewLoop.js` (`paintJointTransition` flash/fade branches); jest `frontend/src/demoCta/transitions.test.js` (catalog ids)

## Context

The 0048 catalog shipped six options: hard cut plus whip, zoom, spin,
glitch and swipe. Swipe's traveling panel was the most complex branch in
the painter and the least TikTok-native of the five — the trends that read
instantly on the platform are the strobe (flash) and the dip to black
(fade), both single-overlay effects with no geometry to mistime.

## Decision

- **Swipe leaves the catalog; flash and fade join it.** Whip, zoom, spin
  and glitch are untouched. The picker now reads: hard cut (default),
  whip, zoom, spin, glitch, flash, fade.
- **Both are pure overlays, no frame motion.** Flash peaks a white strobe
  at the cut; fade peaks near-black. The frame beneath never moves, so the
  two new branches are the simplest in the painter and cannot drift out of
  alignment the way a traveling edge could.
- Hard cut stays the default off-state: removing it would force motion onto
  every existing two-clip export, which 0048 already decided against.

## Alternatives rejected

- **Keeping swipe alongside the two newcomers.** Eight options for a join
  nobody previews until they pick one; the weakest trend leaves so the
  grid stays scannable.
- **A cross-dissolve instead of fade.** Needs both frames at once, which
  the sequential decode loop cannot provide (see 0048). Dip-to-black is
  the dissolve this pipeline can actually paint.

## Consequences

- Saved `transition: "swipe"` values (only weeks old, pre-release) fall
  back to no window via `transitionDef` returning null — a hard cut,
  never a crash.
- The jest suite pins the new catalog ids; any future swap updates the
  same single list.
