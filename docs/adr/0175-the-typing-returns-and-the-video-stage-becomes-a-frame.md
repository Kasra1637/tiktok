# ADR 0175: The typing returns, and the video stage becomes a frame

Status: accepted

Refines ADR 0168 (the two-page hero) and ADR 0173 (the mockup
mirrors the real UI); supersedes ADR 0172's removal of the typed
store-link field. Kasra's orders, Nov 16 2026, from screenshots
of the shipped hero: page one read empty — "typing wont show,
fix it" — and the finished-video stage was parts scattered in
dead space. In the same breath he ordered the polish pass that
follows the fixes: "do it then push all."

## Context

ADR 0172 removed page one's typed field on the strength of
Kasra's "remove yourapp.com/store above the phone mockup". Seen
live, the removal's cost was plain: page one opened on a lone
button in an empty screen — his first screenshot shows the
Research button marooned at the bottom of a dark phone. His
"above the phone" order had targeted the floating drop-in
label (retired under ADR 0168, still gone); the in-phone
typing is his own designed step from ADR 0168, the gesture
that makes page one a story instead of a button. The second
screenshot showed the finished-video stage the same way: hook
lines at the top, a large empty middle, the play badge floating
alone, the presenter a small line glyph in the bottom-right
corner, the progress bar part-filled.

## Decision

- **The typing is restored on page one, exactly as ADR 0168
  built it.** The field returns — Link2 icon, the full
  "yourapp.com/store" text always in the DOM, clipped by the
  stepped width track (`hs-typing`, `steps(17)`) so the link
  types in character by character, the caret riding its right
  edge and blinking while page one stands. The field wears the
  app's real input styling: the Input skin's rounded-xl and
  hairline border over the input-well's inset surface. The
  figure's aria-label describes the typing again. ADR 0172's
  absence pins flip to presence pins — field, typed text,
  caret, the stepped track, and a clock-order assertion that
  typing completes before the research button wakes.
- **The timeline refits inside the same 13s loop.** Page one
  lengthens to hold the typing: the field lands at 5%, the link
  types 4%→18% (0.5s→2.3s), the caret blinks to 33%, page one
  exits at 36%. Everything downstream shifts by the same ~3
  points and keeps its relative order and durations: page two
  40%→69%, the steps checking off 50%→62%, Generate clicked at
  69%, the video taking the screen at 80%, the end card
  resolving at 96% and the frame holding to 97% before the
  loop turns. The 13s total does not change.
- **The video stage is recomposed into a frame.** One stage
  surface (`.hero-story-stage`) now wraps the presenter and the
  hook: an indigo radial wash pooled behind the presenter over
  a deeper card surface, a hairline rim, rounded corners. The
  hook lines sit at the stage's head as the video's caption
  block; the presenter is centered under them at subject size
  (150px, was a 96px corner glyph); the play badge seats on
  the presenter inside the stage instead of floating at the
  screen's middle; the progress bar fills across the stage's
  whole run (81%→95% of the clock). The end card keeps its ADR
  0172/0173 treatments and lands below the stage as the loop's
  closing moment. Reduced motion still rests on this assembled
  frame — the stage's base styles are its composed state.

## The 9/10 pass (same delivery, Kasra's addition)

- **The presenter becomes a person in a scene.** The line glyph
  is replaced by a filled, shaded SVG figure in the brand
  indigos: hair in the dark brand indigo framing a tinted face
  (features in deep indigo), a brand-indigo top, the phone she
  holds at her side with its play mark — recognizably the same
  character (head, shoulders, held phone), now present instead
  of outlined. Behind her, a small abstract scene: a window
  with a soft moon, drifting shapes, a desk edge — brand
  palette only.
- **The phone gains depth.** Its shadow takes real weight
  (a deep 30px drop over a tighter contact shadow) and a faint
  indigo glow spills onto the page behind it; a glass
  reflection — a diagonal sheen at 8% white, gone by the
  screen's middle — lies over the screen. All CSS, no layout
  change.
- **The beats move instead of cutting.** Page one exits sliding
  left, page two enters from the right and exits left, the
  video frame scales up from 0.97 as it takes the screen, and
  each step's check draws itself in on a dash track
  (`hs-check-1..4`) just after its row lands. Still one CSS
  clock, no JS timers; the dash lives only in the keyframes,
  so reduced motion's standing frame shows every check fully
  drawn.
- **The typing moment tells the truth.** While the link types,
  the field is lit with the app's real focus treatment — the
  input-well's focus border (`--indigo-35`) and ring
  (`0 0 0 3px var(--indigo-15)`) — and the Research button
  rests visible but dimmed (opacity 0.45 on its track from 8%)
  under its unchanged ADR 0173 secondary treatment; when the
  typing completes it wakes to full presence (24%) right
  before its click (27%). It is never hidden during typing —
  Kasra's sooner/longer rule stands — it is simply quiet until
  its moment.

## Consequences

Page one is a story again — a customer typing their way in —
and the finished video reads as a video: a person, her words,
a frame. The contracts around the change stand: ADR 0173's
mirror (Research's Sparkles and secondary surface, Generate's
Play and accent bevel, the rail's filled check badges), ADR
0172's sooner/longer button philosophy, `.hero-shot` hidden
below 1024px (ADR 0158), no JS timer, and the headline,
sub-headline, CTAs, checkmark lines and How-it-works strip
untouched. The pins grew teeth for each piece — the stepped
typing track, the wake-after-typing order, the focus tokens in
the field's rule, the stage's wash, the presenter's subject
size and filled shapes, the phone's glow, the check dash
tracks — so a drift back to an empty page one or a scattered
stage fails the gate.
