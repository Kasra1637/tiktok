# 0116 — Craft bar at 80, hook frozen in craft retry, quote salvage on exhaustion

- **Status:** accepted
- **Date:** 2026-11-11
- **Anchors:** `backend/ai_service.py` (`CRAFT_RETRY_BELOW`, `_craft_retry_block`,
  generate loop quote salvage), `backend/ai_spoken.py` (`_QUOTED_SPAN_RE`,
  `strip_quote_marks`), `backend/creative_quality.py` (POV deductions),
  `backend/tests/test_spoken_pov.py`. Amends 0115; see also 0114.

## Context

Typical Hook + Story output was landing below an 8/10 quality bar: scripts
quoted their own words, narrated stage directions, repeated the hook, or
ended on a vague stand-in. ADR 0115's bar of 60 only retried clearly weak
drafts, and its never-refuse rule still left a hard path where a model that
kept emitting quotation marks after the bounded editorial repairs failed the
whole plan.

## Decision

- **Bar at 80.** A hard-valid draft below 80 gets one targeted correction;
  keep-best still guarantees the correction never worsens the pair. Existing
  stored plans are untouched — future generation only.
- **Hook frozen in the craft retry.** The quality pass rewrites the script
  only; the hook is copied back byte-for-byte and the retry's own hook is
  discarded. A weak-but-valid hook is answered better by the script rather
  than rewritten; observably broken hooks are still repaired in the hard
  loop before craft scoring.
- **Live POV rules.** The script speaks live straight to camera in first
  person: no quotation marks (straight, curly-single and curly-double forms,
  contractions excluded), no stage directions or self-narration, no quoting
  own words as a past event, first-clause answer, single image-word echo as
  the payoff, one concrete lived detail, and no vague payoffs. All are
  identity-neutral per ADR 0089.
- **Quote salvage on exhaustion.** Quotation marks remain an editorial
  repair target for the bounded attempts. If quotes are the *only* remaining
  issue at the end of those attempts, the punctuation is stripped
  mechanically (`strip_quote_marks`: delimiters removed, contractions kept),
  the plan is logged and shipped quote-free. Every other hard defect still
  refuses.

## Consequences

- Most plans spend one extra text call; keep-best protects against a worse
  retry.
- A quote-persistent model can no longer fail a plan — worst case is a
  mechanical punctuation strip, surfaced in the Review-step `spoken_check`.
- The hook the founder saw can never silently change in a quality pass.

## Alternatives considered

- **Retry every C (0115's rejected bar of 70–80):** now accepted — the
  rubric caught POV defects the old bar let through.
- **Hard-fail on quotes:** rejected — quotable words are the price of one
  punctuation class; failing a shippable plan over marks a strip can remove
  destroys founder work.
- **Yield hook rewrite when hook scores low:** rejected — a conditional
  rewrite would break the frozen-hook contract; the script answering a
  weak-but-valid hook is the only permitted improvement at craft time.
