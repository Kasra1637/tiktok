# 0217 — The finish step has no Back arrow

Status: accepted (superseded by 0218 on Nov 20 2026; restored the
same day by 0229, which reversed the removal and brought the bar —
and this exception with it — back)

## Context

The Create wizard's sticky action bar carried its Back arrow on
every step, the last one included. The rule was recorded in the
bar's own comment: the wizard has no separate exit control, so
the arrow stayed everywhere and leaving the studio was the
sidebar's job. On Nov 19 2026 Kasra looked at the Demo + CTA
step live — the finished clip open in the editor, the step
marked done — and ordered the back button removed from this
section only. The finish is the end of the flow; a way back
sitting under a finished piece reads as chrome the step has
outgrown.

Removing the arrow exposed one state the every-step rule had
kept invisible. On the finish step with a finished render, the
bar carries nothing else: the hint line is already null in that
state (Kasra's earlier order — with a render in hand the editor
is the work), no bar action is offered there, and the forward
arrow never renders on the last step. The arrow was the pill's
only content, so taking it away would leave an empty glass pill
floating at the bottom of a finished step.

## Decision

1. **The Back arrow renders on every step but the last.** In
   `frontend/src/pages/CreateVideo.jsx` the button is gated on
   `isLastStep` (`step === STEPS.length - 1`, the Demo + CTA
   step). Steps 1–3 are untouched, including the arrow's
   disabled state on the first step and its destination-naming
   aria-labels. This reverses the every-step rule for the last
   step only.
2. **A bar with nothing to carry does not render.** When the
   step in view is the last and the bar would hold no hint, no
   bar action and no forward arrow (`barStandsDown`), the whole
   sticky bar unmounts instead of floating an empty pill. In
   the finish step's other state — no render yet — the bar
   stays, carrying its hint ("Render the piece first — the
   finished clip opens here.") and its Go to the render action,
   minus the arrow.
3. **Nothing else about navigation moves.** The step rail and
   pills still name every step, the section headers still walk
   the canvas, and leaving the studio stays the sidebar's job,
   exactly as before.

## Alternatives rejected

- **Remove the arrow on every step.** Kasra named this section
  only; the earlier steps' way back is used and pinned, and it
  stays.
- **Hide the arrow but keep the bar mounted on the finished
  step.** An empty glass pill is chrome without content — the
  exact visual the order was removing, kept.
- **Give the finish step a replacement exit control.** The
  worded last-step exit was removed deliberately in an earlier
  round, and no second back control may stack under the bar;
  the sidebar owns leaving.

## Consequences

The Demo + CTA step's bottom is clean in both its states: with
a render, no bar at all; without one, the bar carries only the
line and the action that name the missing render. The render
smoke pins all three states — earlier steps keep a working
Back arrow, the finish with a render shows neither arrow nor
bar, and the finish without a render keeps the bar with no
arrow — so the arrow cannot quietly return to the last step,
and the empty pill cannot appear if the bar's other contents
change.
