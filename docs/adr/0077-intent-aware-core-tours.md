# 0077 — Core tours wait for explicit first-run readiness

Status: accepted

## Context

A route's first visit is not proof the founder needs an interruption. The tour audit already fails on missing targets; it was not part of the normal frontend check command.

## Decision

App Profile, Create, and History register explicit eligible state with the provider. Loading, populated workspaces, filtered History, and resumed drafts do not trigger automatic introductions. Other page tours remain available by manual replay. Eligibility is not seen-state: a deferred tour stays unseen until it actually opens. The existing short delay is only presentation timing after eligibility, not a guess at data readiness.

Core copy names one next action at a time. The existing keyboard, focus, dismissal, persisted seen state, and target audit remain; the audit joins the frontend check command. Existing draft storage is reused only to defer Create help, never as an authorization decision.

## Alternatives and consequences

Deleting all secondary tours would remove useful manual help. DOM polling for account state would couple eligibility to incidental markup. Automatic tours during loading would interrupt the very task they explain. Experienced founders can always use Show me around.

Anchors: `frontend/src/components/onboarding/OnboardingProvider.jsx:useTourEligibility`; page calls in BrandSetup, CreateVideo and GenerationHistory; render checks prefixed `intent onboarding`.
