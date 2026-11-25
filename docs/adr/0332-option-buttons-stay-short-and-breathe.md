# ADR 0332: Option buttons stay short and breathe

## Status

Accepted, Nov 25 2026 — Kasra's ruling at the same live review
as ADR 0330's addendum and ADR 0331.

## Context

With every small option button wearing the resolution treatment
(ADR 0331), two faults remained. A generated place can run long
— "Calm living room with a plant beside the chair" — and as a
button label it sprawls across the row, which Kasra called
obnoxious. And the rows still sat tight: the stock small
button's padding and the 8px row gap made the controls feel
crowded rather than unified.

## Decision

- A direction button's text never exceeds 25 characters. The
  label is trimmed at a word boundary with an ellipsis; the
  full option still applies underneath — the pick stores the
  whole string, and the full text rides the button's title.
- Every thumb-pair row breathes: the row gap grows from 8px to
  12px, and every button in the row stands at least 2.5rem
  tall with 0.5rem by 1.125rem padding — one spacing language
  across camera setup, voice, location, wardrobe, tone, shape,
  hook length, and resolution, on Create and HookSnap alike.
- The app selection pill grows to match: h-10 with px-4 in
  place of h-8 with px-3.

## Consequences

Long generated places show short on their buttons while the
plan keeps the full wording. Every small option control in the
app shares one size and spacing, so a row reads the same
wherever it stands.
