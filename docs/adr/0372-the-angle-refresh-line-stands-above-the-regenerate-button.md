# ADR 0372: The angle refresh line stands above the Regenerate button, in plainer words

## Status

Accepted, Nov 26 2026 — Kasra's order on the call: the
refresh line above the Regenerate angle button, right
under the "Audience angle (required)" heading, and the
line made more punchy, more conversational and easier
to understand. One component: the populated
audience-angle list in
`frontend/src/components/studio/SelectionPanels.jsx`.
The gate (empty-state) branch of the same component is
out of scope and untouched.

## Decision

The populated list rendered the Regenerate angles
button first and the freshness/hint row below it. The
whole row — the "Refreshed {freshness}" stamp
(`angle-set-freshness`), the separator, and the aim
hint (`angles-aim-hint`) — now stands directly above
the button. The fixed-camera indoor note
(`angles-fixed-indoor-note`) keeps its text and its
seat below the button.

The hint's words change: "Pick a goal first —
regenerating aims fresh angles at it." becomes "Pick
your goal first — new angles will aim straight at it."
Same meaning — pick a goal first; regenerating aims
the fresh angles at it — in plainer, more direct
words. The element keeps `data-subtitle`, so the
wizard subtitle budget binds it: the new string is 58
characters, inside the 55–60 window (counted in code
before the change was made; the budget check pins it
from source as before).

This reverses, for this one panel and on Kasra's
explicit order, the standing "primary action above its
guidance copy" arrangement: here the status line leads
and the button follows it, because the line is the
decision's context — how fresh the set is, and what a
regeneration would aim at — and Kasra wants it read
first, under the heading.

## Checks

New: "the angle refresh line stands above Regenerate
in its new words (ADR 0372)" — pins the hint's exact
new copy, the row above the button in document order,
and, on a second mount standing on the fixed camera,
the indoor note still below the button. Written red
first.

Examined and unchanged:

- "the angle freshness and the aim hint share one
  line" (ADR 0291): its assertion is the shared parent
  — the row moved as one element, so the one-line rule
  stands exactly as protected. Only its comment
  changed: it said the line stands "under Regenerate";
  it now records the line's seat above it. No assertion
  moved.
- "the angle list dates its set": asserts the
  freshness stamp's text; the panel's internal order
  was never its subject.
- "regenerating without a picked goal names the aim":
  asserts the hint exists without a goal, names a
  goal, and retires when one is picked; the new copy
  still names the goal.
- "Review and dense panels put the primary action
  above its guidance copy": its angle coverage is the
  gate (empty-state) branch — untouched here — and it
  never pinned the populated list's row order. It
  stands unchanged, and this record is where the
  populated panel's exception lives: Kasra's explicit
  order, not a drift the check missed.
- "every wizard subtitle fits the shared size and
  length budget": unchanged, and it is the check that
  holds the new copy at 58 chars.

No check was weakened: the one assertion family that
could have spoken to this panel's order never covered
it, and the new check pins the new order directly.

## Alternatives considered

Keeping the button first and only rewriting the copy:
rejected — Kasra's order names both halves, the move
and the words, and the line's whole point is to be
read before the press it informs.
