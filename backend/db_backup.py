"""
Consistent SQLite snapshots and restores for the operator backup tool.

Split out of backup_db.py so the round trip can be asserted against temp
databases without booting the server, loading .env, or touching whatever
keys a developer's machine happens to hold — the same reason
recovery_report is split out of repair_failed_saves.

Snapshots go through SQLite's backup API, never a raw file copy: the API
reads a consistent database even while the app holds the file open in WAL
mode, where copying the .db file alone can capture a torn state and lose
the writes still sitting in the -wal sidecar. Every snapshot and every
restore is verified with PRAGMA integrity_check before it is trusted.
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


def _integrity_ok(path: Path) -> bool:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        return row is not None and row[0] == "ok"
    finally:
        conn.close()


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def snapshot_database(source: Path, backup_dir: Path) -> Path:
    """
    Snapshot `source` into `backup_dir` and return the snapshot path.

    Names are timestamped to the microsecond so two snapshots in the same
    second never overwrite each other. Raises FileNotFoundError for a
    missing source and RuntimeError when the snapshot fails its integrity
    check — a backup that cannot be verified is reported, not filed away.
    """
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"database to snapshot does not exist: {source}")
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"hookforge-backup-{_stamp()}.db"

    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    if not _integrity_ok(target):
        target.unlink(missing_ok=True)
        raise RuntimeError(f"snapshot failed its integrity check: {target}")
    return target


def restore_database(snapshot: Path, target: Path) -> None:
    """
    Restore `snapshot` over `target` (created when missing).

    The snapshot is verified before anything is overwritten, and the
    restored database is verified after. Run this with the app stopped:
    the backup API writes a consistent database, but a running app's open
    connections are not coordinated with the swap.
    """
    snapshot = Path(snapshot)
    if not snapshot.is_file():
        raise FileNotFoundError(f"snapshot to restore does not exist: {snapshot}")
    if not _integrity_ok(snapshot):
        raise RuntimeError(f"snapshot failed its integrity check: {snapshot}")
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    src = sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True)
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    if not _integrity_ok(target):
        raise RuntimeError(f"restored database failed its integrity check: {target}")


def list_snapshots(backup_dir: Path) -> list:
    """Snapshot files in a backup directory, oldest first."""
    backup_dir = Path(backup_dir)
    if not backup_dir.is_dir():
        return []
    return sorted(backup_dir.glob("hookforge-backup-*.db"))
