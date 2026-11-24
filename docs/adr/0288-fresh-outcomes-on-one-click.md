# ADR 0288: Fresh outcomes on one click

Status: accepted

## Context

On Nov 23 2026 Kasra opened the Hook + CTA Focus pick on his saved
Vocolens profile and read broken options: "from your own words",
"triggers", "and growth over time" — fragments of longer outcomes,
chopped at their commas by a research run that predated ADR 0249's
completeness bar. The bar governs new research only (its own
ruling: already-stored profiles are untouched), so his list could
only heal by re-researching the whole app. He ordered the direct
remedy instead: a Refresh button in the Focus area, where the user
can click and get fresh ideas.

## Decision

A Refresh button stands beside the Focus pick on the Hook + CTA
page. One click calls POST /app-profiles/{id}/outcomes/refresh,
which writes a FRESH outcome layer onto the profile and returns
the updated profile; the page adopts it as its detail read, so the
fresh lines are the pick's options at once.

The layer is written by ai_service.generate_outcome_refresh from
the profile's STORED facts only — features, problems, use cases,
audience, differentiators; no new sources, no re-research — with
the current lines as an avoid list, and it is accepted through the
research run's own bars: `_normalize_outcome_statements` (each
statement linked to a core feature verbatim, each outcome standing
alone) and the flat list's completeness filter. A reply yielding
fewer than three usable statements fails with the standard
sentence (ADR 0242's pattern) and changes nothing — a failed
refresh never halves a profile's outcomes.

Because the refreshed lines are saved ON the profile, ADR 0247's
membership proof holds unchanged: the pick is still one of the
profile's own lines, at save time and at generation time. A saved
focus pick the new layer no longer carries reads as the app's
choice, the standing behavior for a line a profile stops carrying.

## Consequences

Kasra's fragments heal with one click, in the place he found them,
and any founder can refresh a stale outcome layer without
re-researching their app. The outcome layer now has two writers —
research and this refresh — both held to the same bars by the same
normalizers, so no surface can be offered a fragment again from a
refreshed profile.
