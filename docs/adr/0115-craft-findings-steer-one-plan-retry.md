# 0115 - Craft findings steer one bounded plan retry

- **Status:** accepted
- **Date:** 2026-11-10
- **Anchors:** `backend/ai_service.py` (`CRAFT_RETRY_BELOW`, `_craft_retry_block`,
  `_read_plan_spoken`, `generate_creative_plan`), `backend/test_hook_voice.py`,
  `backend/test_studio_api.py`. See ADR 0114 for the score itself.

## Context

ADR 0114 added an advisory craft score over the two spoken lines. The score
made a weak pair visible in Review, but the generator still produced the same
words it would have produced without it: the score was measured after the plan
was written, and the model never saw it. A founder had to notice the card and
edit the words by hand before any quality improvement reached the next plan.

The plan flow already had a bounded editorial loop for observable defects:
length, empty or unfinished sentences, promotion, personal-history claims,
screen-action narration and question/diary hook rules. That loop retries up to
three times and then refuses an invalid draft. Craft findings are different:
they are not a reason to refuse a plan, and the loop already had to keep a
hard-valid draft alive.

## Decision

After the hard-issue loop accepts a complete, fitting draft, score it with
`creative_quality.assess_spoken_quality`. If the total is below **60** (a
clearly weak C or a D), make **one** targeted retry:

- The retry prompt carries the weakest dimensions' `next_step` text (up to
  three), the current draft as data, and the same hard rules. It is a craft
  correction, not a new brief.
- The retry routes through the same `_chat_json` envelope and JSON schema as
  the plan call, so it costs one extra text call at most.
- The retried draft must pass the same hard checks. If it does, keep whichever
  hard-valid draft scores higher. If it is invalid, weaker, missing fields or
  the call fails, keep the first draft.
- The craft retry never refuses a plan. A hard-invalid first draft still fails
  through the existing editorial loop; a hard-valid draft is never destroyed
  over craft.
- The score remains advisory: the retry improves the draft, but no score gates
  the render or the submit path.

The bar is 60, not 70. The first pass targets clearly weak drafts while
limiting billed calls; raising it to retry every C is a separate decision after
the score is calibrated against real posted performance.

## Alternatives rejected

- **Retry every C (<70).** More text calls with an uncertain lift; calibrate
  the rubric against retention/completion first.
- **Gate the render on the score.** Refuses work over taste and violates ADR
  0081 and 0114.
- **Extend the hard-issue list with craft findings.** The hard loop raises
  after its third attempt; craft must never make a plan unrenderable.
- **Ask a model judge to rewrite.** Cost, latency and self-preference; the
  deterministic score already names the weak dimensions.
- **Retry on every dimension.** A retry prompt with eight findings becomes a
  second brief; the three weakest findings are the actionable set.

## Consequences

- The plan flow costs at most one extra text call, and only when the first
  hard-valid draft scores below 60. A strong draft (for example the 91/100
  rewrite in ADR 0114) gets no extra call.
- A clearly weak pair (56/100 in the sample) gets one targeted rewrite attempt;
  a worse or invalid retry leaves the original plan exactly as it was.
- The generator itself now improves the weakest drafts instead of only
  reporting them. It is not a blanket quality guarantee: a 60-69 draft is still
  accepted without a retry, and the rubric still needs calibration against
  posted performance before the bar is raised.
- The hard checks and the advisory status are unchanged: observable defects
  still fail or retry through `_generated_spoken_issues`, and no craft score
  blocks a render.
- Tests cover the retry, the never-refuse path, the no-retry path, and the
  existing claim policy: a banned claim is still accepted as written; any
  craft retry is not a claim correction.
