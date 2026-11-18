# ADR 0199: One temperature for every text generation — 0.4

Status: accepted

Kasra ruled on Nov 17 2026 that the app speaks with ONE fixed
temperature for all text generation through OpenRouter, set at
0.4, so the words sound solid and consistent through every
video's copy. Seven creative flows had grown their own values
over time — cover text 0.6, brand templates 0.5, hook rewrite
0.6, spoken-line rewrite 0.6, hook bake-off 0.7 and 0.6, video
strategy 0.5 — so the same app's copy was being sampled at five
different temperatures depending on which button produced it.

## Decision

- The seven explicit `temperature=` overrides in
  `backend/ai_service.py` are removed. Each of those flows
  (`generate_cover_text`, `generate_brand_templates`,
  `rewrite_hook_line`, `rewrite_spoken_line`, `_hook_bake_off`
  both calls, `generate_video_strategy`) now falls back to the
  `_chat_json` default, which is `CHAT_TEMPERATURE`.
- `CHAT_TEMPERATURE` stays 0.4, and its comment now records that
  it is the single app-wide value by the founder's ruling — no
  per-flow overrides.
- The `_temperature_param` endpoint-support guard machinery is
  untouched: whether a given endpoint accepts the field at all
  remains a measured, per-endpoint fact.

## Exceptions, named by the ruling

- `analyze_hook`'s vision call keeps sending 0.3 via
  `_temperature_param(VISION_MODEL, 0.3)`. That is video-side
  frame analysis, not text generation, and sits outside the
  ruling.
- The app-profile research/generation flow carries no override
  today and already rides the shared default; its call path is
  left exactly as it is.

## Consequences

Pins live in `backend/test_chat_temperature.py`: the constant
is 0.4, the `_chat_json` default is the constant, none of the
six ruled functions (seven call sites) passes an explicit
temperature, no numeric `temperature=` kwarg exists anywhere in
the module, and the vision call still sends 0.3. A future flow
that wants its own temperature now has to break a test to get
one — which is the point: the exception would be a decision,
not an accident.
