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

    def test_project_kind_step_is_recorded(self, api, tmp_path):
        async def main():
            import schema

            assert 7 in [step[0] for step in schema.MIGRATION_STEPS]

            db_path = tmp_path / "kind.db"
            await _apply(api, db_path)
            conn = await aiosqlite.connect(str(db_path))
            try:
                cur = await conn.execute(
                    "SELECT name FROM schema_migrations WHERE version = 7"
                )
                row = await cur.fetchone()
                assert row is not None and "kind" in row[0]

                cur = await conn.execute("PRAGMA table_info(studio_projects)")
                cols = {r[1]: r for r in await cur.fetchall()}
                assert "kind" in cols
                _cid, _name, col_type, notnull, dflt, _pk = cols["kind"]
                assert col_type == "TEXT"
                assert notnull == 1
                assert dflt == "'video'"
            finally:
                await conn.close()

        asyncio.run(main())

    def test_story_fields_step_is_recorded(self, api, tmp_path):
        async def main():
            import schema

            assert 8 in [step[0] for step in schema.MIGRATION_STEPS]

            db_path = tmp_path / "story-fields.db"
            await _apply(api, db_path)
            conn = await aiosqlite.connect(str(db_path))
            try:
                cur = await conn.execute(
                    "SELECT name FROM schema_migrations WHERE version = 8"
                )
                row = await cur.fetchone()
                assert row is not None and "story" in row[0]

                cur = await conn.execute("PRAGMA table_info(studio_projects)")
                project_cols = {r[1]: r for r in await cur.fetchall()}
                for name in ("story_type", "screen_text", "sticker_plan"):
                    assert name in project_cols
                    assert project_cols[name][2] == "TEXT"
                assert "frame_count" in project_cols
                assert project_cols["frame_count"][2] == "INTEGER"
                assert project_cols["frame_count"][4] == "1"

                cur = await conn.execute("PRAGMA table_info(generations)")
                generation_cols = {r[1]: r for r in await cur.fetchall()}
                assert "story_kit" in generation_cols
                assert generation_cols["story_kit"][2] == "TEXT"
            finally:
                await conn.close()

        asyncio.run(main())

    def test_project_surface_step_is_recorded(self, api, tmp_path):
        async def main():
            import schema

            assert schema.MIGRATION_STEPS[-3][0] == 9

            db_path = tmp_path / "surface.db"
            await _apply(api, db_path)
            conn = await aiosqlite.connect(str(db_path))
            try:
                cur = await conn.execute(
                    "SELECT name FROM schema_migrations WHERE version = 9"
                )
                row = await cur.fetchone()
                assert row is not None and "surface" in row[0]

                cur = await conn.execute("PRAGMA table_info(studio_projects)")
                cols = {r[1]: r for r in await cur.fetchall()}
                assert "surface" in cols
                _cid, _name, col_type, notnull, dflt, _pk = cols["surface"]
                assert col_type == "TEXT"
                # Nullable with no default: every row the wizard made,
                # and every existing row, reads NULL — only a surface
                # that marks its drafts writes a value (ADR 0244).
                assert notnull == 0
                assert dflt is None
            finally:
                await conn.close()

        asyncio.run(main())

    def test_project_voice_mode_step_is_recorded(self, api, tmp_path):
        async def main():
            import schema

            assert schema.MIGRATION_STEPS[-2][0] == 10

            db_path = tmp_path / "voice-mode.db"
            await _apply(api, db_path)
            conn = await aiosqlite.connect(str(db_path))
            try:
                cur = await conn.execute(
                    "SELECT name FROM schema_migrations WHERE version = 10"
                )
                row = await cur.fetchone()
                assert row is not None and "voice mode" in row[0]

                cur = await conn.execute("PRAGMA table_info(studio_projects)")
                cols = {r[1]: r for r in await cur.fetchall()}
                assert "voice_mode" in cols
                _cid, _name, col_type, notnull, dflt, _pk = cols["voice_mode"]
                assert col_type == "TEXT"
                # NOT NULL with the talking default: every existing row
                # reads as a talking project, which is the behavior it
                # always had (ADR 0246).
                assert notnull == 1
                assert dflt == "'talking'"
            finally:
                await conn.close()

        asyncio.run(main())

    def test_project_hook_picks_step_is_recorded(self, api, tmp_path):
        async def main():
            import schema

            assert schema.MIGRATION_STEPS[-1][0] == 11

            db_path = tmp_path / "hook-picks.db"
            await _apply(api, db_path)
            conn = await aiosqlite.connect(str(db_path))
            try:
                cur = await conn.execute(
                    "SELECT name FROM schema_migrations WHERE version = 11"
                )
                row = await cur.fetchone()
                assert row is not None and "hook picks" in row[0]

                cur = await conn.execute("PRAGMA table_info(studio_projects)")
                cols = {r[1]: r for r in await cur.fetchall()}
                assert "hook_focus" in cols
                _cid, _name, col_type, notnull, dflt, _pk = cols["hook_focus"]
                assert col_type == "TEXT"
                # Nullable with no default: the pick is the picked
                # outcome line verbatim, and an unpicked row carries
                # nothing — the app chooses (ADR 0247).
                assert notnull == 0
                assert dflt is None
                assert "hook_shape" in cols
                _cid, _name, col_type, notnull, dflt, _pk = cols["hook_shape"]
                assert col_type == "TEXT"
                # NOT NULL with the auto default: every existing row
                # reads as letting the app choose the hook's shape,
                # which is the behavior its hooks have always had.
                assert notnull == 1
                assert dflt == "'auto'"
            finally:
                await conn.close()

        asyncio.run(main())

    def test_existing_projects_become_video_and_story_rows_stay_story(
        self, api, tmp_path
    ):
        async def main():
            db_path = tmp_path / "kind-rows.db"

            # A database from before the step: baseline only, carrying a
            # project row written when no kind marker existed.
            await _apply(api, db_path, baseline_only=True)
            conn = await aiosqlite.connect(str(db_path))
            try:
                await conn.execute(
                    "INSERT INTO studio_projects (id) VALUES ('legacy-project')"
                )
                await conn.commit()
            finally:
                await conn.close()

            await _apply(api, db_path)
            conn = await aiosqlite.connect(str(db_path))
            try:
                cur = await conn.execute(
                    "SELECT kind FROM studio_projects WHERE id = 'legacy-project'"
                )
                (kind,) = await cur.fetchone()
                assert kind == "video"

                await conn.execute(
                    "INSERT INTO studio_projects (id, kind) "
                    "VALUES ('story-project', 'story')"
                )
                await conn.execute(
                    "INSERT INTO studio_projects (id) VALUES ('plain-project')"
                )
                await conn.commit()
                cur = await conn.execute(
                    "SELECT id, kind FROM studio_projects ORDER BY id"
                )
                rows = {r[0]: r[1] for r in await cur.fetchall()}
                assert rows == {
                    "legacy-project": "video",
                    "plain-project": "video",
                    "story-project": "story",
                }
            finally:
                await conn.close()

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
