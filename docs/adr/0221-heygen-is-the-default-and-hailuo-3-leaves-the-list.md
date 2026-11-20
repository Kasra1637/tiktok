# 0221 — HeyGen is the default, and Hailuo 3 leaves the list

Status: accepted

## Context

Kasra's two linked orders on Nov 19 2026: remove the video model
`minimax/hailuo-3` (catalog key `minimax-h3`) from the app's model list,
and — when the removal needed a successor — "HeyGen should be the
default model," naming HeyGen Video himself over the MiniMax H3 Max
option that was put to him.

The removal could not be a one-line deletion. `minimax-h3` was the
app's standing default: `ai_service.DEFAULT_VIDEO_MODEL` pointed at
it and is read at import time (`VIDEO_MODEL` is derived from it), and
both surviving models were recorded in the catalog as opt-in only. A
first attempt at the removal stopped on exactly that: deleting the
entry without a named successor would have meant inventing a default,
which is a product decision, not a refactor. Kasra then named HeyGen
Video, and this change carries out both orders together.

Hailuo 3 was the only model on the list that renders 2K. Removing it
therefore also settles the default's picture: the standing default
becomes HeyGen Video at 768p, and no catalog entry renders 2K any
more. Kasra made the call knowing that trade.

## Decision

1. **Hailuo 3 is removed from the catalog.** The `minimax-h3` entry
   leaves `ai_service.VIDEO_MODELS`, its capability notes (including
   its 6,800-character prompt ceiling) leave
   `video_providers._CAPABILITY_NOTES`, and the key leaves
   `STUDIO_ELIGIBLE`. The drift check in `provider_capabilities.py`
   iterates `STUDIO_ELIGIBLE`, so it stops expecting the model with
   no change of its own. Nothing else was keyed on the model: the
   prompt ceilings, the duration planning and the hook-length rules
   all read whichever capability record they are handed.

2. **HeyGen Video is the standing default.** `DEFAULT_VIDEO_MODEL`
   is repointed to `heygen-video-1`, so `default_model_key()`, the
   `GET /studio/video-models` endpoint, and every caller that names
   no model resolve to HeyGen. The environment levers are unchanged:
   `VIDEO_MODEL_DEFAULT` and `VIDEO_MODEL_ALLOWLIST` still override
   the shipped default, and allowlisting H3 Max alone still makes it
   the default — that documented switch keeps working.

3. **MiniMax H3 Max stays, opt-in, untouched.** Its catalog entry,
   capability record, 768p resolution, first-frame identity route and
   6,800 ceiling are exactly as they were. It becomes the model a
   render uses only when it is named, or when an operator allowlists
   it alone. Its pins were reworked only where they asserted facts
   about Hailuo 3 beside it.

4. **Existing projects keep the established removal contract** — the
   Seedance/Grok precedent of ADR 0006, unchanged in shape, now
   landing on HeyGen:
   - A generate request that explicitly names the stored `minimax-h3`
     is refused before any spend by `_assert_model_usable`: a loud
     HTTP 400 naming the key and the models that remain. Silently
     rendering a stale pick on a different model is the one outcome
     the boundary exists to prevent.
   - Read and resolve paths degrade instead: `video_providers.resolve()`
     and `capability()` treat the stale id as unknown and return the
     default — now HeyGen — with the reason recorded
     (`provider_reason` on the generation), never a 500 and never
     silently keeping the removed model.
   - A direct `ai_service.generate_video` caller naming the removed
     key resolves to the default inside the provider call, the
     last-resort guard that layer has always kept.

5. **The words follow the facts.** Every passage that named Hailuo 3
   as the default or HeyGen as opt-in — the catalog header, both
   entries' comments and descriptions, the capability notes, the
   eligible-list comment, and the identity-routing docstrings that
   described Hailuo 3's reference-image route as current — now states
   the new truth. Historical records (older ADRs, measured-failure
   stories) keep their wording; they describe the past correctly.

## Consequences

- A render that names no model is now a HeyGen render: 768p instead
  of 2K, synthesized audio, HeyGen's 4,090-character prompt ceiling
  with the spoken script sacred, and the founder's photo pinned as
  the opening frame — where the old default carried it as a
  reference image. Founders who had been rendering on the default
  will see that identity route change on their next render.
- Fixed camera has no servable model for now. The submit guard
  refuses a first-frame model for a fixed setup — a pinned photo
  cannot open a stationary head-to-mid-thigh shot — and both
  remaining models pin the first frame, so every fixed-camera submit
  meets that 409, on a named model and on the default alike, until a
  reference-route model returns to the list or the guard is
  revisited. No model is switched in silently; handheld is
  unaffected. The fixed-strategy direction-conflict refusal still
  stands in the prompt builder; at the submit boundary the model
  guard now fires first.
- H3 Max is now the roomiest prompt budget on the list (6,800) and
  the refusal a tight HeyGen ceiling produces names it as the way
  out, which the prompt-ceiling refusal already did from live data.
- Tests: the default pins now assert HeyGen; `test_hailuo_3_remains_the_default`
  is replaced by a pin that HeyGen is the default and `minimax-h3` is
  absent from the catalog and the eligible list; the opt-in pin for
  HeyGen is inverted; the exact-entry pin for Hailuo 3 is replaced by
  absence pins; the 2K payload pin is replaced by a pin that a removed
  key falls back to HeyGen inside the provider; the API suite gains a
  pin that an explicitly stored `minimax-h3` is refused with a 400
  before spending, and the default-identity pin now asserts HeyGen's
  pinned-frame route. The fixed-camera API pins now assert the model
  guard's refusal on the default as well as on a named model, and the
  app-specificity suite's render helper names H3 Max, since it pins
  the full-form prompt contract and the default now hands the builder
  HeyGen's condensed form (pinned in its own suites). H3 Max's opt-in
  pins stand as they were.
