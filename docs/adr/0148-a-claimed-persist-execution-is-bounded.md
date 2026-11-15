# ADR 0148: A claimed persist execution is bounded, so a hung save frees the video

Status: accepted

## Context

Kasra watched a finished render freeze live on Nov 14 2026: the panel
sat at the stitching stage with 7:28 elapsed and counting, the video
never appeared in the Render & result section or in History, and
"Check again" changed nothing. The render was not lost — the provider
had finished it. Its durable save was hung, and the queue machinery
ADR 0120/0138 built could not let go of it:

- The detached runner (ADR 0138) heartbeats the persist job's 300s
  lease every 60s for as long as the execution runs — with no overall
  bound. A step that hangs holds the claim forever.
- Every later poll re-enters `_persist_via_queue`, dedupes to that same
  claimed job (the enqueue is deduped per render — that suspect was
  innocent), finds it unclaimable under the live lease, and answers
  "generating". The startup sweep cannot rescue it either: the job
  never becomes claimable. While the process stays up, the loop is
  unbreakable and the row never leaves `generating`.

The steps inside the save mostly carry timeouts of their own — the
download's per-attempt httpx timeout (240s, three attempts), the
encode chain's 25–600s subprocess bounds, the storage client's
connect/read timeouts. Two gaps remained: nothing bounded the
execution as a whole, and the download's timeout is per socket
operation, so a source that drip-feeds bytes — each chunk arriving
just inside the read window — can hold one attempt open indefinitely
without ever tripping it.

## Decision

- **One bound, in the one executor.** `_execute_claimed_persist_job`
  runs the persist under `asyncio.wait_for` at
  `_PERSIST_EXECUTION_LIMIT_SECONDS` (1800). Every path — the detached
  runner, the inline queue path, the startup drain — already executes
  through this function, so the bound cannot drift between them.
- **A timeout is an ordinary failure, named.** It is converted to a
  RuntimeError that says the save timed out and was stopped, then
  flows through the existing bookkeeping unchanged: `_fail_job`
  requeues the job while attempts remain (parks it at max), and the
  caller applies the outcome through `_apply_persist_outcome` exactly
  as for any raised persist — the row lands at completed with the
  error named in `storage_error`, where the storage-retry endpoint
  already serves it. No new status is invented, and when the pipeline
  answers again the requeued job (or a fresh one, once the old is
  parked) drains and heals the row in place.
- **The heartbeat answers to the bound.** Its cadence is now the named
  `_PERSIST_HEARTBEAT_SECONDS` (60, unchanged); it still extends the
  lease for a save that is merely slow — ADR 0138's contract — and it
  stops with the execution when the bound cuts a hung one off (the
  runner's `finally` already cancels it).
- **The download attempt is capped as a whole.** Each attempt's stream
  runs under `_DOWNLOAD_ATTEMPT_LIMIT_SECONDS` (600). A stall becomes
  an ordinary failed attempt — partial file dropped, backoff, next
  attempt or candidate — instead of an invisible hang.
- **Sizing.** 1800s is three times the 600s the storage-retry request
  already budgets for this same pipeline, and every step inside
  carries a tighter timeout of its own, so a healthy save — a 2K
  download retrying, then the full encode chain — lands far inside
  the bound. The per-step timeouts make most stalls fail within
  minutes; the bound is the last resort that converts the rest from
  forever into a named, retryable error.

Not changed: the 300s lease, the 3-attempt requeue/park policy, the
drain's heartbeat-free execution (it claims at startup in a
single-process deployment; the bound now caps its exposure the same
way), and the storage/encode timeouts, which were already bounded per
call.

## Consequences

- A hung save resolves itself: within the bound at the very latest —
  and typically within one step's own timeout — the video leaves
  `generating` for the recoverable completed-with-storage-error state,
  with the retry the app already offers. Kasra's instruction was that
  this never happens again; the freeze is now a state the system exits
  on its own, not one only a restart could clear.
- Regression-pinned in `backend/test_persist_execution_bound.py` (its
  own file and database: the wiring suite's poll test counts the
  shared jobs table, and these tests enqueue jobs of their own): a
  never-returning persist is cut off by the bound, the row lands
  completed with the timeout named and the job released, and the
  requeued job later drains and heals the row; the drain is bounded
  the same way; and a slow save under the bound completes with its
  lease observably heartbeated mid-flight.
