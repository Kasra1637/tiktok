# 0070 — Posted performance judges, founder verdicts nominate

Status: accepted

## Context

The loop's only reward signals were in-app approval: picks, thumbs,
builds. Momentum (ADR 0069) made commitment visible, but commitment is
not success — the app's actual objective is TikTok performance, and
views sat in the Analytics ledger without ever flowing back. The chain
existed (`generations → studio_projects → content_angles`, with
`tiktok_views` on the generation); only the feedback query never walked
it. Meanwhile counts accumulated forever: an early win compounded into
a permanent incumbent with no decay, no normalization, no exploration.

## Decision

- Posted clips join angle feedback as the strongest evidence. Only
  renders with a TikTok link count; a views-less post still counts as a
  completed post. Each clip weighs 2.0 beside thumbs inside a new
  `effective` tally read by the score — never inside wins/flops. The
  prompt names them first (`POSTED PERFORMANCE ... Strongest evidence,
  still not proof`), the UI counts them (`posted in 2 clips · 12.4k
  views`), and the fit tally counts each clip double while naming it in
  the basis (`proven in 3 posted clips`).
- Time decays the sort only. Every evidence row carries a 90-day
  half-life weight; the top-five ranking sorts by decayed weight while
  the displayed counts stay exact. Old wins retire instead of ruling
  forever.
- Thumbs stay the nomination signal, momentum the weak-positive one.
  Verdicts name the founder's intent, momentum names commitment,
  posted performance names the audience. Three labeled signals, one
  honest ordering: audience > verdict > commitment.

Alternatives rejected: folding posted clips into wins (a view count is
not a founder's judgment — mixing them would corrupt both meanings);
decaying the displayed counts (the display must never lie about what
happened); a separate performance badge (two badges compete — one
count line reads as one record, ADR 0069's rule).

## Consequences

- A kind with tries but no posts reads as explored; a kind with watched
  clips reads as proven. The loop steers toward what audiences watch,
  corrected from what founders merely like.
- `POSTED_CLIP_WEIGHT` and `OUTCOME_HALF_LIFE_DAYS` are reasoned
  constants, not measured ones — the calibration pass that measures
  them against outcomes is still open.
- Anchor: `backend/feedback.py:summarize_angle_feedback` (posted_rows,
  `_decay_weight`); `backend/server.py:_angle_feedback_for_profile`
  (posted join); `frontend/src/lib/angleSubtitle.js:formatVerdicts,
  goalFitScore`.
