# 0189 — The History filter bar splits, and the attention banner's action sits with its sentence

Status: accepted

## Context

On the Nov 17 2026 evening call, the founder proposed moving all
seven History filter controls (search, the copy dropdown, Full cards,
Compact, All apps, All statuses, Newest first) from under the
"Generation History" headline up to the right of the "With post copy
& plan context · 6 total" group label.

Flash's design call was no: those are page-level filters, and parking
them beside a group label mis-scopes them — the label names one group
of cards, the filters govern the whole page — and seven controls
would wrap awkwardly there. The counter-proposal was a split: the
filters stay grouped on the left under the title, and only the Full
cards / Compact view toggle moves to the far right of the filter row,
because the toggle is not a filter at all — it changes how every card
is drawn, not which cards show. The founder answered "Okay. Go
please.", approving the split, not the original move.

On the same call he pointed at the attention banner ("N finished
renders have no post copy yet. Open its card and press Generate post
copy."): its "Review without copy" action floated detached at the
banner's far right edge and "looks awkward right now" — place it
somewhere more appropriate, grouped with the notice.

## Decision

1. **The toolbar splits.** In `GenerationHistory.jsx` the view toggle
   (`history-view-toggle`) carries `ml-auto`, seating it at the far
   right of the filter row on wide screens and wrapping below the
   filter group, still right-aligned, on narrow ones. The search, the
   copy filter, the More filters expander and the secondary row (All
   apps, All statuses, sort) do not move. No control is removed,
   renamed or re-behaved; the filter-polish styling and states are
   untouched. Nothing moves beside the group label — that placement
   was considered and refused.
2. **The banner composes as one row.** The attention banner's
   description is no longer a flex row that can strand the action at
   the edge: the summary, the guidance and the action now flow inside
   one span (`history-attention-text`), the button sitting inline
   immediately after the sentence it belongs to. The banner is shared
   markup, so the repair variant ("Review repair") composes the same
   way. Words, count logic, link destination and behavior are exactly
   as before — only the placement changed.

## Consequences

A new smoke check ("History toolbar splits filters left and view
toggle right, and the attention action sits with its sentence", red
before green) pins the toggle's right-aligned group after the filter
group in DOM order, and the action rendered inside the notice's text
group with the notice's words. No existing pin changed: the toggle,
banner and link testids all predate this ADR and are unchanged.

Numbering note: 0188 was taken by the craft-trait delivery built in
parallel (each craft trait is paid once); this delivery follows it so
the sequence stays consecutive.
