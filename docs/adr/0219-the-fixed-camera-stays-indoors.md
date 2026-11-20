# 0219 — The fixed camera stays indoors, and the set-down opening is reversed

Status: accepted (supersedes 0216)

## Context

Two rulings from Kasra on Nov 19 2026, the same evening ADR 0216
shipped.

The first is a reversal. The set-down opening sits behind the
Fixed camera model error problem — the red warning and the blocked
render a founder meets when a first-frame model is paired with the
fixed setup — and Kasra ordered it reverted and removed from the
video prompt so the problem goes with it: "revert and undo the
update you made so that the user would never going to start or
drop the phone or anything like that."

The second is a rule for what the fixed setup is. Kasra: "for
fixed camera setup should only be used indoor. not on a bench,
not in the airplane, not somewhere weird. Only inside homes. or
somewhere like office or bed or something like that." ADR 0216's
environment rule had allowed fixed scenes outdoors wherever the
scene itself offered a resting surface — a bench, the steps, a
low wall, a café table. That allowance was part of the set-down's
logic (a surface to land on), and it goes with the reversal: a
placed camera is an interior setup.

## Decision

1. **ADR 0216 is reversed in full.** `FIXED_SET_DOWN_OPENING` and
   its condensed twin are removed from
   `backend/generation_planning.py`, and the set-down block is
   removed from the strategy prompt in `backend/ai_service.py`. A
   fixed-camera prompt contains no set-down staging at all: no
   recording already running, no phone being placed on a surface,
   no thump or settle wobble, no stepping into frame. The wording
   ADR 0216 trimmed to pay for the set-down stands in full again —
   the starting shot's shelf-or-tripod rest, the locked hold's
   frame restatements, the condensed header's ending clause, the
   condensed handoff's doubled orientation — so the fixed prompt
   is its pre-0216 self apart from the indoor sentence below.
   Handheld prompts are untouched, exactly as they were under
   0216: the set-down never reached them, and neither does its
   reversal. ADR 0213's wider handheld framing stands.

2. **Fixed camera is indoors only, at every generation level.**
   When a plan's `camera_setup` is "fixed":
   - the plan prompt (`generate_creative_plan`) states the plan's
     location must be INDOORS, in the rules the location field is
     written under;
   - the strategy prompt states `scene.location` must be an
     interior, where hook_action and the scene are written — for
     this setup the rule outranks `scene_location_guidance`'s
     outdoor steering, which handheld keeps untouched;
   - the render prompt's `FIXED_STARTING_SHOT` states the scene
     is indoors: an interior room, never outdoors or in transit.

   Indoors means inside a home, an office, a bedroom, an interior
   space like those. Never outdoors and never in transit: no
   bench, no park, no street, no terrace, no balcony, no rooftop,
   no airplane. If the angle's moment or the usage moment sits
   outdoors, the same moment is staged at the nearest indoor
   setting that keeps the moment and every spoken word intact —
   only the setting moves inside; the words never change.
   Handheld stays flexible to any location.

3. **One shared indoor/outdoor classification.**
   `backend/template_library.py` gains
   `location_setting(location)` beside `DIRECTION_OPTIONS`, the
   backend's direction location-options list: it returns
   `"indoor"`, `"outdoor"` or `None` from signal words in the
   location text — outdoor signals win a clash (a cafe terrace is
   not an interior), transit counts as outdoor, and no signal
   returns `None`, unknown rather than permission. Every curated
   location in `DIRECTION_OPTIONS` classifies. The generation
   prompts carry the rule in prose today; this classifier is the
   deterministic half a later UI build reuses to offer a fixed
   camera indoor locations only.

## Prompt budget (ADR 0053)

The reversal frees more than the indoor rule spends. The
saturated fixed build at HeyGen's 4,090 ceiling measures 4,008
(it measured 4,088 under ADR 0216), and the measured floors do
not move: both are built on the selfie default, and no handheld
text changed. No provider ceiling was raised and the spoken
script's budget was not touched.

## Consequences

- Fixed renders open on the presenter already framed by a
  stationary phone, indoors — the staging that sat behind the
  Fixed camera model error problem is gone from every prompt.
- A fixed plan or strategy whose moment lives outdoors is
  written indoors from the first generation, so a founder never
  reviews a fixed video staged on a bench or in an airplane seat.
- Tests: the strategy-prompt suite pins the indoor rule in a
  fixed strategy prompt, its absence from a handheld one, and no
  set-down staging in either; the plan-prompt suite pins the rule
  in a fixed plan prompt only; the selfie-framing suite pins the
  restored pre-set-down wording (starting shot, locked hold,
  condensed handoff), the absence of every set-down phrase from
  fixed render prompts at both budgets, the indoor sentence's
  presence there, and its absence from handheld prompts; the
  template-library suite pins the classification over the whole
  curated location list plus free-text and transit cases.
