# 0134 — The render panel shows one primary action: the un-saved plan hides Generate too

- **Status:** accepted
- **Date:** 2026-11-14
- **Anchors:** `frontend/src/components/GenerationPanel.jsx`
  (`planSaveRequired`, the generate gate, the save-edits remedy),
  `frontend/scripts/check-render-smoke.cjs` ("GenerationPanel shows only
  the save remedy while the plan is unsaved"). Extends this panel's
  one-action rule (rebuild owed; no strategy — the latter folded into
  the ADR 0128 push) and ADR 0133 (the bar carries the one unblocking
  action).

## Context

The founder screenshotted the render panel with two primary buttons
stacked: a greyed "Generate the video" above a bright "Review and save
the plan". The state is reachable and ordinary — the strategy exists
and is current, but the plan itself is not saved (saving a content edit
returns the project to draft, so `status` is not
`ready_for_generation`). The one-action rule already hid Generate while
a rebuild was owed and before a strategy existed, but the un-saved plan
was not one of its states: Generate rendered disabled for `!ready`
while the save remedy rendered bright beside it — two competing
actions, one of which could not act.

## Decision

**Where a blocking remedy is the required next action, "Generate the
video" is not rendered at all; only the remedy shows.** The un-saved
plan (`planSaveRequired`: not ready, with a photo, an angle, and no
stale or drifted strategy) joins the rebuild-owed and no-strategy
states under the same gate. The condition is named once in the panel
so the remedy and the gate cannot drift apart. The explanatory copy
("Review and save your script plan first. A saved plan is checked
before rendering.") stays, and the in-flight carve-out is unchanged: a
render already running keeps its progress button, and the remedies
stand down while one runs.

The navigation remedies keep the old shape deliberately: with no angle
picked or no photo attached, the remedy jumps to another step and the
disabled Generate stays as the gate that names the block — those
states were carved out when the rule was first set, and this extension
does not reopen them.
