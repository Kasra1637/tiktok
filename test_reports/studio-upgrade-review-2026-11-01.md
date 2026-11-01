# Studio upgrade review — 2026-11-01

## Delivered scope

- Wizard review: place claim findings beside the script, keep supporting evidence collapsed, select flagged editable wording, and confirm before regenerating a plan. Findings outside editable text direct the founder to strategy repair. No safety rule is removed and approved dialogue is not silently rewritten.
- Angles / plans / strategy: detect conservative lexical duplicates across problem + promise pairs, allow one correction request, reject persistent duplicates or a depleted correction, and carry recorded feature/outcome links into planning briefs. This is not semantic quality scoring.
- Onboarding: automatic core tours require explicit first-run readiness; loading, existing work and resumed drafts defer introductions without marking them seen. Manual replay remains. Core tour copy is synchronized separately. The target audit joins the normal frontend check command.
- History: isolate failed polling rows, prevent overlapping requests per row, expose active/paused/error check states, and provide a direct shortcut to existing results inputs. Browser polling stopping does not declare a provider render failed.

Decisions: ADRs 0075–0078. ADR 0062 is partially superseded.

## Verification

| Check | Result |
|---|---|
| `python -m pytest backend/test_ai_json_calls.py -q` | 121 passed; deprecation warnings |
| `CI=true yarn --cwd frontend test --watchAll=false --runInBand` | 33 suites, 239 tests passed; expected missing-Clerk setup warnings in the local test environment |
| `node frontend/scripts/check-render-smoke.cjs` | 390 checks passed, including integrated claim selection/cancellation, tour eligibility/replay, and compact History results focus |
| `node frontend/scripts/check-imports.cjs` | 149 files scanned; no unresolved named imports |
| `node frontend/scripts/check-frontend-logic.cjs` | Passed |
| `node frontend/scripts/audit_tour_targets.cjs` | All tour targets exist |
| `yarn --cwd frontend build` | Passed with five existing hook-dependency warnings in CreateVideo |
| `CI=true yarn --cwd frontend build` | Failed because CI treats those five warnings as errors; the affected effects/callbacks and dependency lists exist in the pre-change commit |
| `git diff --check` | Passed |
| Local dev preview | Compiled with the same warnings; HTTP 200 with HTML root at `http://127.0.0.1:3010`; registered in Preview tab |
| `python -m pytest backend/ -q` | 1,320 passed, 200 deprecation warnings, exit status 0; 154.51 seconds. The initial synchronous attempt timed out; this result comes from the completed background run. |

The strict-build limitation was not hidden by weakening lint rules, adding suppressions, or changing the project's check scripts. No unrelated hook refactor was bundled into this upgrade.

## Re-evaluation

These are subjective engineering/product assessments from code review and automated behavior checks, not measured usability or output-quality benchmark scores.

| Area | Provisional rating | Basis and remaining gap |
|---|---:|---|
| Create wizard | 8/10 | Claim findings now lead directly to repair; dense state ownership and existing hook warnings remain. |
| Script / angles / strategy | 7.5/10 | Better argument diversity and recorded grounding, but no representative live-model quality benchmark was run. |
| Onboarding / tours | 8/10 | Readiness-aware introductions and preserved replay; real first-time-user testing remains. |
| History / generations | 8/10 | Visible bounded checks, per-row error isolation and direct results access; live-provider recovery still needs end-to-end evidence. |

## Boundaries

No paid provider render, live authentication flow, TikTok moderation test, or browser visual review was performed. The preview is frontend-only evidence, not a verified backend session. An app claim-check pass is neither video-provider approval nor TikTok approval; no change can guarantee a video will never be refused.

Scratch logs and browser fixtures remain untracked and are not part of the commits. A push triggers the repository's existing deployment workflow, but push success alone does not establish that deployment completed or that production was verified.
