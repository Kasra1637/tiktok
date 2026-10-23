# 0014 — Retire underline and spotlight from the entrance picker

- **Status:** accepted
- **Date:** 2026-10-23
- **Anchors:** `frontend/src/demoCta/constants.js` (`OVERLAY_ANIMS`);
  `frontend/src/demoCta/overlays.js` (`overlayIntro` keeps both branches);
  `frontend/scripts/check-frontend-logic.cjs` (eighteen-entrance gate)
- **Supersedes:** 0013 (partially — the picker, not the motion)

## Context

0013 expanded the shared overlay entrance catalog to twenty, hook and end
card picking from the same `OVERLAY_ANIMS`. Two of them earned removal:
`underline draw` reads as a text-decoration state rather than an entrance,
and `spotlight` washes out the small overlay type it should be selling.
Both sat in the customize-animation grids as options founders skipped over.

## Decision

- **Remove `underline` and `spotlight` from `OVERLAY_ANIMS`** (twenty
  entrances → eighteen). Both grids render through the one shared
  `EntranceGrid`, so one catalog change lands on hook and end card together.
- **Keep both branches in `overlayIntro`.** Old renders and remembered looks
  that already use them must still paint; the determinism gate keeps
  asserting them as back-compat coverage, and `prefAnim` falls stored values
  back to the defaults.
- **Pin the removal in the logic gate** (eighteen with unique ids, neither
  id present), so a re-addition fails the build instead of slipping back.

## Consequences

- **Gain:** a tighter picker; every remaining entrance reads as motion.
- **Cost:** founders with a saved `underline`/`spotlight` look fall back to
  the default entrance on next load — no data loss, but a visible change.

## Alternatives considered

- **Removing the motion branches too.** Rejected: it would break playback of
  already-exported looks for zero picker benefit.
- **Leaving both in.** Rejected: the picker is the product surface, and two
  never-picked options tax every real choice.
