# 0039 — History rows are one attached card, no expand step

- **Status:** accepted
- **Date:** 2026-10-26
- **Supersedes:** 0009 (drawer in card), 0035 (full-width band), 0036 (pair rows), 0037 (pair-aware band)
- **Anchors:** `frontend/src/pages/GenerationHistory.jsx` (`GenerationRow` attached card, `.history-row-grid`); `frontend/src/index.css` (`.history-grid` single column, `.history-row-grid` 900px split)

## Context

The expand-then-read model kept failing the same complaint in different
clothes: a drawer inside the card made the open tile ~3x its neighbors; a
full-width band below the pair kept every collapsed tile flat but read as a
separate section from its video; pairing two tiles per row narrowed the
band without ever attaching it. Each iteration added a tab, a drag, Esc, a
footer close, focus return, and scroll-into-view rules to manage a split the
founder never asked for.

The request is explicit: the video and the rest of its content belong in one
container, video left and record right, with no expand or collapse control.
Harmony means every card has the same structure, not that closed cards hide
theirs.

## Decision

- Each render is one attached card: media left (stage + identity summary),
  record right (facts, post copy, votes, TikTok row, actions). One card per
  row on every breakpoint; the side-by-side split lives inside the card
  (stacked on phones, `minmax(300px, 380px)` + `1fr` from 900px).
- No expand state anywhere: no `openId`, no tab, no drag, no Esc, no footer
  close, no focus return. Deep links scroll to the named card and, when it
  still awaits its TikTok link, focus that input.
- Actions stay grouped by consequence (Download + Demo + CTA wide pair,
  Delete quiet beneath), unchanged from 0009/0035.

## Alternatives rejected

- **Keep the band and attach it visually.** A band that looks attached but
  mounts separately still splits keyboard order, focus, and grid structure
  from what the eye sees — the exact mismatch the screenshots kept showing.
- **Keep pairs with always-visible bands.** Two wide bands side by side
  squeeze the vote block and the TikTok row back into the cramped width
  0035 was created to escape.

## Consequences

- Every card mounts its full record: heavier DOM per page (still capped at
  one page of 50), but no interaction cost to reach any action.
- Smoke pins assert the attached layout (clip beside record, no expand
  control, single-column grid, 900px split) instead of tabs, drags, Esc,
  and collapsed-height reservations. Tour copy names the attached record.
- No API, filter, sort, paging, winner, or post-kit contracts change.
