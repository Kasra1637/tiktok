# 0105 — The middle is the hook, continued

- **Status:** accepted
- **Date:** 2026-11-06
- **Anchors:** `backend/ai_service.py` (strategy prompt "THE MIDDLE IS THE
  HOOK, CONTINUED", "WRITE THE MIDDLE AS SPOKEN WORDS, NOT APP COPY",
  "SHOW ONE LIVED DETAIL, NOT A SUMMARY", "END ON THE STRONGEST LINE"
  rules, `HOOK_TARGET_CHARS`/`SCRIPT_TARGET_CHARS` unchanged), tests
  `backend/test_ai_json_calls.py` (`TestStrategyBudget` ceiling 31,000 and
  rule-presence assertion). Extends ADR 0101 (hook voice) to the middle.

## Context

The hook line worked — it says one problem in the viewer's own words. The
middle script was weaker: it read like app copy, summarized instead of
showing something lived, made the viewer wait for the answer to the hook's
question, and buried its strongest line. "ONE STORY, TWO LINES" required the
middle to answer the hook, but the prompt never said how it should sound
aloud, show a lived moment, or close.

## Decision

Four prompt rules now govern every middle script, stated abstractly with no
fixed wording or reused examples:

- **Answered first.** The middle picks up the hook's last words and answers
  its open question within the first clause; no recap or delayed answer.
- **Spoken, not written.** Short clauses and contractions in the speaker's
  voice; no marketing verbs (discover, elevate, transform, journey,
  solution), no feature list. A hook word may be echoed from this video's own
  facts, never a fixed phrase.
- **One lived detail.** A single concrete moment from the angle/facts/usage
  moments — object, place, or routine — pins the script to this app; if the
  middle could fit any app with the name swapped, it is rewritten.
- **Strongest line last.** The final sentence is the strongest; if it appears
  earlier it is moved or rewritten to the end, never buried.

A say-it-out-loud self-check runs before output: the model re-reads the
middle and rewrites any sentence that reads as written copy, restates the
hook, delays the answer, or sounds generic. Length discipline stays:
near `SCRIPT_TARGET_CHARS=150` (unchanged), never pad under
`_strategy_middle_budget`, and claim checks remain as they were (advisory,
ADR 0081). No server-side re-check is added — enforcement is prompt-only.

## Alternatives rejected

- **Server-side lexical rewrite.** Rejected: it would need keyword
  heuristics that misfire, duplicate the model's self-check, and move voice
  rules out of the prompt where they can be versioned with the schema.
- **Fixed example sentences or templates.** Rejected: the rules must
  generalize across apps, angles, and hooks; a memorized example would make
  every script sound alike and turn craft into fill-in-the-blank.
- **Raising the middle target.** Rejected: 150 chars already fits one
  developed thought; the fix is voice, not length.

## Consequences

- Every generation's middle reads as a continuation of its own hook, with
  fresh wording grounded in that video's facts — no two scripts share a
  sentence unless the hook does.
- The strategy prompt is ~1,400 chars larger; the budget ceiling was raised
  to 31,000 (measured, pinned by `TestStrategyBudget`).
