# Contributing to HookForge

Start with [setup](README.md#quick-start), the [ownership map](docs/architecture.md),
[AGENTS.md](AGENTS.md), and the relevant [ADRs](docs/adr/README.md). Use the
existing Python/React stack and locked frontend dependencies.

## Change discipline

1. Check branch and working-tree state. This is a shared checkout: retain
   unrelated work and stage only your own hunks/files.
2. Locate the owner of the behavior. Pure recommendation and angle rules belong
   in their policy modules; HTTP authorization/queries stay at the entry point;
   model calls stay in the AI adapter. Do not add a second render path.
3. For a behavior fix, reproduce it with a focused failing check before changing
   production logic. For a move-only refactor, retain integration assertions and
   add a contract for the intended dependency direction.
4. Keep behavior/default changes separate from structural cleanup. No silent
   provider fallback, invented face, swallowed refusal, or retry of a permanent
   error to make a test pass.
5. Update the guide that names changed ownership/commands. Real trade-offs add
   an ADR; overturned decisions keep their history and a superseding record.
6. Run the smallest affected checks below and inspect their real exit statuses.
   A repaired failure requires a rerun of the affected check. Record unavailable
   tools, existing failures and unverified live behavior explicitly.

## Verification matrix

All commands run from the repository root in Bash. No command below requires
paid model calls. Backend tests must use their isolated fixtures, never a live
DB or the operator's credentials.

| Changed area | Focused verification |
|---|---|
| Recommendation fit / shared notes | `python -m pytest backend/test_architecture.py backend/test_template_library.py backend/test_template_library_api.py -q` |
| Angle grounding / normalization / AI envelopes | `python -m pytest backend/test_architecture.py backend/test_ai_json_calls.py -q` |
| Studio save/readiness/version flow | `python -m pytest backend/test_studio_api.py -q` plus the relevant frontend generation checks below |
| Render planning/provider routing | Relevant cases in `backend/test_generation.py`, `backend/test_generation_api.py` and `backend/test_influencer_workflow.py`; read ADRs 0001–0006 first |
| Claim rules | `python -m pytest backend/test_claim_safety.py -q` plus the route/plan cases that consume the changed rule |
| Any frontend import/module move | `node frontend/scripts/check-imports.cjs` |
| Frontend generation flow | Imports, `node frontend/scripts/check-frontend-logic.cjs`, and `node frontend/scripts/check-render-smoke.cjs` |
| Browser editing document | `node frontend/scripts/check-demo-cta-draft.cjs` plus the affected render-smoke checks |
| Tours and target names | `node frontend/scripts/audit_tour_targets.cjs` plus the affected onboarding checks |
| React test behavior | `CI=true yarn --cwd frontend test --watchAll=false --runInBand --runTestsByPath src/pages/historyPolling.test.js` (replace the test path with the affected existing test) |
| Production compilation / effect warnings | `CI=true yarn --cwd frontend build` |
| Database backend / health | `python -m pytest backend/test_database_backend.py backend/test_health_endpoint.py -q` |
| Backend-wide integration change | `python -m pytest backend/ -q` (requires ffmpeg/ffprobe) |
| Docs only | Verify commands against scripts/configuration and resolve changed relative links; do not describe an unrun command as tested |

Run the full local frontend gates when the change spans their owners:

```bash
yarn --cwd frontend check
```

This includes imports, pure logic, editing-document checks, render smoke and the
tour-target audit. It does **not** include Jest or the production build.

### Focused smoke checks

The existing harness supports case-sensitive label filtering:

```bash
SMOKE_ONLY='wizard' node frontend/scripts/check-render-smoke.cjs
SMOKE_ONLY='review checks focus' node frontend/scripts/check-render-smoke.cjs
```

Read the final count: a filter that selects zero checks verifies nothing.
A focused pass does not replace the full generation-flow gate for a structural
move across its owners. `SMOKE_TRACE=1` includes failure stacks. The harness
uses real React modules with stubbed API/media infrastructure, not real browser
codecs or a provider. Source-based assertions must follow moved code without
losing assertions or claiming that static text alone tests behavior.

### Backend execution

[backend/pytest.ini](backend/pytest.ini) fixes two xdist workers with loadscope;
keep its configured defaults. Media cases encode actual MP4s; missing ffmpeg
is a setup failure, not a reason to skip/weaken those tests. Pure policy tests
can import [template_recommendations.py](backend/template_recommendations.py)
or [angle_policy.py](backend/angle_policy.py) without importing the HTTP app.

### Capture failures without hiding them

```bash
node frontend/scripts/check-render-smoke.cjs > frontend/.local-smoke.log 2>&1
result=$?
tail -40 frontend/.local-smoke.log
exit "$result"
```

If piping to `tee`, enable Bash `set -o pipefail`. Scratch logs stay untracked;
put concise, dated evidence in [test_reports](test_reports/) when recording a
review. Distinguish current checks from historical evidence, and mocked checks
from live outcomes. Do not call a build warning-free just because warnings did
not fail a non-CI build.

## UI and state rules

- Shared spacing comes from CSS surface/inset tokens, not new card `p-*`
  utilities. Token changes update [design_guidelines.md](design_guidelines.md).
- Wizard subtitle text retains `data-subtitle`, `text-sm`, and the 55–60
  character budget checked by the smoke harness.
- Loading narration must end on both success and error; list staggering must
  collapse under reduced motion.
- Keep a single angle control. Other steps navigate to it rather than silently
  changing the chosen angle.
- Review autosave is a validated server write. The Demo + CTA editing document
  is a separate browser-local save. Do not conflate their ownership or claim
  that browser storage is a cloud backup.
- Prefer current-value refs only for intentional lifecycle boundaries; do not
  suppress effect-dependency warnings or add lint exclusions to hide bugs.

## Commits and publishing

Use imperative conventional commits with a why-body for non-trivial changes.
Keep one logical change per commit and independent copy sync in its own commit.
Do not commit secrets, media fixtures captured from personal sessions, scratch
logs, or unrelated modifications. Commit/push only when requested.

**A push to `main` can deploy production.** The backend CI workflow and deploy
workflow are independent; frontend gates are local. Review the
[operations runbook](docs/operations.md) before a push, rollback, credential
change, or migration. A passing test/push is not proof of a healthy deployment.
