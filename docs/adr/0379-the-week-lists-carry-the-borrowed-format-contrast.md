# ADR 0379: The week lists carry the borrowed-format contrast

## Status

Accepted, Nov 26 2026 — Kasra's order: the landing
says everywhere that HookForge builds from the
founder's own product; the one thing it never said
is the contrast — the old way pushes a founder
toward borrowing what worked for other brands.
The contrast lands in exactly one place: the "Your
week, with the blank page removed" section's two
lists in `frontend/src/pages/Landing.jsx`.

## Context

The hero, the feature cards, the steps and the FAQ
already carry the built-from-your-facts claim, so
adding it to the hero again would repeat it. What
no section carried was the difference in method:
starting from scratch quietly pushes a founder to
hunt through other brands' winning posts and bend
their own product to fit a borrowed format.
Kasra's own correction governs the wording: not
everybody copies competitors, so the copy must
never claim that — it names the hunt the old way
pushes you into, nothing more.

## Decision

One line changes on each side of the week lists.
Four lines a side stay; there is no fifth line,
and the hero is untouched.

- "Starting from scratch" loses "Guess which hook
  might stop the scroll — and watch views stall."
  and gains "Hunt other brands' winning posts and
  bend your product to fit."
- "With HookForge" loses "Compare suggested
  openings by fit scores, reasons, limitations."
  and gains "Openings drawn from your own product,
  reasons and limitations."

The replaced pair sat in the same seat — the
opening line's seat — so the contrast reads as one
thought across the divider: borrowed format on the
left, your own product on the right.

Two standing pins shaped the final wording, and
both are recorded here rather than silently bent.
The bullets are length-pinned in pairs (ADR
0268/0269) so the two columns read as one ledger;
the pair was re-cut to a matched 62/62 and the
pin's second row updated to match. And the old
right-hand line was the landing's only carrier of
the word "limitations" — the claims check requires
it on the page, because template fit is presented
with its limitations, never as proven performance —
so the new line keeps the disclosure in the seat
that always carried it. The buyer half of the
contrast did not fit the pinned row beside it;
"your own product" carries the contrast against
the left side's borrowed posts.

## Checks

No check pinned the week lists' line text; the
section's title and card labels are unchanged, and
the full frontend gate stands green with the new
lines in place.

## Alternatives considered

A contrast line in the hero: rejected — the hero
already says the product is built from the
founder's input, and a second claim there crowds
the headline Kasra settled. A fifth line on each
side: rejected on Kasra's order — the lists stay
at four, so the contrast earns its seat by
replacing the weakest line, not by lengthening
the section.
