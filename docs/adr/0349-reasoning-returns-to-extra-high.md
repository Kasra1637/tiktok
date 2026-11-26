# ADR 0349: Reasoning returns to extra high

## Status

Accepted, Nov 25 2026 — Kasra's order on a voice call.
Asked what level generation runs at and told medium, he
ruled it too low; offered the ladder (low, medium, high,
extra high, Max), he picked extra high, on everything,
in the same push as the ADR 0342–0348 round.

## Context

The app has run the whole ladder at one time or another:
Max (ADR 0110), extra high with the plan chain at high
(ADR 0211), then medium app-wide for speed on the model
swap (ADR 0295, carried through ADR 0297 and the Ember
restore, ADR 0310). The medium pin was a speed ruling,
not a quality finding. Since then the generation rules
have grown much more demanding — the story arc scoring,
the no-word-twice rule, the land-the-verb rule — and
Kasra's call is that the model gets the room to think
them through, accepting the slower generations that come
with it.

## Decision

`REASONING_EFFORT` and `PLAN_CHAIN_REASONING_EFFORT`
both return to "xhigh" — the value extra high carried
under ADR 0211 — so every chat call and the plan chain
reason at extra high. This supersedes ADR 0297's
medium-everywhere pin; the declaration gate in
`_reasoning_effort_param` is unchanged (the field still
goes only to the shipped slug).

## Consequences

Generations run slower and reasoning tokens bill against
the same max_tokens budget; the truncation retry in
`_chat_json` (doubling on finish_reason=length) already
covers a budget a longer think can exhaust. Pinned by the
request-shape tests, updated to the new level.
