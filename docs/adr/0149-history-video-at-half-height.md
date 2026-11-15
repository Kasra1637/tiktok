# ADR 0149: The History video stands at half height, in a capped media column

Status: accepted

Refines ADR 0143; supersedes its "the video is never capped" line and
the balanced two-column proportion of the fc74233 layout, at the
founder's direction.

## Context

Kasra, reviewing History live on Nov 14 2026: the finished video is
far too tall. The fc74233 layout (ADR 0137's flush frame on ADR
0143's balanced split) gives the media column half the card, and a
9:16 frame at that width stands over a thousand pixels tall at the
design width — the card reads as a video with a record attached, and
the record's own content is exiled to a narrow column beside it. His
instruction: shrink the video by two times — about half its current
displayed height — and realign the card's components around the
smaller video so the card stays organized, with correct spacing.

He sharpened the equal-height half of the design in the same call:
the two sections must still stand equal in height, but WITHOUT extra
filler spacing showing between the record's boxes and sections.
ADR 0143's fill did exactly that — the record column stretched to the
frame's height by distributing its blocks over it (`space-between`),
so the taller the video grew, the wider the gaps between the record's
own sections became. At the old height that already read as filler;
it is part of what he was objecting to.

## Decision

- **The proportion is set by the column, not the frame.** At 900px
  and up the row grid is `minmax(0, 288px) minmax(0, 1fr)`: the media
  column is capped, the record takes the freed width. The 9:16 frame
  lands at about half its former height at the design width (288px
  wide → 512px tall, against ~1022px before). ADR 0137 stands inside
  the column: the frame still spans it edge to edge, flush, hairline
  edge, no padding, no cap on the frame itself — only the column
  narrowed, so the clip, the Download row and the Work row beneath it
  still share one edge-to-edge block, and the summary rides under
  them as before.
- **Equal height stays; the distribution goes.** The row still
  stretches its columns equal (ADR 0143), and the record still fills
  its column — but its blocks now keep their natural `space-y-5`
  rhythm and any leftover height collects at the column's foot,
  inside the body's padding, instead of being spread between blocks
  as visible filler. The card is one cohesive surface whose two sides
  end together, with the app's ordinary spacing everywhere.
- **Everything that mirrors the card inherits.** The generating
  skeleton and the no-clip notice state wear the finished card's
  classes, so both take the capped column and the same fill with no
  separate geometry to keep in sync (ADR 0143's mirror rule stands).
- **Untouched:** the stacked layout below 900px, compact cards (their
  own 135px geometry), the verdict/journey/chips content and their
  order, the Download and Work rows' membership in the media column,
  and the render panel's own preview (a different surface, not in
  scope).

## Consequences

- A finished card is a record with a clip in it again: the video is
  present at a size a founder scans past, the record gets the wide
  share of the card for the facts, post copy and verdict it carries,
  and neither column shows stretched filler to reach the other's
  height.
- ADR 0143's "the video is never shrunk or capped to meet it" is
  retired as a rule: the founder is the designer, he met the
  uncapped layout in real use, and this record is the correction.
  What survives of 0143 is the part he kept — equal columns and the
  skeleton mirror.
- Regression-pinned in the render smoke suite: the desktop grid
  template is the capped split and the balanced template is gone; the
  record carries no `space-between` distribution in the desktop
  rules while the stretch rule stands; the flush-frame pins (0137)
  and the skeleton-mirror pins pass unchanged.
