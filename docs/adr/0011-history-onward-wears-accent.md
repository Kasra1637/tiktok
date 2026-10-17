# 0011 — History's onward action wears accent, not brand

- **Status:** accepted
- **Date:** 2026-10-17
- **Anchors:** `frontend/src/pages/GenerationHistory.jsx:607`
  (`variant="accent"` on the Demo + CTA button)
- **Supersedes:** 0010, in part (the onward Demo + CTA's assignment to `brand`)

## Context

0010 retired coral from button surfaces and gave the onward Demo + CTA button
the dark selected surface (`variant="brand"`), on the grounds that its call
sites mean "this one is chosen". In the History drawer that reading does not
hold: beside the neutral Download button, a dark Demo + CTA button looks like
a second neutral action rather than the way onward, and on bundles predating
0010 the same call site still painted the old coral fill — a red button in the
video section either way. The drawer is a commit point (take this render into
the studio), and commit points are exactly what the indigo accent is for.

## Decision

History's Demo + CTA button wears `variant="accent"` (indigo, the acting
colour). `brand` remains the dark selected surface, now with a single meaning:
an active thumb verdict (`ThumbPair`), which genuinely is a selection among
alternatives rather than an onward action.

## Alternatives rejected

- **Keep `brand` and rebuild.** Removes the stale-bundle red but leaves the
  hierarchy problem: two dark buttons side by side, neither marked as the way
  onward.
- **Demote Download instead (accent on Download, dark on Demo + CTA).**
  Inverts the consequence order the drawer is grouped by — getting the file is
  the safe action, taking it onward is the commit.

## Consequences

- On a failed row the drawer shows two adjacent accent buttons (Retry render,
  Demo + CTA). Both are commits, so sharing the acting colour is honest; the
  labels carry the distinction.
- The palette table in `design_guidelines.md` drops the onward Demo + CTA from
  `brand`'s "Selected" use.
