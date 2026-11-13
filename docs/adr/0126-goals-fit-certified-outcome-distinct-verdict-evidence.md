# 0126 — Goals fit the certified outcome, are distinct by meaning, and carry verdict evidence

- **Status:** accepted
- **Date:** 2026-11-12
- **Anchors:** `backend/ai_service.py` (`generate_angle_goals`),
  `backend/angle_policy.py` (`same_outcome_goal_pairs`),
  `backend/feedback.py` (`verdict_objective_evidence`),
  `backend/routers/brands.py` (`_verdict_objective_evidence`,
  `_serialize_profile_angles`, `live_angle_goals`),
  `frontend/src/hooks/useWizardAngleStep.js`,
  `frontend/src/components/studio/SelectionPanels.jsx`
  (`AngleGoalPicker`); tests in `backend/test_ai_json_calls.py`
  (`TestLiveAngleGoals`), `backend/test_template_relevance.py`
  (`TestSameOutcomeGoals`), `backend/test_video_verdicts.py`
  (`TestVerdictObjectiveEvidence`),
  `backend/test_template_library_api.py`
  (`TestGoalVerdictEvidencePayload`).

## Context

Kasra walked the pipeline step by step (Nov 12 2026); with the angle
step strengthened (ADR 0125), he reviewed the goal step and approved
three additive strengthenings — the standing rule for this walk:
enhancements only add, the pipeline improves together as one
cohesive piece, nothing is removed, and downstream shapes do not
change.

The goal ranking had three gaps, each the goal-step analogue of
something the angle step or ADR 0124 already fixed:

- **Fitting ignored the certified fact.** `generate_angle_goals`
  ranked the six vocabulary goals from the verified profile facts and
  the angle's own words, but never consulted the angle's certified
  grounding — the feature/outcome pair `angle_grounding` verified
  against the profile, and the very pair the plan and strategy briefs
  carry as `verified_feature_outcome`. The goal step was fitted to
  the angle's prose while every later step trusts the certified pair.
- **Distinctness stopped at names.** The six goals were distinct by
  vocabulary name only (a repeat fails loudly). Two goals with
  different names could still promise the viewer the same outcome in
  different words — the same flaw ADR 0125's same-moment check fixed
  for angles.
- **Goal cards showed no verdict evidence.** Angle cards show what
  the founder's whole-video verdicts (ADR 0124) say about an angle
  kind; goal cards showed the older record axes (goal thumbs by kind,
  by objective, by pairing) but nothing from the verdict signal —
  even though every verdict bundle froze the objective its video was
  made for.

## Decision

- **The certified pair enters the goal prompt.** When
  `angle_grounding(profile, angle)` resolves a feature/outcome pair,
  the goal prompt gains a clearly labeled CERTIFIED section carrying
  the pair as `verified_feature_outcome` JSON — the same key and
  presentation the plan and strategy briefs use — with the
  instruction that every goal's `why_it_fits` aims at that certified
  outcome. When no pair certifies, no section is added and the
  prompt is exactly what it was. The goal schema (vocabulary name,
  description, why_it_fits, fit_score) does not change.
- **Meaning-level distinctness beside the name check.** New pure
  helper `same_outcome_goal_pairs` in `angle_policy`: a pair is the
  same outcome when the token set of its combined outcome-bearing
  text — description + why_it_fits read as one text — reaches
  >= 0.6 Jaccard similarity. The bar is the same-moment bar (ADR
  0125), for the same reason: token sets ignore word order, so a
  retold outcome scores high while its wording diverges, and 0.6
  stays far above what shared connective filler contributes. One
  combined text rather than the angle check's both-fields rule,
  because a goal's two fields are one promise split across a
  description and a fit reason, where an angle's two fields are two
  different claims that must each repeat. The check is
  deterministic — no model calls — so any flag reproduces from the
  two texts alone.
- **Same bounded handling as the angle diversity correction.** In
  `generate_angle_goals`, same-outcome pairs get one DIVERSITY
  CORRECTION pass naming the pairs and demanding a genuinely
  different promised outcome (vocabulary name kept), then the same
  loud failure with nothing persisted — the live-goals endpoint's
  existing failure behavior (502, no partial set) is preserved.
- **Verdict evidence on the goal card, mirroring the angle cards.**
  `feedback.verdict_objective_evidence` tallies the profile's
  whole-video verdict rows per objective, keyed by the objective
  frozen in each bundle's context — the goal the video was actually
  made for when judged, so later project edits never re-attribute
  it (the existing `objective_evidence` axis attributes by the
  project's current objective; both axes stay). Buckets keep the
  shared evidence shape (wins/flops counted; adoptions/posted/views
  zero, as those belong to the behavior record). The tally rides the
  angles payload (`verdict_objective_evidence` on
  `_serialize_profile_angles`, so GET and generate/regenerate agree)
  and the live-goals response, and the goal card renders it through
  the existing `formatVerdicts` as "… at this goal". An objective
  with no verdicts renders nothing, exactly as the other axes
  behave.
- **The evidence is a pure read.** It is computed from stored
  verdicts at payload time and never triggers goal generation —
  ADR 0122's click-to-generate discipline is absolute. A read
  failure degrades to an empty map rather than failing the list,
  the way the studio steering read degrades.
- **Non-goals.** No goal schema change; no new generation triggers;
  nothing removed; the Review recovery copies of the picker are
  unchanged (they never received the objective/pair maps either —
  the main step carries the evidence lines).

## Consequences

- When an angle certifies, its six goals are now fitted against the
  same certified outcome the plan and strategy will be built from,
  so the pipeline's steps argue from one fact instead of adjacent
  prose.
- Goal generation may now spend its one correction retry on
  same-outcome pairs it previously shipped. A set that cannot be
  made distinct fails loudly and shows nothing, rather than offering
  the founder six names for fewer real choices.
- Profiles with verdicts pay one more bounded read (200 rows) per
  angles payload and per live-goals call; profiles without verdicts
  see an empty map and no new line anywhere.
- The 0.6 threshold is pinned in tests (`TestSameOutcomeGoals`,
  `TestLiveAngleGoals`), so retuning it is a deliberate, visible
  change, as with the angle bars.
