# ADR 0370: The Demo + CTA editor's chrome wears the one face, and its standing guidance is gone

## Status

Accepted, Nov 26 2026 — Kasra's spread order in the main
chat, applied to `demoCta/DemoCtaEditor.jsx` — the editor
shared by Create step 4, HookSnap's Demo + CTA card and
the standalone route. Chrome only: no pairs are built in
the editor, and no stage geometry changes — the overlay
system is a pure function of video time, and every change
here stands outside the stage's measured geometry.

## Decision

**Heading-face completion.** The local `SubLabel` learns
an `icon` prop: passed one, it renders through the shared
GroupLabel, so the sub-label's face is the primitive's own
rather than a second eyebrow dialect. Icons, where a
natural one exists: the style pickers (Smartphone),
Transition between clips (Repeat), Background (ImageIcon —
see the collision note below), Animation (Sparkles),
Customize (SlidersHorizontal), Accent (Palette), Hand
size & position (Hand), Mockup height (MoveVertical),
Phone screen position (Move), Video crop (Crop), the
image sequence (Images), Device frame (MonitorSmartphone),
Happy with your look? (Heart), Your looks (Bookmark). The
one iconless GroupLabel, "Text style", gains Type. The
two bold Fine-tune framing disclosure summaries take the
eyebrow face through GroupLabel itself (`as="summary"`):
a hand-built `eyebrow flex` class on a summary is exactly
what the icon-system check bans, so the face comes from
the primitive, not from a copied class string.

**The line pass.** Standing guidance out; every
operational and state line stays. Removed, named: "This
render is your base. Add footage after it in Second clip,
or put a phone over it in Real Video."; "Upload one clip
to start — footage or a finished render."; the base
StylePicker's hint ("Drag the preview to reframe. Hand
Holding picks a scene too."); "Drag to move • scroll to
zoom"; "Plays after the base, in its own style — a clip,
or your app screens as an image sequence. One export
covers both."; the image-sequence paragraph ("Each screen
sits still unless you give it a motion below…"); "On-
screen overlay only; spoken script unchanged."; "Colors
hook text and handle chip."; "Hook, story & end card
share this style."; "Drag hook text on preview to
reposition"; "Uses Opening text style; spoken script
unchanged."; "Drag Story text on preview to reposition";
"On-screen end card. Write one clear next step."; "Drag
the end card up or down on the preview to reposition";
the safe-area line ("Laid out inside TikTok's safe area —
clear of the right icon rail and bottom caption strip.");
"Save this hook & end card styling for your next video.
Video, copy & zoom not included."; "A note from your plan
— never part of the generated clip." (the plan's brief
itself — the readout — stays); the zoom-lock help line
("Seek → adjust zoom → Lock…"); "Upload one clip to style
it." in the empty frame.

Kept, by classification: every clip name and duration, the
crop consequence line with its source size (it reports
the CURRENT pick's effect and the source's real
dimensions — crop state, not guidance), the reduced-
motion readout, the story window ("Available: … Auto-
keeps clear of hook & end card." — it carries the live
window values), the loading and saved-state lines, and
the export card's hook-window readback.

**The Image collision, recorded because it bit.** The
Background glyph is lucide's `Image`, imported here as
`ImageIcon`. This module's image-sequence decode path
constructs the global — `new Image()` — and an unaliased
`Image` import shadows it module-wide: the decode threw,
the sequence never reported its duration, and this
round's own gate caught it ("the second slot takes an
image sequence" went red on the unaliased import, green
on the alias). Any future icon import into this file must
be checked against the globals the module constructs.

## Checks

Changed, named here per the house rule: the demo-cta
player source check anchored an ordering assertion on the
removed "Upload one clip to style it." line ("the upload
guidance must be below the upload button"). The line is
gone, so the ordering claim it protected is moot; the
assertion is replaced by the upload button's presence in
the frame and the line's absence. The check's other pins
(the caption row's absence, the player as a plain bar,
the transport order) are unchanged.

New in this round: the editor chrome check — the removed
set's absence, the kept set's presence, every iconed
sub-label, and the two GroupLabel summaries, pinned at
the source (much of the editor mounts only with real
media, which jsdom cannot supply; the DOM-level editor
checks stand as before).

## Alternatives considered

Exempting the Fine-tune summaries from the icon-system
check instead of routing them through GroupLabel: the
exemption would leave a second eyebrow dialect in the
one file the round was completing. `as="summary"` costs
nothing and keeps one face.
