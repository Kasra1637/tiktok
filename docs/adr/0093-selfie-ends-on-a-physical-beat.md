# 0093 — Selfie renders end on a physical beat, never a phone

- **Status:** accepted
- **Date:** 2026-11-04
- **Anchors:** `backend/final_beat.py` (curated endings, `pick`, `strip_fields`,
  `apply_ending`), `backend/server.py` (`_guard_render_scene`),
  `backend/generation_planning.py` (`_SELFIE_FINAL_BEAT`, the fixed-camera
  `_PHONE_HANDOFF_FRAMING`), `backend/ai_service.py` (strategy and plan prompt
  rules), `backend/scene_consistency.py`; tests
  `backend/tests/test_final_beat.py`; prompt pins in
  `backend/test_generation.py` and `backend/test_ai_json_calls.py`
- **Shapes:** the ending of ONE render, by camera setup. It refines the final
  moment of ADR 0004's single pass; the phone handoff is no longer universal.

## Context

Every render ended with the same visual beat: "raise the phone into view, back
to camera, screen facing her, whole phone uncropped, excited, through the last
frame". In a selfie-style video the camera IS the phone in the character's
hand — the recording device cannot also appear as a prop, and a phone "found"
at the end contradicts the premise. It was also identical on every render of
a project, so a founder generating another take saw the same ending again.

A fixed-camera render is different: the phone is on a stand, both hands are
free, so the handoff is filmable and stays.

## Decision

- **Selfie (handheld):** no phone is raised, held or shown anywhere in the
  video. The last 1-2s end on ONE short physical beat in the same final
  moment — physical only, no extra words and no extra time, with a
  split-second hold before the cut. Examples: eyes dropping off to the side
  then snapping back to the lens with a small nod; a slow head tilt with a
  half smile; a shoulder drop and exhale into a nod.
- **Fixed camera:** the phone handoff framing stays exactly as it was.
- **One ending per render:** `final_beat.pick` rotates a curated list of 12
  physical endings using the number of renders this project already has, so
  consecutive renders differ; it prefers endings whose mood tags match the
  strategy's emotional triggers, and skips any listed as recently used. The
  chosen ending is never stored on the saved strategy — it belongs to the
  render, so the same strategy can produce different takes.
- **Every surface agrees.** The ending is defined once and applied
  everywhere: the strategy prompt (selfie rule: no phone, no written ending
  beat), the plan prompt's shot timeline (selfie rule), the middle section's
  "What they do" line, Props, Movement, Framing and Camera angle, and the
  final render prompt (full and condensed). The phone clauses are stripped
  from all of those fields for selfie before the prompt is built; the chosen
  ending is written into the middle action and movement and printed in the
  final-beat section with the framing hold.
- **Fix or block before render.** `_guard_render_scene` strips any phone held
  or shown from a selfie strategy's own fields, so the Props/Movement
  completion pass of ADR 0092 cannot copy it back, then applies the chosen
  ending. A fixed-camera strategy is untouched by this pass.

## Alternatives rejected

- **One fixed physical ending for all selfie renders.** No variety between
  takes; the beat would become as recognisable as the phone raise it
  replaces.
- **Let the model invent the ending.** It cannot know which endings the
  previous renders used, and the same strategy would tend to produce the
  same beat. The curated rotation is deterministic and reviewable.
- **Removing the phone from the founder's story too.** "Reach for the phone"
  is the handoff moment that hands the video to the founder's own demo, not a
  device shown on camera. Only held/raised/shown phones are removed.

## Consequences

- The selfie render prompt is setup-dependent; the measured fixed-text floors
  moved to the selfie default (full 4,223 -> 4,237, condensed 2,377 -> 2,330,
  pinned by `test_generation`).
- Old strategies that still carry a phone ending are repaired in memory at
  render time; none need a paid rebuild for this.
- The plan generator now receives `camera_setup`, so a regenerated timeline
  cannot write a phone ending into a selfie project.
- The generation row records the render as usual; ending variety comes from
  the render count, not a new column.
