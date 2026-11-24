# ADR 0312: The model evaluates the Craft check

Status: accepted

## Context

The founder learned the Craft check is deterministic code with
no intelligence behind it — cue lists counting words — and
reversed his earlier no-touch ruling for the scorer (Nov 24
2026): "plug in the same ember model to do the check on those
eight areas... using the same metrics and methodology that
you are already using in those checklist... those should pass
to the ember model so the ember can then learn and read and
understand what we are looking for in the rating." This
supersedes the Nov 17 2026 entries that held the scorer
deterministic and untouched, wherever they say so.

## Decision

- The checklist writes itself out as a rubric
  (`creative_quality.evaluation_rubric`, pure): the eight
  categories, weights and reachable caps from its own
  constants, the cue vocabularies its scorers match, each
  scorer's earns/loses transcribed in `_METHODOLOGY`, and
  each category's lift read out of the scorer itself. The
  rubric IS the checklist's methodology, not a paraphrase.
- `ai_service.assess_spoken_quality_with_model` hands that
  rubric and the pair to the app's text model
  (meta/muse-ember, ADR 0310) under a strict JSON schema. The
  model returns, per category, a score, the findings on this
  clip, and the lift. `creative_quality.report_from_evaluation`
  validates the reply and clamps each score to the cap the
  category can actually award (ADR 0300), so the report is
  the exact shape every surface already stores and renders:
  same totals math, same grades, same 0–10 reading. The eight
  areas, weights, caps and display do not move.
- The evaluation produces the report at the two points the
  rendered surfaces read: the single-project read behind the
  Review card, and the submit-time freeze (ADR 0117) that
  History and Analytics render. List and mutation payloads
  keep the deterministic mirror — a list read cannot wait on
  a model per project — and a legacy row with no stored
  report still recomputes deterministically on read.
- FALLBACK: any failure — provider error, timeout, an
  unusable reply — scores the pair with today's deterministic
  scorer instead. The check never breaks a page because its
  evaluator is a model.
- NOT touched: the deterministic hard gates in `ai_spoken`
  (length bands, caps, refusals); the spoken-line rules; the
  deterministic scorer's cue logic, which stays as the
  fallback; any frontend file. Generation's internal craft
  comparisons (the hook bake-off, the editorial retry) and
  the suggestion comparisons (cover, direction change) keep
  the deterministic scorer — they compare many candidates and
  are not the rendered report.

## Consequences

One honest property: the model does not train or change
between ratings. It is handed the rubric fresh on every
evaluation, so it rates by the checklist's methodology the
same way every time — what the founder described as "learn
and read and understand what we are looking for" happens
inside each evaluation, from the rubric itself. Ratings can
vary slightly between two evaluations of the same words in a
way counted cues never did; that is the accepted price of an
intelligence judging instead of a counter. Each rendered
evaluation costs one text-model call (single attempt, 45s
bound); the frozen report keeps the score a render shipped
with stable thereafter.
