# ADR 0153: A full History card rebalances by pairing and moving

Status: accepted

Refines ADR 0150 (the summary rides in the record) and ADR 0151
(the record sections stand solid). Neither decision changes: the
sections stay solid, and the media column keeps ADR 0149's 288px
cap — the clip is not shrunk, capped or letterboxed by this record.

## Context

Kasra, live on Nov 15 2026, with a screenshot of a full History
card — post kit written, plan context present, the paste-link row
at the record's foot: "Still the left portion of the video history
page is shorter."

He was right. ADR 0150 balanced the sparse card: moving the
identity summary into the record gave the record enough content to
end near the media column's foot. A full card tips the other way.
Measured on his screenshot, the record's content runs about
1,065px — summary, journey and verdict, then Post copy stacked
over Plan context (about 700px of sections alone), then the
feedback block — against about 700px of media content (the 512px
clip, the Download row, the Work row). The left side's content
ends roughly 365px above the card's foot, and dead card surface
sits under it.

His standing rules bind the fix: the two sides must read equal
height, no filler spacing may be distributed between boxes to
force it, and every function on the card survives. So the
rebalance rearranges real content, the same way ADR 0150 did —
it takes height out of the record and adds real height to the
media column.

## Decision

- **Post copy and Plan context pair side by side.** When both
  sections are present on a standard (non-compact) card, they sit
  in a two-column grid instead of stacking, taking several hundred
  pixels of stacked height out of the record. A row with only one
  section keeps the full record width. The pairing is a named
  class pair on the sections wrapper (`history-record-sections`,
  plus `history-record-sections-paired` when both render), and the
  two-column template lives in `index.css` at a container
  breakpoint: the card itself is the container
  (`container-type: inline-size`), and the pair engages at 1080px
  of card width. The geometry: at 1080px the record's content
  column runs about 744px (card minus the 288px media column and
  the body's 48px of padding), leaving each section about 366px —
  the narrowest the post kit's label-and-value rows and the
  context rows read without cramming. The founder's card sits at
  the 1150px content cap, where each section gets about 400px.
  A container breakpoint, not a viewport one, because the
  viewport cannot see the sidebar's state and the card can.
  The kit-less generate-post-copy box is not part of the pair:
  it renders instead of a kit, and beside a context section it
  keeps today's stacking and full width.
- **The feedback block moves to the media column.** On standard
  cards the HistoryFeedback block — the paste-the-TikTok-link
  form, its note, and the views and results fields that follow a
  posted link — renders under the Work with this render row, as
  part of the render's own action stack: same component, same
  props, same testids, same behavior. Its content is actions on
  the render, and its height now stands in the column that had
  room. The journey line's buttons keep their contract across
  the move: they scroll to and focus the link and results inputs
  by testid, document-wide, wherever the block renders. With
  nothing left in the record's secondary area, a standard card
  no longer renders the Results & actions disclosure at all —
  a toggle that opens nothing is not kept.
- **Compact cards are untouched.** Their feedback block stays in
  the record's secondary area behind its toggle, exactly as
  before; the pairing never reaches them (a compact row carries
  neither section by definition). One render site per mode,
  never both.
- **The loading skeleton mirrors the new shape** (ADR 0143):
  its section placeholders pair under the same classes, and its
  feedback placeholder rides in the media column under the work
  row placeholder.

## Consequences

- On the founder's full-card shape the two sides land close:
  the record sheds the stacked second section (about 300px) and
  the feedback block (about 105px), and the media column gains
  the feedback block (about 130px at its narrower width).
  Estimated from the component structure, the record ends at
  roughly 730px and the media column at roughly 810px on that
  card — within about 100px, against about 365px the other way
  before. Exact equality varies with content length — a longer
  caption or demo brief grows the record, a posted link grows
  the media column with its views and results fields — and that
  variance is accepted: the aim is the two sides ending together
  on a typical full card, never filler spacing spent to force a
  pixel match.
- Post copy and Plan context are readable at a glance side by
  side — the copy the founder ships next to the context it was
  written for — at the price of narrower sections on a full
  card; below the container breakpoint they stack as before.
- Regression-pinned in the render smoke suite: a full standard
  row renders the pair modifier and its feedback inside the
  media column and not the detail panel; a context-only or
  kit-only row does not pair; a compact row keeps its feedback
  in the record; the skeleton mirrors both moves; and the
  feedback saves' guarantees (views, link, winner sync) are
  pinned card-wide, as they were when the block sat in the
  panel.
