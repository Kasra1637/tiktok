# ADR 0320: The Buffet is staged

Status: accepted

## Context

The Buffet — the Focus header's outcome refresh (ADR 0288,
named by ADR 0308) — stood in the Hook + CTA hook card
from the first moment, before any hook existed. The
founder asked whether it should appear only after a
generation, when it is needed (Nov 24 2026), and approved
the staging: hidden until the first hook, shown early
only when the menu is stale. Its placement does not move:
a section's action belongs in the section's header, beside
the menu it refreshes, and away from the generate button
it must never compete with.

## Decision

HookPicksControl renders the Buffet only when the host
wires the refresh AND one of two states holds: a hook
exists on the project (hasHook — the steering moment), or
the focus menu is stale (focusStale). A menu is stale
when the profile still stores outcome lines the
completeness bar cannot offer — the fragments an older
research pass left behind, which the pick silently drops
(`profileOutcomeMenuStale`, computed from the same stored
texts `profileOutcomeLines` filters). Shown early, the
Buffet carries its reason under the pick: some stored
outcomes are fragments the menu can't offer whole, and
the Buffet writes a fresh set. Shown after a hook, it
needs no reason — the founder is steering.

## Consequences

The hook card opens quieter: Focus, Tone and Shape, with
no long refresh on offer before it can help. The escape
from a fragment-carrying menu survives — it simply
announces itself, with its reason, only when it is owed.
Jest's component suite cannot run in this environment
(a pre-existing "@/lib/utils" resolution failure, verified
on the pristine tree); the staging is pinned by the
render-smoke gate and by unit tests that run wherever
that suite is configured.
