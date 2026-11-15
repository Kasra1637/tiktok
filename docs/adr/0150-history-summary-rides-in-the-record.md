# ADR 0150: The History summary rides in the record column

Status: accepted

Completes ADR 0149's equal-height intent.

## Context

Kasra, reviewing History live on Nov 15 2026 with a screenshot: the
finished card's left side still stands taller than the right. ADR
0149 capped the video at half height and removed the filler
distribution, but the columns' content still did not balance. The
media column carried the clip, the Download row and the Work row —
and then the whole identity summary under them: app name and status,
date, the provenance chips, the hook line and the results line. The
record column (journey line, verdict, post copy, plan context, the
paste-link row) ended much higher, leaving a large dead region at
the card's lower right.

The summary is record content — provenance and state, the facts
about the render — that happened to be parked in the media column.
No spacing rule can balance a card whose content sits in the wrong
column; ADR 0149's no-filler rule (Kasra's standing sharpening)
forbids disguising the imbalance by stretching gaps.

## Decision

- **The summary stack moves to the head of the record column.** It
  opens the record — identity first, then the journey line and the
  whole-video verdict under it, then post copy, plan context and
  the results row, in the order the record already used. Every
  element and its wording is unchanged; only its column changes.
  Its media-column band chrome (the `row-pad` gutter and top
  hairline) goes with the move: inside the record, the body's
  padding is the gutter and the record's `space-y-5` rhythm is the
  separation.
- **The media column is media only:** the stage, the Download row
  and the Work with this render row. Nothing else rides under the
  clip.
- **The stacked reading order does not change.** Below 900px the
  summary was the media column's last block and is now the record's
  first, so a phone reads the card in exactly the sequence it did
  before; compact cards take the same move with their own geometry
  untouched.
- **The loading skeleton mirrors the new structure** (ADR 0143's
  mirror rule): its summary placeholder leads the skeleton's
  record, and its media column carries only the frame, Download
  and work placeholders.

## Consequences

- On the screenshot's card (post copy expanded), the layout math
  lands the two sides within roughly 30px of each other — media
  ≈655px (the 512px frame, the Download row, the Work row),
  record ≈685px with the summary's ~90px home — where before, the
  record ended some 170px above the media's foot and the summary's
  ~110px sat on the wrong side of the card.
- The 512px clip remains the floor: a sparse record (no post copy,
  nothing to show) can still end above the media column's foot.
  That leftover collects at the record's foot inside the body's
  padding, per ADR 0149 — it is the video's height, not a gap the
  design papers over.
- Regression-pinned in the render smoke suite: the summary renders
  inside the record column and not under the media block, the media
  column contains only its stage and action rows, the record's
  order is summary → journey → verdict, the hook headline lives
  exactly once in the card, and the skeleton mirrors the placement.
