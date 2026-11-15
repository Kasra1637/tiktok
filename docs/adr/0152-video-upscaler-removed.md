# ADR 0152: The Video Upscaler is removed

Status: accepted

Supersedes the living surface of ADR 0086 (which stays as history).

## Context

Kasra, on a voice call on Nov 15 2026, ordered the Video Upscaler
removed entirely — the page, all its backend resources and source
code — cleaned up, and registered in the app's own memory for
future reference.

The upscaler was a standalone browser-side tool: upload a sub-1080p
clip, enhance it to 1080p in the tab (decode, canvas unsharp pass,
mediabunny encode), preview and download. It sat outside the app's
one working sequence — App Profile → Create Video → Demo + CTA →
History → Analytics — and polished footage the pipeline itself
already delivers at canvas size. It was the only page whose input
was not made by the app.

## Decision

- **The feature is deleted, not hidden.** `pages/VideoUpscaler.jsx`,
  the `/upscale` route and its lazy chunk in `App.js`, the sidebar
  entry, and `frontend/src/upscale/` (`sizing.js`, `enhanceVideo.js`,
  `useUpscaler.js` and their two test suites) are all removed, with
  the smoke pins that guarded them (the sidebar-order pin, the
  page-header pin, the content-reveal page list, and the upscaler
  half of the landing-payload chunk check).
- **There was no backend surface to remove.** The tool ran entirely
  in the tab; no endpoint, service function or config existed for
  it. The backend's `build_upscale_command` / `rescale_to_canvas`
  in `backend/overlays.py` is the render pipeline's canvas fit — it
  scales a finished render onto the 1080x1920 canvas for the plain
  Download MP4 path — a passing word, not this feature. It and its
  tests are untouched, as is the finalize comment in
  `ai_service.py` that names the same step.
- **The one shared helper is kept, under its remaining owner.**
  `passthroughSegmentAudio`, the single-segment AAC passthrough,
  was shared by the upscaler's encoder and the Demo + CTA export.
  It moves to `frontend/src/demoCta/audio.js` — the export is its
  only consumer now — with its body byte-for-byte unchanged, so
  export behavior is identical; only the header comment and the
  import path moved. The smoke pin that guards the export's direct
  audio path follows it to the new home.
- **ADR 0086 remains as history.** Its decision (the upscaler
  exports 1080p, not 4K) has no living surface after this removal;
  nothing in it is reopened.

Alternatives rejected: **hide the nav entry and keep the page** (a
dead surface stays to maintain, and the founder asked for removal,
not concealment); **move the whole `upscale/` folder under
demoCta/** (the sizing rules and encode pipeline have no second
consumer — keeping them keeps a feature's worth of dead code under
a new address).

## Consequences

- The sidebar is one item shorter and the app has one less surface
  that owed upkeep, pins and tour-free explanations.
- mediabunny now ships only in the Demo + CTA editor chunk; the
  landing-payload check guards that one door.
- Downloads the founder already made with the tool stay valid
  files; nothing about the render path, the export, or any saved
  data changes.
- If a browser-side enhancer is ever wanted again, it is a new
  feature to design, not a resurrection: this record and ADR 0086
  together hold what it was and what it cost.

## Anchors

- Deleted: `frontend/src/pages/VideoUpscaler.jsx`,
  `frontend/src/upscale/` (`sizing.js`, `enhanceVideo.js`,
  `useUpscaler.js`, `sizing.test.js`, `enhanceVideo.test.js`)
- Kept and moved: `frontend/src/upscale/audio.js` →
  `frontend/src/demoCta/audio.js` (body unchanged)
- Edited: `frontend/src/App.js`, `frontend/src/components/Sidebar.jsx`,
  `frontend/src/demoCta/exportTikTok.js`,
  `frontend/scripts/check-render-smoke.cjs`
