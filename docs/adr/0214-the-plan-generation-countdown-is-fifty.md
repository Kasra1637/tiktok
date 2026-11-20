# 0214 — The plan-generation countdown is exactly fifty seconds

Status: accepted

## Context

On Nov 19 2026 Kasra dictated the plan-generation wait
directly: "For the plan generation reduce the time the user
have to 50 second exactly." He confirmed the number against
the wait as he experiences it: "currently is around 90."

The countdown a busy button wears is a declared estimate, not
a measurement: `BUSY_ETA_SECONDS` in
`frontend/src/lib/busyEta.js` is the starting number the
button counts down from, holding at 0s when a run goes past
it. The plan-generation button (the wizard's Generate plan
and the Review step's strategy suggestion pass) wore
`planStrategy: 80` — an arithmetic sum, not a decision: the
plan's founder-measured 50s plus the strategy's ~30s, because
the one button covers both stages back to back. The plain
`plan` entry already read 50.

A summed estimate is exactly what the founder's dictation
overrules. The wait the user sits through for plan
generation is one wait, and he named its declared length:
50 seconds, exactly.

## Decision

1. **`BUSY_ETA_SECONDS.planStrategy` is 50**
   (`frontend/src/lib/busyEta.js:40`). The whole
   plan-generation countdown — plan and strategy behind the
   one button — starts at exactly 50s and holds at 0s past
   it, like every estimate in the map.
2. **Nothing else in the map moves.** `angles` 50,
   `templates` 20, `plan` 50, `strategy` 30, `research` 40,
   `refresh` 45 and `postKit` 12 keep their founder-measured
   values; the 10s threshold is untouched.
3. **The declaration is all that changes.** No call, timeout,
   token budget or reasoning level moves: ADR 0211's split
   (the plan chain at High, everything else at extra high) is
   the speed fix; this record only sets the number the button
   declares, per the founder's dictation.

## Alternatives rejected

- **Keep the summed 80 because it is the more accurate
  estimate.** The countdown is the founder's declared wait,
  set by his measurement and his word — the same basis as the
  founder-measured values the smoke pin already carries for
  angles, templates and plan. Accuracy of the sum was never
  the point; the declared wait is a product decision.
- **Lower the strategy stage's own `strategy` entry too.**
  Kasra named the plan-generation wait — the combined
  button's countdown. The standalone strategy rebuild keeps
  its measured ~30s.

## Consequences

Every plan-generation button now counts down from exactly
50s. A run that takes longer holds at "· 0s" instead of
restarting or going negative — the map's standing behavior —
so a slow run reads as over its declared wait, which is the
honest signal that sent Kasra to ADR 0211's speed fix in the
first place. The render smoke pins `planStrategy` at 50
beside the other founder-set countdowns, and its in-flight
plan check's countdown thresholds (opens at the full count,
resumes where the wait actually is) are re-based on 50, so
the number cannot drift back to the sum silently.
