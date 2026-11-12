# 0081 — Remove claim wording as a render block

Status: superseded by 0119

## Context

The claim-safety report (`backend/claim_safety.py:build_safety_report`) refused
renders over wording: founder-banned phrases and feature-list shapes set
`passed` to `False`, and the ready gate (`_require_claims_clear`), the submit
gate, the Generate button (`GenerationPanel`), the strategy panel
(`HookContinuityPanel`), and the Review `SafetyPanel` all enforced it. The
plan and strategy generators retried drafts — and failed loudly — over the
same wording. Founders repeatedly met "Fix the flagged wording before
rendering" / "BLOCKS RENDERING" on ordinary copy (e.g. "typing and reading")
and could not render without editing or regenerating.

## Decision

No wording flag may refuse a render. `build_safety_report` always returns
`passed: True` with `blocking: []`; `_require_claims_clear` recomputes and
returns the report without raising; the plan/strategy generators accept drafts
as written (length/shape retries unchanged); and the frontend drops the block
message, block section, repair actions, and button gating. Reports, warnings,
and claim evidence remain advisory. Old stuck projects clear on next
load/regenerate because every gate recomputes live.

## Consequences

- Generate stays enabled regardless of wording; banned-claim and feature-list
  copy can reach a paid render.
- Post-kit and opening-message guards are untouched (separate flows).
- Tests that asserted blocking now assert never-blocks.

Rejected alternative: keep blocking for banned claims only. The founder asked
for removal after repeated false-feeling blocks, and a half-block keeps the
same message on screen.
