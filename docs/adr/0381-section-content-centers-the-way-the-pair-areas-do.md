# ADR 0381: Section content centers the way the pair areas do

## Status

Accepted, Nov 26 2026 — Kasra's order, sharpened
twice on the same call: make all content in any
section across HookSnap, Create, Profile, Dashboard,
Assets, History and Analytics appear the way the
content inside HookSnap's Location and Wardrobe
areas appears, buttons at the same proportion of
the screen everywhere. Placement and alignment
ONLY — no font size, icon size or text size changes
anywhere — and no new layout, no new boxes, no new
dividers: only the content that already stands in
each section is re-aligned, through the shared CSS
and the shared components.

## Context

Inside a `.section-pair` cell (ADR 0371) a content
group stands centered in its area: the cell is a
flex column with `align-items: center`, so the
group shrink-wraps to its widest row and centers,
its heading over its controls, while the divider
between the areas stands at the container's exact
center (ADR 0364). Everywhere else in the app the
same groups pooled at the left of their sections —
the difference Kasra measured in his screenshot,
where the Location pin stood ~188px in and the
card's own heading glyph stood at the 28px padding
line. The button proportion was already one
language (`.thumb-pair`: min-height 2.5rem, padding
0.5rem 1.125rem, ADR 0332/0334); what differed was
placement.

## Decision

One mechanism, in `frontend/src/index.css`, in the
same un-layered style as `.section-pair`:

- `.thumb-pair` rows center their buttons
  (`justify-content: center`). An option row standing
  in a full-width area now centers under its heading;
  inside a pair cell the row already shrink-wraps to
  its buttons, so nothing moves there. This carries
  the treatment to every option row in the app at
  once: voice, camera, tone, shape, focus, hook
  length, direction, resolution, and the History
  verdict thumbs.
- `.center-area` is the pair cell's own declaration
  carried to a section body or a control's root: a
  flex column, `align-items: center`. Its safeguards
  are part of the rule, not per-site judgment: a
  direct paragraph stretches (`align-self: stretch`)
  so running text is never force-centered; a direct
  `.section-pair` keeps `width: 100%` so its divider
  stays at the container's exact center; a direct
  form keeps `width: 100%`; and any direct child
  carrying a field (`textarea`, `input`, `select`
  among its descendants) stretches, so fields never
  narrow to content width — a form area centers as
  a block at its current width or not at all.

Inside the pair areas themselves, one more rule —
Kasra's addition on the same call, after seeing
Create's direction pairs live: a pair area's heading
and its button row start at the same place, on one
line, the same treatment in every pair on both
pages. ADR 0371's centering could not give him
that: a centered group starts wherever its own
width puts it, so the wide Camera setup and Voice
groups read at their areas' edges while the short
Location and Wardrobe groups stood indented — four
areas, four starting offsets. The pair cell rule
therefore aligns each area's contents to the area's
start (`align-items: flex-start`), superseding
0371's centering inside the pair areas only; the
divider's geometry (ADR 0364) does not move. Two
overrides carry the same line where the desktop
cell rule cannot reach: a thumb-pair row standing
at a pair area's full width (the stacked layout)
starts its buttons on the heading's line, and a
centered group standing inside a pair area
(Create's Voice group, through `VoiceModeControl`)
aligns its label and row to the same start —
outside a pair, both keep the centered treatment
this record gives the rest of the app.

The class is applied to containers that already
stand — no element was added anywhere:

- Shared controls: `VoiceModeControl`'s root (the
  voice group now centers on HookSnap and in
  Create's camera/voice pair alike; its note still
  stretches the full width) and `HookPicksControl`'s
  root (Focus, Tone and Shape groups center; each
  group's rows keep their internal order — the
  Buffet still stands beside its label, ADR 0308).
- HookSnap: the Choose an app body (the pick row
  centers; the subtitle stretches), the Place and
  wardrobe body (the pair safeguarded at full
  width), and the spoken-line area in The hook (its
  label and button row center; the editor keeps the
  area's full width under the field rule).
- Create: the Audience angle panel (`AngleSelector`'s
  inset panel — its gate action centers under its
  heading; the angle list keeps the panel's width),
  the Review plan stack (the regenerate row and the
  section labels center; paragraphs stretch; the
  hook and script editors keep the step's width),
  and the Recommended templates area (its heading
  and regenerate group center; the template grid
  keeps the step's width). The direction section's
  pairs were already the reference; its voice group
  centers through the shared control.
- Dashboard: the Recent renders tile row centers
  when the tiles do not fill it.
- Assets: the search row centers; the field keeps
  its own pill width — only its placement moves.
- History: the filter row centers; the Work with
  this render group centers in the media column
  (label over its buttons); the retry row centers;
  the verdict thumbs center under the thumb-pair
  rule.
- Analytics: the Clip results chip row (`FactList`)
  centers in its card.

## Stopped on, by name

- The render panels — Create's `GenerationPanel`
  and HookSnap's `HookRenderPanel`: working stages
  (progress narration, preview, actions at the
  edges), and GenerationPanel carries ADR 0378's
  beside layout. Their resolution rows center under
  the thumb-pair rule; their bodies stay.
- The Demo + CTA editor on both pages, including
  its Export ready card: a canvas workspace, not a
  content-group stack.
- `PostKitSection` (HookSnap's Post kit, Create's
  Review, History's detail): its header row spreads
  its label and actions to the edges like a card
  header, and centering its root would collapse
  that spread; its copy blocks are record rows.
- `PresenterPhotoControl` (HookSnap, Create): a
  headed panel whose heading row is a card header;
  its body is a face tile grid and an upload row
  standing at the panel's width.
- `AngleGoalPicker` (Create's Audience step and
  Review recovery): its header row spreads its
  label and the Shuffle action to the edges; its
  goal cards fill the area.
- Create's App Profile step: its content is two
  inset panels — a pickable-card grid and a facts
  record — already spanning the step.
- Create's Demo + CTA step: it hosts the editor
  (above).
- Profile — `BrandSetup`'s research form and
  profile cards, and `AppProfileDetail`'s form
  groups: forms. Their field blocks span their
  cards at their current widths, and centering
  inside a form would narrow fields, which this
  record's own safeguard forbids. The detail page's
  header action cluster is a page header, and
  headers stay at their edges, as card titles do.
- Dashboard's Next action hero (a routing banner —
  text at the left, its action at the right, ADR
  0208), its First video checklist (a header row
  over a three-column grid that fills the card),
  and Where to start next (a heading over a
  destination grid that fills its area; the cards
  are link rows).
- Assets' upload row (a field-and-button form row —
  the field keeps its width and the row its shape)
  and the asset groups (a record list: headings
  stand with their rows, and the rows fill the
  area).
- History's card interiors beyond the Work group
  and the retry row: the media rail and the record
  structure are settled (ADR 0149/0153), and Post
  copy and Plan context are record sections whose
  running text is not force-centered.
- Analytics' Renders per week, What happened, and
  What you liked & disliked: ledgers and a timeline.
  Rows stay rows, and there is no control group in
  them to center; Clip results' ledger entries stay
  the same way — only its chip row centers.

## Checks

New: "section content centers the way the pair
areas do (ADR 0381)" pins the mechanism the way
ADR 0364's check pins the divider — the
stylesheet declarations (thumb-pair centering, the
`.center-area` declaration, its paragraph and pair
safeguards) and, on a mounted HookSnap, the Choose
an app and Place and wardrobe bodies carrying the
class, the pair itself NOT re-centered, and the
voice group standing inside a centered area.
Changed, named here as the house rule requires:
"the section pair's areas center their contents
in their halves (ADR 0371)" is superseded by "the
section pair's areas align their contents on one
start line (ADR 0381)" — it pins the start-aligned
cell rule and the pair's two one-line overrides
instead of the centering, at the same strength;
ADR 0364's divider check stands untouched beside
it. No other standing check was weakened; the
full frontend gate and the backend suite stand
green.

## Alternatives considered

Centering through the shared `SectionCard`: rejected
— its children are not wrapped, and wrapping them
would add an element to every card, which the order
forbids; the heading row would also have to be
exempted card by card. Per-page utility edits
(`justify-center` sprinkled row by row): used only
where a single standing row was the whole group
(the History filter row, the Assets search row, the
Dashboard tiles, the History retry row); everywhere
a stack of groups needed the treatment, the one
class on the standing container carries it, so the
next section takes the same rule instead of a new
one-off.
