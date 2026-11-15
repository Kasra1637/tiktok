# ADR 0159: The Analytics and History polish bundle

Status: accepted

Follows ADRs 0143/0149/0150/0151/0153 (the History card's balance
rules) and the 2026-11-14 audit's Analytics findings; refines them
where noted. Nothing here changes data, endpoints, or what the
verdict loop learns — this record governs presentation only.

## Context

Kasra, on Nov 15 2026, reviewed his History card and Analytics page
from screenshots and a voice call, rated them (History 8.5/10,
Analytics 7.5/10 as SaaS UI), and ordered one bundled polish pass —
explicitly all of it in ONE push ("No, I want them all bundled in
one push"), then "go":

- The Analytics top pair — Clip results and Renders — stands at
  unequal heights, Renders ending far above Clip results over dead
  space, the same imbalance the History cards had before ADR 0150.
- The Clip results table does not fit its own card: a sideways
  scrollbar shows and the right edge clips.
- Renders per week looks unpolished: the week bars barely differ
  against very different counts, and each bar sits in a bordered
  well whose outline doubles the bar's own edge.
- A long History is a long scroll of full cards, with no way to
  scan it.
- On the History card, the Post copy and Plan context field labels
  sit to the LEFT of their values; he wants each label ABOVE its
  value, for every labeled field in both sections.
- The Plan context box carries a listen (speaker) control at its
  top right that he wants gone.
- The Post copy card carries the line "Written for this clip when
  it finished, from its approved hook." — he left shrink-or-remove
  to Flash, confirmed the exact spot inside the Post copy card and
  its container, and the line is removed.

## Decision

### Analytics

**A1 — the top pair stands at one height.** The pair's grid
stretches its cards (`items-stretch` in place of `items-start`),
the History rule from ADR 0149: equal height with no filler
spacing — content keeps its natural rhythm and any leftover
collects at the card's foot. Below the desktop breakpoint the pair
stacks and each card takes its natural height. The Renders card
fills its height with real content: a status group now shows up to
twenty of its renders before the "+N more in History" pointer
(`STATUS_LIST_LIMIT` 6 → 20), so at the founder's current scale
the open group simply shows its renders.

**A2 — the Clip results table fits its card.** The table is
fixed-layout (`table-fixed`) under a seven-column template whose
shares follow the reading order — Rank 7%, Clip 24%, Posted 12%,
Views 19%, Craft score 10%, Your verdict 15%, Next take 13% — and
its container no longer scrolls sideways. Cells wrap instead of
forcing width: the hook text wraps in its column (never truncated),
the views bar narrows and stacks above its count, and no column is
dropped. At desktop widths every column is visible inside the
card.

**A3 — Renders per week is one clean bar per week.** The bordered
well is gone; each bar is a single accent column in a borderless
recessed track, its height the count's honest share of the busiest
week shown — pure proportion, no floor rounding a quiet week up —
with a 3px minimum so a lone render still shows. The count chip
above and the week label below keep their hierarchy, and the
"Same N renders as above" note stays.

### History

**H1 — a compact scan view beside the full cards.** A Full cards /
Compact toggle in the History filters switches the list's
presentation; full cards stay the default, and the choice is
remembered across visits through the guarded localStorage helper
the app already uses for preferences (`lib/historyView.js`). In
the compact view each render is a slim scan row (`HistoryScanRow`):
the hook line, status, date and results line, and — for a finished
render — the whole-video verdict, in the row. The verdict is never
behind the expansion: it is the app's steering signal (ADR 0124),
and a scanning mode that buried it would bury the loop. Opening a
row mounts the full card under its face with every control the
card owns (the scan row forwards the card's props, so the two
views cannot disagree); collapsing unmounts it, so a page of scan
rows stays light. Both views carry the same information — compact
is a scanning mode, not a data cut — and filters, sections, search
and the pager are untouched.

**H2 — labels above values in Post copy and Plan context.** The
two sections' rows carry a stacked variant of the shared spec-sheet
row (`.post-kit-row-stacked`): single-column at every width, each
label — Caption, Hashtags, Cover text; Audience, Location, Your
demo brief — on its own line above its value. The variant is
scoped to these two sections wherever they render (the full card
and the compact view's expanded card alike); the shared
two-column row stays for the denser spec sheets that were not
part of this order (the picked angle details).

**H3 — no listen control inside Plan context.** The speaker
control at the context box's top right, and its wrapper, are
removed. The removal is scoped to that one control: read-aloud
stays on the create page, and the Analytics Clip results card
keeps its Listen button.

**H4 — the written-for line is removed, with its element.**
PostKitSection no longer renders "Written for this clip when it
finished, from its approved hook." — the `<p>` itself is deleted,
so no empty shell or orphan spacing remains. PostKitSection is
the shared post-copy component, so the line goes everywhere the
kit renders, not only in History's card; the kit's caption,
hashtags, cover text and actions are unchanged.

## Pins

The render smoke suite pins each change: the pair's stretch rule
and the funnel showing a seventeen-render group in full; the
table's fixed layout, seven-column template and absent sideways
scroller; the week bars' exact proportional heights (7/2/5/3 →
100/29/71/43) and borderless tracks; the stacked class on every
labelled row of both History sections plus the stylesheet rule
that keeps it single-column; the absence of any listen control
inside Plan context; the written-for line's absence from the
rendered card and the component source; and the compact toggle —
scan rows carrying hook, status and verdict with no video mounted,
expansion bringing the full card, and the choice persisted.

## Consequences

- Analytics reads as one composed page at desktop widths: two
  cards at one height, a table that fits, a chart whose bars mean
  their counts.
- History can be scanned at fifty rows a page without losing the
  one action that steers the app, and read in full one tap later.
- The two History sections scan top-down, matching how the rest
  of the record already reads.
