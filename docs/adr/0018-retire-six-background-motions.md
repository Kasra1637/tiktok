# 0018 — Retire six background motions from the picker

- **Status:** accepted
- **Date:** 2026-10-23
- **Anchors:** `frontend/src/demoCta/constants.js` (`ANIMATIONS`, `DEFAULTS.anim`);
  `frontend/src/demoCta/DemoCtaEditor.jsx` (background painter branches);
  `frontend/scripts/check-frontend-logic.cjs` (nine-motion gate)
- **Supersedes:** 0013 (partially — the background motion catalog, not the overlay entrances)

## Context

0013 grew the background/phone animation catalog to sixteen motions. Six of
them earned removal: Gentle Float, Breathing Pulse, Light Rays, Orbiting
Ring, Energy Surge and Light Cascade. They taxed every real choice in the
Animation picker without earning their slots.

## Decision

- **Remove `float`, `pulse`, `rays`, `orbit`, `surge` and `cascade` from
  `ANIMATIONS`** (fifteen motions → nine). The picker renders from the one
  shared catalog, so one change lands everywhere.
- **Move the default from `float` to `bloom`** (Slow Bloom, the calmest of
  what remains). `anim` is per-session UI state — it is neither persisted
  in overlay prefs nor stored in reusable looks — so there is no stored
  value to migrate; the next load simply starts on bloom.
- **Delete the six painter branches.** Unlike the retired overlay entrances
  in 0014, no persisted look or render references these ids, so keeping
  dead branches buys no back-compat.
- **Pin the removal in the logic gate** (nine with unique ids, the six ids
  absent), so a re-addition fails the build instead of slipping back.

## Consequences

- **Gain:** a tighter picker; nine motions that read as motion.
- **Cost:** a founder mid-session on a removed motion falls back to bloom
  on next load — no data loss, since the choice was never saved.

## Alternatives considered

- **Keeping the motion branches for back-compat.** Rejected: nothing
  persists the background choice, so the branches would never execute.
- **Leaving all six in.** Rejected: the picker is the product surface, and
  six never-picked options tax every real choice.
