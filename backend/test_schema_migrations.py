"""
Versioned migrations: the bootstrap is now a recorded baseline, not folklore.

Before ADR 0120 the schema was whatever `apply_schema` happened to run: 20
tables of CREATE TABLE IF NOT EXISTS plus guarded ALTERs, with no record of
what had been applied to a given database and no ordering for future changes.
These tests pin the new contract:

- a fresh database and a database built by the pre-change bootstrap (the
  baseline body alone, no migration records, no jobs table) converge to the
  same schema and the same recorded versions after `apply_schema` runs;
- re-running `apply_schema` is a no-op for the migration record.
"""
import asyncio
import importlib
import os
import sys
import tempfile
from pathlib import Path

import aiosqlite
import pytest

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(scope="module")
def api():
    tmpdir = tempfile.mkdtemp(prefix="tiktok-migrations-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["OPENROUTER_API_KEY"] = "test-key-not-real"
    os.environ["CLERK_JWKS_URL"] = ""
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "test.db"
    try:
        yield server
    finally:
        sys.modules.pop("server", None)


def _schema_kwargs(api):
    return dict(
        analysis_frame_path=api._analysis_frame_path,
        normalize_analysis_frame=api._normalize_analysis_frame,
        normalize_template_thumbnail=api._normalize_template_thumbnail,
        generated_id_re=api.GENERATED_ID_RE,
    )


async def _apply(api, db_path, *, baseline_only=False):
    import schema

    conn = await aiosqlite.connect(str(db_path))
    try:
        if baseline_only:
            await schema._apply_baseline_schema(conn, **_schema_kwargs(api))
        else:
            await schema.apply_schema(conn, **_schema_kwargs(api))
    finally:
        await conn.close()


async def _fingerprint(db_path):
    """Schema shape only: objects, columns, and the migration record."""
    conn = await aiosqlite.connect(str(db_path))
    try:
        cur = await conn.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        )
        objects = [tuple(r) for r in await cur.fetchall()]
        columns = {}
        for obj_type, name, _tbl, _sql in objects:
            if obj_type != "table":
                continue
            cur = await conn.execute(f"PRAGMA table_info({name})")
            columns[name] = [
                (r[1], r[2], r[3], r[4], r[5]) for r in await cur.fetchall()
            ]
        versions = None
        cur = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='schema_migrations'"
        )
        if await cur.fetchone():
            cur = await conn.execute(
                "SELECT version, name FROM schema_migrations ORDER BY version"
            )
            versions = [tuple(r) for r in await cur.fetchall()]
        return objects, columns, versions
    finally:
        await conn.close()


class TestMigrationConvergence:
    def test_fresh_and_legacy_converge(self, api, tmp_path):
        async def main():
            fresh = tmp_path / "fresh.db"
            legacy = tmp_path / "legacy.db"

            # Legacy = exactly what the pre-change code produced: the
            # baseline body, no migration runner, no schema_migrations, no
            # jobs table.
            await _apply(api, legacy, baseline_only=True)
            _objs, _cols, legacy_versions = await _fingerprint(legacy)
            assert legacy_versions is None

            await _apply(api, fresh)
            await _apply(api, legacy)

            fresh_fp = await _fingerprint(fresh)
            legacy_fp = await _fingerprint(legacy)
            assert fresh_fp == legacy_fp

            versions = fresh_fp[2]
            assert versions is not None and len(versions) >= 2
            assert versions[0][0] == 1  # the recorded bootstrap baseline
            assert "jobs" in fresh_fp[1]  # the queue table arrived via a step

        asyncio.run(main())

    def test_rerun_is_a_noop_for_the_record(self, api, tmp_path):
        async def main():
            db_path = tmp_path / "twice.db"
            await _apply(api, db_path)
            first = await _fingerprint(db_path)
            await _apply(api, db_path)
            second = await _fingerprint(db_path)
            assert first == second

            conn = await aiosqlite.connect(str(db_path))
            try:
                cur = await conn.execute(
                    "SELECT version, applied_at FROM schema_migrations "
                    "ORDER BY version"
                )
                rows_first = [tuple(r) for r in await cur.fetchall()]
            finally:
                await conn.close()
            await _apply(api, db_path)
            conn = await aiosqlite.connect(str(db_path))
            try:
                cur = await conn.execute(
                    "SELECT version, applied_at FROM schema_migrations "
                    "ORDER BY version"
                )
                rows_again = [tuple(r) for r in await cur.fetchall()]
            finally:
                await conn.close()
            # No step re-ran and no record was rewritten.
            assert rows_first == rows_again

        asyncio.run(main())
