"""SQLite/Turso data layer: connections, schema bootstrap, and row helpers.

This module owns every database primitive the app runs on — the Turso
embedded-replica connection (with boot sync and the refuse-local-fallback
rule), the libsql async wrappers, `init_db` schema creation, the `_fetch_one`
/`_fetch_all`/`_execute` helpers, and the model/asset event ledger writes.

Composition root stays `server.py`: it imports this module, injects the
helpers into routers via `configure_*`, and re-exports the names its tests
and other modules call. The mutable configuration those tests redirect at
runtime (`DB_PATH`, `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`, `_ACTIVE_BACKEND`,
`_TURSO_BOOT_SYNC_DONE`) stays owned by `server` — they are plain module
attributes there, and `db.py` resolves them through `_server` (set once at
import time) so a test that does `server.DB_PATH = tmp` changes the value this
module actually connects with. No import of `server` here; `_server` is
assigned, never imported, keeping the dependency one-way.
"""

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

import aiosqlite

from models import now_iso, row_to_dict

# Log under the composition root's logger so caplog filters on logger="server"
# (and any production log routing keyed on it) keep seeing the DB messages
# exactly as before the extraction.
logger = logging.getLogger("server")

# Set by server.py right after importing this module. The composition root
# owns the mutable DB configuration (its tests redirect server.<name>), and
# this module reads that live config through this reference at call time.
_server = None


def _cfg(name, default=None):
    """Read a live config value from the composition root."""
    return getattr(_server, name, default) if _server is not None else default


def _set_cfg(name, value):
    """Write a live config value back to the composition root."""
    if _server is not None:
        setattr(_server, name, value)


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

def _database_backend() -> str:
    """
    Which store this process is actually writing user data to.

    "turso" means the cloud database (survives redeploys); "local-sqlite"
    means a file on this machine's disk. The distinction is the difference
    between a profile surviving a deploy and silently vanishing with it, so
    anything that reports on the health of the deployment reads this rather
    than guessing from config.
    """
    return "turso" if _cfg("TURSO_DATABASE_URL") else "local-sqlite"


def _log_database_backend() -> None:
    """
    Say, once per boot and impossible to miss, where user data is going.

    Profiles vanishing on every deploy is exactly what local SQLite on an
    ephemeral host does, and it looks from the outside like the app "deleting"
    things. If that is the configuration, the deploy log must say so in plain
    language instead of letting the next data-loss report be the discovery.

    Reports the ACTUAL backend established by get_db (module global), not the
    configured one: a previous version logged "Turso cloud" from config while
    the connection had in fact fallen back to ephemeral, which is precisely
    backwards. Call only after init_db has run, so the actual value exists.
    """
    actual = _cfg("_ACTIVE_BACKEND")
    if actual == "turso" or (actual is None and _database_backend() == "turso"):
        # "turso" as an actual value is only ever set after a real
        # connect+pull succeeded, so this line can no longer claim cloud
        # persistence while running ephemeral. (The None branch covers a call
        # before any connection was opened; init_db always connects first.)
        logger.info("Database backend: Turso cloud — user data survives redeploys.")
        return
    if actual == "unavailable":
        logger.critical(
            "Database unavailable: Turso could not connect or sync. Refusing local "
            "SQLite fallback; database requests will fail until Turso recovers."
        )
        return
    if actual == "local-ephemeral-fallback":
        message = (
            "Database backend: EPHEMERAL local SQLite — Turso is configured but "
            "unreachable, so user data (profiles, projects, generations) will "
            "NOT survive a redeploy or restart."
        )
    else:
        message = (
            f"Database backend: local SQLite at {_cfg('DB_PATH')}. User data (profiles, "
            "projects, generations) will NOT survive a redeploy or restart."
        )
    if os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_NAME"):
        # Render sets these itself, so their presence means this process is on
        # Render's ephemeral filesystem rather than a dev laptop. Local SQLite
        # here is a data-loss configuration, not a dev default.
        logger.critical(
            message + " Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN (see render.yaml) "
            "or every deploy wipes the database."
        )
    elif actual == "local-ephemeral-fallback":
        logger.error(message)
    else:
        logger.info(message + " (fine for local dev)")


@asynccontextmanager
async def get_db():
    """Async context manager for database connections.

    When TURSO_DATABASE_URL is set, connects to a remote Turso database via
    libsql_experimental (cloud-persisted, survives Render redeploys).
    Otherwise falls back to local aiosqlite (for dev/testing).
    """
    use_turso = False
    if _cfg("TURSO_DATABASE_URL"):
        conn = None
        try:
            import libsql_experimental as libsql
            conn = libsql.connect(
                "hookforge.db",
                sync_url=_cfg("TURSO_DATABASE_URL"),
                auth_token=_cfg("TURSO_AUTH_TOKEN"),
            )
            # No PRAGMA journal_mode=WAL here, deliberately — and it must stay
            # out. Journal mode is a local-SQLite concern (kept on the local
            # branch below); on a libsql embedded replica the statement is
            # unsupported, and issuing it took down the whole Turso branch, so
            # every boot fell back to ephemeral storage while the config said
            # "Turso cloud". Durability on a replica comes from sync, not from
            # pragmas.
            #
            # Pull cloud state into the replica before anything reads it. A
            # freshly deployed container starts with an empty replica file, and
            # without this the first reads see no profiles at all — which looks
            # exactly like "the deploy deleted everything" even when the cloud
            # copy is intact. Retried on every connection until one succeeds
            # (flag stays False), so recovery from a blip is automatic; a
            # failed pull is FATAL to this attempt and refuses local fallback,
            # because an unsynced replica is operationally identical to local
            # SQLite while reporting as Turso — the worst combination.
            if not _cfg("_TURSO_BOOT_SYNC_DONE"):
                conn.sync()
                _set_cfg("_TURSO_BOOT_SYNC_DONE", True)
            use_turso = True
            _set_cfg("_ACTIVE_BACKEND", "turso")
        except Exception as e:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            _set_cfg("_ACTIVE_BACKEND", "unavailable")
            logger.error("Turso connection failed; refusing local SQLite fallback: %s", e)
            raise RuntimeError(
                "Turso is configured but unavailable; refusing to write to local SQLite. "
                "Restore Turso, or unset TURSO_DATABASE_URL intentionally for local development."
            ) from e
    else:
        _set_cfg("_ACTIVE_BACKEND", "local-sqlite")

    if use_turso:
        try:
            yield _LibsqlAsyncWrapper(conn)
        finally:
            conn.close()
    else:
        local_conn = await aiosqlite.connect(str(_cfg("DB_PATH")))
        local_conn.row_factory = aiosqlite.Row
        await local_conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield local_conn
        finally:
            await local_conn.close()


class _LibsqlAsyncWrapper:
    """
    Thin wrapper that gives a libsql_experimental sync connection the same
    async interface that aiosqlite provides (await conn.execute(), await
    conn.commit(), etc.) so the rest of the codebase doesn't need changes.
    """

    def __init__(self, conn):
        self._conn = conn

    async def execute(self, sql, params=()):
        return _CursorWrapper(self._conn.execute(sql, params))

    async def executescript(self, sql):
        self._conn.executescript(sql)
        self._conn.commit()
        if hasattr(self._conn, "sync"):
            try:
                self._conn.sync()
            except Exception as e:
                logger.warning(f"Turso sync after executescript failed (local replica is safe): {e}")

    async def commit(self):
        self._conn.commit()
        # Sync local embedded replica to/from Turso cloud.
        # Network hiccups during sync must not crash the caller — unsynced
        # writes are still durable in the local embedded replica and will be
        # pushed on the next successful sync.
        if hasattr(self._conn, "sync"):
            try:
                self._conn.sync()
            except Exception as e:
                logger.warning(f"Turso sync failed (writes are safe in local replica): {e}")

    async def close(self):
        pass  # handled by get_db's finally block


class _CursorWrapper:
    """Wraps a libsql cursor to provide awaitable fetchone/fetchall + description."""

    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def description(self):
        return self._cursor.description

    async def fetchone(self):
        return self._cursor.fetchone()

    async def fetchall(self):
        return self._cursor.fetchall()


async def _fetch_one(query: str, params: tuple = ()) -> Optional[dict]:
    """Fetch one row as a dict, or None."""
    async with get_db() as conn:
        cursor = await conn.execute(query, params)
        cols = [d[0] for d in cursor.description]
        row = await cursor.fetchone()
        if row is None:
            return None
        return row_to_dict(row, cols)


async def _fetch_all(query: str, params: tuple = ()) -> list:
    """Fetch all rows as list of dicts."""
    async with get_db() as conn:
        cursor = await conn.execute(query, params)
        cols = [d[0] for d in cursor.description]
        rows = await cursor.fetchall()
        return [row_to_dict(r, cols) for r in rows]


async def _execute(query: str, params: tuple = ()):
    """Execute a write query and commit."""
    async with get_db() as conn:
        await conn.execute(query, params)
        await conn.commit()


async def _record_model_request(
    operation: str,
    modality: str,
    model: str,
    status: str,
    latency_ms: int,
    user_id: str,
    error: str = "",
    brand_profile_id: str = "",
    studio_project_id: str = "",
    generation_id: str = "",
    template_id: str = "",
    research_run_id: str = "",
):
    """
    Persist one provider interaction for operations visibility.

    Prompts and generated copy are deliberately not stored. Operations needs to
    know that a request happened, which model handled it, and whether it
    worked — not the creative material itself.
    """
    await _execute(
        """INSERT INTO model_requests
           (id, operation, modality, model, status, latency_ms, error,
            brand_profile_id, studio_project_id, generation_id, template_id,
            research_run_id, created_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), operation, modality, model, status, int(latency_ms),
         (error or "")[:500],
         brand_profile_id or None, studio_project_id or None,
         generation_id or None, template_id or None, research_run_id or None,
         now_iso(), user_id),
    )


async def _record_asset_event(
    kind: str,
    reason: str,
    user_id: str,
    brand_profile_id: str = "",
    studio_project_id: str = "",
    generation_id: str = "",
    asset_id: str = "",
    asset_kind: str = "",
    filename: str = "",
):
    """Persist an asset failure that would otherwise exist only as an HTTP error."""
    await _execute(
        """INSERT INTO asset_events
           (id, kind, reason, brand_profile_id, studio_project_id, generation_id,
            asset_id, asset_kind, filename, created_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), kind, reason[:500],
         brand_profile_id or None, studio_project_id or None,
         generation_id or None, asset_id or None, asset_kind or None,
         (filename or "")[:200], now_iso(), user_id),
    )


async def _log_model_call(operation, modality, model, call, user_id, **refs):
    """
    Run one retained provider call and ledger its outcome.

    Centralizing this keeps operations honest: a failed research, plan, or poll
    is recorded with its latency before the route converts it into an HTTP
    error. Only metadata is stored; prompts and generated copy are not, and
    nothing about what the call cost is recorded.
    """
    started = time.perf_counter()
    try:
        result = await call()
    except Exception as exc:
        await _record_model_request(
            operation, modality, model, "failed",
            int((time.perf_counter() - started) * 1000), user_id,
            error=str(exc), **refs,
        )
        raise
    await _record_model_request(
        operation, modality, model, "completed",
        int((time.perf_counter() - started) * 1000), user_id,
        **refs,
    )
    return result


async def init_db():
    """Create tables if they don't exist. Schema body lives in schema.py."""
    from schema import apply_schema
    _cfg("DB_PATH").parent.mkdir(parents=True, exist_ok=True)
    srv = _server
    async with get_db() as conn:
        await apply_schema(
            conn,
            analysis_frame_path=srv._analysis_frame_path,
            normalize_analysis_frame=srv._normalize_analysis_frame,
            normalize_template_thumbnail=srv._normalize_template_thumbnail,
            generated_id_re=srv.GENERATED_ID_RE,
        )
