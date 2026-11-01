# HookForge frontend

React 19 + React Router, built through **CRACO / Create React App**.
[Root setup](../README.md#quick-start) covers the Python API; this directory is
not a standalone full-stack app. See [architecture](../docs/architecture.md),
[contributing](../CONTRIBUTING.md), and [design rules](../design_guidelines.md).

## Install and run

From the repository root:

```bash
yarn --cwd frontend install --frozen-lockfile
yarn --cwd frontend start
```

Use Yarn Classic **1.22.22** and the tracked [yarn.lock](yarn.lock), not npm or a
new lockfile. The root package is a workspace convenience, not the client
dependency manifest. Scripts invoke CRACO; do not bypass
[craco.config.js](craco.config.js) with raw react-scripts or eject.

The dev server normally uses `http://localhost:3000`. To select a free port in
Bash, set `PORT=3010` before the start command. Preserve other settings and do
not terminate an unrelated listener. `HOST=127.0.0.1 BROWSER=none` is useful for
an agent-owned loopback preview; these are environment variables, not Vite flags.

## Environment

Create/edit the ignored `frontend/.env` without overwriting existing values:

```dotenv
REACT_APP_BACKEND_URL=http://127.0.0.1:8000
# Optional for isolated local development:
# REACT_APP_CLERK_PUBLISHABLE_KEY=your-real-publishable-key
```

CRA embeds `REACT_APP_*` values at **build time**. Restart development or rebuild
after edits. Never place a server secret in a `REACT_APP_*` variable.

- Development needs the backend origin; otherwise `/api` hits CRA and fails.
- Production's combined image uses an empty backend URL for same-origin calls.
- Without a valid publishable key the client runs in no-auth mode and warns.
  This is only suitable when the isolated local backend also runs anonymously.
  Hosted deployments need matching Clerk frontend/backend configuration.

## Where to change behavior

| Area | Owner |
|---|---|
| Routes and protected lazy pages | [src/App.js](src/App.js) |
| Three-step wizard orchestration | [src/pages/CreateVideo.jsx](src/pages/CreateVideo.jsx) |
| Atomic draft/selection transitions | [src/pages/wizardDraft.js](src/pages/wizardDraft.js) |
| Recommendation/tailoring lifecycle | [src/hooks/useWizardTemplates.js](src/hooks/useWizardTemplates.js) |
| Angle/goal/template selection UI | [src/components/studio/SelectionPanels.jsx](src/components/studio/SelectionPanels.jsx) |
| Revision inspection/direction inputs | [src/components/studio/ReviewPanels.jsx](src/components/studio/ReviewPanels.jsx) |
| Render gate and strategy review | [GenerationPanel](src/components/GenerationPanel.jsx), [HookContinuityPanel](src/components/HookContinuityPanel.jsx) |
| Transport, errors, signed/durable media | [src/lib/api.js](src/lib/api.js), [src/lib/errorMessage.js](src/lib/errorMessage.js) |
| History snapshots/polling/repair | [GenerationHistory](src/pages/GenerationHistory.jsx), [historyPolling](src/pages/historyPolling.js), [historyRepair](src/pages/historyRepair.js) |
| Onboarding readiness/help | [OnboardingProvider](src/components/onboarding/OnboardingProvider.jsx), [tours](src/lib/onboarding/tours.js) |
| Browser composition/editor | [src/demoCta](src/demoCta/) |
| Surface spacing/type tokens | [src/index.css](src/index.css) |

The wizard is **App Profile → Audience & template → Review & submit**. Selection
panels receive data and callbacks; project writes stay with the page. Review
edits autosave through the server's claim-checked save path. The Demo + CTA
editor instead saves a browser-local editing document with undo/redo; it is not
a cloud backup. Its overlay drawing must be a pure function of video time so
preview and export agree.

## Checks

| Command (from root) | What it does |
|---|---|
| `yarn --cwd frontend check:imports` | Resolves named local imports. |
| `yarn --cwd frontend check:logic` | Checks pure helpers from shipped modules. |
| `yarn --cwd frontend check:draft` | Editing-document storage/history checks. |
| `yarn --cwd frontend check:render` | Mounts real modules with stub API/media infrastructure; includes gates, errors, copy budgets and flows. |
| `yarn --cwd frontend check:tours` | Audits tour target references against source. |
| `yarn --cwd frontend check` | All five checks above; not Jest or build. |
| `CI=true yarn --cwd frontend test --watchAll=false --runInBand` | Existing Jest suites without watch mode. Prefer an affected test path for a narrow change. |
| `CI=true yarn --cwd frontend build` | Production compilation with warnings treated as errors. |

`SMOKE_ONLY='wizard' node frontend/scripts/check-render-smoke.cjs` selects labels
for a focused diagnostic; verify the count is non-zero. Use the full generation
checks for structural changes across wizard owners. Do not remove assertions
when source moves; retarget their source inventory.

These frontend gates currently run **locally**, not in GitHub CI. Passing mocked
media checks does not prove real browser encoding, provider acceptance, identity
likeness, TikTok approval, or successful authentication. A frontend dev preview
alone does not verify an API session.
