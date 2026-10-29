# 0055 — Implicit behavior signals supplement explicit thumbs

- **Status:** accepted
- **Date:** 2026-10-29
- **Anchors:** `backend/feedback.py` (`EVENTS`, `BEHAVIOR_WEIGHTS`); `backend/server.py` (`_record_behavior`); smoke check "picking an angle files the passed-over angles as generated"

## Context

Thumbs are the founder's explicit verdict, but they are sparse: most
sessions cast none, while every session leaves behavior — what was picked,
what moved forward, what was dropped, what was shown and passed over. The
AI loop steered only on stated judgments plus two coarse triggers
(regenerate, download), so a template that was always shown and never
chosen looked identical to one never shown at all.

## Decision

- Three behavior events supplement (never replace) thumbs: `adopted` (picked
  AND moved forward — strongest positive, +3.0, outranks a thumb up),
  `abandoned` (picked or produced then dropped without proceeding — hard
  negative, −2.0), `generated` (shown but not picked — soft negative, −0.25).
- Like thumbs they name a component, carry no signal or reason, and attribute
  the same way (goal rows carry `objective=..;kind=..`). The video rating
  stays thumbs-only.
- Adoption and abandonment are server-side (plan/strategy/submit/project-update
  seams know what moved forward); shown-but-not-picked is frontend-only (only
  the UI knows what else was on screen). All three dedupe to one row per
  item per project.
- Prompt cost is guarded: behavior lines render only when nonzero, so an
  empty history adds zero characters against the ceilings ADR 0005 protects.

## Alternatives rejected

- **Replace thumbs with behavior.** Explicit verdicts carry intent behavior
  cannot prove; dropping them would trade a sparse truth for a dense guess.
- **Count impressions as rejections.** Being passed over once is not
  rejection; the soft weight (−0.25) lets repetition accumulate instead of
  punishing a single pass-over.

## Consequences

- The loop learns from every session, not just voting ones: repeated
  pass-overs sink a template's score, adoptions lift it, abandonments mark
  what founders try then drop.
- A feedback insert can never fail a render, plan, or update: `_record_behavior`
  logs loudly and returns instead of raising.
