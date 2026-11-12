# 0108 — Setup owns camera words, Location owns the place, plan owns shape

- **Status:** partially superseded by 0119 (the bounded-by submit refusal is removed; setup/Location/shape ownership stands)
- **Date:** 2026-11-07
- **Anchors:** `backend/scene_consistency.py` (`strip_location_objects`,
  `camera_setup_wording`, `carry_camera_movement`, `reconcile_scene`),
  `backend/final_beat.py` (`split_phone_clauses`, `split_phone_mentions`,
  `strip_fields`, `is_selfie`), `backend/ai_service.py`
  (`normalize_strategy`, `generate_video_strategy`),
  `backend/angle_scene.py` (`opening_shape`, `opening_development`,
  `template_angle_fit`), `backend/template_recommendations.py`
  (`score_template_for_angle`), `backend/claim_safety.py`
  (`last_sentence`, `bounded_by_conflict`), `backend/server.py`
  (`_public_project`, `_project_strategy`, `recommend_templates`,
  `_guard_render_scene`, `_submit_generation`,
  `update_studio_project`), `frontend/src/lib/angleSubtitle.js`
  (`angleDetails`), `frontend/src/components/studio/SelectionPanels.jsx`
  (`RecommendationCard`, `TemplateShape`, `AngleSelector`),
  `frontend/src/hooks/useWizardTemplates.js`,
  `frontend/src/pages/CreateVideo.jsx`; tests
  `backend/tests/test_scene_consistency.py`,
  `backend/tests/test_final_beat.py`, `backend/test_claim_safety.py`,
  `backend/test_template_relevance.py`,
  `backend/test_generation.py::TestFinalPhoneFraming`,
  `backend/test_influencer_workflow.py`
- **Shapes:** extends ADR 0092 (render & result scene fields agree),
  ADR 0093/0097 (selfie never shows a phone), ADR 0089 (one character,
  one opening) and ADR 0064 (fixed-camera conflicts refuse before render)
  — without overturning them. ADR 0064's refusal still owns fixed-camera
  action conflicts and any non-rewritable direction; ADR 0108 rewrites
  simple setup wording instead of refusing it.

## Context

Render & result read on the founder's chosen setup named two setups at
once. A handheld strategy said "fixed camera", "Locked medium shot" and
"steady framing" in Camera angle, Framing and Scene details, and said
"phone" in the Hook concept, Position in Frame, Props, Movement and
both "What they do" lines and in Location itself. The plan's default
look promised "a slow push in during the middle" that appeared nowhere
in Framing or Movement, the template's Shape and middle quoted a different
hook's words and a phone-reading middle, and the final spoken line
promised self-understanding the angle's "bounded by" forbade — all
visible before money was spent, all sent to the provider as written.

## Decision

- **Setup is the source of truth; wording is rewritten.** The strategy's
  `camera_setup` decides. For handheld, `camera_setup_wording` rewrites
  "fixed camera"/"locked shot"/"steady framing" to handheld-selfie camera
  wording and `camera_setup_wording` translates a physical camera move
  in Movement ("the camera pushes in") to the lean it can film
  ("they lean in toward the lens"). For fixed, scene wording
  ("handheld selfie") is rewritten to "fixed camera"/"from a fixed
  position" deterministically, so the panel and the prompt agree without
  a rebuild; Movement for fixed is deliberately left for
  `require_camera_setup_directions` to refuse (ADR 0064), so an actor's
  "holds the recording phone at arm's length" still blocks with a
  rebuild named rather than becoming "at fixed camera" nonsense.
- **Handheld names no phone anywhere; Location never names objects.**
  `final_beat.strip_fields` removes phone clauses (including bare
  "Phone stays..." without a determiner, and "phone at chest height" in
  Position in Frame) from hook concept, hook/middle action, Movement,
  Framing, Camera angle, Character positioning and Props, while camera
  direction ("handheld camera", "the camera pushes in") is kept via the
  narrower phone-mention rule. `strip_location_objects` drops carried-
  object clauses from Location in every setup — a fixed camera may keep
  the phone in the action and Props, never in the place — keeping scenery
  ("dark yard", "closed front door") conservative.
- **The plan's camera move is carried.** `carry_camera_movement` puts
  the plan's default-look move ("a slow push in during the middle") into
  Framing and Movement, translated to a lean for handheld. It runs on
  generate, on the read paths (`normalize_strategy` carries no timeline,
  so `_public_project`/`_project_strategy` carry after normalize) and in
  `reconcile_scene`; the lighting split stays a save/render repair.
- **Spoken words are quoted, never paraphrased.** `opening_shape` with
  an approved hook line returns it exactly as written; `opening_development`
  with the approved middle returns its first sentence. They thread through
  `template_angle_fit`, `score_template_for_angle`, the recommendations
  endpoint (`hook_line`, `middle` params), `useWizardTemplates`,
  `AngleSelector`/`angleDetails` ("First 3 seconds promise" quotes the
  hook line) and `TemplateShape` (actual middle when a plan exists). A
  promise naming unspoken words can never render.
- **The final line is checked against its bounds before spend.** `last_sentence`
  + `bounded_by_conflict` (per-domain intersection: self-understanding,
  inside, verdict, emotional-intelligence, diagnosis) run in
  `_guard_render_scene` with the stored angle; a final line promising
  self-understanding the angle forbids is refused with the line and the
  bound named and nothing charged. Advisory `build_safety_report` still
  never blocks (ADR 0081).

## Alternatives rejected

- **Refusing every setup mismatch.** Blocking a bare "handheld selfie"
  style phrase would spend a rebuild on a one-word fix the setup already
  decides; rewriting simple wording keeps the earlier ADR 0064 refusal
  for action conflicts it cannot safely substitute.
- **Rewriting phone to camera in Position in Frame.** Stripping the
  phone clause keeps the position ("centred") without inventing a camera
  height the founder never approved; the height is the model's to state
  in Framing, where the filming device is already named.
- **Another prompt rule for shape.** The display is string logic over
  approved words, not a model paraphrase: deterministic quoting cannot
  promise unspoken words, while a prompt can.

- **Repairs leave an audit trail.** Pure modules return `changed`; the
  callers log it — `normalize_strategy` at debug (it runs on every panel
  read), `generate_video_strategy` at info (one persisted repair), the
  read-path carry at debug, and `_guard_render_scene` at info before the
  prompt is built. No repair is silent at spend time.

## Consequences

- One logical change per commit still holds: display and render repairs
  ride `normalize_strategy`, `reconcile_scene`, the guard and the read
  paths together, and copy-only syncs (test expectation updates for the
  fixed-style rewrite and the stripped position) stay in this commit
  because they pin the same decision.
- A strategy with wrong setup wording now renders a fixed/held
  correctly-stated video instead of refusing for a one-word style phrase;
  action conflicts (pans, close-ups, walks toward the lens, gestures
  pushing in) still refuse with "rebuild" as before.
- Move carry is pinned for every move kind (push-in, pull-back,
  zoom-in/out, pan, tilt, orbit, track) in both setups, including the
  non-slow variants and the no-duplicate-on-second-carry idempotence.
