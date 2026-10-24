# Per-clip presentation — verification

## What changed

Each sequence clip now has its own style picker: the base keeps the existing
first-clip selector (`view-mode-*`), the added clip gets `append-mode-*`
(floating / hand / real, default real). The sequence exists whenever an added
clip is attached, in any combination. Single-source (no added clip) rendering
is unchanged.

## Live browser verification (Chrome, http://127.0.0.1:3001/demo-cta)

- Attached History render (5.758s) as base; uploaded the 8s/880 Hz fixture as
  the added clip. Timeline summed to **13.76s**; added-clip picker defaulted
  to Real Video.
- Set added style to **Floating Phone** (aria-pressed confirmed): base kept
  playing full-bleed, auto-advanced into the added clip at the cut, pause and
  End/Home seeks stayed on the global playhead (seek-to-end landed 8.0s into
  the added clip at 13.76s global).
- Preview canvas on the added segment: dark lavender background at the frame
  edges with vivid test-pattern bars in the middle — the floating phone, not
  full-bleed.
- Export produced `demo-cta-s24-ultra-tiktok-1080x1920.mp4` (13.5 MB), saved
  to History ("In History", original untouched).

## Export media (ffprobe + decoded PCM)

- Video: H.264, **1080×1920, 30/1 fps**; audio: **AAC 48000 Hz stereo**;
  container **13.717s** (= 5.758 + 8.0 within a frame + AAC priming).
- Decoded frame at t=10 (added segment): dark runs only at the phone bezel;
  illuminated test-pattern center — phone presentation baked in.
- Base audio correlation vs source: **0.9999965 at lag 0** — untouched.
  Added audio correlation: **0.9983** (−168-sample AAC priming offset,
  expected). No gap or pop at the cut.

## Gates (all green)

- Frontend unit: **102 passed** (17 suites). Render smoke: **248/248**,
  including the rewritten per-segment sequence test (floating/hand added clip
  renders through its painter, base style change keeps both segments, remove
  recovers base-only export).
- Imports, frontend logic, tour targets: green. Production build: success.
- Backend: 1146 passed on unchanged backend code (no backend files touched).

## Notes

- Fixture media (`perclip-base.mp4`, `sequence-added.mp4`, `perclip-export.mp4`)
  and raw logs stay untracked; only this report is committed.
- An early full-smoke run caught a real bug from this change
  (`appendBlob` referenced before initialization in the hand-asset gate);
  fixed by gating on `appendUrl`, re-verified green.
