# 0080 — Wizard draft changes use named transitions

Status: accepted

## Context

The creation wizard kept seven coupled values in independent React states:
profile/angle/template choices, goal, tone, saved project and unsaved edits.
Resuming a draft, switching profiles and accepting a plan each repeated a
sequence of setters. Recommendation rows, key, shared notes and errors also
updated independently inside the page alongside plan/save orchestration.

## Decision

Use React's existing `useReducer` with the pure `wizardDraftReducer` for the
coupled draft values. Name transitions after their meaning:

- `profile-selected` clears the old draft and creative choices together;
  `profile-loaded` retains URL-initialized choices during initial loading.
- `draft-resumed` adopts a saved project's selections and clears old edits.
- `angle-selected`, `template-selected` and `goal-selected` change current
  choices without pretending the server has saved them.
- `tone-edited` updates next-plan tone and pending Review tone together.
- `edit-field` merges against the latest reducer state, optionally removing
  a direction/camera edit when the saved/default value applies again.
- `project-received` keeps unsaved edits; `plan-accepted` clears them after
  the existing plan/save path settles.

Keep side effects outside the reducer: requests, single-flight refs, validation,
claim checks, readiness, autosave scheduling, URL navigation and UI focus.
Strategy/photo/render child callbacks send `project-received`; they do not
mutate a second project store.

Move recommendation requests, keyed tailoring, visible-list derivation and its
progress timer into `useWizardTemplates`. A ranked response stores key, rows,
shared notes and error together. Preserve existing request keys, current-request
guards, tailoring fallback and manual-pick protection. This extraction is not
a new retry/cache policy and does not claim full async-race elimination.

## Alternatives rejected

- A generic field-patch reducer: merely renames many setters and leaves the
  multi-value invariants scattered across callers.
- Redux, Zustand or a global context: no cross-page state requirement and no
  reason to add a dependency or a second persisted project source.
- One giant reducer including network timers and derived progress: obscures
  lifecycles and turns transient UI into durable domain state.
- Moving every remaining handler at once: broadens risk around paid calls,
  server readiness and autosave. Those lifecycles remain page-owned.

## Consequences

Related draft changes become atomic and directly testable; successive input
changes merge without a render-snapshot spread. The page has fewer independent
states but is still substantial. This decision refines ADR 0079's page ownership
without changing the three-step flow or transferring server writes into panels.
No backend API, model default, paid generation trigger, claim rule or render
gate changes.

Anchors: `frontend/src/pages/wizardDraft.js:wizardDraftReducer`,
`frontend/src/pages/wizardDraft.test.js`,
`frontend/src/hooks/useWizardTemplates.js:useWizardTemplates`,
`frontend/src/pages/CreateVideo.jsx:dispatchDraft`.
