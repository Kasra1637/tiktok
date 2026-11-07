# 0106 — Hooks default to a statement; the middle is two beats

- **Status:** accepted
- **Date:** 2026-11-07
- **Anchors:** `backend/ai_service.py` (`_spoken_line_rules_block`,
  `_plan_requests_question_format`, `_generated_spoken_issues` with
  `allows_question`, `rewrite_hook_line` question correction, plan schema +
  editorial correction, strategy schema + "THE MIDDLE IS TWO BEATS MAX" and
  the mechanism rule), tests `backend/test_hook_voice.py` and
  `backend/test_ai_json_calls.py` (`TestStrategyBudget` ceiling 32,000)
- **Shapes:** refines ADR 0101 (hook voice) and ADR 0105 (middle voice):
  the statement default replaces the question-first opening, and the two-beat
  shape replaces the question-answering middle

## Context

ADR 0101 asked hooks to open on a question, a curiosity gap, or a frustration.
In practice the question shape dominated: the model asked the viewer's problem
rather than naming it, and ADR 0105 then required the middle to answer that
question. The middle also sprawled across situation, pain, reaction, action
and transition instead of saying one thing and letting it land.

## Decision

- **Statement default.** The hook line states the viewer's feeling or
  situation directly, never a question — unless the plan explicitly requests
  a question format. The request is detected by
  `_plan_requests_question_format` from the template's own category/name and
  opening structure (e.g. Pain-Point Question's category and its "ask … as a
  question" opening). A middle that merely mentions a question ("resolve it
  into the product question") does not count.
- **Enforcement, not just wording.** `_generated_spoken_issues` flags a
  hook-line question as a defect when `allows_question` is false, so the
  plan's editorial loop rewrites it; `rewrite_hook_line` retries a question
  answer once with a targeted correction. Founder-approved question hooks
  save through as the request that licenses them.
- **Two-beat middle.** Every plan and strategy middle is two beats max: one
  concrete action (the lived detail), then one lingering thought (the
  strongest line, last). Filler items are cut from lists. The emotional arc
  is kept in order: problem, then insight, then the shift in feeling.
  Length targets (`HOOK_TARGET_CHARS` / `SCRIPT_TARGET_CHARS`) are unchanged
  and the middle shape stays prompt-only — no brittle sentence counting.
- **All templates and plans automatically.** Both surfaces share
  `_spoken_line_rules_block`, so changing it changes the plan prompt, the
  strategy prompt and the hook rewrite together; per-template edits are
  never needed.

## Alternatives rejected

- **Prompt-only.** Without the lexical check, non-question plans kept
  drafting question hooks and the editorial loop accepted them.
- **Sentence-counting the middle.** Beats are thoughts, not sentences; a
  hard count would reject valid two-beat middles and accept filler that
  happens to be two sentences.
- **Banning questions outright.** Pain-Point Question is a selected template
  whose opening structure is a question; the decision names the default and
  its single explicit exception, it does not retire that shape.

## Consequences

- New drafts name the problem instead of asking it; the one template that
  asks for a question still gets one.
- The strategy prompt is measured at ~31,044 characters; the budget ceiling
  was raised 31,000 → 32,000 in `TestStrategyBudget`.
