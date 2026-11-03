# Fix Failing Backend Pytest CI Check

HookForge's backend test suite is failing in the GitHub Actions "ci / backend pytest (push)" check, even though the same tests pass in the local preview environment. This plan diagnoses why pytest behaves differently when run by CI and restores a green check without changing any already-approved feature behavior (including the recently completed Location field unification).

## Who it's for
The project maintainer(s) who need every push to show a passing CI check before they trust a commit is safe to merge or deploy.

## Core features and experience
- Pull the actual failing CI run's logs/error output to see the real stack trace, not a guess.
- Identify the root cause. Likely candidates given the recent work: a path or environment assumption that only holds in the preview pod (e.g. the `_staging` upload directory rename), a dependency present in the pod but missing from `requirements.txt`, an environment variable the CI runner never receives, or a SQLite file/working-directory difference on a clean checkout.
- Apply the smallest fix that makes the suite behave the same way in CI as in preview — no unrelated refactors, no test deletions to "make it pass."
- Re-run the full backend pytest suite the way CI runs it (clean checkout, no leftover pod state) to confirm the fix holds, then confirm the GitHub check turns green on the next push.

## User flow
Maintainer pushes a commit → GitHub Actions triggers the "backend pytest" workflow → workflow installs dependencies, sets up the environment, runs pytest → all tests pass → check turns green.

## UI/UX feel
Not applicable. This is a backend/CI reliability fix with no visible UI change for end users.

## Implementation phases

**Phase 1 — MVP (built now):** Read the failing CI run's log, pinpoint the exact assertion/error causing it, apply the targeted fix, and verify the "backend pytest" check passes on the next push.

**Phase 2:** Add a way to catch "works locally, fails in CI" problems before pushing — e.g. a script that runs the backend suite in a clean environment mirroring CI's setup.

**Phase 3:** Harden the CI workflow itself — dependency caching, version pinning, and clearer failure output — so future failures are faster to diagnose.

## Assumptions
- The failure is an environment/configuration mismatch between the preview pod and the CI runner, not a genuine logic bug, since the handoff notes all backend tests passing locally.
- No test behavior or product feature changes; only CI-related configuration or path handling is adjusted if that turns out to be the cause.
- No new secret or API key is required for the fix. If the CI failure turns out to require a secret unavailable to GitHub Actions, that will be surfaced separately before any workflow change is made.
- "Push" refers to the GitHub Actions check that runs automatically after using the "Save to GitHub" flow.
