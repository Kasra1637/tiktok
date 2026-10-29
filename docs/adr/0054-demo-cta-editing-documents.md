# 0054 — Demo + CTA editing documents, undo history & two-sided trims

- **Status:** accepted
- **Date:** 2026-10-28
- **Supersedes:** 0045 (start-only trimming and its controls)
- **Anchors:** `frontend/src/demoCta/draftStorage.js` (`readDraft`, `writeDraft`), `frontend/src/demoCta/editSession.js` (`useEditSession`), `frontend/src/demoCta/TrimTimeline.jsx`, `frontend/src/demoCta/constants.js` (`clipWindow`)

## Context

Editing was disposable: leaving the page lost copy, framing, uploads and timing.
There was no reversible edit history and only the head of each clip could be cut.

## Decision

- Save one versioned editing document per signed-in user and source generation,
  plus a separate standalone document, in this browser's IndexedDB. Store source
  Blobs alongside settings so uploads resume without expired object URLs or
  re-selecting files. Create fresh object URLs on recovery. No server draft API,
  new service, cross-device sync, or dependency is introduced.
- Save after 500 ms of inactivity, serialize writes, and flush on navigation,
  pagehide and hidden visibility. Show loading/saving/saved/error state; recovery
  failure blocks editing until retry or an explicit start-without-recovery action.
  Quota errors are visible and retryable. Browser-cleared storage and a crash
  before the last write completes cannot be recovered.
- Keep up to 50 whole-document undo steps during a mounted editing session.
  Coalesce successive changes to the same fields within 500 ms. A new edit
  after Undo clears Redo. Source swaps/removals retain their Blob references in
  history. Playback, seeks, open panels, saved-result state and lock-following
  slider readbacks are not edits. Text fields retain native undo shortcuts;
  elsewhere Ctrl/Cmd+Z, Ctrl/Cmd+Shift+Z and Ctrl+Y control document history.
- Both clips receive source-space in/out points in one compact timeline beneath
  the preview, replacing duplicated start-only controls in settings. The seek
  strip remains output-space. Trimming pauses at the new first frame; Play
  reviews the kept run. `clipWindow` is the sole duration/clamping policy for
  preview, overlay timing and encoding, preserving a minimum 0.5s run. Video and
  audio decoding stop at the same out-point; the second clip starts at the
  trimmed base end. Full clip resets both edges.
- Story timing is resolved against the current trim without overwriting its
  requested values, so Undo restores a longer window without losing timing.

## Consequences & alternatives

Drafts are device-local, not a claim of cloud backup. Large uploads consume
browser storage; undo retains at most 50 documents referencing immutable Blobs.
Keeping Blobs in IndexedDB was preferred to localStorage (cannot hold bytes),
and to automatic server uploads (new privacy, quota and API scope). Undo history
is intentionally session-local while the latest edit survives reloads. No
thumbnail extraction, waveform generation, arbitrary tracks or clip reordering
is added to the two-clip timeline.
