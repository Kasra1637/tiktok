# Architecture and ownership

Read [the product/setup overview](../README.md) first. This is a navigation
map of the shipped code, not a proposal for a new framework. Decisions and
exceptions live in [ADRs](adr/README.md).

## Terms

- **App Profile**: researched product facts, audience and claim boundaries;
  persisted in `brand_profiles` for historical schema compatibility.
- **Angle**: audience + problem + promise + recorded feature/outcome link.
- **Template**: an abstract opening/middle structure, not a copied performance
  or a proven engagement claim.
- **Studio project**: editable plan and strategy, with readiness/version gates.
- **Generation**: one submitted provider job and its playback, storage and
  provenance record. Not the project itself.
- **Editing document**: the browser-local Demo + CTA draft. It is not the
  server's reviewed script or a durable cloud backup.
- **Post kit**: generated caption/copy attached to a completed generation.

## Runtime and dependency direction

```text
React routes (App.js)
  -> CreateVideo: request coordination, save/version gates, navigation
     -> wizardDraft reducer: selections, saved project, pending Review edits
     -> useWizardTemplates: keyed recommendations/tailoring and progress
     -> studio/SelectionPanels: angle, goal, template comparison UI
     -> studio/ReviewPanels: direction dropdowns, plan-phase narration
     -> GenerationPanel / HookContinuityPanel: strategy and submit controls
  -> lib/api: session token + /api transport and durable-media URL selection
     -> server: authenticated HTTP, ownership, DB, project/render orchestration
        -> template_recommendations: deterministic fit + shared-note policy
        -> ai_service: OpenRouter requests and correction/retry orchestration
           -> angle_policy: normalization, recorded grounding, lexical diversity
        -> generation_planning / claim_safety / video_providers
        -> storage_service / pipeline / media_signing

DemoCtaEditor -> usePreviewLoop / overlays / scene drawing
              -> exportTikTok (timestamped browser encoding)
              -> editSession / draftStorage (device-local document)
```

The policy modules import vocabulary/tag/feedback helpers, **not** HTTP,
network clients, authentication or persistence. New callers should import
those policies directly. The old private names in `server` and `ai_service`
remain aliases for compatibility, not duplicate implementations. Contract
checks in [test_architecture.py](../backend/test_architecture.py) enforce
identity and import isolation.

There is no new repository interface, plugin system, global state library,
or generic service layer. A module should own a coherent responsibility,
not just forward calls into the old large file.

## Backend owners

Paths below are relative to [backend](../backend/).

| Owner | Responsibility / change here when… |
|---|---|
| [server.py](../backend/server.py) | Routes, ownership-scoped queries, schema bootstrap, project versions/readiness, render lifecycle. `_submit_generation` is the sole submit path; `_studio_identity_references` resolves the photograph. |
| [models.py](../backend/models.py) | Request schemas, editable-field lists and row serialization. |
| [auth.py](../backend/auth.py) | Clerk verification, local anonymous mode and hosted boot guard. |
| [template_recommendations.py](../backend/template_recommendations.py) | `score_template_for_angle(template, profile, angle, objective, feedback_events)` returns score/reasons/limitations/matches; `split_shared_notes(recs)` mutates the visible comparison list and returns its common notes. It neither fetches rows nor sorts HTTP results. |
| [angle_policy.py](../backend/angle_policy.py) | `normalize_content_angles`, `angle_grounding`, `duplicate_angle_pairs`. Grounding matches recorded facts conservatively; duplicates are lexical overlap, not semantic judgments. Correction model calls remain in the AI adapter. |
| [template_library.py](../backend/template_library.py), [recommendation_tags.py](../backend/recommendation_tags.py) | Curated vocabulary/seeds and normalization/tag matching. |
| [ai_service.py](../backend/ai_service.py) | Model request envelopes, JSON parsing/correction, research/planning/strategy and provider polling. `VIDEO_MODELS` owns model IDs/catalog data. |
| [video_providers.py](../backend/video_providers.py) | Capability enrichment, availability, allowlist/default, identity routing and ceilings. It derives records from the model catalog, so it is not independent of the AI adapter. |
| [generation_planning.py](../backend/generation_planning.py) | Single-pass prompt assembly/budgeting, camera directions and retry/error classification. Tight prompt fitting must preserve the reviewed spoken script. |
| [claim_safety.py](../backend/claim_safety.py) | Deterministic claim/risk checks. Do not replace them with model self-report. |
| [feedback.py](../backend/feedback.py) | Explicit/implicit feedback interpretation and recorded-performance ranking. Fit, momentum and performance are distinct signals. |
| [routers/post_kit.py](../backend/routers/post_kit.py), [routers/health.py](../backend/routers/health.py) | Endpoint-specific ownership with DB functions injected by the composition root. They must not import `server` back. |
| [pipeline.py](../backend/pipeline.py), [storage_service.py](../backend/storage_service.py), [media_signing.py](../backend/media_signing.py) | Local media operations, R2 durability and signed app URLs. Provider URLs are not durable browser playback links. |
| [overlays.py](../backend/overlays.py) | Server ffmpeg composition helpers; not the current Demo + CTA browser editor. |

## Plan → render → durable media

1. Read profile, angle and template under the authenticated user. Check profile
   approval and permitted assets; never invent a presenter when the photo is
   missing.
2. Generate/edit a plan. Server saves re-run deterministic checks; manual save
   and debounced Review autosave use the same path (ADR 0067).
3. Build a strategy for that plan/angle. Script/strategy versions and currentness
   prevent rendering an old strategy after edits. Readiness is a gate, not an
   alternate way around checks.
4. Submit once through `_submit_generation`, with provider-specific identity
   routing, duration and prompt ceiling. No model fallback, render chain or
   silent dialogue rewrite is introduced by this extraction.
5. Poll and finalize. Provider completion and durable save are different facts:
   a finished job can still carry `storage_error`.
6. Playback/download use the signed app route or durable saved media. Retry a
   storage copy before buying another render. See [operations](operations.md).

Request-local authorization must stay at HTTP/DB entry points. A pure policy
accepts data; it must not be mistaken for an authorization check.

## Frontend owners and state

| Owner | State / responsibility |
|---|---|
| [App.js](../frontend/src/App.js) | Real route inventory, protected shell, lazy page loading. |
| [CreateVideo.jsx](../frontend/src/pages/CreateVideo.jsx) | Three-step orchestration, URL navigation, request cancellation, autosave and plan/strategy handoffs. |
| [wizardDraft.js](../frontend/src/pages/wizardDraft.js) | Pure named transitions for selections, saved project and pending edits. Resume/reset/save adoption are atomic; background project updates retain edits. |
| [useWizardTemplates.js](../frontend/src/hooks/useWizardTemplates.js) | Keyed recommendation/tailoring requests, shared fit/error state, visible list and progress timer. Tailoring fires only when the page calls `runTailoring` — the goals-section Generate CTA or the header Regenerate — never on the goal pick. No project writes. |
| [SelectionPanels.jsx](../frontend/src/components/studio/SelectionPanels.jsx) | Angle selector, goal picker, template shape and recommendation cards. Receives callbacks/data; does not take over project writes. |
| [ReviewPanels.jsx](../frontend/src/components/studio/ReviewPanels.jsx) | Profile-matched direction dropdowns (per-dropdown refresh) and plan-phase narration. It does not own plan writes or render submission. |
| [GenerationPanel.jsx](../frontend/src/components/GenerationPanel.jsx), [HookContinuityPanel.jsx](../frontend/src/components/HookContinuityPanel.jsx) | Render preconditions and strategy building/review. Keep their server gates authoritative. |
| [GenerationHistory.jsx](../frontend/src/pages/GenerationHistory.jsx), [historyPolling.js](../frontend/src/pages/historyPolling.js), [historyRepair.js](../frontend/src/pages/historyRepair.js) | Confirmed row snapshots, bounded per-row polling and durable-save recovery. Stopped browser polling does not mean provider failure. |
| [OnboardingProvider.jsx](../frontend/src/components/onboarding/OnboardingProvider.jsx), [tours.js](../frontend/src/lib/onboarding/tours.js) | First-run readiness and manual help; deferred tours are not marked completed. |
| [DemoCtaEditor.jsx](../frontend/src/demoCta/DemoCtaEditor.jsx) | Editor controls and composition state. |
| [usePreviewLoop.js](../frontend/src/demoCta/usePreviewLoop.js), [exportTikTok.js](../frontend/src/demoCta/exportTikTok.js), [overlays.js](../frontend/src/demoCta/overlays.js) | Video-time rendering/transport, timestamped export and shared overlay drawing. No time-dependent randomness. |
| [editSession.js](../frontend/src/demoCta/editSession.js), [draftStorage.js](../frontend/src/demoCta/draftStorage.js) | Undo/redo and browser-local editing document, distinct from server autosave. |
| [api.js](../frontend/src/lib/api.js), [errorMessage.js](../frontend/src/lib/errorMessage.js) | Authenticated transport, durable media selection and actionable errors. |
| [index.css](../frontend/src/index.css) | Card spacing/type tokens; follow [design guidelines](../design_guidelines.md). |

Use effect dependencies to express the actual lifecycle. Refs may hold the
latest callback or snapshot when only project/options identity should reset a
control; they must not hide a needed synchronization. Declare derived values
before effects that read them. The mount harness catches runtime declaration
errors the production compiler may not report.

## Persistence and deployment constraints

- DB bootstrap/migrations still live in `server.init_db`, not an independent
  migration system. Back up before applying a new schema; an image rollback
  is not a database rollback.
- Turso uses an embedded replica with boot synchronization. Local in-flight
  sets guard one process only. Do not raise instance/worker counts without
  redesigning coordination and read freshness.
- Health reports the **active** backend after reads; configured credentials
  alone do not prove cloud durability. A configured Turso connection/sync failure
  reports `unavailable` and refuses local SQLite fallback. Pending replica sync
  can still lose writes if the local host disappears.
- The Docker image serves the CRA bundle and Python API together. Cloud Build
  deploys it to the existing Cloud Run service. Current CI and deployment run
  independently; CI is not a deploy dependency. See the
  [runbook](operations.md) before publishing anything.

## Remaining debt (not hidden by moving code)

The HTTP module, model adapter, wizard and browser editor remain large. The
current extraction creates testable owners for recommendation/angle policy and
selection/review presentation; it does **not** isolate database access, migrate
all HTTP routes, or turn the wizard into a small state machine. Source-scanning
smoke assertions also couple some tests to file layout. CRA dependency age,
cloud replica/native-extension coverage and real-device export verification
remain separate concerns.

When further decomposition is justified, choose one cohesive lifecycle, retain
its real entry-point regression tests, and record a decision before changing
its state owner. Smaller file counts or more modules alone are not success.
