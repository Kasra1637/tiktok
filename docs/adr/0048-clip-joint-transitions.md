# 0048 — Five joint transitions between the two clips

- **Status:** accepted
- **Date:** 2026-10-26
- **Anchors:** `frontend/src/demoCta/transitions.js` (catalog, `transitionAt`), `frontend/src/demoCta/usePreviewLoop.js` (`paintJointTransition`), `frontend/src/demoCta/DemoCtaEditor.jsx` (`TransitionPicker`); jest `frontend/src/demoCta/transitions.test.js`

## Context

The appended-sequence work (0027) joins the base and the added clip with a
hard cut, and the per-clip presentation work (0028) lets each side carry its
own look — but the join itself has no vocabulary. TikTok-native joins (whip
pans, punch zooms, spins, glitches, swipe occlusions) are the most-requested
gap between what the editor produces and what trends look like.

The pipeline constrains the answer: `exportTikTok` decodes the two segments
sequentially and hands the painter one frame at a time, so the painter never
holds both clips' frames at once. Anything needing both frames on screen
together (cross-dissolves, true match-cut morphs) does not fit without
re-architecting the encode loop.

## Decision

- **Five trends, one catalog.** Whip pan, zoom punch, spin, glitch and
  swipe live in `transitions.js` with fixed durations (0.25–0.45s, a TikTok
  beat, never a linger). The catalog also carries the hard cut as `none`.
- **Single-frame post-effect in the shared painter.** Each side of the cut
  animates out/in with peak energy exactly at the join, masking it: the
  outgoing half borrows the base's tail, the incoming half the added clip's
  head. Total duration and the audio join are untouched. Because the effect
  lives in `paintFrame`, preview and export paint identically by
  construction — the same guarantee the overlay entrances keep (0007).
- **Hard cut is the default.** Existing renders stay byte-identical; the
  founder opts into motion per second clip. The picker lives in the Second
  clip group and only renders once the added clip's metadata exists, and
  picking a transition invalidates a finished export so a stale file can
  never be saved.
- **Transitions are pure functions of timeline time.** `transitionAt` and
  the deterministic per-frame hash decide everything; glitch slices use a
  seeded hash, never a dice roll, so the same timeline time always paints
  the same frame.
- No new tokens, components, dependencies, or WebGL: `TransitionPicker`
  reuses the `StylePicker` button-grid idiom and the existing `SubLabel`.

## Alternatives rejected

- **Cross-dissolve / dual-frame blending.** Needs both frames in one draw
  call; the sequential decode loop cannot provide that without buffering a
  decoded stream. Rejected for scope, not taste.
- **WebGL shader transitions.** Heavier surface for five effects Canvas 2D
  already expresses, plus a second rendering path the export would have to
  mirror. Canvas keeps one painter for both.
- **Defaulting to whip.** A motion default would silently rewrite every
  existing two-clip export. Defaults stay hard cut; trends are a choice.

## Consequences

- Two-clip exports can now carry a trend-native join with no duration,
  audio, or overlay-window changes.
- The jest suite pins the catalog, the window math (sides, progress,
  short-clip shrink), and hash determinism; any new trend only extends the
  catalog and one painter branch.
