# 0132 — Angle generations are unique per profile, across generations

- **Status:** accepted
- **Date:** 2026-11-13
- **Anchors:** `backend/schema.py` (`_migration_0004_offered_angle_history`,
  migration version 4), `backend/routers/brands.py`
  (`_prior_offered_angles`, `_record_offered_angles`, the three
  generation flows), `backend/ai_service.py`
  (`generate_content_angles` prior_angles), `backend/angle_policy.py`
  (`angle_collisions_with_prior`), `backend/test_ai_json_calls.py`
  (`TestAngleUniquenessAcrossGenerations`),
  `backend/test_template_library_api.py` (`TestOfferedAngleHistory`).
  Extends ADR 0125 (within-set angle diversity).

## Context

ADR 0125 made one generated set internally diverse: no two angles in
the same batch may duplicate an argument or retell the same moment.
But the set is derived data — every generation replaces it wholesale —
so nothing stopped the NEXT generation from offering the same angles
again. A founder starting a new campaign, or regenerating angles on
the same profile, could be handed the exact set they had already
seen, judged, and moved past. The founder's rule: never offer the
same angle twice; every generation must be unique.

There was no durable record to check against: content_angles holds
only the current set, and replacement deletes the old rows.

## Decision

**Record every offer.** Migration 0004 adds `offered_angle_history`
(one row per generated angle: profile, kind, label, and the
problem/promise signature the judges read). Every generation flow —
approval auto-generation, the generate endpoint, and regenerate —
appends its set at the same moment it writes content_angles, so the
record cannot drift behind what the founder has seen.

**Check against the whole record.** Before generating, the router
builds the prior set: the history UNION the live content_angles rows
(a profile whose current set predates the migration still has that
set counted, and the set a regeneration is about to replace counts
as offered), de-duplicated by signature. `generate_content_angles`
takes it as `prior_angles`:

- the prompt carries a compact ALREADY OFFERED list (label + problem,
  most recent 30) so the first attempt can steer clear;
- enforcement is deterministic, not the prompt text:
  `angle_collisions_with_prior` runs the ADR 0125 judges —
  duplicate_angle_pairs (wording) and same_moment_angle_pairs (the
  moment retold) — over prior + new as one list and keeps only the
  cross-boundary pairs. No second judge was built;
- a colliding candidate joins the same single bounded correction as
  an in-set duplicate, with the correction naming the offered angle
  it repeats; the corrected reply must return the complete set, so
  the set size never shrinks;
- a repeat that survives the correction fails loudly — a distinct
  RuntimeError naming the rule — and the caller's generate-then-
  replace order means the previous set stays exactly as it was. The
  approval-time auto-generation keeps its best-effort contract: the
  failure is logged and the old set kept, never a silent repeat.

Regenerating inside one project is a generation like any other: the
replacement set is checked against the set it replaces and every
earlier set for the profile. With no prior record (a profile's first
generation), the prompt and behavior are exactly what they were.

## Alternatives rejected

- **Prompt-only avoidance** (list the old angles, trust the model).
  The within-set rule already learned this lesson: wording is a
  request, the deterministic judges are the guarantee. A model that
  ignores the list would silently re-offer, which is the failure the
  rule exists to prevent.
- **Checking only the immediately previous set.** The rule is "never
  the same," not "not twice in a row": an angle from three campaigns
  ago is still an angle this founder has been offered. The history
  table makes the full record cheap to keep.
- **Filtering collisions out of the returned set.** Dropping the
  repeat would shrink the set below the requested count and hide the
  model's failure to find a fresh angle. Correction-then-loud-failure
  keeps the count honest and the failure visible, matching the
  in-set diversity contract.
- **A semantic/embedding judge for "same angle."** The repo's judges
  are deterministic and reproducible from the two texts alone; a
  second, softer judge would flag pairs nobody can explain. The
  witnessed failure class is the same wording/moment class ADR 0125
  already judges.

## Consequences

- Angle generation costs at most one extra model call when the
  provider repeats itself (the correction), the same bound as
  in-set diversity.
- `offered_angle_history` grows by one set per generation per
  profile, unbounded by design — it is the record the rule reads.
  The prompt render is capped at the most recent 30; the check is
  not capped.
- Hand-written (manual) angles are never recorded as offers, but the
  live rows count toward the prior set while they exist: a generated
  twin of a manual angle would read as a repeat on the founder's own
  list.
- Tests pin: correction-away of a verbatim repeat and of a
  same-moment retelling, loud failure on a persistent repeat, two
  generations for one profile coming out disjoint by both judges, and
  the endpoint recording both sets while a repeat-only regeneration
  502s with the old set intact.
