# ADR 0304: First drafts aim inside their length on every surface

Status: accepted

## Context

The evening Sonnet 5.5 replaced Sol (ADR 0299), the founder hit
length refusals across the app — the Hook + CTA hook (ADR 0301),
the script remake (ADR 0303), and the cover text — and ruled:
the first generation should always follow the length rule; a
user should never have to regenerate just because a draft ran
long; that should never happen. The audit behind the ruling:
the two fixed surfaces were not special. Every bounded
generation loop in the app stated its length as an edge — a
ceiling, a band's two walls — with nothing to aim at inside it,
and ran two attempts; a model that counts characters loosely
lands past an edge as often as inside, and two corrections were
not always enough. The plan chain was the exception that proved
the shape: three attempts and a target band, and its first live
plan on the new model landed.

## Decision

The remaining bounded loops take the same shape. The cover
rules block — the one block every cover prompt shares — now
aims at 4 words, the middle of its 3-to-5 range, and
generate_cover_text runs three attempts. rewrite_hook_line and
rewrite_spoken_line each state an aim a breath inside their set
length (five characters under it) and run three attempts. The
plan chain is unchanged: it already runs three attempts
against its band. Everywhere, the standing doctrine holds: the
budgets do not move, the corrections still name the exact
counts, nothing over-long or unfinished is ever stored, and no
draft is ever trimmed into fitting — three misses still refuse,
honestly, with the last miss named.

## Consequences

First drafts across the app now aim at the middle of their
room instead of its walls, and a near-miss costs a small call
instead of the founder's click. The cost is one more bounded
call on the surfaces that used to stop at two, spent only when
the first two drafts miss. If a surface still fails live after
this, the evidence will name it, and it gets its own look —
the aim and the attempt count are the levers this ruling
settled, not a promise no model can ever miss three times.
