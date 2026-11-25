# ADR 0325: HookSnap's Focus refresh is always there, as New options

Status: accepted

## Context

ADR 0320 staged the Focus outcome refresh (the Buffet,
ADR 0308): it stood only once a hook existed to steer,
or early when the stored menu was stale. On the
Nov 24 2026 call the founder opened the HookSnap page's
Focus menu — "Let the app choose" plus the outcome
lines — saw no way to regenerate them, and ruled the
staging wrong for this page: the regeneration control
belongs in the Focus area, always available. He then
sharpened its shape with a screenshot of the page's own
direction picks: it must be the "New options" link —
the small underlined text link those picks already
use — so the whole page reads as one design, "all same
unified filling and design."

## Decision

On the HookSnap surface only, the Focus refresh is
always rendered and wears the link's clothes.
`HookPicksControl` gains a `focusRefreshAsLink` prop,
which HookCta passes and no other host does:

- With the prop, the refresh renders whenever the host
  wires a handler — no has-hook, no stale-menu staging
  — in the same left-hand spot beside the Focus label
  (ADR 0308's placement stands), as a plain underlined
  text button reading "New options" ("Finding new
  options…" while it runs), class-for-class the
  direction picks' refresh link in ReviewPanels.
- The stale-menu note on this surface names the
  control the founder sees: "use New options for a
  fresh set from your profile."
- Without the prop, nothing moves: the Buffet button
  (secondary, sm, with its icon) and ADR 0320's staging
  stand exactly as built, and the control's unit pins
  for that default stay green. Create Video uses no
  HookPicksControl Focus at all, so nothing there
  changes either.

## Consequences

A founder on HookSnap can regenerate the outcome lines
whenever they want, before any hook exists, through a
control that looks like the rest of the page instead of
a lone button style. ADR 0320's reasoning — don't
invite a long refresh nobody needs yet — is superseded
for this surface by the founder's direct look at the
page; it still governs the control's default rendering
wherever the link surface is not chosen.
