# ADR 0360: Camera setup and Voice stand side by side inside the direction section

## Status

Accepted, Nov 25 2026 — Kasra's order on a voice call: in
Create's Visual & audio direction section, the visual & audio
direction content (the Camera setup area) and the Voice area
stand side by side instead of stacked, with enough space
between them, divided cleanly, visually organized and sleek —
built as a reusable pattern, because he wants it applicable
elsewhere. His constraints, in his words: "you're not touching
the main section you're just adding those subsections side by
side in the same main section that is already there", and
"you're not adding container section or any shit — you're
just placing the content side by side."

## Context

The Visual & audio direction section on Create's Audience &
template step (ADR 0220) is one `Disclosure` card
(`frontend/src/pages/CreateVideo.jsx`, testid
`visual-audio-direction`) whose areas stacked in a column:
Camera setup, Voice, Location & wardrobe, then the live
"What will render" preview. Each area after the first carried
its own top hairline. On a desktop canvas the section is wide
and the two short pick areas — a pair of camera buttons with
their framing copy, and the voice pair with its note — each
ran the full width, so the section read as a tall stack of
short controls.

The two areas this record moves are the section's first two,
identified from the code as it stands: the Camera setup block
(the `camera-setup` thumb-pair and its framing copy) and the
Voice block (`VoiceModeControl`). Location & wardrobe and the
preview keep their full-width rows below.

## Decision

A reusable layout class, `.section-pair`, lands in
`frontend/src/index.css` beside the thumb-pair rules it
neighbours. It is a chrome-less grid — no card, no border of
its own, nothing a reader would call a container — that a
section drops two of its own areas into. Stacked (below
1024px) the second area takes the section's own divider: a
hairline with the section's 0.75rem rhythm around it, exactly
the separation the stacked blocks already used. From 1024px
the two areas stand in equal columns — spelled
`repeat(2, minmax(0, 1fr))`, ADR 0153's own form for two
equal columns — with a
4rem channel between their contents, and the hairline stands
in the middle of that channel (the second area's left border
plus its 2rem left padding form the channel's far half), so
the areas read as two columns of one section, divided
cleanly, never as two cards.

Inside the section, the Camera setup block and the Voice
block become the pair's two cells, in that order. The Voice
block's own `border-t`/`pt-3` come off — the pair owns the
divider in both orientations now — and nothing else about
either area changes: same controls, same copy, same order
inside each area. The section card itself is untouched (same
Disclosure, same summary, same subtitle), Location & wardrobe
keeps its full-width row and its own top hairline below the
pair, and the preview below that is unchanged. On HookSnap
nothing moves: its direction card is a different page's
layout, outside this order.

The pattern is deliberately a class, not a component: the
codebase's other shared layouts (`.thumb-pair`, the History
record pair of ADR 0153) are classes in `index.css` that
elements adopt, and a future section lays two areas side by
side by wrapping them in `.section-pair` alone.

## Alternatives considered

A React component (a `SectionPair` beside `SectionCard`):
rejected — it would put a named container around the areas,
which is what the order rules out, and the codebase's layout
patterns live as classes the markup adopts.

Floating the two blocks at half width with Tailwind
utilities: rejected — the spacing would live as utilities in
card JSX (the token rule keeps spacing in `index.css`), the
divider would need hand-rolled responsive border utilities on
one block, and nothing reusable would remain for the next
section.

Pairing further areas (Location & wardrobe into the pair, or
a second pair): rejected — the order names two areas, and
Location & wardrobe's three-option rows need the full width.

## Consequences

The render-smoke suite gains a check (red before green): the
pair stands inside the untouched section with Camera setup
first and Voice second, Location stays outside it, and the
stylesheet carries the two-column rule and the hairline
divider. No existing check changed — no content, copy or
control inside either area moved, so every check that drives
the camera pair, the voice pair or the direction selects
drives the same elements in a new arrangement.

One conflict surfaced and is named, not worked around in
silence: the History proportion check ("History lays one
card per row and gives the record the wide share") scans the
whole stylesheet with a lazy pattern — a 900px media query,
then any `.history-row-grid` rule, then any literal
`minmax(0, 1fr) minmax(0, 1fr)` template after it — so this
pair's first spelling of its two columns, written in that
literal form, matched the scan and read as the History card
splitting into balanced columns. The check itself is
unchanged and still asserts everything it ever asserted
about the History card; the pair's columns are spelled
`repeat(2, minmax(0, 1fr))` instead — the form ADR 0153's
own paired layout already uses in this stylesheet, which
the History scan has always read past — and the stylesheet
carries a comment at the rule saying why.
