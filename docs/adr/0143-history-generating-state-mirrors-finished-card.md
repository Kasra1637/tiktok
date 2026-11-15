# ADR 0143: The History generating state mirrors the finished card exactly

Status: accepted

## Context

On Nov 14 2026 Kasra screenshotted a History card in its Generating
state (a Vocolens render, heygen-video-1, template v1, script v2) and
named the defect plainly: the placeholder at the top of the card was a
small, centered, phone-shaped box, far narrower than the rest of the
card, so the whole card jumped and resized when the finished video
landed. His rule: the skeleton layout must match the exact structure
of what will come when it renders — show the whole container and the
exact thing that will show up eventually on the page.

Two surfaces broke that rule:

- The History page's loading skeleton rendered a 135×240 phone-shaped
  box centered in a full-width stage, above a single thin line — no
  two-column row grid, no Download row, no work row, no summary, no
  record. Nothing about it predicted the finished card's shape.
- A generating row's stage kept the old padded stage and a small
  dashed notice box (max-width 340px), while the finished card's stage
  is flush with a full-width 9:16 frame (ADR 0137). The media column
  changed height and shape the moment the clip arrived.

The same evening Kasra screenshotted the completed card itself (the
bakery render, finished 6:13 PM) with the companion defect: the left
and right sides are not equal height. The portrait clip makes the
media column tall; the record column's content ended early and left
a void at the bottom of the card. The mirror rule therefore has to
describe the finished card's true geometry — including how its two
columns fill — or the skeleton would mirror a shape the finished
card does not have.

## Decision

- **The loading skeleton is the finished card's structure with
  placeholders in it**: the same flush `history-card`, the same
  `history-row-grid` (two columns from 900px, stacked below, in the
  finished order — clip, Download row, work row, summary, record), a
  frame placeholder at the finished frame's full width and 9:16
  aspect inside the flush stage, placeholder rows at the Download
  row's and work row's real heights, summary bars where the summary
  sits, and record placeholders inside `history-body`. It reuses the
  existing `Skeleton` shimmer; no new visual language.
- **A regular card with no playable clip stands its notice in the
  finished frame's geometry**: the stage takes `history-stage-flush`
  at every width, and the notice renders inside a full-width 9:16
  frame (`.history-stage-frame` wearing `.history-preview-frame`'s
  edge). The notice keeps its words, its icon and its repair meaning —
  only its footprint changes — so a generating card already occupies
  the exact space the clip will fill, and completion is a swap, not a
  resize.
- **The placeholder is not the clip.** The framed notice deliberately
  does not take the playable clip's `history-brand-frame` testid or a
  `<video>` element: the frame is reserved geometry, not a claim that
  a clip exists.
- **The finished card's columns stand equal, and the mirror includes
  the fill.** At 900px and up the row grid stretches to its taller
  side — almost always the media column, whose 9:16 frame sets the
  card's height — and the record column fills that height: the detail
  column and its body become a full-height flex column and the record
  blocks (`.history-record`) distribute the leftover space between
  them, so no block stretches and no void sits at the bottom. The
  video is never shrunk or capped to meet the record — the ADR 0137
  flush frame stands and the record side does all the filling. Below
  900px the stacked layout is unchanged, and compact cards keep their
  own geometry. The skeleton wears the same classes, so its record
  fills the same way before the clip lands.
- **Compact cards are unchanged.** Their stage stays a small centered
  stage by design and their notices stay in the record; the mirror
  rule governs the standard card Kasra screenshotted.
- **Layout only.** Polling, the ADR 0140 honest-progress wording
  (words plus elapsed, the paused-poll announcement) and every repair
  action are untouched.

## Consequences

- A render finishing is now a content swap inside a stable footprint:
  the card a founder watches while waiting is the card they get.
- Every no-clip state on a regular card (queued, generating, no
  durable copy, preview broken, failed) reserves the same frame
  geometry, so recovery and retry transitions stop resizing the card
  too.
- design_guidelines.md's History section now records the mirror rule
  where it previously said no-clip cards keep "their notice and no
  frame".
