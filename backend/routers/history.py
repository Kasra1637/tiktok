"""Generation history: list, detail, poll, retry, archive, and delete.

One router owns the `/generations` and `/history/generations` endpoints that
read or update a render after it has been submitted: both history listings,
detail, provider polling, the durable-save retry, the failed-render retry,
the TikTok link and view-count fields, archive, and delete. Routes are moved
verbatim from `server.py`; the wrapper is an `APIRouter` included under the
existing `/api` prefix.

The render lifecycle they drive stays in the composition root:
`_submit_generation` is still the sole submit path, and
`_persist_generation_clip` still owns download/trim/upload. This module
resolves those helpers, the DB helpers, and the row serializers through
`_cfg` over the `_server` back-reference, so the tests that patch
`server.<name>` keep intercepting at call time (same mechanism as
`db._server`/`db._cfg`). No import of server here, in either direction: an
unconfigured call fails loudly instead of half-working. `server.py`
re-exports the handlers and `_run_storage_repair` for existing callers.
"""

import asyncio
import logging
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

import ai_service
import generation_planning
import media_signing
import pipeline
import posters
import storage_service
import video_providers
from auth import get_current_user_id
from models import TikTokLinkRequest, TikTokViewsRequest, now_iso

logger = logging.getLogger(__name__)

router = APIRouter()

_server = None


def _cfg(name, default=None):
    """Read a live binding from the composition root.

    Call sites resolve through this so test monkeypatching of
    `server.<name>` is seen at call time, never a stale import-time binding.
    """
    if _server is None:
        raise RuntimeError("history router used before configure_history ran")
    return getattr(_server, name, default)


def configure_history(server):
    """Inject the composition root. Called once at include time."""
    global _server
    _server = server


def _fetch_one(*a, **k):
    return _cfg("_fetch_one")(*a, **k)


def _fetch_all(*a, **k):
    return _cfg("_fetch_all")(*a, **k)


def _execute(*a, **k):
    return _cfg("_execute")(*a, **k)


def _log_model_call(*a, **k):
    return _cfg("_log_model_call")(*a, **k)


def _public_generation(*a, **k):
    return _cfg("_public_generation")(*a, **k)


def _public_generation_detail(*a, **k):
    return _cfg("_public_generation_detail")(*a, **k)


def _with_verdicts(*a, **k):
    return _cfg("_with_verdicts")(*a, **k)


def _persist_generation_clip(*a, **k):
    return _cfg("_persist_generation_clip")(*a, **k)


def _recovery_sources(*a, **k):
    return _cfg("_recovery_sources")(*a, **k)


def _schedule_post_kit(*a, **k):
    return _cfg("_schedule_post_kit")(*a, **k)


def _schedule_poster(*a, **k):
    return _cfg("_schedule_poster")(*a, **k)


def _playback_url(*a, **k):
    return _cfg("_playback_url")(*a, **k)


def _poster_url(*a, **k):
    return _cfg("_poster_url")(*a, **k)


def _parse_post_kit(*a, **k):
    return _cfg("_parse_post_kit")(*a, **k)


def _require_renderable_project(*a, **k):
    return _cfg("_require_renderable_project")(*a, **k)


def _assert_within_single_pass_cap(*a, **k):
    return _cfg("_assert_within_single_pass_cap")(*a, **k)


def _submit_generation(*a, **k):
    return _cfg("_submit_generation")(*a, **k)


def _request_id(*a, **k):
    return _cfg("_request_id")(*a, **k)


def _with_request_id(*a, **k):
    return _cfg("_with_request_id")(*a, **k)


def poll_video_job(*a, **k):
    return _cfg("poll_video_job")(*a, **k)


@router.get("/generations")
async def list_generations(
    studio_project_id: str = "",
    brand_profile_id: str = "",
    status: str = "",
    limit: int = 50,
    user_id: str = Depends(get_current_user_id),
):
    """Generation history, newest first."""
    clauses = ["user_id = ?"]
    params: list = [user_id]
    if studio_project_id.strip():
        clauses.append("studio_project_id = ?")
        params.append(studio_project_id.strip())
    if brand_profile_id.strip():
        clauses.append("brand_profile_id = ?")
        params.append(brand_profile_id.strip())
    if status.strip():
        clauses.append("status = ?")
        params.append(status.strip().lower())
    rows = await _fetch_all(
        f"""SELECT * FROM generations WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC LIMIT ?""",
        tuple(params) + (max(1, min(int(limit or 50), 200)),),
    )
    out = [_public_generation(r) for r in rows]
    await _with_verdicts(out, user_id)
    return {"generations": out}


@router.get("/generations/{generation_id}")
async def get_generation(generation_id: str, user_id: str = Depends(get_current_user_id)):
    # `demo_brief` rides along from the project. It is the plan's note telling
    # the founder what to record for their own demo, and the Demo + CTA editor —
    # the one screen where that footage is actually added — opens through this
    # endpoint. Without it here the founder had to leave the editor and reopen
    # Review to remember what they were told to show. The LEFT JOIN keeps the
    # standalone case working: a row with no project (an export filed with no
    # Hook + Story behind it, or a project deleted since) simply carries None,
    # and the editor renders no note rather than an empty one.
    row = await _fetch_one(
        """SELECT g.*, p.demo_brief
             FROM generations g
             LEFT JOIN studio_projects p ON p.id = g.studio_project_id
            WHERE g.id = ? AND g.user_id = ?""",
        (generation_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")
    return await _with_verdicts(_public_generation_detail(row), user_id)


@router.post("/generations/{generation_id}/poll")
async def poll_generation(
    generation_id: str,
    user_id: str = Depends(get_current_user_id),
    background_tasks: BackgroundTasks = None,
    request: Request = None,
):
    """
    Refresh a generation's status and resolve a finished clip to a URL.

    Poll is the only place a completed clip is resolved to a URL and handed to
    persistent storage, so a completed generation always has a durable copy
    even if the provider's links later expire.
    """
    rid = (request.state.request_id if request is not None and getattr(request, "state", None) else "") or _request_id()
    logger.info("poll_generation id=%s user=%s request_id=%s", generation_id, user_id, rid)
    row = await _fetch_one(
        "SELECT * FROM generations WHERE id = ? AND user_id = ?", (generation_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")
    if row.get("status") in ("completed", "archived"):
        return await _with_verdicts(_public_generation_detail(row), user_id)

    job_id = row.get("openrouter_job_id")
    if not job_id:
        raise HTTPException(
            status_code=409,
            detail="This generation was never submitted to the provider.",
        )

    try:
        response = await _log_model_call(
            "video_poll", "video", row.get("model") or "",
            lambda: poll_video_job(job_id),
            user_id,
            brand_profile_id=row.get("brand_profile_id"),
            studio_project_id=row.get("studio_project_id"),
            generation_id=generation_id,
            template_id=row.get("template_id"),
        )
    except Exception as e:
        message = str(e)
        if generation_planning.is_rate_limit_error(message):
            # Throttled status check, not a broken render — words owned by
            # planning; the row is untouched and the panel keeps waiting.
            raise HTTPException(
                status_code=429,
                detail=generation_planning.RATE_LIMIT_POLL_DETAIL,
            )
        await _execute(
            "UPDATE generations SET error = ?, retryable = ?, updated_at = ? WHERE id = ?",
            (message[:2000], 1 if generation_planning.is_recoverable_error(message) else 0,
             now_iso(), generation_id),
        )
        raise HTTPException(status_code=502, detail=f"Could not check generation status: {message[:800]}")

    status = str(response.get("status") or "").lower()
    urls = response.get("unsigned_urls") or response.get("urls") or []
    video_url = urls[0] if isinstance(urls, list) and urls else response.get("video_url") or ""
    if not video_url:
        # A completed job can arrive with no URL list at all. The content
        # endpoint is derivable from the job id we already hold, and it is what
        # those URLs point at anyway, so use it rather than completing the row
        # with nothing playable and an empty video_url.
        video_url = ai_service.video_content_url(job_id)
        if video_url:
            logger.info(
                f"Generation {generation_id}: poll returned no URL for job {job_id}; "
                f"using the provider content endpoint instead."
            )
    now = now_iso()

    if status in ("completed", "succeeded", "success") and video_url:
        stored_url = None
        storage_error = None
        delivered_seconds = int(row.get("duration") or 0)
        # Persist locally first so the clip survives even if R2 is unconfigured.
        # _persist_generation_clip owns the whole sequence -- download, trim,
        # rescale, upload, local fallback -- because retry_generation_storage
        # runs the identical pipeline to repair a row that already failed, and
        # two copies of this is how the studio downloader ended up without the
        # bearer token the legacy one always sent.
        #
        # It also resolves the precedence for us: a real problem outranks a
        # trim note, so "the upload fell back to local storage" is never
        # overwritten by "Cut down to 5s", and a clean run reports neither.
        try:
            stored_url, storage_error, delivered_seconds = await _persist_generation_clip(
                row, user_id, video_url
            )
        except Exception as e:
            storage_error = str(e)[:500]
            logger.warning(f"Generation {generation_id}: storage step failed: {e}")

        await _execute(
            "UPDATE generations SET status = 'completed', video_url = ?, r2_url = ?, "
            "duration = ?, error = NULL, storage_error = ?, completed_at = ?, updated_at = ? "
            "WHERE id = ?",
            (video_url, stored_url or "", delivered_seconds,
             storage_error or None, now, now, generation_id),
        )
        if stored_url:
            await _execute(
                "UPDATE video_assets SET r2_url = ? WHERE job_id = ?", (stored_url, generation_id)
            )
        # Frozen post copy, written once at completion and deferred past the
        # response like the poster: a kit failure leaves NULL, never invented
        # copy. A NULL kit renders as no kit.
        await _schedule_post_kit(background_tasks, generation_id, user_id)
        if stored_url:
            # Poster is best-effort and off the critical path: History works
            # without it, it just costs video bytes per thumbnail. Scheduled
            # after the response so the save never stacks two ffmpegs.
            await _schedule_poster(background_tasks, generation_id, user_id)
    elif status in ("failed", "error", "cancelled", "canceled", "expired"):
        # "expired" is terminal but arrived here as infinite "generating":
        # OpenRouter lists it in the status enum, yet it matched none of the
        # failure branches, so the row polled forever with no banner. Name it
        # plainly: the provider discarded the job, its clip is not
        # recoverable, and retrying renders it anew (a fresh render, not a
        # repair — recovery of this clip is no longer possible).
        if status == "expired":
            message = (
                "The provider discarded this render job before it could be "
                "saved (expired). Its clip is no longer recoverable; retrying "
                "renders it anew."
            )
            retryable = 1
        else:
            message = str(response.get("error") or response.get("message") or "Generation failed.")
            retryable = 1 if generation_planning.is_recoverable_error(message) else 0
        await _execute(
            "UPDATE generations SET status = 'failed', error = ?, retryable = ?, completed_at = ?, "
            "updated_at = ? WHERE id = ?",
            (message[:1000], retryable,
             now_iso(), now_iso(), generation_id),
        )
    else:
        await _execute(
            "UPDATE generations SET status = 'generating', updated_at = ? WHERE id = ?",
            (now, generation_id),
        )

    return await _with_verdicts(_public_generation_detail(
        await _fetch_one("SELECT * FROM generations WHERE id = ?", (generation_id,))
    ), user_id)


@router.post("/generations/{generation_id}/storage/retry")
async def retry_generation_storage(
    generation_id: str,
    user_id: str = Depends(get_current_user_id),
    background_tasks: BackgroundTasks = None,
):
    """
    Retry durable storage for a completed generation.

    This is separate from retrying a failed render: the video itself is done,
    but its durable copy failed.

    It runs the same pipeline the poll path does, via _persist_generation_clip,
    because a download failure and an upload failure need different repairs:

    - Upload failed, local file survived -> re-upload that file. One PUT.
    - Download failed -> the partial file was deleted, so the only copy left is
      the provider's, and the retry re-fetches it. This is the case the old
      endpoint could not service at all: it demanded a local file that the
      failure had just removed, so the button the panel offered for a download
      failure was guaranteed to answer 409. That is how a finished render could
      sit finished and unrecoverable behind a "Retry durable save" button.

    Recovery checks the exact owner's R2 object before a provider source.
    Relative media paths are local locators, never network download sources.
    Native exports have no provider rendition and must never be substituted
    with their parent render. If every copy is gone, re-upload is required.

    It no longer refuses when R2 is unconfigured. _persist_generation_clip falls
    back to serving the local copy, which is a watchable, downloadable result;
    an error the founder can do nothing about is strictly worse than that.
    """
    row = await _fetch_one(
        "SELECT * FROM generations WHERE id = ? AND user_id = ?", (generation_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")
    if row.get("status") != "completed":
        raise HTTPException(
            status_code=409,
            detail="Storage can be retried only after the video has completed.",
        )

    local_path = pipeline.VIDEOS_DIR / f"{generation_id}.mp4"
    if generation_id in _cfg("_storage_repairs_in_flight"):
        # Not an error so much as an answer: the work is already happening, and a
        # second run would fight the first one for the same file.
        raise HTTPException(
            status_code=409,
            detail=(
                "A durable save for this render is already running. It can take a "
                "few minutes; wait for it to finish rather than starting another."
            ),
        )
    _cfg("_storage_repairs_in_flight").add(generation_id)
    try:
        # Resolved through _cfg at call time so the tests that patch
        # server._run_storage_repair still intercept (the arrival test for
        # the single-flight guard), even though the repair lives here.
        return await _cfg("_run_storage_repair")(row, generation_id, user_id, local_path, background_tasks)
    finally:
        _cfg("_storage_repairs_in_flight").discard(generation_id)


async def _run_storage_repair(
    row: dict,
    generation_id: str,
    user_id: str,
    local_path: Path,
    background_tasks: BackgroundTasks = None,
):
    """The body of a durable-save repair, run under the single-flight guard."""
    # Same test the helper uses, so this log line describes what will actually
    # happen rather than what is merely on disk.
    has_local = await asyncio.to_thread(storage_service.is_usable_video, local_path)
    durable, source = _recovery_sources(row)
    if not has_local and not durable and not source and not storage_service.is_configured():
        raise HTTPException(
            status_code=409,
            detail=(
                "This video has no local copy and no cloud or provider copy to recover, "
                "so it cannot be recovered. Re-upload your saved export if you have it."
            ),
        )

    logger.info(
        f"Retrying durable storage for generation {generation_id}: "
        f"usable local copy={'yes' if has_local else 'no'}, "
        f"provider link={'yes' if source else 'no'}"
    )
    try:
        stored_url, storage_error, _delivered = await _persist_generation_clip(row, user_id)
    except Exception as e:
        logger.error("Storage retry failed for %s (%s)", generation_id, type(e).__name__)
        raise HTTPException(status_code=502, detail="Storage recovery failed. Please try again.")

    if not stored_url:
        # The helper already phrased this for the founder and knows which half
        # failed -- nothing to work from, or a download that was refused. Pass
        # it through rather than flattening it, because the two need different
        # actions from the founder.
        raise HTTPException(
            status_code=502,
            detail=storage_error or "Storage retry failed without a provider error.",
        )

    await _execute(
        "UPDATE generations SET r2_url = ?, storage_error = ?, updated_at = ? WHERE id = ?",
        (stored_url, storage_error or None, now_iso(), generation_id),
    )
    await _execute(
        "UPDATE video_assets SET r2_url = ? WHERE job_id = ?", (stored_url, generation_id)
    )
    logger.info("Generation %s: saved copy recovered", generation_id)
    await _schedule_poster(background_tasks, generation_id, user_id)
    return {"id": generation_id,
            "r2_url": media_signing.sign_stored_path(stored_url),
            "playback_url": media_signing.build_signed_path(f"{generation_id}.mp4"),
            "poster_url": media_signing.build_signed_poster_path(f"{generation_id}.jpg"),
            "storage_error": storage_error or None}


@router.post("/generations/{generation_id}/retry", status_code=202)
async def retry_generation(generation_id: str, user_id: str = Depends(get_current_user_id), request: Request = None):
    """
    Replace a failed segment.

    The new attempt is recorded as a child of the failed generation rather
    than overwriting it, so the failure stays in history — a failed generation
    that is silently replaced makes the history read as though it worked.
    """
    row = await _fetch_one(
        "SELECT * FROM generations WHERE id = ? AND user_id = ?", (generation_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")
    if row.get("status") != "failed":
        raise HTTPException(
            status_code=409,
            detail="Only a failed generation can be retried. This one is "
                   f"'{row.get('status')}'.",
        )
    if not row.get("retryable"):
        raise HTTPException(
            status_code=409,
            detail="This failure is not retryable: " + str(row.get("error") or "")[:200],
        )

    project_id = row.get("studio_project_id")
    if not project_id:
            raise HTTPException(
                status_code=409, detail=_with_request_id("Cannot retry: this generation is not tied to a studio project.")
            )

    # Same gates as a fresh render, and for the same reason. This path used to
    # load the project, profile and template by id and call _submit_generation
    # directly, so it inherited none of the submit checks: a project edited back
    # to draft, or an App Profile no longer approved, still spent real money.
    # A retry is the same render, so it answers to the same questions.
    project, profile, template = await _require_renderable_project(project_id, user_id)

    # The retry reuses the recorded model and length rather than accepting new
    # ones, so the question is whether those choices are still valid. Both used
    # to drift silently: _submit_generation clamps a length past the model's cap
    # and video_providers.resolve() falls back to the default for a model that
    # has left the allowlist. Either way the founder got one render and got
    # another -- a different model, or a shorter clip than the plan describes.
    # Refusing is cheaper than a surprise.
    model_key = row.get("model") or ""
    if model_key:
        resolved, reason = video_providers.resolve(model_key)
        if resolved != model_key:
            # video_providers.capability() falls back to the default for an
            # unknown key, so it would name the wrong model here. Use the
            # recorded key verbatim and let resolve() explain the substitution.
            raise HTTPException(
                status_code=409,
                detail=_with_request_id(
                    f"This retry was recorded on {model_key!r}, which is no longer usable "
                    f"({reason}). Pick a model and generate again rather than retrying, "
                    "so you know what the render will use."
                ),
            )
    wanted = row.get("duration")
    if wanted:
        _assert_within_single_pass_cap(model_key or video_providers.default_model_key(), int(wanted))

    return await _submit_generation(
        project=project,
        profile=profile,
        template=template,
        user_id=user_id,
        model=row.get("model") or "",
        duration=row.get("duration"),
        segment_role=row.get("segment_role") or "primary",
        segment_index=int(row.get("segment_index") or 0),
        attempt=int(row.get("attempt") or 1) + 1,
    )


@router.post("/generations/{generation_id}/tiktok-link")
async def set_generation_tiktok_link(
    generation_id: str, payload: TikTokLinkRequest, user_id: str = Depends(get_current_user_id)
):
    row = await _fetch_one(
        "SELECT id FROM generations WHERE id = ? AND user_id = ?", (generation_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")
    link = (payload.tiktok_url or "").strip()
    if link:
        if len(link) > 500:
            raise HTTPException(status_code=400, detail="That link is too long to be a TikTok URL.")
        try:
            parts = urlsplit(link)
        except ValueError:
            raise HTTPException(status_code=400, detail="That is not a TikTok link. Paste the video's tiktok.com URL.")
        host = (parts.hostname or "").lower()
        if (parts.scheme not in ("http", "https")
                or not (host == "tiktok.com" or host.endswith(".tiktok.com"))
                or parts.username is not None or parts.password is not None):
            raise HTTPException(status_code=400, detail="That is not a TikTok link. Paste the video's tiktok.com URL.")
    await _execute(
        "UPDATE generations SET tiktok_url = ?, updated_at = ? WHERE id = ?",
        (link or None, now_iso(), generation_id),
    )
    return await _with_verdicts(_public_generation_detail(
        await _fetch_one("SELECT * FROM generations WHERE id = ?", (generation_id,))
    ), user_id)


@router.post("/generations/{generation_id}/tiktok-views")
async def set_generation_tiktok_views(
    generation_id: str, payload: TikTokViewsRequest, user_id: str = Depends(get_current_user_id)
):
    row = await _fetch_one(
        "SELECT id FROM generations WHERE id = ? AND user_id = ?", (generation_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")
    stored = payload.tiktok_views
    if stored is not None and not 0 <= stored <= 10_000_000_000:
        raise HTTPException(status_code=400, detail="Views must be a whole number from 0 to 10 billion.")
    stamped = now_iso()
    await _execute(
        "UPDATE generations SET tiktok_views = ?, tiktok_views_at = ?, updated_at = ? WHERE id = ?",
        (stored, stamped if stored is not None else None, stamped, generation_id),
    )
    return await _with_verdicts(_public_generation_detail(
        await _fetch_one("SELECT * FROM generations WHERE id = ?", (generation_id,))
    ), user_id)


@router.post("/generations/{generation_id}/archive")
async def archive_generation(generation_id: str, user_id: str = Depends(get_current_user_id)):
    row = await _fetch_one(
        "SELECT id FROM generations WHERE id = ? AND user_id = ?", (generation_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")
    await _execute(
        "UPDATE generations SET status = 'archived', updated_at = ? WHERE id = ?",
        (now_iso(), generation_id),
    )
    return await _with_verdicts(_public_generation_detail(
        await _fetch_one("SELECT * FROM generations WHERE id = ?", (generation_id,))
    ), user_id)


@router.get("/history/generations")
async def generation_history(
    brand_profile_id: str = "",
    status: str = "",
    limit: int = 100,
    user_id: str = Depends(get_current_user_id),
):
    """
    Generation history with everything needed to judge a result at a glance:
    profile, template, objective, duration, status, and output links.
    The script itself stays on the detail endpoint to keep this list light.
    """
    clauses = ["g.user_id = ?"]
    params: list = [user_id]
    if brand_profile_id.strip():
        clauses.append("g.brand_profile_id = ?")
        params.append(brand_profile_id.strip())
    if status.strip():
        clauses.append("g.status = ?")
        params.append(status.strip().lower())

    rows = await _fetch_all(
        f"""SELECT g.id, g.studio_project_id, g.brand_profile_id, g.template_id,
                   g.template_version, g.script_version, g.model, g.duration,
                   g.status, g.segment_role, g.attempt, g.video_url,
                   g.r2_url, g.error, g.retryable, g.created_at, g.completed_at,
                   g.post_kit, g.tiktok_url, g.tiktok_views, g.tiktok_views_at, g.location,
                   b.brand_name, p.objective, p.hook_line, p.demo_brief, p.audience,
                   p.strategy_version, ca.kind AS angle_kind
            FROM generations g
            LEFT JOIN studio_projects p ON p.id = g.studio_project_id
            LEFT JOIN content_angles ca ON ca.id = p.content_angle_id
            LEFT JOIN brand_profiles b ON b.id = g.brand_profile_id
            WHERE {' AND '.join(clauses)}
            ORDER BY g.created_at DESC LIMIT ?""",
        tuple(params) + (max(1, min(int(limit or 100), 500)),),
    )

    out = []
    for row in rows:
        entry = dict(row)
        entry["retryable"] = bool(entry.get("retryable"))
        # This endpoint builds its rows by hand rather than through
        # _public_generation, so both media paths have to be signed here too.
        # Both, because this is the one row whose player and download take
        # `r2_url || video_url`. Signing only video_url left the field the
        # browser actually asks for unsigned, so the now-signed media route
        # answered the <video> with a 404 — the "Preview unavailable" that
        # appears instead of the clip whenever the durable copy is the local
        # fallback path written when the R2 upload returned None.
        entry["video_url"] = media_signing.sign_stored_path(entry.get("video_url"))
        entry["r2_url"] = media_signing.sign_stored_path(entry.get("r2_url"))
        entry["playback_url"] = _playback_url(row)
        entry["poster_url"] = _poster_url(row)
        entry["post_kit"] = _parse_post_kit(entry.get("post_kit"))
        entry["tiktok_url"] = (entry.get("tiktok_url") or "").strip() or None
        views = entry.get("tiktok_views")
        entry["tiktok_views"] = int(views) if views is not None else None
        entry["tiktok_views_at"] = entry.get("tiktok_views_at")
        entry["composition"] = None
        out.append(entry)
    await _with_verdicts(out, user_id)
    return {"generations": out}


@router.delete("/generations/{generation_id}")
async def delete_generation(generation_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Delete a generation and its derived records.

    Archiving is usually the better choice: the row keeps the render, its
    prompt, and its verdict while dropping it from the working list. Delete is
    for removing something that was never usable.
    """
    row = await _fetch_one(
        "SELECT * FROM generations WHERE id = ? AND user_id = ?", (generation_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")

    await _execute("DELETE FROM video_assets WHERE job_id = ?", (generation_id,))
    await _execute("DELETE FROM generations WHERE id = ? AND user_id = ?", (generation_id, user_id))
    try:
        storage_service.delete_video(user_id, generation_id)
    except Exception as e:
        logger.warning(f"R2 delete failed for generation {generation_id}: {e}")
    try:
        storage_service.delete_poster(user_id, generation_id)
    except Exception as e:
        logger.warning(f"R2 poster delete failed for generation {generation_id}: {e}")
    for local in (pipeline.VIDEOS_DIR / f"{generation_id}.mp4",
                  posters.poster_path(generation_id)):
        try:
            if local.is_file():
                local.unlink()
        except OSError as e:
            logger.warning(f"Could not remove {local}: {e}")
    logger.info(f"Deleted generation {generation_id}")
    return {"deleted": generation_id}
