# ADR 0271: The Dashboard list loses Demo + CTA and says "Where to Start Next"

Status: accepted

## Context

The Dashboard's destination grid (ADR 0208's routing home) listed
seven boxes under the label "Where to next", Demo + CTA among
them. Kasra ruled on Nov 22 2026: Demo + CTA is not a place to
start — it is a finishing step a founder reaches from inside
Create Video and Hook + CTA — so its box comes off the list. He
also called the label grammatically incorrect and approved the
replacement wording: "Where to Start Next".

## Decision

**In `frontend/src/pages/Dashboard.jsx`: the Demo + CTA entry is
removed from `DESTINATIONS` (six boxes remain — Create Video,
Hook + CTA, History, Asset Library, Analytics, App Profile), and
the section label becomes "Where to Start Next".** The Demo + CTA
route and page are not touched, and the next-action hero's own
finish action still points at Demo + CTA — only the destination
list changes.

The pins move in the same commit: the Dashboard checks'
`expectGrid` now expects the six routes without `/demo-cta`, and
the dashboard tour's grid step no longer names Demo + CTA among
the places the grid jumps to. No other pin asserted the old label
or the seven-box set.

## Consequences

The Dashboard routes to six starting places under a label that
says what the section is for. Demo + CTA loses no path in: it
remains the create flow's finishing step, the hero's finish
action, and (until ADR 0273) an entry in the sidebar pop-up.
