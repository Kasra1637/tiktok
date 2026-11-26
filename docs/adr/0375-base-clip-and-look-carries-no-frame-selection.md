# ADR 0375: Base clip & look carries no frame selection

## Status

Accepted, Nov 26 2026 — Kasra's direct order: "and
also remove Frame selection from this section only."
The change lands in
`frontend/src/demoCta/DemoCtaEditor.jsx`, scoped to
the Base clip & look section.

## Context

Base clip & look carried a Frame block: a line naming
the active frame, its catalog frame-type tag (Phone,
Web / Browser, Desktop / Monitor — ADR 0260), and a
device picker offering the eleven catalog frames,
from handsets to the desktop monitor. The block drove
the editor's shared `device` state. But the base it
sat over is the founder's footage: since ADR 0374 it
always paints full-frame at the TikTok preset, and
the frame choice never changed what the base itself
looked like — it shaped the phone a dressed look
would draw, a look the base no longer has. The pick
was a decision with no visible consequence on the
clip it named, standing at the head of the section.

## Decision

The whole Frame block — the line, the tag
(`demo-cta-frame-tag`) and the picker
(`device-frame-select`) — leaves Base clip & look.
Nothing else moves:

- The `device` STATE stays, with its default and its
  restore path: the snapshot still carries it, drafts
  still restore it, and the Second clip's own frame
  picker (shown with its floating presentation) drives
  the same shared state and stands untouched.
- What the base's frame now resolves to: the shared
  `device` value, which is `DEFAULTS.device`
  ("s24_ultra") on fresh work, a restored draft's
  stored device, or a value the founder sets at the
  Second clip's frame picker. There is no longer any
  control in Base clip & look that names or changes
  it.
- What still reads `device`: the painter
  (`usePreviewLoop`) resolves the catalog entry for
  the phone geometry a floating or hand-held segment
  draws — since ADR 0374 that can only be the second
  segment; the editor's `activeDevice` still feeds the
  Second clip's frame tag and the overlay safety
  width's source-preset shape (the preset is pinned
  to "tiktok", so the preset's own 1080×1920 governs
  today); and the export names its file from it
  (`buildExportFilename`). The base's own painted
  frame is the preset's, full-bleed, whatever `device`
  holds.

## Checks

Changed, named per the house rule:

- "Base clip & look carries no frame selection; the
  second clip keeps its own (ADR 0375)" replaces "the
  Demo + CTA editor names its frame with its type
  tag". The old check pinned the tag-and-picker pair
  on both clips; the new one pins the removal (no
  frame tag, no base device picker in source) and
  what survives of the old protection: ADR 0260's tag
  discipline on the control that remains — the second
  clip's tag still resolves through
  `deviceKindTag(activeDevice)` and its picker still
  stands.
- The new runtime check "the base clip always stands
  as a Real Video: no style or frame pick in Base clip
  & look (ADRs 0374-0375)" carries this record's
  runtime half: no `device-frame-select`, no
  frame-type tag and no Frame line render in the
  section.

## Alternatives considered

Removing the `device` state with the block: rejected
— the Second clip's floating presentation genuinely
draws a catalog frame, and its picker drives this
same state; the order removes the selection from this
section, not the frame from the composition. Moving
the picker to another section for the base's sake:
rejected — a Real Video base has no frame to choose,
and a control in search of a section is the same
consequence-free decision wearing a new seat.
