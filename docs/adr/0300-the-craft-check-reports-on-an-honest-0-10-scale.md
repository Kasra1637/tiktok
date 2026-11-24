# ADR 0300: The Craft check reports on an honest 0–10 scale

Status: accepted

## Context

The Craft check summed its eight categories to a total shown
"out of 100" — but two categories cannot reach their weights:
Hook stopping power's positive cues sum to 17 of its 20 points,
and Audience truth's to 13 of its 15, so no pair could ever pass
95 while the card implied 100 was reachable. The capped maxima
sat as an open audit finding until Kasra closed it himself
(Nov 23 2026): rate it zero to ten so a user can grasp it, and
fix the logic to be accurate — "it should be true to exactly
what it is; zero being worst, ten being best."

## Decision

Every surface that shows a Craft score now shows it on a 0–10
scale computed against what the scorer can actually award. The
report gains achievable_max (95 for the full report; 17 and 13
for the two capped categories, the weight for the rest), a
score10 on the report and on each dimension (points divided by
the achievable max, times ten, one decimal), and max10. The
scorer itself is untouched — same cues, same points, same
weights, same grade thresholds; only the reading is made true.
The Craft card shows the total and each tile out of 10, the
ring and the tile bars fill against the honest scale, the copy
blocks and the Analytics result rows read the same number, and
reports stored before this change (frozen at submit, ADR 0117)
gain their 0–10 fields on read via with_score10, computed from
their own dimensions, so an old render and a fresh one read on
one scale.

## Consequences

Settled pairs keep their meaning: the mural's 87 becomes 9.2,
the riverside pair's 81 becomes 8.5, the orchard pair's 76
becomes 8 — the same standing, honestly labelled. A perfect
pair can now actually read 10, which no pair could read as 100
before. The raw points stay on the report (total, max, per-
dimension score/max) for the feedback loop and the tests that
reason in points; nothing that consumed them changes. The grade
letters do not move, because their thresholds read the points,
not the display.
