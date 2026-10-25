# 0031 — First-run checklist carries the founder across pages

Status: accepted

## Context

The sidebar lists six destinations with no order, and each spotlight tour
only explains the page already open. A new founder's problem is never "what
is this button" — it is "which page am I supposed to be on", and no
page-local tour answers that. The golden path is Create Video, then Demo +
CTA, then Export, and nothing said so.

## Decision

- A `FirstRunChecklist` card on Create Video (the app's landing route)
  names the three steps as doors: each links to its page and offers that
  page's existing tour via `startTour`. The card teaches the path; the
  tours keep teaching the pages.
- The card shows until the first Demo + CTA export saves to History
  (`markFirstRunDone` in `saveExport`) or the founder dismisses it — never
  again after either. Steps never tick themselves: the card cannot know a
  render finished, so it promises no progress it cannot see.
- Empty-state doors stay plain links, not tour triggers: History's empty
  state already links to Create, the Demo + CTA empty frame now links to
  History. A door is not a lesson.
- Tour plumbing hardens to match: `useOptionalOnboarding` lets provider-less
  mounts (the smoke suite) render links without crashing, and the overlay's
  `scrollIntoView` is optional-chained for DOMs that do not implement it.

Anchors: `frontend/src/components/onboarding/FirstRunChecklist.jsx`,
`frontend/src/lib/onboarding/firstRun.js`,
`frontend/src/components/onboarding/OnboardingProvider.jsx`
(`useOptionalOnboarding`), `frontend/src/demoCta/exportFlow.js`
(`markFirstRunDone`), `frontend/src/pages/CreateVideo.jsx` (placement),
`frontend/src/demoCta/DemoCtaEditor.jsx` (empty-frame History link).

## Alternatives rejected

- A fourth tour for the whole journey: tours are page-local spotlights;
  a cross-page tour would fight navigation instead of riding it.
- Auto-checking steps (e.g. "render done ✓"): derived state the card
  cannot observe honestly — a tick that lies is worse than no tick.
- Baking the path into the sidebar order: the sidebar is dependency order
  for daily use (App Profile first), not a first-run funnel.

## Consequences

Wayfinding success is measurable end-to-end: signup to first export saved.
The checklist is the instrument for that metric, and it deletes itself as
the reward. Unit tests pin the storage rule (done, dismissed, hostile
storage); the smoke suite pins the three doors, the tour opening, and both
retirement paths.
