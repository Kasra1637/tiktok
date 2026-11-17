# ADR 0179: The finished save is reconciled, and a long save is named

Status: accepted

Extends ADR 0170 (the stages name the phase the backend is in)
and ADR 0171 (the panel never stops watching). Kasra's order,
Nov 16 2026, from his own render live: the panel reached
"Saving your finished video…" at 2:50 elapsed and sat there
past six minutes with no video appearing — "display and fix
the video not showing at that section. Debug and fix."

## Context

The whole completion chain was traced before anything
changed: the panel's poll loop and swap condition, the poll
endpoint, the persist queue (claim, heartbeat, execute,
apply), the serializers, and History's read of the same
endpoint. Most of the chain is sound, and the trace says so
with evidence rather than by assumption:

- The panel's old poll budgets are gone (ADR 0171) and its
  pins are behavioral — a mounted panel, real timers — so a
  poll-chain death would have failed them.
- The panel polls the row it adopted; a completed row with a
  storage error surfaces as completed, with the alert and the
  storage-retry path (ADR 0148), never as endless generating.
- A dead runner's claim is reclaimable: the claim primitive
  takes a pending job or one whose lease lapsed, and the
  drain test proves a dead worker's save is re-run to
  completion.

Three findings remained, two of them defects and one a cost
nobody had measured:

1. **The save is minutes long by construction, and was
   silent about it.** The durable save is two full re-encodes
   on a small box: the canvas rescale, then the camera move —
   a per-pixel `geq` remap, single-threaded at 1080x1920.
   Measured on this box class with a synthetic 15s 480p clip:
   the rescale took ~34s, and the camera move had not
   finished the post-cut portion after ~6.5 minutes when the
   measurement was stopped. Both run inside the 1800s
   execution bound (ADR 0148) with the claim heartbeating, so
   the machinery was honest and `persist_in_flight` truthful —
   the mural render most likely sat inside the camera-move
   encode for Kasra's whole window. But ADR 0171's stall
   honesty covers failing polls only; the saving phase ADR
   0170 introduced had no long-phase signal of its own, so a
   healthy multi-minute encode and a dead save were
   indistinguishable to the founder watching.
2. **A finished save could be stranded in its job's
   result.** The executor completes the persist job WITH the
   outcome recorded in its `result` BEFORE the runner applies
   the outcome to the generation row. If the apply is lost —
   the runner dies between the two steps, or the apply's
   write is refused at exactly that moment (ADR 0083
   documents the database refusing writes on a configured
   outage) — nothing ever read a completed job's `result`
   back (verified by search: the result was written and never
   consumed). The row stayed `generating` until a later poll
   happened to re-run the entire save. The detached runner's
   success-path apply was also unguarded, so the failure
   escaped into the framework's background-task log with no
   named cause.
3. **The camera move's cost is a product decision, not a
   bug.** The `geq` graph was chosen deliberately — its
   comment records why: one inverse-coordinate resampling
   keeps fractional crop coordinates and the exact setting,
   without integer rounding or dynamic reconfiguration
   shifting the crop origin. Replacing it with a cheaper
   crop+scale graph would change the rendered output, so it
   is NOT bundled into this fix; it is named here as the
   remaining lever on the wait itself, for Kasra to rule on
   with the measurements above in front of him.

## Decision

- **A finished save is reconciled, never re-run.**
  `_persist_via_queue` now looks for this generation's last
  completed persist job before enqueueing new work. When one
  recorded an outcome and the row is still in flight, the
  recorded outcome is applied — the same write the original
  runner owed — and returned, so the poll that notices
  converges in the same response. The construction is safe:
  a row reaches this call only while in flight (the poll
  returns completed rows before asking the provider again),
  a generation completes exactly once, and the
  storage-repair path runs only on completed rows, so a
  recorded outcome beside an in-flight row is unapplied by
  construction.
- **A lost apply is loud, and self-healing.** The detached
  runner applies its outcome through a guarded wrapper: a
  failure is logged as an error naming the generation and
  the reconcile that recovers it, instead of escaping the
  background task unnamed. With the reconcile in place, the
  next poll lands the row.
- **A long save is named while it runs.** When the panel's
  row has been in the saving phase for more than two
  minutes, a status line appears (`render-save-long`): the
  render is finished, the durable save is taking longer than
  usual, it has not stopped, and the video will appear in
  the section — and be in History — when the save lands. The
  phase's anchor is the row's `updated_at`: the backend
  polls that notice the finish and watch the save never bump
  it, so it stands at the moment the save began, and a
  mid-save poll error can only push it later, never earlier.
  The line never shows for a row still rendering at the
  provider, however old its timestamp, and it yields to the
  stall notice when the checks themselves are being slowed.
  It clears when the phase ends or the row settles.
- **The convergence contract, restated.** If the record has
  a video, the section shows the video. If the save
  genuinely failed, the section says so truthfully with the
  storage-retry path (ADR 0148). The saving phase never sits
  silent past two minutes again.

## Consequences

The regression pins land with the fix: a backend test
stages a dead runner's leavings — a claimed job executed to
completion, its outcome recorded, the row still
`generating` — and proves the next poll applies the recorded
outcome without running the save pipeline a second time
(before the fix, the poll re-ran it). Two smoke checks pin
the notice: present for a saving row anchored three minutes
back; absent for a save that just began and for an
old-timestamped row still rendering at the provider.

What did not change: the `geq` camera-move graph, the 1800s
execution bound, the claim and lease semantics, the panel's
poll cadence and backoff, and History — it reads the same
endpoint and inherits the reconcile for free. The mural
sequence under the new behavior: the save still takes its
minutes (the encode is the encode, until Kasra rules on the
graph), but at two minutes the panel says what is happening
and why, and had that save's apply been lost at the last
step, the next poll would have landed the video from the
job's own record instead of starting the save over.
