# 0109 — No screen surfaces in generated clips; Location never opens as a fragment

- **Status:** accepted
- **Date:** 2026-11-07
- **Anchors:** `backend/final_beat.py`
  (`_SCREEN_INTERACTION_RE`, `_SCREEN_SURFACE_RE`, `split_screen_clauses`,
  `split_phone_clauses`, `split_phone_mentions`, `strip_props`),
  `backend/scene_consistency.py` (`is_location_fragment`,
  `place_anchor_from_text`, `repair_location_fragment`, lighting-clause
  guard, `reconcile_scene` post-split anchor),
  `backend/angle_scene.py` (`angle_moment`, `_development_beat`),
  `backend/angle_policy.py` (`normalize_content_angles`),
  `backend/claim_safety.py` (`_SELF_UNDERSTANDING_DOMAINS`),
  `backend/ai_service.py` (`_generated_spoken_issues`, selfie rules),
  `backend/server.py` (`_serialize_angle_row`, `_public_project`,
  `update_studio_project`, `_submit_generation`, `_guard_render_scene`);
  tests `backend/tests/test_final_beat.py`,
  `backend/tests/test_scene_consistency.py`,
  `backend/test_claim_safety.py`, `backend/test_template_relevance.py`
- **Shapes:** extends ADR 0093/0097 (selfie never shows a phone or a
  second hand) and ADR 0108 (setup owns wording, plan owns shape)
  without overturning either. The phone rule widens from "a second
  device" to "a screen surface on that device", and the bounded-by
  grammar gains the knowledge-result shape ("Now I know ...") as a
  diagnosis-domain benefit.

## Context

A later handmade video read, item by item, as one drift rather than five
unrelated typos: Location was the tail clause "with grass and trees
behind"; Movement and the middle's "What they do" scrolled a "weekly
chart" by thumb while one hand gripped the rail and the other held the
camera; the script asserted the week "appears on screen" though Props
showed no chart; the angle's promise and the template shape promised
the same chart on a phone; and the script promised
"Now I know how long it's been there" while its own bounds said trends
are shown, not diagnosed. The demo clip that follows already shows the
app, so a generated clip asking that same chart appear on screen is
unfilmable, not merely unnecessary.

## Decision

- **Screen surfaces are phone-second under selfie rules.** Clauses that
  look at, scroll, swipe, or tap a chart/graph/screen/report/dashboard —
  or thumb-tap/scroll on the phone's behalf ("thumb taps once to scroll",
  "scrolls my week") — are forbidden in action/direction wording for
  selfie across hook concept, hook/middle action, Movement, Props,
  Framing, and Position. The `Stop the scroll` idiom (a viewer swiping
  past) and negated rules ("no chart on camera") survive. Spoken words
  are never rewritten or refused for this.
- **The chart leaves the video entirely.** Actions become the physical
  beats the hand can actually do: railing grip, exhale, glance down,
  snap back to the lens. Props never lists the chart; Framing never
  promises it. The script no longer narrates "I scrolled my week" or
  "saw the worry come back on Monday": the demo shows the app, the
  generated clip speaks on leaning, breathing and naming.
- **Location never opens as a fragment.** A clause that is mostly light
  or time ("Soft natural daylight from the side") is never read as a
  carried object by its tail ("the side"); direction words (`side`,
  `front`, `back`) are excluded as objects; `railing` is scenery. When
  the surviving place is a continuation fragment, the promise's own
  anchor ("A park railing") is prepended on generate, save, display,
  render-where, and guard — a deliberate founder place (non-fragment) is
  never rewritten.
- **Promises never promise screen work.** Angle `hook_promise` values,
  card shapes, and template developments strip screen-interaction
  clauses before save/display, leaving the place/task clause
  ("Leaning on a park railing"). Stored angles keep theirs once
  normalized.
- **Knowledge results defer to diagnosis bounds.** `bounded_by_conflict`
  maps "now I know" / "know how long" benefits to the diagnosis domain,
  so a final line (and any spoken novel sentence in generation) promising
  a length/trend the angle forbids diagnosing is refused at render or
  rewritten at plan time, while a self-understanding close still needs a
  self-understanding bound to block it.

## Alternatives rejected

- **Patching the Textarea or prompting once.** A display-only location
  patch would leave the prompt broken, and the model writes the second
  sentence after any hint; the strip and anchor run at every save/display/
  render boundary instead.
- **Bespoke two-hands thumb rule.** The chart-scroll clause is the same
  impossible second-hand clause as the rail-grip/thumb pairing, so it
  rides the existing strip rather than a hand-enumeration.
- **Blocking every "know" sentence.** "Now I know" blocks only when a
  diagnosis bound co-occurs; an unbounded angle may still voice a
  knowledge result, and a plain speaking close keeps every bound.

## Consequences

- An action field whose content was only screen work now repairs to its
  remaining physical clause rather than refusing; a Location that was
  only a screen clause still repairs to its anchor or a place noun.
- `Location` text "with grass and trees behind" repairs to
  "A park railing, with grass and trees behind"; "from the side" lighting
  residue is dropped with the light move and never re-attached.
