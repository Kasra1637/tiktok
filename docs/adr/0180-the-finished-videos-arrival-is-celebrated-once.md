# ADR 0180: The finished video's arrival is celebrated once

Status: accepted

Kasra's order, Nov 16 2026, in the same delivery as ADR
0179's fix: when the video appears in the "Generate your
video" section, add an appropriate celebration animation
that shows only for a few seconds as it appears. His
companion ruling the same evening: no auto-redirect to
History on completion — the reveal stays in the section,
which is what makes the arrival worth marking there.

## Decision

- **The trigger is the observed transition, nothing else.**
  The panel tracks the previous generation row it rendered;
  the celebration fires only when that row was submitted or
  generating and the same row (same id) now reads completed
  — the generating→completed flip the panel itself watched
  happen. It does not fire when the panel mounts already
  showing a finished video (the return visit, the reload),
  not on re-renders or later polls, and not when the storage
  retry completes a row that was already completed: that
  arrival was celebrated, or not, at its own moment.
- **The form is the app's own motion language.** The finished
  frame rises and settles on the one entrance motion (ADR
  0165: rise-settle, 300ms, the signature ease), a soft
  indigo glow pulses around it once (2.6s, the brand indigos
  of the generate-glow family), and twelve small indigo dots
  burst outward from the frame's edges and fade (1.5s, per-dot
  drift and delay). CSS-only — no library, no image — and the
  panel clears the state at 2.8s, so the whole marking is
  over in under three seconds.
- **The video is never gated by it.** The celebration is a
  layer on the arrival, not a step before it: the frame, its
  player and the Download MP4 control render in the same
  paint whether or not the celebration is running, the dots
  layer is aria-hidden and pointer-events-none, and nothing
  about the completed block's content, order or controls
  changes.
- **Reduced motion gets silence.** Both animations are
  applied only inside `@media (prefers-reduced-motion:
  no-preference)` blocks, one rule per block like every
  gated entrance in the stylesheet. Under reduced motion the
  classes carry no animation at all: the video simply
  appears.

## Consequences

Three smoke pins land with it: a behavioral check that
mounts a generating row whose second poll completes it and
watches the celebration appear (frame, at least eight dots,
the video and its download present inside the moment) and
then clear; a check that a panel mounted on an
already-finished video never celebrates; and a source check
that both celebration animations resolve only inside the
reduced-motion gate, the frame's to the unified rise-settle
plus the glow pulse. The one-shot state lives beside the
poll loop that feeds it, so the contract — observed
transition, same row, once — is readable where it is kept.
Nothing else in the panel changes: the stages, the stall and
long-save notices (ADRs 0170/0171/0179), and the completed
block's contents are untouched.
