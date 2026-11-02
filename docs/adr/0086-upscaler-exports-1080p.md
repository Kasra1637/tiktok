# 0086 — The upscaler exports 1080p, not 4K

Status: accepted

## Context

The browser-side upscaler shipped with a 4K target: short side grown to 2160,
long side capped at 3840, AVC at 32 Mbps (`frontend/src/upscale/sizing.js`).
Everything runs in the tab — decode per frame, paint through a canvas with an
unsharp convolution, encode AVC through mediabunny — so the target sets the
cost of every export three ways: pixels to paint, pixels to encode, and bytes
in the file.

Three things made 4K the wrong target:

- **The source does not have the detail.** A 540p clip scaled to 2160x3840
  gains pixels, not information. The unsharp pass recovers edge contrast; it
  cannot recover what was never sampled.
- **The destination is 1080p.** Finished clips are 1080p by the time they reach
  TikTok delivery (ADR 0012). A 4K intermediate is re-encoded down before
  anyone sees it.
- **The tab pays for it.** Four times the pixels to encode per frame is the
  difference between a clip finishing in the tab and the tab being unusable
  while it does.

## Decision

- `UPSCALE.targetMinSide` is 1080 and `maxSide` is 1920. A 540x960 clip lands on
  1080x1920, 1280x720 on 1920x1080, 640x480 on 1440x1080 (aspect preserved, the
  short side is what hits the target).
- **Eligibility moves with the target.** Sources already at or above 1080p on
  the short side are refused with their own dimensions quoted. So are sources
  whose long side already fills 1920 — 1920x800 has a short side under 1080 but
  no room to grow, so the only possible "1080p" export is the input's own size.
  `upscaleTarget` returns null for both, and the refusal names the dimensions
  rather than handing back an un-enlarged file under a 1080p label.
- Copy, refusal strings and the download name (`-upscaled-1080p.mp4`) all say
  1080p, so nothing on the page promises a resolution the encoder is not
  producing.
- **`videoBitrate` stays 32 Mbps.** Bitrate per pixel is a separate quality
  decision and a resolution change must not silently re-decide it; the constant
  carries a comment saying so, and the export is now roughly 4x smaller on
  pixels alone.

Alternatives rejected: **keep 4K** (the tab cost and the re-encode both stay,
and the detail argument never held); **1440p** (a middle target nobody
delivers, so it costs a third of the 4K encode time for pixels that get thrown
away); **lower only `targetMinSide` and leave the 3840 ceiling** (wide sources
would still encode 3840 across); **crop wide clips to reach 1080p** (cropping is
a content decision the founder did not make).

## Consequences

- Export size drops with the pixel count, and the per-frame work drops with it,
  so a given clip finishes in the tab sooner.
- Clips that used to be accepted now get refused: 1440p sources (previously
  eligible up to the 4K ceiling) and 4K sources were never eligible, but
  1080p-and-above now is not either — which matches what the page can deliver.
- Downloads already made at 4K stay valid; only new exports are 1080p.

## Anchors

- `frontend/src/upscale/sizing.js` — `UPSCALE`, `upscaleTarget` (the `factor
  <= 1` refusal)
- `frontend/src/upscale/enhanceVideo.js` — the encode gate's refusal
- `frontend/src/upscale/useUpscaler.js` — probe refusal, download name
- `frontend/src/pages/VideoUpscaler.jsx` — page copy
- `frontend/src/upscale/sizing.test.js` — target expectations, both
  ineligibility edges
