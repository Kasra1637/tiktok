# 0004 — Generation is single-pass only; durations clamp, never chain

- **Status:** accepted
- **Date:** 2026-10-14 (decision predates this record; backfilled)
- **Anchors:** `backend/server.py` (`_submit_generation` docstring and duration clamp);
  `backend/video_providers.py` (`plan_duration`, `clamp_for_single_pass`);
  `backend/server.py` (`_assert_within_single_pass_cap`)

## Context

The generated piece is a hook plus a middle — one render. An earlier design
chained segments (hook, extensions, bridge frames, second jobs for the
remainder), which meant approval gates between segments, join steps, and spend
on footage the founder films themselves (demo, CTA). Chaining also multiplied
continuity failure modes: every seam was a place the character, wardrobe, or
scene could drift.

## Decision

- One video is one render. Requested durations clamp to the provider's
  single-pass ceiling; anything longer is refused with a 400 naming the ceiling,
  never silently shortened or split across jobs.
- `plan_duration`'s primary/extension pair is retained only as the measuring
  helper; the submit path honours the primary and ignores the remainder.
- Continuity machinery (bridge frames, clip references) is out of the submit
  path: with no second render there is no seam to pin.

## Consequences

- **Gain:** one spend, one artifact, no seam drift, no gates; duration errors
  are legible before money moves.
- **Cost:** pieces longer than the ceiling can't be generated whole — the
  founder records the overflow as their own demo, which is a product
  constraint, not just an engineering one.

## Alternatives considered

- **Multi-job chaining with bridge frames:** rejected — the seam-pinning it
  needed is exactly what providers support inconsistently (see ADR 0002), and
  the extra spend bought footage outside the generated piece's scope.
- **Silent clamping to the ceiling:** rejected — hands back a file that is not
  the video the plan describes, on spend approved for a different length.
