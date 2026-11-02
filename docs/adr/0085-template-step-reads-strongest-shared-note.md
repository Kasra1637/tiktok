# 0085 — The template step reads the strongest shared note, not every one

Status: accepted (partially supersedes 0074's section-copy clause)

## Context

0074 moved the fit notes every card shared out of the cards and into one block
under the section eyebrow, so "Fit 10/10" cards stopped repeating six identical
lines. It fixed the repetition and left the length: the block joined every
hoisted note with `join(" ")` into two paragraphs, and the notes are whole
sentences from the scorer, so the section above the grid ran to six sentences
and ~90 words — longer and louder than the cards it summarised. The card it
summarised leads with one verdict and tucks the rest behind "More on this fit",
so the summary had a worse hierarchy than the thing being summarised.

Two specific defects came out of the same block:

- **Notes ran together.** Not every scorer note ends in a full stop —
  `"Bounded by: " + "; ".join(claims)` never did — so joining with a space
  produced "…do not state a time length for the process Needs character
  reference.", two limits fused into one sentence with the boundary gone.
- **The angle's claims were re-sold as template limits.** `claims_to_respect`
  bounds the *angle*, and `frontend/src/lib/angleSubtitle.js:angleDetails`
  already renders them as a "Bounded by" row in the picked angle's panel —
  which sits directly above this list on the same step. Carried into the
  template's limitations they showed up a second time, one surface down, in the
  model's own imperative voice ("Do not claim clinical insight", "Do not claim
  the app improves emotional intelligence"): writer instructions the founder
  cannot act on, in the place they choose a template.

## Decision

- Each shared limitation renders as its own list item, the shape the card's own
  limits use. No `join(" ")` over notes anywhere in the section.
- The section reads **one** shared reason: `shared_reasons[0]`, which is the
  strongest because the server sorts reasons by weight
  (`backend/template_recommendations.py:weighted.sort`) and feedback/outcome
  reasons are inserted at the front. That note answers why the set ranks at all,
  which is the section's entire job.
- The remaining shared reasons are not read. They are echoes of input the
  founder just supplied — the app's category match, and the "open to anyone"
  0.5-point tiebreak — and each cost a line above a grid they came to pick from.
- The scorer no longer copies the angle's `claims_to_respect` into a template
  limitation (`backend/template_recommendations.py`). The constraint still
  reaches the prompt from the angle row; the only thing removed is the
  duplication on screen.
- Scaffolding labels ("True of every template below:", "Limits on every
  template below:") go. The eyebrow above already scopes the block; the labels
  spent twelve words saying what position on the page already said.

Alternatives rejected: **bullets only, no content change** (the run-on is fixed
but eight indented lines replace six sentences — taller, still a wall);
**deleting the block and returning the notes to the cards** (that is the
repetition 0074 exists to prevent, and the goal match is the only thing
explaining why the set is here); **filtering "Bounded by" out of
`shared_limitations` client-side** (a string-prefix rule in the view standing in
for a fact the scorer owns — the note should not be produced, not hidden).

## Consequences

- The section is one line and the limits below it, typically two short lines:
  ~16 words instead of ~90, with every note that changes what the founder must
  do still visible (a required photo, an unapproved draft).
- The shared fit block no longer describes the angle. Reading it top to bottom,
  the angle panel states the bounds and the template step states the ranking.
- `shared_reasons` still carries every hoisted note, so the payload stays
  honest and a future surface can read the rest; the section's choice of one is
  a copy decision here, not a second implementation of the hoisting rule 0074
  rejected on drift grounds.
- Response shape is unchanged apart from the missing `Bounded by:` entry, so a
  single-card set reads as before minus one duplicated line.

## Anchors

- `backend/template_recommendations.py` (`score_template_for_angle`: the
  removed claims limitation; `weighted.sort` for the ordering the section
  depends on)
- `frontend/src/pages/CreateVideo.jsx` (`templates-shared-fit`,
  `templates-shared-reason`)
- `frontend/src/lib/angleSubtitle.js` (`angleDetails`, the "Bounded by" row)
- `frontend/scripts/check-render-smoke.cjs` — "notes every template shares are
  read once above the cards" asserts one reason line, one `<li>` per limit, and
  no "Bounded by" in the section
