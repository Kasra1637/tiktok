# ADR 0183: The post kit budgets for thinking plus payload

Status: accepted

Fires the watch item ADR 0129 left open. On 2026-11-16 the
mural render finished and landed in History, but its post
copy was never written: regenerating it from the card failed
twice — "Post kit was cut off after 3000 tokens
(finish_reason=length) before the JSON closed", then "Post
kit: model returned no content (finish_reason=length)" — so
the card sat in its empty state ("This render finished
before its caption was written, so there is no post copy
yet") and the founder had a finished video with no caption
to post.

## Diagnosis, measured

- **The visible payload is the smallest in the codebase.**
  For a mural-like render the call's prompt measures ~890
  tokens (system ~148, user ~744) and the answer it demands
  is bounded by the kit's own validators: a caption of 50
  to 80 characters, a pool of 12 to 15 short tags, a cover
  line — ~94 tokens for a real kit, ~297 tokens at the
  absolute worst case the validators allow. The output JSON
  is not large, and no candidate-pool field bloats it: the
  pool is a flat array of strings.
- **The budget was spent on thinking, not writing.** The
  shipped text model reasons at Max effort and the provider
  bills that reasoning against `max_tokens` (ADR 0129). The
  kit still started at the inline literal 1500 — the exact
  figure ADR 0129 recorded as a watch item ("post kit
  1500") — so attempt one had ~1200 tokens of headroom over
  the worst-case answer for all of the model's reasoning
  about the strategy rules (ADR 0139's pool shape, ADR
  0145's cover rules, the caption's constraints), and
  `_chat_json`'s doubled retry raised that only to 3000.
  Both fired live: one reply spent the whole 3000 thinking
  and returned empty content; the other reached the JSON
  and was cut mid-object at 3000. The failure is the ADR
  0129 class exactly, not a payload that grew past its
  budget — the payload ADR 0139/0145 built is mostly
  *prompt* (rules the model must reason over), and prompt
  growth raises reasoning demand, which is what the budget
  must cover.

## Decision

- **`POST_KIT_MAX_TOKENS = 6000`**, a named constant at the
  call, sized by ADR 0129's rule: twice the largest budget
  observed to return empty or truncated for this call —
  the 3000 doubled retry that failed live. `_chat_json`'s
  existing doubled retry reaches 12000 from there; it
  stays the backstop, not the budget, so no extra retry
  machinery is added.
- **Nothing about the kit changes.** The caption contract,
  ADR 0145's cover text and ADR 0139's hashtag rules
  (candidate pool, researched selection, exactly five,
  ~3 at 10k–50k and ~2 at 100k–500k, never million-plus)
  are untouched, and the prompt is not trimmed: at ~900
  tokens it is not the problem, and its rules are product
  features, not ballast (ADR 0129's rejected alternative).
- **The pin is a gate, not a number match.**
  `TestPostKitBudget` in `backend/test_ai_json_calls.py`
  replays the failure: a provider gate that returns empty
  content with `finish_reason=length` below 4000 — between
  the observed-failing 3000 and the new start — and the
  kit whole at or above it. Pre-fix, both attempts truncate
  and the test raises the founder's exact
  `TruncatedResponse`; post-fix, the first attempt already
  clears the gate. A source pin holds the constant at
  ≥ 6000 and routes the one call through it, so a future
  "tidy the number" fails a test instead of a click.

## Alternatives rejected

- **Trimming the prompt or the output contract.** The
  measured answer is ~94–297 tokens; there is no fat that
  explains a 3000-token overflow. Cutting ADR 0139/0145
  rules to save budget would shrink the kit's substance
  to fit a stale number — the inverse of ADR 0129.
- **A special larger retry for length finishes.**
  `_chat_json` already retries once at double budget with
  a shorter-values nudge; the defect was that even the
  doubled size sat under the reasoning demand. Right-sizing
  the start fixes the class; a third attempt at a bigger
  size is the same failure slower (ADR 0129).
- **Lowering the reasoning effort for this call.** Max
  effort is part of the shipped request shape for this
  model; changing it is a product decision about output
  quality, not a budget fix (ADR 0129).

## Consequences

Regenerating post copy for a finished render like the
mural one now succeeds on the first attempt with the
reasoning demand covered: the first attempt carries 6000
against a worst-case visible answer of ~297 — roughly
5700 of headroom for thought — and the doubled retry
reaches 12000. The remaining ADR 0129 watch items
(direction options 500, opening messages 3000, angle goals
4000, hook analysis 3000) are unchanged; the post kit
leaves the list. ADR 0129's watch list in its own file
stands as written — it is the historical record of the
rule that produced this fix.
