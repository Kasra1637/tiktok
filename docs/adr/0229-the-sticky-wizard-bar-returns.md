# 0229 — The sticky wizard bar returns; sections stop jumping steps

Status: accepted (supersedes 0218; restores 0217 and the bar provisions
of 0095, 0133, 0144 and 0147 as scoped by 0147/0169)

## Context

ADR 0218 removed the wizard's floating bar on Nov 19 2026, on an
order framed as "three navigation layers are too many." On
Nov 20 2026 Kasra reversed that ruling: the removal was not what
he had ordered in the way it was framed to him, and living with
the result made the cost plain — with the bar gone, the sections
had grown their own ways of moving the founder between steps,
and those in-section jumps are what he named and rejected. His
screenshot showed the angle-regeneration notice on Audience &
template carrying a "Go to Review and rebuild" button; the same
pattern stood across the wizard: first-gap buttons on Review &
submit that jump to whichever step is missing something, a
"Go to the render" button on the finishing step, the render
panel's cross-step remedies and its in-wizard "Open in Demo +
CTA", and the photo panel's "Add your photo" jump.

His ruling: the bar comes back with its buttons, restored as it
was immediately before the removal — and the cross-step CTA
buttons inside the pages' main container come out. Navigation
is the four top tabs plus the sticky bar, nothing else.

## Decision

1. **The bar returns, faithfully restored.** The sticky
   bottom-centre pill (`wizard-arrows` in
   `frontend/src/pages/CreateVideo.jsx`) is back with its Back
   arrow, Continue arrow, hint line and primary action slot, in
   the same placement with the same behavior, together with
   everything that existed only to feed it: the `footerHint`,
   `barAction`, `showContinueArrow` and `barStandsDown`
   computations, and the panels' action registrations
   (`HookContinuityPanel`'s `onActionChange`,
   `GenerationPanel`'s `onRenderActionChange`). ADR 0217 is
   back in force with it: no Back arrow on the finish step, and
   the bar stands down there when a finished render leaves it
   nothing to carry. The bar navigates and scrolls; it does not
   submit — ADR 0169 stands: on the render half the bar wears
   the registered Generate's face and its click only scrolls to
   the render section, whose own Generate is the only button
   that submits.
2. **Sections keep only their own actions.** The cross-step CTA
   buttons inside the main container are removed:
   the angle-regeneration notice's "Go to Review and rebuild"
   (the notice renders its sentence and keeps its Dismiss, per
   the ADR 0207 pattern); the first-gap jump buttons on Review
   & submit (`plan-first-gap-button`, `goto-first-gap-button`,
   `hook-first-gap-button`) and the render half's angle gate
   that hosted a second angle selector; the finishing step's
   "Go to the render" (`finish-goto-render` — the bar's own
   finish action carries that move); the render panel's
   cross-step remedies (`goto-angle`, `goto-photo` — its
   same-step remedies, rebuild and save, stay) and its
   in-wizard "Open in Demo + CTA" (the block renders only on
   standalone mounts, with its route link); and the photo
   requirement panel's "Add your photo" jump.
3. **A gap is named in words, never jumped to.** Where a removed
   button named the first missing choice, the panel now renders
   that same label as a sentence (`first-gap-name`): the
   plan-failed panel, the still-missing panel, and the render
   half's two gates. The words are unchanged; only the walking
   moved — to the rail segments and the bar, which is where
   Kasra's model puts it.
4. **The navigation model is two layers, each with one job.**
   The four top tabs (the rail segments, and the section
   headers in the stacked canvas) and the sticky bar move the
   user between steps; each section's own buttons run that
   section's actions and generations, and nothing inside a
   section moves the user to another step.

## Alternatives rejected

- **Keep the bar out and keep the in-section jumps.** That is
  the state Kasra rejected: the jumps are the problem he named,
  and the bar's absence is what made sections grow them.
- **Restore the bar and keep the jumps too.** Two competing
  ways to reach the same step from the same screen — the
  competing-duplicate pattern the one-naming rule exists to
  prevent, now at navigation scale.

## Consequences

ADR 0218 is superseded. The render smoke pins the bar's
presence on the wizard steps in the states it used to occupy
(plan flight, render flight, blocked, finished, the finish
step's stand-down), the removed CTAs' absence, and the gap
panels' naming in words; its step-walking coverage rides both
the rail segments and the bar's arrows, as the founder uses
both. The wizard's bottom edge carries the bar again; the
sections are quieter — each holds its own work and names what
it is waiting on.
