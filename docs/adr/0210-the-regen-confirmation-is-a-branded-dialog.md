# 0210 — The regen confirmation is a branded dialog, and its receipt is short

Status: accepted

## Context

Kasra's screenshot on Nov 19 2026 showed the regenerate-angles
warning as the browser's own confirm box: plain system chrome,
one long paragraph, and none of the app's design language. His
order was direct — update this message box to be branded just
like the delete message, and keep it concise.

A second screenshot showed the receipt that follows a completed
regeneration. It restated the whole cost in three sentences,
including an instruction to pick a new angle and a closing line
saying this draft already had one — two instructions that read as
if they contradicted each other. He ordered that shortened along
with the confirmation.

## Decision

1. **The browser confirm is replaced by the shared Dialog.** The
   regenerate-angles confirmation now wears the same treatment as
   the delete-render dialog (`frontend/src/components/ui/dialog.jsx`):
   a title, a short description, the consequences as a plain list,
   and the decision in the footer — Cancel in ghost, focused first,
   and the action in accent. The component is
   `frontend/src/components/studio/AngleRegenConfirmDialog.jsx`,
   rendered once by `CreateVideo.jsx`.
2. **The copy follows ADR 0203 — each fact once.** Title:
   "Regenerate angles?" Description: fresh angles replace the
   generated ones, and hand-written angles stay. Consequences:
   affected drafts keep their drafts but lose their stories, and
   each affected strategy is rebuilt at Review. Nothing else is
   said, because nothing else is at stake in the decision.
3. **The spend stays behind the answer.** `useWizardAngleStep`
   holds the pending confirmation (the preflight's affected count,
   or the generic fallback when the preflight fails) and the
   promise the click is waiting on. Opening the dialog calls
   nothing; confirming runs the regeneration once; cancelling,
   closing, or switching profiles resolves the wait as a refusal.
   The preflight itself (ADR 0198) is unchanged: the dialog fires
   exactly when a draft on this profile is planned around a
   generated angle.
4. **The receipt is the short form.** After a regeneration that
   cost drafts, the notice now reads "Regenerated. N drafts lost
   their stories. Rebuild their strategies at Review." — the
   outcome once, the next step once. Its Review action and Dismiss
   keep ADR 0198's lifecycle exactly.

## Alternatives rejected

- **Keep `window.confirm` and only shorten its text.** The words
  were only half the complaint; the box itself belongs to the
  browser, not the app, and cannot wear the delete dialog's
  treatment.
- **A type-to-confirm gate, like profile deletion.** Out of
  proportion: the drafts survive, the stories are rebuildable,
  and the cost is counted before the click. One clear decision is
  the right weight.
- **Drop the receipt entirely.** The confirmation says what
  *will* happen; the receipt is the only confirmation that it
  *did*, and its button is the straight path to the rebuild. It
  stays — shorter.

## Consequences

ADR 0203's say-each-fact-once standard stands; its note that the
regenerate-angles confirmation was checked and left unchanged is
superseded for presentation and receipt wording. The render-smoke
check that stubbed `window.confirm` is rewritten against the real
dialog: it pins the branded copy, proves opening and cancelling
spend nothing, confirming spends exactly once, and the receipt
carries the short form.
