# 0091 — Voice direction is the one delivery control

- **Status:** accepted
- **Date:** 2026-11-04
- **Anchors:** `frontend/src/pages/CreateVideo.jsx` (Review's *Visual & audio
  direction* disclosure — the removed `review-tone` pick, the kept
  `review-voice-direction`), `frontend/src/pages/useWizardDirections.js`,
  `frontend/src/pages/Landing.jsx` (the retired "Tone is optional" promise);
  smoke checks "Review offers one delivery control, not two" and the Landing
  workflow pin that fails if the promise returns
- **Shapes:** the Review step keeps **one** delivery control — Voice direction.
  A project that already carries a `tone` keeps it; it still seeds plan and
  strategy generation. No database or API change.

## Context

The founder-facing surface had three voice controls:

1. App Profile **"Tone / voice"** (`tone_voice`) — brand-wide, passed to both
   generators as `brand_voice`.
2. Review **Tone** (`tone`) — a steering input into the plan and strategy
   calls; survives regeneration.
3. Review **Voice direction** (`voice_direction`) — a plan field the generator
   drafts; the founder's edit rides to the strategy call as approved-plan
   context and is re-drafted when the plan regenerates.

The render reads exactly one of these — the strategy's `voice_delivery` — so
2 and 3 are two knobs on the same dial. Their option lists read as synonyms
("friendly and natural" / "Natural friendly delivery"), the two dropdowns sat
side by side in the same disclosure, and nothing on screen explained the
difference.

## Decision

- The Review step keeps **one** delivery control: **Voice direction**. Its pick
  is concrete, is the material the strategy consumes as approved delivery, and
  its option lists adapt to the angle's Location.
- The video-level Tone dropdown is removed from the Review step (the pick, the
  live-preview line, and the steering wiring that existed only to move it).
- The App Profile's **"Tone / voice"** is untouched — brand-level voice
  remains the standing register, and it is what steers scripts and delivery
  between videos.
- `tone` stays in the schema and API. A project that already carries one keeps
  seeding plan and strategy generation with it; there is simply no second
  control that can set it. Saved projects render exactly as before.

## Alternatives rejected

- **Keep Tone, remove Voice direction.** Loses the only way to correct the
  model's drafted delivery, and the plan schema keeps drafting a
  `voice_direction` the founder can no longer see a control for.
- **Keep both, explain the difference in copy.** Copy cannot repair two
  dropdowns that feed one field; the founder still has to learn that one is
  steering and one is correcting a draft, for no extra capability.
- **One control writing both fields.** Conflates a steering input with an
  editable generated field and doubles the writes; regeneration would then
  re-draft `voice_direction` over the founder's voice pick.

## Consequences

- Fewer knobs on Review; one delivery concept end-to-end (Voice direction →
  strategy `voice_delivery` → the render's single delivery line).
- New projects cannot set a video-level tone; the register comes from the App
  Profile's brand voice, the angle, and the template. This is an explicit
  product decision, not a silent default change.
- The backend refresh endpoint and `DIRECTION_OPTIONS` still carry a `tone`
  list; it is dead to the UI. Removing it from the API would be a follow-up
  cleanup with schema churn for no behavior change.
