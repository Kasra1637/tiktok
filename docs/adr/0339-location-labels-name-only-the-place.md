# ADR 0339: Location labels name only the place

## Status

Accepted, Nov 25 2026 — Kasra's ruling on a voice call, at the
live review of the ADR 0334–0338 rounds.

## Context

The Location buttons offered dressed-up descriptions: "Quiet
garden bench", "Calm living room with a plant beside the
chair", "Balcony with a simple chair". Kasra's ruling: a
location label mentions the location, nothing else — no
adjectives, no extra wording — two or three words, nice and
simple, like "in the car" or "on the balcony". The first
options a founder sees are the template library's deterministic
lists (no model call), so the rule lands there first; the
refresh writer must hold it too, so a refreshed set does not
dress the places back up.

## Decision

Every location label in the template library now names only
the place, in two or three words: "Garden bench", "Living
room", "Home balcony", "Kitchen counter", "Park table". The
place noun itself is untouched, so the indoor/outdoor
classifier (ADR 0219) and the angle fit read the same places
as before.

The direction refresh writer carries the same rule for the
location field: name only the place itself, in two or three
words, no adjectives, no extra wording. Wardrobe is not a
place and keeps the ADR 0337 completeness rule only.

Labels already stored on a profile or project are not
rewritten; the ADR 0337 display trim shortens those safely
when they are long.

## Consequences

A new location option, from the library or from a refresh, is
the plain place name or it is a change to this record. A
backend test pins the refresh instruction, and the API tests
pin the library's served lists.
