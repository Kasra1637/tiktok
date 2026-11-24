# ADR 0293: The invitation stands down while it works

Status: accepted

## Context

ADR 0290 gave the empty plan's Regenerate plan button the final
Generate's pulsing glow, so the one required click could not be
missed. On Nov 23 2026 Kasra watched it through a regeneration:
the plan stays wordless until the new words land, so the button
kept pulsing for the whole flight — still inviting a click it
was already carrying out. He ordered the glow to stop once the
user starts generation.

## Decision

The pulse now requires the button to be idle: the Regenerate
plan button wears generate-invite only while the plan is empty
AND no regeneration is running. The moment the flight starts,
the class comes off and the button's busy face — disabled, the
"Regenerating plan" label, the countdown — narrates the wait
alone. When the flight settles the state re-reads as before: a
plan that landed words never pulses, and an empty plan whose
regeneration failed pulses again, because the click is required
again. A smoke check pins both halves on the empty-plan fixture:
pulsing before the click, dark and disabled mid-flight.

## Consequences

The glow means exactly one thing everywhere it appears — this
click is waiting for you — and never competes with the busy
narration of work already underway.
