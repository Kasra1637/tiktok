# ADR 0315: The rail wears its progress

Status: accepted

## Context

The founder asked for the Create Video wizard rail to be
"more stylish, while not competing with the buttons"
(Nov 24 2026), then refined it on a call: remove the thin
white hairline line — only the active stage's colorful line
should show; that active line shrinks to half its current
LENGTH (not thickness) and starts from the LEFT, for the
progress feel; the step percentages (25/50/75/100 and the
overall score) stay. The rail was four flat tabs on a
hairline (ADR 0298): correct and calm, but the track read
as a static white rule and progress showed only as numbers.

## Decision

The hairline is removed. In its place, the rail's only line
is its progress: a slim gradient fill on the nav's bottom
edge, stretched from the left to the rail's live score —
the same number the quarters and the end readout derive
from, so they can never disagree — easing on the app's
signature curve (no transition under reduced motion). The
active segment's underline now runs at half the segment's
length, anchored left, drawn as a background line so the
layout never shifts. The end score lifts from muted to
foreground/70 (no weight change — the type system enforces
two weights, and a gate check holds that line). Segments
keep no border, no card and no resting fill; the page's
filled shapes still belong to its action buttons alone.
(Numbered 0315, reserved for this build when ADR 0316 was
taken the same night; it lands after 0317 in the log.)

## Consequences

The rail reads as one line of progress with the current
step standing on it — stylish at the level of a line, not
a control, and quieter than any button on the page.
