# ADR 0273: The sidebar pop-up loses Demo + CTA

Status: accepted (refines ADR 0259)

## Context

ADR 0259 settled the Create Video sidebar entry as the
classic-flow link itself, with a chevron toggling a pop-up of the
two other ways: Hook + CTA and Demo + CTA (the latter to the
remembered draft's finishing step). Kasra ordered on Nov 22 2026
that the pop-up lose its Demo + CTA entry — the same reasoning as
ADR 0271's Dashboard removal: Demo + CTA is a finishing step,
reached from inside Create Video and Hook + CTA, not a way a
founder starts.

## Decision

**In `frontend/src/components/Sidebar.jsx` (`CreateFlowMenu`),
the pop-up's Demo + CTA entry is removed**, with the
remembered-draft finishing-step link it was the only builder of
(`demoHref`) and the draft subscription that fed it. The Create
Video link itself, the chevron toggle, and the Hook + CTA entry
are unchanged: the pop-up now holds exactly one entry, reading as
it always did — one bold title, one short explainer. The Demo +
CTA route and page are not touched.

The ADR 0259 smoke check moves in the same commit to the
one-entry contract: Hook + CTA required, the Demo + CTA testid,
explainer, and finishing-step link asserted absent, and the
check renamed for the one other way.

## Consequences

The sidebar offers two doors into creation — Create Video itself
and, one chevron away, Hook + CTA — and Demo + CTA is reached
only where it belongs: at the end of a flow, or from the
next-action hero's finish action. ADR 0259's arrangement stands
otherwise: the entry is the link, the chevron is its own button,
and the collapsed rail is untouched.
