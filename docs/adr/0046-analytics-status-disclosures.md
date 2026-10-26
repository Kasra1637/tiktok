# 0046 — Analytics opens on three results; render statuses open their clips

- **Status:** accepted
- **Date:** 2026-10-26
- **Anchors:** `frontend/src/pages/Analytics.jsx` (`LEADERBOARD_PAGE_SIZE`, `RenderFunnel` status disclosures, `RenderActivity`, `SignalCounts`); smoke checks "a long clip leaderboard opens on three rows behind show all", "clip results collapse to their header and reopen", "a render status opens the clips behind its count"

## Context

The visual pass in 0041 made the Analytics cards *look* like a creator
ledger, but the page still opened on a ten-row table that pushed the weekly
chart and the signal timeline below the fold. The "Renders" card counted
generations by status and then stopped: the count was a dead end, so
finding which render failed meant leaving Analytics for History. The two
activity cards read flat next to it — floating bars with no scale behind
them, and timeline dots hung off a border rather than sitting on a rail.

## Decision

- **Clip results is collapsible and opens on its top three rows.** The card
  header carries the toggle; the one-line count summary stays visible when
  collapsed, and the leaderboard's own "Show all N" still expands to the
  full list. Three rows show rank order and the scale between them without
  becoming the whole page.
- **Each render status opens the clips behind its count.** A status with
  rows is a one-open disclosure: label, count, and up to six renders with
  their landing date, each linking to its History anchor. The first filled
  status is open on arrival; empty statuses stay plain rows (a disclosure
  with nothing in it is a control that cannot act).
- **The two activity containers are polished inside the existing system.**
  Week bars sit in a hairline well so the column height reads against a
  scale, counts stay `FactChip`s, and the footer states how many renders
  and weeks are shown. "What happened" gains one continuous rail, larger
  markers, full-row hover and `text-sm` labels.
- No new tokens, components or dependencies: `SectionCard`, `FactChip`,
  `Button`, `Chevron*` and the existing link styles only. The collapsed
  disclosure names no panel (`aria-controls` only while open), matching
  0040's record disclosures.

## Alternatives rejected

- **Radix Accordion for the four status rows.** A dependency and a sizeable
  surface for four rows, and the card needs one group open at a time, which
  local state already gives.
- **Collapse only the table, keeping the whole card.** The header and count
  line are the one-glance summary; hiding them too would make the collapse
  lose the answer instead of the detail.
- **Tabs for statuses.** Three of four statuses would be invisible at all
  times, which is the opposite of a ledger you scan.

## Consequences

- The cards below clip results — weekly count, signals, reasons — are now
  visible without scrolling past a ten-row table.
- Finding a failed or archived render costs one click inside Analytics
  instead of a trip to History, and the History anchor is still one click
  away when the full row (views, votes, post copy) matters.
- The smoke suite pins the three-row opening and the two new disclosures;
  the old ten-row expectation is retired as an explicit default change.
