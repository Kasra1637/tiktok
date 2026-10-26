# 0047 — Analytics states its loaded set once; views carry recorded dates

- **Status:** accepted
- **Date:** 2026-10-26
- **Anchors:** `frontend/src/pages/Analytics.jsx` (`analytics-scope`, `analytics-status-empty`, `analytics-reason-*`, `tiktok_views_at`), `backend/server.py` (`tiktok_views_at` column, `set_generation_tiktok_views`, `_public_generation`, `generation_history`); smoke checks "analytics states its loaded set once above the cards", "empty render statuses collapse to one shared line", "clip views carry their recorded date, never a bare count", "reasons link back to the history rows behind them"; `backend/test_tiktok_views_api.py` (timestamp round-trip and clear)

## Context

The 0046 pass left four honest gaps on the Analytics page. The loaded-set
wording repeated in three places — the clip footer said "Activity below uses
this same set", the weekly card counted "across the N weeks shown", and a
feedback paragraph restated the 500-event window — so the scope read as three
answers instead of one. Empty render statuses each held a zero row, which
made "nothing here" take three lines. "Reasons you gave" listed the
founder's own codes with no way back to the row behind each one, while "What
happened" already linked every signal to its latest render. And a view count
was a bare number: two clips at 9,000 views read identically when one count
was pasted yesterday and the other a month ago, because the paste moment was
never stored.

## Decision

- **One scope line above the cards.** `analytics-scope` names the shared
  loaded set once — N most recent renders (up to 200) plus up to 500 saved
  events — and the per-card footers stop repeating it. Clip results keeps a
  ranking note, the weekly card names the same renders as above, and the
  feedback note keeps only the events-are-not-outcomes caveat.
- **Empty statuses share one collapsed line.** Filled statuses keep their
  one-open disclosures; every empty status folds into a single
  `analytics-status-empty` line ("Failed · In progress · Archived — nothing
  here") with one zero chip. No disclosure is rendered for a status with
  nothing to open.
- **Views carry their recorded date.** `generations.tiktok_views_at` is
  stamped on every set and cleared on every clear, surfaced through detail,
  list, and history serializers. Analytics renders "9,000 · Recorded Oct 25"
  beside the bar; an older count with no stamp shows no date rather than an
  invented one.
- **Reasons link like signals do.** Each reason row carries a History link
  (`analytics-reason-<code>`) to the latest render behind that code, falling
  back to the app's History when no render carries it — the same rule the
  signal timeline already follows.
- No new tokens, components, or dependencies: `SectionCard`, `FactChip`,
  existing link styles, and the `shortDate` helper already on the page.

## Alternatives rejected

- **Stamping the date on the client.** The paste happens in History and reads
  in Analytics; a client-side "today" would disagree across machines and
  could be edited. The server stamps `now_iso()` on the same write that
  stores the count, so the date and the count can never disagree.
- **Keeping per-card footers plus a header line.** Two sources for the same
  scope drift — one gets edited and the other does not. The header owns the
  scope; the cards own only what differs (ranking rule, week grouping,
  events caveat).
- **Hiding empty statuses entirely.** A ledger that only names statuses with
  rows leaves the founder guessing whether "Failed" is zero or broken. One
  shared nothing-here line keeps the zero visible without spending three
  rows on it.

## Consequences

- The page answers "what set am I looking at" once, before the first card,
  instead of three times across three footers.
- A recorded count is now a snapshot with a date, so reach comparisons read
  as snapshots from different days rather than simultaneous measurements.
- Every reason code is one click from the render it came from, matching the
  signal rows.
- The smoke suite pins the scope line, the shared empty line, the recorded
  date, and the reason links; the timestamp round-trip and clear are pinned
  in `test_tiktok_views_api.py`.
