# 0224 — Template cards follow the fixed camera indoors

Status: accepted (extends 0219, follows 0220's pattern)

## Context

Kasra's report from the live app on Nov 19 2026: with Fixed camera
picked in the direction section, every template card on the
Audience & template step still read "In your video: Outdoors in
the evening. The character's look comes from the photo you
upload." — the fixed indoor rule contradicted on the very screen
where the founder picks the setup, before any plan exists.

The plan, strategy and render prompts have enforced ADR 0219's
rule since it landed. The card had not: `angle_scene.opening_staging`
built the "In your video" line from the angle alone
(`video_scene(angle)` → `_where(scene)`), and the recommendations
path — `recommend_templates` → `score_template_for_angle` →
`template_angle_fit` — never received a camera setup at all. The
angle's outdoor moment reached the card verbatim, so the one
surface the founder reads before generation described a video the
app would refuse to stage that way.

## Decision

1. **The setup threads the recommendations path.** The
   template-recommendations endpoint takes `camera_setup` as a
   parameter, the way the direction-options read takes the picked
   setup (ADR 0220): the read is profile-scoped and owns no
   project, so the wizard passes the setup saved on its project
   draft. It flows endpoint → `score_template_for_angle` →
   `template_angle_fit` → `opening_staging`, as a keyword argument
   whose default is the old behavior — every existing caller, and
   handheld, is byte-identical to before.

2. **Under a fixed camera, the staging line states the indoor
   staging.** `angle_scene._scene_for_setup` restates an outdoor
   scene's place as indoor for the staging line only, keeping the
   moment and its time of day: "Outdoors in the evening" reads
   "Indoors in the evening". That is ADR 0219's nearest-indoor
   move stated at the card's level of detail — the card names
   where and when, never a specific room, so the exact interior
   remains the plan's to write. The angle itself, its moment, the
   shape and development lines, and the fit judgement (structure,
   example conflicts, score) are all computed against the angle as
   written and do not change; the spoken words never change.

3. **The wizard keys the cards on the setup.** `useWizardTemplates`
   sends `camera_setup` with the recommendations request and
   carries it in the request key, beside the approved hook line
   and middle (ADR 0108): display-shaping inputs ride the request
   and the key together. Flipping the setup retires cards computed
   under the other one instead of leaving a wrong place on screen;
   they reload on the next tailoring run, the only path that loads
   them (ADR 0098).

4. **`fit_direction_options` was examined and left unchanged.**
   Its angle-moment lead heads the Location list inside
   `angle_scene`, but its only production caller is the
   direction-options endpoint, which applies ADR 0220's
   `location_setting` filter to the whole list — the lead
   included — after the fit, and the per-field refresh applies
   the same filter to refreshed locations. The frontend never
   reads the payload's `angle_moment` field. No response a founder
   sees can carry the outdoor moment as a fixed camera's location
   pick, so there was nothing to align.

## Consequences

- A fixed camera's template cards read indoors, matching what
  the plan, strategy and render will do; the contradiction Kasra
  screenshotted is gone at the source.
- Handheld cards are unchanged, word for word.
- Tests: `test_template_relevance.py` pins the staging line under
  fixed (outdoor angle reads indoors, same time, photo line kept),
  handheld (the angle as written), a fixed indoor angle
  (untouched), and the scorer threading the setup into the card
  payload. All four new checks failed before the change.
