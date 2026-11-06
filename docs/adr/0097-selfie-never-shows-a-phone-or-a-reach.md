# 0097 — A selfie never shows a phone, a reach, or a second free hand

- **Status:** accepted
- **Date:** 2026-11-05
- **Anchors:** `backend/final_beat.py` (`_PHONE_ENDING_RE`, `_PHONE_OBJECT_RE`,
  `_SECOND_HAND_RE`, `split_phone_clauses`, `strip_fields`, `forbidden_hits`),
  `backend/scene_consistency.py` (selfie Props/Movement completion),
  `backend/server.py` (`_guard_render_scene`: strip, then refuse),
  `backend/generation_planning.py` (`_SELFIE_FINAL_BEAT`,
  `_CONDENSED_SELFIE_FINAL_BEAT`, the setup-dependent opening and middle job),
  `backend/ai_service.py` (strategy and plan rules),
  `frontend/src/components/HookContinuityPanel.jsx` (setup-dependent copy);
  tests `backend/tests/test_final_beat.py`,
  `backend/tests/test_scene_consistency.py`, `backend/test_location_source.py`,
  `backend/test_generation.py`, `backend/test_influencer_workflow.py`
- **Shapes:** the whole selfie frame, not only its last second. It supersedes
  the exception ADR 0093 carved out for "reach for the phone"; ADR 0093's
  varied physical ending and the fixed-camera phone handoff both stand.

## Context

ADR 0093 ended a selfie on a physical beat and kept the phone handoff for the
fixed camera. It deliberately left one clause alone: "Reach for the phone" was
read as the story's handoff moment, not a device on camera, so it was allowed
to survive in the strategy's own fields.

That exception is what the founder hit. A handheld selfie is filmed with the
phone in the character's hand, so the character can never reach toward, hold,
raise or show a phone or camera, and one hand holds the camera, so no action
can need a second free hand. The middle still ended with "reaches a hand
toward the lens with her other hand" — two contradictions of the premise in
one line, in the field the founder reads before paying.

The completion pass of ADR 0092 made it worse: it copied every object the
actions named into Props, so a phone the founder's action mentioned came back
as a prop on a selfie, and the shot contradicted itself.

## Decision

- **Selfie (handheld) forbids four things:** reaching toward a phone, camera
  or lens; holding, raising, showing or lifting one; naming one as an object
  of the action (the camera IS the phone in their hand, so a second phone in
  frame is the recording device appearing as a prop); and any action that
  needs a second free hand.
- **A phone call is not a phone on camera**, so it is not forbidden.
- **Fixed camera keeps the phone handoff.** Both hands are free, the phone is
  on a stand, and the reach is filmable.
- **Fix, then block.** The forbidden clauses are removed from the opening
  action, the section actions, Movement, Props and the camera fields, and the
  Props/Movement completion pass can no longer put a phone back. If a field
  was nothing but the forbidden reach, there is no action left to film: the
  render is refused with that field named and nothing charged, rather than
  rendering a shot with an empty action.
- **Spoken words are never touched.** "I reached for my phone" is what the
  viewer hears, and the script is the founder's own. The hook dialogue is left
  alone for the same reason: the strategy schema lets it hold the exact words
  spoken, so stripping a clause from it could delete the founder's line.
- **One place states the rule.** The selfie final-beat section of the render
  prompt carries the prohibition (full and condensed); the opening, the middle
  job and the plan/strategy rules name the same stop in their own words. The
  fixed prompt text is load-bearing against the tightest provider ceiling
  (4,090), so the rule is stated once rather than three times.

## Alternatives rejected

- **Keep the reach for the phone, forbid only the ending.** The founder's own
  complaint: the middle still ends with a hand toward the lens.
- **Allow a phone on a desk.** In a selfie the camera is the phone in their
  hand, so a phone in frame reads as the recording device; the shot would
  argue with its own premise.
- **Block every selfie whose action mentions a phone.** An ordinary strategy
  that names a phone in passing would be refused for something the render can
  simply not film. Stripping keeps the render; blocking is for the case where
  stripping leaves nothing to film.
- **Rewrite the spoken words.** The script is sacred: the founder approved
  those words, and a render may not change them.

## Consequences

- The selfie render prompt carries the prohibition in its final-beat section,
  so the measured fixed-text floors rose (full 4,237 → 4,268; condensed 2,330
  → 2,395). Both stay inside the tightest ceiling in the catalog.
- The Render & result panel's copy is setup-dependent: a selfie says the
  middle ends on the payoff words and one short physical beat, a fixed camera
  says it ends where you would reach for your phone.
- Old strategies that still carry a reach are repaired in memory at render
  time; none need a paid rebuild. A strategy whose middle was only the reach
  is refused with the field named.
