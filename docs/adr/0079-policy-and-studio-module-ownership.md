# 0079 — Deterministic policy and studio panels have explicit owners

Status: accepted

## Context

Template fit/shared-note policy lived inside the HTTP/database module; angle
normalization, source grounding and diversity lived inside the model adapter.
Reading or testing those deterministic rules pulled in infrastructure. The
creation page also mixed selection/review presentation with project request,
version and save coordination. Existing setup docs described retired routes
and an older wizard, making those owners harder to find.

## Decision

Move the existing deterministic implementations into `template_recommendations`
and `angle_policy`. Their interfaces take ordinary data and return the same
shapes as before; shared-note extraction retains its documented in-place
mutation. They may use the existing template/tag/feedback vocabulary but may
not import HTTP, AI, auth, network or persistence adapters. Old private adapter
names remain aliases to the same functions for existing callers.

Move angle/goal/template selection UI into `studio/SelectionPanels.jsx` and
revision/direction/progress UI into `studio/ReviewPanels.jsx`. Keep project
writes, request cancellation, save scheduling and wizard step state in
`CreateVideo`. Revision inspection retains its existing latest-generation
read. No new global store, repository abstraction or extra render path.

Keep the existing intended effect lifecycles explicit: autosave depends on
edits, availability and stable project identity; saved directions are read
when project/options identity changes rather than overwriting current picks
after each save. Stable angle adoption belongs in callback dependencies.

Replace stale setup/client docs and add linked ownership, contribution and
operations guides. Document remaining deployment and architecture debt instead
of representing a source move as its repair.

## Alternatives rejected

- A directory-wide router/database rewrite: much broader risk than isolating
  deterministic policy, especially with schema helpers and render recovery
  still sharing process state.
- A generic policy/service framework: adds an interface without a second real
  adapter or a product requirement.
- One file per small UI helper: fragments a cohesive selection/review surface.
- Lint suppression or a reset-on-every-save dependency list: hides warnings or
  changes the control lifecycle rather than expressing it.

## Consequences and evidence anchors

- Pure rule tests can import the policy directly; integration tests still
  exercise the HTTP/model entry points. Import isolation and alias identity
  are enforced in `backend/test_architecture.py`.
- Weights, normalization limits, grounding rules, duplicate thresholds, retries,
  validation, model defaults and the sole render submit path are unchanged.
- Source-based subtitle/style smoke checks enumerate the moved owners and keep
  the same assertions. Runtime mounts remain necessary: compilation alone
  missed declaration-order and a missing formatter during this extraction.
- `server.py`, `ai_service.py`, `CreateVideo.jsx` and the editor remain large;
  these seams do not complete database or state-lifecycle decomposition.
- ADRs 0067 (Review autosave), 0073/0076 (grounding/diversity), 0074 (shared notes)
  and the provider decisions remain in force.

Anchors: `backend/template_recommendations.py:score_template_for_angle`,
`backend/angle_policy.py:normalize_content_angles`,
`frontend/src/components/studio/SelectionPanels.jsx:AngleSelector`,
`frontend/src/components/studio/ReviewPanels.jsx:ReviewRevisionsPanel`,
`frontend/src/pages/CreateVideo.jsx:saveEditsRef`,
`docs/architecture.md`, `docs/operations.md`, `CONTRIBUTING.md`.
