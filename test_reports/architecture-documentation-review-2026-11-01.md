# Documentation and maintainability review — 2026-11-01

## Scope delivered

- Extracted existing deterministic template scoring/shared notes into
  `backend/template_recommendations.py` and angle normalization/grounding/lexical
  diversity into `backend/angle_policy.py`. Kept compatibility aliases in the
  HTTP/model adapters; added import-isolation and alias-identity contracts.
- Moved cohesive wizard selection UI into `studio/SelectionPanels.jsx` and
  revision/direction/progress UI into `studio/ReviewPanels.jsx`. Request/draft
  orchestration and project writes remain in `CreateVideo.jsx`.
- Made effect dependencies express the intended save/control lifecycle without
  suppressions. The final production build passes with CI warning enforcement.
- Replaced obsolete root/client README material. Added the ownership map,
  contributor/test matrix and operations/recovery/rollback runbook. Updated
  AGENTS and the ADR index, including four previously unindexed decisions.
  ADR 0079 records module ownership and its limits.

No model defaults, scoring weights, normalization limits, validation rules,
provider routing or paid-render behavior were intentionally changed. An AST
comparison of seven moved backend functions against HEAD was identical after
renaming the extracted entry points and their internal references.

## Verification on final code

| Check | Result |
|---|---|
| `python -m pytest backend/test_architecture.py backend/test_template_library.py backend/test_template_library_api.py backend/test_ai_json_calls.py -q` | 308 passed, 29 existing deprecation warnings, 13.40s, exit 0. Includes direct policy and HTTP/model integration coverage. |
| `node frontend/scripts/check-render-smoke.cjs` | All 390 checks passed, exit 0, final background run completed. |
| `SMOKE_ONLY='wizard' node frontend/scripts/check-render-smoke.cjs` | 11 selected checks passed after repair. |
| `SMOKE_ONLY='Real Video sequences History' node frontend/scripts/check-render-smoke.cjs` | 1 selected check passed independently; the same check passed in the final complete run. |
| `node frontend/scripts/check-imports.cjs` | 151 files scanned, no unresolved named imports. |
| `node frontend/scripts/check-frontend-logic.cjs` | Passed. |
| `CI=true yarn --cwd frontend build` | Compiled successfully, exit 0, 27.37s. No application lint warnings; Node emits the existing `fs.F_OK` deprecation notice. |
| Backend moved-function AST comparison | Seven functions matched their pre-extraction bodies after symbol renaming. A first comparison decoded Git output with Windows' default encoding and falsely differed on punctuation; explicit UTF-8 comparison passed without source changes. |
| Documentation local-link/ADR audit | Relative file/directory targets resolve; every numbered ADR is in the index. This is not an external-link or Markdown-anchor/browser audit. |
| `git diff --check` | Passed. |
| Local preview | Existing thread server at `http://127.0.0.1:3010` reused and re-registered after HTTP 200/HTML root readiness check. A redundant task-owned server was stopped. No visual/browser interaction review performed. |

### Failures observed, not hidden

The first complete smoke run failed (114/390), chiefly because the revised
save effect read `hasEdits` before declaration. Moving that derived value before
the effect removed the runtime crash. Focused mounts then exposed a missing
page-local `humanize` formatter still used outside the extracted panels; it
was restored. Existing mount assertions reproduce these regressions without
weakening checks. All 390 checks passed after both repairs.

An editor-sequencing assertion failed in that first run, outside the moved
owners. It passed independently and in the final full run without editor code
or assertion changes. This does not establish that its scheduling can never
be flaky. Earlier passing builds did not cover the later repairs; the strict
build was rerun on the final frontend code.

No broad backend/Jest suite was rerun for this focused extraction. No paid
provider generation, live Clerk/Turso/R2 verification, container build,
production deploy or TikTok moderation test was run. Scratch logs remain
untracked. Changes have not been committed or pushed by this task.

## Re-evaluation

Scores are subjective engineering assessments, not measured usability or
external acceptance benchmarks. A requested number is not evidence.

| Area | Current rating | Basis |
|---|---:|---|
| Documentation | **9/10, provisional** | Accurate current setup/workflow, linked ownership map, verification matrix, recovery and rollback, explicit privacy/durability caveats, complete ADR index. A clean-machine onboarding/restore exercise and ongoing drift checks are still missing. |
| Maintainability / architecture | **8/10** | Deterministic policies are independently importable/testable; cohesive panel owners are separate; aliases preserve callers; strict build is clean. Large orchestration owners and deployment safeguards remain unresolved, so a whole-app 9 is not justified. |

### What still separates architecture from 9

1. `server.py` remains roughly 9,800 lines with DB/bootstrap, HTTP and render
   lifecycle coordination. The extracted policy removes coupling but does not
   isolate those lifecycles.
2. `ai_service.py` remains roughly 5,600 lines; `CreateVideo.jsx` roughly 3,300;
   the browser editor and its preview loop remain substantial stateful owners.
3. Process-local coordination and embedded-replica boot sync are not a durable
   multi-instance job/consistency design.
4. Frontend gates are local; backend CI and deploy run independently. Neither
   a push nor a passing local build is a verified deployment.
5. The Docker runtime differs from CI's Python version; its manifest-hash step
   precedes the runtime asset copy, and dependency installation has a non-frozen
   fallback. These existing pipeline concerns are documented, not repaired.
6. Real browser-codec, authenticated cloud-storage/replica and provider-output
   evidence is not supplied by mocked checks.

A next architecture increment should choose one cohesive stateful lifecycle,
retain real entry-point regression coverage, and validate its cloud/process
assumptions. Do not scatter the remaining files merely to reduce line counts
or claim that documentation alone repairs operational risks.
