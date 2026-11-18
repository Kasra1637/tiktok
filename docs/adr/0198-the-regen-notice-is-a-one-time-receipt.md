# ADR 0198: The regen notice is a one-time receipt — and its Dismiss works

Status: accepted

Kasra reported three things about the "Regenerated. N drafts
were planned around angles that no longer exist…" banner: it
lingered while he was about to generate, it showed in two places
saying the same thing, and clicking its Dismiss button did
nothing — the banner stayed.

## The dead Dismiss: the defect, named

`angleRegenNotice` lives in `useWizardAngleStep`, which returned
the value but **never returned its setter**. Both Dismiss
handlers in `CreateVideo.jsx` called
`() => setAngleRegenNotice(null)` — an identifier that does not
exist in that module. Creating the closure was harmless; the
click resolved the name, threw a ReferenceError inside the
event handler, and the state never cleared. The banner stayed
because the button was wired to nothing. No test caught it
because the smoke suite asserted the notice and its action, but
never clicked Dismiss.

## Decision

The notice is a one-time receipt for one regen event, with a
defined lifecycle:

- **Before the click, the cost is named.** A read-only preflight
  (`GET /app-profiles/{id}/content-angles/regen-impact`) runs
  the same count the regen endpoint reports afterwards
  (`_regen_projects_affected`, one helper, two readers). The
  confirm fires exactly when that count is non-zero — any draft
  on the profile planned around a generated angle, not only the
  draft on the selected angle the old confirm covered — and its
  text names the count, that hand-written angles are kept, and
  that each affected draft keeps its draft but loses its story
  and needs its strategy rebuilt at Review. A failed preflight
  falls back to the old selected-angle check rather than
  dropping the warning or blocking the click.
- **One place.** The receipt renders only on the angle step,
  with its "Go to Review and rebuild" action. The duplicate on
  Review's gated angle selector is removed: Review's signal is
  its own live enforcement (rebuild button shown, Generate
  hidden), which cannot go stale.
- **It clears itself.** The receipt clears when the founder
  dismisses it (the hook now exports `clearAngleRegenNotice`,
  which both the Dismiss and the lifecycle use), leaves the
  angle step, picks a different angle, or completes the owed
  strategy rebuild (`HookContinuityPanel` reports a successful
  build up to the page). Once cleared by any route it never
  reappears for that regen — nothing re-derives it; it is set
  only inside the regenerate handler, from the endpoint's
  count, and a count of 0 sets nothing.

## Consequences

Smoke pins in `frontend/scripts/check-render-smoke.cjs`:
dismiss → navigate steps → notice stays gone; a regen with
`projects_affected: 0` shows no notice; the confirm names the
cross-draft cost and declining it spends nothing. The backend
count is pinned in `test_template_library_api.py` (drafts on
generated angles count, drafts on hand-written angles do not —
regeneration keeps those rows). The pre-existing notice check
(action lands on Review) still passes unchanged.
