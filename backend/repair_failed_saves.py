"""
One-off repair for generations whose durable save failed on the download.

    .venv\\Scripts\\python.exe repair_failed_saves.py --dry-run
    .venv\\Scripts\\python.exe repair_failed_saves.py

Background. `unsigned_urls` is a misleading name: OpenRouter's video URLs are
not presigned, so downloading one that points at the OpenRouter API needs the
bearer token. The studio's downloader did not send it, so every completed
render came back HTTP 401 at the moment its durable copy was taken. The clip
was finished the whole time; only the copy was missing.

The recovery path had a second problem, which is why this script exists at all
rather than a note to click the button: a failed download DELETES the partial
local file, and the retry endpoint used to demand a local file. So the button
offered for that exact failure answered 409 every time. Both are fixed now.

This walks the affected rows and runs the real repair endpoint's logic against
each, so it repairs exactly what the UI would -- no second code path to drift.

Scope: rows with a non-empty storage_error, a status of completed, and no
stored URL. Ordered oldest first, because a provider content URL is likelier
to have expired the longer ago a row sits there, and a row that can still be
recovered is worth taking first.

Reads and writes the live database. --dry-run reports without changing
anything. Exits non-zero if any row could not be repaired.
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

# Load .env BEFORE importing anything that reads a key at import time.
# ai_service captures OPENROUTER_API_KEY at module scope, so importing it first
# and loading dotenv second would silently send no bearer token -- which is the
# exact bug being repaired here.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

os.environ.setdefault("TURSO_DATABASE_URL", "")
os.environ.setdefault("CLERK_JWKS_URL", "")

import server  # noqa: E402


async def _candidates() -> list:
    return await server._fetch_all(
        "SELECT id, user_id, model, duration, video_url, openrouter_job_id, "
        "r2_url, storage_error, created_at "
        "FROM generations "
        "WHERE status = 'completed' AND storage_error IS NOT NULL AND storage_error != '' "
        "ORDER BY created_at ASC"
    )


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report what would be repaired without changing anything.",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Stop after this many rows. 0 means no limit.",
    )
    parser.add_argument(
        "--user", default="",
        help="Only repair rows belonging to this user id.",
    )
    parser.add_argument(
        "--db", default="",
        help="Point at a specific SQLite file instead of the configured one.",
    )
    args = parser.parse_args()

    if not server.ai_service.OPENROUTER_API_KEY:
        print("OPENROUTER_API_KEY is not set, so no clip can be re-fetched.")
        print("Load it from backend/.env, or set it in this shell, and retry.")
        return 2

    if args.db:
        server.DB_PATH = Path(args.db)
        server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        print(f"Using database {server.DB_PATH}")

    # Boot the schema first. Every app start runs this, and it is what adds
    # columns like storage_error to a database created before they existed --
    # without it this script fails on an older local file rather than reporting
    # "nothing to repair", which reads like a bug in the script.
    try:
        await server.init_db()
    except Exception as exc:
        print(f"Could not initialise the database schema: {exc}")
        print("That database looks older than the app's migrations can repair.")
        print("Point --db at the deployed database, or restore from a backup.")
        return 2

    rows = await _candidates()
    if args.user:
        rows = [r for r in rows if r.get("user_id") == args.user]
    if args.limit:
        rows = rows[: args.limit]

    if not rows:
        print("Nothing to repair: no completed row carries a storage_error.")
        return 0

    print(f"{len(rows)} completed row(s) carry a storage_error.\n")
    repaired, failed, skipped = [], [], 0

    for row in rows:
        label = f"{row['id'][:8]} {row.get('model') or '?'} {row.get('duration') or '?'}s"
        print(f"--- {label}")
        print(f"    error : {row['storage_error']}")
        print(f"    video : {row.get('video_url') or '(none stored)'}")
        print(f"    job   : {row.get('openrouter_job_id') or '(none)'}")

        if args.dry_run:
            local = server.pipeline.VIDEOS_DIR / f"{row['id']}.mp4"
            usable = server._is_complete_mp4(local)
            link = bool(
                row.get("video_url")
                or server.ai_service.video_content_url(row.get("openrouter_job_id") or "")
            )
            if not usable and not link:
                print("    verdict: UNRECOVERABLE (no local copy, no provider link)")
                skipped += 1
            else:
                source = "local copy" if usable else "re-fetch from provider"
                print(f"    verdict: would repair via {source}")
            print()
            continue

        try:
            result = await server.retry_generation_storage(row["id"], row["user_id"])
        except Exception as exc:
            detail = getattr(exc, "detail", None) or str(exc)
            print(f"    verdict: FAILED -- {detail}")
            failed.append((row["id"], detail))
            print()
            continue

        print(f"    verdict: REPAIRED -> {result.get('r2_url')}")
        if result.get("storage_error"):
            print(f"               note: {result['storage_error']}")
        repaired.append(row["id"])
        print()

    print("=" * 60)
    if args.dry_run:
        print(f"dry run: {len(rows)} row(s) examined, nothing written.")
        return 0
    print(f"repaired: {len(repaired)}   failed: {len(failed)}   unrecoverable: {skipped}")
    for gen_id, detail in failed:
        print(f"  FAILED {gen_id}: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))