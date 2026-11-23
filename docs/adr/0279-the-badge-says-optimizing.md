# ADR 0279: The hero badge says "Optimizing from your input"

Status: accepted

## Context

ADR 0277 stood a plain EyebrowPill above the hero headline
carrying "Learns from your input," in the section-eyebrow
style, with the headline eased down two points. On Nov 23
2026 Kasra asked for the badge's words to change: he wanted
the optimizing idea instead — the message that the app
auto-optimizes as the user adds input to the system — in
three or four words. He picked "Optimizing from your input"
from the options and confirmed the flow into the headline
reads well before ordering the change.

## Decision

The badge's line becomes "Optimizing from your input." Only
the words change: the EyebrowPill, its seat as the first
element of the hero column, its all-caps eyebrow styling, and
the headline's 46/58 size tokens from ADR 0277 all stand
untouched. The render-smoke pin moves to the new line in this
commit, its comment recording that the words changed once,
under this ADR. The badge still carries no counts, no live
data, and no proof copy; ADR 0261's proof-pill ban stands.

## Consequences

The hero now opens with the optimizing claim — the app
improves what it makes from what the user puts in — then the
headline. ADR 0277's record stands as the badge's origin;
this ADR supersedes only its wording.
