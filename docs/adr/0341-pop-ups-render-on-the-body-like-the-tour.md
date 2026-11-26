# ADR 0341: Pop-ups render on the body, like the tour

## Status

Accepted, Nov 25 2026 — Kasra's live report, minutes after
ADR 0338 shipped: the pop-up dim still did not match Show me
around, because it did not cover the whole screen — "it
should cover the whole screen, not just any given section."

## Context

ADR 0338 matched the dim's VALUE to the tour's combined
weight (0.8), and the value was right. The coverage was not.
The tour overlay renders through a portal on the document
body, so its fixed layer answers to the viewport. The angle
pop-up and the Focus pop-up rendered their fixed layers
inline, inside the step — and a fixed element inside an
ancestor that carries a transform (the step's cards arrive
with fade-up transforms, the very trap ADR 0330 recorded) is
positioned against that ancestor, not the viewport. The dim
covered the section the pop-up sat in and left the rest of
the screen lit, exactly as Kasra's screen showed. The shared
dialog was never affected: Radix already portals it.

## Decision

The angle pop-up and the Focus pop-up render through
`createPortal` on `document.body`, exactly like the tour
overlay, and stand at the tour's own layer, z-[100]. The
shared `.pop-scrim` value is unchanged: the tour's combined
dim, rgba(0, 0, 0, 0.8) (ADR 0338).

## Consequences

A pop-up's dim now covers the whole screen by construction,
not by the accident of where the pop-up happens to be
mounted. The render-smoke suite pins both pop-ups standing
on the document body, and a source pin holds the portal in
both components. A future pop-up inherits the rule: portal
to the body, like the tour, or its dim is a section's dim.
