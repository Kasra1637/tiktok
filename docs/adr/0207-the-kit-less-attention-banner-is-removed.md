# 0207 — The kit-less attention banner is removed

Status: accepted

## Context

On Nov 18 2026 the founder ordered the History page's no-post-copy
attention removed entirely: both the banner ("N finished renders have
no post copy yet. Open its card and press Generate post copy.") and its
"Review without copy" action — the action ADR 0204 had just seated in
the toolbar's right cluster, beside the Full cards / Compact toggle.
He double-checked on a voice call ("You think is that a good idea to
remove that?") and confirmed: "Do it."

The banner's work is already done elsewhere. Every kit-less finished
render carries its own Generate post copy offer in its card (ADR 0060),
and the "With post copy & context" filter still finds those renders.
The page-level notice only repeated, above the list, what each card
already says on its own row.

## Decision

1. **Kit-less rows raise no attention.** `getHistoryAttention` in
   `frontend/src/pages/historyRepair.js` no longer returns the kitless
   kind: a completed or archived render with a durable copy and no
   post kit yields no banner and no toolbar action, however many such
   renders exist.
2. **The kit-less words and link branch go with it.**
   `describeHistoryAttention` loses its kitless branch (the "has no
   post copy yet" summary, the "Open its card and press Generate post
   copy" guidance, the "Review without copy" label), and
   `historyAttentionLink` loses its kitless branch (the forced
   without-copy side); the repair link keeps its own side rule.
   `GenerationHistory.jsx` needs no change: its banner and action are
   driven by the attention data, which is now simply absent for
   kit-less rows.
3. **Repair is untouched.** The repair banner, its three guidance
   variants (failed / awaiting provider / other), its "Review repair"
   action beside the toggle, and its link behavior render exactly as
   before; when repair and kit-less rows coexist, the repair banner
   shows, exactly as today. The per-card Generate post copy button
   (ADR 0060) and the copy filter stay.

## Consequences

This supersedes the kit-less half of the History attention system.
ADR 0204's placement now applies to the repair action alone: the
toolbar's right cluster seats "Review repair" only, and the banner
that can render is the repair banner. ADR 0204's filter-row decision
(one row at desktop widths) stands untouched.

Checks, red before green: the jest attention contract drops its
kit-less selection, words and link cases and pins kit-less-only rows
to no attention; the rescue flow's banner assertions invert (no
banner before, during or after a Generate press — the row's own
offer is the rescue); the ADR 0204 smoke check now raises its banner
with a repair row (a completed render with no durable copy) and pins
"Review repair" beside the toggle, joined by a new smoke check,
"History raises no attention for kit-less finished renders", pinning
that a kit-less-only History renders neither the banner nor the
action.
