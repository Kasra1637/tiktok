# 0036 — History pairs two videos per row

- **Status:** superseded by 0037 (band lands after the open pair) and 0039 (attached cards, no expand)
- **Date:** 2026-10-26
- **Partially supersedes:** 0035 (band spanned the responsive grid, not a pair)
- **Anchors:** `frontend/src/pages/GenerationHistory.jsx` (flat `paged.map`,
  stable row keys); `frontend/src/index.css` (`.history-grid` two-up)

## Context

The responsive 1/2/3-up grid plus the full-width band read as an uneven page:
at three-up each video container was narrow, so an open band towered over
stubby tiles, and the contact sheet never settled into a stable rhythm. The
band fixed the stacking, but the tiles themselves still changed personality
at every breakpoint.

## Decision

- History lays pair rows: two tiles side by side from 768px, stacked on
  phones, pairing through the grid itself with no wrapper divs. A lone
  trailing tile simply ends the last row. The open tile's band spans beneath
  its pair, as before.
- Deliberately not chunked in JSX: grouping rows into pair divs would key
  each pair from its members, so every sort, filter, or show-more regrouping
  remounts tiles — dropping focus and typed input mid-edit (caught by the
  sync pin during implementation). Stable row keys let React reorder without
  remounting.
- Each video container is wider than a three-up tile by construction, so an
  expanded pair reads as one balanced row instead of a tall panel beside
  small clips. One band at a time, same as 0035.
- Preview heights, filters, sorting, paging, and the band interior are
  untouched: this changes tiling, not the record.

## Alternatives rejected

- **Keeping 1/2/3-up with the band.** Verified live and kept as an interim,
  but the narrow-tile/tall-band imbalance is structural to three-up, not a
  spacing bug — no gutter or preview-height tweak fixes proportions.
- **Fixed pairs only on desktop.** Two layout systems (pairs mid-band, grid
  elsewhere) doubles the pins and the mental model for one page. Pairs
  everywhere with phone stacking is one rule.
- **Masonry columns.** Unchanged from 0035: reading order would run down
  columns instead of newest-first rows.

## Consequences

- Wide PCs show two wider tiles per row instead of three narrow ones; phones
  are unchanged (one stacked column either way).
- The 1/2/3-up smoke pin is replaced by a pair pin (flat tiles, two-up
  grid, no pair wrappers); the band pin scopes to the list grid again.
- No API contracts, filters, sorting, paging, winner rules, or band content
  change. The band holds no media, so opening it still fetches no video
  bytes.
