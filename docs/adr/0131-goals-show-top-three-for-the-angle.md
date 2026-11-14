# 0131 — The goal picker shows the top 3 goals for the selected angle

- **Status:** accepted
- **Date:** 2026-11-13
- **Anchors:** `backend/ai_service.py` (`GOAL_DISPLAY_LIMIT`,
  `_select_display_goals`, `_goal_outcome_coverage`,
  `generate_angle_goals`), `backend/ai_spoken.py`
  (`certified_outcome_key_terms`), `frontend/src/components/studio/SelectionPanels.jsx`
  (`AngleGoalPicker` featured list), `frontend/src/pages/CreateVideo.jsx`
  (`handleGoalPick` mirror), `backend/test_ai_json_calls.py`
  (`TestLiveAngleGoals`). Extends ADR 0126 (goals fit the certified
  outcome).

## Context

The angle step generated six live goals for the selected angle
(ADR 0126: fitted to the angle's certified outcome, checked distinct
by meaning) and the picker showed all six, padding the grid with the
rest of the goal vocabulary behind them. Six fitted cards plus padding
is a wall of near-equal choices for a step whose whole job is one
pick. The founder's decision: show only the top 3 goals by relevance
to the selected angle — no show-more, no carousel.

## Decision

**The pool stays six; the display is three.** `generate_angle_goals`
still generates exactly six goals and runs the meaning-diversity check
over the whole pool — selection needs a pool, and the three shown stay
meaning-diverse because they are drawn from a set already proven
diverse. It then returns only the top `GOAL_DISPLAY_LIMIT` (3), ranked
by `_select_display_goals`, so every client of the live-goals endpoint
sees the same three.

**Ranking basis, strongest signal first** (recorded because the order
is the product surface here):

1. **Certified-outcome coverage** — the count of the certified
   outcome's key terms (ai_spoken.certified_outcome_key_terms, the
   ADR 0127 measure) carried by the goal's own description +
   why_it_fits, matched with the same continuity matcher
   (hook_carries_certified_outcome's). Live only when the angle
   certifies an outcome. ADR 0126 defines a goal's fit as delivering
   the certified outcome; coverage counts that from the goal's text
   instead of trusting the model's say-so.
2. **fit_score** — the generation's own 0–10 rating of this goal for
   this angle, already a goal field.
3. **Generation order** — the pool returns strongest first, so a full
   tie keeps the model's order rather than reshuffling.

The ranking is internal. No new score is computed for display: shown
goals keep exactly the fields they had in the pool (name, description,
why_it_fits, fit_score), and the picker annotates with fit_score as
before.

**The picker caps at the same three.** `AngleGoalPicker`'s featured
list is the ranked order's first three in every state — the live
selection when live goals exist, the persisted facet order otherwise —
and the vocabulary padding that used to fill a six-card grid is gone
from the display. `handleGoalPick`'s behavior-record mirror uses the
same cap, so what the app records as "shown" is what was shown. A goal
already picked from outside the three stays selected, named by the
existing outside-suggestions note.

## Alternatives rejected

- **Generate only three goals.** Selection needs a pool: three drawn
  from six meaning-checked candidates are more diverse and better
  ranked than three generated cold, and the six-goal prompt/schema
  contract (and its loud failures) stays untouched.
- **Rank by fit_score alone.** fit_score is the model grading its own
  homework. When a certified outcome exists, the deterministic
  coverage count is the stronger, reproducible signal — the same
  reasoning that made ADR 0127 check the hook's words instead of its
  score. fit_score remains the tiebreak and the only signal when
  nothing is certified.
- **Client-side selection.** Two clients could rank differently and
  the founder would see different triples on different surfaces; the
  endpoint's answer is the single source.
- **A show-more expander.** The directive was three, full stop; a
  collapsed six is still six choices wearing a trench coat.

## Consequences

- The live-goals API returns 3 goals; consumers that passed the
  response through unchanged (the endpoint, the wizard hook) needed
  no change. Tests that pinned six returns now pin the top 3 and the
  ranking rule, including a certified case where coverage outranks a
  higher fit_score.
- Goals ranked 4–6 for an angle are no longer clickable in the
  picker. A draft already carrying one keeps it (outside note), and
  Shuffle still rotates the persisted suggestion order, which changes
  which three sit on top for the curated list.
- The curated suggestion pool itself is unchanged server-side (six
  per kind in template_library); only its display is capped.
