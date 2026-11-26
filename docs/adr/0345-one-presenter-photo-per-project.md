# ADR 0345: One presenter photo per project

## Status

Accepted, Nov 25 2026 — Kasra's order: do not allow two
presenter photos on one render, so the founder never meets
an issue or an error about a duplicated presenter photo.

## Context

Attaching a presenter photo appended it to the project's
asset list with no regard for the photo already there. A
second attach stacked two character references onto one
project, and which face a render would take was left to
whatever read the list first.

## Decision

Attach is replace, at the endpoint: attaching a presenter
photo first drops every other character reference on the
project, and re-attaching the photo already on file is a
no-op that returns the list as it stands. Never two, never
an error. Nothing else on the list is touched, and the
library itself is unchanged — the founder's collection
still holds every photo; a project simply holds one.

## Addendum — the rows that already hold two

Kasra met the render's refusal live the same evening: a
project holding two references (the same photo twice) was
refused with "detach all but the photo you want" — the
exact error this ADR exists to prevent, arriving through a
row written before the ruling. So the read repairs it,
following the two-section backfill's pattern: opening a
project (single read or list) collapses its character
references to the most recently attached one — the list
stands in attach order, so the last face is the latest
pick — and writes the healed list back. The render's
refusal remains in the code as a backstop for a row that
somehow reaches submit unhealed; in the app's own flow the
project is always read before it can render, so the
founder never meets it.

## Consequences

The render's face is always the last photo the founder
picked, by construction rather than by reader convention.
Pinned by API tests: a second face leaves only the new one;
the same face twice leaves one entry.
