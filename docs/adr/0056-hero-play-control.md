# 0056 — The hero footage carries its own play/pause control

- **Status:** accepted
- **Date:** 2026-10-29
- **Anchors:** `frontend/src/components/LazyHeroVideo.jsx` (`showPlayControl`, `togglePlayback`); `frontend/src/pages/Landing.jsx` (`landing-hero-shot`); smoke checks "the hero's play control pauses the footage and plays it again", "the reduced-motion hero waits for the play tap before loading footage", "a refused hero autoplay leaves Play, not a dead Pause"

## Context

The landing hero is a looping screen recording that autoplays muted. It had no
control at all, which left three holes:

- Moving content that loops indefinitely has to be pausable (WCAG 2.2.2), and
  the only way out was to leave the page.
- Muted autoplay is usually allowed but not guaranteed — data saver, an
  embedded webview, or a strict default can refuse it, and the hero then sat
  on its poster with nothing to press.
- Under `prefers-reduced-motion` the component deliberately never loads the
  footage, so a reduced-motion visitor had no way to see the recording even if
  they wanted to.

## Decision

- `LazyHeroVideo` takes `showPlayControl`; the landing hero sets it, the
  hypothetical preview does not (its card carries a caption bar across the
  bottom edge, where the control would sit).
- The control is one circular button in the frame's bottom-right corner using
  the existing on-media token (white hairline at 25%, black at 65%, backdrop
  blur — the History idle-frame chips) plus `.tap-chip` and `.focus-ring`.
- Its state comes only from the element's own `play`/`pause`/`error` events.
  Autoplay being refused therefore leaves the button saying *Play* — never a
  *Pause* drawn over a frozen poster — and pressing it retries.
- A tap that lands before the footage is attached (the poster state, and the
  reduced-motion state) records the intent and starts playback as soon as the
  `<source>` elements mount, so the first press always works.
- `canplay` no longer restarts footage the visitor paused on purpose; autoplay
  still starts playback on its own when nobody has pressed Pause.

## Alternatives rejected

- **Native `controls`.** The browser's chrome is a 40px bar over a portrait
  recording, and it exposes volume and fullscreen the marketing frame does not
  want; it also renders UI while the footage has not loaded.
- **Hover-only affordance.** Unreachable by touch and invisible to the
  reduced-motion visitor, who needs the button before there is anything to
  hover.
- **Load the footage under reduced motion and autoplay nothing.** Costs every
  reduced-motion visitor the bytes the lazy load exists to save, to serve a
  poster they already have.

## Consequences

- The reduced-motion contract is now "no bytes until an explicit tap" rather
  than "never", which keeps the saving for everyone who never presses and
  keeps the recording reachable for everyone who does.
- The control's label — not its icon — is the contract: the smoke suite pins
  Pause → pause → Play → play → Pause, plus the reduced-motion first press and
  a refused autoplay, so a dead button fails the gate instead of shipping.
- Footage the browser cannot decode drops the control rather than leaving a
  Play that cannot start anything; the poster alone reads as what it is, and
  the smoke suite pins that too.
