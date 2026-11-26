# ADR 0363: The direction section's title carries no Optional chip

## Status

Accepted, Nov 26 2026 — Kasra's order, given in the main
chat during the layout work and sharpened on his voice call:
"No, I don't want. I want it removed. What's the point of
having that button there?" The "Optional" chip that stood
beside the Visual & audio direction title is removed.

## Context

ADR 0362 cleaned Create's Visual & audio direction section
down to its title, its two `.section-pair`s and its
state-carrying elements, and recorded what remained as "the
title with its Optional chip, the two pairs, their headings,
buttons and separators". The chip was a `Badge` in the
Disclosure's summary, at the title's right — a standing label
saying the section's picks are optional.

Since ADR 0361 the section already says that itself: no
direction button stands picked until it is clicked, so an
untouched section visibly asks for nothing. The chip repeated
that fact in a second place, in a face no other element in
the cleaned section wears.

## Decision

The chip is removed. The Disclosure's summary is the
`GroupLabel` title alone — the fragment that wrapped the
title and the chip goes with the chip. Nothing else in the
section changes: the pairs, the headings, the buttons, the
separators and the conditional state elements stand exactly
as ADR 0362 left them, and no other section's title is
touched — this order named this section's chip.

This record supersedes the one clause of ADR 0362 that
counted the chip among what remains in the section.

## Alternatives considered

Restyling the chip to match the unified heading face:
rejected by the order itself — Kasra's question was what
the chip is for, not how it should look, and a label whose
whole content the section already shows earns no face.

Removing Optional chips app-wide: not ordered. Other
sections keep theirs until Kasra names them.

## Consequences

The render-smoke check for ADR 0362 gains the word "Optional"
in its list of texts that stand nowhere in the section
(red before green: the check failed on the chip and passes
without it), and its header comment records the removal.
The `Badge` component stays — it is used elsewhere in the
page. The wizard subtitle-budget check never counted the
chip (it scans `data-subtitle` elements) and is untouched.
