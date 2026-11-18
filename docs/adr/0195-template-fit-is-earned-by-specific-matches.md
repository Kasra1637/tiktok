# ADR 0195: Template fit is earned by the specific matches, not the givens

Status: accepted

Across Kasra's Nov 14 and Nov 17 2026 screenshots, every tailored
template scored Fit 9/10 or 10/10 while every angle scored 3-4/10.
A fit number that sits at the top of the scale for every card
cannot help the founder choose, and the identical Shape and
"In your video" lines across cards made the whole panel read as
decoration.

## What the trace found

Template fit is a deterministic weighted sum in
`score_template_for_angle` (`backend/template_recommendations.py`)
— no model self-rating is involved. The collapse was arithmetic:

- The factors a tailored template earns merely by being generated
  for the profile — tailored bonus 2.0, objective match 3.0,
  category match 2.5, structure affinity 2.0 — summed to **9.5 of
  the 10** before any template-specific match was counted. The
  specific factors (audience overlap, problem overlap, feature
  hit) could add at most the remaining clamp headroom, so every
  tailored card landed at 9.5-10.0 regardless of its content.
- Three no-match fallbacks paid 0.5 each from below: the affinity
  else-branch paid 0.5 silently for the ABSENCE of a structure
  match, and the audience ("Open to anyone") and no-category
  fallbacks paid 0.5 each for the absence of a match, lifting
  weak cards toward strong ones.
- The specific factors also fire rarely on real generated text:
  the problem/audience tag vocabularies in
  `backend/recommendation_tags.py` are small curated sets, and
  the screenshot fixture's rich problem text ("thoughts outrun
  their hands and typing is too slow") maps to no problem tag at
  all. That vocabulary breadth is a separate, larger question;
  this record fixes the weights so that when a specific match
  does fire, it is what separates the cards.

## Decision

Rebalanced in place — no rescaling, no cosmetic spread:

- Givens capped at 6.5 of 10 combined: tailored 2.0 → 1.0,
  objective match 3.0 → 2.5, category match 2.5 → 1.5,
  structure affinity 2.0 → 1.5 (objection branch 1.5 → 1.0).
- Specific matches pay more: audience overlap 1.0 → 1.5 with its
  ≥2-overlap bonus 0.5 → 1.0; problem overlap 1.0 → 1.5 with its
  ≥2-overlap bonus 0.5 → 1.0. The feature factor stays 1.0
  (ADR 0194).
- The no-match fallbacks stopped paying: the affinity else-branch
  pays nothing; the audience and no-category sentences remain on
  the card as zero-weight notes, because reach and neutrality are
  facts worth printing — they are just not fit.
- Penalties (relevance −2.0, scene structure −3.0, verdict delta,
  retirement −3.0) and the objective-mismatch 0.5 are unchanged.

## Measured distribution

On the fixture built from the screenshot's own cards
(`backend/test_template_fit.py`, Vocolens-shaped profile/angle):

- Screenshot set: **10.0 / 9.5 / 9.5 before → 6.5 / 6.0 / 5.0
  after** (spread 0.5 → 1.5).
- Scale set (an angle whose problem carries a tag, so the
  specific factors are in play): **10 / 10 / 8.5 before →
  10.0 / 8.0 / 5.0 after** (spread 1.5 → 5.0). The ceiling stays
  reachable — by a card that earns the specific matches, not by
  the givens alone; a givens-only card now scores 5.0.

## Consequences

Pins live in `backend/test_template_fit.py`
(`TestFitDiscrimination`, `TestScaleDiscriminates`).
`test_template_library.py`'s objective-match floor was updated to
the new arithmetic (6.5 for its fixture, asserted ≥ 6.0). The
angle half of the fit problem — the frontend rank transform that
floored every untested angle at 3-4 — is a separate mechanism and
its own record (ADR 0193).
