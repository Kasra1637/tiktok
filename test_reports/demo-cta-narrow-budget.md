# Demo + CTA narrow-budget proof (post-52vh)

Loaded-source layout check at phone widths with the preview parked, never
playing. Supplements the automated gate
`the loaded player row fits narrow columns without horizontal overflow` in
`frontend/scripts/check-render-smoke.cjs`, which asserts the same overflow
contract in jsdom but cannot measure pixels (jsdom has no layout).

## Method

- Live desktop session on `/create` (Demo + CTA), clip loaded through the
  upload path, then left **paused at frame 0, never played** — no decode loop,
  no playback, so nothing in this proof can wedge CDP the way the retired
  with-clip playback sessions did.
- The probe's `onloadedmetadata` was fired with stubbed 1280x720/8s
  dimensions (no real decode; the frame/column layout resolves from the
  `--demo-cta-frame-w` CSS token, not from the metadata values).
- Viewports set to 390x844 and 768x900. For each: read
  `.demo-cta-frame`, `[data-testid="demo-cta-player"]`, and
  `documentElement.scrollWidth` rects straight from the DOM, then
  screenshotted the player row.

## Measurements (DOM rects)

| viewport | data-player | frame (w x h) | frame vs 52vh | player row h | page h-overflow | worst child overhang |
|---|---|---|---|---|---|---|
| 390x844 | on | 247 x 439 | 100% | 188px | none (-10px) | none (-10px) |
| 768x900 | on | 263 x 468 | 100% | 156px | none (-10px) | none (-10px) |

The stacked frame spends exactly the 52vh no-headroom budget at both
widths, the player row (scrubber, one control row, Export + Lock) stays
compact beneath it, and no element extends past the viewport edge.

## Screenshots

- `demo-cta-narrow-390.png` — frame + player row at 390px.
- `demo-cta-narrow-768.png` — frame + player row at 768px.

Note: both shots show the loud-failure banner for the session's unloadable
clip bytes (`"clip.mp4" couldn't be played as video…`). That is the
fail-loudly path working as designed, not a layout defect — the column is
in the loaded state (`data-player="on"`) and the budget numbers above are
the real rendered rects.
