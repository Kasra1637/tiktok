# 0130 — The hook bake-off, and set character lengths as a generation rule

- **Status:** accepted
- **Date:** 2026-11-13
- **Anchors:** `backend/ai_service.py` (`_hook_bake_off`,
  `HOOK_CANDIDATES_MAX_TOKENS`, `generate_creative_plan`,
  `rewrite_hook_line`, `rewrite_spoken_line`),
  `backend/ai_spoken.py` (`_generated_spoken_issues`,
  `check_spoken_story`, `spoken_targets`),
  `backend/creative_quality.py` (`assess_spoken_quality`),
  `backend/routers/studio.py` (`suggest_hook_rewrite`,
  `suggest_line_rewrite`), `backend/test_hook_bakeoff.py`.
  Extends ADR 0115 (the craft pass) and ADR 0129 (budget sizing).

## Context

Two founder directives from one live session, after the newest pair on
the body-sensations angle rated the hook 5/10 and the script 6/10 —
the third consecutive pair whose hook sat at 4–5 while the script
climbed (3 → 6 → 6). The gates of ADR 0128 catch observable defects,
but a hook can pass every gate and still be flat: hedged ("tend to"),
impersonal, withholding nothing. No additional rule fixes that,
because the defect is not a breakage — it is a mediocre draw from a
distribution. The plan pass wrote ONE hook and shipped whatever came
back, corrected only when it broke a rule or scored under the craft
bar (ADR 0115's script-only correction, which freezes the hook by
design).

The same session produced the second directive. Review shows each
line's live count against its set aim ("59 characters, aiming for
about 60"), yet only the script-line rewrite treated length as a rule,
and even there the endpoint credited the line's own length on top of
its share — so a suggestion could be accepted at the length of a line
that was itself over its share. The hook rewrite had no length rule
at all. The founder's reason is a rendering fact, not tidiness:
over-length regenerated lines OVERLAP when rendered — the spoken
lines are laid over the video, so a line that runs past its character
budget breaks the visual. Generation must therefore be based on the
set character lengths from the start, not merely checked after the
fact.

## Decision

**The bake-off.** After the editorial loop accepts a hard-valid draft
and before the ADR 0115 craft correction, `generate_creative_plan`
runs `_hook_bake_off`:

1. One candidates call writes THREE alternative hooks for the accepted
   story (the script is fixed; it is never rewritten here). Budget:
   `HOOK_CANDIDATES_MAX_TOKENS` = 6000, sized by ADR 0129's rule from
   the rewrite family's failure history (1500 and its doubled 3000
   both truncated for a one-line payload; three lines against the same
   rules start at the family's proven floor).
2. Each candidate is measured with the accepted script by the SAME
   `_generated_spoken_issues` the editorial loop enforces — bare
   place, UI-control constructions, repeats across the pair, ending
   rules, and length past the hook's ceiling included. A candidate
   with any issue is out, however it would score.
3. The certified outcome (ADR 0127) is a HARD requirement at this
   filter, not a scoring bonus: a candidate whose hook does not carry
   it is out even when it is the highest scorer in the pool.
4. Survivors are scored by the existing craft machinery
   (`creative_quality.assess_spoken_quality` on the pair). No new
   scorer exists.
5. A candidate ships only when it scores STRICTLY above the draft
   hook. The draft is the incumbent, so the bake-off is never worse
   than the single-hook flow it replaces.
6. Fallbacks, in order: if every candidate breaks a gate, the best of
   them (fewest issues, then highest craft) gets one bounded
   correction in the editorial style, problems named; a correction
   that still breaks a gate or scores no higher is discarded — the
   editorial loop's loud stop applies to the candidate, never to a
   plan that already holds a hard-valid hook. If the candidates call
   itself fails, the plan is byte-for-byte what the single-hook flow
   produced.

The honest framing, stated to the founder when he approved it: this
raises the FLOOR. Hooks that would have shipped at 4–5 are filtered
or outscored before they reach Review. It is NOT a guarantee of an
8 or 9 on any single generation — viewers hand out the real score,
and the verdict loop (ADR 0124) remains the calibration against
posted results. The cost is one extra model call per plan (plus a
correction call only when every candidate breaks a gate), so the
plan pass takes longer; the founder accepted the wait.

**The set-length rule.** Every generated or regenerated line is sized
by its set character length as a hard acceptance rule:

- `rewrite_hook_line` takes `max_chars` — the hook's set length (the
  target `check_spoken_story` reports, the aim Review prints: 60 on a
  three-second hook, where target and ceiling meet). Both hook
  endpoints (`/rewrite-hook` and `/rewrite-line` with role=hook)
  compute it from the project's hook seconds and duration. An
  over-length suggestion is rejected, corrected once with the count
  named, and refused with the typed "kept running long" message if it
  stays over.
- A script line's suggestion must fit the line's SHARE of the script's
  set length: the middle's ceiling minus what the rest of the script
  already uses. This removes the earlier own-length credit (a
  suggestion could be accepted at the length of a line that was
  itself over its share). An over-share suggestion was already
  rejected by `rewrite_spoken_line`; it now actually receives the
  share, so the rejection binds. The endpoint's no-share-left refusal
  ("shorten it first") is unchanged.
- Bake-off candidates past the hook ceiling fail the hard filter with
  every other gate break — the same `_generated_spoken_issues` length
  check.

## Alternatives rejected

- **More prompt rules for hook quality.** The failure was variance,
  not disobedience: the rules were already followed by the 5/10
  hooks. Rules set a floor of correctness; selection sets a floor of
  quality.
- **Letting the craft correction rewrite the hook too.** ADR 0115
  froze the hook in the quality pass so a reviewed line could never
  change silently; the bake-off changes the hook BEFORE the score the
  founder reviews exists, which is the pass where changing it is the
  point.
- **Best-of-several full plans.** Three plans would triple the plan
  wait and cost to vary mostly the hook; the story and script were
  not the weak half (6 and climbing, against the hook's stuck 4–5).
- **Accepting an over-length suggestion and trimming it.** A trimmed
  sentence is a manufactured fragment — the defect class the editorial
  loop exists to refuse. Rejection plus one named correction keeps
  every accepted line a complete sentence that fits.
- **Scoring candidates on hook-only dimensions.** The pair is what
  ships and what the founder's Craft check grades; scoring the pair
  keeps the bake-off's judgment identical to the one Review shows.

## Consequences

- The plan pass makes one more model call (two more when every
  candidate breaks a gate and the correction fires). Plan generation
  is free in this product — only the render is paid — so the cost is
  wait time, which the founder accepted explicitly.
- Tests that counted plan-flow payloads gain the candidates call in
  their sequences; the pins are updated to say so rather than loosened.
- The hook a founder reviews may now be any of four lines (the draft
  or a bake-off winner); the frozen-hook guarantee of the craft
  correction is untouched — it still rewrites the script only, with
  whichever hook won frozen into it.
- `backend/test_hook_bakeoff.py` pins the order of operations with a
  scripted provider: a gated star that outscores every clean line is
  never picked (bare place AND over-ceiling), the certified star is
  filtered, the craft-highest clean candidate ships, the
  all-broken pool falls back to exactly one correction, and a failed
  candidates call reproduces the single-hook plan exactly. The same
  file pins the rewrite length rule for both roles.
