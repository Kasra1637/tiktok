# 0076 — Correct duplicate angle arguments and carry recorded outcome links

Status: accepted

## Context

The angle prompt already asks for distinct arguments, but normalization accepted repeated problems and promises. It also trusted invented outcome prose despite a recorded feature-to-outcome link. Strategies already have two sections and bind approved words; neither needs redesign.

## Decision

Check normalized problem + hook promise pairs. Exact normalized pairs duplicate at any length; longer fields need at least 80% shared word trigrams in both fields. Short nonidentical phrases are not rejected. This is a conservative lexical heuristic, not semantic quality scoring.

Allow one correction request retaining profile, objective, and feedback. Reject persistent duplicates or a correction that silently depletes the original usable batch. Existing generate-before-replace keeps stored/manual angles intact on failure. Distinct arguments may share a kind, feature, or outcome.

For an exact normalized core-feature match, resolve its recorded linked outcome (flat desired outcomes second). The supported outcome replaces unanchored model prose before the angle is saved and before plan/strategy brief assembly. Manual/legacy paraphrases are not falsely certified. No missing limitation or feature is invented; approved spoken words and model/provider settings stay unchanged.

## Alternatives and consequences

Fixed six-kind quotas would conflict with the existing twelve kinds and feedback ranking. Blind deduplication/backfill would hide a depleted or invented batch. Forcing three verbatim facts into dialogue would make worse scripts and reject sparse profiles. Correction can cost one extra text-model request; failures name regeneration, never trigger a paid render.

Anchors: `backend/ai_service.py:_duplicate_angle_pairs`, `_angle_grounding`, `generate_content_angles`; `backend/test_ai_json_calls.py:TestAngleDiversity` and `TestAngleGoalPromptWiring`.
