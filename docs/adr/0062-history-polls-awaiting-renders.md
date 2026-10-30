# 0062 — History polls its awaiting renders on its own

- **Status:** accepted
- **Date:** 2026-10-30
- **Anchors:** `frontend/src/pages/GenerationHistory.jsx` (awaiting poll effect); smoke check "History polls a still-awaiting render on its own"

## Context

A render that finished at the provider while History was open sat
"generating" until someone opened its card and pressed Check again. The
studio panel already polls an in-flight render; History left every
stranded row to a manual check, so paid renders looked unfinished for no
reason.

## Decision

- History polls only its awaiting rows (submitted/generating with no
  playable copy), every ten seconds, up to twenty rounds.
- A 429 never stops the loop — throttling is not failure. Any other error
  stops it quietly; the row keeps its manual Check button.
- A completed poll merges into the row, so the finished clip appears where
  the generating card was.

## Alternatives rejected

- **Poll every row.** Finished rows never change server-side; polling them
  burns requests for nothing. Awaiting-only keeps the loop tiny.
- **No attempt cap.** An orphaned job id would poll forever. Twenty rounds
  (~3 minutes) covers a real render tail; past that the manual Check owns it.

## Consequences

- Finishing renders land on History without interaction; stuck ones still
  surface through the existing stranded repair, unchanged.
- The smoke suite pins the self-landing clip, so a future removal of the
  loop fails the gate.
