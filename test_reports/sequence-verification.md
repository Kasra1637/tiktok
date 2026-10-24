# Real Video appended sequence — verification

## What changed

Real Video no longer overlays the second upload on the base. It plays the
History base first, then the uploaded clip, as one 1080×1920 30 fps TikTok MP4
with both original soundtracks. Text/overlays apply to the base by default with
an opt-in for the added clip. Floating/hand-held single-source modes unchanged.

## Live browser verification (Chrome, http://127.0.0.1:3001/demo-cta)

- Attached History render `71e5182a` (5.88s) as base; uploaded 8s fixture with
  original 880 Hz audio as the added clip; switched to Real Video.
- Timeline read **13.8s** (5.88 + 8.0); added clip labeled `8.0s`; overlays
  opt-in unchecked by default.
- Play ran base → added automatically across the cut; pause held on the added
  segment; seek to 6.94s landed on the added clip only (1.06s in); play/pause
  from there worked with the global playhead correct.
- Export produced `demo-cta-s24-ultra-tiktok-1080x1920.mp4` (14.00 MB), saved
  to History ("In History", original untouched).

## Export media (ffprobe)

- Video: H.264, **1080×1920, 30/1 fps**, 13.866667s stream / 13.888s container
  (= 5.880933 + 8.0 within one frame + AAC priming).
- Audio: **AAC, 48000 Hz, stereo**, 13.888s — present across the join.

## Audio continuity (decoded PCM vs originals)

- Base segment correlation **0.999997** at lag 0 — untouched.
- Added segment correlation **0.99985** (109-sample ≈2.3 ms AAC priming offset,
  expected for AAC) with the 880 Hz tone intact.
- Max adjacent-sample jump in ±3 ms around the cut: **2.9e-06** — no pop.

## Gates (all green)

- Frontend unit: **102 passed** (17 suites), incl. sequential timestamp/summed
  duration tests and joined-AAC tests.
- Export gate tests: joined duration + AAC stereo coverage for both segments,
  rejection of missing/short/undecodable audio.
- Render smoke: **248/248**, incl. sequence seek-across-cut, base-only default
  overlays, opt-in coverage, and phone-mode isolation.
- Imports, frontend logic, tour targets: green.
- Backend: **1146 passed**. Production build: success (existing
  exhaustive-deps warnings only).

## Notes

- Verification media (`sequence-base.mp4`, `sequence-added.mp4`,
  `sequence-export.mp4`) and raw logs stay untracked; only this report is
  committed.
- The prior phone-composite behavior is fully retired; ADR 0025 is superseded
  by ADR 0027 in the same commit.
