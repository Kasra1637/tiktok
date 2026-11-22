# ADR 0266: The second clip gets its own Fine-tune framing

Status: accepted

## Context

Reviewing the Demo + CTA editor on Nov 22 2026, Kasra's order was
short: "Add the same fine-tuning setting in the first clip for the
second clip."

Fine-tune framing — the disclosure inside Base clip & look holding
Phone size (Floating), Hand size & position (Hand Holding), Mockup
height, and Phone screen position (Hand Holding) — existed only for
the base clip. The Second clip already carried its own style,
scene, backdrop, transition, audio, and its own Video crop block
(ADR 0164), but no framing of its own. What the added segment did
instead was borrow the base's geometry in the one painter both
preview and export call (`paintFrame` in `usePreviewLoop`): its
phone size and hand zoom/pan came from the base's lock-resolved
framing (`ez`), its mockup height from the base's
`mockupStretchY`, and its hand shot was composited into the ONE
shared screen rect — the base section's Phone screen position
control even stood when only the added clip was hand-held, because
that single rect drove both hand shots. None of it was the added
clip's own choice, and the shared rect meant one control silently
drove two clips.

## Decision

**The Second clip group carries a Fine-tune framing disclosure of
its own**, mirroring the base's group for group, following ADR
0164's pattern: the same labels, the same `RANGES`, steps, formats
and reset behaviour, over its own state — `appendScale`,
`appendHandZoom`, `appendHandPanX`, `appendHandPanY`,
`appendMockupStretchY`, and its own screen rect `appendScreenX` /
`appendScreenY` / `appendScreenW` / `appendScreenH` — defaulting
exactly where the base's defaults sit (phone size from
`DEFAULTS.scale`, hand zoom 1 and pans 0, stretch 1, the rect
`DEFAULT_SCREEN`). The disclosure stands when second media is
present — a loaded clip or an image sequence, the same gate as the
Second clip style picker, since the framing styles apply to both —
and each group inside follows the added clip's own style
(`appendMode`) the way the base's groups follow `viewMode`: Phone
size only in Floating, Hand size & position and Phone screen
position only in Hand Holding, Mockup height always. The Video
crop is NOT duplicated into it: the added clip's own crop block
(ADR 0164) already stands in the group and stays where it is. The
base's disclosure is not moved, renamed or restyled.

**One painter, resolved per segment.** `paintFrame` now resolves
the framing per segment beside the per-segment crop: the base from
its lock-resolved `ez`, its `mockupStretchY` and its rect; the
added segment from its own framing state — a fixed treatment, like
its crop, never keyframed. The floating branches measure the phone
from the segment's own stretch and phone size; the hand branch
hands `drawHandView` the segment's own rect and hand transform.
The canvas-level phone height (which sizes the canvas itself for
the source preset) stays the base's — it is not a segment value.
Export calls this same painter per decoded frame, so the added
segment's framing is baked into the file exactly as previewed
(ADR 0007). The added clip's framing controls invalidate the
sequence through the export edit key, the way its crop controls
do, and the painter's dependency array carries the new values, so
a slider move repaints the preview like any other setting.

**The base's screen control governs the base alone.** Its render
gate narrows from "the base is hand-held, or the added clip is"
to the base's own hand mode only: with the shared rect gone, the
old second clause would have stood a control whose only hand shot
was no longer its to govern. The added clip's rect is set in its
own section, by its own control, with its own Reset to photo
screen.

**The framing rides the draft.** The nine fields join the edit
snapshot and the restore setters beside the added clip's crop
fields, so the demo-CTA draft parity check covers them — with
them included it counts 66 snapshotted fields and holds. Drafts
saved before this change carry none of
the fields; restore skips absent keys, so the added clip's
framing opens on the defaults above and the base's saved rect is
untouched. Removing the second clip resets its framing with its
crop, the way `removeAppend` already reset the rest of the added
clip's treatment.

**What deliberately did not move.** Canvas drag and scroll still
drive the base's lock framing (`updateZoomDraft`), including over
the added segment — the same settlement ADR 0164 left for the
crop, whose added-clip offsets are likewise slider-set. The added
clip's hand group therefore carries no "Drag to move • scroll to
zoom" hint: its hand framing is set by its sliders alone, and the
hint would promise an interaction that edits the other clip. The
zoom-lock timeline itself stays the base's, one timeline across
the cut; nothing about keyframes, the base's groups, or the
image-sequence composition (whose frames the painter treats as
the added segment, so the framing applies to stills exactly as
to a clip) changes.

## Checks

Two render-smoke checks, written red before green. The first
drives the real controls: no disclosure before second media
exists; in Real Video only Mockup height stands; in Floating the
painted phone grows by exactly the Phone size slider's ratio
while the base's painted phone does not move, and the base's own
slider reads untouched (and driving it never reaches the added
clip); Mockup height takes its End press and its Reset; in Hand
Holding the hand sliders and the added clip's own screen controls
stand, the base's hand zoom and rect read back unmoved, the
base's screen control leaves when the base floats again while
the added clip's stays, and the added clip's resets return its
own framing. Hand and screen independence is pinned at the
sliders: the hand photo never loads under jsdom, so hand frames
paint no pixels for the harness to read — the same limit the
base's own hand checks live with. The second check pins the
draft: the fields save, a reload restores the founder's Phone
size whole, and a stored draft with the nine keys stripped (a
pre-0266 draft) reopens on defaults.
