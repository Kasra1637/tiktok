# 0069 — Proceeding to build shows as momentum, never as fit

Status: accepted

## Context

Fit scores on angle and goal rows come from model ranking plus outcome
evidence (wins/flops). Selection alone never moved them — but nothing
showed that a founder actually proceeded to build from a kind, so
repeated commitment was invisible and the loop could not tell a
much-tried kind from a never-tried one. The behavior signal for this
already exists: `adopted` (ADR 0055) records picked-AND-moved-forward
per project, one row per item.

## Decision

Adoption counts ride beside the verdicts as momentum — "2 moved
forward" — appended to the same count line that carries "3 wins ·
1 flop". `goalFitScore` never reads adoptions: the badge stays
rank-only while the count line names the commitment. Verdicts stay the
strong signal, momentum the weak-positive one, and post performance
(the analytics ledger) stays the judge. Counts are keyed by kind and
objective, so they survive angle regeneration like verdicts do.

Alternatives rejected: folding adoption into the score (commitment is
not success — a much-tried kind is not a proven one); a separate
momentum badge (two badges compete; one count line reads as one
record).

## Consequences

- Moving forward is visible on the goal card without inflating fit.
- A kind with tries but no wins reads as explored, not endorsed.
- Anchor: `backend/server.py:_serialize_angle_row` (adoptions served
  with evidence); `frontend/src/lib/angleSubtitle.js:formatVerdicts`.
