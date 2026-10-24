# 0029 — Second clip gets its own group and its own look

Status: accepted

## Context

After 0028 each sequence clip picked its own floating/hand/real
presentation, but three problems from the follow-up review stayed open:
the panel still showed two upload buttons before any base existed, the
Source & Look group held both clips' controls in one long scroll, and both
segments shared one background, one motion and one hand scene — a calm base
could not flow into an energetic upload.

## Decision

- The appended clip moves into its own `Second clip` group (`demo-cta-second`),
  rendered only once a base exists. One clip per group, one style picker per
  clip; the accordion stays single-open.
- The added clip owns `appendBg` / `appendAnim` / `appendEnv`, seeded from the
  same defaults as the base but never synced after. The painter resolves the
  look per segment (`lookBg` / `lookAnim` / `lookEnv`); export preloads both
  hand scenes.
- Zoom locks, phone scale and screen geometry stay shared: one mockup, one
  timeline, so locks and the crop sliders keep working across the cut.

Anchors: `frontend/src/demoCta/DemoCtaEditor.jsx` (Second clip group,
`StylePicker`/`EnvGrid`/`BackgroundPicker`/`AnimationPicker`),
`frontend/src/demoCta/usePreviewLoop.js` (per-segment look resolution),
`frontend/src/demoCta/exportFlow.js` (both hand scenes preloaded).

## Alternatives rejected

- Per-segment zoom and phone geometry: locks are global keyframes on one
  timeline, and forking them doubles the framing model for no requested use
  case. Shared geometry is the documented limit, not an oversight.
- Syncing the added look from the base on every change: the seed equals the
  base default once, then diverges. Continuous sync would silently restyle a
  clip the founder already finished.
- Keeping both clips in Source & Look: the group was the density problem.
  Splitting by clip is what makes each group's controls fit on one screen.

## Consequences

Two clips mean two simultaneous look states in preview and export, and the
stored section key moves to `openSections.v4`. Realistic segments ignore
palettes and scenes entirely, so the extra state costs them nothing. The
smoke suite pins the gating (no group before a base), the per-segment
backdrop/motion picks, and the per-segment scene id reaching the hand
painter.
