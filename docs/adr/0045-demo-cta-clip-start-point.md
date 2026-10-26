# 0045 — Demo + CTA clips carry a start point; the head is trimmed, the tail is not

- **Status:** accepted
- **Date:** 2026-10-26
- **Anchors:** `frontend/src/demoCta/constants.js:296` (`clipWindow`), `frontend/src/demoCta/exportTikTok.js` (decode origin), `frontend/src/demoCta/DemoCtaEditor.jsx` ("Starts at" in Source & Look and Second clip)

## Context

Demo + CTA takes a founder's clip whole. Real footage opens on the wrong
frame: a screen recording starts on a countdown or a stray tap, a take opens
on a fluffed first line, and a finished render opens on a beat that is not
the hook. The only fix was to trim the file elsewhere and upload it again —
which threw away the looked-and-reviewed state and re-probed the clip.

Both clips in the editor had the same gap. The base clip is where the hook
and story live, and the second clip is the payoff; a start point on one but
not the other would make half the sequence unaddressable.

## Decision

- Each clip carries one **start point**. It trims the **head** only: the
  used run is `[start, source end]`. There is no out-point.
- Everything rebases onto that run through one helper, `clipWindow`:
  timeline mapping, the hook/story/CTA windows, the scrubber length, zoom
  lock times, the export's decode origin, and each segment's audio window.
  Preview and export therefore open on the same frame by construction, not
  by two matching subtractions.
- The start point is clamped to leave at least `MIN_CLIP_SECONDS` (0.5s);
  the control offers at most `duration - 0.5`. A clip with nothing left fails
  loudly and names the next step rather than exporting an empty segment.
- Changing the start point rewinds the preview onto the new first frame. A
  number that claims what the file opens on cannot leave the playhead on
  footage the export skips.
- The second clip's start point is measured on its own file, not on the
  joined timeline, so editing it never moves the base.

## Alternatives rejected

- **An out-point too.** A second number doubles the surfaces (windows,
  scrubber, story clamp, audio) and every overlay window would need to clamp
  both ends. The reported problem was always the opening frame.
- **Trim in the wizard before generation.** The wizard has no second clip
  and no overlay timeline, so the trim would be re-entered in the editor
  anyway. The studio is the place the clip is actually used.
- **Require a re-upload.** Never recorded; the file is already in the
  browser, and re-uploading discards the reviewed state on purpose.

## Consequences

- The preview, the scrubber and the MP4 all start on the chosen frame; the
  first video and the second clip each get their own control.
- Zoom locks, saved looks and overlay windows are keyed to the trimmed
  timeline, so trimming earlier in the session does not move a lock set on a
  frame that is still in the cut.
- A source-length readout stays visible beside the control ("12.4s used")
  so a founder can see how much of the file was skipped.
