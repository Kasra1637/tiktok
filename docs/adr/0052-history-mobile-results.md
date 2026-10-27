# 0052 — Compact History filters and results on mobile

- **Status:** accepted
- **Date:** 2026-10-27
- **Partially supersedes:** 0039 and 0040 (always-visible results on with-copy cards)
- **Anchors:** `frontend/src/pages/GenerationHistory.jsx` (`history-secondary-filters`, `history-compact-secondary`); `frontend/src/index.css` (mobile disclosures)

## Context

History's filter bar squeezed the desktop page title and occupied multiple rows on phones. With-copy cards also required substantial scrolling between videos because post copy and all result controls were visible at once.

## Decision

Place filters below the heading. Keep search and the copy/context selector visible, with other filters behind a mobile disclosure that indicates active filters. Keep post copy open by default and exclusive with plan context; on phones, tuck feedback and onward actions behind a separate Results & actions disclosure. Notices and repair actions remain visible, and deep links reveal the TikTok input when needed. Desktop results remain visible.

## Alternatives and consequences

Collapsing post copy by default would shorten the card further but reverse the existing product decision to lead with it. Collapsing secondary results instead adds one tap for feedback on phones while preserving the primary content and all repair actions.
