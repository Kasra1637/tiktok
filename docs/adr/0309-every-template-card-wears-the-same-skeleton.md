# ADR 0309: Every template card wears the same skeleton

Status: accepted

## Context

The template recommendation cards each rendered only the blocks
their fields filled: a card whose row carried no outcome showed
no lead line, a card with no example showed no "Sounds like"
line, the WHY IT FITS block stood wherever the content above it
ended, and a long template name wrapped inside the header row
and pushed the badges around. Side by side — three cards in one
row — the same card read as three different layouts, with the
text structure differing from top to bottom. On Nov 23 2026 the
founder ordered it fixed: "find a way so the layout and the text
structure from top to bottom appear the same way", bolded or
formatted however a line is, "they should appear the same
appearance and formatting and text style."

## Decision

`RecommendationCard` renders one fixed skeleton on every card,
in one order, with one styling per slot: name, badges, outcome,
example ("Sounds like:"), shape, develops, moment ("In your
video:" — or the misfit warning in that same slot, keeping its
warning weight), and the WHY IT FITS verdict block.

- Every slot renders whether or not its field carries text. An
  empty slot holds its line blank (`min-h`) instead of
  collapsing, so a missing field never reshapes the card. The
  name reserves two lines and stands on its own line, with the
  badges on their own row beneath it, so a long name can no
  longer push the badges around; the outcome reserves two lines
  as the lead.
- A slot's `data-testid` rides only when the slot carries text,
  so the checks keep reading "the line that says it" exactly as
  before; every slot also carries a constant `data-slot` name,
  and a smoke check pins the full slot sequence on every card.
- The card is a full-height flex column and the verdict block
  anchors to its foot (`mt-auto`), so every card in the row
  stands at the row's height and the WHY IT FITS lines up
  across the row. The "More on this fit" disclosure still
  follows the verdict, on demand as before.
- No text is cut to fit. Following the house equal-height
  pattern (profileUi: no fixed heights, no line-clamp, content
  top-aligned and the row grows together), a longer line simply
  takes its lines; only the reserved minimums and the anchored
  verdict are fixed. Pixel-identical middles would require
  truncating words, which this app never does to generated text.
- This deliberately reverses the older card rule that a card
  with no reasons shows no WHY IT FITS block at all ("an empty
  heading is worse than no heading"): under the fixed skeleton
  the block stands on every card, empty when there is nothing
  to say, and the smoke check that pinned the old rule now pins
  this one.

## Consequences

The three cards in a row now read as one layout three times:
same header, same lead, same labelled lines in the same order,
same verdict at the same foot. A card whose row lacks an
outcome or an example shows the slot empty rather than a
different card — the absence is visible as space, in the same
place on every card, instead of a reshaped stack.
