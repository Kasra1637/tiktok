# 0103 — Props are carried objects; Camera angle and Visual style say "the camera"

- **Status:** accepted
- **Date:** 2026-11-06
- **Anchors:** `backend/scene_consistency.py` (`camera_wording`,
  `_is_scenery_entry`, `prune_scenery_props`, `_mentioned_objects`,
  `reconcile_scene`), `backend/ai_service.py` (`normalize_strategy`, the
  strategy schema's `scene.props` and `scene.visual_style` lines and the
  props rule), tests `backend/tests/test_scene_consistency.py` and
  `backend/test_ai_json_calls.py`
- **Shapes:** refines ADR 0092's props invariant (it asked for every object
  that appears, which included the place) and extends ADR 0097 (a handheld
  selfie never shows a phone); ADR 0059's natural amateur look is unchanged

## Context

Render & result is read before money is spent, and every scene row is sent to
the video model. Two rows kept naming the wrong thing:

1. **Props listed scenery.** The old invariant said `scene.props` names "every
   object that appears" in the actions and timeline. The object extractor
   therefore copied "the counter", "the window" and "the sign" out of lines
   like "sets the mug on the counter" — and the model, following the prompt,
   also wrote the place into Props. The row duplicated Location and told the
   video model to put furniture, buildings and signs in the character's hands.
2. **Camera angle and Visual style called the filming device "the phone".**
   A phone named in those rows reads as a phone in the scene; a handheld selfie
   cannot film one because the camera *is* the phone in the character's hand
   (ADR 0097). The model draws what the direction calls the device.

Spoken lines are the founder's words and must never be rewritten by either fix.

## Decision

`backend/scene_consistency.py` owns both deterministic rules:

- **Props are carried, worn or used.** An entry is reduced to its object
  before any place phrase ("a mug on the counter" → "a mug"). Fixed furniture,
  rooms, buildings, fixtures and decor are always dropped (table, counter,
  desk, wall, window, door, building, street, sink, lamp, screen). Signage —
  sign, billboard, poster, banner, logo — is dropped only when Location already
  names it, because a sign the person picks up is a legitimate prop. Completing
  Props from the hook/middle actions and the timeline skips scenery for the
  same reason: "sets the mug on the counter" adds the mug, never the counter.
- **The filming device is the camera.** Camera angle and Visual style replace
  phone, smartphone, iPhone, phone camera and camera phone with "the camera"
  (or "camera" inside a compound like "camera footage"). A determiner or
  possessive becomes "the camera" ("shot on her phone" → "shot on the
  camera"), so the direction never puts a phone in the character's hand.
  Spoken fields are not part of this pass.
- **Both paths agree.** `normalize_strategy` applies the rules on every read,
  so Render & result never displays a counter in Props or a phone in the camera
  rows; `reconcile_scene` applies them on save and before render, and reports
  the labels it rewrote. The strategy prompt asks for the same shape up front,
  and its visual-style hint now says handheld camera footage, never phone UGC.

## Alternatives rejected

- **Prompt-only.** A saved strategy would keep its old Props and phone wording
  until the founder paid to rebuild it; the panel and the prompt would still
  disagree with the rule.
- **Drop every prop not named in an action.** Worn accessories and objects the
  scene sets in hand can be real props even when the action text does not
  repeat them; the concrete failure was scenery duplication, not every
  unmentioned object.
- **Ban all signage.** A protest sign or a shop sign the person carries is an
  object, not the place; only the sign Location already names is scenery.
- **Rewrite spoken lines to remove "phone".** The hook and script are the
  founder's own words; ADR 0090 already refuses rather than rewrites them.
- **CSS or display-only renaming.** The stored strategy feeds the prompt lock,
  so a display-only fix would still tell the model to draw a phone.

## Consequences

- Existing strategies are cleaned on read and on save; no migration and no paid
  rebuild are needed.
- The scenery lexicon is deliberately conservative and testable. It can miss a
  fixed object it does not know, but it never removes an object merely because
  an action text did not repeat it.
- The strategy prompt stays under the existing 29,000-character ceiling, pinned
  by `test_ai_json_calls`.
- A future field that needs the same rule should call `camera_wording` or
  `prune_scenery_props`, not grow a second regex.
