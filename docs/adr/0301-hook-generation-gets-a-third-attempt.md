# ADR 0301: Hook generation gets a third attempt

Status: accepted

## Context

Sonnet 5.5's first live Hook + CTA generation (Nov 23 2026, the
evening it replaced Sol, ADR 0299) failed in the founder's hands:
the line ran 10 words against the 4-second frame's 9-word budget
(ADR 0238's numbers) on the first attempt, the correction named
the miss exactly — the words, the budget, the rewrite — and the
second attempt missed by the same one word. The loop's two
attempts were spent, so the page raised "The hook could not be
written inside its length and finish rules" and the founder got
a failure for a one-word overage the machinery understood
completely. The plan chain, the app's other gate-held flow, has
always run three editorial attempts for exactly this shape of
near-miss.

## Decision

generate_hook_line runs three attempts instead of two. Nothing
else moves: the budgets stay ADR 0238's, the gate stays whole,
the correction still names each miss and carries the budgets,
and a line still failing after the third attempt raises rather
than storing an over-long or unfinished line. No trimming, no
relaxed budget, no prompt retune — the founder's route-to-8
settlement (improve hooks through the rewrite, not the
instruction) is untouched; this is attempt count, not doctrine.

## Consequences

A one-word miss now costs one more small call instead of the
generation. The worst case is unchanged in kind — three misses
still refuse, with the last miss named in the error — and one
attempt slower in that case only. The refusal tests re-pin to
the new count, and a new test pins the shape that happened
live: two over-budget replies, then a good one, lands.
