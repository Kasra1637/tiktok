# ADR 0369: The strategy panel's groups wear the one face, and its standing lines are gone

## Status

Accepted, Nov 26 2026 — Kasra's spread order in the main
chat, applied to Create's strategy panel
(HookContinuityPanel).

## Decision

"What you get" gains the ListChecks icon. The
CollapsedGroup headers gain icons of their own — Zap
(Hook concept), Lightbulb (Why this works for this app),
Target (What the viewer ends up with), MapPin (Scene
details) — the last two matching the icons those blocks'
own StrategyBlock headings already carry. The suggestion
modal's "Hook"/"Script" mini-labels take the eyebrow
face, joining the modal's column heads that already wear
it. `CollapsedGroup` takes an `icon` prop for this; its
collapse behavior is untouched.

Removed: "This strategy guides the Hook + Story render."
(the panel's lead line), "Text only. It fixes the concept,
the words and the locked scene…" (the pre-build note), and
the "What you get" per-role descriptive lines. The last
removal covers BOTH lines each role carried in the empty
state — the section-copy gloss beside the role name and
the note under it — so the list now names the shape only:
the two role names. This is scoped to the empty state:
SectionRow's readout keeps the same section copy whole,
because there it is the readout, not standing description.

Every readout value stays: the sections, the scene rows,
the digests, the outcome rows, and every alert and state
line in the panel are exactly as before.

## Checks

No existing check is changed by this round. The standing
"What you get" presence pin still passes — the heading
stands, now with its icon — and the panel's readout
checks are untouched. New in this round: the strategy
check (the lead line's absence, the four group headers'
icons, the sections readout intact, the modal labels
pinned at the source) and the empty-state check (the
shape-only list, the removed lines' absence, the heading's
icon).

## Alternatives considered

Keeping the section-copy gloss in the What-you-get list
because the readout uses the same words: in the empty
state the gloss describes a video that does not exist
yet, which is the standing-description shape this whole
round removes; in the readout it describes the built
strategy, which is content. The line's home decides, not
its wording.
