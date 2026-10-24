# 0025 — Real Video combines a base clip and a phone upload

Status: superseded by 0027

## Context

Real Video needs a full-frame History source with a separate uploaded clip on a floating or hand-held phone, delivered as one TikTok MP4. The original floating and hand-held single-source modes must keep their existing rendering.

## Decision

- The editor owns the base source and independent phone-upload state. Replacing or removing the phone upload cannot replace the base. Phone size and position are separate from the base crop/zoom controls.
- Base duration and audio define the output. The phone upload is silent and loops at `baseTime % phoneDuration`; no extra audio mix or duration extension is introduced. The UI states this policy.
- Preview transport follows the base; the phone follows seeks, pauses, playback, loop wraparound and mode changes. Export decodes both pinned blobs at explicit timestamps rather than capturing either playback element.
- One painter receives the base frame and optional phone frame. It draws base, phone, then hook/story/CTA text. Hand overlays use the existing keyed subject on a transparent offscreen canvas, not an opaque environment plate.
- Export closes the additional decoder on success, failure and cancellation. Existing H.264/AAC, 1080×1920, 30 fps validation and History-save gates stay in force.

Anchors: `frontend/src/demoCta/DemoCtaEditor.jsx` (overlay source and placement state), `frontend/src/demoCta/usePreviewLoop.js` (base-owned transport and shared painter), `frontend/src/demoCta/exportTikTok.js` (looped overlay decoder), `frontend/src/demoCta/handView.js` (`transparentBackground`).

## Alternatives rejected

- Real-time capture of two playing elements: scheduler drift can change the output and drop frames.
- Extending output to the overlay duration or mixing both soundtracks: changes the base story and introduces extra editing policy the request does not need.
- A separate compositor for export: duplicates placement and mockup math and risks preview/export divergence.

## Consequences

A composite requires two simultaneous video decoders. The shorter phone clip repeats, while only the base soundtrack is preserved. Phone upload controls are confined to Real Video; switching to another mode retains the upload for later but excludes it from preview and export.
