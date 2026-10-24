# Per-segment look + Second clip group — verification

Date: 2026-10-24. Scope: review fixes 1, 2, 4 (density, per-segment
background/animation/scene, upload gating). Zoom/phone geometry intentionally
stays shared (ADR 0029).

## What changed

- `frontend/src/demoCta/DemoCtaEditor.jsx` — new gated `Second clip` group
  (`demo-cta-second`, only when a base exists); shared
  `StylePicker`/`EnvGrid`/`BackgroundPicker`/`AnimationPicker` components;
  base controls keep their exact testids.
- `frontend/src/demoCta/usePreviewLoop.js` — painter resolves `lookBg` /
  `lookAnim` / `lookEnv` per segment; new settings in the paint deps.
- `frontend/src/demoCta/exportFlow.js` — preloads both hand scenes.
- `frontend/scripts/check-render-smoke.cjs` — section key `v4`; sequence test
  pins gating, per-segment backdrop/motion picks, and the added clip's scene
  id reaching the hand painter; palette assertion tracks the new declaration.
- `docs/adr/0029-second-clip-group-and-look.md` — decision record.

## Gates (all green, this change)

- `CI=true yarn --cwd frontend test --watchAll=false` — 17 suites, 102 tests.
- `node frontend/scripts/check-imports.cjs` — 148 files, 0 problems.
- `node frontend/scripts/check-frontend-logic.cjs` — logic behaves correctly.
- `node frontend/scripts/check-render-smoke.cjs` — 248/248, including:
  - `demo-cta-second` absent with no base, present once the base attaches;
  - `append-background-sage` + `append-animation-embers` take on the added
    clip while the base keeps lavender + bloom;
  - `append-env-bedroom` reaches `drawHandView` as the segment's env id while
    the hand base still paints `living_room` in the same export.
- `yarn --cwd frontend build` — production build succeeds.

## Not re-verified here

Live two-file preview/export transport was verified for the sequence mechanics
in the prior pass and is untouched by this change (no transport, timing, or
audio edits). Zoom locks remain global by design.
