# 0259 — The pop-up holds only the other ways

Status: accepted (refines ADR 0251: the pop-up's placement on the
sidebar entry and its two surviving destinations stand; the
entry's trigger arrangement and the pop-up's option set change)

## Context

ADR 0251 made the sidebar's Create Video entry a pop-up trigger
offering three ways, its own "Create Video — hook + story" way
among them. That self-entry was load-bearing: the entry itself
was a button whose only handler opened the panel, so the pop-up's
first entry was the only route from the sidebar entry to the
classic /create flow.

Kasra's ruling (Nov 21 2026, reviewing the live sidebar pop-up):
the pop-up should hold only TWO entries, not three — the
"Create Video — hook + story" self-entry goes — and each entry
should read like a normal sidebar link: one bold title with one
short explainer line under it, the shape the History link reads
in, not one long em-dash line. Removing the self-entry without
stranding the classic flow means the entry itself has to become
the /create link again.

## Decision

1. **The entry is the classic-flow link again.** In the expanded
   sidebar and the mobile drawer (both render `CreateFlowMenu`),
   the Create Video entry is NavItem's row drawn as a Link to
   /create — same rail, icon, label, hint, and the canonical
   `create-nav-link` testid the tours anchor to — so clicking the
   entry navigates to the classic flow exactly as every other
   sidebar entry navigates to its page. `aria-current` names only
   /create, the page the link itself opens; the row still stands
   visually active on the Hook + CTA page too, the pop-up's
   family rule from 0251.

2. **A separate chevron hit-area toggles the pop-up.** A small
   chevron button sits at the row's right edge: its own button,
   `aria-label` "Show other ways to create a video",
   `aria-haspopup="menu"`, `aria-expanded` tracking the panel,
   rotating while the panel stands open. The panel keeps the
   app-drawn menu's contract — Escape closes, a press outside
   closes, choosing a way closes the panel and the mobile drawer
   alike — and navigating anywhere now closes it too, a case the
   link's return creates: the founder can travel, through the
   entry itself, with the panel open.

3. **The pop-up holds exactly two ways, in sidebar-link shape.**
   - **Hook + CTA** — "Short hook, then your demo" → `/hook-cta`,
     its destination unchanged.
   - **Demo + CTA** — "Your demo and closing message" → the
     remembered draft's finishing step
     (`/create?project=<id>&step=finish`), or plain `/create`
     when no draft is remembered — the remembered-draft behavior
     is preserved exactly as 0251 built it.
   Each option is a bold title over a muted explainer, the
   NavItem text block's shape. The old options' check-mark
   column goes with the self-entry: it marked which way the
   founder was on, and with the classic way now the entry itself,
   the two remaining ways are destinations, not a current-state
   readout.

4. **The collapsed rail is untouched.** It has no room for a
   panel or a chevron, so there the entry stays the plain NavItem
   link it has always been in the rail — 0251's recorded
   limitation stands as the rail's standing behavior.

## Consequences

- The ADR 0251 smoke check is rewritten to the new contract: the
  entry links to /create, the chevron toggle carries its testid
  (`create-flow-toggle`) and aria-label, the pop-up carries
  exactly the two options with their exact titles and explainers,
  the removed testid (`create-flow-option-create`) and the three
  old em-dash wordings are asserted absent, and the
  finishing-step link construction still stands. The rewritten
  check failed on the old tree — on the removed entry's presence
  — before the change (red before green).
- Tour anchors are untouched: `create-nav-link` stays on the
  entry, now its link, and the tour-targets audit passes.
- Hook + CTA still has no sidebar link of its own (ADR 0248);
  the Dashboard keeps its Hook + CTA destination card.

## Anchors

`frontend/src/components/Sidebar.jsx` (`CreateFlowMenu`),
`frontend/scripts/check-render-smoke.cjs` (the rewritten sidebar
pop-up check).
