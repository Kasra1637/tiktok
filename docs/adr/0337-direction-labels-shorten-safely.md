# ADR 0337: Direction labels shorten safely

## Status

Accepted, Nov 25 2026 — Kasra's rulings at the live review of
the ADR 0334–0336 round: first from his screenshot in chat,
then refined on the voice call that followed.

## Context

ADR 0332 capped a direction button's text at 25 characters so
the row would not look obnoxious, and ADR 0334 removed the
ellipsis from the trim. The trim itself survived both rounds:
it backed off to the last whole word inside the cap and still
amputated the phrase mid-thought — his screenshot shows "Calm
living room with a" and "Balcony with a simple", labels that
read cut off even with no dots. On the call he set the rule
exactly: a label may be shortened, and it stays inside the
character count he already set — but the shortened text must
still make sense, with its spelling, meaning and grammar
intact, in these buttons throughout the app.

## Decision

Two layers, one rule: a shortened label is a complete phrase
or it is not shown shortened at all.

At the source, the direction-options writer is instructed
that each option is at most 25 characters and stands complete
on its own — never ending in a, an, the, with, or a describing
word still waiting for what it describes — so fresh options
are born fitting the button.

On screen, the button's trim (the pick still stores the whole
string) cuts at a word boundary inside the 25 characters and
then drops any trailing word still waiting for the rest of
its phrase: articles, prepositions and conjunctions, and an
article + describing word whose noun was cut away. "Calm
living room with a plant beside the chair" becomes "Calm
living room"; "Balcony with a simple chair" becomes
"Balcony". No dots, ever (ADR 0334 stands).

## Consequences

The render-smoke suite pins the fixture's three places to
their safely shortened forms, and a backend test pins the
writer's instruction. A future label surface inherits the
rule: shorten only to a complete phrase, inside the count.
