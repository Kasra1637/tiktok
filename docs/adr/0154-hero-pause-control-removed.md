# ADR 0154: The hero flow has no pause control

Status: accepted

Supersedes the living surface of ADR 0056 (the autoplaying hero
carries its own play/pause control); 0056 itself stays as history.

## Context

Kasra, live on Nov 15 2026, on the landing hero where the five
how-it-works steps cycle in the frame beside the headline: remove
the play/pause button between the dots and the steps — "just hide
it" — so the flow always auto-plays and there is no need to show
or hide a button.

## Decision

The toggle is gone entirely: the button element, its handler, the
`hero-flow-toggle` testid, and the dead `.hero-flow-toggle` CSS
rule. "Playing" is now derived from the motion setting alone,
never toggled. The loop otherwise behaves exactly as before — the
five slides, the four-second cycle with its crossfade, and the
dots as position indicators that also step by hand.

Two stillness paths are deliberately kept, because neither is a
visible control and Kasra's order named the button:

- Hover pause stays: the pointer resting on the frame still
  stills the loop, and leaving the frame resumes it.
- Reduced motion stays: under `prefers-reduced-motion` the loop
  never starts and the first step sits still, with the dots as
  the way through.

The smoke suite pins the new shape: a check asserts no pause
control renders anywhere in the hero and that the flow advances
on its own, and a CSS assertion holds the dead rule absent.
