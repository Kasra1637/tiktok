# 0257 — Going back for a new location works, and the choice flows everywhere

Status: accepted

## Context

Kasra's live failure (Nov 21 2026, Create Video): he generated a plan
and a strategy, changed his mind, and went BACK to change the
location. Three things failed:

1. The location dropdown was EMPTY — no locations in it at all.
2. Clicking "New options" for the location generated NO options.
3. A new location did not update anywhere else it should — not
   through the templates and angles, not anywhere the location
   should display and work, front end or back end. His instruction:
   make sure it works without any issue and without any adverse
   effect.

Each failure was reproduced against the real endpoints before any
fix (red-first; the probes ran on a temp database with the test
suites' configuration):

**Failure 1 — two filters compose to nothing.** The direction-options
endpoint fits the static lists against the selected angle
(`angle_scene.fit_direction_options`, ADR 0084) and then, for a fixed
camera, keeps only locations the classifier calls indoor
(ADRs 0219/0220). With an angle that opens outdoors ("on the park
bench in the morning") and a fixed camera, the fit removes every
indoor option for contradicting the outdoor scene and keeps only the
angle's outdoor moment; the indoor filter then removes the moment.
No top-up runs after the camera filter, so the endpoint returns
`location: []`. Handheld for the same angle returns three options;
an indoor angle under fixed works. The plan's existence never
entered it — the endpoint is profile/angle/camera-scoped — which is
why the empty list appears exactly when a founder returns to the
step with an outdoor-opening angle and a fixed camera.

**Failure 2 — the refresh could filter a whole reply away, and the
page swallowed the empty success.** The refresh endpoint filtered
the model's four options through the angle's scene conflicts (and,
for fixed, the indoor rule) with no top-up and no retry: an
all-indoor reply against an outdoor angle, or an all-time-clashing
reply against a morning angle, returns 200 with `options: []`.
Under a fixed camera the two instructions fought outright — the
prompt demanded options fit the angle's exact (outdoor) place while
the endpoint discarded every non-indoor answer — so most fixed
refreshes emptied too. The frontend then treated the empty success
as "nothing to do": no merge, no error, a dead button.

**Failure 3 — the audit.** Every reader of the location was traced:

- **The save (PATCH project)** already carries a location edit
  everywhere it must: the stored place is split from lighting/time
  words, the `location`/`visual_direction` mirrors stay in sync, and
  when a strategy exists the same save rewrites its scene and
  direction lines (`angle_scene.reconcile_location` +
  `scene_consistency.reconcile_scene`), bumps the strategy version,
  and reports — never rewrites — spoken lines that still name
  another place (ADR 0090; pinned by `test_location_source.py`).
- **Staleness stays honest by design.** After a location save the
  strategy's build snapshot still holds the old place, so the drift
  diff fires (ADR 0133) and the render step owes the rebuild whose
  click offers refreshed spoken words (ADR 0142; pinned by
  `test_strategy_suggestions.py` and the render smoke). The snapshot
  is NOT re-stamped on a location save — re-stamping would silence
  the one signal that the strategy was built against another place.
- **Plan generation** reads the saved row's location into its brief
  (pinned: "the founder location reaches the prompt"), and strategy
  normalization takes the plan's location, falling back to the angle
  moment only when none is given.
- **The render prompt** is guarded pre-submit by the thorough
  reconcile (studio.py), so its place lines follow the saved
  Location even in prose fields the save left alone; the prompt
  names the place once, from the Location.
- **Templates and template fit** read the ANGLE and the camera
  setup (`template_angle_fit`), never the project's location pick —
  the pick is a plan input, not a template input (ADRs 0084/0224).
  Unchanged, deliberately.
- **Angles**: the stored angle is never rewritten by display logic;
  the displayed angle restates an outdoor place as its indoor
  version under a fixed camera (ADR 0233). Unchanged, deliberately.
- **The direction section's own display** was the one genuine
  defect: a saved place that no offered option contains (a refreshed
  option; the plan's own location words) read as an empty pick with
  no sign a place was in force — under handheld, no note at all;
  under fixed, a note asserting the saved place "is not an indoor
  location", which is false for a saved indoor place that simply is
  not in the fitted static list.

## Decision

- **The camera's indoor rule replaces the angle's place as the
  place constraint on the location list under a fixed camera** — in
  the options endpoint, the refresh filter, and the refresh prompt
  alike. The angle's time of day still binds everywhere. In the
  options endpoint, when the angle fit plus the indoor filter
  compose to an empty list, the list falls back to the profile
  group's own indoor places, still held to the angle's time. The
  dropdown therefore always offers locations in the reported state,
  Fixed stays indoor-only, and unclassifiable is still never
  permission (ADR 0219 stands).
- **The refresh prompt learns the camera.** `refresh_direction_options`
  takes `camera_setup`; for a location refresh under a fixed camera
  the angle block's fit sentence is replaced — the camera is FIXED
  and placed indoors, every location must be an indoor place, the
  angle's time still binds — and with no angle the fixed rule is
  stated on its own. The model is no longer asked for answers the
  endpoint is bound to discard.
- **A refresh that filters to nothing retries once, then fails
  loudly.** The endpoint re-asks once with the rejected options
  added to the avoid list (the house pattern of one bounded
  correction); if the retry also yields nothing usable it raises
  the standard 502 sentence (ADR 0242) instead of returning an
  empty list. The frontend hook matches it: an empty refresh
  success sets the same sentence as the field's refresh error
  rather than silently doing nothing.
- **The direction section names the place in force.** When the
  lists are loaded, a location is saved, and no offered option
  matches it, the section names the saved place beside the empty
  pick: under a fixed camera, "not offered for a fixed camera —
  pick an indoor location from the list"; otherwise, "not in this
  list — it still applies; pick a listed place to change it." The
  note never asserts the saved place's classification. The pick
  still changes only by choosing (click-to-generate and
  pick-to-save are untouched), and nothing regenerates on a
  location change — the ADR 0133/0142 drift-and-rebuild signaling
  remains the honest consequence.

## Consequences

- Kasra's exact state — plan and strategy generated, back at the
  direction step, outdoor-opening angle, fixed camera — now offers
  the group's indoor locations, "New options" returns fresh indoor
  options that fit the angle's time, and a hopeless refresh says so
  in words instead of dying silently.
- The handheld fit is untouched (the angle's moment still heads the
  list; a companion pin guards it), as are the ADR 0233 restatement,
  the stored angle, template fit's inputs, and the drift gate's raw
  diff (ADR 0146).
- A refresh that needs its retry costs one extra text call on that
  rare path; each attempt is logged like any other model call.
- Pins: five new backend tests (empty-list state, handheld
  no-regression, fixed refresh prompt+filter, bounded retry, loud
  failure), one new jest test (empty refresh success names the
  failure), two new smoke checks (the section names an unlisted
  saved place; the fixed note never misnames an indoor place). All
  four failure tests failed on the untouched tree with the reported
  symptom — an empty list where options belonged.
