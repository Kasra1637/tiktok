# 0209 — Clip results are stacked entries, not a table

Status: accepted

## Context

On Nov 18 2026 the founder sent his Analytics screenshot at a narrow
(~650px) width: in Clip results "some of the content are being
cramped", heights are wrong, contents are "cut off, some are
overlapping" — and he ordered it fixed across that section and the
whole page.

The causes, read from the shipped code:

1. **Cramped.** The ledger was a `table-fixed` table under ADR 0159's
   seven-column percentage template (7/24/12/19/10/15/13). The card
   is paired at half the workspace width on desktop and full width
   below it, so its columns landed near 600px or less in both shapes —
   and at those widths the template squeezed every column below its
   content: the clip title wrapped to four lines, "Not posted" wrapped
   under its dot, the craft grade "B · 76" split at its middot, the
   verdict pill wrapped inside itself ("Not / rated", growing tall),
   and "Reuse draft" wrapped to two lines. None of the short fields
   carried a no-wrap rule; the template simply starved them.
2. **Cut off.** The expanded region's bound (`.clips-table-scroll`,
   max-height 20rem) was summed by ADR 0160 from a 6rem row rhythm
   the wrapped rows no longer matched — every row ran far taller, so
   the region's edge landed mid-row after barely two rows. The same
   rule set `overflow-x: hidden`, silently clipping whatever
   overflowed horizontally instead of revealing it.
3. **Overlapping.** The Rank cell (7%, ~26px of content box at card
   widths) held a 24px number circle plus the winner crown plus gap —
   ~54px of content — so on winning rows the crown painted out of its
   cell over the clip title's area. (The dark band across the third
   row in the screenshot matches the shell's sticky mobile top bar
   passing over the scrolled page; the fragmentation beneath it is
   what made ordinary chrome read as damage.)

The rest of the page was audited section by section — PageHeader,
the fact chips, the verdict summary, the why-these-numbers details,
the next-take banner, the show-all row, the Renders funnel, Renders
per week, the signals and reasons cards: all wrap, truncate or scroll
by their own honest rules, and the expanded ledger's bound was the
page's only fixed-height clip. They are unchanged.

## Decision

1. **The table is replaced by stacked entries** in the page's own
   ledger language (the divide-y list the Renders funnel and Renders
   per week already speak). Each clip is one entry: rank circle and
   crown beside the title and its app line, then the facts as a
   wrapping row of labelled items beneath — posted state, Views with
   its bar and count, Craft with its grade, the verdict pill, the
   next-take link — and the recorded snapshot facts as a plain line
   under them. A sideways-scrolling table was considered and
   rejected: this is a ledger the founder reads top to bottom, and
   hiding columns off-screen trades the squeeze for invisibility.
2. **Short fields never wrap internally.** The posted state, the
   views count, the craft grade, the verdict pill and the next-take
   link all carry `whitespace-nowrap`; the facts row wraps only
   between whole items. The rank cluster is shrink-0, so the crown
   can never be pushed out of its place again. The clip title — the
   one long field — wraps inside its own line, as titles do.
3. **Heights are honest.** The collapsed region carries no height
   bound, so its first three entries always stand whole. Expanded,
   the region keeps ADR 0160's in-card scroll bound (renamed
   `.clips-scroll-region`, still 20rem — the pair's one-height
   behaviour was tuned against it and the shorter entries ask for no
   more) with Show less outside it. The Clip results / Renders pair
   still stands at one height on desktop (ADR 0159's pairing stands;
   only its column template is superseded). No new token, color or
   visual language: the entries reuse the hairline, the secondary
   tints and the type scale the page already had.
4. **Every existing testid survives** (`analytics-results-table` now
   names the ledger region; `result-*`, `result-rank-*`,
   `result-views-bar-*`, `result-craft-*`, `result-vote-*`,
   `result-results-*` keep their elements' meanings), so the
   comparison, leaderboard, show-all and pair pins keep their grip.

## Consequences

ADR 0159's Clip results column template (fixed layout, seven
percentage columns, "the table fits its card") is superseded; the
rest of 0159 and all of 0160's bound principle stand. Checks: the
table-era pins are rewritten to the entry selectors; the ADR 0159
fit check is replaced by one pinning the stacked shape — no table,
no sideways scroller, no-wrap on the four short fields, the crown
riding a shrink-0 rank — and the expanding check pins the renamed
scroll region and the bound-free collapsed state.
