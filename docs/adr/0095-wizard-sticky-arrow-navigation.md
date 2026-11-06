# 0095 — Wizard: step task under the title, sticky arrow navigation

- **Status:** accepted (the hint-free bar superseded by 0099; the
  "Back to your app" exit removed — the arrow Back covers every step)
- **Date:** 2026-11-04
- **Anchors:** `frontend/src/pages/CreateVideo.jsx` (`wizard-step-task` under
  `PageHeader`, `wizard-arrows` sticky bar, `wizard-back-button` /
  `wizard-continue-button` arrow-only); smoke checks "wizard arrows walk the
  steps in order" and "the wizard states the step once under the title and
  centres its arrows"
- **Shapes:** the top and bottom of the Create wizard only. Step contents,
  the free-jump pills and every gate are unchanged.

## Context

The step's one guidance line ("Step 2 of 3: Angle, goal, template and photo —
each one ranks the next") lived between the step's content and the footer
arrows, where it was easy to miss, and the footer's "Continue when ready —
you can always go back" hint led the bottom of the page with a promise
instead of a direction. The arrows themselves were text buttons ("Back",
"Continue") sitting in the normal page flow, so on a long step (goal +
templates + photo) the way forward was only reachable after scrolling.

## Decision

- **The task line sits directly under the page title** ("Create Video",
  then "Step 2 of 3: …"), before the progress pills. It is the only guidance
  line; nothing in the sticky footer repeats it.
- **The arrows are sticky.** The Back/Continue cluster sticks to the bottom
  of the scroll (`sticky bottom-4, z-30`) for the whole step, centred as one
  control. The Back arrow renders on **every** step, the last one included;
  the worded "Back to your app" exit was removed, so leaving the studio is the
  sidebar's job and no second back control stacks under the bar.
- **Arrow-only.** No words on either button; the destination remains in the
  aria-label and the `aria-label`-based checks are unchanged. The hint is
  dropped from the sticky bar entirely: it was a standing sentence that
  could not name what was actually missing, the per-step gates already do
  that, and an icon bar with a sentence above it is not the minimal control
  the step needs.

## Alternatives rejected

- **Sticky top or a floating pill.** The arrows already sit at the end of the
  content; sticking them where they are is less motion than relocating them.
- **Keeping the words.** "Back" and "Continue" repeat the aria-labels the
  buttons already carry; the icon-only pair is the direction control the
  founder reads by position.
- **Keeping the hint.** It could not name what is missing, so it was a
  promise in place of guidance. The gates and red buttons already name the
  gap with a destination.

## Consequences

- The wizard's primary chrome — title, task, pills, then content — reads top
  to bottom without a repeated sentence, and the way back/forward is one tap
  away from any scroll position on the long step.
- The smoke suite pins the task line's position (below the title, above the
  pills), the stickiness, the centred cluster and the empty button bodies, so
  a word or a scroll-away control fails the gate.
- No backend, data or workflow change: the arrows still only move and the rail
  still jumps. The last step's separate exit is gone (its own later change):
  the arrow Back covers every step now.
