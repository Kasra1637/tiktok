# 0124 — One verdict on the whole video replaces per-element feedback

- **Status:** accepted
- **Date:** 2026-11-12
- **Anchors:** `backend/schema.py` (`_migration_0003_video_verdicts`),
  `backend/feedback.py` (`build_verdict_bundle`,
  `summarize_video_verdicts`, `build_verdict_feedback_section`),
  `backend/routers/history.py` (`set_generation_video_verdict`),
  `backend/routers/studio.py` (`_verdict_feedback_for_profile`),
  `backend/ai_service.py` (`generate_creative_plan`,
  `generate_video_strategy`), `frontend/src/components/VideoVerdict.jsx`.
- **Supersedes:** ADR 0117's steering design (its record half stays).

## Context

Feedback learning was fragmented. The founder rated elements separately
— a thumbs-down on the plan that ordered a fresh plan, thumbs on the
goal, the template and the script, each teaching only the AI stage that
produced it — and, since ADR 0117, posted metrics joined to frozen
craft scores steered the plan and strategy prompts at 3+ clips.

Neither signal can support the lesson it teaches. When a posted video
does well or badly, neither the founder nor TikTok can say whether the
spoken words, the opening visual, the captions or the hashtags did it.
Per-element thumbs and craft-dimension correlations both assign credit
to one element of an outcome the whole video produced, so the loop was
learning false lessons with real confidence. Kasra's call (Nov 12
2026): simplify and merge everything into one comprehensive move — a
single thumbs up or down on the WHOLE finished video, and the loop
learns from that.

## Decision

- **One verdict per video.** A new `video_verdicts` table (migration
  step 3) holds one CURRENT verdict per generation per user: `up`
  ("this one worked") or `down` ("this one didn't"). Setting replaces;
  a null verdict clears. The only rating control in the app is the
  verdict control on the finished video's History card, beside the
  finished → posted journey line.
- **The bundle is frozen at verdict time.** Setting a verdict copies
  everything that went out with the render into the row's `bundle`
  JSON: the hook line and script from the render's project (the
  codebase's established source for a render's words), the caption,
  hashtags and cover text from the generation's own frozen post kit,
  the opening visual (poster asset path plus template id/version), the
  audio identity (the render's model plus the project's voice and
  sound directions), and context (angle id and kind, objective,
  duration, segment role). Later edits to the project or a regenerated
  post kit never mutate a stored bundle. A field the render genuinely
  lacks is stored absent, never invented; there is no `goal_id`
  anywhere in the schema — the project's objective is the goal — so
  the bundle carries no such key.
- **Steering is verdict bundles only.** The plan and strategy prompts
  carry exactly one feedback section, built from verdict bundles:
  worked bundles' words presented WITH their template and angle
  context to lean toward, didn't-work bundles' to steer away from —
  whole bundles, never element scores. Posted metrics no longer steer
  on their own, per-element thumbs no longer reach any generation
  stage (plan, strategy, angle and template generation alike), and the
  Analytics headline line reports the verdicts — counts, and what the
  worked bundles share — in place of the craft-correlation summary.
- **Silence below 3 verdicts.** The verdict section is empty until 3
  verdicts exist in total (the threshold pattern ADR 0117 used), and
  the section itself notes that patterns firm up around 5–7 verdicts,
  so the model treats it as a lean, not a law.
- **The record stays.** ADR 0117's other half is untouched: the craft
  score is still frozen on the generation at submit (a quality grade,
  not feedback), `performance_snapshots` still accumulate as the
  founder's dated results record in History and Analytics, and the
  stored `quality_report` still renders. The summarizers that joined
  scores to snapshots remain as that record's math; they simply have
  no prompt consumer any more. The winner rule is unchanged in shape —
  a worked verdict plus a posted link — and now reads the verdict.
- **The old controls come out.** The Review thumbs-down refine loop
  (with its three-refinement cap), the goal/template/script ratings in
  Create Video, the render panel's video thumbs, and History's video
  thumbs are removed, along with the `ComponentThumbs`/`ThumbPair`
  components. The `feedback_events` table, the `/feedback` endpoint
  and the behavior signals (adoptions, abandonments, regenerations)
  stay: they are the app's factual record, and the displays that read
  them (angle evidence, template fit) keep working from history.

## Consequences

- The strategy prompt's measured worst case grows: the counts-only
  feedback section (~450 rendered chars) is replaced by up to six
  frozen bundles at their truncation caps (~5,700 rendered chars).
  The budget ceiling in `test_ai_json_calls` moves by a measured
  5,250 to 41,500.
- Template recommendation ranking still reads historical thumbs and
  posted outcomes (`template_feedback_adjustment`,
  `template_outcome_adjustment`). That is a ranking of suggestions the
  founder sees, not generation steering, and no new thumbs can be cast
  anywhere — the adjustment now only ever reads the historical record.
  Recorded as a deliberate keep, flagged for a future decision.
- A deleted generation's verdict is deleted with it (it is a live
  teaching signal, not a record); its result snapshots still outlive
  the row, as before.
