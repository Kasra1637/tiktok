# 0027 — Real Video appends the second clip after the base

Status: accepted (supersedes 0025)

## Context

0025 composited the second upload as a looping silent phone overlay on top of
the base. The request corrects that: the second clip must play after the base
ends, with its own original audio, as one TikTok-ready MP4. The base stays
fully intact — audio, timing and length unchanged — and the floating/hand-held
single-source modes must keep working unchanged.

## Decision

- Real Video is a two-segment sequence, not a composite: History base first,
  uploaded clip second. Total length is base plus upload (5.88s + 8s = 13.888s
  in the verified export). No looping, retiming, overlap, gap, or speed change.
- One 30 fps timeline decodes both pinned blobs in order; one PCM timeline and
  one AAC encoder join both soundtracks (each resampled to 48 kHz stereo, base
  untouched). Only a 2 ms de-click at the added segment's first samples guards
  the cut; nothing is overlapped, extended, or silenced.
- Text/overlay layers apply to the base segment by default, with an explicit
  opt-in to extend them to the added clip. The added segment otherwise uses its
  own uncoupled full-bleed framing.
- Preview plays base then clip on a single global playhead: seek lands across
  the cut, pause holds, transport resumes correctly, and the timeline sums both
  durations. Phone overlay modes keep their existing single-source rendering.
- The export gate validates the joined container: 1080×1920, duration within
  0.1s of base + upload, AAC stereo 48 kHz present, and decodable audio at both
  segment starts.

Anchors: `frontend/src/demoCta/DemoCtaEditor.jsx` (appended-clip state),
`frontend/src/demoCta/usePreviewLoop.js` (single-playhead sequence transport),
`frontend/src/demoCta/exportTikTok.js` (sequential video + joined AAC),
`frontend/src/demoCta/exportFlow.js` (joined gate),
`frontend/src/demoCta/exportTikTok.test.js`,
`frontend/src/demoCta/exportFlow.test.js`, `frontend/scripts/check-render-smoke.cjs`.

## Alternatives rejected

- Simultaneous composite (0025): plays both clips at once and drops the added
  clip's audio — the opposite of the requested sequential delivery.
- Real-time capture of two elements: scheduler drift can change the output and
  drop frames; explicit timestamps keep preview and export identical.
- Separate export compositor: duplicates framing math and risks
  preview/export divergence.

## Consequences

Two sequential decoders run instead of one; peak memory is unchanged in kind.
The added clip's container is normalized to 1080×1920 30 fps AAC on export
while its content, order, and duration are preserved. Mode switches retain the
added clip for later but exclude it from single-source preview and export.
