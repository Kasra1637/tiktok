# ADR 0160: Renders per week reads as week rows; the expanded ledger stays bounded

Status: accepted

Supersedes ADR 0159's decision A3 only. ADR 0159's A1 (the Analytics
top pair stands at one height) and A2 (the Clip results table fits
its card), and the whole History half of 0159, stand unchanged.
Nothing here changes data, endpoints, or what the verdict loop
learns — this record governs presentation only.

## Context

Kasra, on Nov 15 2026, saw the ADR 0159 Renders per week chart live
and rejected the bar design outright: the four vertical bars with a
digit on top "look ugly and unclear". He ordered a brand-new way for
the section to be understood better and more easily. In the same
review he screenshotted a second imbalance the 0159 stretch created:
expanding Clip results ("Show all 17") grows that card to the full
ledger while the Renders card beside it stretches into a mostly
empty tall card — "when you expand this card and container it
becomes unequal in height with section next to it."

## Decision

### 1 — Renders per week is one row per week, one dot per render

The bars, their tracks, and the floating count chips are removed
entirely. Each week (the existing Monday-start buckets, newest
first, unchanged) becomes one horizontal row in the app's ledger
style, rows divided by hairlines:

- LEFT: the week label ("This week", "Week of Nov 2", ...) at a
  fixed width, never truncated away.
- MIDDLE: one filled dot per render — small circles in the brand
  accent in a wrapping flex row — so each video is a countable
  object the eye can tally.
- RIGHT: the count as words ("7 renders", "1 render",
  "0 renders"); the busiest week's count carries the foreground
  emphasis the retired max chip had, the rest stay muted. A zero
  week shows no dots and "0 renders", and the row still stands.

The static subtitle "Loaded render counts by week, newest first."
is replaced by one plain-language sentence computed from the data,
naming the busiest week and its count:

- This week busiest: "You made 7 renders this week — the busiest of
  the last four weeks." (the span word follows the number of weeks
  shown; with a single week shown the superlative clause drops).
- An older week busiest: "Busiest week: week of Oct 26, with 5
  renders."
- Singular and plural are handled ("1 render"). A tie names the
  most recent of the tied weeks — buckets arrive newest first, so
  the first bucket at the maximum wins. With nothing counted, the
  sentence falls back to "No renders in the weeks shown yet."
  rather than crowning an empty week.

The card, its "RENDERS PER WEEK" eyebrow title, and its footer note
("Same N renders as above, in the N weeks shown.") are unchanged.
The dots are aria-hidden decoration: each row's label and written
count carry the full fact ("This week: 7 renders") to assistive
tech, so the count never lives in the dots alone.

### 2 — Expanding Clip results bounds its table region

The collapsed state is exactly as ADR 0159 left it (the first three
rows behind "Show all N"). In the EXPANDED state the clips table
region carries `.clips-table-scroll` (index.css): a max-height with
internal vertical scrolling, so the card's total height stays at
its collapsed height and the pair keeps one height in both states.
"Show less" stays outside and under the scroll region, never
scrolled away. The Renders card is untouched, and the ADR 0159 A1
stretch stands — this decision bounds what expansion does to the
pair, it does not revisit the stretch.

The bound is anchored to the collapsed layout's own proportions,
not picked as a round pixel guess: the header row (2rem) plus the
collapsed page of three rows at the tall-row rhythm (6rem each — a
three-line clip name, its sub-line, and the row's padding) sums to
20rem. The trade-off, stated plainly: a CSS bound cannot measure
the collapsed render, so rows shorter than the rhythm leave the
region a touch under-filled and longer ones scroll a touch sooner.
The card's height — the thing Kasra objected to losing — holds
either way.

## Pins

The render smoke suite replaces the two bar pins with the new
reading model: each week row renders exactly as many dots as its
render count (7/2/5/3 and 2/1 fixtures), the count phrase matches in
words (singular included), the summary sentence names the busiest
week and count, and no bar or track markup remains in the card. A
sibling of the ADR 0159 one-height pin asserts the expansion rule:
the collapsed region carries no bounded-scroll treatment, the
expanded region does, all rows render inside it, and Show less
sits outside it while the pair grid keeps `items-stretch`.

## Consequences

- Renders per week reads at a glance: weeks compare by counting
  dots and reading words, not by judging column heights against a
  floating digit.
- The Analytics pair now holds one height in both of the Clip
  results states, collapsed and expanded; the imbalance Kasra
  screenshotted cannot recur through expansion.
- ADR 0159's A3 (proportional week bars) is retired after one day:
  honest proportions were necessary but not sufficient — the form
  itself was the unclear part.
