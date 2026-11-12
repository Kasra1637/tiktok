# 0117 — Performance feedback loop: manual dated snapshots, frozen craft score, prompt steering

- **Status:** accepted
- **Date:** 2026-11-11
- **Anchors:** `backend/schema.py` (`performance_snapshots`),
  `backend/routers/history.py` (`set_generation_performance_snapshot`,
  `generation_history` join), `backend/feedback.py`
  (`summarize_posted_performance`, `build_performance_section`),
  `backend/server.py` (`_submit_generation` stores `quality_report` at
  submit; reads prefer stored). Builds on 0114 (advisory craft score) and
  the profile-feedback prompt sections in `backend/ai_service.py`.

## Context

The craft score existed only as a live computation over a render's final
words: nothing stored it, so once a clip was posted there was no score left
to compare its results against. The founder could paste a TikTok link and a
view count into History, but views alone cannot say whether the clip held
anyone, and no reading ever reached generation. Craft dimensions were
therefore steered by intuition forever, however many clips were posted.

## Decision

- **Freeze the craft score at submit.** `_submit_generation` scores the
  plan's final words once and stores the report on the generation row
  (`quality_report`). Reads prefer the stored report and recompute only
  for rows that predate the column. The list endpoint reads stored only —
  the row's script is not selected there.
- **Manual dated snapshots.** The founder pastes results back per posted
  clip — 3-second retention %, average watch %, saves, shares, alongside
  the existing views — through `POST /generations/{id}/performance-snapshot`.
  Each save is a dated row in `performance_snapshots`; reads show the
  latest, earlier readings are kept. Snapshot views write through to the
  legacy `tiktok_views` fields so view-ranked surfaces stay truthful.
- **Join in Analytics.** The history list carries each clip's stored craft
  grade and latest snapshot, plus a `performance_summary` naming which
  craft dimensions' high scorers averaged better retention / average watch
  than the rest — computed only when at least 3 clips carry both halves.
- **Steering as a prompt section.** The same summary feeds plan and
  strategy prompt assembly through the existing profile-feedback path
  (`feedback_context`). Completion (average watch) and saves outweigh raw
  views; below 3 joined clips the section is empty and nothing steers.

## Alternatives rejected

- **Pull the numbers from TikTok automatically.** No connected TikTok
  account or API credential exists in the app, and manual paste matches
  how the link and views already arrive. Revisit if a TikTok integration
  lands; the snapshot table is the shape an automated pull would write.
- **One overwriting metrics row per clip.** A single row throws away the
  trajectory — a clip's day-2 and day-14 readings differ, and "latest
  wins" over dated rows keeps both the current answer and the history.
- **Steer via template outcome adjustment.** A parallel per-template
  bonus would double-count what the prompt section already teaches and
  would move template ranking for reasons the founder cannot read. The
  prompt section is visible, plain-language, and bounded by the 3-clip
  guard.

## Consequences

- Entry stays manual: the loop learns only as fast as the founder pastes.
  That is accepted — the guard makes thin data silent rather than wrong.
- Craft weights themselves are unchanged. Recalibrating them against
  outcomes waits for 50–100 posted clips with snapshots; below that the
  per-dimension averages are a reading aid, not a fitted model.
- The score is advisory as ever (ADR 0114): a stored report never blocks
  a render, and steering text never overrides hard validation.
