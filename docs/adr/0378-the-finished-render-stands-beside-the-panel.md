# ADR 0378: The finished render stands beside the render panel's content

## Status

Accepted, Nov 26 2026 — Kasra's order: redesign
Create's render section to read more modern, with
the finished video appearing beside the section's
content instead of below it. The change lands in
`frontend/src/components/GenerationPanel.jsx`.

## Context

The render panel stacked everything in one column.
When a render finished, the clip appeared inside
that column in a row of its own — the video at the
left, the frozen post copy beside it — below the
controls and the progress that produced it. Judging
the finished video meant scrolling to it, and the
panel read as a stack of frames rather than one
surface with a result standing next to the work.

## Decision

The panel's inside becomes two columns exactly
when there is a finished, playable render to show:

- The layout is a grid at desktop widths: a
  flexible first column carrying the panel's
  content — its heading, controls, progress and
  record — and a fixed 320px second column carrying
  the finished video alone (the platform phone
  frame, the preview retry and the Download MP4),
  sized for the 9:16 clip.
- Below desktop widths the columns stack in order:
  content first, the video right after it.
- With no finished video — idle, in flight, failed —
  the grid never forms and the content keeps the
  full width it always had. A failed render grows
  no empty video column.
- The frozen post copy stays in the content column,
  under the record. Only the video moved; the
  Demo + CTA upsell block's conditions are
  unchanged (its standing `onNavigate` gate folded
  into the finished block's own condition, which
  already implied it).

## Checks

New: "the finished render stands beside the render
panel's content" pins the grid — the video in its
own column after the content column, the post copy
still in the content column, the stacked order
below desktop widths. "a failed render keeps its
retry and grows no video column" pins the negative:
no finished render, no second column, the retry
untouched.

## Alternatives considered

A permanent two-column panel with the video's seat
held empty during generation: rejected — an idle
panel squeezed by an empty column gives up the
width the controls and the plan record use, to
reserve a seat that is empty most of the panel's
life. Moving the post copy into the video column
with the clip: rejected — the copy is part of the
record the founder reads and edits; only the video
was asked to stand beside the content.
