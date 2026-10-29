# 0057 — The Demo + CTA preview plays from its own frame

- **Status:** accepted
- **Date:** 2026-10-29
- **Anchors:** `frontend/src/demoCta/DemoCtaEditor.jsx` (`demo-cta-preview-play`, `togglePlayPause`); smoke check "the loaded Demo + CTA preview carries one branded play button"

## Context

The Demo + CTA preview is a canvas, so it has no native controls. Playback
lives in the transport row, which sits in the player bar **under** the frame
inside a column that caps at the viewport and scrolls internally when frame +
bar exceed it. On stacked layouts the preview column follows the whole
settings panel. Either way, starting the clip meant scrolling away from it —
the founder is looking at the video and the play control is somewhere else.

## Decision

- One play button sits **on** the preview frame: centered, 56px, circular,
  `accent` (indigo bevel + the glow the variant already carries).
- It is shown only when a clip is loaded, playback is paused, and nothing is
  recording. It calls the same `togglePlayPause` the transport calls — there is
  no second playback path and no second `isPlaying` state.
- It leaves the frame the moment playback starts, so it never covers footage
  being reviewed and never contradicts the transport row.
- Recording hides it, because the export owns the timeline while it runs.

## Alternatives rejected

- **A second transport on the frame.** Two sets of play/pause state can
  disagree, and the row below already owns seeking, stepping and muting.
- **An always-visible play/pause overlay.** It sits over the footage the
  founder is judging, and the transport is one glance below it.
- **A neutral or ghost icon.** Over arbitrary footage a low-contrast control
  disappears into the clip; `accent` is the variant the guidelines reserve for
  "the action a screen commits to", which this is.
- **A corner button.** Corners read as chrome (mute, settings). Play is looked
  for in the middle of the thing it plays.

## Consequences

- While paused, the dead center of the preview is now Play rather than a drag
  handle. Dragging the framing still works everywhere else on the canvas, and
  the zoom/position sliders remain the precise path; the alternative — hiding
  the button during a drag — couples two unrelated gestures for no gain.
- The smoke suite pins the contract: an empty frame has no button, a loaded
  paused frame has exactly one inside `.demo-cta-frame`, pressing it starts the
  transport, and the button is gone while the clip plays.
