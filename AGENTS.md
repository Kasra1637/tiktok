# AGENTS.md — HookForge (TikTok studio)

Dark-studio web app: FastAPI backend (`backend/`) + CRA frontend (`frontend/src/`).
One render path, single-pass video generation via OpenRouter.

## Commands (run from repo root)

- Backend tests: `python -m pytest backend/ -q`
- Frontend checks: `node frontend/scripts/check-imports.cjs` (add
  `check-frontend-logic.cjs` and `check-render-smoke.cjs` when touching
  generation flows)
- Frontend tests/build: `yarn --cwd frontend test --watchAll=false` /
  `yarn --cwd frontend build`
- Tool shells use Bash (Git Bash on Windows); preserve failure exit status
  when redirecting/piping checks. For a manual PowerShell terminal use its
  environment syntax and `; if ($?) { ... }` rather than Bash assignments.
- Local setup: `README.md`; ownership: `docs/architecture.md`; change/test
  matrix: `CONTRIBUTING.md`; incidents/deploy/rollback: `docs/operations.md`.

## Architecture (ownership map)

- `backend/server.py` — HTTP layer; `_submit_generation` is the ONLY render
  path; `_studio_identity_references` resolves the photo.
- `backend/ai_service.py` — all OpenRouter calls; `VIDEO_MODELS` is the model
  catalog; `generate_video` submits, `describe_provider_refusal` classifies.
- `backend/angle_policy.py` — pure normalization, source grounding and lexical
  diversity. `backend/template_recommendations.py` — pure fit/shared notes.
  Neither may import HTTP, AI, auth or persistence adapters; guarded by
  `backend/test_architecture.py`. Old adapter names are compatibility aliases.
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
  `components/studio/SelectionPanels.jsx` (the only `AngleSelector`); revision
  inspection/direction inputs in `ReviewPanels.jsx`. Project writes stay in
  the page. `pages/wizardDraft.js` owns coupled draft transitions;
  `hooks/useWizardTemplates.js` owns recommendation/tailoring state. Other
  steps navigate to the angle control, not a second selector.

## Conventions

- Conventional commits, imperative, with a why-body on non-trivial changes.
- Spacing tokens live in `frontend/src/index.css` (`.surface`, `.inset-panel`);
  never add `p-*` to card JSX. Token changes update `design_guidelines.md`
  same-commit.
- Significant trade-offs add or supersede a record in `docs/adr/` same-commit
  (see `docs/adr/README.md` for the rules).
- Fail loudly, never silently: no fallback model, no invented lookalike, no
  generic take. A refusal must name the next step. A red button that cannot
  act must navigate to what's missing instead of dying silently.
- One logical change per commit. A behavior or default change is an explicit
  product decision named in the message, never bundled inside a fix; copy
  sync rides in its own commit so behavior stays reviewable and revertable.
- Red before green: a behavior fix ships with a regression check that fails
  without it. Suites staying green proves nothing changed, not that the new
  behavior works.
- Wizard subtitles carry `data-subtitle`, stay `text-xs` and 55–60 chars,
  enforced by the smoke suite. Loading indicators narrate fresh work and
  unmount on settle *and* error; lists arrive staggered, collapsing to
  instant under reduced motion.
- `memory/` is an empty stub, not a system. `test_reports/` holds committed
  review evidence; scratch logs stay untracked.

## Before changing provider behavior

Read `docs/adr/README.md` first — decisions 0001–0007 constrain the submit
path, identity routing, temperature handling, single-pass scope, prompt
ceilings, Grok retirement, and overlay fonts/motion. Frontend design
constraints live in `design_guidelines.md`.
