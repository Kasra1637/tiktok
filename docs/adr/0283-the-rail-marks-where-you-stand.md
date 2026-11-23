# ADR 0283: The rail marks where you stand

Status: accepted

## Context

The Create Video wizard's four-segment progress rail stated the
active step with a light indigo border and wash, and a finished step
with a filled check badge — correct, but quiet: moving between steps
changed state without any tactile feedback. On Nov 23 2026 Kasra
ordered the second of three visual enhancements: the active step
gets a crisper indigo underline/accent, and checking off a completed
step gets a smooth transition, so the multi-step flow feels guided.
Navigation itself is settled (ADR 0229: the rail segments and the
sticky bar own it) and does not change.

## Decision

Three styling changes, all in the rail's existing language:

- The active segment gains `.rail-segment-active` (index.css): an
  inset box-shadow underline in full `--brand-indigo` along the
  segment's bottom inside edge, over its existing indigo border and
  wash. An inset shadow, so the accent never shifts the layout.
- The segment's transition widens from colors-only to
  `transition-all duration-300`, so state changes — the underline
  arriving, a border settling — ease instead of snapping. The step
  badge gets the same transition, so the hollow ring filling into
  the indigo check disc animates too.
- A done step's badge gains `.rail-done-badge`: one soft indigo
  pulse (a ring that swells and fades over 900ms on the app's
  signature ease) as the badge lands. The animation is declared
  only inside the `prefers-reduced-motion: no-preference` gate,
  following ADR 0264's pattern — under reduced motion there is no
  pulse and the badge is simply filled, exactly as before.

States, labels, percentages, locking and click behavior are
untouched; the ticks remain the only color story, now with an
underline under the step you are standing on.

A render-smoke check pins the mount (the active segment carries the
accent class, the done profile segment's badge carries the pulse
class) and the stylesheet (the inset underline rule and the pulse
keyframes exist).

## Consequences

The rail now answers "where am I" at a glance and rewards a finished
step with a small settle of motion. Nothing about how the wizard
navigates, unlocks or scores progress changes.
