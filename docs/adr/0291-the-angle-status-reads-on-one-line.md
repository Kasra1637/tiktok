# ADR 0291: The angle status reads on one line

Status: accepted

## Context

On Nov 23 2026 Kasra looked at the Audience & template step's
angle area and pasted what he saw under the Regenerate angles
button:

"Refreshed 2d ago

Pick a goal first — regenerating aims fresh angles at it."

Two stacked lines saying two halves of one thing — when the set
was refreshed, and what regenerating will aim at. He ordered the
line not to break into two.

## Decision

The freshness line and the aim hint now stand in one wrapping
flex row under the Regenerate button, separated by a middot when
both show: "Refreshed 2d ago · Pick a goal first — regenerating
aims fresh angles at it." Either piece still renders alone when
it is the only one that applies, and neither shows while a
regeneration is running.

Nothing else moves. Both pieces keep their elements, their
testids and their exact words — the aim hint keeps its
data-subtitle marker, so the wizard subtitle budget still counts
it — and the fixed-camera indoor note below them keeps its own
line. A smoke check pins the two pieces to one shared parent.

## Consequences

The angle area's status reads as a single line of small print
instead of a stack, and the two facts keep arriving and leaving
on their own conditions exactly as before.
