# ADR 0361: No direction button is picked until it is clicked

## Status

Accepted, Nov 25 2026 — Kasra's order on a voice call: "by
default no button should be selected or active. Every button
should be off by default unless user click." His example:
under Voice, "Character stays silent" stands active by
default on a fresh project, and it must not.

## Context

Create's direction pairs derived their picked face from
`editValue(key, fallback)` (`frontend/src/pages/CreateVideo.jsx`):
the draft edit if one exists, else the project row's value,
else a hardcoded fallback. A value always exists on that
chain, so one button of each pair always stood picked —
Handheld selfie in the camera pair, Character stays silent in
the voice pair — before the founder touched anything.

The write side never agreed with that face. The draft
reducer's `edit-field` (`frontend/src/pages/wizardDraft.js`)
deletes the edit when the clicked value equals the standing
default (`omitDefault`): picking Handheld selfie or Character
stays silent stores nothing at all. The display was the only
place that called the default a pick.

What generation does when nothing is picked, grounded in the
code — this record changes no part of it:

- Camera setup: nothing the founder can click stores
  "handheld"; the stored row simply stands on the default
  every reader applies — `_public_project` serializes an
  empty value as "handheld" (`backend/routers/studio.py:265`),
  the column itself defaults to 'handheld'
  (`backend/schema.py`, the `studio_projects` column list),
  and strategy normalization does the same
  (`backend/ai_strategy.py:276`). Nothing picked renders
  handheld framing.
- Voice: a project born through `create_studio_project` has
  "silent" written explicitly at creation
  (`backend/routers/studio.py`, the ADR 0248 note at the
  insert) — a fresh project is silent at render because its
  row says so, not because a button was pre-picked. Rows that
  predate that rule carry 'talking' from migration step 10's
  column default, and an empty value reads as talking at
  submit (`backend/server.py`: `(project.get("voice_mode")
  or "talking") == "silent"`) and in serialization
  (`backend/routers/studio.py:269`). Nothing picked renders
  the row's standing voice: silent for any project created
  today, talking for a legacy row.
- Location & wardrobe already complied: their selects stand
  on a placeholder with no value until a pick is made. Tone
  has no control on Create (ADR 0102) and shape is a HookSnap
  pick, so on this page the defaulted-button family is
  exactly the camera pair and the voice pair — the two
  `edit-field` dispatches carrying `omitDefault`.

## Decision

The picked face and the effective value are separated,
display only. A new reader beside `editValue`,
`editPick(key, standingDefault)`
(`frontend/src/pages/CreateVideo.jsx`), returns the effective
value when it stands off the field's standing default
("handheld", "silent") and "" when it equals it. The camera
pair's picked test reads `editPick`, and `VoiceModeControl`
gains an optional `pickedValue` prop — the value its buttons
may show as picked, "" for none — which Create passes from
`editPick`. A caller that passes nothing (HookSnap, the
existing tests) keeps the control's original face, buttons
following the value itself.

Everything else keeps reading the effective value through
`editValue`, untouched: the camera pair's `data-value`, the
framing copy under it, the direction lists keyed on the
camera setup, the plan requests, and the render. The voice
note under the pair still follows the effective mode — on a
fresh project the character will be silent, so the note
naming the text-to-speech line stands, under a pair with
nothing picked.

The resulting rule, stated once: a stored value off the
default is a pick the founder made and stands picked,
including on return; a value standing on the default shows
no pick, whether it got there by birth, by the column
default, or by the founder clicking the default option —
which the write side has always recorded as no pick at all.

## Alternatives considered

Tracking provenance (a marker for "the founder clicked
this"): rejected — the row carries one value per field and
no marker exists; adding one is a schema change to answer a
display question, and the write side's own omitDefault rule
already defines picking the default as no pick.

Changing what is stored (writing "" instead of the birth
"silent", or dropping the creation write): rejected — that
changes generation semantics silently for every existing
reader (a fresh row would fall to the 'talking' coercions),
which this order does not ask for and the repo's no-silent-
fallback rule forbids. ADR 0248's birth pick stands.

Applying the face to HookSnap's direction card too: not in
this order — the call named Create's area and its example;
HookSnap's card keeps ADR 0246's face until Kasra rules on
it there.

## Consequences

The render-smoke suite gains a check (red before green): on
a project standing on both defaults, neither pair shows a
picked button while the camera group's effective `data-value`
still reads "handheld" and the silent note still stands; a
click earns the picked face in both pairs; and a saved
project carrying "fixed"/"talking" shows both picked on
return. `VoiceModeControl`'s unit test gains the unpicked
face (note: that Jest suite currently fails to run at all —
it cannot resolve the `@/lib/utils` alias, which only the
webpack config maps; the failure is identical on the tree
without this change and the suite is not the gate of
record). No existing check changed: the checks that drive
these pairs assert values, saves and reloads, all of which
read the effective value this record leaves alone.
