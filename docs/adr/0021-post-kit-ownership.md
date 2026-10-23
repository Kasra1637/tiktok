# 0021 — Post-kit state has one owner per layer

- **Status:** accepted
- **Date:** 2026-10-26
- **Anchors:** `backend/server.py` (`_load_post_kit_materials`);
  `frontend/src/components/PostKitSection.jsx` (internal kit state);
  `backend/ai_service.py` (`generate_post_kit` parsing)

## Context

Regeneration spread kit state across three parent idioms (a state merge in
the studio panel, a local override in the History row, a detail merge in
the modal), the server read the same two material rows in two places, and
the parser carried a branch for a shape the strict schema cannot produce.

## Decision

- **The section owns the displayed copy.** Parents pass the starting kit
  and the row id; a reloaded kit is adopted via render-phase sync, a mere
  re-render never clobbers a fresh regeneration. Adding the section to a
  new surface is one element, not a state protocol.
- **The server reads material once.** `_load_post_kit_materials` serves
  both the frozen writer and the regenerate route; the quiet-skip vs loud
  404 difference stays at the call sites.
- **No coercion in the parser.** A non-string caption fails validation
  loudly instead of being joined into copy.

## Consequences

- **Gain:** one place to change display, loading, and regeneration
  behavior respectively.
- **Cost:** none observed — behavior is unchanged, verified by the
  existing one-caption, back-compat, and regenerate suites.
