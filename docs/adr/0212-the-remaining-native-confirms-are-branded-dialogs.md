# 0212 — The remaining native confirms are branded dialogs, and the long-save notice is shorter

Status: accepted

## Context

The strategy panel asks before one specific rebuild: the plan has
moved on since the strategy was built, or the picked audience
angle changed. That rebuild discards a strategy written against
an older plan or a different angle, and the render follows the
newer one — the one click in the flow whose cost is invisible
unless it is stated. ADR 0203 tightened the wording ("Rebuild
from plan v7? This replaces the strategy built from plan v1,
and the render will follow the newer one."), but the words still
arrived in the browser's own confirm box: plain system chrome,
one run-on sentence, none of the app's design language.

Kasra hit that box on Nov 19 2026, after the regenerate-angles
confirmation had been branded the same evening (ADR 0210), and
his order was direct: get it branded too. Asked whether other
plain pop-ups remained, he was told three more native confirms
existed — the re-roll ("Generate another"), deleting an asset
that projects still use, and regenerating the plan — and ordered
the whole set branded in the same conversation ("Yes").

In that same conversation he also approved a shorter long-save
notice for the render panel (ADR 0179's notice, shortened once
on Nov 18): the three lines he settled on are recorded in
decision 6 below.

## Decision

1. **Every remaining browser confirm is replaced by the shared
   Dialog.** Each confirmation wears the same treatment as the
   delete-render and regenerate-angles dialogs
   (`frontend/src/components/ui/dialog.jsx`): a title, a short
   description, the consequences as a plain list, and the
   decision in the footer — Cancel in ghost, focused first, and
   the action in accent. Each lives in its own component under
   `frontend/src/components/studio/`, rendered by the surface
   that owns the action.
2. **The strategy rebuild (the lead case).**
   `StrategyRebuildConfirmDialog.jsx`, rendered by the strategy
   panel (`HookContinuityPanel.jsx`) itself, the only place the
   rebuild lives. Title: "Rebuild the strategy?" Description:
   "Build a fresh strategy from plan v{new}." Consequences: it
   replaces the strategy built from plan v{old}, and the render
   will follow the new strategy. The angle variant shares the
   card: a fresh strategy for the newly picked audience angle,
   replacing the strategy built for a different angle, same
   closing line.
3. **The re-roll.** `GenerateAnotherConfirmDialog.jsx`, rendered
   by the render panel (`GenerationPanel.jsx`). Title:
   "Generate another video?" Description: "This runs a second
   render from this plan." Consequence: the video you already
   have stays in History.
4. **Deleting an asset in use.** `DeleteAssetConfirmDialog.jsx`,
   rendered by the Asset Library (`AssetLibrary.jsx`), which
   hosts the library both standalone and embedded in the wizard.
   Title: "Delete this asset?" Description names the use: "It
   is used in N project(s) (names)." Consequence: deleting it
   removes the face reference from those projects until a new
   one is attached. An asset used nowhere never sees the dialog;
   it deletes on the click, exactly as before.
5. **Regenerating the plan.** `PlanRegenConfirmDialog.jsx`,
   rendered by `CreateVideo.jsx` beside the regenerate-angles
   dialog. Title: "Generate a new plan?" The no-edits wording
   keeps ADR 0203's approved facts, split so each is said once:
   description "This discards plan v{version}.", consequence "A
   new plan is generated in its place." With unsaved edits, the
   description is "You have unsaved edits." and the consequences
   are that a new plan replaces this one and the unsaved edits
   are lost.
6. **The long-save notice is shorter.** The render panel's
   long-save notice (ADR 0179) now reads: "Your render is
   finished. The save is just slow, not stuck. It will appear
   here and in History the moment it lands." Nothing else about
   the notice changes: it still appears only after 120s of
   watched saving, and the panel still never gives up polling.
7. **Each ask fires exactly where it fired before.** Only a
   rebuild that would discard a strategy built from an older
   plan version or a different angle asks; a first build, an
   ordinary rebuild of a current strategy, and the suggestion
   modal's accept/keep paths run with no dialog, exactly as
   before. The re-roll asks only when a generation already
   exists; the asset delete asks only when the asset is in use;
   the plan regeneration asks on the same button it always did.
8. **Every spend stays behind its answer.** Each host holds the
   pending confirmation and the promise the click is waiting on.
   Opening a dialog calls nothing; confirming runs the action
   once; cancelling, closing, or unmounting resolves the wait
   as a refusal. A second click while the plan dialog is open
   is dropped, so a double-tapped Regenerate still starts
   exactly one plan generation.

## Alternatives rejected

- **Keep `window.confirm` and only shorten its text.** The same
  half-fix ADR 0210 rejected: the box belongs to the browser,
  not the app, and cannot wear the delete dialog's treatment.
- **Ask on every rebuild or delete.** A current strategy's
  rebuild and an unused asset's delete are harmless and stay
  one click; interrupting them every time would teach the
  founder to dismiss the prompt without reading — the exact
  habit the ask exists to prevent where the cost is real.

## Consequences

No native `window.confirm` remains anywhere in the frontend:
every destructive or discarding confirmation now wears the one
branded treatment — profile and render deletion, angle
regeneration (ADR 0210), the stale-strategy rebuild, the
re-roll, the in-use asset delete, and the plan regeneration.
The render-smoke checks that stubbed `window.confirm` for
these paths are rewritten against the real dialogs: they pin
each branded copy, prove opening and cancelling spend nothing,
confirming spends exactly once, the direct paths still open no
dialog, and the double-tapped Regenerate still lands on one
dialog and one generation. The long-save smoke pin carries the
new wording.
