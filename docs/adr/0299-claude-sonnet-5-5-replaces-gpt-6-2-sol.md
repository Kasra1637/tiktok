# ADR 0299: Claude Sonnet 5.5 replaces GPT-6.2 Sol

Status: accepted

## Context

GPT-6.2 Sol shipped as the app's text and vision model one day
earlier (ADR 0295). The comparison Kasra then ran — live
OpenRouter prices against his benchmark table — put Claude
Sonnet 5.5 at the same listed price as Sol ($2/$10 per 1M,
checked Nov 23 2026) with the stronger benchmark score of the
two (69.45% against 65.07%), and Kasra picked it: the switch off
Sol 6.2, to Sonnet 5.5, across every written surface at once, the
same one-setting reach as the swap it reverses. Measured on
Sonnet 5.5's endpoints listing before the build: five endpoints,
reasoning_effort and response_format declared on all five,
structured_outputs on three, temperature on none, a 1M-token
context and a 128K completion ceiling.

## Decision

DEFAULT_TEXT_MODEL and DEFAULT_VISION_MODEL are
anthropic/claude-sonnet-5.5. Everything Kasra set around the
model stands untouched: reasoning effort medium everywhere, the
plan chain included (ADR 0297), and CHAT_TEMPERATURE stays 0.4 in
code — a field Sonnet's endpoints do not declare, so the
declaration guard leaves it off the shipped slug exactly as it
did for GPT-6, and the Claude 5 families join the offline
fallback's omitted prefixes so a cold process does not spend a
refused call learning it. Model selection stays env-overridable;
the video models are untouched.

## Consequences

One day of Sol ends. The app has no production output record on
Sonnet yet — its first live generations are the proof, watched
the same way Sol's first failure was caught within minutes. The
strict-JSON flows ride on response_format, declared everywhere
Sonnet is served; where an endpoint treats the schema as a hint,
the parse-and-retry net that already exists is the catch. If
Sonnet disappoints, the way back is the same one-setting change,
and Ember's record (ADR 0295's context) is unchanged by this
ruling.
