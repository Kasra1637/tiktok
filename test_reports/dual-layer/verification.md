# Real Video dual-layer verification

Date: 2026-10-24

## Delivered behavior

Real Video accepts a History base and a separate phone upload. The upload can use Floating Phone or Hand Holding with independent size, horizontal and vertical positioning. Preview and export draw base, phone, then text overlays. The base defines output duration and audio; the phone clip loops silently. Existing single-source modes exclude the second clip.

Structure/policy: [ADR 0025](../../docs/adr/0025-real-video-phone-composite.md).

## Real browser/export exercise

- Ran the actual CRA app at `http://127.0.0.1:3001/demo-cta`, using the existing FastAPI server at port 8000. No API/encoder mocks in this browser exercise.
- Selected Real Video, opened Choose from History, and attached History row `91288c04-6056-4ece-a059-aeab676e4e9c` through its actual picker button.
- Uploaded `overlay.mp4` separately: a one-second 360×640 green clip, making its decoded pixels easy to distinguish from the base. The ~19.83s export therefore exercised repeated overlay decoding.
- Exported both phone styles using the actual Export button. Both produced result players, passed the application's MP4/decode gate, and saved new History rows.
- Played both exported MP4s in Chromium: 1080×1920, 19.833333s, decoded readyState 4, playback time advanced, no media error.
- Full ffmpeg decode of both downloaded files completed with no errors. ffprobe confirmed H.264, 1080×1920, 30/1 fps, AAC stereo 48kHz.
- Preview pixel readback included 424,591 identifiable phone pixels. Moving the position sliders to the top left moved their centroid to approximately (235, 510), proving placement changes reach the painter.
- Paused seek to 6s landed base at 6s and the 1s overlay at 0s, both paused. Switching to each single-source mode paused the hidden overlay; switching back retained the upload.
- Browser error log was empty after the exercised flows.

## Export frame checks

The following values came from decoded RGB pixels, not screenshots or visual judgement. Opening and CTA yellow counts are evidence of rendered text treatment, not OCR assertions.

| File / time | Phone green pixels | Overlay yellow pixels |
|---|---:|---:|
| Floating 0.6s | 423877 | 159174 |
| Floating 5s | 423722 | 26906 |
| Floating 18.8s | 364650 | 57418 |
| Hand 0.6s | 314635 | 159476 |
| Hand 5s | 316881 | 27358 |
| Hand 18.8s | 275897 | 59452 |

At 5s, the upper region outside the phone differed from the History base by a mean absolute RGB error of 1.24/255 in both styles, consistent with re-encoding rather than replacement of the base.

Artifacts:
- [Floating-phone composite](real-video-floating.mp4)
- [Hand-held composite](real-video-hand.mp4)
- [History base used](history-base.mp4)
- [Phone upload fixture](overlay.mp4)

## Final checks

- Frontend unit tests: 97 passed, 16 suites.
- Named-import gate: passed (146 files).
- Frontend logic gate: passed.
- Render smoke gate: 248 passed, including a new mounted-editor History attach/upload/composite/export-callback/isolation/error-recovery test.
- Backend export API tests: 19 passed. Full backend suite not run; no backend behavior was changed.
- Production build: succeeded with existing hook-dependency warnings in DemoCtaEditor and CreateVideo; not warning-free.
- `git diff --check`: passed.

Encoder regressions cover repeated shorter-overlay timestamps, missing/undecodable overlay frames, and cancellation/iterator disposal. Single-source export does not pass an overlay blob.

## Verification limitation

Every current History row in this local checkout is marked `segment_role: demo_cta`. Some link to a studio project, but none is an original Create Video render. The real end-to-end exercise therefore proves History attachment, two-layer composition and MP4 export using a prior History export, **not original Create Video provenance**. No paid render was triggered and no synthetic original-generation row was inserted to hide this limitation. An original render can use the same attachment/media path, but that exact source category remains unverified with the available local data.

No commit, push, or deployment was performed.
