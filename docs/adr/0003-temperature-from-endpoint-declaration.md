# 0003 — Temperature support is read from the endpoint declaration, not a model list

- **Status:** accepted
- **Date:** 2026-10-14 (decision predates this record; backfilled)
- **Anchors:** commits `0602c9bd`, `27c47b13`, `02cfed05`; `backend/ai_service.py`
  (`refresh_temperature_support`, `_temperature_param`, `_post_chat`)

## Context

Whether a chat endpoint accepts `temperature` is a property of the serving
endpoint, not the model family — and it moves. Every Claude 5.x and GPT-5/6
endpoint declares no temperature while Gemini, Qwen, GLM and DeepSeek declare
it, with older models inside the same families differing again. A
hand-maintained prefix list is wrong for some model on every change, and each
wrong entry costs a 400.

## Decision

- Support is read from OpenRouter's per-endpoint declaration
  (`supported_parameters`), cached at startup via `refresh_temperature_support()`.
- A model counts as accepting temperature only when **every** listed endpoint
  declares it (OpenRouter routes across them; a partial listing is a coin flip).
- The offline prefix list remains solely as a cold-start/network-failure
  fallback, and `_post_chat` retries once without the field if a provider
  refuses it despite declaring it.

## Consequences

- **Gain:** pointing the service at a new model needs no code change in either
  direction; a bad fallback costs one round trip, never a call.
- **Cost:** one unauthenticated endpoint-listing fetch per model at startup
  (short timeout, best-effort, never blocks boot).

## Alternatives considered

- **Hand-maintained family prefix list as source of truth:** rejected — drifts
  on every provider change and fails by 400; kept only as the offline fallback.
- **Always send temperature and retry on refusal:** rejected as the primary path —
  kept as the net beneath the declared data, since listings have lied before.
