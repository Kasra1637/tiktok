# 0101 — The hook speaks to the viewer: the hook line uses 'I' at most once

- **Status:** accepted
- **Date:** 2026-11-06
- **Anchors:** `backend/ai_service.py` (`_spoken_line_rules_block` HOOK
  bullet, `_FIRST_PERSON_I`, `_generated_spoken_issues`, the plan's schema
  line and editorial correction, `rewrite_hook_line`'s bounded correction);
  `backend/test_hook_voice.py`
- **Shapes:** the spoken-copy side of the plan and the strategy; the middle
  (script) stays the customer's first-person story

## Context

Hooks drifted into diary narration: a real draft read "Friday evening, and I
feel off, and I cannot say why." — two first-person clauses, a feelings log
as the opening line. The hook's job is the viewer's problem in the words the
viewer uses; that is what classifies the clip for the algorithm and stops the
thumb. A diary open makes the scroller an observer of someone else's evening
instead of recognising themselves, and the first clause spends its tension on
"I feel" rather than on the problem.

## Decision

- **The shared craft block (plan, strategy, and the hook rewrite) states the
  rule:** open on a question, a curiosity gap, or a frustration this viewer
  recognises — said TO or ABOUT them, never a diary — with 'I' at most ONCE
  in the whole hook line; zero is better.
- **The plan's editorial loop enforces it.** `_FIRST_PERSON_I` counts the
  standalone word and its contractions ("I'm", "I've"); more than one is an
  observable defect, so the bounded rewrite runs and the correction names the
  defect ("hook_line narrates in first person more than once").
- **The hook rewrite gets one bounded correction.** A diary-open suggestion
  is re-asked once with the defect named; if both replies keep narrating it
  raises rather than returning an unimproved line.
- **The rule is the hook's alone.** The middle/script stays first person —
  it is the customer telling what happened; the hook's opening is the part
  that must name the problem.

## Alternatives rejected

- **Prompt-only guidance.** The previous wording ("in first person") actively
  asked for the drift; without the gate the same drafts return.
- **Banning 'I' outright.** One first-person 'I' can anchor a genuine line
  ("I can never say why Friday evenings feel off" is still a problem
  statement); the product decision is at most one, not zero.
- **Refusing the plan on a wording slip.** The editorial loop rewrites within
  its bounded attempts; a hard refusal would burn a billed plan on a sentence
  the next draft fixes.
- **Counting only the standalone word.** Contractions are the same narration
  ("I'm off and I can't say why"), so they count with it.

## Consequences

- Hooks classify a problem instead of journaling a feeling; the example that
  started this ("Friday evening, and I feel off…") is now rewritten by the
  editorial loop.
- The measured strategy prompt moved 28,537 -> 29,000 (ADR 0101 comment in
  `TestStrategyBudget`); the number is recorded where every previous raise is.
- No request-shape, storage, or frontend change: the plan's fields are the
  same, only the hook's words are held to the new rule.
