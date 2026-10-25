# 0033 — Compare saved clip results without inferring conversions

Status: accepted; partially supersedes 0009 (collapsed tile contents only).

## Context

Views, posted links, and render votes already exist, but Analytics showed only
production activity. History hid clip identity and kept newly saved results
inside drawer state, leaving its list and Most viewed ordering stale.

## Decision

- Analytics reads the existing History endpoint, scoped to one app or All
  apps (including unassigned exports), up to 200 newest rows. Finished clips
  compare posted status, recorded views, and the founder's render vote.
- Recorded views sort descending; zero is recorded, null is missing. Explicit
  copy distinguishes reach snapshots from installs, revenue, conversions,
  controlled experiments, and causal claims. No template aggregates or new
  winner scoring: Winner remains a positive render vote plus a posted link.
- History tiles show app, hook or stable fallback identity, date, status, views,
  and vote without opening the drawer. Context and working/destructive actions
  remain inside. Existing spacing tokens are reused.
- Successful saves patch the owning History list row from the confirmed save;
  list ordering and summaries update without unmounting the editor.
- The views request uses a strict nullable integer before endpoint range
  validation (0–10 billion); booleans, floats, and strings are not coerced.

## Alternatives & consequences

Template summaries or conversion recommendations would overstate the available
observations. A new analytics API would duplicate data already returned by
History. Full-list reloads on each save would discard drawer state and focus.

The comparison is explicitly limited to loaded rows, not lifetime totals. App
scope can exclude unassigned exports, so All apps remains available even with
one profile. Analytics fetch errors are shown, never presented as empty success.

Anchors: `frontend/src/pages/Analytics.jsx` (`ClipResults`),
`frontend/src/pages/GenerationHistory.jsx` (`updateRow`, `history-summary`),
`frontend/src/components/HistoryFeedback.jsx` (`onUpdated`),
`backend/models.py` (`TikTokViewsRequest`). Regression behavior is exercised in
`frontend/scripts/check-render-smoke.cjs` and `backend/test_tiktok_views_api.py`.
