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
- PowerShell here: chain with `; if ($?) { ... }`, never `&&` or `cd`
  (use `workdir`); prefer Read/Edit/Write over shell for files.

## Architecture (10-line map)

- `backend/server.py` — HTTP layer; `_submit_generation` is the ONLY render
  path; `_studio_identity_references` resolves the photo.
- `backend/ai_service.py` — all OpenRouter calls; `VIDEO_MODELS` is the model
  catalog; `generate_video` submits, `describe_provider_refusal` classifies.
- `backend/video_providers.py` — capability source of truth (limits, identity
  routing, prompt ceilings). Swapping providers is env config, not redesign.
- `backend/generation_planning.py` — prompt assembly + `is_recoverable_error`
  (retry policy). Prompt budget + sacred-script rule live here.
- `frontend/src/components/GenerationPanel.jsx` — the render panel; errors via
  `lib/errorMessage.js`. Card padding/spacing tokens live in `index.css`.

## Conventions

- Conventional commits, imperative, with a why-body on non-trivial changes.
- Spacing tokens live in `frontend/src/index.css` (`.surface`, `.inset-panel`);
  never add `p-*` to card JSX. Token changes update `design_guidelines.md`
  same-commit.
- Significant trade-offs add or supersede a record in `docs/adr/` same-commit
  (see `docs/adr/README.md` for the rules).
- Fail loudly, never silently: no fallback model, no invented lookalike, no
  generic take. A refusal must name the next step.
- `memory/` is an empty stub, not a system. `test_reports/` holds committed
  review evidence; scratch logs stay untracked.

## Before changing provider behavior

Read `docs/adr/README.md` first — decisions 0001–0005 constrain the submit
path, identity routing, temperature handling, single-pass scope, and prompt
ceilings. Frontend design constraints live in `design_guidelines.md`.
