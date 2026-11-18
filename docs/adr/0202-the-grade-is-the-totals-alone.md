# ADR 0202: The grade is the total's alone

Status: accepted

Kasra's ruling on Nov 18 2026, made after his own Craft check
panel showed 72/100 beside a letter grade of F: "It shouldn't do
that. The whole grade should be independent." The eight category
scores on that panel (16/12/10/7/6/7/10/4) add up to exactly 72,
which the grade bands grade as a B — but the report forced F and
"Off-brief. Rewrite before rendering." because Trust &
compliance sat at 4, under the cap threshold of 5. Its two
charges, shown in his own tooltip, were "hook_line has an
unfinished sentence" and "script has an unfinished sentence":
form defects, taxed 3 points each by the Trust category's
arithmetic (every spoken-line issue costs 3, whatever kind it
is), and enough to trip a cap designed for promotional or
personal-history lines.

## Decision

- The cap is removed from `assess_spoken_quality`
  (`backend/creative_quality.py`): the block that overrode
  grade to "F" and band to "off_brief" when
  `trust_compliance < 5` is deleted, comment and all. Grade and
  band now come only from `_grade(total)` — the eight
  categories' total alone.
- The Trust & compliance CATEGORY survives intact: its score,
  evidence and advice are computed exactly as before, and its
  points still count toward the total like the other seven. A
  promotional pair still scores badly — it just earns its letter
  through its total, the same way every other weak category
  drags a grade.
- The `capped_by` field goes with the cap. It was written by the
  backend and read by no surface — not the Craft check card, not
  Analytics (which displayed the same unexplained "F · 72") —
  so nothing downstream referenced it; stored reports frozen
  before this change may still carry the field and the capped
  letter, which is their historical record (ADR 0117), and any
  surface reading them simply finds no reader for the field,
  as before.
- Nothing else in the scorer changes: no weights, no cue lists,
  no payment rebalancing. The audit's capped-maxima finding
  (Hook stopping power can reach only 17/20, Audience truth
  13/15) remains an open founder decision, untouched here, as
  does the question of whether form defects belong in Trust's
  arithmetic at all — the generator-side half of that problem
  (lines arriving unfinished) is ADR 0201's FINISHED SENTENCES
  rule.

## Pins

`backend/test_creative_quality.py`: the promotion test keeps its
trust assertions and now pins that its pair's F comes from its
total (36) with no cap marker attached; a new test reproduces the
founder's panel exactly — total 72, Trust 4 — and pins grade B,
band "strong", and no `capped_by` key. Both failed on the capped
scorer and pass without the cap (red before green).
