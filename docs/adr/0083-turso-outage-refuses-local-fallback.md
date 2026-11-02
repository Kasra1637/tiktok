# 0083 — A Turso outage refuses local SQLite fallback

- **Status:** accepted
- **Date:** 2026-11-01
- **Anchors:** `backend/server.py:get_db`, `backend/routers/health.py:health_database_report`, `backend/test_database_backend.py`

## Context

When `TURSO_DATABASE_URL` was configured but the connection or boot sync failed,
`get_db` opened local SQLite and continued serving reads and writes. On an
ephemeral host that file could start empty and disappear on the next restart.
The UI then presented an empty profile or accepted new work into a different
store even though the cloud data still existed. Error-level logs and health
labels disclosed the fallback but did not prevent the divergence.

## Decision

A configured Turso database must connect and complete its initial sync before
any database request is served. A failure closes the replica, marks the active
backend `unavailable`, and raises an error naming recovery or an intentional
unset of `TURSO_DATABASE_URL` for local development. It never opens the local
SQLite fallback implicitly.

Health reports `unavailable` with `durable: false`, and startup logs the same
state as critical. Non-database routes may remain available after startup
retries; database routes fail until Turso recovers. An intentionally unconfigured
Turso URL still selects local SQLite for local development.

## Alternatives rejected

- **Keep the availability-first fallback:** preserves requests temporarily but
  can present cloud data as deleted and accept writes that are lost or require
  manual reconciliation.
- **Add an automatic local-to-cloud merge:** introduces conflict resolution and
  a separate recovery system rather than fixing the small durability contract.
- **Refuse local SQLite in every configuration:** unnecessarily breaks ordinary
  local development, where an explicitly selected persistent file is useful.

## Consequences

A Turso outage now causes visible database unavailability instead of silent
split-brain persistence. This deliberately trades short-term availability for
not losing or diverging user work. Existing local-only development is unchanged.

The change does not make local media durable, eliminate unsynchronized replica
write risk, provide a durable job queue, or make multi-instance coordination
safe. Those constraints remain separate operational work.
