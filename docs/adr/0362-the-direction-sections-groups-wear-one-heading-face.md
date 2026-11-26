# ADR 0362: The direction section's groups wear one heading face, and its descriptive lines are gone

## Status

Accepted, Nov 26 2026 — Kasra's order on a voice call, from his
live screenshot of ADR 0360's shipped pair. He loved the new
way Camera setup and Voice stand — the layout, the divider,
the four buttons in one line, in his words "very harmony and
beautiful" — and named the one problem: "they are not equal
like camera setup is wide title and is aligned with the voice.
which is all cap." Confirmed piece by piece on the call:
Camera setup takes Voice's face, all caps with an app-relevant
icon; Location and Wardrobe get the same — "Same all cap, same
font color, same font tone. Same icon to the left. But of
course a unique icon for each" — and stand side by side like
the first pair, the separator kept ("we should not remove
those lines", of the divider). Then the cleanup, of the long
texts under the buttons: "should we remove those texts so
there is less visual noise?" — and, asked about the section's
own subtitle line, "Yeah, remove them all."

## Context

ADR 0360 laid the Visual & audio direction section's first
two areas side by side but changed nothing inside either area,
so the pair's two headings came from two different families:
Camera setup was a plain bold span (`text-sm font-semibold`
in `frontend/src/pages/CreateVideo.jsx`), while Voice is
rendered by `VoiceModeControl` through the shared `GroupLabel`
— the uppercase `.eyebrow`, muted tone, icon at the left.
Below the pair, Location and Wardrobe stacked in a block under
a third bold face, the umbrella "Location & wardrobe" heading,
each field's label a bold span inside `DirectionSelect`.

The section also carried standing descriptive lines under
nearly every group: a subtitle under the title ("Optional
scene picks; the plan's defaults render as-is."), two lines
under the camera buttons (the framing description for the
standing pick, in a handheld and a fixed form, and "Camera
setup controls framing; the plan and the render follow the
setup saved here."), the voice note under the Voice buttons
in both modes, a subtitle under the umbrella heading ("The
place is picked here; wardrobe refines the saved look."), and
a closing sentence ("Location and wardrobe apply together in
the plan written from them. Lighting is set from this video's
scene.").

Both shared controls are shared with HookSnap's Place and
wardrobe card, which this order does not touch: `VoiceModeControl`
renders there with its note (the note is that card's own
instruction — it names the exact hook line to paste into
TikTok's text-to-speech), and `DirectionSelect` labels its
fields with the plain span.

## Decision

Three moves, all inside Create's Visual & audio direction
section:

**One heading face.** Camera setup renders through
`GroupLabel` with the `Camera` icon, matching Voice's
`GroupLabel` with `Mic` exactly — same eyebrow, same size,
color and tone, icon at the left. `DirectionSelect` gains an
optional `labelIcon` prop: passed, its label renders through
`GroupLabel` with that icon (the `id` the buttons' group is
labelled by rides along, and the "New options" action still
sits beside the label); unpassed, it renders the plain span
it always has. Create passes `MapPin` for Location and
`Shirt` for Wardrobe. The icons are the label's own object,
as Mic already was; all four were verified present in the
installed lucide-react (0.516.0, per-icon ESM files and the
package's exports). The umbrella "Location & wardrobe"
heading is gone — the two headed groups replace it.

**A second pair.** Location and Wardrobe stand side by side
as a second `.section-pair`, reusing ADR 0360's pattern
as-is — same center separator from 1024px, same stacked
hairline below it — mirroring the Camera/Voice pair above.
The block keeps its own top hairline against the first pair:
the pair owns the divider between its two areas, the hairline
between the two pairs is the section's rhythm between groups.
The conditional notes stay with the pick they belong to — the
saved-place warnings under Location, the plan default line
under Wardrobe, a refresh error below the pair. Picks, saves
and ADR 0361's no-default-pick faces are untouched.

**No descriptive lines.** Every standing descriptive line in
the section is removed: the section subtitle, both camera
lines (the framing description in both its forms and the
controls-framing line), "The place is picked here; wardrobe
refines the saved look.", and "Location and wardrobe apply
together…". The voice note is removed on Create only:
`VoiceModeControl` gains a `hideNote` prop (default off), and
Create passes it, so neither the silent text-to-speech note
nor the talking note renders there; HookSnap passes nothing
and keeps the note in both modes. What remains in the section
is the title with its Optional chip, the two pairs with their
headings, icons, buttons and separators, and the section's
conditional, state-carrying elements — the saved-place
warnings, the plan default, the refresh error and the "What
will render" preview — which render values and warnings, not
standing description, and are untouched.

This record supersedes one clause of ADR 0361 for Create:
the note no longer stands under the unpicked voice pair
there. ADR 0361's separation — the effective value untouched,
the picked face earned only by a click — stands exactly as
recorded; the note was display, and this order removes the
display.

## Alternatives considered

Lowering Voice to Camera setup's bold title face: rejected —
the eyebrow is the face every group heading in the wizard
already wears (the section's own title included), and the
shared control's face is HookSnap's as well; the bold spans
were the outliers, three of them against one.

Giving `DirectionSelect` the eyebrow unconditionally, or
deleting the voice note from the shared control: rejected —
HookSnap's card is outside this order and keeps its faces
byte-for-byte. Both changes ride opt-in props in the
established pattern (ADR 0358's `card` flag, ADR 0361's
`pickedValue`): the new face and the missing note exist only
where a caller asks for them.

Dropping the block's top hairline now that a second pair
stands there: rejected — Kasra named the separator as kept,
and the hairline between pairs is what separates two groups
of picks, distinct from the divider a pair draws between its
own areas.

Keeping the voice note because it instructs: rejected on
this page by the order itself — Kasra read the note in his
screenshot and named it among the texts to remove ("the
character stays silent in this video" was his own example).
On HookSnap, where the note names the hook line at the pick,
it stands.

## Consequences

The render-smoke suite gains a check (red before green): the
second pair stands Location then Wardrobe, all four headings
wear the eyebrow with an icon, the umbrella heading is gone,
every removed line is absent in both camera faces and both
voice modes, the scene picks still save from the pair, and
HookCta.jsx passes neither new prop. `VoiceModeControl`'s
unit test gains the `hideNote` case (that Jest suite still
cannot run in this environment — the `@/lib/utils` alias
failure ADR 0361 recorded is pre-existing and identical
without this change; Jest is not the gate of record).

Existing checks changed, each named — none weakened in what
it protects, each moved only where this order moved the app:

- ADR 0360's pair check counted one `.section-pair` and
  asserted Location stayed full width below it; it now counts
  two pairs and asserts Location stands in the second. The
  first pair's composition and the stylesheet assertions are
  unchanged.
- ADR 0361's check asserted the silent note stands on Create
  under the unpicked pair; that clause is this record's
  supersession, so the assertion now pins the note's absence
  on Create. Every value and picked-face assertion in the
  check is unchanged, and HookSnap's own checks still pin the
  note where it lives.
- "Delivery comes from the video, never from a direction
  control" and "camera setup and profile-matched direction
  pairs save and survive reload" asserted the text "Location
  & wardrobe"; both now assert the Location and Wardrobe
  eyebrow labels themselves. The second check also asserted
  "Camera setup controls framing" after a save; the line is
  removed by this order, so the assertion now pins its
  absence — the save and reload assertions around it, the
  check's actual subject, are unchanged.

The wizard subtitle-budget check is unchanged and needs no
exemption: it budgets the `data-subtitle` elements that exist
across the four wizard files and pins none of this section's,
so the section's removed subtitle ("Optional scene picks; the
plan's defaults render as-is.", 55 chars, in budget while it
stood) simply leaves the scanned set; the section's remaining
subtitle — the preview's "Saved here first; the plan and
render read these words." — still stands inside the budget.

The framing copy's removal also retires the section's last
prose distinction between the two camera framings. Nothing
functional read that copy: the camera value, its `data-value`,
the direction lists keyed on it and generation all read the
value itself, exactly as ADR 0361 recorded.
