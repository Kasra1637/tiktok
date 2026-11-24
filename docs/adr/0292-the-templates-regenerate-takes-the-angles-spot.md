# ADR 0292: The templates Regenerate takes the angles' spot

Status: accepted

## Context

On Nov 23 2026 Kasra looked at the "Tailored template for this
app" section on Audience & template: its Regenerate button sat
in the section label's own row, pushed to the right edge. The
angle list directly above it holds its Regenerate differently —
in its own block at the top-left of the section, above the rows
it refreshes. He ordered the templates' button placed in that
same other spot.

## Decision

The templates Regenerate button leaves the label's row. The
section label stands alone, and the button stands in its own
block directly under it — ghost, small, with its refresh icon —
above the shared fit notes and the cards, mirroring the
Regenerate angles block. The button itself is unchanged: same
click (a fresh tailored set for the picked goal), same disabled
state while tailoring, same title. It gains a testid
(regenerate-templates-button), and a smoke check pins the new
seat: the first element holding both the label and the button
is the section stack itself, so a shared row wrapper fails.

## Consequences

Both regenerate controls on the step now stand the same way —
alone above the set they refresh — and the section label's row
carries nothing but the label.
