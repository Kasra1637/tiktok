# ADR 0357: The hook waits for the place and wardrobe picks

## Status

Accepted, Nov 25 2026 — Kasra's correction at his live review
of ADR 0356, confirmed with "go" on the call and "do it" in
the web chat. This supersedes ADR 0356's gate for The hook
(the settled direction read) and reverses the alternative
that record rejected (requiring the picks). The rest of
ADR 0356's cascade stands exactly as shipped.

## Context

ADR 0356 opened The hook when the direction read for the
picked app settled — landed or failed — on the reasoning
that the place and wardrobe picks are optional refinements
the page defaults. Kasra saw the shipped page live and ruled
otherwise, in his own words: "place and wardrobe should be
first selected then you should reveal the hook section
detail", and "only reveal them when they are filled". The
settled read is the page's own machinery finishing behind
the scenes; it is not the founder progressing. A section
opening on it showed The hook's detail before the founder
had made the two choices the hook is written from.

## Decision

The hook opens when place and wardrobe stand selected —
`dirSel.location` and `dirSel.wardrobe` both non-empty — or
when a hook line already exists, which proves the step was
passed. One pick alone is not the step done: both must be
filled. The picks the direction read matches in from the
saved draft count as selected, so a returning project opens
from its own state, exactly as the rest of the cascade does.

Nothing else in the cascade changes: Choose an app and Place
and wardrobe stand open as before, and Presenter photo,
Render the hook, Demo + CTA and Post kit keep ADR 0356's
gates. The hook still generates from the app's defaults when
a generation is driven with the picks empty — this record
changes when the section shows, and the founder's path
through it (pick place, pick wardrobe, then the hook), not
what generation accepts.

## Alternatives considered

Keeping the settled-read gate (ADR 0356's choice): rejected
by the founder's live ruling — the read settling is not
progress the founder made.

Opening on either pick alone: rejected by the same words —
"place and wardrobe" are named together, and the hook is
written from both.

## Consequences

A fresh HookSnap draft now stands with The hook at its
headline until the founder picks a place and a wardrobe;
the walk down the page gains that step, and the ADR 0356
smoke checks are updated to walk it (the fresh-draft check
now expects five sections at their headlines, and the
sequence check picks both before it writes the hook). The
Create wizard is untouched: its direction picks live on its
Review step under their own standing rules.
