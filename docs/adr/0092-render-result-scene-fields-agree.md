# 0092 — Render & result scene fields agree before render

- **Status:** accepted (props scope refined by 0103: Props names what the person carries, wears or uses, never scenery; Movement cap raised to 600 and overflow made advisory by 0104)
- **Date:** 2026-11-04
- **Anchors:** `backend/scene_consistency.py` (`split_location`,
  `reconcile_scene`, `clean_placeholders`), `backend/server.py`
  (`_guard_render_scene`, `update_studio_project`'s Location branch),
  `backend/ai_service.py` (strategy schema + rules, `normalize_strategy`),
  `frontend/src/components/HookContinuityPanel.jsx` (the scene helper and the
  "What the viewer ends up with" block); tests
  `backend/tests/test_scene_consistency.py`; smoke checks "Review offers one
  delivery control, not two", "the strategy review shows what the viewer ends
  up with" and "the scene block points at the Location editor for its place"
- **Shapes:** extends ADR 0090 (Location is the single source of truth) and
  refines ADR 0084's scene ownership: the Render & result panel is read before
  money is spent, so its fields must literally agree with each other

## Context

The strategy review is the last thing a founder reads before paying, and every
field on it is sent to the video model. Four kinds of disagreement kept
slipping through:

1. **Location carried lighting and time.** The strategy prompt asked for "the
   place, visible surroundings, time of day and situational context" in one
   field, so "Kitchen at 7am, soft morning light" sat in Location while
   Lighting said something else — two statements of the same fact that could
   argue, with the render lock printing both.
2. **Props and Movement were incomplete.** The actions and the shot timeline
   name objects (a mug, a phone) and movements (stands, reaches) that never
   appeared in `scene.props` or `performance.movement`, so the founder read a
   timeline the locked scene did not describe.
3. **Internal wording leaked into scene values.** `camera_angle` and `framing`
   held the literal instructions "Use STARTING SHOT" / "Use STARTING SHOT and
   final-phone rule" — placeholder text for the prompt builder, shown to the
   founder as if it were a scene description.
4. **The viewer block's payoff row was labelled by when it is spoken** ("The
   last thing said") rather than by what the viewer takes away, and the three
   fields were not explicitly asked for from the viewer's point of view.

## Decision

`backend/scene_consistency.py` is the one place these invariants live, as pure
policy (no HTTP, AI, auth or persistence imports, guarded by
`test_architecture.py`):

- **Location is the place only.** `split_location` moves lighting words and
  time-of-day phrases out of a Location and into Lighting ("Kitchen at 7am" →
  Location "Kitchen", Lighting "…; 7am"). A Location that is only lighting
  text declines to split rather than being emptied. The split runs on save
  (`update_studio_project`), in the render guard, and in the strategy
  generator's approved-plan override; the stored `location` column keeps the
  place only, and the legacy `environment`/`background`/`setting` copies are
  overwritten with it so `merge_legacy_location` cannot resurrect the time.
- **Props and Movement are complete lists.** `reconcile_scene` reads every
  determiner phrase out of `hook_action`, both section actions and the
  timeline's action clauses and appends any object missing from
  `scene.props`; every action text not already covered by
  `performance.movement` is appended there. Body parts, places, times,
  lighting words and abstract nouns are never objects. A list that would
  exceed its size cap is **reported, not cut**: the render guard refuses with
  the field named and nothing charged.
- **Internal wording never survives.** `clean_placeholders` blanks
  `camera_angle`/`framing` values containing "starting shot" or
  "final-phone"; it runs in `normalize_strategy` (so the panel and every read
  are clean) and in the render guard (so an older row fixes itself before its
  prompt is built).
- **The viewer rows read from the viewer.** The payoff row is labelled
  **"What the viewer is left with"** (its text unchanged), and the strategy
  prompt asks for all three fields — desired_outcome, mechanism_beat,
  payoff_beat — written from the viewer's point of view. The scene helper
  text now points at where the Location is actually edited ("Render your
  Hook + Story below"), not at Review & submit.
- **Fix, or block.** Save-time rewrites report what changed in
  `location_change` (the panel shows it); the render guard re-runs the same
  pass and refuses the render, naming the field, when anything still
  disagrees — including the existing spoken-word block from ADR 0090.

## Alternatives rejected

- **Strip lighting/time at read/display only.** The prompt prints the lock
  from the stored strategy, so a display-only fix leaves the model reading the
  contradiction.
- **Let the model police its own scene.** It already produced these
  disagreements across ordinary strategies; the invariants are mechanical and
  belong in deterministic code, with the prompt rules as prevention.
- **Cut a too-long props list silently.** The founder would read a list that
  is missing objects the render will show — exactly the drift this closes.
- **Extract objects with a parts-of-speech model.** No new dependency for a
  conservative, reviewable heuristic; the determiner pattern plus the
  body/place/time/abstract exclusion sets is deterministic and testable.

## Consequences

- The Render & result panel reads as one self-consistent scene: place,
  light, time, objects and movement all say the same thing, in the fields
  they belong to.
- Older strategies gain the fixes on save, on read (placeholder cleaning) and
  at render; none of them need a paid rebuild for this.
- The strategy prompt grew by a measured 570 characters (ceiling 27,500 →
  28,500, pinned by `test_ai_json_calls`); the scene lists share the existing
  300-character field caps, and exceeding one blocks instead of trimming.
- The Location option lists on Review had their own lighting/time wording
  cleaned ("Quiet garden bench at golden hour" → "Quiet garden bench"), so
  picking an option cannot reintroduce the mix.
