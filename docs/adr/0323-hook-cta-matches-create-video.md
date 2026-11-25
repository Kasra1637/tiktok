# ADR 0323: Hook + CTA generates its hook the Create Video way

Status: accepted

## Context

The founder compared the two hook surfaces and ruled
(Nov 24 2026, confirmed twice): he likes Create Video's
hook generation better, so Hook + CTA's hook generation
is matched to Create Video's exact framework and
structure. The code-verified split behind the ruling:
both pages share the spoken-line rules block and the
render-prompt builder, but a Create Video hook is
written inside the creative plan — it knows the angle,
the template shape, the location and the script it
opens — and then goes through the hook bake-off
(ADR 0130) and the Craft-scored correction (ADR 0115).
A Hook + CTA hook was one standalone call from profile
facts alone, corrected only for length and finished
sentences. On the same call the founder added a framing
ruling: hook videos were starting zoomed in — face
filling the frame, hair cropped, the location unreadable
— because the hook's opening direction led with her head
lifting and her eyes rising into the camera, pushing in
over the render prompt's wide framing order.

## Decision

`generate_hook_line` keeps its draft loop untouched —
the same three attempts under the same hard gates (word
and character budgets, the finished-sentence gate, the
shape pick, the dangling-question charge), so a hook
still lands inside its limits on the first generation —
and then runs the plan's two stages:

- **The bake-off, the same function.** The accepted
  draft is the incumbent in `_hook_bake_off`. The page's
  story is the demo that follows: the demo stands in the
  story slot, anchored on the profile's promised
  outcome, because the founder's demo is chosen after
  the hook and is the answer it points to. Two seams,
  both defaulted off for the plan: the hard filter is
  the page's own gate composition (the exact checks the
  draft loop enforces, held in one `_line_issues` list
  both stages use), and candidates are scored with an
  empty script — the demo is the founder's footage, not
  spoken words, so a hook is scored as the standalone
  line it is. A winning candidate keeps the draft's
  direction: candidates open the same story, so the
  direction written for its moment stands — the plan's
  own precedent for a hook swap.
- **The craft correction, ADR 0115's pattern adapted.**
  When the winning hook scores below the bar — the
  plan's own fraction, CRAFT_RETRY_BELOW of the pair's
  achievable 95, applied to the total this surface can
  reach (Story arc and Demo handoff read a script and
  are structurally silent here, so their achievable
  maxima are excluded) — ONE correction, steered by the
  weakest dimensions' findings, rewrites the hook line
  AND its direction as one package. It ships only when
  it passes the same hard gates and scores strictly
  higher; it never refuses the hook.
- **Scene-anchored direction.** The hook_action
  instruction is rewritten the Create Video way: she is
  in the place the location names, already mid-gesture —
  never led by her head lifting or her eyes rising into
  the camera. The gesture rule and the place rule the
  page's writer carries (and Create Video's does not)
  stand unchanged: a face-only change never counts as
  the opening beat, and the generation still invents and
  names the one place the hook happens.
- **Start wide, land close.** The render prompt's
  camera move is swapped on the hook surface only
  (`camera_move_section`'s `hook_surface`): the take
  opens wide — waist-up, the place visible around her,
  even on a handheld selfie — and her own hand eases the
  phone toward her face as she delivers the line,
  landing at the close framing by its end. Starting
  zoomed in is a failed opening; arriving close is the
  design. Create Video's hold ("hold that framing, no
  push in") is byte-for-byte untouched, and a fixed
  strategy keeps the fixed text whatever the surface.

## Consequences

A Hook + CTA generation costs the draft call plus the
bake-off's candidates call, a bounded correction when
every candidate breaks a gate, and one craft correction
when the winner scores below the bar — the plan's cost
shape, bounded the same way, and every added stage
fails back to the hook the stage before it accepted.
The founder's steering picks steer the candidates and
the correction too (the form block carries the steering
block into the bake-off). Not covered, deliberately:
the single-pass prompt builder carries no start-wide
text — a hook render always has a strategy, so that
builder never assembles one — and Create Video's plan
flow, prompts and framing are unchanged in every byte.
