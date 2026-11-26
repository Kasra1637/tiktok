# ADR 0373: A clicked pick is remembered as a pick — the silent voice button can be clicked

## Status

Accepted, Nov 26 2026 — Kasra's live bug report from
Create's Visual & audio direction section: "there is
also a bug that will not allow the character stay
silent button to be clicked, I can only tap on
character talks button not character stay silent
button. Fix that." VoiceModeControl is shared and the
cause sits in both pages' draft machinery, so the
repair lands in `frontend/src/pages/wizardDraft.js`
and `frontend/src/pages/CreateVideo.jsx`, and in
`frontend/src/pages/HookCta.jsx`'s own reducer and
read. The shared control itself is untouched: it always
rendered the picked face it was handed — what it was
handed was wrong.

## The cause

Two halves of the pick machinery cooperated to swallow
the tap:

1. The write side. Both draft reducers store an
   edit-field pick only when it differs from the saved
   row: a pick that restates the saved value is "no
   edit at all" (the omitDefault rule). A fresh project
   stands silent — the create endpoint wrote
   voice_mode "silent" (ADR 0248) — so tapping
   Character stays silent restated the saved value and
   stored nothing: no edit, no save, no state change
   of any kind.
2. The read side. ADR 0361's `editPick` (landed on
   HookSnap by ADR 0364) derives the picked face from
   the effective VALUE: a value equal to the field's
   standing default reads as no pick. So even where
   the tap did register — tapping silent from a
   talking draft stores the edit and saves — the
   silent button never lit: "silent" always reads
   back as "untouched".

Together: on a fresh project the silent button was
indistinguishable from disabled, and from any state it
could never show as picked. Character talks, standing
off the default, stored an edit and lit — the only
button that answered, exactly as reported.

## Decision

The draft learns the difference between "the field
stands at its default because nobody picked" and "the
field stands at its default because the founder picked
it": the click itself is remembered.

- Both reducers gain a pick record (`picks`) beside
  `edits`. An edit-field action carrying `omitDefault`
  and a value records `picks[field] = value` whether
  or not an edit is stored. Non-pick edits (the text
  editors ride the same action without omitDefault)
  never touch the record.
- Save adoptions (plan-accepted, picks-saved,
  project-received) keep the record: the pick survives
  the autosave settling, which a pending edit alone
  could not promise — an adopted edit is cleared, and
  a restating pick has no edit at all.
- A fresh draft clears it: both draft constructors
  start empty, and resume, profile switch and
  draft-opened all build fresh state. A reopened
  project therefore shows ADR 0361's standing faces
  again — nothing picked at the default, a stored
  off-default value picked — until the founder clicks.
- Both pages' `editPick` reads the record first: a
  recorded pick is the pick, at the default or off it.
  With no record, ADR 0361's rule stands verbatim.

Scope notes. The record is written by every omitDefault
pick, so Create's camera pair inherits the same repair
through the shared mechanism — Handheld selfie's
button was dead in the same way on a fresh project,
and a clicked handheld now stands picked; no camera
check pinned the dead face (the two checks that click
Handheld assert the indoor note's disappearance and
the saved place's return, not faces). HookSnap's
focus/tone/shape picks also write the record through
changePick, but nothing reads it for them — their
faces follow the effective value directly and are
unchanged. Generation is untouched: it reads
editValue, never the record, so what renders is
identical in every state — a fresh project still
renders silent, a clicked silent renders silent; only
the face now admits the click happened.

## Checks

New, written red first (both failed on the unmodified
tree at the first click assertion):

- "clicking Character stays silent picks it on Create
  (ADR 0373)": a fresh silent project shows no pick,
  the click lights silent (and not talking), the lit
  face survives the autosave settling, and the pair
  swings talking then silent off the record.
- "clicking Character stays silent picks it on
  HookSnap (ADR 0373)": the same pin on the other
  wiring, through the page's own harness.
- `wizardDraft.test.js` gains a reducer test: a
  restating pick stores no edit, is remembered as a
  pick, and survives a save adoption.

Changed, named per the house rule:

- `wizardDraft.test.js`'s three whole-shape
  expectations (draft-resumed, profile-selected, the
  createWizardDraft deep-link shape) gain `picks: {}`.
  They still protect what they always protected — a
  resume adopts all selections and discards edits
  together, a profile switch clears the draft
  atomically, deep-link picks initialize the same
  shape — over a state that now carries the record.
  (The Jest suite is not the gate of record in this
  environment — ADR 0364 recorded it cannot run here —
  but the file stays truthful.)

Unchanged, deliberately:

- "no direction button stands picked until the founder
  picks it" (ADR 0361): every assertion stands —
  untouched faces empty, clicked fixed/talking lit,
  saved off-default picks lit on return. It is the
  rule this repair completes, not revises.
- "a silent draft switches back to talking when the
  pill is tapped" (ADR 0248's regression, ADR 0364's
  read face): a saved-silent draft still opens
  unpicked, the note still renders, the tap on talking
  still picks and saves.
- "the silent pick saves, names the hook line for
  text-to-speech, and submits audio off": tapping
  silent from a talking row still saves silent and
  submits audio off. It never asserted the pill's
  face — which is how the dead face survived it — and
  the new HookSnap check closes that hole.

## Alternatives considered

Letting a click on the default store a real edit
(dropping omitDefault for voice_mode): rejected — the
edit would be adopted and cleared by the first save
flight, so the face would light on the tap and go dark
when the save landed, and the autosave would spend a
write restating the row's own value. Tracking the
click in the shared control's local state: rejected —
the control mounts inside cards and steps whose bodies
stay mounted hidden when collapsed (ADR 0356), so a
mount's memory is the wrong lifetime; the draft is the
state that already owns "what the founder has chosen
in this session" on both pages.
