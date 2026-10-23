# 0012 — Timestamped TikTok MP4 export

Status: accepted

## Context

A playable download is not enough: full-resolution canvas recording can skip frames and drift against source audio. WebM metadata also failed duration validation in the tested browser. Preview and download previously used different clocks (media playback, RAF, and elapsed wall time).

## Decision

Export one upload-ready profile: 1080×1920, 9:16, 30 fps, H.264 High Level 4.0 at a target 8 Mbps, and AAC stereo 48 kHz at 192 kbps when source audio exists. Remove alternate platform sizes, WebM output and transparent backgrounds. WebM remains accepted as input.

Use Mediabunny/WebCodecs to decode source frames and encode explicit `frame / 30` timestamps with backpressure. Decode audio directly and retain its offset relative to the video, independent of preview mute/volume. Preview and export call the same painter with media time, including mockup/background motion and zoom. Before the first zoom lock, both use the live settings; preview must not promise a framing the download omits.

Wait for selected fonts and hand-view assets before encoding. Validate the MP4 container, decoded dimensions and duration before exposing a download or saving to History. Unsupported encoders fail with a browser-upgrade action, never a fallback container or silently removed audio.

Anchors: `frontend/src/demoCta/exportTikTok.js:1`, `frontend/src/demoCta/DemoCtaEditor.jsx:1`.

## Alternatives rejected

- Tuning MediaRecorder: still depends on real-time playback, scheduler load and browser capture behavior.
- WebM fallback: adds an unsuitable delivery choice and reintroduces unreliable metadata.
- Server transcoding: adds infrastructure and upload latency without solving parity with the client painter.

## Consequences

Encoding can take longer than playback on slower computers without changing output timestamps. A current browser with H.264/AAC WebCodecs encoding is required. The in-memory MP4 requires memory proportional to the encoded clip. No new external service or credentials are involved. ADR 0007's shared video-time overlay painter remains in force.
