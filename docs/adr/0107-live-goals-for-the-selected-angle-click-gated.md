# 0107 — Live goals for the selected angle, click-gated

- **Status:** accepted
- **Date:** 2026-11-07
- **Anchors:** `backend/ai_service.py` (`generate_angle_goals`,
  `_normalize_angle_goals`, `GOALS_JSON_SCHEMA`, `_angle_goal_block`),
  `backend/server.py` (`live_angle_goals`), `frontend/src/lib/api.js`
  (`generateAngleGoals`), `frontend/src/pages/CreateVideo.jsx`
  (`liveGoals` state + click handler), `frontend/src/components/studio/SelectionPanels.jsx`
  (`AngleGoalPicker` live props + Generate button); tests
  `backend/test_ai_json_calls.py::TestLiveAngleGoals`,
  `backend/test_template_library_api.py::TestLiveAngleGoalsEndpoint`
- **Shapes:** extends ADR 0098 (template requests wait for the founder's
  click) to goal generation; the facet-ordered suggestions stay the fallback

## Context

The Video Goal step ranked goals from a precomputed facet lookup keyed by
angle kind. The ranking could not use THIS angle's own audience, problem,
promise, outcome, emotion and feature — only the kind it came from — so two
angles of the same kind always saw the same six goals in the same order.

## Decision

- **Live goals from full angle context.** `generate_angle_goals` calls the
  model with the profile's verified facts plus `_angle_goal_block(angle)`
  (WHO / PROBLEM / PROMISE / SOLUTION / OUTCOME / FEELING) and returns six
  distinct vocabulary objectives, strongest first, each
  `{name, description, why_it_fits, fit_score}`. The `name` stays inside
  `VIDEO_OBJECTIVES`, so selecting a live goal still satisfies the
  plan/strategy objective contract. Same JSON-call pattern as
  `generate_content_angles` (`_chat_json`, strict schema, loud failure).
- **Click-gated, never on angle pick.** The endpoint is POST-only and the
  wizard only calls it when the founder clicks Generate goals. Switching
  goals or picking an angle queues nothing (ADR 0098's rule); the current
  facet-ordered list is what shows before that click.
- **Fallback, never a blank step.** On failure the facet-ordered list is
  kept and the error surface names the next step. The live goals are
  returned, never persisted; reloads return to the saved variant order.

## Alternatives rejected

- **Firing on angle pick.** A billed call on a pick would spend on the first
  tap, which is exactly what ADR 0098 forbids for template requests.
- **Free-form goal names.** A goal outside `VIDEO_OBJECTIVES` would be
  rejected downstream by the plan's objective handling, so the name is
  validated against the vocabulary.
- **Persisting live goals on the angle row.** That would entangle billing
  with the saved variant order; returning them keeps the row shape stable.

## Consequences

- New goals are fitted to the selected angle, not its kind, while the
  selection contract is unchanged downstream.
- A failed call costs the founder a retry, never the goal step: the facet
  list and its copy stay in place.
