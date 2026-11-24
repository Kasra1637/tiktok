# ADR 0295: GPT-6.2 Sol replaces Muse Ember

Status: accepted

## Context

On Nov 23 2026 Kasra ordered every generation in the app switched
off Muse Ember. He named GPT-6.2 Sol, then corrected himself to
GPT-6.1 Sol, then asked Flash to compare the candidates before
anything changed — GPT-6.1 Sol, GPT-6.2 Sol, and Gemini 4 Neon,
each checked live on OpenRouter first, per his standing rule.
Flash's recommendation was 6.1 Sol: two months in production, the
same price and context, against a 6.2 six days old with uneven
early reports. Kasra's final ruling overrode it: 6.2 — the newest
model, his standing preference. The listing, checked live:
`openai/gpt-6.2-sol`, released Nov 17 2026, $2/$10 per 1M tokens,
a 1,050,000-token context window, up to 128K completion tokens,
structured outputs and image input supported.

He set the rest of the shape himself in the same conversation:
the reasoning effort goes to medium, and the temperature stays
0.4 — he asked what it currently was, heard 0.4, and ruled "keep
it that way for this one." Asked whether the new model replaces
everything Ember does, he confirmed: yes, it can.

## Decision

- `DEFAULT_TEXT_MODEL` and `DEFAULT_VISION_MODEL` now read
  `openai/gpt-6.2-sol`. Angles keep following TEXT_MODEL, so one
  pair of defaults moves every written surface at once: profile
  research, angles, plan and strategy, hooks and rewrites, cover
  text, post kit, and the vision frame analysis. The env overrides
  (AI_TEXT_MODEL / AI_VISION_MODEL / AI_ANGLE_MODEL) work exactly
  as before, and no deployment config sets them, so the code
  default is the production model.
- `REASONING_EFFORT` drops from extra high to medium.
  `PLAN_CHAIN_REASONING_EFFORT` drops from high to low, keeping
  ADR 0211's structure — the chained plan flow sits one level
  under the app-wide pin — at the new levels.
- `CHAT_TEMPERATURE` is unchanged at 0.4 (ADR 0199 stands). One
  consequence travels with the new slug: the GPT-6 endpoints
  declare no temperature parameter, so the declared-data guard
  leaves the field off the shipped model; the constant still
  governs any model that declares the field.
- The video models are untouched — HeyGen and MiniMax still
  render; only the words change hands.

## Consequences

- Text generation costs more per token: $2/$10 per 1M against
  Ember's $0.10/$0.50. Kasra made the call with the price in front
  of him, for stronger instruction-following on the doctrine the
  words must obey — pain first, no place named, finished
  sentences, the script's length band.
- The model is six days old at the switch. If its output shape
  drifts against the tuned prompts, the parse-and-retry nets and
  the finished-sentence gates absorb the first shock, and the
  fallback is the same one-line default change back.
- The request-shape pins in `backend/test_ai_json_calls.py` are
  re-pinned to the new truth: the shipped slug receives
  reasoning_effort=medium and no temperature field, and the plan
  chain's calls carry low. Two temperature tests that used the
  shipped default as their vehicle now name Muse Ember
  explicitly, since Ember is the slug that declares the field.
- `backend/verify_chat_model.py` — the live, unmocked proof that
  the shipped slug accepts the strict schema and the pinned
  effort — now describes and probes the new model at medium.
