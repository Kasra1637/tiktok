# 0125 — Angle grounding gains a guarded near-match tier; diversity gains a same-moment check

- **Status:** accepted
- **Date:** 2026-11-12
- **Anchors:** `backend/angle_policy.py` (`_select_feature`,
  `_near_feature_match`, `angle_grounding`, `same_moment_angle_pairs`),
  `backend/ai_service.py` (`generate_content_angles`),
  `backend/test_template_relevance.py` (`TestAngleGrounding`,
  `TestSameMomentAngles`), `backend/test_ai_json_calls.py`
  (`TestAngleDiversity`).

## Context

Kasra walked the pipeline step by step (Nov 12 2026) and reviewed how
app-profile facts feed the angle step — the foundation the plan, the
strategy and the render are all built on. He declined removing any
angle field and approved two strengthenings.

Grounding was exact-only: `angle_grounding` certified an angle's
feature only when its wording equaled a profile core_feature's
normalized wording. A paraphrase of the same feature ("voice
journaling with one tap" for the recorded "One-tap voice journaling")
got no certified link, so the angle's own wording — not the recorded
fact — was what normalize kept and what the plan and strategy briefs
carried as `verified_feature_outcome`, even though that link is
exactly what those briefs trust.

Diversity was wording-only: `duplicate_angle_pairs` flags a pair only
when both fields share >= 80% word trigrams (its docstring: "not a
claim of semantic similarity"). Two angles staging the SAME moment
in different words passed, reached the founder as two choices, and
were really one angle. The generation prompt already forbids shared
moments ("no two angles may share the same moment"), but nothing
checked it.

## Decision

- **Two-tier grounding.** Tier 1 is unchanged: exact normalized
  equality, first match, and it always wins. Tier 2: a near match on
  word tokens — the smaller token set fully contained in the larger,
  OR token Jaccard >= 0.8 — accepted ONLY when exactly one profile
  feature qualifies. Ambiguity (two qualifying features) means no
  link, exactly as a non-match does today; a tier-2 candidate never
  beats another feature's exact match; identical recorded features
  count once. Nothing is invented: no qualifying feature still
  resolves to no link, and unlinked prose is left as written.
- **The outcome link resolves the same way.** Each outcome
  statement's `from_feature` goes through the same two-tier
  selection and links only when it resolves to the selected feature
  — so a paraphrased from_feature now links, and an outcome recorded
  for a different feature is never pulled in by resemblance.
- **Same-moment diversity beside the lexical check.** New
  `same_moment_angle_pairs` in angle_policy: a pair is the same
  moment when BOTH `user_problem` and `hook_promise` reach >= 0.6
  Jaccard similarity on word-token sets. The 0.6 bar sits below the
  lexical check's 0.8 trigram bar because token sets ignore word
  order and repetition: a retold moment scores high here while its
  trigrams diverge, and requiring both fields keeps a shared topic
  with a different problem (or the reverse) from flagging.
  `duplicate_angle_pairs` is untouched.
- **Same handling, one correction.** In `generate_content_angles`,
  same-moment pairs join the existing single DIVERSITY CORRECTION
  pass — one retry naming the pairs, then the same loud failure —
  and pairs already named as lexical duplicates are not named
  twice. The delivered-set size guard is unchanged.
- **The policy module stays pure.** Both checks are deterministic
  token rules — no model calls, no embeddings — so any link or flag
  can be reproduced from the two texts alone. A model-judged
  similarity check was rejected for exactly this reason: its
  verdicts could not be explained or pinned in a test.
- **Non-goals.** Angle fields are unchanged (Kasra's explicit
  call), so plan, strategy and render consume the same shapes.
  Showing the grounding link on the angle card (the review's first
  suggestion) was not chosen and is not built here.

## Consequences

- More generated angles will carry the profile's exact feature text
  and its recorded outcome into the briefs, because the paraphrases
  the model writes naturally now certify. The uniqueness guard is
  the price: a profile whose feature list holds two near-identical
  features will see paraphrases of them go unlinked (exact wording
  still links) — the honest outcome, since the record itself is
  ambiguous there.
- Angle generation may now spend its one correction retry on
  same-moment pairs it previously shipped. A set that cannot be
  made distinct still fails loudly with the same message, and a
  stored set is never replaced by a worse one.
- The thresholds are pinned in tests (`TestAngleGrounding`,
  `TestSameMomentAngles`, `TestAngleDiversity`), so retuning them
  is a deliberate, visible change.
