# 0038 — Workspace type scale steps up: body and inputs at 16px

- **Status:** accepted
- **Date:** 2026-10-26
- **Anchors:** `design_guidelines.md` (§3, 4 Sizes × 2 Weights);
  `frontend/scripts/check-render-smoke.cjs` (workspace scale pin);
  `frontend/src/components/PageHeader.jsx` (`text-3xl`, `text-base`);
  `frontend/src/components/ui/input.jsx` (`text-base`)

## Context

The workspace set body copy, inputs, and titles at 14px with page titles
at 24px. Two pressures made that wrong: phones are the primary surface and
14px body is below the comfortable mobile reading floor, and iOS Safari
auto-zooms on focus for any text entry below 16px — a 14px input
punishes every founder on every field.

## Decision

- The workspace scale moves from 3 sizes to 4: `text-xs` (12px labels,
  metadata, hints — unchanged, still the AA-cleared floor), `text-sm`
  (14px controls, labels, kickers, dense data — unchanged in size,
  narrowed in role), `text-base` (16px body, inputs, titles — the new
  workhorse), `text-3xl` (30px page H1 + auth wordmark).
- Titles move with body (14 → 16 semibold; H1 24 → 30) so the hierarchy
  keeps exactly one step between levels instead of flattening.
- Deliberately unchanged: buttons and form labels at 14 (controls stay
  compact), tables/ledger rows/menus at 14 (dense data), `text-xs`
  everywhere (the quiet step hierarchy needs), marketing/LegalPage
  editorial scales, Demo + CTA canvas faces (paint, not page type).
- Filter pills hold at 14 semibold: the one sub-16px text-entry-adjacent
  control, kept compact on purpose.

## Alternatives rejected

- **Bump everything one step uniformly.** Hierarchy would flatten: titles
  landing on the same size as body just moves the smallness up 2px.
- **Redefine the `text-sm` step to 16px in tailwind config.** One line,
  but it moves ~150 instances at once — buttons, labels, dense rows —
  and deletes the 14px control step the density decisions depend on.
- **Leave 14px body, bump only inputs.** Fixes the zoom but keeps the
  smallest common body size on a mobile-heavy product.

## Consequences

- ~40 files change one utility class each; no layout rewrites, no new
  families, no weight changes. px-coupled spots (History meta
  reservation, skeletons, tour anchors) are unaffected because the 12px
  step they measure against did not move.
- The workspace scale pin now enforces xs/sm/base/3xl × normal/semibold;
  wizard subtitles stay `text-xs` and the AA check re-passes unchanged.
- Shipped as three behavior commits (inputs + H1; body; titles) plus this
  record, each green on its own.
