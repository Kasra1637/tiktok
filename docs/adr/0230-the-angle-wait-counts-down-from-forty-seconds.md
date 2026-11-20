# 0230 — The angle wait counts down from forty seconds

Status: accepted

## Context

On Nov 20 2026 Kasra dictated the angle-generation wait
directly: the countdown comes down from 50 seconds to 40.
The set the wait covers changed the same morning — angle sets
are four now, not six (ADR 0226) — and the declared number is
his, following the precedent of ADR 0214 (the plan countdown
dictated to exactly 50s).

The countdown a busy button wears is a declared estimate, not
a measurement: `BUSY_ETA_SECONDS` in
`frontend/src/lib/busyEta.js` is the starting number the
button counts down from, holding at 0s when a run goes past
it. The `angles` entry read 50 — founder-measured for six
fielded angles — and it is the ONE entry both angle buttons
read: the angle panel's Generate angles and Regenerate angles,
and the sticky bar's mirrored faces of them (ADR 0229), all
count down from this single value.

## Decision

1. **`BUSY_ETA_SECONDS.angles` is 40**
   (`frontend/src/lib/busyEta.js`). Both angle countdowns —
   Generate and Regenerate — start at 40s together, because
   they were never two numbers.
2. **Nothing else in the map moves.** `templates` 20, `plan`
   50 and `planStrategy` 50 (ADR 0214), `strategy` 30,
   `research` 40, `refresh` 45 and `postKit` 12 keep their
   values; the 10s threshold is untouched.
3. **The declaration is all that changes.** No call, timeout,
   token budget or generation behavior moves: the angle call
   takes what it takes, and a run past 40s holds at 0s like
   every estimate in the map.

## Consequences

The render smoke's busy-button check pins the map's founder
times with angles at 40 beside plan and planStrategy at 50, so
the dictated number cannot drift silently. The header comment
in `busyEta.js` records the dictation and the four-angle set
it belongs to, superseding the six-angle measurement it
replaces.
