"""Deployment health and export metrics: one router owns both reads.

/api/health says where user data is (and how much of it there is);
/api/metrics says whether the export path is working (outcome counters plus
request volume and uptime). server.py stays thin composition: it includes
this router and re-exports the helpers its tests and serializers still call.

Shared stateless deps (auth, observability) import here directly. The
DB-touching read (`_fetch_one`) and the live backend label stay owned by the
composition root — they resolve `server.DB_PATH` / `server._ACTIVE_BACKEND`
at call time, which is what every test redirects — and server injects them
via `configure_health` at include time. No import of server here, in either
direction: an unconfigured call fails loudly instead of half-working.
"""

from typing import Optional

from fastapi import APIRouter, Depends

import observability
import storage_service
from auth import get_current_user_id, hosted_environment

router = APIRouter()

_fetch_one = None
_get_active_backend = None
_get_turso_configured = None


def configure_health(fetch_one, get_active_backend, get_turso_configured=None):
    """Inject the composition root's DB read and backend label. Once at include."""
    global _fetch_one, _get_active_backend, _get_turso_configured
    _fetch_one = fetch_one
    _get_active_backend = get_active_backend
    _get_turso_configured = get_turso_configured


def _require_configured():
    if _fetch_one is None or _get_active_backend is None:
        raise RuntimeError("health router used before configure_health ran")


def _turso_configured() -> bool:
    # An unconfigured composition (a direct call in a test) keeps the older
    # judgement: the label is decided by the active backend alone.
    if _get_turso_configured is None:
        return True
    return bool(_get_turso_configured())


def health_database_report(active_backend: Optional[str], *, production: bool = False,
                           turso_configured: bool = True) -> dict:
    """
    The database half of /api/health, as a pure function of the active backend.

    Split out so the mapping can be asserted without standing up a cloud
    database, and so the endpoint body stays about reading rows rather than
    about deciding what they mean.

    `durable` is the field to read. Only "turso" means writes survive a restart;
    both local labels mean they do not, and on Render neither does. Reporting
    anything else here is the one genuinely dangerous thing this endpoint could
    say, because it is consulted precisely when someone has already lost data.

    The production case (ADR 0120, extending ADR 0083): a hosted process with
    no Turso configured is serving from ephemeral local SQLite — a store that
    is indistinguishable from unavailable the moment the host restarts. It is
    reported as `unavailable`, with the fix named in `database_detail`, rather
    than as a plain local label that reads like a choice someone made.
    """
    # An unset backend means the connection has not been opened yet. This
    # endpoint always reads rows before calling this, so in practice it is set;
    # the fallback only keeps a direct call honest.
    backend = active_backend or "local-sqlite"
    if production and not turso_configured and backend != "turso":
        return {
            "database": "unavailable",
            "durable": False,
            "database_detail": (
                "Production environment without TURSO_DATABASE_URL configured: "
                "this process is serving from ephemeral local SQLite, whose "
                "writes do not survive a restart. Set TURSO_DATABASE_URL and "
                "TURSO_AUTH_TOKEN for a durable database."
            ),
        }
    return {"database": backend, "durable": backend == "turso"}


@router.get("/health")
async def health(user_id: str = Depends(get_current_user_id)):
    """
    Where user data actually is right now, and how much of it there is.

    When Turso is configured but cannot connect or sync, `get_db` refuses to
    open local SQLite. The report then names `unavailable` and `durable: false`;
    it must never present an empty local store as though the founder's cloud
    data were deleted. Local-only development keeps its explicit local label.

    The backend is read AFTER the counts below on purpose: `get_db` re-establishes
    the active backend on every connection, so the value that matters is the store
    THIS request just used, not whatever the previous one happened to leave behind.
    Failed reads are named in their counts rather than converted to zeroes.

    The counts are scoped to the caller's own rows so this cannot be used to size
    up another account.

    Authenticated, because it reports inventory. A founder can read it from the
    browser console while signed in; an anonymous visitor learns nothing.
    """
    _require_configured()
    counts = {}
    for table in ("brand_profiles", "studio_projects", "generations"):
        try:
            row = await _fetch_one(
                f"SELECT COUNT(*) AS n FROM {table} WHERE user_id = ?", (user_id,)
            )
            counts[table] = int((row or {}).get("n") or 0)
        except Exception as exc:  # a missing table is itself the answer
            counts[table] = f"unavailable: {type(exc).__name__}"
    production = hosted_environment()
    report = health_database_report(
        _get_active_backend(),
        production=production,
        turso_configured=_turso_configured(),
    )
    media_durable = storage_service.is_configured()
    out = {
        "status": "ok",
        **report,
        "media_durable": media_durable,
        "your_rows": counts,
    }
    if production and not media_durable:
        # The media half of the same warning the startup log shouts (ADR
        # 0120): in production an unconfigured R2 means every finished
        # render is one deploy away from gone.
        out["media_warning"] = (
            "R2 is not configured: finished renders will not persist across "
            "deploys. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
            "R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME."
        )
    return out


@router.get("/metrics")
async def read_metrics(user_id: str = Depends(get_current_user_id)):
    """
    Export outcome counters plus request volume and uptime.

    Health-adjacent on purpose: /api/health says where user data is,
    this says whether the export path is working. Authenticated like
    /api/health — counters are operational, not public.
    """
    return observability.get_metrics()
