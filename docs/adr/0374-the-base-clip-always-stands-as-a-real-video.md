# ADR 0374: The base clip always stands as a Real Video — Base clip & look loses its style pick

## Status

Accepted, Nov 26 2026 — Kasra's direct order: "Please
remove the base clip style, floating phone hold, and
real photo of the demo plus CTA area only from base
clip and look area. So the video always applies a real
video as the first base clip and look." The change
lands in `frontend/src/demoCta/DemoCtaEditor.jsx` and
`frontend/src/demoCta/constants.js`; the tour copy that
pointed at the pick follows in
`frontend/src/lib/onboarding/tours.js`.

## Context

Base clip & look opened with a three-way style pick —
Floating Phone, Hand Holding, Real Video — and the
default was Floating Phone, so a founder's finished
render or uploaded footage arrived dressed as a phone
mockup unless they changed it. The two dressed looks
carried a train of controls behind them: a backdrop &
motion disclosure and a phone-size slider for the
floating phone; a scene grid, hand framing sliders and
a phone screen rect for the hand-held photo; a mockup
height block serving both. In use the pick earned
nothing on the base: the base is the founder's actual
footage, the full-frame presentation is the surface's
settled shape, and the choice — plus its twelve
sliders — stood between the founder and the work the
section is for. The Second clip's identical pick is a
different matter: an added clip is an insert, and its
presentation against the base is a real choice. It is
untouched.

## Decision

The base clip style is removed end to end, and the
base always applies Real Video:

- The base StylePicker leaves Base clip & look. The
  shared component stays — the Second clip's picker
  (`append-mode-*`) is its remaining consumer, in every
  mode, with its own env grid, backdrop & motion and
  fine-tune framing exactly as before.
- `DEFAULTS.viewMode` is "realistic", so fresh work
  starts as Real Video.
- Restore heals: `restoreEdit` applies any restored
  `viewMode` as "realistic", at the one funnel every
  restore passes through (the ADR 0351 pattern — a
  stored floating or hand draft, or an undo entry
  carrying one, lands at Real Video; the stored value
  no longer drives anything). The field
  itself stays in the snapshot and the plumbing: the
  painter resolves the base segment through it, and
  with the value pinned it always takes the realistic
  branch — the actual clip full-bleed, no phone, no
  scene. `exportFlow.js` reads the same pinned value
  unchanged. The painter's floating and hand branches
  are NOT removed: the second clip still paints
  through them per segment.
- The base-only controls that existed solely for the
  removed looks go with them, all inside Base clip &
  look: the floating Backdrop & motion disclosure
  (`source-style-details`), the hand scene grid, and
  inside Fine-tune framing the phone-size slider, the
  hand size & position block, the phone screen
  position block and the mockup height block (it sizes
  only the phone mockup, which a Real Video base never
  draws).
- Fine-tune framing keeps the Video crop — fit, zoom
  and offsets genuinely work in Real Video, because
  the realistic painter applies them to the whole
  canvas — and, the crop being its only remaining
  content, the disclosure itself now stands only once
  a clip is loaded.
- The look state (`bg`, `anim`, `envBg`, the screen
  rect, hand framing, phone scale, mockup stretch)
  stays in state and snapshots as plumbing: the
  painter still resolves the added segment's fallback
  backdrop, motion and scene from the base fields, and
  stored drafts carry them. Only the base's UI and its
  pinned value change.

## Checks

New, written red first:

- "the base clip always stands as a Real Video: no
  style or frame pick in Base clip & look (ADRs
  0374-0375)": a loaded base shows no `view-mode-*`
  control, no Base clip style label, none of the
  removed look controls; Fine-tune framing stands and
  carries the Video crop; and the Second clip's style
  picker still takes hand, floating and realistic in
  turn. (Its frame assertions are ADR 0375's half of
  the pin.)
- "a stored floating or hand edit restores with the
  base as Real Video (ADR 0374)": a fresh draft stores
  the realistic default; a tampered floating draft
  reloads painting the full-frame cover box and
  re-saves as realistic; a tampered hand draft heals
  the same way.

Changed, named per the house rule:

- "the second clip carries its own video crop,
  independent of the base": the opening click on
  `view-mode-realistic` is gone — the base starts
  there now. It still protects ADR 0164 whole: each
  clip's fit, zoom and offsets resolve per segment in
  preview and in the export's own paint, and neither
  clip's crop moves the other's.
- "the second clip carries its own fine-tune framing,
  independent of the base": the base-side slider
  driving (the base's phone size and hand rect read
  back after driving the added clip's) is replaced by
  absence assertions — the base offers no look sliders
  and no picker at all. Every second-clip assertion
  keeps its full strength: the painted phone grows by
  exactly its slider's ratio while the base's picture
  does not move, mockup height and its reset, hand
  framing and the screen rect standing only in hand,
  and the added clip's own resets.
- "multiple Real Video zoom locks preview new edits
  and replay zoom-in/out": replaces the pair of runs
  that drove the same lifecycle once per base
  presentation (hand, floating). The lifecycle now
  runs on the base's surviving framing channel — the
  crop zoom the canvas wheel and the crop slider
  share, read back as `vScale` — with every lifecycle
  assertion at its old strength: locks preview new
  edits, replay in and out across six timestamps,
  resolve in the export callback, replace in place,
  reveal their predecessor on removal, and clear. The
  hand/phone snapshot fields still ride in every lock
  (zoom.js is unchanged).
- "Real Video sequences History then upload with a
  presentation per clip": the closing base-mode
  sequence (hand base beside a hand upload, base scene
  asserted) is replaced by its post-removal truth —
  beside a hand-held upload the joined export still
  carries both segments, exactly one hand paint lands
  (the added clip's own scene), and no base picker
  exists to change that. It still protects the
  History-then-upload sequencing, per-clip
  presentation in preview and export, the mute
  defaults and the remove-recovers-export path.
- "Demo + CTA offers Real Video with a History render
  picker": the pick-and-pressed assertions became
  absence assertions — no view-mode control, no
  fine-tune disclosure before a clip, no phone-only
  controls anywhere. The History picker half (only the
  attachable render is offered) is unchanged.
- "no Advanced group: fine-tuning lives in Base clip
  & look": the marker split follows the new shape —
  the base block must carry the Video crop and must
  NOT carry the mockup-height or phone-screen-position
  markers, which now pin to the Second clip's mirrored
  disclosure. It still protects the five living
  groups, the no-Advanced rule, and the renamed
  phone-screen label discipline.
- "fine-tuning hides behind Fine-tune framing until
  opened": gained the assertion that the disclosure is
  gated on a loaded clip in source. It still protects
  the collapsed-by-default disclosure standing inside
  Base clip & look.
- Frontend-logic "defaults match the standalone app,
  the base look pinned to Real Video (ADR 0374)": the
  `viewMode` expectation follows the pin; every other
  default still matches the standalone app.
- The Jest fixtures in `exportFlow.test.js` and
  `sourceChangeClearsHistory.test.js` now hand the
  export flow `viewMode: "realistic"` — the only value
  the editor can pass it for the base. Both suites
  assert export-error history behavior, which never
  read the mode; the fixtures stay truthful about the
  call they model.
- The demo-cta tour's "Mockup or full-frame" step is
  retargeted to the second clip's picker and marked
  optional (the group stands only once a base exists),
  with copy that states the base's fixed presentation
  and the second clip's surviving pick. The tour-target
  audit still passes.

Unchanged, deliberately:

- "the second clip's fine-tune framing rides its
  draft, and drafts saved before it open on defaults":
  it never drove a base control.
- ADR 0370's chrome check: its icon patterns still
  resolve — on the Second clip's mirrored blocks,
  which keep their faces.
- The demo-cta draft gate: the draft shape does not
  change — `viewMode` was already a snapshot field.

## Alternatives considered

Ripping `viewMode` out of the snapshot, the painter
and the export: rejected — the painter resolves looks
per segment through the one field pair
(`viewMode`/`appendMode`), the second clip's modes
share those branches, and stored drafts carry the
field; healing the value is the smaller move and the
one ADR 0351 already proved. Leaving the look controls
standing but inert under a pinned Real Video: rejected
— a slider for a phone that is never drawn is a broken
promise on the section's face, and the order removes
the style, not just its effect.
