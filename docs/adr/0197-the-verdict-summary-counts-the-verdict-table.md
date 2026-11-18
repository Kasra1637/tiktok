# ADR 0197: The verdict summary counts the verdict table, not the history page

Status: accepted

Kasra's report, open since Nov 14 2026: he marked a finished
render "This one didn't" in History, and his Nov 17 2026 History
screenshot shows the mural card carrying a "This one worked"
verdict — yet Analytics still read "No verdicts yet" and
"0 rated". The verdicts were stored and the History cards read
them back correctly; the count was the broken part.

## What the trace found

- Write: `POST /generations/{id}/verdict`
  (`backend/routers/history.py`, `set_generation_video_verdict`)
  stores one row per (generation, user) in `video_verdicts` with
  the frozen bundle (ADR 0124). Sound.
- Per-row read: `generation_history` attaches each row's
  `video_verdict` from that same table via `_video_verdicts`.
  Sound — this is why the cards showed the verdicts.
- The summary was the break: `generation_history` computed
  `verdict_summary` by summarizing **only the verdicts whose
  generations appeared in the rows that one fetch returned** —
  the current page, under the request's limit and profile scope.
  A verdict whose generation fell outside that set (an older
  render past the page, or a render under another profile while
  Analytics was scoped to one) contributed nothing, so the
  Analytics headline — which reads the summary as "verdicts so
  far" — reported zero over verdicts that exist.

## Decision

`generation_history` now aggregates the verdict table itself:
`_verdict_rows_for_summary` selects every current verdict row
for the user, joined to `generations` so the endpoint's profile
scope still applies, newest first, and `summarize_video_verdicts`
counts those. The per-row `video_verdict` attachment is
unchanged. The summary's scope is the scope the page declares
(this app, or all apps) — never the accident of pagination.

## Consequences

- A verdict recorded on any generation in scope is counted by
  Analytics even when that generation is not among the rows the
  same fetch returned; two regression tests pin this (a verdict
  beyond a `limit=1` page counts; another app's verdicts do not
  leak into a scoped summary).
- The summary query is one extra indexed read per history fetch;
  verdict counts are small (one row per judged video), so the
  join stays cheap.
- The frontend "N rated" chip in Clip results still counts the
  renders in Analytics' loaded set, which the page states plainly
  ("Everything below uses this same set"); the headline line,
  which makes the global claim, is the one now backed by the
  global count.
