# 0250 — Hook renders open clean, move physically, and show their scene

Status: accepted (extends ADR 0181's head trim for the hook surface only; the regular renders' 0.2s is untouched)

## Context

Kasra rendered a 4-second hook on the Hook + CTA page (Nov 21 2026:
journaling at a desk — location "Tidy desk with a notebook", wardrobe
"Comfortable cream knit top", hook line "I'm trying to journal
tonight and I keep stalling.") and reported three defects in the
delivered clip:

1. The first frame is still the model's blurry dissolve. ADR 0181's
   0.2s head trim fixed regular Create Video renders, but the
   dissolve on these short hook renders runs longer than 0.2s — and
   MiniMax H3 Max, the other model a hook can render on, has no head
   trim entry at all.
2. The model performed a face-only flicker — eyes widening — instead
   of the hook's physical action. The hook was journaling at a desk:
   hand, pen and notebook should already be moving in the first
   frame. The direction chain never said so in terms the model could
   not satisfy with a face: `generate_hook_line`'s hook_action
   instruction asked for a physical move, the stored strategy's scene
   carried an empty `character_positioning`, and the assembled prompt's
   opening rule (ADR 0187) expressly allows the opening to play
   through a face channel.
3. The background was plain white with no scene, despite the chosen
   location. Nothing in the hook's prompt required the location to
   render as a scene; a backdrop satisfied every stated rule.

## Decision

**The hook head cut is 0.5s, composed with the beat tail cut.** In
`_persist_generation_clip`, a fresh render whose project surface is
`hook_cta` AND whose generation row is beat-shaped (the ADR 0244
rule: `requested_duration == trim_to_seconds`, i.e. the pick sits
below the provider floor and a tail cut is recorded) now takes one
composed cut: 0.5s off the head, then the tail cut to the pick, so
the delivered length is still exactly the pick. The composition is
staged on a temp file and replaces the canonical clip only when both
cuts land; on any failure the ordinary sequence runs instead — the
per-model head table, then the tail attempt — with every existing
soft-failure behavior preserved (a failed beat cut still delivers the
full render and names what was being cut). It covers both models,
because it keys on the surface and the row shape, not the model
table.

The value is stated honestly: **0.5s is derived from repo evidence,
not measured from Kasra's file.** His live renders are hosted
elsewhere; no local sample exists to measure. The precedent is
`backend/posters.py`, which takes the poster frame at 0.5s precisely
because that is "past a possible black first frame" — the codebase's
own settled answer to how long a model's opening artifact lasts.

What does not change: `_MODEL_HEAD_TRIM_SECONDS` stays
`{"heygen-video-1": 0.2}` and regular renders take exactly ADR
0181's cut (the open 0.2s vs 0.25s question for long renders is
Kasra's call and stays untouched). A hook rendered AT the floor (a
5s pick records no tail trim) keeps its exact length and its head:
there is no tail to give the longer cut back, and the page's promise
(ADR 0244) is that the saved video is exactly the picked length.
Legacy story beats (surface NULL) keep the path ADR 0243 preserved.

**The hook's opening is physical, in all three links of its
direction chain** (generator-side only; the Craft scorer is
untouched):

- `generate_hook_line`'s hook_action instruction now requires the
  central action performed as a physical gesture with the hands and
  body, in frame from the first frame, and states that a face-only
  change — eyes widening, an expression shifting — never counts as
  the opening beat; the face rides the gesture, it never replaces it.
- The strategy the hook endpoint stores seats the presenter for it:
  `character_positioning` is "Waist-up, hands and body in frame; the
  opening is the physical action, never face-only." — which rides the
  scene lock into every hook render's prompt.
- The assembled prompt for a hook-surface plan gains a
  physical-opening section beside the general opening rule it
  narrows: the opening movement MUST be the hook's physical gesture,
  hands and body visibly in frame, waist-up (ADR 0213); a face-only
  change does NOT satisfy the opening beat when the scene has a
  physical action to perform. A condensed twin carries the same rule
  under the tight provider ceiling. A plan with no hook surface
  builds the prompt it always built — pinned byte-side by the
  existing prompt suites plus a negative pin here.

**The hook's place must render as a scene.** Beside the location
section, a hook-surface prompt states that the location renders as a
real scene behind the presenter — surfaces, objects and light in
frame for the whole take — and names a plain, empty or white
background as a failed render (with a condensed twin). The closing
bookend (ADRs 0187/0223) is unchanged.

## Consequences

- New pins in `backend/test_hook_head_trim.py`: marked clips (0.5s
  red/silent head) prove both models' 4s hooks open blue and loud at
  exactly 4.0s; the floor case keeps 5.0s; a regular HeyGen render
  still opens inside its marked head at 4.8s (the 0.2s cut, no leak);
  the constants are pinned; the prompt sections are pinned present
  for hook plans and absent for regular ones; the hook-line
  instruction and the stored strategy positioning are pinned.
- The head cut remains a persist-time transform of the provider's
  file: a hook whose composition fails falls back to today's exact
  behavior, never to a lost render.
- Whether 0.5s clears every model's dissolve in the wild is
  Kasra's next live render's evidence; the constant is one line if
  it needs to move.
