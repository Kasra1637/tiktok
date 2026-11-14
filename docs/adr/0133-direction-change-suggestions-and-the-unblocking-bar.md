# 0133 — Direction-change word suggestions, and the bar carries the one unblocking action

- **Status:** accepted
- **Date:** 2026-11-13
- **Anchors:** `backend/routers/studio.py` (`DIRECTION_FIELDS`,
  `_direction_snapshot`, `_strategy_direction_changes`,
  `suggest_strategy_refresh`, the `direction_snapshot` stamp in
  `generate_project_strategy`), `backend/test_strategy_suggestions.py`,
  `frontend/src/components/HookContinuityPanel.jsx` (the suggestion
  modal, the registered bar action), `frontend/src/pages/CreateVideo.jsx`
  (the sticky bar's primary slot), `frontend/src/components/GenerationPanel.jsx`
  (the matched rebuild label). Extends ADR 0090 (location edits reconcile
  the scene, never the words) and ADR 0122 (navigation generates nothing).

## Context

Two frictions in Review, both named by the founder from live use.

**The words outlive the direction.** The strategy binds to the saved plan
verbatim, and a Visual & audio direction edit reconciles the strategy's
scene in the same save (ADR 0090) — but the spoken words are deliberately
never rewritten by a save. Edit the location from a bus stop to a garden
and the rebuilt strategy films the garden while the hook still says
"bus stop". The founder's fix is not a silent rewrite: the approved words
are theirs, and generation may only *offer* better ones.

**The bar did not drive.** The sticky bottom bar showed a locked forward
arrow on blocked steps while the action that would unblock the step sat
somewhere up the page. One state already worked the right way — a ready
Review carried "Go to render" in the bar — but it was a special case.

## Decision

**Stamp the direction at build time.** The strategy build writes
`direction_snapshot` (location, visual_direction, voice_direction,
sound_direction, as saved on the project row at that moment) inside the
strategy JSON itself — the record it describes carries it, like the angle
stamp, so no parallel tracker exists to drift. A strategy built before
the stamp has no snapshot: the diff is unknown, and unknown never fires
the popup.

**Suggest before rebuilding, never apply before the choice.** The
rebuild click first calls `POST /studio/projects/{id}/strategy-suggestions`:

- No strategy, or no field differs from the snapshot → the endpoint
  answers `direction_changed: false` **without a model call** and the
  click rebuilds exactly as before. The check is free; only a real
  change spends a generation.
- A difference → the plan's words are regenerated for the current
  direction through the same machinery the plan route uses (same prompt
  inputs, same arrival partition), and gated by the craft scorer: the
  suggested hook must score at least the saved hook on hook stopping
  power, or only the script is offered; a pair identical to the saved
  words is no suggestion at all.
- A suggestion opens the **Suggested update** modal: saved words beside
  the refreshed pair. **Accept** saves the new words through the normal
  plan-save path (the plan version bumps) and then rebuilds, once,
  against them. **Keep mine** writes nothing — the saved words stay
  byte-identical — and rebuilds against them. The modal choice replaces
  the version confirm for that rebuild: the founder just decided with
  the words in front of them.
- A provider failure is a 502, and the client falls back silently in
  flow but honestly in copy: the rebuild proceeds with the saved words
  and a note says suggestions were unavailable. The popup never blocks
  a rebuild.

**One rebuild label.** Every surface that offers the strategy rebuild
reads "Rebuild strategy", and the first build reads "Build the strategy"
— the panel button and the render panel's remedies alike. The reason a
rebuild is owed stays in the alerts that already explain it; two
phrasings of one action read as two actions.

**The bar carries the one unblocking action, on every step.** The
sticky bar's primary slot generalizes the "Go to render" state: while
the step in view is blocked, the slot shows the blocking section's own
button — same handler, same busy/countdown behavior, anchored where
the flight began (the strategy panel registers its action with the page
while Review is in view) — and no forward arrow shows beside it: one
working action at a time, the rule Review's render button already
followed (51f56d8), applied to the bar. In-flight generations mirror
their progress in the bar. When the step can proceed as-is, there is no
bar action and the arrow is the way forward. Two deliberate exceptions:
content picks (an angle card, a goal, a template, a photo) are clicks,
not buttons, so those states keep the locked arrow and the hint line;
and the first-gap buttons are never mirrored, because exactly one
'first' action ever renders.

## Consequences

A direction edit after a build no longer strands the words: the founder
is offered a refreshed pair, in context, at the moment they act — and
the offer costs nothing when nothing changed. The bar now answers "what
do I press next" identically on every step: whatever is in its primary
slot is the thing to press.
