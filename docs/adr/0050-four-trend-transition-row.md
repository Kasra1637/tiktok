# 0050 — Four motion trends in one transition row

- **Status:** accepted
- **Date:** 2026-10-27
- **Anchors:** `frontend/src/demoCta/transitions.js` (`TRANSITIONS`), `frontend/src/demoCta/DemoCtaEditor.jsx` (TransitionPicker `grid-cols-4`), `frontend/src/demoCta/constants.js` (`DEFAULTS.transition`); jest `frontend/src/demoCta/transitions.test.js` (catalog ids)
- **Supersedes:** 0049 (flash and fade leave the catalog they joined)

## Context

The 0048 catalog shipped a hard cut plus five motion trends; 0049 swapped
swipe for flash and fade, leaving seven picker buttons in a 3-column grid
that wrapped 3 + 3 + 1. The cut duplicated "no choice" (an untouched join
already plays straight), and the two pure overlays read as filters rather
than TikTok transitions next to the four motion trends.

## Decision

- **Hard cut, flash and fade leave the catalog.** Whip, zoom, spin and
  glitch stay, in one unstacked row of four.
- **Whip pan is the default pick,** replacing the retired cut. Saved
  `transition: "none"`, `"flash"` and `"fade"` values resolve to no window
  via `transitionDef` returning null — a straight join, never a crash.
- **Reduced motion parks everything as a cut,** which is now the only
  thing it can do: the fade exemption goes away with fade.
- `"none"` survives only as the internal cut token in
  `effectiveTransition` and the painter guard, never as a picker choice.

## Alternatives rejected

- **Keeping the cut as an explicit "no motion" option.** An unpicked join
  already plays straight, so the button restated the default and cost the
  row its fourth motion slot.
- **Keeping flash and fade as the gentle options.** They are luminance
  effects, not motion, and under reduced motion they were the only picks
  that did not park as cuts — one exemption that complicated the rule for
  two buttons nobody asked to keep.

## Consequences

- New two-clip sequences always carry motion; founders who want a straight
  join pick any trend under reduced motion, or nothing at all on an
  untouched join.
- The jest suite pins the four-trend catalog; any future swap updates the
  same single list.
