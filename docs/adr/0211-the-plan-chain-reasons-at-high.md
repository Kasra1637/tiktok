# 0211 — The plan chain reasons at High, and everything else at extra high

Status: accepted

## Context

On Nov 19 2026 Kasra timed the plan step live: "It takes 90
seconds sometimes, way too long" — one plan took over 100
seconds — and ordered the cause found and fixed. When the
diagnosis came back, he extended the order: "also reduce
everything else to extra high." His reason is speed, across the
app, not just the plan.

The plan wait is the chain, not any single call. One click on
Generate plan hits `POST /studio/projects/{id}/plan-and-strategy`
(`backend/routers/studio.py:2559`), which runs the plan stage and
the strategy stage back to back. The plan stage
(`generate_creative_plan`, `backend/ai_service.py:4530`) chains,
all sequentially:

1. an editorial loop of 1–3 full plan calls at
   `PLAN_MAX_TOKENS=32768`, each with a 120s timeout;
2. the hook bake-off (ADR 0130): one candidates call at
   `HOOK_CANDIDATES_MAX_TOKENS=6000`, plus one bounded correction
   call when every candidate breaks a gate;
3. one craft correction call at `PLAN_MAX_TOKENS` whenever the
   accepted draft scores below the 80 bar (ADR 0115).

The strategy stage then makes its own call at
`STRATEGY_MAX_TOKENS=24576`. Every one of these calls went
through `_chat_json`, which pinned `reasoning_effort` to
`REASONING_EFFORT = "max"` (ADR 0110) for the shipped slug. A
clean run was 3 sequential Max-reasoning calls; a typical run 5;
the worst case 7 or more. The wait was the sum of Max thinking
times, paid one call after another — and every other flow in the
app paid the same Max level on its own calls.

## Decision

1. **`_chat_json` gains a per-call reasoning-effort override**
   (`backend/ai_service.py:943`). When a flow passes
   `reasoning_effort`, the payload carries that level; when it
   does not, the payload carries the app-wide pin exactly as
   before — and nothing for any other slug. The override rides
   the same declaration gate as the default
   (`_reasoning_effort_param`, `backend/ai_service.py:439`,
   ADR 0003): the field is sent only where the shipped slug
   declares it, override or not.
2. **The plan-and-strategy chain passes the override at High** —
   `PLAN_CHAIN_REASONING_EFFORT = "high"`
   (`backend/ai_service.py:135`) — at exactly its five call sites:
   the plan editorial loop (:4980), the bake-off candidates call
   (:4470), the bake-off correction call (:4534), the craft
   correction (:5111) and the strategy call (:6036). The strategy
   call is the strategy stage's one call, so the stage's own
   rebuild endpoint — the same function, the same wait — carries
   High too.
3. **The app-wide pin drops from Max to extra high**:
   `REASONING_EFFORT = "xhigh"` (`backend/ai_service.py:127`).
   Every other chat flow — profile research, angles, goals,
   rewrites, post kit — now reasons one level down from where
   ADR 0110 set it. This supersedes ADR 0110's
   `reasoning_effort=max` pin; ADR 0110's model choice (Muse
   Ember for every chat flow) stands untouched.
4. **Nothing else about the calls changes.** Temperature is
   untouched (ADR 0199: one fixed 0.4; the app-profile flow keeps
   its own path; the vision frame-analysis call stays video-side).
   Token budgets are untouched: ADR 0129 sized them for Max
   thinking billed against the budget, and both new levels reason
   less, so the budgets only gain headroom — no budget is shrunk
   on a guess.

## Alternatives rejected

- **Drop the bake-off or the craft correction.** Both are the
  founder's quality directives (ADRs 0130 and 0115): the bake-off
  raises the hook floor, the correction lifts a sub-80 draft.
  Buying speed by deleting quality machinery trades the product
  for the stopwatch.
- **Lower only the plan chain and keep Max everywhere else.**
  This was the first shape of the fix; Kasra overruled it
  directly — the wait he objects to is not only the plan's, and
  one-shot flows at Max were paying the top level for thinking
  their answers do not need.
- **Shrink the prompts.** The strategy prompt is ~48k characters
  of load-bearing rules; trimming it is a quality project of its
  own, and it is secondary — the multiplier was the reasoning
  level paid on every call, not the size of any one call.

## Consequences

A clean Generate plan run is now 3 sequential High-reasoning
calls instead of 3 at Max, the worst case shrinks by the same
factor per call, and every other generation in the app thinks
at extra high instead of Max. The chain's structure — how many
calls, in what order, with what gates — is unchanged, so the
quality machinery behaves exactly as before and only the
thinking level moved. Pins: `TestPlanChainReasoningEffort` in
`backend/test_ai_json_calls.py` proves an overridden call sends
the override, an override for another slug sends no field, and
every payload of a full plan run plus the strategy call carries
High; `TestChatModelRequestShape` now pins the new default —
a default call sends `xhigh`, and the one older test that pinned
the plan flow itself at Max now pins the split: direct flows at
xhigh, the chain at High.
