# ADR 0364: HookSnap's Place and wardrobe stands as a pair, and every center divider sits at its container's center

## Status

Accepted, Nov 26 2026 — Kasra's spread order in the main
chat (the ADR 0360–0363 pattern carried across both pages),
plus his live-review catch the same night: the pair's center
divider leaned toward the second area on his screen, and he
ruled the centered placement locked in throughout all
sections and all pages.

## Context

ADR 0362 unified Create's Visual & audio direction section:
two `.section-pair`s, every group heading in the one
GroupLabel eyebrow face, no standing descriptive lines. Its
record scoped the shared controls' new props to Create —
HookSnap passed neither `labelIcon` nor `hideNote`, and its
smoke check pinned exactly that. HookSnap's Place and
wardrobe card still stacked Location over Wardrobe under
plain bold labels, carried a card subtitle and an
apply-together sentence, and lit "Character stays silent" on
a fresh draft because its VoiceModeControl never received
ADR 0361's `pickedValue` read.

The divider: at desktop widths `.section-pair` laid its two
equal columns out with a 2rem column gap, and the divider
was the second area's `border-left`. The line therefore
painted at the second area's left edge — half the gap (1rem)
to the right of the container's center — with the rest of
the 4rem channel carried as one-sided `padding-left` inside
that same area. Centered between the two areas' contents;
off-center against the container, leaning toward the second
area (the Wardrobe / Voice side), exactly as Kasra's
screenshot showed.

## Decision

**The card takes the pair.** Location and Wardrobe stand
side by side in a `.section-pair` — the exact twin of
Create's second pair — each DirectionSelect passed its
`labelIcon` (MapPin, Shirt), so both headings wear the one
eyebrow face. The card subtitle and the apply-together
sentence are removed. The plan-default line moves into the
Wardrobe area, mirroring Create. The voice control receives
`pickedValue` from an `editPick` read at the HookCta call
site (Create's helper, same shape; Create itself does not
move), so a create-fresh silent project shows no voice
button picked until a click — ADR 0361 lands on this page.
The voice note STAYS in both modes, untouched: `hideNote`
is never passed here. Below 1024px the pair stacks and the
stylesheet's rhythm puts one hairline between Location and
Wardrobe where none stood before; that is the only mobile
change. The ADR 0356/0357 collapse gates read `dirSel`
values only and are untouched — this round's smoke walks
the gate end to end over the new pair to prove it.

This supersedes the `labelIcon` half of ADR 0362's scoping
clause. The `hideNote` half stands.

**The divider mechanism is corrected, and the rule is
locked in.** The pair's desktop columns now meet AT the
center: the column gap is 0, and the 4rem channel is
carried as symmetric padding — 2rem inside the first area
(`padding-right`), 2rem inside the second (`padding-left`)
— so the second area's left edge, and the hairline standing
on it, sit at exactly 50% of the container by construction,
both halves equal. The standing rule, locked in throughout
all sections and pages: **wherever a center divider splits
a container into two sides, the divider sits exactly at the
container's center with both halves equal, measured against
the container — never carried off-center by a gap or by
one-sided padding.**

**The sweep.** Every other two-side split in the app was
checked against the rule:

- `.thumb-pair` rows (the resolution pairs, the direction
  groups, the pick pills): flex button rows with a gap —
  no divider is drawn. Nothing to center.
- `.history-row-grid` (288px capped media column + record):
  unequal by Kasra's own proportion (ADR 0149), and no
  divider is drawn between the columns.
- `.history-record-sections-paired`: two equal halves, a
  gap between them, no divider drawn.
- The strategy panel's spec grid: two definition columns
  with horizontal row rules only — no vertical divider.
- The strategy suggestion modal's two columns, the
  Analytics signals/reasons split: gap only, no divider.
- `.post-kit-row` readouts and the angle spec sheet:
  stacked label-over-value rows with horizontal rules.
- FactList: a chip row. The Demo + CTA editor's main grid:
  unequal fractions by design (settings vs preview), no
  divider. Its scrubber segments are positioned by time,
  not a two-half split. The sidebar's edge line and the
  Analytics timeline rail are edges, not center dividers.
  Card grids everywhere draw no middle line.

One instance STOPPED on, not fixed: the compact History
card draws a real vertical divider (`.history-media`'s
`border-right`), but its split is a fixed 180px media rail
beside the record — not two halves — and centering that
line would restructure the compact card. History is also
outside this round's scope by Kasra's own held list. It is
recorded here for his ruling, untouched.

## Checks

Changed, named here per the house rule: ADR 0362's smoke
check pinned "HookCta.jsx passes neither `labelIcon` nor
`hideNote`" — the pin is split: `hideNote` still fails the
build if HookSnap ever passes it; `labelIcon` is now
expected, and the card's new face is pinned directly by
this round's own checks (the pair, its headings, the
unpicked voice, the note's presence, the gate walk), plus a
stylesheet check pinning the divider arithmetic (equal
columns, no column gap, symmetric half-channel padding,
the hairline on the second area). ADR 0360's own CSS pins —
the `repeat(2, minmax(0, 1fr))` spelling and the
`border-left` hairline — stand unchanged under the new
arithmetic.

## Alternatives considered

Moving the line with a negative margin or a `left: 50%`
overlay: both paint the right pixel while leaving the
mechanism — a gap and one-sided padding doing the spacing —
free to drift again at the next value change. Taking the
channel out of the gap makes the center a property of the
layout itself, not of a tuned number.
