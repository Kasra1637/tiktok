# AGENTS.md — HookForge (TikTok studio)

Dark-studio web app: FastAPI backend (`backend/`) + CRA frontend (`frontend/src/`).
One render path, single-pass video generation via OpenRouter.

## Commands (run from repo root)

- Backend tests: `python -m pytest backend/ -q` (media cases need ffmpeg/ffprobe
  on PATH; a missing ffmpeg is a setup failure, not a reason to skip).
- Frontend gates: `yarn --cwd frontend run check` (imports, logic, demo-cta draft,
  render smoke, tour targets — not Jest or the build). Focused smoke:
  `SMOKE_ONLY='wizard' node frontend/scripts/check-render-smoke.cjs` — a filter
  that selects zero checks verifies nothing.
- Frontend tests/build: `CI=true yarn --cwd frontend test --watchAll=false` /
  `yarn --cwd frontend build`.
- Match your harness's shell (Git Bash or PowerShell); preserve failure exit
  status when redirecting/piping. In PowerShell chain with `; if ($?) { ... }`.
- Local setup: `README.md`; ownership: `docs/architecture.md`; change/test
  matrix: `CONTRIBUTING.md`; incidents/deploy/rollback: `docs/operations.md`.

## Architecture (ownership map)

- `backend/server.py` — composition root (ADR 0111): includes the domain
  routers, re-exports their helpers, and owns the render lifecycle.
  `_submit_generation` is the ONLY render path; `_studio_identity_references`
  resolves the photo. Keeps the mutable DB config the tests rebind.
- `backend/db.py` + `backend/schema.py` — SQLite/Turso primitives and schema
  bootstrap; `db.py` reads config through a `_server` back-reference. Domain
  routers (`routers/brands.py`, `routers/studio.py`, `routers/assets.py`) own
  their endpoints and resolve test-patched `server` names at call time via
  `_cfg`; none may import `server` back (ADR 0111).
- `backend/ai_service.py` — all OpenRouter calls; `VIDEO_MODELS` is the model
  catalog; `generate_video` submits, `describe_provider_refusal` classifies.
- `backend/angle_policy.py` — pure normalization, source grounding and lexical
  diversity. `backend/template_recommendations.py` — pure fit/shared notes and
  Problem/Promise relevance. `backend/character_policy.py` — pure identity rule:
  the on-screen person is never given a gender, role or pronoun (ADR 0089).
  Same pure contract — no HTTP, AI, auth or persistence imports; `test_architecture.py`
  parametrizes the 5 it imports — for `backend/scene_consistency.py` (ADR 0092 /
  0103 / 0104: `reconcile_scene`; Movement ≥600 is advisory, Props stays a hard
  block), `backend/final_beat.py` (ADR 0093 / 0097: selfie strip; spoken words
  never rewritten), `backend/opening_move.py` (ADR 0090: validate / repair the
  opening move), `backend/angle_scene.py` (ADR 0084), `backend/face_crop.py`
  (YuNet crop + defocus, fallback to the original image), and
  `backend/hook_prompting.py` (extracted prompt builders, re-exported by
  `server.py`). `backend/observability.py` + `backend/routers/health.py` own
  `/api/metrics` — process-local counters, observability only, never a gate.
  Old adapter names are compatibility aliases.
- `backend/video_providers.py` — capability source of truth (limits, identity
  routing, prompt ceilings). Swapping providers is env config, not redesign.
- `backend/generation_planning.py` — prompt assembly + `is_recoverable_error`
  (retry policy). Prompt budget + sacred-script rule live here.
- `frontend/src/components/GenerationPanel.jsx` — the render panel; errors via
  `lib/errorMessage.js`. Card padding/spacing tokens live in `index.css`.
- `frontend/src/demoCta/` — canvas overlay system; `overlays.js` motion is a
  pure function of video time (export matches preview), faces come from
  `OVERLAY_FONTS` (vendored woff2 only). See ADR 0007.
- `frontend/src/pages/CreateVideo.jsx` — three-step wizard orchestration:
  App Profile → Audience & template → Review & submit. Selection UI lives in
  `components/studio/SelectionPanels.jsx` (the only `AngleSelector`); direction
  dropdowns and plan-phase narration in `ReviewPanels.jsx`. Project writes stay
  in the page. `pages/wizardDraft.js` owns coupled draft transitions;
  `hooks/useWizardTemplates.js` owns recommendation/tailoring state. Other
  steps navigate to the angle control, not a second selector.
  Review/editor siblings: `components/studio/HookLineEditor.jsx` (spoken-line editor),
  `pages/useWizardDirections.js` (stale-request guard), `components/SafetyPanel.jsx`
  (advisory per ADR 0081, never a gate), `pages/PendingSaveCard.jsx` (storage retry),
  `lib/vitals.js` (LCP/INP/CLS, window-exposed, no sink), `lib/recentDraft.js`
  (sidebar draft link), `pages/DemoCtaStudio.jsx` (starts blank ADR 0082).
- `frontend/src/pages/GenerationHistory.jsx` (+ `historyPolling.js`,
  `historyRepair.js`) — confirmed row snapshots, bounded per-row polling and
  durable-save recovery; a stopped browser check is not a provider failure.
  `components/PostKitSection.jsx` + `backend/routers/post_kit.py` own post
  kits; routers receive DB functions from `server` and never import it back.
- `backend/claim_safety.py` — deterministic claim checks, advisory only: no
  wording flag refuses a render (ADR 0081). `backend/feedback.py` — signal vs
  reason, posted-performance ranking (ADRs 0055/0070/0071).
- Persistence: Turso refuses local SQLite writes on a configured outage
  (ADR 0083). `backend/storage_service.py` + `backend/media_signing.py` own R2
  durability and signed playback — a provider URL is not a durable link, and a
  finished render can still carry `storage_error`.
- Other surfaces: `backend/auth.py` (Clerk; authz stays at HTTP/DB entry
  points), `frontend/src/upscale/` + `pages/VideoUpscaler.jsx`, and onboarding
  tours in `components/onboarding/` + `lib/onboarding/tours.js`.
  Schemas: `backend/models.py` owns `STUDIO_EDITABLE_FIELDS` and row
  serialization; `backend/template_library.py` + `backend/recommendation_tags.py`
  own curated vocab / tag matching. Operator tooling — NOT a render path:
  `backend/repair_failed_saves.py`, `backend/recovery_report.py`,
  `backend/live_sample.py`, `backend/mp4_samples.py`, and the Media
  offload (`backend/pipeline.py`, `backend/posters.py`,
  `backend/modal_worker.py`). `_submit_generation` stays the sole submit.
- Voice: `frontend/src/lib/listen.js` + `ListenDock` (mounted by `AppShell`) —
  browser `speechSynthesis` only (no text leaves the device), text built from
  the data model, never the DOM. See ADR 0088.

## Conventions

- Conventional commits, imperative, with a why-body on non-trivial changes.
- Commit or push only when requested — a push to `main` can deploy production.
- Spacing tokens live in `frontend/src/index.css` (`.surface`, `.inset-panel`);
  never add `p-*` to card JSX. Token changes update `design_guidelines.md`
  same-commit.
- Significant trade-offs add or supersede a record in `docs/adr/` same-commit
  (see `docs/adr/README.md` for the rules).
- Fail loudly, never silently: no fallback model, no invented lookalike, no
  generic take. A refusal must name the next step. A red button that cannot
  act must navigate to what's missing instead of dying silently.
- Claim reports are advisory: no wording flag refuses a render; banned wording
  is rewritten during plan/strategy and gates stay at submit time (ADR 0081).
- Review autosave is a validated server write; the Demo + CTA editing document
  is browser-local — never call browser storage a cloud backup.
- One logical change per commit. A behavior or default change is an explicit
  product decision named in the message, never bundled inside a fix; copy
  sync rides in its own commit so behavior stays reviewable and revertable.
- Red before green: a behavior fix ships with a regression check that fails
  without it. Suites staying green proves nothing changed, not that the new
  behavior works.
- Wizard subtitles carry `data-subtitle`, stay `text-sm` and 55–60 chars,
  enforced by the smoke suite. Loading indicators narrate fresh work and
  unmount on settle *and* error; lists arrive staggered, collapsing to
  instant under reduced motion.
- `memory/` is an empty stub, not a system. `memory/PRD.md` is the historical
  Unified Location spec (ADR 0090), implemented. `test_reports/` holds committed
  review evidence; scratch logs stay untracked.

## Before changing provider behavior

Read `docs/adr/README.md` first. One hundred and eleven decisions (0001–0111) now
exist; `docs/adr/README.md` index is the source of truth if this line drifts.
the submit-path canon is 0001–0006 (identity, temperature, single-pass, prompt
ceilings, Grok retirement, no silent fallback), joined by 0053 (generation
orbit), 0061 (429 is throttling), 0063–0064 (camera setups, conflicts refused
pre-render), 0083 (database durability), 0090 (Location is the single source
of truth; the hook opens on a visible move), 0092 (Render & result scene
fields agree — fix or block) and 0097 (a selfie never shows a phone, a reach
toward the lens, or a second free hand); 0099 stacks the wizard as one canvas.
Post kits follow 0100: 4 to 6 classified hashtags, never bait.
`provider_capabilities.py` compares
the catalog to OpenRouter's live listing at boot as a warning only — never a
gate. Frontend design constraints live in `design_guidelines.md`.
