# 0136 — The Location is edited in one place: the Visual & audio direction pick

- **Status:** accepted
- **Date:** 2026-11-14
- **Anchors:** `frontend/src/pages/CreateVideo.jsx` (the removed
  standalone Location field; the Location `DirectionSelect` inside
  `visual-audio-direction`), `frontend/src/components/GenerationPanel.jsx`
  (the removed render-step editor), `frontend/src/components/HookContinuityPanel.jsx`
  (the scene block's pointer), `frontend/scripts/check-render-smoke.cjs`
  ("the render panel offers no Location editor — one place edits the
  place", "the plan view edits the Location only through the direction
  pick"). Builds on ADR 0090 (Location is the single source of truth)
  and ADR 0133 (direction changes and the rebuild suggestion flow).

## Context

One fact — where the video happens — had three editors. The plan view
carried a free-text Location textarea ("This Location feeds the
strategy, the prompt and the result."), the Visual & audio direction
section below it carried a Location pick writing the same field, and
the render panel carried a second free-text editor with its own
"Save location" button. All three wrote `project.location` through
the same PATCH; the founder screenshot showed the place stated and
editable over and over on one page, and asked why. The render editor's
only unique contribution was its note reporting the server-side
rewrite ("Rewritten to match: …"), which described a reconcile that
never belonged to the editor.

## Decision

**The Location is edited in exactly one place: the Location pick
inside Visual & audio direction, beside the camera setup.** The plan
view's standalone Location field and the render panel's Location
editor (textarea, "Where it happens", "Save location", its draft
state and save handler) are removed. The pick already writes
`project.location` through the plan's draft edits, saved by the same
validated write as every other Review edit — the manual Save edits
button or the debounced autosave — so no save path is lost.

What did not move, deliberately:

- **The ADR 0090 reconcile stays in the shared PATCH handler.** Any
  PATCH carrying a changed `location` still splits lighting out of the
  place, syncs the legacy mirror, runs
  `angle_scene.reconcile_location` plus
  `scene_consistency.reconcile_scene` over the stored strategy, and
  re-stamps the strategy to the saved plan version in the same write.
  It was never specific to the render editor — that editor merely
  called the same endpoint with `{location}` — so a direction pick's
  save receives the identical scene consistency, with no wiring added.
  Backend tests (`backend/test_location_source.py`) pin that
  reconcile unchanged.
- **The ADR 0133 suggestion flow still sees the change.** The
  direction snapshot is stamped only when a strategy is built, so a
  location saved through the pick still diffs against the snapshot at
  the next rebuild, and the refreshed-words modal is offered exactly
  as before.
- **The strategy panel's Scene Details keeps its read-only LOCATION
  row.** It is the locked-scene breakdown, the same standing as the
  wardrobe and lighting rows; the duplication removed here was
  editors and repeated prose, not the scene record. The scene block's
  pointer line now names Visual & audio direction as the editor.
- **The PATCH response still carries `location_change`.** The audit
  (rewritten lines, spoken lines that still disagree) remains part of
  the save contract for API consumers; its one UI consumer was the
  removed editor's note. Nothing else read it.

## Consequences

A founder who wants a place the generated options do not offer uses
the pick's refresh for fresh options; free-text place entry no longer
exists anywhere in the wizard. The plan prompt and the strategy build
read the same `project.location` row field as before — one editor,
one field, one save path.
