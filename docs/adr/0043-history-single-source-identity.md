# 0043 — History identity lives once, under the clip

- **Status:** accepted
- **Date:** 2026-10-26
- **Anchors:** `frontend/src/pages/GenerationHistory.jsx` (history-summary owns identity; detail keeps `FactList` technical meta); smoke check "History shows each render as one attached card with clip beside its record"

## Context

Each History card showed its identity twice: app name, status badge, render
date, and the hook-line headline appeared once under the video
(`history-summary`) and again at the top of the record beside it (detail
header, quoted headline, date `FactChip`). The screenshot that prompted
this read as two stacked panels saying the same thing before any action.

## Decision

- The clip's identity is single-source: app name, status, date, hook line,
  and posted/views/vote results live only in `history-summary`, directly
  under the video.
- The record beside the clip drops the brand/status header, the quoted
  headline, and the date chip. It keeps what the summary does not have:
  technical `FactList` meta (model, duration, attempt, objective, template
  and script versions), plan-context disclosures, the vote, and the work
  actions.
- Smoke pins assert the split: the summary carries the headline, and the
  detail panel no longer repeats it.

## Alternatives rejected

- **Keep both copies.** Costs the tallest part of the record to restate
  what the eye just read under the clip.
- **Move identity into the record only.** Orphans the clip: a video with no
  name, date, or result under it reads as an attachment, not a render.

## Consequences

- The record starts with distinguishing context (what made this take)
  instead of restating which render this is.
- Future identity additions (new badges, result lines) go in
  `history-summary` only; the smoke pin fails if they leak into the record.
