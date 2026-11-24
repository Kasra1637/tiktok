# ADR 0297: The plan chain runs at medium

Status: accepted

## Context

Kasra's model-switch order (ADR 0295) named the level plainly:
set the generation effort to medium. The switch kept ADR 0211's
structure — the app pin at medium, the plan-and-strategy chain
one level under it — which put the chain at low on a model the
app had never generated with. The chain is the most
gate-constrained flow in the app: up to three editorial attempts,
each draft held to complete, fitting spoken sentences inside the
hook and middle budgets and the script's delivery band, with
nothing saved when every attempt misses. On Nov 23 2026, minutes
after the switch deployed, Kasra's first live plan generation
failed exactly that way — all three attempts refused, "no
incomplete draft was saved" — on a flow that had generated fine
on the old model at high the same day.

## Decision

The one-level-under structure is retired. PLAN_CHAIN_REASONING_EFFORT
is "medium" — the level Kasra named, applied to the chain as to
everything else. No gate, budget, band, or attempt count changes:
the drafts are still refused rather than saved incomplete, and
the chain simply thinks at the level the founder set when it
writes them. The pinning test moves with the constant.

## Consequences

Plan generation runs slower than the low pin would have, in
exchange for drafts that clear the app's own bars on the new
model. If a future model earns a cheaper chain, that is a fresh
ruling on fresh evidence — the structure no longer demotes the
chain silently as a side effect of an app-wide level change.
