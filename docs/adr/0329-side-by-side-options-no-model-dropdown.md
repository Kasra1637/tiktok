# 0329 — Few-option controls stand side by side; the model dropdown is gone

Status: accepted. Kasra's orders on the Nov 24 2026 call, from his
screenshot of HookSnap's hook card.

## Context

Four of Kasra's rulings land in one pass over the pickers.

He set a standing control rule: when a control has only two or three
options, show them side by side as selectable buttons — there is no
need for a dropdown; a dropdown is used only when there are four or
more options. His example was HookSnap's Hook length, which offers
only 4 and 5 seconds behind a full dropdown.

He gave the resolution picker the same treatment — its options
display in a row — and named the design: the buttons are black,
using the same thumbs up / thumbs down design as the History page's
video verdict buttons (the `.thumb-pair` row: small buttons, the
pick wearing the selected state).

He ordered the blank field area removed from HookSnap's hook line:
the dark empty field that stands in The spoken line area before a
hook exists looks obnoxious and long; only the generated hook should
show there.

And because HeyGen Video is now the only video model (ADR 0327), he
ordered the dropdown for video model selection removed — a picker
with one entry is not a choice.

## Decision

- **Hook length stands side by side.** HookSnap's Hook length
  renders its two options (4 seconds, 5 seconds) as the page's own
  pick pills (the shared `PickPills` row the Tone and Shape picks
  already use), not as a dropdown. The pick, its save and its
  default behave exactly as before.
- **Resolution stands side by side, in the verdict buttons'
  design.** In both render panels (Create's GenerationPanel and
  HookSnap's HookRenderPanel) the resolution dropdown becomes a
  `.thumb-pair` row of small black buttons — one per resolution the
  model offers, the model's default among them — with the pick
  wearing `thumb-selected`, exactly as a History verdict does. The
  row renders only when the model offers a real choice (a second
  resolution beside its default); a model with one resolution gets
  no control, as before. The pick still persists per project and
  still rides the render request; the default still sends nothing.
- **The model dropdown is removed from both render panels.** The
  catalog still loads and the panel still resolves the model the
  render runs on (the catalog's default, or a saved pick the
  catalog still offers); there is simply no control. Copy that
  pointed at the picker ("Choose a model above…") now names only
  the remedy that remains.
- **HookSnap's spoken line area shows no field before a hook
  exists.** The hook line editor renders only once a hook line
  exists, and stays rendered while the founder works on the page;
  before that, the area carries its label, its guidance and the
  Generate the hook button alone. This supersedes ADR 0254's
  standing that the area's editor renders gracefully empty from
  the first visit — on this page only; Create Video's Review keeps
  its always-standing editor.
- **Pinned by render-smoke checks**: the hook length pick is made
  by its buttons and still saves; the resolution buttons render
  for a model offering a choice and not for one without, the
  default stands picked, and a picked resolution reaches the
  render request; no model control renders in either panel; the
  hook editor is absent before a hook exists on HookSnap and
  present with the written line after.

## Not covered

- Other dropdowns in the app keep their form in this pass, even
  where they hold few options today; the standing rule applies as
  each surface is next touched, and the Focus dropdown (six-plus
  outcome lines) is a dropdown by the rule's own terms.
- The model-switch reset behavior the old dropdown carried is
  retired with it: with no switch there is nothing to reset, and
  its smoke check is removed rather than kept as a fiction.
