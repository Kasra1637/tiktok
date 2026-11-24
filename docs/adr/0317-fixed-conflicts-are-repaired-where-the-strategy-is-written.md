# ADR 0317: Fixed conflicts are repaired where the strategy is written

Status: accepted

## Context

Live, Nov 24 2026 (request_id=dd5dc5ec1143): a project with a
Fixed camera carried a stored strategy whose hook_action read
"Mid-exhale leaning toward camera with one hand already
sweeping up from the counter". At render submit,
`require_camera_setup_directions` rightly refused — and that
guard was the ONLY place the conflict was ever checked. The
strategy had been written by the app itself, stored unchecked,
and the founder met the refusal at the Generate button: a dead
end, for a direction he never wrote. The strategy prompts
already instruct Fixed setups (ADR 0219's indoor, already-in-
frame staging), but an instruction is not an enforcement, and
the one enforcement sat at the far end of the flow.

## Decision

The check moves to the writing, inside
`generate_video_strategy` — the one generation entry, whose
return the studio endpoint stores. (The endpoint's later steps
never touch a field the guard checks: spoken-word binding
writes scripts, which the guard deliberately excludes, and the
camera-beat re-derivation is deterministic over the same
values.) Before the strategy returns:

- The submit-time guard itself runs over it, unchanged. A
  handheld strategy returns untouched — the guard already
  returns early, and no repair call is spent on it.
- On a conflict, ONE automatic repair: a single `_chat_json`
  call on the app's text model with its own small prompt (it
  does not ride in the strategy prompt, so no prompt-budget
  ceiling moves) and a strict `{"rewritten"}` schema. The
  instruction names the conflicting field, its current text,
  the offending clause verbatim, and the Fixed contract —
  stationary phone, presenter already in frame, head-to-mid-
  thigh framing, camera setup owns framing and movement. It
  rewrites ONLY that field, keeping the action's energy, its
  mid-motion opening and every non-conflicting detail (the
  hand sweep stays; the lean goes), cleaned to the same cap
  `normalize_strategy` applied to the field.
- The repaired strategy must pass the guard itself. If the
  repair call fails or comes back empty, the original conflict
  surfaces; if the repair still conflicts, the guard's wording
  for the remaining conflict surfaces. Either way the error is
  the guard's existing wording, raised at generation, and the
  studio endpoint passes it through whole instead of wrapping
  it in its generic failure line. A strategy that would
  dead-end at render is never stored, and no field is ever
  silently stripped — the guard's own rule, kept: a mixed
  direction may carry reviewed details that must not be thrown
  away.

The field and clause the repair needs are read out of the
guard's error message — that wording is the guard's public
surface, pinned by its tests — rather than duplicating its
matcher where the two could drift apart. The submit-time
guard, its regex and the Fixed starting-shot text are
untouched: the guard remains the backstop for every path this
decision does not cover.

Deliberately not covered: Hook + CTA, whose assembled
strategy is hardcoded handheld (ADR 0252), so the guard
returns early there by design; and founder-edited strategy
saves, which are not generation — the submit guard remains
their check, exactly as before.

## Consequences

A Fixed conflict now costs at most one small model call at
generation and is usually invisible: the founder gets a
strategy whose directions already obey the setup he picked.
When the repair cannot land, he hears about it at the moment
of writing, in the same words the render would have used,
with the strategy unsaved rather than stored as a dead end.
Each repaired field is logged at info, matching the existing
generation-repair audit trail.
