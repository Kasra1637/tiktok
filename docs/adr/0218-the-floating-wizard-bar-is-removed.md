# 0218 — The floating wizard bar is removed

Status: superseded by 0229 (Kasra reversed the removal the next day:
the bar returns, and the cross-step CTAs inside the sections are
removed instead)

## Context

The Create wizard carried three navigation layers at once: the
step-progress rail at the top, the section headers on the canvas,
and a floating pill stuck to the bottom centre of the screen — the
wizard bar (`wizard-arrows` in `frontend/src/pages/CreateVideo.jsx`),
holding a Back arrow, a forward Continue arrow, a one-line hint
naming what the step was waiting on, and a primary action slot
that mirrored the section's own unblocking button (ADR 0095
introduced the arrows; ADR 0133 gave the bar the unblocking
action; ADRs 0144/0147 scoped its Review faces; ADR 0217 took its
Back arrow off the last step).

On Nov 19 2026 Kasra looked at the Review & submit step live and
named the problem: three ways to navigate is too many. His
screenshot showed the bar's button reading "Generating your
plan · 24s" while the section's own card carried the same button
with the same countdown — the bar was a second copy of controls
the sections already owned. His order: remove the button in the
centre throughout all the steps. The top pills keep showing
progress; the sections keep carrying the actions.

Before editing, the bar's contents were inventoried per step
against the sections, and every element had an in-section owner:

- App Profile: the bar held only its arrows and hint; the step's
  work is the profile picker itself.
- Audience & template: "Generate angles" and "Generate tailored
  templates" (and their busy faces) are the angle panel's own
  `generate-angles-button` and the section's `templates-generate`
  button, same handlers, same countdowns.
- Review & submit: the plan states are the section's
  `plan-generate-button`, `plan-progress-button` (the screenshot's
  in-section "Generating your plan" button), `plan-retry-button`,
  `plan-regenerate-button` and `plan-save-button`; the strategy
  build is the strategy panel's own `strategy-build-button`; the
  render is the render panel's own `render-generate-button` with
  its in-section progress narration; the bar's "Go to render"
  shortcut duplicates the step's own Render & result tab.
- Demo + CTA: the no-render state's "Go to the render" is the
  section panel's own `finish-goto-render` button, same handler.

Navigation never depended on the bar either: the rail's segments
are buttons (`studio-progress-segment-*`, one `setStep` state
machine) and the canvas section headers walk the same way, so
every step — Demo + CTA included, once it unlocks — is reachable
without the bar's forward arrow, and a locked step still lands on
its lock banner naming the predecessor.

## Decision

1. **The wizard bar is removed on every step** — the Back arrow,
   the Continue arrow, the hint line and the action slot — with
   everything that existed only to feed it: the `footerHint`,
   `barAction`, `showContinueArrow` and `barStandsDown`
   computations in `CreateVideo.jsx`, and the panels' action
   registrations (`GenerationPanel`'s `onRenderActionChange`,
   `HookContinuityPanel`'s `onActionChange`). No dead code stays
   behind; each panel's own button keeps its handler, busy anchor
   and countdown untouched.
2. **Two layers remain, each with one job.** The rail segments
   (and, in the stacked canvas, the section headers) own step
   navigation in both directions; the sections own the actions
   and narrate their own busy states, as they already did beside
   the bar. The step task line under the title remains the one
   standing guidance line.
3. **The bar's lines go with it, unrelocated.** That includes
   Kasra's exact-words Review line, "Generate a plan above, read
   it, then render." (the bar's ADR 0190-era helper), and the
   finish step's "Render the piece first" line — the finishing
   section's own panel still names the missing render in its own
   words. Nothing is moved into a replacement element; Kasra
   ordered a removal, not a redesign.
4. **ADR 0217 is superseded.** There is no Back arrow on the
   finish step because there is no Back arrow anywhere — there
   is no bar. The bar provisions of ADRs 0095, 0133, 0144 and
   0147 retire with the element; their in-section halves stand
   (the task line under the title, the direction-change
   suggestions, the panel's ready-state invitation, the Review
   halves and their tabs).

## Alternatives rejected

- **Remove the bar only where it duplicates.** Kasra's order was
  every step; a bar that appears on some steps and not others is
  a third inconsistency, not a simplification.
- **Keep the bar but empty it of actions, as a pure hint line.**
  A floating line with no controls is the empty pill ADR 0217
  already refused, stretched across every step.
- **Keep the panels' registrations for a future surface.** Dead
  wiring with no consumer; if a surface ever needs a panel's
  action again it can register then, against a real design.

## Consequences

The wizard's bottom edge is clean on every step: progress reads
at the top, work happens in the section in view, and nothing
floats over the canvas. ADR 0169's rule — the render panel's own
Generate is the only button that submits — is now structural
rather than scoped: there is no second Generate face left. The
render smoke pins the bar's absence on every step and in every
state it used to occupy (plan flight, render flight, blocked,
finished), and its step-walking coverage rides the rail segments
the founder actually uses.
