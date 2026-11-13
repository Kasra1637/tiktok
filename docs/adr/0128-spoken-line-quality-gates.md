# 0128 — Spoken-line quality gates: articles, control words, restating endings

- **Status:** accepted
- **Date:** 2026-11-13
- **Anchors:** `backend/ai_spoken.py` (`_bare_place_hit`, `_ui_control_hit`,
  `_ending_restates_problem`, `_generated_spoken_issues`),
  `backend/test_hook_voice.py` (the Nov 13 section),
  `backend/ai_service.py` (`REWRITE_MAX_TOKENS`, `UnusableResponse`),
  `backend/routers/studio.py` (`_rewrite_failure_http`),
  `backend/test_spoken_line_rewrite.py`,
  `frontend/src/components/GenerationPanel.jsx` (`strategyMissing`),
  `frontend/scripts/check-render-smoke.cjs`. Extends ADR 0123; the
  one-working-button rule is ADR-less commit 51f56d8's, extended here.

## Context

Kasra rated a live generated pair — hook "On days at bus stop, emotions
come, words won't, I check in." at 4/10, script "I choose pleasant and
calm levels while waiting here… but I sit with it." at 3/10 — and
ordered the generation raised to 8–9. The pair carried three observable
defects that no deterministic check covered, each of a kind the prompt
already banned in words: a place that lost its article, the app's
slider vocabulary spoken aloud as "levels", and an ending that restated
the hook's problem instead of opening the discovery. The same
screenshot showed all three clearer-line rewrite buttons failing with
the one flat generic sentence, on the very lines the founder would have
used them to fix the pair.

## Decision

- **A place keeps its article.** `_generated_spoken_issues` flags a
  determiner-less place phrase for the witnessed noun class ("at bus
  stop", "at office", "at gym", "at store", "at park"). The class is
  deliberately narrow: "at home", "at work" and "at night" are
  idiomatic bare, and "at school" / "at church" are the standard US
  forms for the institution, so the two are left out rather than
  flagged — a general article rule would refuse natural speech to
  catch one broken shape. A determiner or possessive in front never
  matches.
- **The app is never worked out loud.** A control verb (choose, pick,
  set, select, adjust, tap) governing "levels" or "sliders" within a
  few words flags the line for the same bounded correction. The catch
  is the construction, never the noun: "my stress levels are high" and
  "energy levels crash by three" are a person describing their own
  state and never flag. This closes the generic-vocabulary leak the
  feature-name ban in the shared craft block could not see.
- **An ending that restates the problem is a hard issue.** Extending
  ADR 0123's question check: the script's last sentence flags when it
  shares one of the hook's image words AND is still phrased in
  problem-state words (a narrow set — "difficult", "stuck", "won't",
  "can't" — not the wider problem markers), AND opens nothing: no
  resolution marker, no new place or moment, and no naming of what is
  still unknown (the not-knowing forms ADR 0123 protects). This is the
  deterministic slice of "open the discovery" that word arithmetic can
  see. A restatement in entirely fresh problem words is beyond it and
  stays the prompt's business — the ADR records that limit rather than
  pretending the check is a theory of endings.
- **The rewrite path names its failures.** The reliability half landed
  as c56a5f2: the one-line rewrites' budget rises 400 → 1500
  (`REWRITE_MAX_TOKENS`) because the shipped model reasons at Max and
  bills thought against the same budget, so 400 (and the retry's 800)
  truncated replies into empty content; an empty-choices reply now
  costs one retryable attempt instead of raising on the spot;
  unusable replies get a typed `UnusableResponse`; and both rewrite
  endpoints map each failure class to its own founder sentence via
  `_rewrite_failure_http`. The flat generic line survives only for a
  failure no class claims, and that path logs the cause server-side
  and in the model-call ledger. No existing guard (room math, echo
  correction, refusal honesty) is weakened.
- **One working button, before a strategy exists too.** The generate
  control in Review is not rendered while no strategy exists for the
  project (`strategyMissing`), extending the rebuild gate of 51f56d8:
  the render follows the strategy, so the control cannot function
  before then and must not sit greyed beside the strategy panel's
  build control. The no-angle state is carved out — there the standing
  remedy is the angle pick itself — and a render in flight keeps its
  progress button.

All three spoken checks ride the existing bounded editorial loop (and
the craft retry's revalidation, and the advisory craft report's shared
issue list) exactly as ADR 0123's ending check does: clean drafts cost
no extra call, a draft that keeps failing refuses honestly, and the
correction prompt names each defect from the issue text — so the
shared craft block, and the strategy prompt ceiling measured against
it, are untouched.

## Alternatives rejected

- **Prompt-only strengthening.** The rule wordings already existed for
  all three defects; ADR 0123's lesson is that a prompt-only rule
  drifts and ships broken.
- **A general grammar/article check.** False positives on idiomatic
  bare places ("at home", "at work", "at school") would refuse the
  loose natural speech the PLAIN LOOSE WORDS rule exists to protect.
- **Banning "levels" outright.** The noun is natural body speech; only
  the control construction is UI language.
- **A semantic ending score.** Not deterministic, and scoring is
  advisory by design (ADR 0114); the observable slice belongs in the
  loop, the rest stays with the prompt and the craft report.
- **Keeping Generate greyed before a strategy exists.** The same
  two-competing-actions defect Kasra ruled on for the rebuild state.

## Consequences

- A plan whose model keeps dropping articles, working the controls
  out loud, or restating the problem at the ending now fails after the
  bounded loop with the honest refusal instead of reaching Review at
  3–4/10. The founder's rescue for a weak draw — the clearer-line
  buttons — works against a budget that fits the model's reasoning,
  and when it still fails it says which class failed and what to do.
- The gates run at generation only; founder edits are not gated.
- The no-strategy Review state now shows exactly one working action,
  the strategy build, until a strategy exists.
