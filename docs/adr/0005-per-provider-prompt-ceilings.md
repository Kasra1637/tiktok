# 0005 — Each provider gets its own prompt ceiling; the spoken script is sacred on tight ones

- **Status:** accepted
- **Date:** 2026-10-14 (decision predates this record; backfilled)
- **Anchors:** commit `d618f150`; `backend/server.py` (prompt-budget build and
  pre-send 409 refusal); `backend/generation_planning.py` (budget scaling,
  `prompt_ceiling_refusal`); `backend/video_providers.py`
  (`prompt_char_limit`, `script_is_sacred`)

## Context

Hailuo 3 was measured live refusing a ~7,700-char prompt; other providers allow
far less (HeyGen/Grok: 4,090). Handing every model a Hailuo-sized prompt 400s
after the founder has committed to the render — after the spend decision, with
nothing to show. A single global limit would either starve Hailuo's quality or
break every tight-ceiling model.

## Decision

- Each provider declares `prompt_char_limit` (measured where possible,
  conservative 4,090 where unproven). The builder scales field budgets to fit
  rather than cutting the finished tail.
- On tight ceilings the spoken script is sacred (`script_sacred`): only
  direction and template wording absorb the squeeze, never the founder's
  approved words — a squeezed script is a different video.
- A prompt still over budget after scaling is refused with a 409 **before**
  any spend, never discovered as a provider 400. The refusal names the
  overshoot, the size of a cut that would fit, and the roomiest model this
  deployment offers above that ceiling — levers the founder actually has.
  It used to say "shorten the script or the app's own wording, or pick another
  model", which named one thing that is ours to change, not theirs, and gave
  no size and no model (`generation_planning.prompt_ceiling_refusal`).

## Consequences

- **Gain:** no paid prompt-too-long 400s; script integrity holds on every model.
- **Cost:** direction prose degrades first on tight models; ceilings from
  listings (not live refusals) are conservative by design and need revisiting
  on evidence.

## Alternatives considered

- **One global limit for all models:** rejected — wrong in both directions at once.
- **Truncate the finished prompt to fit:** rejected — cuts the tail (often the
  CTA/close), silently changing what the video says; scaling budgets preserves
  structure.
