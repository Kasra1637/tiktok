# 0104 — Movement cap raised to 600; overflow is advisory, not a block

- **Status:** accepted
- **Date:** 2026-11-06
- **Anchors:** `backend/scene_consistency.py` (`MOVEMENT_LIMIT`, `reconcile_scene`
  advisory `warnings`, `_compact_clause` limit parameter, `_truncate_to_limit`),
  `backend/ai_service.py` (`_normalize_strategy_section` per-field limits,
  strategy prompt `performance.movement` wording), `backend/server.py`
  (`_guard_render_scene` unchanged — still refuses on `blocked`), tests
  `backend/tests/test_scene_consistency.py`; supersedes the Movement clause of
  ADR 0092.

## Context

ADR 0092 capped every scene/performance field at 300 characters and made
`reconcile_scene` report a list that cannot hold its requirement instead of
cutting it. Movement is required to cover *every* action from `hook_action`
(cap 700), both section actions and the timeline's action clauses. A normal
strategy exceeds 300 characters of distinct content tokens, and
`_compact_clause` can only drop a clause when another surviving clause already
covers its tokens — distinct actions (`stands`, `reaches`, `taps`) never
qualify. So ordinary strategies were refused in `_guard_render_scene` with
"Movement cannot cover every action the sections and timeline show within its
size limit" — the founder was told to edit the script plan for a system-side
cap collision.

## Decision

- **Movement's cap is 600 characters** (`MOVEMENT_LIMIT`). The prompt asks the
  model for "a concise verb-phrase list (600 characters max)", and
  `normalize_strategy` stores up to 600. The old 300-char cap remains for
  `Props` and the other scene fields.
- **Beyond 600, Movement is advisory.** `_compact_clause` first drops redundant
  clauses; if the result still cannot fit, the field is truncated at the last
  clause boundary and returned in a new `warnings` list. The render proceeds.
  Movement is a *summary lock*: the source actions are still sent verbatim via
  `character_scene_lock`, so a shortened summary loses no approved wording.
- **`Props` keeps the ADR 0092 hard block.** A props list that cannot hold
  every object is still reported and refused rather than cut, because the
  founder reads Props as the complete object list.

## Alternatives rejected

- **Keep the 300-char Movement block.** The prompt still demands completeness,
  so verbose strategies block forever; the message for a cap collision should
  not be the founder's homework.
- **Keep the block at 600 only.** The block would just move to a larger input;
  advisory truncation is the correct fallback for a summary field, matching
  ADR 0081's pattern that only structural contradictions refuse a render.
- **Make Props advisory too.** Props is read as the object's complete list;
  silently truncating it would re-open the drift ADR 0092 closed.

## Consequences

- Ordinary strategies that used to 409 now render. The worst case is a
  truncated Movement with a visible warning, never an unexplained refusal.
- `reconcile_scene` returns an additional `warnings` entry; callers that only
  read `blocked` are unaffected.
- The extra up-to-300 characters sit inside the existing
  `RENDER_PROMPT_LIMIT=6800` budget and are absorbed by the prompt scaler; no
  provider ceiling changes.
