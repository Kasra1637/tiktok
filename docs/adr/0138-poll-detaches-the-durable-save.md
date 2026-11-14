# ADR 0138: The completion poll hands the durable save to its BackgroundTasks

Status: accepted

## Context

The founder's report: when a render finishes, the finished video does not
appear in the render area; the progress sits at its "generating" stage
(the panel's staged bar reads 85%) and only a logout/refresh reveals the
clip in History. The render completes and persists server-side; the live
page never transitions.

The evidence indicted the poll request itself. `poll_generation` is the
only path that resolves a finished provider job, and its completion
branch ran the entire durable save — download, hook trim, canvas
rescale, R2 upload (`_persist_generation_clip` via ADR 0120's queue) —
inline before it could answer. The client's poll carries the axios
default timeout of 120s (`pollGeneration` has no override), while the
storage retry of the very same pipeline carries 600s — the codebase
already knew this pipeline outlasts 120s. So on any long save:

1. the browser aborted the poll at 120s, mid-persist;
2. the request's work died with it, leaving the queue job `claimed`
   under its 300s lease — and nothing heartbeated leases
   (`_heartbeat_job` had no production caller);
3. later polls either answered "generating" against the live lease, or,
   after it lapsed, re-claimed and restarted the save from scratch into
   the same 120s abort — an unbreakable loop while the panel stayed open;
4. the row only ever completed when an unattached run executed the save:
   the startup sweep's queue drain after a cold start — the founder's
   logout/refresh — or a later re-poll that found the download already
   on disk and skipped to the upload.

The panel's own chain was not the failure: it polls every 6s, tolerates
429s and transient failures within budgets, and re-arms on visibility and
mount. It simply never received a terminal row, because no poll it could
make was capable of producing one.

## Decision

- When the provider reports completion, the poll endpoint still records
  and claims the persist job synchronously (ADR 0120's guarantee: the
  owed save is in the table before anything else happens), but the
  claimed job's execution is handed to the response's `BackgroundTasks`
  (`_run_detached_persist`). The poll answers immediately with the row's
  current state — the same "still generating, keep polling" contract a
  throttled status check already used — and the outcome is applied when
  the save finishes; the panel's next poll (6s cadence) serves the
  completed row.
- The detached runner heartbeats the job's lease every 60s, so a save
  longer than the 300s lease is never re-claimed mid-flight (no second
  poll can start a duplicate save — dedupe plus the live lease answer
  "generating"). A failure inside the save fails the job back to the
  queue (existing behavior) and applies the failure outcome to the row
  with the error named, exactly as the inline path's caller did.
- Detach requires the BackgroundTasks carrier a live request provides.
  Without one — the sweep's drains, direct calls in tests — the save
  runs inline, the same convention the post-kit scheduling already
  follows (`_schedule_post_kit` runs inline when `background_tasks` is
  None). Production polls always carry one, so production always
  detaches. The storage-retry endpoint keeps its own inline run and its
  600s client budget; it is a deliberate repair action, not a poll.

## Consequences

- A completion poll's response time is the provider status check alone;
  no client timeout can abort the save it noticed, and the live panel
  flips to the finished preview within one poll interval of the save
  landing — no remount, reload, or cold start involved.
- ADR 0120's durability story is unchanged: a container death mid-save
  leaves the claimed job in the table, its lease lapses, and the startup
  sweep drains it. The difference is that an ordinary long save no
  longer depends on that path.
- Tests pin the new boundary: a poll whose save is blocked still answers
  "generating" promptly, a concurrent poll starts no second save, the
  completion lands when the background work runs (queue job completed,
  dedupe key intact), and the post-kit deferral test now asserts the
  whole completion — save and kit — lands after the poll response.
