# 0016 — Zoom drafts stay editable; playback follows saved locks

- **Status:** accepted
- **Anchors:** `frontend/src/demoCta/DemoCtaEditor.jsx` (`updateZoomDraft`, `handleCaptureZoomLock`, `paintFrame`); `frontend/src/demoCta/zoom.js` (`getEffectiveZoom`)
- **Amends:** ADR 0012's before-first-lock framing rule only.

## Context

Once a zoom lock existed, its framing hid later slider, wheel and drag edits. Users could save another lock without seeing the framing they were capturing. Floating-phone size was not captured at all.

## Decision

Framing edits pause at the current media timestamp and preview a live draft. Lock captures that draft, including hand zoom/pan, floating-phone size and video crop zoom/offset. Seek or Play leaves draft mode and resolves saved locks; controls follow the active lock. Export uses the same resolver but never an uncommitted draft when locks exist.

Locks remain step changes: each holds until the next timestamp, and the last holds through the clip end. Before the first lock, preview and export both use default framing (including 82% floating-phone size). Capture a lock at zero to choose another opening framing. Without locks, live framing applies to the entire clip as before. Replacing/removing the source clears clip-specific locks.

## Consequences and alternatives

Users can audition and capture multiple zoom-ins and zoom-outs without existing locks masking their edits. Timeline labels distinguish hand, phone and video zoom. Automatically modifying the active lock on every adjustment was rejected because it would change earlier footage before the user chooses Lock. Interpolation is not introduced: the existing segment-based timing remains unchanged.
