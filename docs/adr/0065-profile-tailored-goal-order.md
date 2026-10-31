# 0065 — Goal suggestions are profile-tailored, not kind-static

Status: accepted

## Context

Every angle kind mapped to exactly six goals in a fixed curated order
(`ANGLE_GOAL_RECOMMENDATIONS`), so two profiles producing the same angle
kind got the same six goals in the same starting order. The angle was
tailored to the approved profile; the goals it selected were not — e.g. a
profile naming no competitor still led with `compare_alternative`.

## Decision

Keep the same six goals per kind, but demote ones the profile gives
nothing to stand on: `compare_alternative` sinks when the profile names no
alternative (differentiation, description, outcomes, objections scanned for
comparison signals), and `overcome_viewer_doubt` sinks when the profile
records no objection. Demotion preserves curated relative order; Shuffle
rotation applies on top of the tailored order. Evidence counts still only
annotate, never reorder.

Alternatives rejected: model-generated goal sets (nondeterministic, breaks
the stable six-goal Shuffle contract); re-ranking by past verdicts (one
verdict would present a coin flip as a measurement, the same reason angle
evidence never reorders).

## Consequences

- Goal rows open with the option the profile can actually support; the set
  and the Shuffle cycle are unchanged.
- Variant-0 order now depends on profile content, so two apps with the same
  angle kind can show different starting orders — intended.
- Anchor: `backend/template_library.py:goal_suggestions_for_profile`.
