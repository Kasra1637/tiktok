# ADR 0277: A learning badge over the hero headline, and the headline eases down two points

Status: accepted

## Context

On Nov 22 2026 Kasra ordered a badge label above the hero headline
stating that the app learns from your input, styled like the
all-caps eyebrow labels that stand over the page's section titles,
and asked Flash to write the short copy for it. In the same order
he asked for the hero headline's size to come down slightly — by
two points. ADR 0261 had removed the ADR 0260 proof pill from this
seat and pinned the headline standing alone; that ruling barred
re-adding a proof pill over the headline unless Kasra asked again.
He has now asked again — for a plain statement label, not the
proof pill.

## Decision

An EyebrowPill — the same component the section headings wear —
stands as the first element of the hero column, above the
headline, carrying the line "Learns from your input" (rendered in
the eyebrow's all-caps style). It carries no counts, no live data,
and no proof copy; GET /api/landing-proof stays unused by the
page. The headline's size tokens ease down two points: text-hero
48px → 46px on mobile, sm:text-hero-wide 60px → 58px from sm up.
The classes do not move; only the token values in
tailwind.config.js do, and design_guidelines.md's named exception
moves with them. The render-smoke check that pinned the headline
standing alone is rewritten in the same commit: it now pins the
badge's seat and exact words while keeping the proof pill's
absence asserted, and the hero check's token comment records the
new values.

## Consequences

The hero opens with the learning claim, then the headline a touch
smaller than ADR 0263 set it. The proof pill stays gone, and the
distinction is pinned: a statement label Kasra ordered is welcome
in this seat; a live-proof pill is not, unless he asks for one
again.
