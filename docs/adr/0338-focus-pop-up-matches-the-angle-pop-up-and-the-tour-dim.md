# ADR 0338: The Focus pop-up matches the angle pop-up, and the scrim matches the tour's full dim

## Status

Accepted, Nov 25 2026 — Kasra's rulings at the live review of
the ADR 0334–0336 round, from his screenshots.

## Context

Two mismatches in the shipped round. First, the Focus pop-up
(ADR 0334) wore a plain padded card while the angle pop-up
wears a bordered sheet with a header bar and divided rows —
side by side, the Focus pop-up read lighter and looser than
the pop-up it was patterned on. Second, ADR 0335 set the
shared pop-up scrim to the tour's backdrop value, 55% black —
but Show me around stacks that backdrop under its spotlight
ring's own 55% shadow, so the tour's screen actually sits at
just under 80% black. Kasra's screenshots show the difference:
the pop-up's dim is visibly lighter than the tour's.

## Decision

The Focus pop-up takes the angle pop-up's display exactly:
the same panel (rounded-xl, hairline border, bg-card,
shadow-lg), the same header bar (hairline bottom border,
row-pad, text-sm semibold title, plain X close), and the
options list on the same row-pad inset. The pick behavior is
unchanged.

And `.pop-scrim` now carries the tour's combined dim,
rgba(0, 0, 0, 0.8), so a pop-up darkens the screen to the
same weight Show me around does. ADR 0335's one-scrim rule
stands; only its value is corrected to the tour's full
treatment.

## Consequences

Any future pop-up matches both references: the angle pop-up's
panel display and the tour's combined dim. The render-smoke
suite's scrim pin asserts the corrected value.
