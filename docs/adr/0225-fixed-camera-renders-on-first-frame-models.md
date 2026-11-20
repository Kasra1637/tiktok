# 0225 — Fixed camera renders on first-frame models

Status: accepted (supersedes the fixed-camera consequence of 0221;
ADR 0219 stands untouched)

## Context

Kasra's order on Nov 20 2026, after the state was put to him plainly:
Fixed camera is the app's biggest real gap — "Okay, fix that then."
This revisits the guard fix he had set aside on Nov 19 ("never
mind"); the set-down ban from that same conversation is not
revisited and does not move.

Since ADR 0221 removed `minimax/hailuo-3`, both models left on the
list — HeyGen Video (the default) and MiniMax H3 Max — pin the
founder's photo as the literal first frame
(`identity_via_first_frame`). The submit guard in
`_submit_generation` (`backend/server.py`) refused every first-frame
model for a Fixed camera setup with a 409, and the render panel
mirrored the refusal (`cameraIncompatible` in
`frontend/src/components/GenerationPanel.jsx`): a warning above the
model picker and a disabled Generate. So Fixed camera could never
render at all, named model or default, while Handheld rendered on
the same models through the same pinned frame.

The guard's origin matters. It was written when a fixed opening was
staged placement-first — the phone set down, the presenter stepping
into frame (ADR 0216) — a staging a pinned photo genuinely cannot
open. ADR 0219 reversed that opening in full: a fixed prompt now
opens on the presenter already framed by a stationary camera
indoors, head to mid-thigh, both hands in frame
(`FIXED_STARTING_SHOT` in `backend/generation_planning.py`). The
staging the guard protected against no longer exists anywhere in a
fixed prompt; what the guard was left refusing was the mechanism
itself — the pinned photo — which handheld renders already rely on:
the photo is the opening frame, and the model animates from the
presenter herself while the prompt carries the scene and framing.

## Decision

1. **The submit guard is removed.** `_submit_generation` no longer
   refuses a model for a camera setup. A Fixed submit on HeyGen
   Video, on H3 Max, or on the unnamed default proceeds through the
   one render path exactly as a handheld submit does; the founder's
   named (or default) model is the model that renders — no model is
   switched, silently or otherwise, because nothing is refused on
   model grounds. A comment at the guard's old site records why
   nothing stands there and what still refuses (point 3).

2. **The panel mirror is removed with it.** `GenerationPanel` drops
   `cameraIncompatible`, the `fixed-camera-model-warning` paragraph
   and its copy ("This model uses your face photo as its literal
   first frame. For Fixed camera, select a model that accepts an
   identity reference image…"), and the flag's part in the Generate
   button's disabled and ready logic. No model+setup combination
   remains refused on this ground, so no warning path presents one.

3. **The narrower protection that stays is the direction conflict.**
   The guard also stood in front of one genuinely unservable case,
   and that case keeps its own refusal: a strategy whose directions
   contradict the fixed setup — handheld-selfie wording, camera
   movement, close framing — is refused before any spend by the
   prompt builder (`require_camera_setup_directions`, ADR 0064),
   with a message that names the conflicting field and the rebuild
   remedy. With the model guard gone this is now the refusal a
   conflicting fixed submit actually meets, and the API pin asserts
   exactly that. Every other gate (readiness, prompt ceilings,
   spoken-word and scene checks) is unchanged.

4. **ADR 0219 is preserved explicitly.** Nothing about this lift
   reintroduces set-down staging: no phone being placed, no
   recording already running, no settle wobble, no stepping into
   frame. No prompt text changed at all — `FIXED_STARTING_SHOT`, the
   indoor rule and the fixed hold stand byte-identical, and the
   set-down absence pins in `backend/tests/test_selfie_framing.py`
   keep passing unmodified, now also asserted at the submit level
   for a fixed render on a first-frame model.

## Consequences

- Fixed camera renders again, on the standing model list: the
  pinned photo is the opening frame of a fixed render, and the
  model animates from it into the stationary indoor shot the prompt
  stages. The framing is carried by the prompt from that frame, as
  it is for the scene itself; the pin anchors the presenter, not
  the room.
- ADR 0221's recorded consequence — "Fixed camera has no servable
  model for now… until a reference-route model returns to the list
  or the guard is revisited" — is superseded: the guard was
  revisited, on Kasra's order, and this record is the revisit.
- A founder whose fixed strategy still carries handheld directions
  now meets the direction-conflict refusal instead of the model
  refusal. It fires at the same boundary (before a provider call,
  nothing spent) and names the actual problem with its remedy, so
  the submit boundary speaks more truly than it did.
- Tests: `TestCameraSetup` in `backend/test_generation_api.py` is
  reworked — the conflict pin now asserts the builder's "Fixed
  camera conflicts" refusal (and that the first-frame sentence is
  gone from it), and the refused-models pin is replaced by a pin
  that a fixed submit renders on H3 Max named, HeyGen named and
  the default unnamed: three provider calls, three generations
  snapshotted `fixed`, the submitted prompt carrying the fixed
  staging ("head to mid-thigh", indoors) with no set-down phrase
  in it, and the snapshot surviving a later setup flip. The render
  smoke's panel pin is inverted the same way: fixed + a first-frame
  capability renders no warning and leaves Generate enabled. Both
  backend pins and the smoke pin were watched failing against the
  guard before the lift.
