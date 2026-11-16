# ADR 0164: Video fit is individual per clip

Status: accepted

## Context

Reviewing the Demo + CTA editor's sections on Nov 15 2026,
Kasra asked whether the insides of each group matched the way
the app works. The finding: the Video crop block — fit
(Cover / Contain / Fill), the hint naming what each mode does to
the source, Zoom and H/V offset sliders, Reset — existed only
for the base clip, inside Source & Look's Fine-tune framing.
The Second clip group carried the added clip's own style,
scene, backdrop, transition and audio (ADRs 0029/0030), but no
crop treatment at all. What the added segment did instead
depended on the view: in Real Video it painted with a
hard-coded cover at 1x with zero offsets; in the phone views
(floating, static, hand) it painted with the base clip's fit
and lock-resolved zoom. Three behaviours, none of them the
added clip's own choice. His order: "I want that to be
individual for both the first video clip and the second."

## Decision

**The Second clip group carries a complete Video crop block of
its own.** The same block the base carries — an `AppSelect`
fit pick (Cover / Contain / Fill, `CONTROL_CLASS` skin, ADR
0163: no native select), the consequence hint naming the
ADDED clip's source size, Zoom and H/V offset sliders over the
base block's ranges, and a Reset — shown when the added clip
has loaded (`appendMeta`), beside the transition, scene and
audio controls that arrive with it. Its state is its own
(`appendVideoFit`, `appendVideoScale`, `appendVideoOffsetX`,
`appendVideoOffsetY`), defaulting to Cover / 1x / 0 / 0. The
base clip's block, state and behaviour are unchanged.

**One painter, resolved per segment.** Preview and export call
the same `paintFrame` (`usePreviewLoop`); the export names the
segment for every decoded frame it hands the painter. The
painter now resolves the crop once per frame — `segFit`,
`segScale`, `segOffX`, `segOffY`: the base from its fit state
and its lock-resolved framing (`ez`), the added segment from
its own four values — and every renderer branch (hand, Real
Video, floating phone, static phone) consumes the resolved
values. The hard-coded cover/1x the added segment used to get
in Real Video is gone; there is no mode left in which a
segment paints with another clip's crop or a silent default.

**What stays shared, deliberately.** Hand framing (hand zoom
and pan), phone size, the mockup geometry and the zoom locks
themselves stay shared: they are the one stage both segments
stand in, and the locks are the base's framing timeline. The
added clip's crop is a fixed treatment, not a second lock
namespace. Before this change the locks did reach the added
segment's crop in the phone views; that reach is exactly what
"individual" removes. Locks still govern the base's crop and
the shared geometry across the cut.

**The state rides the edit document** like the added clip's
other per-clip values (its look, its mute): the four values
are `editSnapshot` keys with `restoreEdit` setters (the draft
parity check counts them), they join `exportEditKey` so a
crop change invalidates a stale export, and `removeAppend`
resets them to the defaults as it resets the clip's other
state. Replacing the second clip keeps its crop, as it keeps
its look — the treatment belongs to the slot, the trim
belongs to the file.

## Pins

The render smoke suite gains "the second clip carries its own
video crop, independent of the base", red before green: a
mounted editor in Real Video with a 1920×1080 base and a
720×720 added clip, reading the drawn boxes off the stubbed
canvas. It asserts the block exists with the app-drawn fit
menu offering exactly cover / contain / fill and a hint
naming the added clip's own source size; the defaults (each
clip covers, on its own geometry); the added clip's Contain
(its box moves to the padded square, the base's box does not
move); its own Zoom run to 3x (the painted box follows); the
export's `drawFrame` painting segment 1 with the added clip's
crop, not the preview alone; the base then taking Fill (the
added clip unmoved); and Reset returning the added clip to
Cover at 1x. The draft parity check holds at 56 snapshotted
fields, the four new ones included.

## Consequences

- A founder can frame a mismatched second clip — a square
  screen recording after a portrait base — without re-cropping
  the base, and the export records the same per-clip crop the
  preview showed, because there is only the one painter.
- The painter has one crop resolution point. A future
  per-segment framing control extends the `seg*` values rather
  than adding a fourth mode-specific path.
- A founder who relied on a zoom lock to move the second
  clip's crop in a phone view will find the lock no longer
  reaches it: the Second clip group's own block is where that
  framing now lives. The locks' other work — the base's crop,
  the shared hand and phone geometry — is untouched.
