# 0114 - Advisory craft score for the spoken pair; performance stays separate

- **Status:** accepted
- **Date:** 2026-11-10
- **Anchors:** `backend/creative_quality.py` (`assess_spoken_quality`),
  `backend/routers/studio.py` (`_public_project`), `frontend/src/pages/CreateVideo.jsx`
  (Craft check), `backend/test_creative_quality.py`.

## Context

The spoken pair already has hard, deterministic checks: length ceilings,
promotion and AI-fluff markers, claim boundaries, screen-action narration and
the story/continuity flags in `ai_spoken.check_spoken_story`. Those checks are
the ship gate. They are also lexical and intentionally narrow: a line can pass
every one of them and still open as a diary, name a vague stand-in for the real
action, sound like written copy, or resolve the feeling before the founder's
demo has a question to answer.

The inverse is also true. `check_spoken_story` can report
`resolution_in_script: false` for a line a human reads as resolved because the
word that carries the resolution ("steadier", "spot") is not in its marker list.
Tightening that list would be whack-a-mole; using the story flags as a quality
score would mistake a defect detector for a judgment of craft.

The product also has a separate, audience-facing signal: posted views, thumbs,
edit/regeneration reasons and template/angle outcomes. Raw views are confounded
by account size, posting time, the founder's demo and the algorithm. A quality
score and a performance score answer different questions and must not be one
number.

## Decision

Add a pure, advisory 8-dimension craft score over the two spoken lines:

- `creative_quality.assess_spoken_quality(hook, script, ...)` returns a 0-100
  total, a letter/band, per-dimension points with evidence, and one next step
  per dimension. It reads the plan, the existing `spoken_check` and the app's
  name; it has no HTTP, AI, auth or persistence imports.
- The dimensions are hook stopping power, audience truth, clarity,
  concreteness, story arc, spoken naturalness, demo handoff and trust. They are
  weighted because the hook and the handoff do more work in a short feed than
  "clarity" does once the line is already understandable.
- The score is recomputed on read and exposed as `quality_report` on the
  project payload. Review shows the band and the two weakest next steps. It is
  never written to the project and never consulted by the submit path.
- The score is advisory only. No band refuses a render; the hard gates stay in
  `ai_spoken`, `claim_safety` and the render path (ADR 0081's principle).
- Performance remains a separate measurement. The first metrics to add are 3s
  retention, average watch/completion, save+share rate and follow/click rate,
  normalized against the account's own baseline and the same template/angle
  cohort. Views alone are reach evidence, not a verdict.

The score is a semantic layer beside the hard checks, not a replacement for
them. Deterministic checks stay authoritative for observable defects; the score
stays advisory for taste and craft.

## Alternatives rejected

- **One blended score (craft + views).** Confounded by account, demo quality,
  posting time and the algorithm; a high-view weak script would train the
  generator toward the wrong thing.
- **Gate the render on the score.** Refuses work over taste and would make the
  generator chase the rubric; ADR 0081 already establishes advisory checks.
- **Expand the story markers until this pair passes.** Lexical whack-a-mole:
  the next valid resolution will use another word, and a marker hit still does
  not prove the line is good.
- **A model judge on every render.** Cost, latency and self-preference; the
  same model family wrote the line. Use an offline judge with a different
  model for batch calibration, not the render path.
- **Persist the score.** A stored score drifts from the words the founder
  currently sees; recomputing from the saved plan keeps it honest and needs no
  migration.

## Consequences

- The score is a heuristic. It must be calibrated against blind human ratings
  and, over 50-100 posts, against normalized 3s retention/completion before it
  is treated as predictive. A high score that does not outperform a low score
  means the rubric is wrong or confounded, not that the audience is wrong.
- Review gets one more advisory card. It never blocks the Generate button and
  its copy says so. The full dimension report is available in the API for
  offline analysis without adding a second UI.
- The sample pair from the review (`Every week I look back...` + the garden
  script) scores 56/100 (C, competent but generic): the hook is a diary about
  the app's weekly review, the naturalness is low on the fronted modifier and
  written phrasing, and the handoff resolves the feeling. The conservative
  rewrite scores 91. The test suite asserts the bands and the relative
  improvement, not a frozen total, so the rubric can be tuned without turning
  the tests into a snapshot of its own arithmetic.
- `test_architecture.py` includes `creative_quality` in both pure-import
  checks, so the module cannot start importing the adapter or HTTP layer.
