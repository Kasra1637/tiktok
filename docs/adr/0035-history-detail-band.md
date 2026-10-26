# 0035 — History detail is a full-width band below its row

- **Status:** superseded by 0039 (attached cards, no expand)
- **Date:** 2026-10-26
- **Partially supersedes:** 0009 (drawer-in-card, non-exclusive tiles)
- **Anchors:** `frontend/src/pages/GenerationHistory.jsx` (`openId`, `toggleRow`,
  `GenerationRow` fragment); `frontend/src/index.css` (`.history-detail-panel`)

## Context

The drawer lived inside its card, so an open tile grew to ~3x its neighbors
while they correctly stayed flat — the contact sheet read as one tall panel
beside stubby tiles. At the 3-up step the drawer was also squeezed into ~430px,
cramping the vote block, the TikTok row, and the wide action pair. And because
every row owned its own open state, several drawers could stack open at once,
pushing the page into a ragged run of tall cards.

## Decision

- The open row renders its detail as a sibling grid item directly after its
  card, spanning every column (`grid-column: 1 / -1`). The band lands on the
  row below the open card; collapsed tiles never change height.
- One band at a time: open state lives in the list (`openId`), so opening a
  tile closes the band elsewhere instead of stacking a second full-width row.
- Everything else keeps its contract: the tab (click/drag), Esc, footer
  Collapse, focus return on close, the deep-link TikTok focus, and the
  `#generation-` anchor all behave as before. Closing because another tile
  opened skips the focus-return, so focus stays on the newly opened tab.

## Alternatives rejected

- **Drawer stays in the card with `align-items: stretch`.** Makes every tile
  in the row as tall as the open one — the opposite of the complaint.
- **Masonry columns.** A ~5-line change, but reading order runs down columns
  instead of newest-first rows, tab order diverges from visual order, and the
  full-width items (result count, show-more, pager) need `break-inside`
  handling. The band keeps DOM order identical to visual order.
- **Capped drawer with internal scroll.** A second scrollbar inside the record
  the founder is meant to read top-to-bottom, and it fights the plain
  disclosure motion 0009 chose.

## Consequences

- Tiles are exclusive now — two renders can no longer sit open side by side
  for comparison. That is the trade: the sheet stays even, and the band gets
  the full row width the drawer never had.
- The drawer content moved out of the `[data-testid="history-card"]` subtree,
  so smoke pins reach it through `[data-testid="history-detail-panel"]`; the
  collapsed-tile leak checks are unchanged and strictly stronger.
- No API contracts, filters, sorting, paging, or winner rules change. The band
  holds no media, so opening it still fetches no video bytes.
