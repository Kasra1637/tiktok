# ADR 0170: The progress stages name the real backend phase

Status: accepted

## Context

Kasra, watching a render in flight (voice call, Nov 16 2026), ordered
the in-progress panel fixed: the "Render in progress — paid render"
header line and its film icon come out, and the stage labels must say
what is actually happening in the backend at that moment, switching
when the backend switches.

The old labels lied. The checklist read "Locking your approved
script" / "Rendering hook + story in one pass" / "Stitching one clip",
but the derivation highlighted index 2 for every 'generating' row and
the headline mapped 'generating' to "Stitching one clip" — so the
middle stage could never be the highlighted one, and the panel claimed
"Stitching one clip" for the entire provider render, the longest part
of the wait. The headline also duplicated the checklist: the current
stage's name rendered twice, once as a bold line above the bar and
again as the lit checklist row.

The backend lifecycle the labels must follow: the row is inserted as
'submitted' while our backend composes and sends the provider request;
it flips to 'generating' the moment the provider accepts and stays
'generating' through two different phases — the provider rendering,
then, after the provider reports completed, the durable save
(download, ffmpeg trim/rescale, upload) running detached through the
job queue (ADRs 0120/0138/0148). Status alone cannot separate those
two phases; the persist job's existence in the jobs table can.

## Decision

- The stages are: 'submitted' → "Sending your approved script";
  'generating' with no persist in flight → "Rendering your hook +
  story"; 'generating' with a persist in flight → "Saving your
  finished video". One derivation drives the checklist highlight; the
  done state (a completed row or a playable URL) still completes all
  three.
- The signal is honest and minimal: `_public_generation` serializes
  `persist_in_flight`, true exactly while a persist job for the row
  is recorded or claimed (status pending/claimed — the queue's own
  live set) and stamped by the two reads the panel uses: the poll
  response (at the still-generating returns) and the generations
  list (one set query over live persist dedupe keys, never a query
  per row). No fallback stage was needed; the signal reads cleanly.
- The header row ("Render in progress — paid render", film icon) is
  removed entirely, and so is the duplicated bold headline line: the
  checklist alone carries the stages, and the current stage's name
  appears exactly once in the block. The progress bar keeps its row,
  with the elapsed timer re-homed beside it; the timer's anchor (the
  row's created_at) is unchanged.

## Consequences

The panel can no longer claim a phase the backend is not in: the
rendering stage lights for the provider wait it names, and the saving
stage lights only while the save the founder is actually waiting on
runs. Pins cover the mapping per status and persist signal, the
rendering stage's highlight (the regression), the retired labels'
absence, and the stage name appearing exactly once; backend tests pin
persist_in_flight's truth at each phase (no job → false; job live →
true on poll and list; completed row → false).
