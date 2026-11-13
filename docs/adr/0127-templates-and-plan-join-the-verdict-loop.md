# 0127 — Templates and the plan join the verdict loop: verdict-ranked picks, structural diversity, and the hook's certified promise

- **Status:** accepted
- **Date:** 2026-11-12
- **Anchors:** `backend/feedback.py` (`template_verdict_facts`,
  `is_template_retired_by_verdicts`, `verdict_template_evidence`),
  `backend/template_recommendations.py` (`score_template_for_angle`,
  `template_structure_key`, `same_structure_template_pairs`,
  `diversify_template_recommendations`),
  `backend/routers/brands.py` (`recommend_templates`,
  `_verdict_rows_for_profile`),
  `backend/ai_spoken.py` (`certified_outcome_key_terms`,
  `hook_carries_certified_outcome`, `_generated_spoken_issues`),
  `backend/ai_service.py` (`generate_creative_plan`),
  `backend/routers/studio.py` (`_verdict_summary_payload`,
  `get_studio_project`, `generate_plan`, `generate_project_strategy`),
  `frontend/src/components/studio/SelectionPanels.jsx`
  (`RecommendationCard`), `frontend/src/pages/CreateVideo.jsx` (Review);
  tests in `backend/test_template_relevance.py`
  (`TestVerdictTemplateRanking`, `TestSameStructureTemplates`,
  `TestDiversifyRecommendations`), `backend/test_template_retire.py`,
  `backend/test_template_library_api.py` (`TestFeedbackInfluence`),
  `backend/test_template_outcomes.py`, `backend/test_hook_voice.py`
  (the certified-promise pins), `backend/test_studio_api.py`
  (`TestPlanGating`), `backend/test_video_verdicts.py`
  (`TestReviewVerdictSummary`).

## Context

Kasra walked the pipeline step by step (Nov 12 2026); with the angle
step strengthened (ADR 0125) and the goal step fitted to the certified
outcome (ADR 0126), he approved the template + plan step as one piece —
the standing rule for this walk: enhancements only add, the pipeline
improves together as one cohesive piece, and later-step contracts
(strategy, render) do not change. His explicit narrowing for templates:
the template itself gets no new fields and no new internal wiring —
only how templates are picked and shown changes.

Two gaps remained, one per step:

- **Template ranking still read the retired record.** ADR 0124 made
  whole-video verdicts the only signal that steers generation and
  removed per-element thumbs, but flagged the template scorer's inputs
  — `template_feedback_adjustment` (thumbs, rejections, behavior
  counts) and `template_outcome_adjustment` (posted clips, views) — as
  a deliberate keep pending a future decision. The reasoning that
  removed thumbs from steering applies unchanged to ranking: a posted
  result cannot be attributed to one element of the video, so neither
  a thumb on the template nor a post's metrics can say the template is
  what made a video work. Kasra has now made that decision. The
  picker also had the angle step's old flaw: two cards could present
  the same structure under two names, spending two of the three
  presented choices (ADR 0096) on one shape.
- **The plan's hook could promise something else.** The goal step fits
  the goal to the angle's certified outcome, and the plan brief carried
  that outcome as verified material — but nothing held the hook to it.
  A hook could open on a different promise entirely and ship, the
  hook-level form of the drift ADR 0123 fixed at the script's ending.
  Review also showed none of the verdict history the plan had just
  been steered by, even though the goal and template cards show theirs.

## Decision

- **Template ranking reads verdict bundles only.**
  `score_template_for_angle` takes parsed verdict rows
  ({"verdict", "bundle"}) instead of feedback events and outcome rows.
  `template_verdict_facts` tallies each template's worked / didn't-work
  verdicts from the template id frozen in each bundle's opening visual;
  worked weighs +1.0 (cap 3.0), didn't-work −1.5 (cap −4.5) — the
  magnitudes the template thumbs used, so a verdict means on the score
  what a thumb used to mean, no more. Retirement follows the same
  facts: two didn't-work verdicts and no worked one retire, one worked
  verdict revives (`is_template_retired_by_verdicts`). With no
  verdicts, the adjustment is zero and the order is exactly the base
  fit order. The record itself is untouched: `feedback_events`,
  snapshots, `template_feedback_adjustment` and
  `template_outcome_adjustment` still exist and still serve History,
  Analytics and the profile summary — ranking is the only reader that
  stopped.
- **The presented set prefers structurally distinct templates.**
  `template_structure_key` reads a template's shape — opening + middle
  structure (with the hook split), camera pacing, required assets,
  content-slot keys — and nothing of its identity (name, outcome,
  objective, category, audiences are fit, not structure).
  `same_structure_template_pairs` flags two rows equal on that key.
  `diversify_template_recommendations` keeps today's pool rule
  (non-retired while enough exist, else the whole ranked list) and
  today's count, but presents structurally distinct templates first;
  duplicates backfill in rank order, so the picker never shows fewer
  cards than it does today — it only stops spending two of three on
  one shape.
- **Template cards show their verdict evidence.** Each recommendation
  carries `verdict_evidence` — the founder's worked / didn't-work
  tally for that template from the same bundles, in the bucket shape
  the pickers already render — and the card shows it as
  "{counts} at this template" in the same evidence-line style as the
  goal cards' lines (ADR 0126). Display only; absent when a template
  has no verdicts.
- **The hook must carry the certified outcome's key terms.** When
  `angle_grounding` certifies an outcome for the plan, the plan prompt
  gains a HOOK PROMISE rule naming that outcome as the one promise the
  hook may make, and `_generated_spoken_issues` gains the matching
  deterministic check — the enforcement pattern ADR 0123 set for the
  script's ending. Key terms are the outcome's content words
  (normalized to the same lowercase word tokens the grounding
  near-match uses; ≥4 letters, minus stopwords), matched stem-aware
  via the continuity matcher; the hook carries the promise when at
  least half of them (rounded up) appear in it. Below the bar, the
  issue joins the plan's bounded editorial correction loop; a hook
  that still promises something else after the bounded attempts
  refuses the plan loudly rather than shipping. When no outcome
  certifies — older projects, uncertified angles — neither the rule
  nor the check exists and the plan behaves exactly as before. The
  craft retry re-checks with the same target, so it cannot trade the
  promise away either.
- **Review shows the profile's verdict summary.** Project payloads
  from the project read, the plan response and the strategy response
  (the one-pass flow's return) carry `verdict_summary`
  ({total, up, down}) — the same counts the Analytics headline uses,
  projected from the summary the prompts already computed — and the
  Review step renders it as an evidence line in the established style.
  Absent when the profile has no verdicts; display only, a pure read
  that generates nothing (ADR 0122 holds).

## Consequences

- One signal now teaches every step it legitimately can: verdict
  bundles steer the plan and strategy prompts (0124), fit the goals
  (0126), rank and evidence the templates, and headline Review. The
  per-element record is record everywhere — kept, shown in its own
  surfaces, and read by no ranking or generation path.
- A template with no finished-video verdicts ranks exactly as it did
  on fit alone, so a new app's picker is unchanged until the founder
  has judged real videos.
- The hook promise check can refuse a plan the old loop would have
  shipped. That is the intent — the refusal names the certified
  outcome and its missing key words, and regenerating is one click —
  but it makes plan generation stricter on certified projects, in
  exchange for the hook never quietly swapping the goal's promise.
- The plan prompt grows only when an outcome certifies: the HOOK
  PROMISE rule is ~410 characters for a typical outcome. No prompt
  ceiling moves: the plan prompt has no character ceiling, and the
  strategy prompt (ceiling 41,500) is byte-untouched by this change.
