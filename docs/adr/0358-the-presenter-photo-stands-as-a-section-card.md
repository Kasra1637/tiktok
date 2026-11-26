# ADR 0358: On HookSnap the presenter photo stands as a section card

## Status

Accepted, Nov 25 2026 — Kasra's order at his live review of
ADR 0356: the presenter photo layout reads thinner than
Render the hook, its icon smaller and shrunk; "make sure
they're unified in spacing and padding and design", the
presenter photo updated in size and shape to match.

## Context

Every HookSnap section is a `SectionCard` — the `.surface`
card (16px radius, 20px padding rising to 28px on desktop,
the space-y-5 rhythm) under a `SectionHeading` with a 16px
glyph — except one. The presenter photo section is the
shared `PresenterPhotoControl`, whose own panel is an
`.inset-panel`: the nested-aside level (12px radius, a
flatter fill, no card shadow) under a `GroupLabel`, the
12px-glyph eyebrow for groups inside a card. On the Create
wizard that is the right level — the control sits inside a
step card, among that step's groups. On HookSnap the control
stands alone as one of the page's seven sections, so beside
its sibling cards it read thinner, smaller and shrunk —
exactly what the founder saw.

## Decision

`PresenterPhotoControl` gains a `card` flag. A caller that
passes it (HookSnap, the control's only standalone host)
gets the section card's own treatment: the outer panel
wears `surface` with the card's radius and space-y-5
rhythm, and the headline renders as a `SectionHeading`
(16px glyph) in the same heading row `SectionCard` builds.
The body — subtitle, library, collapse wrapper, every
testid — is unchanged; the collapse flag of ADR 0356 works
identically in both forms.

Callers that never pass the flag render byte-for-byte as
before. The Create wizard is such a caller, deliberately:
inside its Audience & template step card the inset panel is
the matching level — a full card nested inside the step
card is the one shape the design system forbids — and the
sequence principle itself already holds there, because the
wizard's steps open in order (paged steps, locked rail
segments) and this very section renders only once a
template is picked.

## Alternatives considered

Restyling the control globally to the surface treatment:
rejected — it would put a full card inside the Create
wizard's step card and change a page the founder did not
name.

Leaving the inset panel and only enlarging its glyph:
rejected — the founder named size, spacing, padding and
design together; the whole treatment is the fix, not the
icon alone.

## Consequences

On HookSnap all seven sections now wear one card design:
same size, spacing, padding and heading glyph, the
presenter photo included. The render-smoke suite pins the
parity (the panel carries the surface, never the inset
panel, and its heading glyph's classes equal the render
card's). The wizard's photo section is untouched.
