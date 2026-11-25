# ADR 0336: One secondary button

## Status

Accepted, Nov 25 2026 — Kasra's ruling in the main chat, after
a counted audit found 19 distinct button treatments in the app
(8 variants of the shared Button, 11 more outside it).

## Context

The shared Button carried three quiet-action looks that
competed as "the secondary button": `secondary` (dark slate,
70% fill), `outline` (lighter slate, 30% fill), and `ghost`
(no fill at all). Fifty-seven call sites were split across
them, so the same kind of action wore a different button from
screen to screen. Kasra's settled structure: the indigo
primary (Default) stays for primary actions, links stay links,
and there is ONE secondary style for every secondary action —
matched to a button he could point at.

## Decision

The unified secondary is the sidebar's "Show me around"
button: a full-round pill over a hairline border and the 30%
secondary fill, with pill-studio's shadow and motion. It is
carried by a `.btn-secondary-pill` rule in index.css
(un-layered, so the pill radius beats the shared Button
sizes' corners), and the shared Button's `secondary` variant
wears it.

The `outline` and `ghost` variants are removed from the shared
Button, and all 57 of their call sites now wear `secondary` —
"Reopen this hook" among them, which Kasra confirmed did not
match Show me around and now does, through the variant it
already used.

The pick family follows the same shape: an unpicked member
wears the unified secondary, and the picked member
(thumb-selected — a verdict thumb included) takes the same
pill radius, standing out by its indigo fill and edge rather
than by a different shape. A generation wait, which wears the
secondary surface while it runs, wears the pill now too; the
busy rule's substance is unchanged.

What this does not touch: the indigo primary family (Default
and accent), `brand` (the selection surface — a state, not a
secondary action), `destructive` (the danger meaning on
delete actions), `link`, and the pick family of ADR 0334,
whose members are Buttons wearing the option treatment.

## Consequences

A new quiet action is `secondary` or it is a design change to
this record. The render-smoke suite pins the variant's
retirement at the source: outline and ghost stay out of the
shared Button, and secondary carries the pill.
