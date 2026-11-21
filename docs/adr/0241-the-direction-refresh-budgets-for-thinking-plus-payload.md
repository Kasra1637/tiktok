# 0241 — The direction refresh budgets for thinking plus payload

Status: accepted (fires the last of ADR 0129's original watch items)

## Context

Kasra's live report (Nov 20 2026): refreshing the direction
dropdowns failed for both Location and Wardrobe with "AI
direction options failed. Please try again. (...)" — the HTTP
502 that `POST /app-profiles/{id}/direction-options/refresh`
(`backend/routers/brands.py`) raises when
`ai_service.refresh_direction_options` raises RuntimeError.
Both fields failed identically because both are the same call.

## Diagnosis, from the code

- **The refresh was the last small budget standing.**
  `refresh_direction_options` called `_chat_json` with
  `max_tokens=500, timeout=60` — the only 500-token call left in
  `backend/ai_service.py`. Every comparable lightweight call
  starts at 3000–16384 (rewrites at `REWRITE_MAX_TOKENS` 6000,
  the post kit at 6000 after ADR 0183, angles at 8000).
- **The budget was spent on thinking, not writing.** The call
  passes no reasoning override, so it runs at the pinned
  `REASONING_EFFORT = "xhigh"` (ADR 0211), and the provider
  bills that reasoning against `max_tokens` (ADR 0129). The
  visible answer is four short phrases; the reasoning about
  the profile, the angle's fixed place and time, and the avoid
  list is what the budget must cover. At 500, reasoning alone
  can consume the whole budget before any JSON is written.
- **The retry could not rescue it.** `_chat_json` detects
  `finish_reason=length` (or empty content) and retries once
  with a doubled budget — 500 → 1000, the smallest retry in
  the system — then raises `TruncatedResponse`, which the
  endpoint wraps as the 502. This is the exact exposure ADR
  0129's budget watch flagged ("direction options at 500
  tokens is the most exposed remaining call"), and the same
  failure family ADR 0183 fixed for the post kit.

## Decision

- **`DIRECTION_REFRESH_MAX_TOKENS = 4000`**, a named constant
  at the call, sized for this call under ADR 0129's rule: the
  largest budget observed to fail is the doubled 1000, and
  4000 puts the start above every other lightweight call's
  floor with the headroom going to reasoning, not payload.
  `_chat_json`'s existing doubled retry reaches 8000 from
  there; it stays the backstop, not the budget.
- **Timeout 60 → 90 seconds**, matching the call's lightweight
  peers (opening messages and the angle calls sit at 90): at
  extra-high effort a reasoning-heavy reply needs the room to
  arrive, not just the tokens to exist.
- **Nothing else about the call changes.** Same prompt, same
  strict schema, same cleaning, same 4-option contract, same
  endpoint and error wording. The deterministic
  `profile_direction_options` endpoint (no model call) is
  untouched, and no other call's budget moves.
- **The pin is a gate, not a number match.**
  `TestDirectionRefreshBudget` in
  `backend/test_ai_json_calls.py` holds the constant at
  ≥ 4000 with the one call routed through it, records the
  payload budget and the client timeout on a clean reply
  (4000, 90s), and replays the failure: a first reply of
  empty content with `finish_reason=length`, with a retry
  landing only if its doubled budget clears the gate.
  Pre-fix the replay raises the founder's exact
  `TruncatedResponse` at budgets 500 and 1000; post-fix the
  retry lands at 8000 and returns the four options.

## Alternatives rejected

- **Lowering the reasoning effort for this call.** The
  extra-high split is Kasra's ruling (ADR 0211); effort is a
  product decision about output quality, not a budget fix
  (ADR 0129's standing rejection, repeated in 0183).
- **Trimming the prompt or the option contract.** The answer
  is four short phrases — there is no payload fat. The
  profile/angle grounding in the prompt is the feature; the
  budget absorbs the reasoning it demands.
- **A special larger retry for length finishes.**
  `_chat_json` already retries once at double budget; the
  defect was that even the doubled size sat under the
  reasoning demand. Right-sizing the start fixes the class.

## Consequences

Refreshing Location or Wardrobe now starts with roughly
3900 tokens of headroom over the four-phrase answer for the
model's thought, and the doubled retry reaches 8000, so the
reasoning spike that 502'd live lands as fresh options.
ADR 0129's watch item for direction options is closed; the
watch list in 0129's own file stands as written — it is the
historical record of the rule that produced this fix. The
remaining small budgets 0183 named (opening messages 3000,
angle goals 4000, hook analysis 3000) are unchanged and
still governed by the same rule: the first observed failure
is fixed by doubling into a named constant with a gate pin.
