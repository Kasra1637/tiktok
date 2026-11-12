"""
Snapshot the app's database before a deploy, and restore a snapshot.

    python backup_db.py --snapshot
    python backup_db.py --list
    python backup_db.py --restore storage/backups/hookforge-backup-<stamp>.db --yes

Operator tooling, NOT a render path (same standing as repair_failed_saves).
The runbook in docs/operations.md names this as the pre-deploy backup step:
an image rollback does not reverse startup migrations or restore lost rows,
so the database gets its own snapshot-and-restore contract (ADR 0120).

Which file is "the database" follows the app's own resolution:

- Turso configured (TURSO_DATABASE_URL set): the libsql embedded replica,
  `hookforge.db` beside this script (db.py connects with that relative
  name, so it lives in the backend process's working directory). A SQLite
  snapshot of the replica preserves local state; for a cloud-side copy,
  also take a Turso dump — the replica can hold writes not yet synced.
- Otherwise: the local SQLite default, `storage/hookforge.db` (server's
  DB_PATH). --db PATH overrides either when the deployment differs.

Snapshots land in `storage/backups/` unless --out says otherwise. Restore
overwrites the target database and refuses to run without --yes; stop the
app first so no open connection fights the swap.
"""
import argparse
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

# Load .env BEFORE reading any configuration, so TURSO_DATABASE_URL is seen
# exactly as the app sees it.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

import db_backup  # noqa: E402

DEFAULT_BACKUP_DIR = BACKEND_DIR / "storage" / "backups"


def _active_db_path(explicit: str = "") -> Path:
    """The database file the app actually uses (see module docstring)."""
    if explicit:
        return Path(explicit)
    if os.environ.get("TURSO_DATABASE_URL", "").strip():
        return BACKEND_DIR / "hookforge.db"
    return BACKEND_DIR / "storage" / "hookforge.db"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", action="store_true",
                        help="take a timestamped snapshot of the active database")
    parser.add_argument("--restore", metavar="SNAPSHOT",
                        help="restore this snapshot over the active database")
    parser.add_argument("--list", action="store_true",
                        help="list snapshots in the backup directory")
    parser.add_argument("--db", default="",
                        help="database file to act on (default: the app's active store)")
    parser.add_argument("--out", default=str(DEFAULT_BACKUP_DIR),
                        help="backup directory (default: storage/backups)")
    parser.add_argument("--yes", action="store_true",
                        help="confirm a restore (it overwrites the target database)")
    args = parser.parse_args(argv)

    backup_dir = Path(args.out)
    db_path = _active_db_path(args.db)

    if args.list:
        snapshots = db_backup.list_snapshots(backup_dir)
        if not snapshots:
            print(f"no snapshots in {backup_dir}")
        for snap in snapshots:
            print(f"{snap}  ({snap.stat().st_size} bytes)")
        return 0

    if args.snapshot:
        snapshot = db_backup.snapshot_database(db_path, backup_dir)
        print(f"snapshot of {db_path} written to {snapshot}")
        return 0

    if args.restore:
        if not args.yes:
            print(
                f"refusing to restore without --yes: {args.restore} would "
                f"overwrite {db_path}. Stop the app first, then re-run "
                "with --yes.",
                file=sys.stderr,
            )
            return 2
        db_backup.restore_database(Path(args.restore), db_path)
        print(f"restored {args.restore} over {db_path}")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
