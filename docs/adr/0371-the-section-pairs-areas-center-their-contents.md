# ADR 0371: The section pair's areas center their contents, so the centered divider reads centered

## Status

Accepted, Nov 26 2026 — Kasra's order on the live Visual &
audio direction section, confirmed twice on the call:
centralize the divider, across every side-by-side section
on both pages. A CSS-only change in
`frontend/src/index.css`; every `.section-pair` consumer
is in scope by construction — Create's two direction
pairs, HookSnap's Place and wardrobe pair, and HookSnap's
Tone/Shape pair.

## Decision

ADR 0364 put the divider at the container's exact center
and proved it by the stylesheet's arithmetic. Kasra's
live review still read the line as leaning toward the
right-hand group (Voice, Wardrobe), and the read was
honest: the line was centered, but each area's contents
stood left-aligned in their half. A short left area (the
two camera buttons) left a wide empty pool between its
contents and the line, while the right area's contents
started close to the line — the whitespace around the
divider was lopsided even though the line itself was
not, and the eye reads the whitespace.

So the areas change, not the line. Inside the same
`min-width: 1024px` block, each pair area
(`.section-pair > *`) becomes a flex column with
`align-items: center`: the group heading and its control
row stand centered in their half, and the empty space
mirrors on both sides of the divider. The divider
mechanism is untouched — two equal columns, gap 0, the
second area's border-left at 50%, the symmetric 2rem
half-channel paddings — and ADR 0364's arithmetic check
passes unchanged over the new stylesheet. The areas'
insides keep their own layout: button rows stay
horizontal rows, and DirectionSelect, VoiceModeControl
and the camera thumb-pair row are consumed exactly as
they were. The stacked layout below 1024px carries none
of this.

No design token changes: the rule spends no token
values, and `design_guidelines.md` does not document
the pair pattern, so no guidelines update rides with
this change.

## Checks

New: "the section pair's areas center their contents in
their halves (ADR 0371)" — a stylesheet check in ADR
0364's shape: the desktop pair block must carry a shared
cell rule making the areas flex columns with centered
contents, and the stacked block must carry no centering.
Written red first; it failed on the unmodified
stylesheet.

Unchanged, deliberately: ADR 0364's divider check. Its
needles all sit before the new rule in the same media
block and it passes as written; what it protects — the
line at exactly 50% — is the half of this round's claim
that did not change.

## Alternatives considered

Moving the divider itself to the contents' visual
center: rejected — it would break ADR 0364's locked
rule (the line at the container's center, both halves
equal) to chase a balance that belongs to the contents.
Centering only Create's direction section: rejected —
Kasra's order names every side-by-side section, and the
pair is one shared layout, so the repair lands once in
the stylesheet rather than per page.
