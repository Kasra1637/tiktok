# ADR 0298: The rail reads as tabs, not buttons

Status: accepted

## Context

The Create Video wizard's top four segments — App Profile,
Audience & template, Review & submit, Demo + CTA — each render as
a rounded, bordered card with a filled wash on the active step.
On Nov 23 2026 Kasra sent a screenshot of the rail and ruled the
shape wrong: the segments look identical to the page's action
buttons — the Try again button, the sticky bar's navigation
buttons, Generate your plan — so the navigation competes with
the actions it is only meant to frame. His scope was exact: only
the top four segments, nothing else on the page. The audience
substep row below already speaks the app's flat nav language (no
border, no box, state carried by text color), and a smoke check
already forbids pill chrome there; the top rail was the row still
wearing it.

## Decision

The four segments lose the button costume. No border, no rounded
card, no resting fill: each segment is a flat tab — badge, label,
state line, cumulative percentage — on a hairline track under
the row. The active tab is marked the way ADR 0283 already marks
it, by the inset indigo underline at its foot and its indigo
label; a done tab keeps its filled check badge; a locked tab
keeps its lock glyph and dimming. Hover borrows the substep row's
faint indigo wash. Everything else is untouched: the segments
stay buttons for keyboard and pointer, with the same testids,
aria-labels, percentages, state lines, and the live score at the
rail's end, and the mobile treatment (badge and label only below
sm, ADR 0285) is unchanged. A smoke pin joins the substep one:
no segment may wear border or fill chrome again.

## Consequences

The page's filled, bordered shapes now belong to actions alone,
and the rail reads as what it is — where you are, not what to
press. The active step's wash (ADR 0283's indigo-6 field) goes
with the card; its underline and glow stay, so the accent ADR
0283 added survives in the flatter language.
