# ADR 0365: Direction fields show two buttons until New options

## Status

Accepted, Nov 26 2026 — Kasra's rule, given on his voice
call with the Optional-chip removal and built in this
round: "Location and Wardrobe show only TWO option buttons
each by default; more options appear only when the user
selects New options."

## Context

`DirectionSelect` (the shared Location/Wardrobe control)
showed three options by default. A saved pick outside the
shown three still applied by the last-seat rule: it took
the third seat beside the first two, so what applied was
always on a lit button. The control has exactly two
consumers — Create's direction section and HookSnap's
Place and wardrobe card, two fields each, every one of
them wired with the "New options" refresh (one text model
call for four fresh options, the current pick preserved by
the merge in `useWizardDirections`).

## Decision

Two buttons stand by default, on both pages, from the one
shared control — no other DirectionSelect consumer exists,
and every instance carries the refresh this rule keys on.

The reveal: pressing "New options" reveals the field's set
in place at once, and the refreshed set that lands in
answer stays revealed. A set that arrives any other way —
a profile or camera change re-reads the lists — starts at
two again. A refresh that fails lands no set, and its press
earns no lasting reveal.

The last-seat rule survives at the smaller width,
reconciled with it: a saved pick outside the visible two
takes the SECOND seat beside the first option (where the
three-wide row seated it last of three), lit, so the
founder's pick always stands in the pair and never hides
behind the reveal. This round's smoke pins the seating on
a fresh mount: a place saved fourth in its set shows as
the second of two buttons, pressed.

Nothing about the options themselves changes: the sets,
the refresh, the pick-saving and the 25-character button
labels (ADRs 0332/0337) are exactly as before — only how
many buttons stand before the press.

## Checks

Changed, named here per the house rule — both keep their
subjects; only the standing count follows this rule:

- "camera setup and profile-matched direction pairs save
  and survive reload": its first-three-buttons assertion
  becomes first-two (its save, reload and plan-default
  assertions are untouched).
- "a fixed camera is offered indoor locations only, a
  handheld any location": its offered-set assertion becomes
  the first two, and its safely-shortened label list the
  two labels that stand (the camera filtering it pins —
  fixed indoor only, handheld the full set — is unchanged;
  the fixed set is two long, so it still reads whole).

New in this round: the HookSnap pair check pins two-by-
default in both fields and the full refreshed set after
the press; the seating check above pins the saved pick.

## Alternatives considered

Revealing on the press but collapsing again when the
refreshed set lands: the founder asked for the fuller set
and would watch it vanish at the moment it arrives.
Keeping three for the field whose set is shortest: the
rule is per field, not per set size — two everywhere reads
as one design.
