# 0041 — Analytics results go visual: leaderboard, bars, timeline

- **Status:** partially superseded by 0046 (three-row opening, collapsible card, status disclosures)
- **Date:** 2026-10-26
- **Anchors:** `frontend/src/pages/Analytics.jsx` (`ClipResults` leaderboard, `RenderActivity` bar chart, `SignalCounts` timeline); smoke checks "clip results render a visual leaderboard with scaled view bars", "renders per week renders scaled bars", "what happened renders signals as a visual timeline"

## Context

The Analytics sections read as text ledgers: a five-column table of clip
facts, a list of week labels with counts, and a list of signal names with
counts — with two long caveat paragraphs sitting above the fold of the
results card. Reviewing reach meant reading every cell; the page looked
like an admin report, not a creator ledger.

## Decision

- Clip results become a leaderboard: rank per row (crown for the winner),
  a view bar scaled to the highest recorded count, and a vote icon beside
  the unchanged vote label. Counts, caveats, links, and row order keep
  their contracts; only presentation changes.
- Renders per week becomes a vertical bar chart: one scaled column per
  Monday-start week, count on the column, same buckets as before.
- What happened becomes a timeline: one indigo icon marker per signal
  (template, edit, regenerate, download, plan open), counts and History
  links untouched.
- Caveats and the compare guidance collapse into one "Why these numbers"
  disclosure using the shared disclosure shape (0040): the numbers stay
  one glance, the honesty stays one click away.

## Alternatives rejected

- **KPI hero strip.** Four big numbers on top add a second summary of the
  same data without making the rows themselves any more scannable.
- **Tabbed panels.** Hides results, activity, and signals behind tabs, so
  the page shows less at once — the opposite of a glanceable ledger — and
  adds state the page has never needed.
- **Thumbnails in every row.** The most visual option, but rows without a
  poster need a fallback design, and a missing image must never break the
  comparison. Deferred until posters are universal.

## Consequences

- Smoke pins keep asserting the same strings, links, and row order through
  the new markup; the three new checks pin rank, bar scale, and timeline
  markers.
- No token, API, winner-rule, or bucketing changes. The "Why these
  numbers" disclosure reuses the 0040 shape, so no new pattern enters the
  guidelines.
