# ADR 0144: Ready-state Generate invites the click, and the sticky bar carries the render itself

Status: partially superseded by 0218 (the sticky bar carrying the render —
the wizard bar was removed; the ready-state invitation on the panel's own
Generate button stands); the bar provision is restored by 0229, with the
bar's click re-scoped to a scroll by 0169

## Context

Two Review defects Kasra named on Nov 14 2026, from his own bakery
project:

- The render was ready — strategy current, plan saved, nothing owed —
  yet "Generate the video" sat as a plain button that did nothing to
  invite the one paid click the whole step exists for.
- The sticky wizard bar's ready-state action read "Go to render" and
  only scrolled to the render section. The words promised the render;
  the click delivered a scroll, and the founder still had to find and
  press the real button. Two surfaces, two promises, one action.
- The render section itself read as attached to the long strategy
  section above it: the strategy panel and the render panel were both
  insets stacked inside the step, so "The strategy behind the piece"
  and "Render your Hook + Story" looked like one block.

## Decision

- **The ready-state Generate invites the click.** When — and only
  when — nothing holds the founder back (strategy current per
  ADR 0142, plan saved, models loaded, no render in flight, no gate
  refusing), the panel's Generate button wears the invitation: the
  play icon it already carries, plus a soft indigo glow
  (`.generate-invite`, a breathing box-shadow). Owed, blocked and busy
  states never wear it. `prefers-reduced-motion` turns it off with the
  app's other animations.
- **The bar carries the render itself in the ready state.** The panel
  registers its own Generate with the page — same words ("Generate the
  video" / "Generate another"), same play icon, same invitation —
  following the strategy panel's registration pattern (ADR 0133). The
  bar's click runs the panel's own `handleGenerate`, with the model
  and resolution chosen in the panel (they live there and nowhere
  else), and then brings the render section into view so the founder
  watches the progress where it happens. The click is an explicit
  press on a generate button — the sanctioned trigger; navigation
  still generates nothing (ADR 0122).
- **The navigation-only shortcut is a fallback, never a peer.** "Go to
  render" remains only for states where the panel cannot register a
  ready action; it never generates, and the panel's gates still
  decide. In every owed or blocked state the bar keeps its ADR 0133
  one-unblocking-action behavior unchanged.
- **The render panel is its own card.** GenerationPanel's root is a
  full `.surface` below the strategy panel, with the normal section
  gap above it (`#review-submit` carries the gap), so Review's two
  halves read as two sections. Inside the card the divider-group
  discipline stands — no new boxes in the box.

## Consequences

- One promise per surface: when the bar says "Generate the video",
  pressing it generates the video, with the settings the panel shows.
- The invitation is state, not decoration: it appears exactly when
  the click will work, and disappears the moment anything is owed —
  the same honesty rule as the hidden Generate and the owed-only
  rebuild button (ADRs 0134/0142).
- The render section's card boundary makes the Review step's two jobs
  — read the strategy, then render — visually distinct, matching how
  the step is actually worked.
