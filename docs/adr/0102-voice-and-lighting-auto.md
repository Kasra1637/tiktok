# 0102 — Voice and lighting are set from each video's own context

- **Status:** accepted
- **Date:** 2026-11-06
- **Anchors:** `frontend/src/pages/CreateVideo.jsx` (Review: no
  `review-voice-direction` and no `review-lighting` control, simplified scene
  copy, `direction-live-preview` shows the auto value); `frontend/src/pages/useWizardDirections.js`
  (voice slot removed, lighting kept only to preserve a saved scene's word);
  `backend/ai_service.py` (plan `voice_direction` and strategy `voice_delivery`
  stated from the video's own context); smoke checks "Review sets delivery from
  the video, never from a control" and "camera setup and profile-matched
  direction dropdowns save and survive reload"
- **Shapes:** supersedes ADR 0091 (voice direction as the single delivery
  control); keeps ADR 0092 (Location names the place, lighting and time of day
  in Lighting — the scene field is still written by the model, just no longer
  picked)

## Context

ADR 0091 made Voice direction the single delivery control on Review, after
removing the video-level Tone dropdown: the two had collapsed into the
strategy's one `voice_delivery`, so one pick was enough. The same was true of
Lighting — a dropdown of profile-matched options that the strategy's scene
already stated from the video's own context. A founder picking either was
choosing a delivery the plan and strategy had already agreed on, and the
choice could only mismatch what was written. Review carried the densest stack
in the step and the copy repeated the same instruction three times.

## Decision

- **Voice direction and lighting are set from each video's own context.** The
  plan writes `voice_direction` from its objective, audience and angle emotion;
  the strategy writes the scene's lighting from the same material. Neither is a
  founder control on Review.
- **Review drops the Voice direction and Lighting controls.** Location and
  Wardrobe remain pickable — they refine the strategy's scene, so a founder
  who wants a different place or wardrobe can still choose. Camera setup stays.
- **The values still ride through.** A project that already carries a tone or
  a voice direction keeps it into plan and strategy generation; only the
  second control is gone, as under ADR 0091. `useWizardDirections` keeps the
  lighting slot as a read-only match so a wardrobe pick recomposes the
  strategy's own lighting word instead of dropping it.
- **The copy is simplified.** The section says what it holds once: "Location
  & wardrobe", "Updates the field above", and one help line. The Location
  placeholder and the live preview copy stop mentioning lighting; the preview
  still shows the delivery the video's plan set, now labelled as such.
- **The render gate is untouched.** Scene consistency (ADR 0092) still
  reconciles Location, lighting and time of day; the founder just no longer
  picks lighting from a list.

## Alternatives rejected

- **Keep Voice direction as the one control (ADR 0091).** It duplicated the
  plan's own delivery and could contradict it; two sources of truth for the
  same sentence is the bug this removes.
- **Keep Lighting, drop Voice direction only.** Lightning is the same kind of
  scene field the strategy already states; picking it re-introduced the
  mismatch at half the scope.
- **A global default delivery.** Flat, same on every clip, and the reason the
  previous wording asked for "fast, upbeat, high-energy" on all of them.

## Consequences

- Review is shorter and says one thing per group; delivery matches the video
  instead of the founder's last pick.
- The direction dropdowns test now covers Location and Wardrobe only; the
  autosave test repoints to Wardrobe, and the delivery test asserts the two
  controls are gone while the auto value still shows.
- `useWizardDirections` keeps its generic refresh path; only the Voice pick and
  its state slot leave.
- No request-shape, storage, render or gate change.
