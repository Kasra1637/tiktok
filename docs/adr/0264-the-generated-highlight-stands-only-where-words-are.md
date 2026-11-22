# 0264 — The generated highlight stands only where words are

Status: accepted

## Context

ADR 0258 dressed every generated line in one indigo wash. The
dress was sewn onto the furniture: the field form
(`.generated-highlight-field`) wrapped the hook, script and demo
brief fields unconditionally, so an unwritten field stood as an
empty full-width indigo bar. On Nov 22 2026 Kasra screenshotted
the Hook + CTA page's Hook line card before anything was
generated — the empty bar standing under the label — and ruled:
the highlight shows only when the output is generated, "throughout
the pages and sections that does it generation in a same way,"
and "the width of that should match the text width itself." The
same day he added the entrance: the highlight appears half a
second after the text lands, animating in gently as it merges
with the words.

## Decision

1. **Existence — no text, no wash.** The field seats are worn
   only while their field holds words. `HookLineEditor` (the
   Review hook line and the Hook + CTA hook line — one shared
   component) and Create Video's script and demo brief fields
   render their `.generated-highlight-field` wrapper only when
   the value is non-blank; an empty field is a plain field with
   its ordinary chrome. Placeholder prose is not generated
   text: the demo brief's hint text never earned a wash, and
   Review's cover placeholder span (CoverTextEditor) stays
   unwashed as it already was. The read-only surfaces — the
   cover value and its suggestion, the clearer-line and Remake
   suggestion text, the post kit's caption and cover, History's
   legacy kit caption and screen text and its Plan-context demo
   brief, the landing ScriptMockup — already rendered their
   highlight spans only alongside the words themselves, so
   their existence was already right and stands unchanged.

2. **Width — the wash hugs the words.** `.generated-highlight`
   gains `width: fit-content` (with `max-width: 100%`), so even
   where a parent block-ifies the span — a flex row, a grid
   cell — nothing can stretch the wash past the text it backs;
   for wrapping text the clone-decoration line fragments already
   hug each line. The hook field, a single line, shrink-wraps
   for real: its wrapper takes `fit-content` while washed and
   the input inside is sized in `ch` to its text, so the wash
   ends where the words do. The wrapping textareas (script,
   demo brief) deliberately keep the column: their text block's
   natural width is the field's own width, and a shrink-wrapped
   flex seat would collapse a `w-full` textarea to its
   intrinsic ~20ch measure — the hug there is the unchanged
   fit of the auto-grown field around its words.

3. **Entrance — half a second late, merging in.** A new
   `@keyframes generated-wash-in` animates `background-color`
   alone, from transparent to the wash token, over 450ms on
   ADR 0165's signature ease, with a 0.5s delay and backwards
   fill: the words stand readable from the first frame and only
   the wash fades in behind them. The animation is declared for
   both highlight classes only inside
   `@media (prefers-reduced-motion: no-preference)` — under
   reduced motion no animation property exists at all, so there
   is no delay and no motion and the wash is simply present
   with the text. The read-only arrival spans (cover value,
   cover suggestion, rewrite suggestion, post-kit caption and
   cover) are keyed by their text, so a regenerated or replaced
   value remounts the span and the entrance replays. On the
   editable fields the entrance plays when the seat appears
   (empty → filled); a filled field's in-place replacement
   keeps the wash it already wears — remounting an editor to
   replay an animation would drop the caret and focus on every
   keystroke, so the seat, not the keystroke, owns the
   entrance. It remains an entrance, not a state change: a
   filled field's wash is still identical at rest, hover and
   focus (ADR 0191's rule, carried by 0258).

4. **Untouched.** The wash itself: the `--generated-highlight`
   token and its measured contrast pairs (foreground 13.42:1,
   muted 5.68:1 on the wash) are unchanged — the animation's
   end state is the same color the gate measures. ADR 0258's
   scoping stands: the suggestion panels' `inset-panel`, the
   demo brief's field-group panel, the hashtag FactChips and
   the record surfaces stay exactly as they were.

## Checks

Four render-smoke checks, the existence and CSS halves red
before green (the empty-field checks failed on the old code
with the wash standing on empty fields — Kasra's screenshot):

- "an unwritten hook wears no highlight" — on a fresh Hook +
  CTA page the hook field is plain and no `.generated-highlight`
  stands anywhere on the page.
- "a written hook, opened from the drafts list, wears the
  highlight" — the filled half, opened the way the founder
  opens a draft (ADR 0262).
- "an unwritten demo brief wears no highlight in Review" — the
  wizard's own empty field, placeholder and all, stands plain;
  ADR 0258's Review check still pins the filled hook, script
  and brief wearing the seat.
- "the generated wash hugs its words and merges in half a
  second after them" — the CSS contract: `fit-content` on
  `.generated-highlight`, the wash-in keyframes defined, the
  gated rule carrying the 450ms / 0.5s / backwards animation
  for both classes, and no wash-in animation anywhere outside
  the reduced-motion gate.
