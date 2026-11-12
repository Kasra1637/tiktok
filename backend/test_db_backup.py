"""
Database snapshot/restore for the operator backup tool (ADR 0120).

The helpers in db_backup are stdlib-only on purpose: the restore path is
exercised here against temp databases without booting the server, loading
.env, or touching whatever keys a developer's machine happens to hold —
the same reason recovery_report is split out of repair_failed_saves.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

import db_backup


def _make_db(path: Path, rows):
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE things (id TEXT PRIMARY KEY, note TEXT)")
    conn.executemany("INSERT INTO things (id, note) VALUES (?, ?)", rows)
    conn.commit()
    conn.close()


def _read_rows(path: Path):
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute("SELECT id, note FROM things ORDER BY id").fetchall()
    finally:
        conn.close()


class TestSnapshotRestore:
    def test_round_trip_restores_rows(self, tmp_path):
        source = tmp_path / "live.db"
        _make_db(source, [("a", "first"), ("b", "second")])

        snapshot = db_backup.snapshot_database(source, tmp_path / "backups")
        assert snapshot.is_file()

        # The live database moves on after the snapshot.
        conn = sqlite3.connect(str(source))
        conn.execute("DELETE FROM things WHERE id = 'a'")
        conn.execute("INSERT INTO things (id, note) VALUES ('c', 'third')")
        conn.commit()
        conn.close()
        assert _read_rows(source) == [("b", "second"), ("c", "third")]

        db_backup.restore_database(snapshot, source)
        assert _read_rows(source) == [("a", "first"), ("b", "second")]

    def test_snapshots_are_timestamped_and_distinct(self, tmp_path):
        source = tmp_path / "live.db"
        _make_db(source, [("a", "first")])
        one = db_backup.snapshot_database(source, tmp_path / "backups")
        two = db_backup.snapshot_database(source, tmp_path / "backups")
        assert one != two
        assert one.parent == two.parent == tmp_path / "backups"

    def test_snapshot_of_missing_source_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            db_backup.snapshot_database(tmp_path / "nope.db", tmp_path / "backups")

    def test_restore_creates_a_missing_target(self, tmp_path):
        source = tmp_path / "live.db"
        _make_db(source, [("a", "first")])
        snapshot = db_backup.snapshot_database(source, tmp_path / "backups")
        target = tmp_path / "restored.db"
        db_backup.restore_database(snapshot, target)
        assert _read_rows(target) == [("a", "first")]

    def test_restore_of_missing_snapshot_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            db_backup.restore_database(tmp_path / "nope.db", tmp_path / "out.db")
