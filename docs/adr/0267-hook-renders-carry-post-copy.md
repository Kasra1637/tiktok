# 0267 — Hook renders carry post copy, and paired record panels stand at one height

- **Status:** accepted
- **Date:** 2026-11-22
- **Anchors:** `backend/ai_service.py` (`generate_post_kit`),
  `backend/test_post_kit_api.py`, `backend/routers/post_kit.py`,
  `frontend/src/pages/GenerationHistory.jsx`, `frontend/scripts/check-render-smoke.cjs`

## Context

Two live History defects were reported from screenshots of a Hook + CTA render
beside a regular Create Video render.

1. **Red error on a finished hook render.** The Hook + CTA card offered
   "Generate post copy", and clicking it showed
   `Could not regenerate post copy: Post kit needs the render's approved hook
   and script.` The same guard made the kit written at completion fail
   silently, so every hook render landed kit-less. Root cause:
   `generate_post_kit` required BOTH `hook_line` and `script`, but a Hook + CTA
   project deliberately writes a hook line and no script (ADR 0244) — the hook
   is its whole spoken piece. The post kit needs the render's own words, not
   two specific columns.

2. **Ragged paired panels.** The Post copy / Plan context pair used
   `items-start` (ADR 0153), so a short slot — a kit-less Post copy, or a
   Hook + CTA Plan context with no demo brief — ended halfway down its taller
   neighbour and left the card visibly out of rhythm with the regular cards.

## Decision

- **Require the render's words, not its shape.** `generate_post_kit` now
  refuses only when the project has NEITHER a hook nor a script
  (`Post kit needs the render's approved hook or script.`). A script-less
  render is grounded in its hook line; the model context names the shape with
  `(no extended script — a short hook; the hook line above is the whole spoken
  piece)` so the caption cannot be asked to narrate a script that does not
  exist. Both kit paths benefit — the background write at completion
  (`_maybe_write_post_kit`) and the click-only regenerate — because both call
  this one generator. Wording is never gated (ADR 0119); the caption,
  hashtag, cover and length rules are unchanged.

- **Paired record panels stretch to one height.** `.history-record-sections`
  carries `items-stretch` instead of `items-start`. At the paired card
  breakpoint (ADR 0153) the two sections stand side by side at an equal
  height; with one section the grid is a single column and nothing changes.
  No content is invented to fill a short slot — a Hook + CTA Plan context
  still has no demo brief, because the demo is recorded later in Demo + CTA.

## Verification

- Two backend checks pin the new contract: a hook-only project produces a
  valid kit whose prompt names the short-hook shape; a project with neither
  hook nor script still refuses loudly.
- The render-smoke solid-section check pins `items-stretch` and the absence
  of `items-start` on the paired wrapper; the hook/regular parity check keeps
  both card shapes on the same structure.

## Consequences

Existing kit-less hook renders recover on their own: the next "Generate post
copy" click now succeeds and the error clears (`setError(null)` at the start
of the handler). New hook renders get their kit at completion like every other
render. No claim-safety or wording check is added.
