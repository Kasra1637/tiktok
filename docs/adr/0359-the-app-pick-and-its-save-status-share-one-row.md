# ADR 0359: The app pick and its save status share one row

## Status

Accepted, Nov 25 2026 — Kasra's question at his live review
of the shipped HookSnap page, over his screenshot of the
Choose an app card: "How do we fix the fucking spacing in
this area?"

## Context

The Choose an app card held four stacked rows for one small
job: the heading, the subtitle, the app picker pill, and —
alone on its own row, under the card's wider space-y-5
rhythm while the rows above it sat in the inner block's
space-y-4 — the autosave status, a whisper of text ("All
changes saved") taking a full row of height. The card's
shell and padding are the shared `.surface` tokens every
section wears, and they stay; what read as broken spacing
was the inside: two rhythms in one card and a status row
the content did not earn, spreading a one-control section
across the full card height.

## Decision

The pick and its save status share one row: the status
paragraph moves into a flex row beside the `AppPicker`,
wrapping under it when the width runs out. Its testid,
role and wording are unchanged — only its seat moves. The
card keeps the shared shell, padding and rhythm, unified
with its sibling sections (ADR 0358's ruling); the
unapproved-profiles panel below keeps its place.

## Alternatives considered

Tightening this card's shell (a compact surface, smaller
padding): rejected — it would break the one card design
the founder had just ordered unified across the page, to
fix a problem that lives inside the card, not in its
shell.

Dropping the save status from the card: rejected — the
status is the founder's only word that a pick was saved;
it earns a seat beside the pick, not removal.

## Consequences

The Choose an app card reads as three rows — heading,
subtitle, pick with its status beside it — and hugs its
content at the same padding as every other section. The
suite's save-status reads resolve the same element in its
new seat; nothing else on the page moves.
