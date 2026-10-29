# Demo + CTA editing features — verification

Date: 2026-10-28

## Delivered

- Browser-local autosaved editing documents preserve both uploaded clip Blobs,
  copy, styles, framing, zoom locks and trim points. Documents are keyed by
  account and source generation, with a separate standalone document.
- Whole-document Undo/Redo has buttons and keyboard shortcuts. Playback and
  seeks do not create edits; text entry keeps native undo behavior. Undo history
  is session-local; the latest editing document survives reloads.
- A compact two-clip timeline provides In/Out sliders, playhead cuts and Full
  clip reset. Preview and MP4 encoding share the same trim-window policy.

## Automated checks

- Frontend Jest: **27 suites, 171 tests passed**.
- Import check: **140 files scanned, no unresolved named imports**.
- Frontend logic check: **passed**.
- Render smoke: **341 checks passed**, including recovery of uploaded drafts,
  undo/redo, navigation flush, trim clamping, recovery failure/retry and
  account/source storage keys.
- A regression reproduced Undo retaining the second clip as the active video:
  the new check failed before the transport reset and passed afterward. It
  verifies timeupdate events and frame stepping use the restored base clip.
- Production build: **passed with warnings**. Three pre-existing hook dependency
  warnings remain in CreateVideo.jsx (phases.length and adoptAngles); no new
  Demo + CTA lint warnings were emitted. Node also reports an fs.F_OK deprecation.
- `git diff --check`: **passed**.

## Real Chromium feature checks

Used the local development app and its running local backend, with real uploaded
MP4 bytes and native IndexedDB (not the smoke suite's storage stub).

- Reload restored both 707,748-byte uploads, CTA copy, base trim 0.01–0.51s and
  second-clip trim 0–0.5s, without selecting the files again. Storage showed both
  Blobs and the saved trim values; the UI reported the document saved.
- In/Out range keyboard edits supported Ctrl+Z and Ctrl+Shift+Z while a range
  retained focus. Undo/Redo buttons restored CTA text. Redo survived transport
  seeking, and the redone copy survived reload.
- Undo from the second clip reset the output playhead to zero; stepping one
  frame afterward advanced the base to 0.043333s (0.01s in-point + 1/30s).
- Preview crossed the trimmed base end and stopped at the added clip's 0.5s
  out-point rather than playing its remaining source footage.
- A real joined export decoded as **1080×1920 MP4**, approximately **1.002667s**
  including AAC framing. Decoded PCM RMS was approximately **0.0872** before the
  join and **0.0881** afterward, confirming non-silent audio in both segments.
- Editing after export removed the stale download.
- DOM width checks at **320px, 390px, 768px and 1440px** found no page-level
  horizontal overflow; both trim tracks and Export remained available.
- Fresh-page checks produced no uncaught browser errors. Local no-auth mode
  emits the expected Clerk-not-configured warning.

## Limits

- Drafts do not sync across devices. Clearing browser data or losing the device
  removes them; a forced shutdown before the pending write completes can lose
  the latest change. Storage quota errors are shown with a retry action.
- Recovery failure/retry, storage-write rejection/retry and account/source keys
  are covered by automated checks. Real quota exhaustion and real signed-in
  two-account switching were not exercised; this local app is in no-auth mode.
- Browser checks ran in Chromium, not Safari, Firefox or physical mobile devices.
- These checks verify the local implementation, not completion of the remote
  production deployment triggered by a push to main.
