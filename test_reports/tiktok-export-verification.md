# TikTok export verification

## Delivered behavior

- One output profile: MP4 / H.264 High, 1080×1920, 9:16, 30 fps, target 8 Mbps.
- Source audio becomes AAC-LC stereo, 48 kHz, target 192 kbps. Silent inputs remain silent.
- Alternate export formats, platform dimensions and transparent backgrounds are removed. WebM input remains supported.
- Timestamped decoding and encoding replace real-time MediaRecorder capture. Export and preview share the media-time painter, including background/hand motion, overlays and zoom.
- Decoded dimensions and duration are checked before offering the result or saving it to History.

## Browser and media checks

Exercised the real editor in Chromium 155 on Windows against the existing local CRA server, without screenshots.

| Check | Result |
|---|---|
| 8-second source with repeated audio pulses → full-resolution MP4 | H.264 High, 1080×1920, 30 fps, exactly 240 frames / 8.000000 seconds |
| Export audio | AAC-LC, 48 kHz stereo, 8.000000 seconds; 384,000 decoded audio frames |
| Pulse cross-correlation at 0, 1, 4 and 7 seconds | 0.000 ms measured audio lag relative to source at each sample |
| Per-channel audio RMS relative to source | 0.991235 (approximately −0.08 dB, lossy AAC conversion) |
| Full MP4 decoding through FFmpeg | No decode errors |
| Live preview vs encoded playback at 0.5, 2, 4, 6 and 7.5 seconds | Mean absolute RGB error 3.30–3.96 / 255; no growing temporal divergence in sampled frames |
| Silent 24 fps WebM input, 3.125 seconds | Valid H.264 MP4, 94 frames / 3.133333 seconds; expected rounding to the next 30 fps frame, no audio track |
| Hand-held view with silent WebM input | Successful export; sampled preview/export mean absolute RGB error 1.01–1.95 / 255 |
| Fresh reload and repeat 8-second export after final source edits | Successful, 1080×1920 / 8 seconds; no browser runtime errors |

Pixel comparisons include normal lossy H.264 conversion and source-frame scaling differences; they are not a claim of pixel-identical output.

## Automated checks

- Named import checks: passed (132 files).
- Frontend logic checks: passed.
- Render smoke suite: 232 passed.
- Frontend Jest: 10 suites, 73 tests passed, including seven timestamp/audio/failure/cancellation export tests.
- Backend export API suite: 19 passed.
- Production build: passed; three pre-existing hook-dependency warnings remain in CreateVideo.
- Git whitespace check: passed.

## Verification limits

- Browser-native download automation reported “Download was canceled,” including for an independent plain-text Blob download diagnostic. The MP4 **bytes behind the actual download link** were retrieved from that Blob URL and verified locally, but native OS save completion is not confirmed.
- The running frontend cannot reach its configured backend, so browser Save to History reports Network Error. Backend save behavior is covered by the 19 passing API tests; the live save round trip remains unverified.
- No TikTok upload was performed, and no numeric 9/10 rating is asserted. A real browser save, connected History round trip and TikTok draft upload are the remaining delivery acceptance checks.
- Encoding requires a browser with supported H.264/AAC WebCodecs encoders; unsupported configurations fail with an actionable message rather than switching format or dropping audio.
