# 0206 — The cover ask is 3 to 5 words, and the caps sit just past it

Status: accepted

## Context

Covers still came out too long. The shared `_cover_text_rules_block`
asked for "under eight" words, while the hard caps behind it allowed
more — `COVER_TEXT_MAX_WORDS = 10` and `COVER_TEXT_MAX_CHARS = 100` —
and the headroom swallowed the ask: a cover could run to ten words
without ever meeting a correction. On the Nov 18 2026 call Kasra
ruled on the size from the cover's job: it sits on screen for the
opening's first two seconds, which is all a viewer can read at a
glance, so the optimized cover is 3 to 5 words — eye catching,
punchy and enticing, the moment up front and the answer withheld.
An 8-word cap was proposed mid-call and he explicitly rejected it
as too long. His example in the new size, from that night's
orchard-gate pair: "Orchard gate, shoulders drop".

## Decision

1. **The ask is 3 to 5 words.** The shared rules block now opens:
   SHORT and punchy — 3 to 5 words, all a viewer can read inside the
   first two seconds, every word earning its place — and carries
   Kasra's words for what the short cover must still be: eye
   catching, punchy and enticing, curiosity up front, making the
   viewer want the answer the video is holding back. The shape rules
   stand unchanged: first person, never a label or a title, the
   moment and the place up front with one concrete felt detail, it
   works with the opening image, the resolution withheld, never a
   copy of the spoken hook.
2. **The caps now equal the ask's edge.** `COVER_TEXT_MAX_WORDS`
   drops 10 → 6 and `COVER_TEXT_MAX_CHARS` 100 → 35: ceilings, not
   targets, sitting just past the ask so a cover at the top of the
   ask always fits. The character ceiling is Kasra's final sizing —
   a cover should be 30 to 35 characters — which superseded an
   interim 50 before this shipped. `generate_cover_text`'s existing
   bounded correction flow is unchanged and now corrects against
   the tighter caps, refusing by name a cover that stays long.
3. **Every cover path tightens at once.** All three cover-drafting
   paths read the shared block or the caps: the plan's first draft
   (`generate_creative_plan`), the Suggest-a-new-cover flow
   (`generate_cover_text`), and the post kit. The two inline copies
   of the length ask are aligned to the same words: the post kit
   prompt's "under 8 words" and the plan schema line's "a few words"
   both read "3 to 5 words" now.

## Consequences

ADR 0145's cover doctrine otherwise stands — the cover is a second
angle on the hook's moment, scored with the hook, shipped verbatim
by the post kit once accepted. Existing fixtures already sit inside
the new sizing ("Bakery queue, words won't come" — five words,
thirty characters) and needed no change; covers drafted before this
ruling are not rewritten, they are simply joined by shorter ones
from the next draft on.
