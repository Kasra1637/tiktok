# 0258 — Generated text wears a highlight, not a box

Status: accepted

Supersedes the frame treatment of ADR 0186 and the frame half of
ADR 0191. Those records' other rules — no quotation marks on the
spoken lines, nothing about the treatment changes on click, the
fields themselves untouched — stand and now govern the highlight
family.

## Context

Kasra's ruling (Nov 21 2026): generated text outputs — the hook line,
the script, the cover text, what the demo should show, the post-kit /
post-copy text, and any other AI-generated text output — must STOP
living inside clickable-looking boxes, containers or cards. Instead
each output reads as plain written text with ONE highlight treatment
over it: a very light, sleek, non-distracting highlight in the brand
indigo family, unified — the same treatment on every page and section
wherever generated text appears.

The surfaces had drifted into two camps. Since ADR 0186 the Review
hook, script and demo brief fields stood inside the History cover's
sunken frame (`.post-kit-cover` worn as `.spoken-line-frame`): a dark
box with a hairline border and an inset shadow — exactly the
clickable-looking box the ruling retires. ADR 0191 took the frame's
quote glyphs and click border off but kept the box. The post kit's
cover text and the legacy story kit's screen text wore the same box.
Meanwhile the kit's caption, Review's cover text and History's demo
brief stood plain with no treatment at all, so the app's generated
words were split between a box and nothing.

## Decision

1. **One shared treatment, implemented once in `index.css`.**
   `.generated-highlight` is the inline form for standing text;
   `.generated-highlight-field` is the block form an editable line
   stands in. Both are backed by a single token,
   `--generated-highlight` (238 28% 17%). The treatment is only a
   wash: no border, no shadow, no radius beyond a soft corner, and
   nothing about it changes at rest, hover, focus or click — the
   caret remains the only sign of editing inside a highlighted field
   (ADR 0191's rule, carried over). The inline form's background
   clones across wrapped lines, so a long value highlights as one
   unbroken run.

2. **Surfaces moved onto it.** The Review hook field
   (`HookLineEditor`, shared with the Hook + CTA page's hook), the
   Review script field and demo brief field (`CreateVideo`), Review's
   cover text value and cover suggestion (`CoverTextEditor`), the
   clearer-line and remake suggestions (`LineRewriteAction`, whose
   quoted preview also drops its quote glyphs as it joins the
   family), the post kit's caption and cover text (`PostKitSection` —
   so History, the render panel and the Demo + CTA studio inherit
   it), the legacy story kit's caption and screen text, and History
   Plan context's demo brief (`GenerationHistory`).

3. **Behavior is untouched.** Same fields, same ids, same editors,
   same live counts, same suggest/accept flows (ADR 0145 cover
   editing, ADR 0205's Remake the script, Suggest a clearer hook).
   Section cards, page structure, the post-kit panel, History's
   unified card layout (ADR 0253) and every control stay exactly as
   they are; only the inner presentation of the generated text
   changed. The demo brief's field group keeps its inset panel — the
   panel holds the group's label and note; the box that retired is
   the sunken frame that wrapped the words themselves.

4. **The contrast gate measures the wash.** `--generated-highlight`
   is a solid token — the indigo tint pre-composited over the card
   surface — and `check-contrast.cjs` gains the two pairs text rides
   on it with: foreground 13.42:1, muted-foreground 5.68:1, both
   clear of AA.

5. **Checks rewritten, red before green.** The ADR 0186/0191 smoke
   check now pins the highlight on the Review lines and the retired
   frame's absence from DOM and CSS; the ADR 0191 History check pins
   the highlighted cover. Both failed on the old tree for exactly
   those reasons before the change.

## Left alone, deliberately

- **Hashtag chips.** Hashtags ride `FactChip`, the app's shared fact
  chrome (models, lengths, dates) across the Asset Library, Analytics
  and History. Chips are chrome, not reading copy, and most of their
  content is not generated text; forking the kit's hashtags off the
  fact treatment would split one element into two.
- **Suggestion panels.** A suggestion's `inset-panel` holds its
  Accept / Keep buttons — it is a decision surface, not the words'
  display box. The suggested words inside it wear the highlight.
- **Spec sheets and records.** Plan context's audience and location
  rows, the picked-angle details, `HookContinuityPanel`'s rows, the
  shot timeline and the App Profile's saved statement record are
  labelled facts or founder-picked values, not prose outputs. The
  hook used as a record's title (History, Analytics, Dashboard) is a
  name, not an output display. Angle and template cards are
  selection controls — clickable by design.
- **Founder-typed text.** The Demo + CTA overlay fields are inputs
  the founder writes in; they keep the field treatment.
- **The post kit's text-to-speech note.** Instruction prose that
  quotes the silent render's line at posting time; the line itself
  wears the highlight at its own home in the editor.

## Alternatives rejected

- **A translucent tint (`var(--indigo-*)`) as the wash.** The
  contrast gate measures solid tokens; a translucent wash's
  effective color depends on the surface beneath it, so no single
  measurement could hold the text on it to AA everywhere it lands.
  The solid token is the same tint, pre-composited once.
- **A React wrapper component.** The treatment is pure presentation
  over unlike elements — field wrappers, spans, definition values.
  One CSS class pair is the single implementation every surface can
  wear without restructuring, the same way `.post-kit-cover` was
  shared before.
- **Restyling only the framed surfaces.** Leaving the caption,
  Review cover and History brief plain would keep the split the
  ruling names: one treatment, everywhere generated text appears,
  or the unification is not real.

## Anchors

`frontend/src/index.css` (`.generated-highlight`,
`.generated-highlight-field`, `--generated-highlight`),
`frontend/scripts/check-contrast.cjs` (the two new pairs),
`frontend/src/components/studio/HookLineEditor.jsx`,
`frontend/src/pages/CreateVideo.jsx`,
`frontend/src/components/studio/CoverTextEditor.jsx`,
`frontend/src/components/studio/LineRewriteAction.jsx`,
`frontend/src/components/PostKitSection.jsx`,
`frontend/src/pages/GenerationHistory.jsx`,
`frontend/scripts/check-render-smoke.cjs` (the two rewritten checks).
