# ADR 0290: An empty plan says so

Status: accepted

## Context

On Nov 23 2026 Kasra switched the camera to Fixed in Visual &
audio direction and landed on Create Video's Review & submit step
in a state that contradicted itself: the plan on file was "Plan
v1 · empty" — hook line, script and cover all blank — yet the step
read as ready, the sticky bar said "Ready — review the render
below" with Go to render lit, the blank form stood open with its
checks boxes, and Save edits was dead because there was nothing
to save. The readiness test explains it: the step counted itself
done on the plan's VERSION (script_version > 0) and never looked
at its words.

His order: when the plan on file holds no words at all — the only
state where the user MUST regenerate before anything else can
happen — hide the whole form and show only a notice that the plan
is empty and must be regenerated, with the Regenerate plan button
as the only action, carrying a pulsing animation like the final
generate-video button's, only when the click is required. The
Review step must not count itself done in that state, so Ready
and Go to render stay off until real words exist.

## Decision

- `planWordsMissing(project)` names the state: a script_version
  exists and both spoken fields are blank. `stepCompletion`'s
  review branch counts it "todo", beside the no-version case —
  so the rail, the bar's hint ("The plan is empty — regenerate
  it above to write it.") and the bar's actions all agree the
  step is unwritten, and the done-branch that lit Go to render
  never fires.
- In Read the plan, when the state holds and no spoken edit is
  pending, everything below the regenerate row — verdict
  evidence, the Script label, the template aim, the hook, script
  and cover fields, the checks, the Save edits row — is replaced
  by one notice: "This plan is empty", with the one sentence
  naming the remedy. The Regenerate plan button in that state
  wears `.generate-invite`, the final Generate button's pulse;
  outside the state it never does.
- A pending hook or script edit stands the state down — the form
  stays so the founder's words can be saved — and the full page
  returns the moment a regeneration lands words. A plan holding
  words is never hidden; a strategy-rebuild state keeps its own
  notice, untouched.

## Consequences

The empty state can no longer masquerade as ready anywhere the
founder looks: not in the form, not in the step's state, not in
the bar. One pulsing button is the only action, which is the
truth of the state — regeneration is the only way forward from
an empty plan.
