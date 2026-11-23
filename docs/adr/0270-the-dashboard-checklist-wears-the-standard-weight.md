# ADR 0270: The Dashboard checklist wears the standard weight

Status: accepted

## Context

ADR 0268 left the "workspace enforces 4 sizes x 2 weights" guard
red on purpose over exactly one offender: the Dashboard
first-video checklist's progress label ("{doneCount} of
{steps.length} complete") carried `font-medium` — a weight the
workspace rule (font-normal / font-semibold only) bans, and the
only `font-medium` left in product JSX. Everything around it,
including the checklist's own step badges, already wore
font-semibold.

Kasra ruled on Nov 22 2026: similar elements must be unified
throughout the app, and this line is to be fixed to font-semibold
— brought into line with the rest, not blessed in the checker.

## Decision

**One class changes in `frontend/src/pages/Dashboard.jsx`: the
checklist progress label's `font-medium` becomes `font-semibold`.**
Nothing else in the file changes in this commit, and the guard
check itself is untouched.

## Consequences

The weights guard is green, and with ADR 0269 both of ADR 0268's
deliberate findings are now resolved — one in the copy, one in
the product — with neither guard weakened. The workspace stands
at 4 sizes × 2 weights with no exceptions in product JSX.
