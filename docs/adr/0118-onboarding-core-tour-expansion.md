# 0118 — Onboarding core tours expand to the journey's fork pages

- **Status:** accepted
- **Date:** 2026-11-11
- **Anchors:** `frontend/src/components/onboarding/OnboardingProvider.jsx`
  (`CORE_AUTO_OPEN_TOURS`, `useTourEligibility`); registrations in
  `frontend/src/demoCta/DemoCtaEditor.jsx`, `frontend/src/pages/Analytics.jsx`,
  `frontend/src/pages/AssetLibrary.jsx`; render checks prefixed
  `intent onboarding` in `frontend/scripts/check-render-smoke.cjs`.
  Extends 0077 (intent-aware core tours); seen-state semantics from
  `frontend/src/lib/onboarding/seenTours.js` are unchanged.

## Context

ADR 0077 limited auto-opening tours to App Profile, Create, and History —
the pages a first run must pass through in order. Three more pages are
forks in that same journey, and each is a place a founder can arrive
before understanding it: Demo + CTA (where the demo and close are added),
Analytics (where posted results join craft scores, ADR 0117), and Assets
(where the presenter photo lives). Their tours existed but were
replay-only, so the founders most likely to be confused by those pages —
first-timers landing on an empty editor, an empty library, or a results
page with nothing recorded — never saw them unless they already knew to
ask via "Show me around".

## Decision

- **The core auto-open set is now six:** brand, create, history,
  demo-cta, analytics, assets (`CORE_AUTO_OPEN_TOURS` in the provider).
- **Each new page registers conservative first-run eligibility** in the
  ADR 0077 pattern — never loading, never populated, never mid-work:
  - *Demo + CTA:* the editor is in its blank standalone state
    (ADR 0082) — no source clip loaded (`videoUrl`/`baseMedia` unset)
    and nothing in flight (not loading a source, not recording an
    export, not saving).
  - *Analytics:* the page has loaded without error and no clip has
    joined results yet — the performance summary's joined-clip count
    (`performance_summary.clips`, ADR 0117) is 0. That count is the
    precise "the founder has not recorded results yet" signal: results
    pasted is what moves it, not mere renders existing.
  - *Assets:* the library has loaded without error and the asset list
    is empty.
- **App Profile detail (`app-profile`) stays replay-only.** It is a
  per-record page a founder reaches deliberately from a chosen profile,
  and most of its steps are state-dependent (claim guardrails, a pending
  proposal, delete). Auto-opening there would interrupt a deliberate
  visit to explain a record the founder came to inspect.
- **Seen-on-open semantics are unchanged** (ADR 0077): a tour is marked
  seen when it opens, a deferred tour stays unseen, and "Show me around"
  remains the deliberate replay for every tour, core or not.

## Alternatives rejected

- **Auto-open every tour on first arrival.** That is the ambush ADR 0077
  removed: loading, populated, and mid-work states are exactly when an
  overlay costs the founder the task they came for.
- **Eligibility from page emptiness alone for Analytics** (no renders at
  all). A founder can have renders and even posted links while having
  recorded no results — the state the analytics tour most needs to
  explain. The joined-clip count names that state exactly; raw emptiness
  would close the tour off for the very people it is for.
- **Auto-open the App Profile detail tour with the rest.** Its steps are
  mostly optional/state-dependent, so a first-open would skip through
  half its content; the deliberate visit plus sidebar replay serves it
  better.

## Consequences

- First runs now meet help at all six working surfaces, each gated on a
  state the page itself owns and reports — no DOM guessing, per 0077.
- Eligibility conditions are per-page product decisions; changing what
  counts as first-run on one of these pages means changing its
  registration and this record's anchor, not the provider.
- The intent-onboarding render checks cover the expanded set: each new
  core tour opens on its eligible state, stays closed when ineligible,
  and does not reopen once seen.
