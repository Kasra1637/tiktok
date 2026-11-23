# ADR 0282: The checklist count becomes a progress bar

Status: accepted

## Context

The Dashboard's First Video Checklist stated its progress as plain
text — "1 of 3 complete" — beside the heading. On Nov 23 2026 Kasra
ordered the first of three visual enhancements: the count drawn as a
sleek, thin indigo progress bar across the top of the checklist card,
so progress feels rewarding at a glance and pulls the founder toward
the remaining steps. No clutter: the bar adds no words, no buttons
and no new information — it draws the number that is already there.

## Decision

`FirstVideoChecklist` in `Dashboard.jsx` renders, as the card's first
element, a one-unit-high rounded track in `--indigo-10` carrying a
`--brand-indigo` fill whose width is the same `doneCount` the text
states, as a percentage of the three steps. The fill animates its
width (`transition-[width]`) so a step checking off visibly grows the
bar. The track is a real `progressbar` for assistive tech
(`aria-valuemin` 0, `aria-valuemax` the step count, `aria-valuenow`
the done count). The "X of 3 complete" text stands unchanged beside
the heading — the bar draws it, it does not replace it. The card
still removes itself when all three steps are done, exactly as
before.

A render-smoke check pins the seat and the math: with an approved
profile and no renders, the bar states 1 of 3 and its fill stands at
a third of the track.

## Consequences

The Dashboard's first card now shows progress before it is read.
Nothing else on the Dashboard changes: the steps, their links, their
done states and the hero's precedence are untouched.
