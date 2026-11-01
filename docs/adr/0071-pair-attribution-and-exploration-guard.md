# 0071 — Pair attribution sharpens the loop, thin evidence invites exploration

Status: accepted

## Context

Kind-level aggregation could never learn which *specific* angle worked —
only that the family did — while objective-level aggregation could not
say which kind served a goal best. Per-angle-id attribution was rejected
earlier by design: regeneration replaces every row id, so identitychased
evidence would die on every regen. Meanwhile the loop had no exploration
mechanism: with one tried kind and nothing else, exploiting the single
data point would freeze the loop on its first guess. The weights
(`POSTED_CLIP_WEIGHT`, `OUTCOME_HALF_LIFE_DAYS`) also remain reasoned
constants, still unmeasured against outcome volume.

## Decision

- Pair attribution (kind × objective) is the sharpest regeneration-safe
  grain: both axes are fixed vocabularies, so their intersection
  survives regeneration that kills row ids. Verdicts and posted clips
  both accumulate into pairs; a verdict naming one axis alone never
  invents a pair.
- Pairs render first in the prompt section (`Proven pairs`), ahead of
  each axis alone, and travel to the wizard as `pair_evidence` keyed
  `kind‖objective` — the goal card knows both, so it names the most
  specific evidence (`4 wins · posted in 1 clip · 12.4k views for this
  pairing`) without re-deriving anything.
- Thin-evidence exploration guard: under 3 units of evidence (thumbs +
  double-weighted posts), the section invites one untried kind alongside
  the proven ones. Exploitation waits until the evidence earns weight.

Alternatives rejected: per-angle-id attribution (dies on regen —
correctness first); a separate exploration budget or epsilon-greedy
sampler (the prompt already says not to exclude on one verdict; a prose
invite at thin evidence is the honest minimum, not a bandit
implementation); measuring the weight constants now (no outcome volume
yet — they stay flagged, not faked).

## Consequences

- The loop learns combinations, not just families: problem_solution for
  demonstrate_feature is a different claim than either alone.
- New apps explore before they exploit; proven apps exploit proven pairs.
- Still open: calibrating the weight constants against posted outcome
  volume, and logging rank-at-pick so calibration has something to fit.
- Anchor: `backend/feedback.py:summarize_angle_feedback` (pairs,
  thin invite); `backend/server.py:_serialize_profile_angles`
  (pair_evidence); `frontend/src/pages/CreateVideo.jsx`
  (goal-pair-evidence-*).
