# Angle-conditioned video goals — final test report

Date: 2026-10-10. This report covers the angle-to-goal implementation and its final six-suggestion revision. No application deployment or publishing was performed.

## Delivered behavior

- The server facets response supplies six ranked existing goals for all 12 recognized angle kinds, plus viewer-outcome descriptions. The 13-goal vocabulary is unchanged.
- Create Video asks for an audience angle before showing six accessible pressed-state goal buttons. The “See all goals” disclosure and full-goal selector are removed from both picker locations.
- Changing angles reranks suggestions without replacing the chosen goal. A saved goal outside the six remains selected, with an explanation; choosing a suggestion replaces it.
- Unknown/legacy angle kinds receive six fallback goals from the existing vocabulary without restoring the removed controls.
- Review recovers missing angles/goals, starts a free plan only after both exist, and does not spin or request a plan while an angle is missing.
- Ranking and project writes receive the selected angle and goal, including the sixth suggestion. Stored choices survive reopening a draft.
- Creative plans now receive the actual angle label and user problem. Plan and strategy prompts preserve the angle's framing while advancing the goal, without generating the founder's later demo/CTA. The existing prompt-size ceiling is unchanged and passes.
- Render safety, photo requirements, stale-strategy protection, and the existing objective vocabulary are preserved.

## Final six-suggestion revision verification

- Focused backend suite: **117 passed**, 18 existing warnings; 6.10 seconds (`test_template_library.py` and `test_template_library_api.py`).
- Frontend application checks: **225 logic assertions and 144 render checks passed**; production build compiled successfully.
- Browser: six selectable cards, updated “Six suggestions” copy, no all-goals controls, and goal retention when switching angles. At 390px, the grid is one column and document width equals viewport width; no browser JavaScript errors were reported.
- Final artifact checks: all 12 angle kinds have six unique valid goals; obsolete controls and five-suggestion copy are absent. `git diff --check` passes.
- No source files changed after these checks. No separate TypeScript typecheck script exists.

## Full automated verification before the six-suggestion revision

The full-suite results below cover the earlier five-suggestion implementation. The affected backend/frontend checks and build were run again after the six-suggestion revision, as recorded above; the full backend suite was not repeated.

| Check | Result |
|---|---|
| `cd backend && python -m pytest -q -ra --junitxml=../.freebuff/goal-tests/backend-junit.xml` | **1,018 passed, 0 failed, 0 skipped**; 114.73 seconds; two configured xdist workers |
| `cd frontend && yarn run check` | **All pass**: named imports resolve across 106 source files, 225 pure-logic assertions, 144 render smoke checks |
| `cd frontend && yarn build` | **Compiled successfully**, no ESLint warnings; production JS/CSS emitted |
| `python -m compileall -q backend` | Pass |
| `git diff --check` | Pass |

The frontend has no separate Jest test files or TypeScript typecheck script; its maintained test gate is `yarn run check` plus the CRA production build. `yarn check` is Yarn Classic's built-in dependency check, not this project's script: it reports existing peer-version mismatches. Use `yarn run check` for the application gate. No dependencies or lockfile were changed.

Existing backend deprecation warnings remain (190 warnings, including FastAPI lifespan, multipart, datetime and pytest fixture deprecations). Frontend React `act` and jsdom confirmation warnings were repaired at their test interaction sources; the final application-check log has neither.

## Historical five-suggestion browser/HTTP verification

Used the running React development server at `http://127.0.0.1:3010/create` and real FastAPI routes at port 8010, backed by a **separate QA SQLite database** under `.freebuff/goal-tests`. Existing local/cloud data was untouched. AI angle/plan responses were deterministic fixtures, and tailored templates were preseeded; no provider calls or paid rendering occurred.

Passed in Chromium via agent-browser:

1. Fresh Create Video: exactly one control for each angle and no goal buttons before selection.
2. Problem-solution angle: exactly five goal buttons with viewer-outcome descriptions.
3. Choose Address User Problem, switch to feature-demonstration angle: five reranked suggestions; original goal retained in the expanded override.
4. Choose Compare Alternative override: real template-recommendation request receives the angle/goal; tailored template is displayed.
5. Enter Review: real project POST/PATCH/plan endpoints store the override and selected angle, generate plan version 1, and show the returned words.
6. Reopen with the project deep link: Compare Alternative remains selected and the override is expanded.
7. Keyboard focus + Enter chooses Explain App; pressed state becomes true and a visible two-pixel focus ring is present.
8. Desktop 1280px and mobile 390px viewports: five goals remain available, no horizontal document overflow.
9. Browser JavaScript error list is empty. Console contains only React development information and the expected explicit no-auth-mode warning.

Without a presenter photo, the ready endpoint correctly returns 400 with the photo requirement after the free plan is written. This is an expected safety gate, not a plan-generation failure.

## Evidence

The full backend log/JUnit and screenshots are historical evidence from the five-suggestion run, not screenshots of the final six-card UI. Frontend/build logs and the focused backend log below cover the final revision.

- [Final focused backend results](angle-goals-six-backend.log)
- [Historical full backend results](angle-goals-backend.log)
- [Backend JUnit results](angle-goals-backend-junit.xml)
- [Frontend results](angle-goals-frontend.log)
- [Production build results](angle-goals-build.log)
- [Desktop screenshot](angle-goals-desktop.png)
- [Mobile screenshot](angle-goals-mobile.png)

## Verification boundaries

Live AI creative quality, a paid video render, cloud SQLite behavior, and a complete signed-in Clerk flow were not exercised. Browser QA intentionally used anonymous local mode and fixture AI responses. The automated suite covers strategy prompt construction, generation orchestration, tenant isolation, media/overlay behavior and safety gates; it does not prove a live provider will return a satisfactory video.

The Preview tab is registered to the running local frontend. Its QA backend remains running alongside it for review.
