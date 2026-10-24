# 0022 — Saved looks live with saving in End Card CTA

- **Status:** accepted
- **Date:** 2026-10-26
- **Anchors:** `frontend/src/demoCta/DemoCtaEditor.jsx` (`look-save-review`,
  `look-presets-block`); `frontend/scripts/check-render-smoke.cjs`
  (look save/reuse checks)
- **Supersedes:** 0017 (partially — the apply list no longer lives in
  Source & Look)

## Context

0017 moved saving to End Card CTA but left applying in Source & Look, so
the round trip spanned two sections: save at the end, then "apply it from
Named looks in Source & Look" two stops back. The starter pills read as
placeholder content with no visible meaning, and the save confirmation
pointed elsewhere instead of at the result.

## Decision

- **The apply/delete list moves into `look-save-review`** under a "Your
  looks" sublabel: save, apply, and delete share one block at the end of
  CTA setup. Source & Look returns to footage/source controls only.
- **The save confirmation points at the list above it** ("saved above")
  instead of across sections.

## Consequences

- **Gain:** one place for the whole loop; no cross-section pointer.
- **Cost:** no start-from-a-look at the top — consistent with looks being
  finished styling, but a founder reusing a look still walks to the end.

## Alternatives considered

- **Keeping apply in Source & Look.** Rejected: the split is what made the
  pills feel disconnected and the confirmation point elsewhere.
