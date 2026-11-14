# ADR 0137: The History clip sits flush, and work with this render lives under it

Status: accepted

## Context

The History card (two columns from 900px, ADR lineage from the card
rebuild) showed the finished clip inside a framed stage: the stage padded
the clip by 20px (12px wide) on a dark slab, and `.history-preview-frame`
capped the clip's width by its height cap (320px tall → 180px wide;
560px → ~325px wide), then added a 4px indigo surround with two corner
marks on top. In the wide layout the media column is much wider than
325px, so the clip rendered noticeably narrower than the Download row
beneath it, floating in a black stage box. The founder asked for the
video to cover its box edge to edge at the same width as the rows under
it, for the heavy frame to go, and for the Work with this render buttons
(Demo + CTA, Remix this plan) to move out of the record column into the
media column directly under the Download row, as their own row — one row
of four buttons was explicitly rejected as too crowded. His screenshot
also showed the browser's three-dots overflow menu inside the player.

## Decision

- **Flush frame.** `.history-preview-frame` spans the media column at
  width 100% with no padding and no max-width, at most the card hairline
  (`--hairline`) for an edge, radius 0.75rem matching the footage; the
  indigo gradient surround and the corner marks are removed. The video's
  height caps (320px/560px) are removed with the width caps they fed:
  the 9:16 height follows the column width. When a standard card plays,
  its stage takes `history-stage-flush` (no padding, no min-height, no
  slab); the empty/notice state keeps the padded stage, and compact
  cards keep their fixed 135px stage untouched. The two overlay facts
  (objective chip, duration chip) are unchanged.
- **Work row under Download.** The Work with this render group
  (`history-actions`: Demo + CTA, Remix this plan / Another take like
  this) renders inside `.history-media`, directly after the Download
  row and before the summary, at every width — so below 900px the order
  stays clip, Download, render buttons, then the record. The record
  column keeps the journey lines, verdict, post copy, plan context and
  the TikTok link row.
- **Native controls contract.** The finished clip's `<video>` (History
  card and the render panel's finished preview) carries
  `controlsList="nodownload noremoteplayback"` and
  `disablePictureInPicture`. The three-dots menu is the browser's own
  overflow for native controls, never app UI; emptying it (Download,
  playback speed, PiP) removes the button in Chrome. Play, pause, seek,
  volume and fullscreen are untouched, and no custom controls are built.
  Browsers that ignore `controlsList` may still show their overflow —
  accepted, per the founder's scope.

## Consequences

- One flush block in the media column: clip, Download (+ Delete),
  render buttons — identical left and right edges.
- The design guidelines' History section describes the flush frame and
  the new action order; the smoke suite pins the frame's uncapped,
  padding-free shape, the flush stage class, the work row's placement
  (inside the media column, after the Download row, absent from the
  record panel) and the video element's controls attributes.
