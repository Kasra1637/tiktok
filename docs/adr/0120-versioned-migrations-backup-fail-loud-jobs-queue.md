# 0120 — Data durability: versioned migrations, operator backup, production fail-loud, and a jobs queue for post-render persistence

Status: accepted. Extends [0083](0083-turso-outage-refuses-local-fallback.md).

## Context

The audit's data & durability aspect sat at 7/10 on four concrete gaps:

- The schema bootstrap created twenty tables with idempotent
  `CREATE TABLE IF NOT EXISTS` plus guarded `ALTER`s. It converged, but
  nothing recorded *what had run* or in what order, so a future change
  had no discipline to land in — only folklore.
- There was no backup or restore path at all. The operations runbook
  said "back up the active store" and "an image rollback does not
  reverse startup migrations", but no command existed to do either.
- ADR 0083 refuses a silent local fallback when Turso is *configured but
  unreachable*. The neighbouring case was still quiet: a production
  process with Turso *not configured* booted on ephemeral local SQLite
  and health reported it as a plain `local-sqlite`, `durable: false` —
  technically true, easy to miss, and indistinguishable from a
  deliberate local setup until the first restart ate the data. R2
  unconfigured was quieter still: nothing anywhere said finished
  renders would not survive a deploy.
- The post-render durable save ran inline in the poll that noticed the
  provider finish, with the stranded-render sweep as the only net. A
  container dying between provider completion and the save left
  nothing recording that a persist was owed; the sweep recovered by
  re-polling the provider and hoping its URL still worked.

## Decision

**Migration discipline.** `schema.apply_schema` keeps the historical
bootstrap as the *baseline* and records it as version 1 in a new
`schema_migrations` table (version, name, applied_at). Later changes
append numbered steps to `MIGRATION_STEPS`; the runner applies each
unrecorded step once, in order, and records it. Re-running boot is a
no-op for the record and for the schema. Two rules keep this honest:

- A shipped step is never edited; a correction is a new step.
- The baseline body still runs every boot, because it also carries the
  curated-template seed/backfill — a per-boot data sync, not DDL.
  Object-level idempotency (`IF NOT EXISTS`, guarded `ALTER`s) stays as
  the convergence net for databases created before versioning, and the
  guarded `ALTER`s remain as repair for them. The record is the source
  of truth for *ordering*; convergence is proven by test (a fresh
  database and a pre-versioning database reach the same objects, the
  same columns, and the same recorded versions).

**Backup and restore are operator tooling** with the same standing as
`repair_failed_saves`: `backend/backup_db.py` over pure helpers in
`backend/db_backup.py`. Snapshots and restores go through SQLite's
backup API — never a raw file copy — so a snapshot is consistent even
while the app holds the file open in WAL mode, and both ends are
verified with `PRAGMA integrity_check`. Snapshot names are timestamped
so runs never overwrite each other. Restore overwrites the target,
refuses without `--yes`, and is run with the app stopped. The
pre-deploy snapshot and the restore procedure are steps in
`docs/operations.md`, not tribal knowledge. With Turso configured, the
script snapshots the embedded replica file the process actually uses,
and the runbook says to pair it with a cloud-side Turso dump, because
the replica can hold unsynced writes.

**Production durability fails loud, on the existing signal.** The
production signal is `auth.hosted_environment()` — Render markers
(`RENDER` / `RENDER_SERVICE_NAME`) or `ENVIRONMENT` / `APP_ENV` naming
production — the same signal the auth boot guard already uses
(ADR 0083's world), extracted so db, health, and startup logging all
read one definition instead of three near-copies. Under that signal:

- No Turso configured and the active backend is a local one: health
  reports `database: "unavailable"`, `durable: false`, and a
  `database_detail` naming the missing configuration. The startup
  database log escalates to CRITICAL with the same wording class it
  already used for Render.
- R2 not configured: startup logs CRITICAL that finished renders will
  not persist across deploys, and health adds `media_durable: false`
  plus a `media_warning` naming the four variables. `media_durable`
  is reported in every environment; the warning only fires in
  production.

The app still boots and serves in that state — the point is that the
condition is *named* everywhere an operator looks, not that a
misconfigured deploy takes itself down and hides its own health
endpoint. Local and development behavior is unchanged in every
particular, including the health labels.

**A jobs table with claim/lease semantics carries the persist.**
`jobs` (kind, JSON payload, dedupe key, status, attempts, max
attempts, worker, lease expiry, last error, result, timestamps) is
created by migration step 2, with the claim/complete/fail/heartbeat
primitives in `db.py`. Claiming is a single conditional UPDATE whose
row count is the proof of ownership — two workers cannot hold the same
job. A claim carries a lease (300s default); an expired lease makes
the job claimable again; a heartbeat extends only the holder's lease.
Attempts increment at claim. Failing requeues the job until its
attempt budget is spent, then parks it `failed` with the error kept.
Enqueue dedupes among active jobs, so a render's persist is owed
exactly once no matter how often it is recorded.

One path is wired through it, minimally: post-render persistence. When
poll sees a provider finish, it enqueues a `persist_generation_clip`
job — the provider URL rides in the payload — claims it, and runs the
unchanged `_persist_generation_clip`. The outcome is written by one
function, `_apply_persist_outcome`, used by both poll and the drain,
so the two paths cannot drift. The startup sweep drains queued
persists *before* re-polling stranded rows, completing a render whose
save was interrupted by a restart from the payload alone, without
re-asking the provider. If another worker holds the job when poll
claims it, poll answers with the row's current state and the panel
keeps polling — the same contract as a throttled status check. If the
persist raises, the job is failed back to the queue *and* the row
completes with `storage_error` named, exactly the behavior the inline
call had.

## Consequences

- Schema changes now have one way to land, and "which migrations has
  this database seen" is a query, not an inference.
- A deploy without a snapshot is now a skipped documented step, and a
  restore is a rehearsed command instead of an improvisation.
- A production deploy missing its durable stores says so in health and
  in CRITICAL startup logs, in the same places ADR 0083 taught
  operators to look.
- A restart between provider completion and durable save resumes from
  the jobs table instead of relying on the provider URL outliving the
  outage.
- Deliberately not built: no continuously running worker (the drain
  points are poll and the startup sweep, matching the app's
  single-process, request-driven shape); no external broker; the queue
  serves the one path that was stranding work — post-kit and poster
  generation remain best-effort background scheduling. `_submit_generation`
  remains the only render path, and provider polling semantics are
  untouched.
- The jobs table grows by one completed row per render. Nothing prunes
  it yet; at current volumes that is a deliberate trade for a complete
  audit trail of what was owed and what ran.

## Evidence

`backend/test_schema_migrations.py` (fresh vs pre-versioning convergence,
recorded versions, re-run no-op), `backend/test_db_backup.py` (snapshot →
mutate → restore round trip on temp databases), `backend/test_job_queue.py`
(claim exclusivity, lease-expiry reclaim, heartbeat ownership, retry
counting, dedupe), `backend/test_durability_fail_loud.py` (the production
signal, health labels, startup log levels, dev defaults unchanged),
`backend/test_persist_job_wiring.py` (poll completes through a claimed
job; a job orphaned by a dead worker's expired lease drains to a
completed render on the same database).
