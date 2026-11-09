# 0110 — Chat generation runs on Muse Ember (Max) only

- **Status:** accepted
- **Date:** 2026-11-09
- **Anchors:** `backend/ai_service.py`
  (`DEFAULT_TEXT_MODEL`, `DEFAULT_VISION_MODEL`, `REASONING_EFFORT`,
  `_reasoning_effort_param`); `backend/test_ai_json_calls.py`
  (`TestChatModelRequestShape`); `backend/verify_chat_model.py`

## Context

Every chat flow in the studio — research, angles, plans, strategies, opening
messages, post kits and vision analysis — ran on Claude Haiku 5.5 via
OpenRouter. The product decision is that all output generation now runs on
one model, Meta Muse Ember pinned to its Max reasoning effort, and Claude
Haiku 5.5 leaves the shipped defaults entirely.

The swap changes the request shape in two ways that a slug change alone does
not cover: Muse Ember's endpoints declare `temperature` (Claude Haiku 5.5's
did not), and the Max reasoning level must travel with every call or the
model runs at another level.

## Decision

- `DEFAULT_TEXT_MODEL` and `DEFAULT_VISION_MODEL` become `meta/muse-ember`.
  `ANGLE_MODEL` keeps defaulting to `TEXT_MODEL`, so angles, the strategy
  flow and every utility flow all ride the same model.
- Every payload for the shipped slug carries `reasoning_effort: "max"`
  (`REASONING_EFFORT`, via `_reasoning_effort_param`), built in `_chat_json`
  and the vision call, beside the temperature guard.
- The effort pin is slug-scoped: an `AI_TEXT_MODEL` / `AI_VISION_MODEL` /
  `AI_ANGLE_MODEL` override pointed at another model does not inherit an
  effort level it never declared.
- Temperature needs no change of mechanism: support is already read from
  OpenRouter's per-endpoint declaration under ADR 0003, and Muse Ember
  declares it — so the field is sent for the shipped slug, while the offline
  fallback and the refuse-and-retry net in `_post_chat` stay for any override
  whose endpoints declare something else. `claude` leaves the offline
  omit-prefixes: it described the retired family, not a property of the
  shipped path.
- `backend/verify_chat_model.py` probes `reasoning_effort=max` acceptance
  in place of the retired temperature probe, next to the strict structured
  output check every shipped schema depends on.

## Consequences

- **Gain:** one model to reason about, verify and price ($0.10/$0.50 per 1M,
  the same listed price as the retired default); a 1M-token context window;
  reasoning effort is pinned by the request, not assumed from the slug.
- **Cost:** none of the Haiku-era assumptions carry over. The shipped default
  now sends `temperature` and `reasoning_effort` on every call; a future
  model swap must re-verify both fields against the live endpoints
  (`verify_chat_model.py`) rather than inheriting this record's conclusions.

## Alternatives considered

- **Slug-only swap, no effort pin:** rejected — the ask is Muse Ember
  (Max); without the pin the model runs at whatever level the provider
  defaults to, and the shipped behavior would not match the decision.
- **Pin the effort for every slug:** rejected — an override is taken as
  given for its request shape; sending one model's effort level to another
  model that never declared the parameter is how a working call starts
  400ing after a config change.
