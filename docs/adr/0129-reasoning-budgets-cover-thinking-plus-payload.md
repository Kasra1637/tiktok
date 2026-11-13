# 0129 — Every reasoning-model call budgets for thinking plus payload

- **Status:** accepted
- **Date:** 2026-11-13
- **Anchors:** `backend/ai_service.py` (`PLAN_MAX_TOKENS`,
  `STRATEGY_MAX_TOKENS`, `REWRITE_MAX_TOKENS`, the model note at the top
  of the file, `_chat_json`'s truncation handling),
  `backend/ai_spoken.py` (`_BARE_PLACE_RE`, `_bare_place_noun`),
  `backend/test_ai_json_calls.py` (`TestCreativePlanBudget`,
  `TestStrategyBudget`, `_BudgetGate`),
  `backend/test_spoken_line_rewrite.py` (`_BudgetRecorder`, the rewrite
  precedent), `backend/test_hook_voice.py` (the ADR 0129 gate section).
  Extends the budget half of ADR 0128.

## Context

The shipped text model reasons at Max effort, and the provider bills
that reasoning against the same `max_tokens` budget as the visible
answer. A call whose budget covers its payload but not its thinking
does not truncate politely — it returns empty content with
`finish_reason=length`, which reads as "the model had nothing to say"
while the budget was simply spent before the first word was written.

This failure class has now bitten four times, and each fix was local:
research 4000 → 8000, angles 3000 → 8000, strategy 8192 → 12288, plan
3500 → 8000, and the one-line rewrites 400 → 1500 (ADR 0128, which
named the constant `REWRITE_MAX_TOKENS`). On 2026-11-13 the plan
failed live in Review & submit — "Creative plan: model returned no
content (finish_reason=length)" — at the 8000 start AND at the doubled
16000 retry: verdict steering (ADR 0124), the certified-promise check
(ADR 0127) and the spoken gates (ADR 0128) had grown the prompt until
the reasoning alone ate 16000 tokens. The strategy call, second in the
same one-pass request, still started at 12288 — below the line the
plan had just proved insufficient — while carrying the largest JSON
schema in the codebase.

Minutes later, the same live session proved the rewrite fix of
ADR 0128 was also undersized: "Suggest a clearer hook" on "On bus
stop days emotions come, words won't, I check in." returned the typed
truncation message — which only surfaces after both attempts are
exhausted, so the 1500 start and its doubled 3000 retry had both
truncated. The honest naming worked; the budget was still short. The
pair in that screenshot also repeated the article break in two shapes
the ADR 0128 grammar gate did not watch: the place compound stood
bare in "On bus stop days…", and the script dropped the article after
a different preposition, "waiting beside signpost until 8:15" —
"signpost" being a noun the gate's class never listed.

## Decision

- **The general rule:** every call to a reasoning model budgets for
  thinking plus payload, never for the payload alone. The first
  attempt must clear the reasoning demand by itself; `_chat_json`'s
  doubled retry is a backstop for a bad draw, not the budget.
- **Sizing:** a family's budget starts at twice the largest budget
  observed to return empty or truncated for a call of its class, and
  lives in a named constant per call family, in the style of
  `REWRITE_MAX_TOKENS`, with the failure history recorded at the
  constant. A family that has not failed yet but starts below a
  proven-insufficient line for a comparable prompt doubles its start
  rather than waiting for its own production failure.
- **The plan:** `PLAN_MAX_TOKENS = 32768` (twice the 16000 observed to
  return empty) at both call sites — the draft call the bounded
  editorial loop reuses (its corrections re-send the whole plan and
  demand the whole plan back, so they need the same headroom) and the
  craft correction.
- **The strategy:** `STRATEGY_MAX_TOKENS = 24576` (twice its 12288
  start), attempts unchanged at 3, so the retries reach 49152.
- **The rewrites, again:** `REWRITE_MAX_TOKENS` rises 1500 → 6000,
  twice the 3000 retry observed to truncate. The recorder gate in
  `test_spoken_line_rewrite.py` moves its threshold to 4000 — between
  that retry and the new start — and the constant itself is pinned,
  so the next shrink fails a test instead of a click.
- **The grammar gate follows the witnessed shapes:** `_bare_place_hit`
  watches the article drop after the prepositions a speaker locates
  with (at, beside, by, near, outside, inside), "signpost" joins the
  noun class, and the bare compound in front of "days" ("on bus stop
  days") matches as its own frame. The deliberate exclusions are
  untouched — home, work, night, school and church stay unflagged
  because their nouns never enter the list — and a determiner or
  possessive after any watched preposition still breaks the match.
  The fix advice names the noun via `_bare_place_noun`, since the
  phrase no longer always starts with "at ".
- **Pins:** each family's budget is pinned the way the rewrite budget
  is — a provider gate that returns empty content below a threshold
  set between the old budget and the new one, asserting the first
  attempt already clears it — plus a source pin on the constant, so a
  future "tidy the number" change fails a test instead of a founder's
  evening.

## Alternatives rejected

- **Copying the rewrite's 1500 to the plan.** The rewrite's payload is
  one sentence; the plan's is a full document, and its reasoning
  demand alone had already consumed 16000. A number is sized from the
  response the prompt demands, not borrowed from another family.
- **Lowering the reasoning effort for these calls.** Max effort is
  part of the shipped request shape for this model, and the plan's
  constraint load is exactly what the thinking is for. Changing it is
  a product decision about output quality, not a budget fix.
- **More retries at the same budget.** `_chat_json` already retries
  with a doubled budget; a third attempt at an exhausted size is the
  same failure slower.
- **Shrinking the prompt back.** Verdict steering, the certified
  promise and the spoken gates are product features (ADRs 0124, 0127,
  0128), not ballast. The budget absorbs the growth; the features
  stay.

## Consequences

- Plan generation no longer dies on an empty reply at the budget the
  old code started with, and the strategy no longer starts below a
  proven-insufficient line in the same request.
- Larger starts cost more per call when the model uses the room; the
  plan and strategy are free pre-render steps, and a failed generation
  that reads as a timeout costs the founder more than the tokens do.
- Known watch items, deliberately unchanged: the remaining small
  budgets (direction options 500, post kit 1500, opening messages
  3000, angle goals 4000, hook analysis 3000) belong to families with
  small payloads and no observed empty-content failure. Under this
  rule, the first such failure in any of them is fixed by doubling
  into a named constant with a gate pin — not by another local bump.
