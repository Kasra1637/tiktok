# 0024 — Retire outline, clean and sticker from the text-style picker

- **Status:** accepted
- **Date:** 2026-10-24
- **Anchors:** `frontend/src/demoCta/constants.js` (`TEXT_STYLES`);
  `frontend/src/demoCta/overlays.js` (`textStylePaint`);
  `frontend/scripts/check-frontend-logic.cjs` (three-style gate)
- **Supersedes:** 0023 (partially — the text-style catalog, not the shared-treatment architecture)

## Context

0023 put six text treatments in one picker: Signature, Outline, Highlight,
Clean, Glow and Sticker. Three of them earned removal: Outline, Clean and
Sticker. They taxed every real choice in the Text style picker without
earning their slots.

## Decision

- **Remove `outline`, `clean` and `sticker` from `TEXT_STYLES`** (six
  styles → three). The picker renders from the one shared catalog, so one
  change lands on hook, story and end card.
- **Delete the three painter branches.** Unlike the retired overlay
  entrances in 0014, no render depends on these recipes: `textStylePaint`
  falls back to signature for unknown ids, and the taste layer validates
  stored prefs against the catalog, so a stale stored `clean` renders the
  signature look on next load — no migration, no blank text.
- **The default stays `signature`**, and every builtin look already uses
  it, so nothing already made moves.
- **Pin the removal in the logic gate** (three with unique ids, the three
  ids absent), so a re-addition fails the build instead of slipping back.

## Consequences

- **Gain:** a tighter picker; three treatments that read as treatments.
- **Cost:** a founder with a stored `outline`, `clean` or `sticker`
  preference falls back to signature — the long-standing look, not a blank.

## Alternatives considered

- **Keeping the painter branches for back-compat.** Rejected: the
  signature fallback already covers stale values, so the branches would
  never execute through the picker.
- **Leaving all six in.** Rejected: the picker is the product surface, and
  three never-picked options tax every real choice.
