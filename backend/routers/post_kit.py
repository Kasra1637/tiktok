"""Frozen post copy for a finished render: one router owns it all.

The kit is written once at completion, read through the existing generation
endpoints, and replaced only by an explicit click on regenerate. server.py
stays thin composition: it includes this router and re-exports the helpers
its serializers and completion hook still call.

Shared stateless deps (auth, models, ai_service) import here directly. The
DB-touching helpers (`_fetch_one`, `_execute`, `_log_model_call`) stay owned
by the composition root — they resolve `server.DB_PATH` at call time, which
is what every test redirects — and server injects them via
`configure_post_kit` at include time. No import of server here, in either
direction: an unconfigured call fails loudly instead of half-working.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

import ai_service
from ai_service import TEXT_MODEL
from auth import get_current_user_id
from models import now_iso

logger = logging.getLogger(__name__)

router = APIRouter()

_fetch_one = None
_execute = None
_log_model_call = None


def configure_post_kit(fetch_one, execute, log_model_call):
    """Inject the composition root's DB helpers. Called once at include time."""
    global _fetch_one, _execute, _log_model_call
    _fetch_one = fetch_one
    _execute = execute
    _log_model_call = log_model_call


def _require_configured():
    if _fetch_one is None or _execute is None or _log_model_call is None:
        raise RuntimeError("post_kit router used before configure_post_kit ran")


def _parse_post_kit(value) -> Optional[dict]:
    """The frozen post kit for a generation, or None when never written."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


async def _schedule_post_kit(
    background_tasks: BackgroundTasks, generation_id: str, user_id: str
) -> None:
    """Kit work runs after the response, never inside it.

    On HTTP the work is deferred to BackgroundTasks; direct (non-HTTP)
    callers such as tests pass None and run it inline. Same contract as
    _schedule_poster.
    """
    if background_tasks is not None:
        background_tasks.add_task(_maybe_write_post_kit, generation_id, user_id)
        return
    await _maybe_write_post_kit(generation_id, user_id)


async def _load_post_kit_materials(generation_row: dict, user_id: str):
    """The render material a post kit is grounded in, or (None, None).

    One owner for the two reads every kit path needs. Missing material is
    not an error here — the frozen writer skips quietly while regenerate
    answers 404 — so that policy stays at the call sites.
    """
    _require_configured()
    project = None
    if generation_row.get("studio_project_id"):
        project = await _fetch_one(
            "SELECT hook_line, script, cta FROM studio_projects WHERE id = ? AND user_id = ?",
            (generation_row["studio_project_id"], user_id),
        )
    profile = None
    if generation_row.get("brand_profile_id"):
        profile = await _fetch_one(
            "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?",
            (generation_row["brand_profile_id"], user_id),
        )
    return project, profile


async def _maybe_write_post_kit(generation_id: str, user_id: str) -> Optional[dict]:
    """Write the frozen post kit for a freshly completed render, once.

    Best-effort by design: a kit failure logs loudly and leaves the column
    NULL rather than failing the completion or inventing copy. A later poll
    finds post_kit set and returns it untouched.
    """
    _require_configured()
    current = await _fetch_one(
        "SELECT post_kit, studio_project_id, brand_profile_id FROM generations WHERE id = ?",
        (generation_id,),
    )
    if not current:
        return None
    if _parse_post_kit(current.get("post_kit")) is not None:
        return None
    project, profile = await _load_post_kit_materials(current, user_id)
    if not project or not profile:
        logger.warning(
            "Post kit skipped for generation %s: render material not found.", generation_id)
        return None
    try:
        kit = await _log_model_call(
            "post_kit", "text", TEXT_MODEL,
            lambda: ai_service.generate_post_kit(project, profile),
            user_id,
            brand_profile_id=current.get("brand_profile_id"),
            studio_project_id=current.get("studio_project_id"),
            generation_id=generation_id,
        )
    except Exception as e:
        logger.warning("Post kit generation failed for %s: %s", generation_id, e)
        return None
    if not isinstance(kit, dict):
        logger.warning("Post kit generation returned no kit for %s.", generation_id)
        return None
    await _execute(
        "UPDATE generations SET post_kit = ?, updated_at = ? "
        "WHERE id = ? AND (post_kit IS NULL OR post_kit = '')",
        (json.dumps(kit), now_iso(), generation_id),
    )
    return kit


@router.post("/generations/{generation_id}/post-kit/regenerate")
async def regenerate_post_kit(
    generation_id: str, user_id: str = Depends(get_current_user_id)
):
    """Write a fresh post kit for a render and replace the saved one.

    Click-only by construction: nothing else calls generate_post_kit. A
    failure answers loudly and leaves the stored kit untouched.
    """
    _require_configured()
    row = await _fetch_one(
        "SELECT post_kit, studio_project_id, brand_profile_id, status FROM generations WHERE id = ? AND user_id = ?",
        (generation_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")
    if str(row.get("status") or "") not in ("completed", "archived"):
        raise HTTPException(
            status_code=409, detail="Only finished renders can regenerate post copy."
        )
    project, profile = await _load_post_kit_materials(row, user_id)
    if not project or not profile:
        raise HTTPException(
            status_code=404, detail="Render material not found for a fresh post kit."
        )
    try:
        kit = await _log_model_call(
            "post_kit", "text", TEXT_MODEL,
            lambda: ai_service.generate_post_kit(project, profile),
            user_id,
            brand_profile_id=row.get("brand_profile_id"),
            studio_project_id=row.get("studio_project_id"),
            generation_id=generation_id,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not regenerate post copy: {str(e)[:800]}")
    if not isinstance(kit, dict):
        raise HTTPException(status_code=502, detail="Could not regenerate post copy: empty response.")
    await _execute(
        "UPDATE generations SET post_kit = ?, updated_at = ? WHERE id = ?",
        (json.dumps(kit), now_iso(), generation_id),
    )
    return {"post_kit": kit}
