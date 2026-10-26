# 0037 — History band lands after the open pair, not the open card

- **Status:** superseded by 0039 (attached cards, no expand)
- **Date:** 2026-10-26
- **Partially supersedes:** 0036 (band sat directly after its card at any width)
- **Anchors:** `frontend/src/pages/GenerationHistory.jsx` (`useHistoryPairLayout`,
  `detailSlotIndex`, `history-detail-slot`); `frontend/src/index.css`
  (`.history-detail-slot`)

## Context

Pair rows (0036) put the full-width band directly after the open card. On
wide grids that split the pair: opening the first tile dropped its partner
below the band, leaving the band floating between two tiles that belong
together. On phones (one column) after-the-card is already after-the-pair,
so only the wide layout needed a new rule.

## Decision

- The list owns the band's grid slot and hands it to the open row to portal
  into. The slot sits after the whole pair on wide grids (after the card on
  phones, after the card when the open tile is the pair's second or a lone
  trailing tile).
- Placement reads the same 768px step the grid CSS lays pairs at
  (`useHistoryPairLayout`), so slot and grid can never disagree about where
  a row ends.
- The row keeps owning the band's content, state, focus, Esc, drag-tab, and
  anchors — only the slot moved, via portal, not by reordering cards. Stable
  row keys still let sorting and filtering reorder without remounting
  mid-edit.
- One band at a time, same as before.

## Alternatives rejected

- **Band after the open card at every width.** The committed 0036 behavior:
  verified to split pairs on wide grids. Correct on phones, wrong in pairs.
- **Reordering cards so the open one ends its pair.** Moves DOM order away
  from sort order; focus and typed input would not survive regrouping.
- **CSS-only (`grid-row` placement of the band).** Keeps the band as the
  card's sibling in DOM order, so it still lands mid-pair; only the slot
  element can sit elsewhere in grid order without moving the card.

## Consequences

- Wide PCs show the pair intact above its band; phones are unchanged (slot
  after the card either way).
- The band-position smoke pin asserts the slot (direct grid item) plus the
  portaled panel; a new pin opens the first tile of a pair under a stubbed
  768px step and requires the slot after the pair's second tile.
- No API contracts, filters, sorting, paging, winner rules, or band content
  change. The band holds no media, so opening it still fetches no video
  bytes.
