# 0213 — The handheld frame sits a little wider: waist up, full head and all her hair in frame

Status: accepted

## Context

Kasra's market-stall render (Nov 19 2026) came back a tight close-up
for the whole take: the head and hair cropped at the top, her hands
never in frame — despite the current framing text. ADR 0113 had
already widened the handheld starting shot once (upper-chest to
mid-chest, "never crop the forehead or chin") and the selfie hold
already forbade tightening. Two gaps remained:

1. Mid-chest still reads as a close-up to the video model, and the
   1.10x processing zoom (ADR 0053) crops a further 4.5% per edge
   out of whatever margin the opening frame has.
2. The margin was stated as "headroom" above the *head*, and the
   never-crop rule named only the forehead and chin — so the hair
   sat outside the protected margin and was the first thing the
   tight frame cut.

Kasra's order on the call: pull the camera a little further back
in the video-generation instruction so the presenter's full head
and all her hair stay visible — the shot starts at that wider
distance and stays there for the whole take, no pulling in. He
confirmed with "Do it."

## Decision

- `HANDHELD_SELFIE_FRAMING` (backend/generation_planning.py) now
  asks **waist up** — one step wider than mid-chest — with "the
  full head and all her hair in frame with clear headroom above
  the hair", and the never-crop rule names the hair beside the
  forehead and chin. Everything else in the ask stands: held at
  arm's length, eye-level, straight-on, about a metre away, room
  at the sides for hand gestures, no 3/4 angle, no off-centre
  framing, no wide-angle distortion, subtle sway. The string is
  shared verbatim by the strategy prompt and every provider
  prompt in both budget modes, so this one wording widens all of
  them.
- The holds keep the wider frame for the whole take: the
  never-tighten rule is unchanged, and both holds now name the
  hair (full: "Keep the full head, hair and chin inside frame";
  condensed: "Never crop the head or hair").
- The strategy-side handheld paragraph in backend/ai_service.py
  carries the same never-crop rule ("never crop the hair,
  forehead or chin"), so the strategy and the render still read
  one framing, not two (ADR 0108).
- This amends ADR 0113's framing decision. ADR 0113's other
  halves — the widened face-crop pads and the vertical identity
  reference — are untouched, as is the fixed camera framing.

## Paying for the text (ADR 0053)

The wider sentence added 49 characters. It paid 26 of its own
back inside the same paragraph: the repeated "Hold straight-on"
(the camera-move hold directly below restates it) and the second
"natural" ("Natural facial proportions" keeps the word). The
rest was paid out of a verbatim duplicate both budget modes
carried — "End before the last second" stated in the header and
again in the middle heading, which is present in every build —
and, in the condensed text, the identity close's "one take: no
cut", which its header's "ONE continuous" already states (the
close keeps the black-frame and title-card bans, which appear
nowhere else in the condensed prompt).

The payment was load-bearing, not bookkeeping: unpaid, the
growth landed a saturated HeyGen prompt 25 characters over its
4,090 ceiling with the script held sacred, and deepened the
default squeeze enough to clip the payoff out of a realistic
brief. Measured with the repo's own empty-build method: the
full floor rose 1 (4013 → 4014), the condensed floor fell 12
(2476 → 2464). The single-pass floor did not move (2835): that
builder's fixed text carries no starting shot. No provider
ceiling was raised and the spoken script's budget was not
touched.

## Consequences

- Handheld renders now open one step wider: waist up, the whole
  head and hair inside the frame with headroom above the hair,
  and the hold keeps that frame to the last frame.
- The gesture room the framing always promised ("room at the
  sides for hand gestures") is likelier to be real: a waist-up
  frame has somewhere for hands to be.
- Tests: the selfie-framing suite gains a pin for the new ask
  (waist up, hair in frame, headroom above the hair, never crop
  the hair, mid-chest gone), and the strategy-prompt suite pins
  the strategy paragraph's hair coverage with a fragment unique
  to that paragraph. The measured-floor pins were re-measured
  and updated to the values above, not loosened.
