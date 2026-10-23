# 0015 — The preview transport owns the playhead; Sora leaves the font catalog

- **Status:** accepted
- **Date:** 2026-10-23
- **Anchors:** `frontend/src/demoCta/DemoCtaEditor.jsx` (preview loop deps;
  transport play/pause; source-load effect);
  `frontend/src/demoCta/constants.js` (`OVERLAY_FONTS`);
  `frontend/scripts/check-render-smoke.cjs` (playhead + font-list gates)

## Context

Changing an overlay option (entrance, size, face, copy variant, end-card
timing) reset the preview to the top and forced playback, by design: the
intent was that the founder see a fresh entrance play out. In practice it
meant a founder who paused mid-clip to compare two faces lost their place on
every click, and paused audio restarted under them. Separately, the overlay
font catalog still carried Sora, a second trim of the same list that already
lost Public Sans.

## Decision

- **Option changes never move the playhead or the play state.** Every
  overlay value is already in the preview loop's dependency array, so the
  canvas redraws with the new choice on the next frame wherever the clip is
  paused. Only the transport (play/pause/seek) and the source-load effect own
  `currentTime` and playback now; pause-then-replay resumes from the same
  spot. The replay-from-top effect is deleted, and the smoke gate pins the
  new behavior (playhead stays at 4s across entrance, face, and size changes).
- **Remove `sora` from `OVERLAY_FONTS`** (ten faces → nine). The vendored
  woff2 and `@font-face` stay on disk unused; the motion branches and the
  `prefFont` fallback are untouched, so a stored Sora look falls back to the
  default face instead of breaking.

## Consequences

- **Gain:** comparing options no longer costs the founder their place; one
  fewer near-duplicate face in both font lists.
- **Cost:** a mid-clip entrance change shows its settled state, not the
  entrance playing out — the founder scrubs or replays to audition motion,
  which the transport already supports.

## Alternatives considered

- **Restart only when paused at 0.** Rejected: two behaviors for one action,
  and the play-state theft (paused → playing) was the louder complaint.
- **Removing Sora's font files too.** Rejected: churn with no user-visible
  effect; the catalog is the product surface.
