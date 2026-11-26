# ADR 0346: No content word twice

## Status

Accepted, Nov 25 2026 — Kasra's dictated rule, from his own
hook: "I'm trying to spot my drains after lunch, why do
drains hide?" (rated 6.5 — "drains" spent twice, said once).
His sharpening, in his own words: not just that word, any
vocabulary — no word should repeat twice, throughout the
generation; when the idea returns, use a synonym.

## Context

The spoken-line rules already barred filler and repeated
phrasing across generations, but nothing barred a content
word repeating inside one generation's own lines. In lines
of nine to twelve words, a repeat spends the budget twice
on one idea and adds nothing the second time.

## Decision

The shared spoken-line block carries the rule as NO WORD
TWICE: no content word appears twice in a line; when the
thought needs the idea again, the generator reaches for a
synonym or reframes the thought. Grammar words (I, my,
the, to) are exempt — they are a sentence's joints, not its
weight. The post-kit prompt carries the same sentence for
the caption and the cover text, so the rule runs throughout
the generation: hook, script, caption, cover. It is an
instruction to the generator, in the class of Kasra's other
dictated rules (ADR 0316 / 0321 / 0340 / 0344) — no hard
gate, because a sentence can legitimately turn on a word
the founder wrote by hand, and the rewrite stays the
founder's remedy there.

## Consequences

Every prompt that writes spoken lines carries the rule, and
the post kit with it. The strategy prompt's ceiling stands:
the passage was sized to fit the headroom ADR 0340 left.
Pinned by a backend test on the shared block.
