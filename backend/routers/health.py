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
from auth import get_current_user_id

router = APIRouter()

_fetch_one = None
_get_active_backend = None


def configure_health(fetch_one, get_active_backend):
    """Inject the composition root's DB read and backend label. Once at include."""
    global _fetch_one, _get_active_backend
    _fetch_one = fetch_one
    _get_active_backend = get_active_backend


def _require_configured():
    if _fetch_one is None or _get_active_backend is None:
        raise RuntimeError("health router used before configure_health ran")


def health_database_report(active_backend: Optional[str]) -> dict:
    """
    The database half of /api/health, as a pure function of the active backend.

    Split out so the mapping can be asserted without standing up a cloud
    database, and so the endpoint body stays about reading rows rather than
    about deciding what they mean.

    `durable` is the field to read. Only "turso" means writes survive a restart;
    both local labels mean they do not, and on Render neither does. Reporting
    anything else here is the one genuinely dangerous thing this endpoint could
    say, because it is consulted precisely when someone has already lost data.
    """
    # An unset backend means the connection has not been opened yet. This
    # endpoint always reads rows before calling this, so in practice it is set;
    # the fallback only keeps a direct call honest.
    backend = active_backend or "local-sqlite"
    return {"database": backend, "durable": backend == "turso"}


@router.get("/health")
async def health(user_id: str = Depends(get_current_user_id)):
    """
    Where user data actually is right now, and how much of it there is.

    This exists because "my profile and videos disappeared" has one cause that
    is not deletion. When Turso is configured but unreachable, `get_db` falls
    back to local SQLite so the app keeps serving — and on Render that file is
    on an ephemeral disk, so it starts EMPTY. Every list then renders as "no
    profiles", which reads exactly like the app deleting the founder's work. The
    cloud copy is usually untouched; the process is simply pointed at the wrong
    store.

    That distinction is a one-glance question here and was previously only
    answerable by digging through the deploy log, which is why the report above
    kept arriving as "the app deleted my data". The backend is read AFTER the
    counts below on purpose: `get_db` re-establishes the active backend on every
    connection, so the value that matters is the store THIS request just used,
    not whatever the previous one happened to leave behind.

    The counts are the other half — "ephemeral, and empty" and "ephemeral, and
    holding 40 generations" need different responses, and only the numbers
    distinguish them. Scoped to the caller's own rows so this cannot be used to
    size up another account.

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
    return {
        "status": "ok",
        **health_database_report(_get_active_backend()),
        "your_rows": counts,
    }


@router.get("/metrics")
async def read_metrics(user_id: str = Depends(get_current_user_id)):
    """
    Export outcome counters plus request volume and uptime.

    Health-adjacent on purpose: /api/health says where user data is,
    this says whether the export path is working. Authenticated like
    /api/health — counters are operational, not public.
    """
    return observability.get_metrics()
