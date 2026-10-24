# 0017 — Review overlay changes in place, save looks after CTA setup

- **Status:** partially superseded by 0022 (apply list joins saving in End Card CTA)
- **Amends:** ADR 0015's playhead rule for hook/CTA option changes only; its font retirement remains accepted.
- **Anchors:** `frontend/src/demoCta/DemoCtaEditor.jsx` (`startScopedPreview`, `ensureScopedPreview`, `lookReviewKey`, `handleSaveLookPreset`, `look-save-review`); `frontend/scripts/check-render-smoke.cjs` (scoped-replay and finished-look review checks).

## Context

A settled mid-clip frame cannot demonstrate a newly selected overlay entrance. Conversely, replaying the whole clip for each choice wastes time. Saving a reusable look in Source & Look also asks users to commit before they have styled and reviewed the hook and end card.

## Decision

Hook and CTA style controls replay only their own media window. Continuous sliders retain playback already inside that window. Playback parks at the window boundary; explicit transport cancels the scope. Text entry does not restart playback. This replaces ADR 0015's prohibition on option-driven replay, without returning to full-clip replay.

Applying existing looks stays in Source & Look. Creating a named look moves to the bottom of End Card CTA, outside its customization disclosures. It requires a playable loaded clip, a nonblank name and an explicit confirmation that the current hook and end-card styling has been reviewed. Approval is keyed to the source and the exact saved style fields; different styling needs fresh approval. The save handler enforces the same conditions as the button.

The reusable payload remains fonts, entrances, text sizes and accent for both overlays. It does not claim to store footage, copy or zoom locks. Saving confirms the name and where to apply it next; applying a saved look remains available on later visits.

## Consequences and alternatives

Users can judge their selections before deliberately saving them. Export is not required: the preview can demonstrate the finished styling without encoding another video. Keeping saving in Source & Look was rejected as premature; requiring export was rejected as unnecessary work for a reusable typography/color choice. The existing dark studio components and spacing are retained.
