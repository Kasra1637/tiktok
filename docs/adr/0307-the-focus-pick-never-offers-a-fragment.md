# ADR 0307: The Focus pick never offers a fragment

Status: accepted

## Context

The completeness bar (ADR 0249) governs new research runs only:
its own record leaves already-stored profiles untouched. The
founder's Vocolens profile predates it, so its stored outcome
lists still carry the chopped pieces the bar was written about
— "from your own words", "triggers", "and growth over time" —
and the Hook + CTA Focus pick offered them verbatim as options
beside whole lines like "See your own rhythms". Shown the open
dropdown on Nov 23 2026, the founder ordered the incomplete,
broken text across the Focus area fixed. The outcome refresh
(ADR 0288) rewrites the stored layer, but until a founder
refreshes, the pick kept serving the pieces.

## Decision

The pick's vocabulary passes through the same bar.
`profile_focus_lines` in ai_service.py returns the stored
outcome lines that stand alone under `_outcome_stands_alone`;
the studio PATCH's membership proof and generation's pick
resolution both check against it, and the frontend's
`profileOutcomeLines` mirrors the bar so the dropdown and the
backend agree line for line. `profile_outcome_lines` itself is
unchanged: the refresh's avoid list still needs every stored
line, fragments included, so the model is told not to repeat
them. Stored profile data is not rewritten by this decision.

The same order capped the list: the pick shows six lines at a
time — the first six that stand alone, in the profile's own
order (`FOCUS_LINE_LIMIT` on the backend, the same slice in the
frontend mirror). The lines beyond six are not offered until a
refresh brings a fresh layer forward. The ADR 0288 smoke
scenario's old premise — the fragment offered before a refresh,
gone after — is flipped with this decision: a fragment is not
offered before the refresh either.

## Consequences

No profile, however old, can offer a fragment as a Focus pick,
and a pick saved earlier that names a fragment stops steering
the hook — it resolves like a line the profile no longer
carries, and the control reads as the app's choice. The stored
pieces remain on the profile until the founder runs the
outcome refresh, which replaces the layer wholesale.
