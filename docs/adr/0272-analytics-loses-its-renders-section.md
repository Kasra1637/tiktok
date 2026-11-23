# ADR 0272: Analytics loses its Renders section

Status: accepted

## Context

Kasra ordered on Nov 22 2026: remove the Renders section from the
Analytics page, and don't touch anything else. The Renders
section is the status-funnel card (`RenderFunnel` — generations
counted by status, each status openable to the renders behind it)
that stood beside Clip results in the two-across, one-height pair
(ADR 0159). It is not the weekly "Renders per week" chart
(`RenderActivity`) further down the page, which is a different
section and stays.

## Decision

**In `frontend/src/pages/Analytics.jsx`, the Renders card is
removed**: the `RenderFunnel` component, its row component
(`StatusRenderRow`) and its list limit (`STATUS_LIST_LIMIT`), the
two icon imports only it used, and the pairing grid that existed
to stand it beside Clip results. Clip results now stands alone at
full width, as the weekly chart below it always did. Clip
results, the verdict summary, the scope line, the signals and
reasons cards, and everything else on the page are untouched in
behavior.

The references move in the same commit, and only those:

- The three checks whose whole subject was the funnel (counts by
  status, a status opening its clips, empty statuses collapsing)
  are removed with it.
- The ADR 0159 one-height check is re-pinned to the new contract:
  "Analytics stands Clip results alone, with no Renders card" —
  the ledger present, the card's absence asserted so it cannot
  quietly return.
- The ledger-bound check keeps its subject (ADR 0160/0209) and
  loses only its funnel fixture assertions; the desktop-width
  source check loses its Analytics half (the two-across band it
  pinned is the arrangement that went) and stands as "Scene
  details use the desktop width".
- The analytics tour loses its funnel step ("Every clip, counted
  by status"); its target no longer exists.

Deliberately left alone: the generations fetch. It is not
orphaned — Clip results, the weekly chart, and the scope line
all read the same loaded set — so no data path changes at all.

## Consequences

Analytics is one wide ledger, a weekly chart, and the feedback
cards. The render-by-render status tally lives only in History
now, where the rows themselves are. ADR 0159's pairing rule is
superseded for this page by Kasra's removal order; the History
cards it also described are unaffected.
