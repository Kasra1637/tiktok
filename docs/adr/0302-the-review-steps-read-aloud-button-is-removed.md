# ADR 0302: The Review step's read-aloud button is removed

Status: accepted

## Context

The Review & submit step carried a speaker-icon ListenButton at
the end of its tab row — read-aloud for the plan and the
strategy, added from the Nov 14 2026 audit's finding that the
step holds the most text in the app. The founder, looking at
the step in the live app (Nov 23 2026), ordered the speaker
icon removed.

## Decision

The Review step's ListenButton instance is removed from
CreateVideo.jsx, with its import. The ListenButton component
itself and its other surfaces — the profile sections and Brand
Setup — are untouched; this is the one button the founder
pointed at.

## Consequences

The Review step's header row is the two tabs alone. The plan
and strategy lose their read-aloud on this step; every other
listen surface keeps working exactly as before.
