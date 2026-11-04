# 0090 — Location is the single source of truth; the hook opens on a visible move

- **Status:** accepted
- **Date:** 2026-11-04
- **Anchors:** `backend/angle_scene.py` (`reconcile_location`, `_drop_conflicting`),
  `backend/server.py` (`_guard_render_location`, `update_studio_project`'s Location
  branch), `backend/generation_planning.py` (`character_scene_lock(strategy, location)`,
  the `WHERE THIS HAPPENS` prompt line, the opening rule),
  `backend/ai_service.py` (`generate_video_strategy` schema + rules),
  `frontend/src/components/GenerationPanel.jsx` (`render-location-input`);
  tests `backend/test_location_source.py`; smoke checks "the render panel edits
  the Location and reports what was rewritten" and "the Location editor names
  spoken words it will not rewrite"
- **Shapes:** extends ADR 0084 (the angle owns the scene — its lexical detector
  and direction dropdowns are unchanged); the new rule is that once the founder
  edits the plan's `visual_direction`, THAT text is the place, and every
  strategy copy of the place follows it

## Context

The angle opened the video somewhere (ADR 0084), but the strategy kept its own
copy of the place — `scene.location` on the current schema, split across
environment/background/setting on older rows — and the render lock read the
strategy, not the plan. Editing the plan's Location could therefore not change
the video: the older strategy text won at the lock every time, on the one
surface where the founder had just moved the shoot. Reviewing a Location edit
only marked the strategy stale, which forced a paid model rebuild whose only
job was to repeat the new place into lines that already existed.

The place was also named in several prompt sections at once, so a strategy built
before an edit competed with the plan's own location text in the same prompt.

Separately, the hook's first on-screen beat was instructed only as what NOT to
do (no neutral pose, no fade, no greeting). The failure mode founders reported
was an opening that shows a talking head with no clearly visible move, and the
strategy was free to write an opening action with no movement in it.

## Decision

**Location.** The plan's `location` field (its `visual_direction` column is the
legacy mirror, kept in sync) is the canonical Location.

- A Location edit rewrites the strategy's place-bearing lines in the same save
  (`update_studio_project`): `scene.location` becomes the Location verbatim
  (and any legacy environment/background/setting copies are overwritten with
  it), and every other place-bearing direction line (hook concept, opening
  action, position in frame, hook/middle "what they do", movement, lighting,
  colour palette) loses only the clauses that contradict the new Location.
  Wardrobe, props, voice delivery, camera, framing, visual style and timing
  are never touched; the strategy stays current (its plan-version stamp is
  re-stamped to the same save), so moving a place name does not force a paid
  text rebuild.
- **Spoken words are never rewritten.** A hook line, dialogue direction or
  section script that still names another place is reported to the founder (on
  the save response: `location_change.blocked`) and refuses the render at
  `_submit_generation` with the field named and nothing charged.
- The render guard (`_guard_render_location`) re-runs the same rewrite before
  the prompt is built, so a strategy from another client or an older build still
  renders against one place.
- The final prompt names the place once: a `WHERE THIS HAPPENS` line carries the
  Location, and `character_scene_lock` skips the strategy's own location field
  whenever that line exists. The lock still carries lighting, wardrobe, props
  and performance.
- The Location is editable on the render step itself
  (`GenerationPanel`'s `render-location-input`), saved with one PATCH and
  re-marked ready, so the founder never leaves the surface they are reviewing.
  The Review step's own Location field (`review-location`) writes the same
  field; both paths run the same save-side rewrite.
- **Supersedes the invalidate-then-rebuild flow** for Location edits: a Location
  change no longer marks the strategy stale. The rewrite is deterministic and
  the render guard re-checks it, so a paid rebuild buys nothing a save already
  did. `backend/tests/test_location_regression.py` pins the new contract.

**Opening movement.** The hook's first beat is a visible move.

- `generate_video_strategy` requires it in the rules and in the `hook_action` /
  hook `action` schema lines: inside the first 1-2 seconds the viewer watches a
  movement, gesture or position change (step, turn, stand, sit, reach, lift,
  place, grab), fitting the scene's place and time, before any words.
- The render prompt's opening directive states the same requirement as what must
  be ON screen, in both the full and condensed fixed text. The wording was
  retightened in the same pass so the measured fixed floors did not grow — the
  full floor actually fell (4,269 → 4,231) and HeyGen's 4,090 ceiling still
  clears the saturated case.

## Alternatives rejected

- **Rebuild the strategy on every Location change.** A full model call to move a
  place name repeats what the founder just wrote, costs a call, and re-rolls
  unrelated copy. The deterministic rewrite touches only the place lines and
  leaves an escape hatch: the founder can still rebuild deliberately.
- **Let the strategy keep its place and treat Location as a hint.** That is the
  bug this record closes: the lock read the strategy, so the hint lost.
- **Rewrite spoken words automatically.** The spoken line is what the founder
  approved hearing; substituting a place inside it silently changes the script
  they signed off. Reported and refused instead.
- **Detect room-to-room moves lexically (kitchen → living room).** The detector
  is conservative by design (ADR 0084): it reads indoor/outdoor and time of day
  only. The scene's place fields are replaced outright, so the older room text
  still cannot win where it matters; prose-level room names in direction lines
  are only rewritten where the detector can see a contradiction.
- **Add the opening rule as new fixed prompt text.** There was ~30 characters of
  measured headroom on the tightest ceiling. The rule was folded into the
  existing opening directive and paid for by cutting its own redundancy,
  verified by the floor pins and the per-provider ceiling tests.

## Consequences

- Location is one edit with one write path; the render prompt has a single
  authoritative place line and no competing copies.
- The save tells the founder exactly what changed and what only their own edit
  can fix (the spoken `blocked` list). The render refuses rather than speaking
  a place the founder moved away from.
- Strategy prose that merely mentions a place but is not on the enumerated list
  (summary, problem, pitch beats) is rewritten only by the render-time audit
  (clause-drop), not by the save; those fields remain the founder's text
  otherwise, and rebuilding regenerates them fully.
- The opening is now required to show a visible move; a strategy whose hook
  action has none is invalidated by the prompt contract, and the next strategy
  rebuild writes one.
