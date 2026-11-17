# ADR 0184: The empty post-copy panel holds its column

Status: accepted

Refines ADR 0153's pairing rule. On the mural render's
History card (2026-11-16) Post copy stacked BELOW Plan
context, top to bottom, while the lighthouse card below it
— a render with its kit written — paired the two sections
side by side in equal columns. The founder read the two
cards side by side and named the difference: the card he
was happiest with looked broken in a second way, beyond
its missing caption (ADR 0183).

## Cause, proven from the code

The hypothesis was that the paired layout only held when
post copy existed. It did, in two compounding lines in
`frontend/src/pages/GenerationHistory.jsx`:

- `sectionsPaired` required `Boolean(row.post_kit)` — a
  kit-less row could never take the paired class, however
  much context it carried.
- The empty post-copy panel (the "This render finished
  before its caption was written…" box with its Generate
  post copy button) rendered OUTSIDE the sections wrapper
  entirely, after it, at the record's full width — while
  Plan context rendered inside the wrapper. So the card's
  two slots were not even siblings: context stood in the
  grid alone, and the panel stacked beneath it.

ADR 0153 had scoped the pair to "both sections render"
and deliberately kept the kit-less box full-width, as a
stand-in for a kit rather than a section. The founder's
screenshot is the verdict on that scoping: the empty state
is exactly when the card most needs to read as the same
record — the missing caption is a state of the Post copy
slot, not a different layout.

## Decision

- **The pair is a property of the two slots, not of the
  kit's presence.** `sectionsPaired` now holds when the
  card is standard, has context, and its Post copy slot
  renders — the kit, or the empty panel a finished
  (completed/archived) kit-less render is offered. A row
  with genuinely one slot — a kit with no context, or a
  context whose render never finished and is offered no
  panel — keeps the full record width, as ADR 0153 held.
- **The empty panel moves into the wrapper**, as the
  grid's first child in the Post copy slot, ahead of Plan
  context (Post copy still leads). Its markup, words,
  dashed stand-in chrome and testids are unchanged — only
  its parent and the pairing rule move — so the journey
  line's scroll target and the generate flow are untouched.
- **ADR 0151 and the rest of ADR 0153 stand.** Both slots
  remain solid, non-expandable, always-expanded sections;
  the pair still engages at the 1080px card-container
  breakpoint in equal columns; the video stays half-height
  and the feedback block stays in the media column. The
  panel keeps its dashed border inside its column: it is
  the unwritten state of the slot, visibly distinct from a
  written kit, in the same geometry.

## Pins

A new smoke check renders a completed row with context
and no kit and asserts the paired structure: the wrapper
carries the paired class, the empty panel is a child of
the wrapper, and it leads Plan context. The ADR 0153 pair
check's kit-less context row flipped honestly to the new
expectation (it pairs now, holding the panel), and a
failed context row took its place in the not-paired set —
a render that never finished is offered no panel, so its
context still stands alone at full width. Both new
assertions failed before the fix for the diagnosed
reason.
