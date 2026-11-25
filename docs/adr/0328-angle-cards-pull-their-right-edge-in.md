# 0328 — The angle cards pull their right edge in

Status: accepted. Kasra's report and ruling on the Nov 24 2026 call:
one section at a time, this one first; the section's width stays as
is — the fix comes from inside the cards.

## Context

Kasra's screenshot of Create Video's Audience & template step: the
four angle rows in the Audience angle panel each stretched the
panel's full width, but a row's content is short — a check, a title,
a Fit pill, a chevron. The title stood at the left and the pill and
chevron were pushed to the far right by the title's `flex-1`, leaving
a wide dead stretch across the right of every card. His words: "to
the right of those cards and containers there's so much spacing all
over" — a complaint he raised about the app's sections generally,
with this section named as the first to fix and the pattern to judge
the rest by.

He considered narrowing the whole section and ruled it out: the
section keeps its width; the cards are fixed from inside.

## Decision

- **The angle cards stand two-up from `lg`.** The four cards move
  into a grid (`grid-cols-1 lg:grid-cols-2`, `items-start`, the
  list's existing 16px gap) — the same two-up rule the step's own
  template cards already follow, and the grid the design guidelines
  already name as the angle list's sibling rule for framed picks.
  Each card's right edge pulls in to half the panel, and `items-start`
  keeps each card at its own height, so a picked card's open spec
  sheet never stretches its row-mate. Below `lg` the single stack
  stands, unchanged.
- **The Fit pill annotates the title, not the row's edge.** The title
  span drops `flex-1`; the pill follows the title directly, the way
  the goal cards' badge rides their title line. Only the chevron —
  the row's expand affordance — stands at the right edge, via
  `ml-auto`. The dead stretch between the title's end and the score
  is gone at every width, phone included.
- **The row's right padding pulls in.** A scoped `.angle-option-row`
  class in `index.css` sets the angle rows' right padding to 12px
  against the shared `.row-pad` rhythm's 16px, so the chevron sits
  flush with its card. `.row-pad` itself is untouched — it is shared
  with the Profile Detail accordion bars and the Demo + CTA group
  headers — and no `p-*` utility was added to card JSX.
- **Nothing else in the section moves.** The panel, its padding
  token, the Regenerate angles header and freshness note, the goal
  and template sections below, and every behavior — selection,
  expand/collapse, the Fit score, regeneration — are exactly as
  they were. The step card's and panel's shared gutters stay: they
  are the step's one padding rhythm, and the dead space was never
  in the gutter — it was the full-width row.

## Consequences

- On wide screens the four angles read as two pairs of framed picks,
  comparable at a glance, with the score beside the name it scores.
- A picked angle's spec sheet opens inside a half-width card; its
  label/value rows stack the way the shared spec-sheet row already
  stacks at narrow widths.
- Pin: one new render-smoke check ("the angle cards pull their
  right edge in") asserts the two-up own-height grid, the
  pulled-in row class, a title with no `flex-1`, the pill's document
  order between title and chevron, and the chevron's `ml-auto`. It
  failed before the change.
- The remaining sections Kasra flagged stay untouched until he
  judges this one — one section at a time, as ordered.
