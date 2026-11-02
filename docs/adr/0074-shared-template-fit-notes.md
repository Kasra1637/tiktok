# 0074 — Template fit notes shared by every card are read once above them

Status: accepted (section-copy clause partially superseded by 0085)

## Context

Template cards in the wizard's template step each carried a WHY IT FITS
block with identical bullets: same goal reason, same category reason,
same angle-kind reason, same audience line, same Bounded-by claims, same
asset need. The cause was structural: the scorer reasons per factor, so
templates ranked for one angle and goal earn the same factor bullets —
and the only per-template differentiators (a feature-token hit, a
problem-tag overlap, the founder's own feedback history) rarely fired.
Two cards could show Fit 10/10 with six identical lines, leaving nothing
to choose with.

## Decision

- `recommend_templates` splits each response into per-card notes and
  section-level notes (`backend/server.py:_split_shared_notes`): a reason
  or limitation present on every visible card moves to `shared_reasons` /
  `shared_limitations` and is stripped from the cards. One card keeps
  everything — with nothing to compare against, hoisting would leave a
  bare card.
- The template step reads the shared notes once under the section eyebrow
  ("True of every template below … / Limits on every template below …");
  each card keeps only what differentiates it. Cards with no remaining
  notes render no verdict block, exactly as the existing empty-state rule.
- Shared is computed across the visible slice, not the whole table, so the
  section line describes exactly the cards beside it. The tailored filter
  is a subset of the same response, so the line stays true there too.

Alternatives rejected: deduping client-side by string intersection (the
server owns the ranking and already shapes the response; a second
implementation of the same rule would drift); deleting the shared
bullets outright (they are real evidence for the set — the goal match is
why the set exists — they just need reading once); keeping per-card
repetition with a "same on all cards" tag (tags the noise instead of
removing it).

## Consequences

- Identical cards are now a signal the set genuinely differs only in
  structure (title, outcome, shape) — and the remaining per-card lines
  are the ones worth comparing.
- Responses without shared keys (older stubs, single-card sets) render
  exactly as before; the frontend defaults both lists to empty.
- Anchor: `backend/server.py:recommend_templates`
  (`_split_shared_notes`); `frontend/src/pages/CreateVideo.jsx`
  (`templates-shared-fit`); smoke check "notes every template shares
  are read once above the cards".
