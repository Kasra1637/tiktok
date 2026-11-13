# Architecture and ownership

Read [the product/setup overview](../README.md) first. This is a navigation
map of the shipped code, not a proposal for a new framework. Decisions and
exceptions live in [ADRs](adr/README.md).

## Terms

- **App Profile**: researched product facts and audience;
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
        -> generation_planning / angle_scene / video_providers
        -> character_policy / final_beat / opening_move / scene_consistency
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
| [server.py](../backend/server.py) | Composition root: includes the domain routers, re-exports their helpers, and owns the render lifecycle. `_submit_generation` is the sole submit path; `_studio_identity_references` resolves the photograph. Also keeps the mutable DB config the tests rebind (`DB_PATH`, `TURSO_*`, `_ACTIVE_BACKEND`, `_TURSO_BOOT_SYNC_DONE`). |
| [db.py](../backend/db.py), [schema.py](../backend/schema.py) | SQLite/Turso primitives and schema bootstrap/migrations, owned here (ADR 0111). `db.py` reads config through a `_server` back-reference; it and `schema.py` never import `server`. |
| [models.py](../backend/models.py) | Request schemas, editable-field lists and row serialization. |
| [auth.py](../backend/auth.py) | Clerk verification, local anonymous mode and hosted boot guard. |
| [template_recommendations.py](../backend/template_recommendations.py) | `score_template_for_angle(template, profile, angle, objective, feedback_events)` returns score/reasons/limitations/matches; `split_shared_notes(recs)` mutates the visible comparison list and returns its common notes. It neither fetches rows nor sorts HTTP results. |
| [angle_policy.py](../backend/angle_policy.py) | `normalize_content_angles`, `angle_grounding`, `duplicate_angle_pairs`. Grounding matches recorded facts conservatively; duplicates are lexical overlap, not semantic judgments. Correction model calls remain in the AI adapter. |
| [template_library.py](../backend/template_library.py), [recommendation_tags.py](../backend/recommendation_tags.py) | Curated vocabulary/seeds and normalization/tag matching. |
| [ai_service.py](../backend/ai_service.py) | Model request envelopes, JSON parsing/correction, research/planning/strategy and provider polling. `VIDEO_MODELS` owns model IDs/catalog data. Pure clusters live in `ai_spoken.py` (spoken budgets, trimming, story checks), `ai_strategy.py` (strategy normalization), `ai_text.py` (HTML→text) and `ai_media.py` (image data URIs) and are re-exported here (ADR 0112); the transport and chat-driven flows stay, so the patched `_chat_json`/temperature/config names keep resolving on this namespace. |
| [video_providers.py](../backend/video_providers.py) | Capability enrichment, availability, allowlist/default, identity routing and ceilings. It derives records from the model catalog, so it is not independent of the AI adapter. |
| [provider_capabilities.py](../backend/provider_capabilities.py) | Boot-time WARN-only comparison of the catalog against OpenRouter's `/v1/videos/models`; never a gate, never blocks boot. |
| [generation_planning.py](../backend/generation_planning.py) | Single-pass prompt assembly/budgeting, camera directions and retry/error classification. Tight prompt fitting must preserve the reviewed spoken script. |
| [angle_scene.py](../backend/angle_scene.py) | Where and when the video happens, owned by the selected angle; later steps conform, not re-decide (ADR 0084). `opening_shape`/`opening_staging` build the card's two opening lines from the First 3 Seconds Promise (ADR 0089). |
| [character_policy.py](../backend/character_policy.py) | The on-screen person is never given a gender, role or pronoun: `neutralize` rewrites, `identity_terms` proves a payload clean. Pure; applied to every video-facing field and again at prompt assembly (ADR 0089). |
| [hook_prompting.py](../backend/hook_prompting.py) | Hook-video prompt construction (motion styles, directives, templates); extracted from server.py, which re-exports it. |
| [final_beat.py](../backend/final_beat.py) | Selfie ending (ADR 0093/0097): one physical beat, no phone / reach / second free hand; fixed camera keeps the phone handoff. Spoken words never rewritten. |
| [opening_move.py](../backend/opening_move.py) | Opening-move check (ADR 0090): `validate_opening` / `repair` — guard refuses a static or speech-only hook before render. |
| [scene_consistency.py](../backend/scene_consistency.py) | Scene-field agreement (ADR 0092/0103/0104): `reconcile_scene` patches what is patchable; Movement ≥600 is advisory, Props stays a hard block. |
| [face_crop.py](../backend/face_crop.py) | YuNet face crop + defocus of surroundings; fallback returns the original image. Identity-only input to the video model. |
| [feedback.py](../backend/feedback.py) | Whole-video verdict bundles and the prompt section built from them, plus the posted-performance record math (dated snapshots, the craft score frozen at submit). The verdict bundle is the only steering signal; the record never steers (ADR 0124). |
| [routers/](../backend/routers) — `post_kit.py`, `health.py`, `media.py`, `brands.py`, `studio.py`, `assets.py`, `history.py` | Domain endpoint ownership (ADR 0111). `post_kit`/`health`/`media` take injected DB functions; `brands`/`studio`/`assets`/`history` resolve test-patched `server` names at call time via `_cfg`. None may import `server` back. |
| [observability.py](../backend/observability.py) | Structured request logs and process-local export counters at `/api/metrics`; observability only, never a gate. |
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
   routing, duration and prompt ceiling. Pre-submit guards run first: `opening_move`
   validate/repair (ADR 0090), `scene_consistency.reconcile_scene` (ADR 0092/0103/0104),
   `final_beat` selfie strip (ADR 0097) — a guard that cannot repair hard-blocks
   with 409 naming the field. No model fallback, render chain or
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
| [CreateVideo.jsx](../frontend/src/pages/CreateVideo.jsx) | Four-step orchestration (App Profile → Audience & template → Review & submit → Demo + CTA finishing step), URL navigation, request cancellation, autosave and plan/strategy handoffs. |
| [wizardDraft.js](../frontend/src/pages/wizardDraft.js) | Pure named transitions for selections, saved project and pending edits. Resume/reset/save adoption are atomic; background project updates retain edits. |
| [useWizardTemplates.js](../frontend/src/hooks/useWizardTemplates.js) | Keyed recommendation/tailoring requests, shared fit/error state, visible list and progress timer. Tailoring fires only when the page calls `runTailoring` — the goals-section Generate CTA or the header Regenerate — never on the goal pick. No project writes. |
| [useWizardAngleStep.js](../frontend/src/hooks/useWizardAngleStep.js) | Angle-step lifecycle: angles + verdict evidence, both click-to-view gates, live billed goals, regenerate handlers (ADR 0112). The page clears through its returned setters. |
| [SelectionPanels.jsx](../frontend/src/components/studio/SelectionPanels.jsx) | Angle selector, goal picker, template shape and recommendation cards. Receives callbacks/data; does not take over project writes. |
| [ReviewPanels.jsx](../frontend/src/components/studio/ReviewPanels.jsx) | Profile-matched direction dropdowns (per-dropdown refresh) and plan-phase narration. It does not own plan writes or render submission. |
| [HookLineEditor.jsx](../frontend/src/components/studio/HookLineEditor.jsx) | Review spoken-line editor under Review & submit. |
| [useWizardDirections.js](../frontend/src/pages/useWizardDirections.js) | Direction fetch with stale-request guard; picks reset on app switch. |
| [PendingSaveCard.jsx](../frontend/src/pages/PendingSaveCard.jsx) | Surfaces a durable-save retry card without claiming that a browser check is a render failure. |
| [GenerationPanel.jsx](../frontend/src/components/GenerationPanel.jsx), [HookContinuityPanel.jsx](../frontend/src/components/HookContinuityPanel.jsx) | Render preconditions and strategy building/review. Keep their server gates authoritative. |
| [GenerationHistory.jsx](../frontend/src/pages/GenerationHistory.jsx), [historyPolling.js](../frontend/src/pages/historyPolling.js), [historyRepair.js](../frontend/src/pages/historyRepair.js) | Confirmed row snapshots, bounded per-row polling and durable-save recovery. Stopped browser polling does not mean provider failure. |
| [OnboardingProvider.jsx](../frontend/src/components/onboarding/OnboardingProvider.jsx), [tours.js](../frontend/src/lib/onboarding/tours.js) | First-run readiness and manual help; deferred tours are not marked completed. |
| [DemoCtaEditor.jsx](../frontend/src/demoCta/DemoCtaEditor.jsx) | Editor controls and composition state. |
| [usePreviewLoop.js](../frontend/src/demoCta/usePreviewLoop.js), [exportTikTok.js](../frontend/src/demoCta/exportTikTok.js), [overlays.js](../frontend/src/demoCta/overlays.js) | Video-time rendering/transport, timestamped export and shared overlay drawing. No time-dependent randomness. |
| [editSession.js](../frontend/src/demoCta/editSession.js), [draftStorage.js](../frontend/src/demoCta/draftStorage.js) | Undo/redo and browser-local editing document, distinct from server autosave. |
| [api.js](../frontend/src/lib/api.js), [errorMessage.js](../frontend/src/lib/errorMessage.js) | Authenticated transport, durable media selection and actionable errors. |
| [Analytics.jsx](../frontend/src/pages/Analytics.jsx) | Manual views and own ratings, visualised; reads recorded outcomes only. |
| [VideoUpscaler.jsx](../frontend/src/pages/VideoUpscaler.jsx), [upscale/](../frontend/src/upscale) | Browser-side 1080p export; the clip's audio stays with the export (ADR 0086). |
| [DemoCtaStudio.jsx](../frontend/src/pages/DemoCtaStudio.jsx) | Standalone entry to the Demo + CTA editor; pinned workspaces resume their draft, otherwise it starts blank (ADR 0082). Its generation loader is also the wizard's finishing step content (ADR 0121). |
| [BrandSetup.jsx](../frontend/src/pages/BrandSetup.jsx), [AppProfileDetail.jsx](../frontend/src/pages/AppProfileDetail.jsx), [AssetLibrary.jsx](../frontend/src/pages/AssetLibrary.jsx) | App Profile research/approval and its asset library; feeds Create Video. |
| [PostKitSection.jsx](../frontend/src/components/PostKitSection.jsx) | Frozen post kit on a finished render; copy buttons and completed-only regenerate. |
| [components/auth/](../frontend/src/components/auth) | Clerk bridge/provider/controls; `ProtectedRoute` gates routes; anonymous local mode when auth is absent. |
| [listen.js](../frontend/src/lib/listen.js) (+ [ListenButton](../frontend/src/components/ListenButton.jsx), [ListenDock](../frontend/src/components/ListenDock.jsx)) | Local browser voice for text-heavy surfaces; reads the data model, never the DOM; one dock owns transport; hidden without `speechSynthesis` (ADR 0088). |
| [index.css](../frontend/src/index.css) | Card spacing/type tokens; follow [design guidelines](../design_guidelines.md). |

Use effect dependencies to express the actual lifecycle. Refs may hold the
latest callback or snapshot when only project/options identity should reset a
control; they must not hide a needed synchronization. Declare derived values
before effects that read them. The mount harness catches runtime declaration
errors the production compiler may not report.

## Persistence and deployment constraints

- Schema is versioned in `schema.apply_schema` (ADR 0120): the historical
  bootstrap is the recorded baseline in `schema_migrations`, and later
  changes append numbered steps the runner applies once. Back up before
  applying a new schema (operations runbook); an image rollback is not a
  database rollback.
- Post-render persistence runs through the `jobs` table with claim/lease/
  attempt semantics in `db.py`: poll enqueues and drains inline, and the
  startup sweep drains whatever a dead process left behind. Health reports
  a production process with no Turso configured as `unavailable` rather
  than a quiet local label, and unconfigured R2 as media that will not
  persist.
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
