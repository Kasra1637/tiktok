# 0042 — History drops per-part ratings; one vote per render

- **Status:** accepted
- **Date:** 2026-10-26
- **Anchors:** `frontend/src/components/HistoryFeedback.jsx` (video vote only); smoke check "History offers one primary video vote and no part ratings"

## Context

Every History render carried five votes: one on the clip plus goal,
template, plan, and script behind an optional disclosure. In practice the
per-part votes duplicated the single judgment that matters — whether the
render landed — while costing the record a disclosure, four thumb pairs,
and a rated-count summary. The backend aggregates that steer generation
read the render-level verdict; part votes added weight without adding
signal.

## Decision

- History offers one vote per render: the primary video thumbs. The
  per-part disclosure, its four thumb pairs, and the rated-count summary
  are gone.
- Saved part verdicts stay stored server-side and the vote API is
  unchanged; nothing recorded is deleted, and Create Video's own review
  thumbs are untouched. Only the History surface stops asking.
- Smoke pins assert the absence (no disclosure, no part thumbs, no
  "Rate the parts" copy) and keep the video highlight, focus-scope, and
  refetch contracts.

## Alternatives rejected

- **Keep parts collapsed.** The disclosure already demoted them, but five
  votes still ask five questions where the founder has one judgment.
- **Migrate part votes into Analytics.** Moves the clutter instead of
  removing it, onto the page whose job is reading saved results, not
  casting new votes.

## Consequences

- New part verdicts stop accumulating from History; the loop learns from
  the render-level vote, the posted link, and the plan-open signal.
- The record is shorter: vote block is one question, one thumb pair, then
  the TikTok row.
