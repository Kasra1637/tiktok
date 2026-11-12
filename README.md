# HookForge — short-form app video studio

HookForge helps app founders research their product, choose an audience angle
and hook template, review a script, and generate one short presenter video.
The Demo + CTA editor adds the founder's own footage, product presentation,
and optional text overlays before a manual download and post.

**Nothing posts automatically.** There is no platform-posting or scheduling
workflow. A claim-check pass does not guarantee video-provider acceptance,
TikTok approval, engagement, or medical accuracy.

## Start here

| Goal | Guide |
|---|---|
| Run locally | [Quick start](#quick-start) |
| Find the owner of a feature or rule | [Architecture](docs/architecture.md) |
| Make and verify a change | [Contributor guide](CONTRIBUTING.md) |
| Diagnose auth, storage, rendering, or deployment | [Operations runbook](docs/operations.md) |
| Understand a product or architecture trade-off | [Decision records](docs/adr/README.md) |
| Change layout, spacing, typography, or motion | [Design guidelines](design_guidelines.md) |
| Work only on the client | [Frontend guide](frontend/README.md) |

## Quick start

Run commands from the repository root in Bash (Git Bash on Windows).
For PowerShell, use its environment/activation syntax rather than pasting Bash
assignments. Keep private values in ignored environment files, not in commands
that will be shared or committed.

### Prerequisites

- Python **3.12**, matching [backend CI](.github/workflows/ci.yml). The current
  [Dockerfile](Dockerfile) still uses Python 3.11; that difference is not a
  statement of equal test coverage.
- Node **20+** and **Yarn Classic 1.22.22**, as declared by
  [frontend/package.json](frontend/package.json). Use the tracked
  [frontend/yarn.lock](frontend/yarn.lock); do not replace it with npm output.
- **ffmpeg and ffprobe on PATH** for media processing and the tests that encode
  real clips. A text-only check is not a substitute for those media tests.

### Backend

```bash
python -m venv backend/.venv
# macOS/Linux:
source backend/.venv/bin/activate
# Git Bash on Windows, instead:
# source backend/.venv/Scripts/activate
python -m pip install -r backend/requirements.txt
```

Copy [backend/.env.example](backend/.env.example) to `backend/.env` only if a
private environment file does not already exist, then fill the required keys.
Start the API with the environment loaded **before module imports**:

```bash
python -m uvicorn server:app --app-dir backend --env-file backend/.env --host 127.0.0.1 --port 8000 --reload
```

The `--env-file` is important: auth, AI, and storage adapters capture settings
at import time, before the late `load_dotenv` in the HTTP module. An existing
shell variable takes precedence over an env-file value. Restart after changing
backend settings.

- API description: `http://127.0.0.1:8000/docs`
- Basic response: `http://127.0.0.1:8000/api/`
- Storage/inventory diagnostic: `GET /api/health` (requires sign-in when auth
  is configured; inspect `database`, `durable`, and `your_rows`, not just HTTP 200).

Startup runs idempotent table creation, column additions and template seeding.
Without Turso settings, local data lives at `backend/storage/hookforge.db`.
Do not point a development process or test fixture at production data.

### Frontend (another terminal)

```bash
yarn --cwd frontend install --frozen-lockfile
```

Create or edit `frontend/.env` without replacing existing settings:

```dotenv
REACT_APP_BACKEND_URL=http://127.0.0.1:8000
# Optional locally; must match backend Clerk configuration when enabled:
# REACT_APP_CLERK_PUBLISHABLE_KEY=your-real-publishable-key
```

```bash
yarn --cwd frontend start
```

The development app normally serves at `http://localhost:3000`. If that port
is occupied, use a free `PORT`; do not stop another project's listener.
`REACT_APP_*` values are build-time inputs: restart the dev server or rebuild
the bundle after changing them. The production bundle uses an empty backend
URL for same-origin API calls.

### Required versus optional configuration

[backend/.env.example](backend/.env.example) lists the adapter settings.

| Setting | Requirement / behavior |
|---|---|
| `OPENROUTER_API_KEY` | Needed for AI research, angles, plans, strategies, and renders; non-AI screens can run without it. |
| `CLERK_JWKS_URL` + client publishable key | Optional only for isolated local development. Without backend auth all callers share `anonymous`. Set `ENVIRONMENT=production` on hosted processes so the boot guard refuses missing auth outside Render too. |
| `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN` | Cloud database. Otherwise local SQLite. If configured Turso cannot connect or sync, database requests fail with `unavailable` rather than writing to a local fallback. Read the active backend from health. |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` | Durable media storage. Without it, clips depend on the host's local disk. `R2_PUBLIC_URL` is optional; private buckets can use signed reads. |
| `MEDIA_URL_SECRET` | Stable signing key for media URLs. Without one, the development process uses a temporary key and links do not survive restart. |
| `PUBLIC_BASE_URL` | Public origin where a provider must retrieve a reference. Loopback is not reachable by an external provider. |
| `CORS_ORIGINS` | Explicit comma-separated browser origins for split-origin setups. Empty defaults to `*`; it does not disable cross-origin requests. |
| `VIDEO_MODEL_DEFAULT`, `VIDEO_MODEL_ALLOWLIST` | Select or restrict existing video providers; not permission for silent model substitution. |
| `AI_TEXT_MODEL`, `AI_VISION_MODEL`, `AI_ANGLE_MODEL` | Override model slugs. Unset angle model uses the text model; inspect current defaults in [ai_service.py](backend/ai_service.py). |
| `MODAL_FRAME_EXTRACTOR_URL`, `MODAL_SHARED_SECRET` | Optional frame-extraction offload for source-video utilities, not required for the primary studio path. |

## Current workflow

The creation wizard has **three steps**, not five:

1. **App Profile** — research or select a profile, review its facts,
   and approve it. Profile editing/research lives at `/brand`.
2. **Audience & template** — choose an angle and goal, compare templates, and
   attach the presenter's photograph. There is one angle selector.
3. **Review & submit** — generate and edit the text plan, inspect the craft
   grade, build/review the matching strategy, and explicitly submit a video.

Rendering remains gated on approved profile, valid angle/template/photograph,
saved/current plan and strategy, and project readiness. Review
edits autosave through the server's normal validation path. A variation is a
**draft**, not a paid render.

One provider job produces the hook and middle. There is no automatic extension
chain. Provider limits, identity routing and prompt budgets come from
[video_providers.py](backend/video_providers.py) and
[generation_planning.py](backend/generation_planning.py). A provider refusal
must remain visible with an actionable next step.

After generation:

- `/history` shows render state, durable playback/download, storage recovery,
  post copy, and manually entered TikTok links, views and verdicts.
- `/demo-cta` or `/demo-cta/:generationId` opens the **browser-side** editor.
  Its editing document is saved on that browser/device, not as the server's
  claim-checked plan. Preview/export share time-based drawing logic.
- `/analytics` summarizes recorded results; it does not retrieve TikTok stats
  automatically or report provider spend.
- `/upscale` is a separate browser-side video tool.

The public `/` is a landing page; sign-in/sign-up, features, terms and privacy
also exist. Current route ownership is in [App.js](frontend/src/App.js).
Old research/media helpers in the backend do not imply a current Research,
Discover, face-swap, or legacy-history page.

## Verification

Choose checks by the changed area; see [CONTRIBUTING.md](CONTRIBUTING.md) for
focused commands and their limits.

```bash
python -m pytest backend/ -q
node frontend/scripts/check-imports.cjs
node frontend/scripts/check-frontend-logic.cjs
node frontend/scripts/check-render-smoke.cjs
CI=true yarn --cwd frontend build
```

Backend pytest uses the repository's fixed two-worker configuration. The full
suite needs ffmpeg. The render-smoke harness mounts real React modules with
stubbed infrastructure; it is not a browser or a live-provider acceptance test.
Frontend checks are currently **local gates**, not a GitHub CI job.

Paid live probes exist, but do not run them as ordinary unit verification:
[verify_chat_model.py](backend/verify_chat_model.py) makes real model calls and
[verify_live_renders.py](backend/verify_live_renders.py) submits real videos.
Use a funded key and explicit authorization, then inspect the clips yourself.
Historical results are recorded in [test_reports](test_reports/); they are not
proof that today's production revision or provider is working.

## Known limits

- HTTP/database/render orchestration still concentrates in
  [server.py](backend/server.py); model workflows in
  [ai_service.py](backend/ai_service.py); wizard request/draft state in
  [CreateVideo.jsx](frontend/src/pages/CreateVideo.jsx). The extracted policy
  and panel modules improve ownership but do not complete their decomposition.
- Local SQLite and local media are not durable on ephemeral hosting. A configured
  Turso outage now refuses database requests instead of falling back locally;
  unsynchronized replica writes still need recovery before an instance disappears.
- Native libsql cloud behavior is not covered by the Windows SQLite test path.
- Export depends on browser codec/device support; a mocked export does not
  establish real-device compatibility or visual identity quality.
- No wording rule can guarantee a provider render or platform moderation outcome.

For deployment, rollback and recovery constraints, use the
[operations runbook](docs/operations.md), not old chat notes or a local service
snapshot.
