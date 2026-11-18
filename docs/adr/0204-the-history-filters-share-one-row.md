# 0204 — The History filters share one row, and the attention action leaves the banner

Status: accepted

## Context

On the Nov 18 2026 call, the founder looked at the History header and
ruled on two placements. The five filter controls (search, the copy
dropdown, All apps, All statuses, Newest first) stood stacked in two
rows under the "Generation History" headline — the first row carried
the search and the copy dropdown, the secondary row (always visible at
desktop widths) carried the other three — and he asked for them in one
row instead of on top of each other. The "Review without copy" action,
which ADR 0189 had set inline inside the attention banner's sentence,
"should be another place"; when the far right beside the Full cards /
Compact toggle was proposed, he agreed ("Yeah") and then said "go".

## Decision

1. **One row at desktop widths.** In `GenerationHistory.jsx` the
   secondary filters wrapper (`history-secondary-filters`) moves into
   the filter row itself, in the founder's order — search, copy
   dropdown, All apps, All statuses, sort — and in `index.css` the
   wrapper renders `display: contents` at 768px and up, so its three
   controls are items of the one row rather than a stacked second row.
   Below 768px nothing changes: the More filters disclosure still
   governs the wrapper, which opens as a full-width row of its own
   under the first (flex-basis 100%, ordered last). No control is
   removed, renamed, reordered or re-behaved.
2. **The attention action leaves the banner.** The banner
   (`history-attention`) renders its sentence only. Its action — the
   same Button/Link, same `history-attention-review` testid, same label
   from `describeHistoryAttention`, same destination from
   `historyAttentionLink` — now renders in the toolbar's right cluster
   (the `ml-auto` group ADR 0189 seated at the row's far right),
   immediately before the view toggle, whenever the banner shows. The
   action is one shared element for both banner variants (kit-less
   "Review without copy" and repair "Review repair"), so both move
   together; words, count logic and link destination are exactly as
   before.

## Consequences

This supersedes ADR 0189's decision 2 (the action composed inline with
the banner's sentence). ADR 0189's decision 1 (the filters grouped
left, the toggle at the far right, nothing beside the group label)
stands, amended only in that the toggle now shares its right-side seat
with the moved action, and the secondary filters join the row at
desktop widths instead of forming the second row 0189 left in place.

The ADR 0189 smoke check is rewritten as "History filters share one
row, and the attention action sits beside the view toggle" (red before
green): it pins the five controls in the one row in order, the desktop
contents rule in `index.css`, the action in the right cluster before
the toggle with its label, the banner free of any link, and neither
banner nor action rendering for a render whose post copy is filed. The
kit-less and repair link checks, which query the action page-wide, and
the mobile disclosure check are unchanged and still pass.
