# 0012 — The tailored minimum keeps qualifying pre-made picks visible

- **Status:** accepted
- **Date:** 2026-10-21
- **Anchors:** `frontend/src/pages/CreateVideo.jsx:1455` (`visibleRecommendations`);
  `frontend/scripts/check-render-smoke.cjs` ("below-bar pre-made templates stay
  hidden…", "a pre-made template meeting the tailored minimum appears…")

## Context

Once the per-objective custom set finished tailoring, the template step showed
only that set: every curated recommendation was membership-filtered out, no
matter its fit score. A pre-made template scoring 9/10 against the chosen
objective vanished the moment a custom 8/10 arrived — filtered out of the list
the founder was asked to choose from, with no waiting state and no rejection
mark to explain where it went.

## Decision

- The ready list is the tailored set **plus any curated row whose fit meets or
  exceeds the tailored minimum** — the lowest score among the tailored rows in
  the current ranked response, i.e. the minimum threshold this objective run
  set. Rank order is the server's, not tailored-first, so the Fit X/10 badges
  stay comparable down the list.
- Rows below the bar stay hidden: a weak generic pick must not crowd the
  custom set it lost to.
- The in-flight gate is unchanged: no cards (curated or custom) show until the
  custom set resolves or fails, so the top pick is never preselected from a
  list the custom set is about to join.

## Consequences

- **Gain:** a qualifying pre-made option can no longer be silently buried; the
  founder sees every option that met the run's own bar.
- **Cost:** the ready list can be longer than the custom set alone — the
  "Tailored for this app" label still marks which cards are custom.
- **Risk accepted:** if the tailored minimum is low, most curated rows
  qualify. That is the honest outcome: the bar is set by the run, not by us.

## Alternatives considered

- **Tailored-only list (status quo ante):** rejected — it hid high-scoring
  options with no trace, the exact failure this record fixes.
- **Fixed global cutoff (e.g. show all curated ≥ 7):** rejected — a magic
  number ignores the run: on a strong custom set 7 is clutter, on a weak one
  it hides contenders. The tailored minimum calibrates itself per objective.
- **Unfiltered ranked list:** rejected — keeps the weak generic tail the
  membership filter was (rightly) hiding.
