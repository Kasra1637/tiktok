import asyncio
import hashlib
import io
import json
import logging
import os
import re
import sys
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

import aiosqlite  # re-exported for tests that monkeypatch aiosqlite.connect
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse, RedirectResponse
from PIL import Image
from starlette.middleware.cors import CORSMiddleware

import pipeline
import storage_service
import posters
import template_library
import angle_scene
import final_beat
import opening_move
import scene_consistency
import creative_quality
import media_signing
import video_providers
import generation_planning
import recommendation_tags
from template_recommendations import (
    score_template_for_angle as _score_template_for_angle,
    split_shared_notes as _split_shared_notes,
    filter_relevant_templates as _filter_relevant_templates,
    check_template_relevance as _check_template_relevance,
)
import overlays
import provider_capabilities
import ai_service
import feedback as feedback_mod
import observability
from ai_service import (
    generate_video,
    poll_video_job, analyze_app_profile,
    generate_content_angles, generate_angle_goals, generate_creative_plan,
    page_text_with_metadata,
    TEXT_MODEL, ANGLE_MODEL,
    generate_video_strategy, normalize_strategy, generate_brand_templates,
    bind_spoken_words, spoken_budget,
)
from models import (
    AppProfileResearchRequest, ApproveAppProfileRequest,
    BrandProfileCreateRequest, BrandProfileUpdateRequest,
    CreateContentAngleRequest, UpdateContentAngleRequest,
    GenerateContentAnglesRequest,
    CreateStudioProjectRequest, UpdateStudioProjectRequest, GeneratePlanRequest,
    ObjectiveTemplatesRequest,
    StudioGenerationRequest,     UpdateAssetRequest, AttachAssetRequest,
    FeedbackRequest, TikTokLinkRequest, TikTokViewsRequest,
    GenerateStrategyRequest, OpeningMessagesRequest,
    DemoCtaUploadCompleteRequest, RefreshDirectionOptionsRequest,
    RewriteHookRequest,
    APP_PROFILE_LIST_FIELDS,
    APP_PROFILE_EDITABLE_FIELDS,
    STUDIO_EDITABLE_FIELDS, STUDIO_TEXT_FIELDS,
    now_iso, row_to_dict,
)
from auth import ensure_auth_configured, get_current_user_id, get_optional_user_id, hosted_environment

# Anonymous mode is local-dev-only: refuse to boot hosted without a Clerk
# key, so production can never serve every request as user 'anonymous'.
ensure_auth_configured()

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

DB_PATH = ROOT_DIR / "storage" / "hookforge.db"

app = FastAPI(title="HookForge API")
api_router = APIRouter(prefix="/api")

# Domain routers own their endpoints; server.py keeps composition (include +
# re-exported helpers) and the single render path. Post kit first: the
# frozen copy and its regenerate endpoint live in routers.post_kit.
from routers.post_kit import (
    router as post_kit_router,
    configure_post_kit,
    _parse_post_kit,
    _schedule_post_kit,
    regenerate_post_kit,
)
api_router.include_router(post_kit_router)
from routers.health import (
    router as health_router,
    configure_health,
    health_database_report,
    health,
    read_metrics,
)
api_router.include_router(health_router)

# Brand profile, content angle, and template-library routes (single owner in
# routers.brands), re-exporting the helpers remaining studio/generation code
# and tests still call from `server`.
from routers.brands import (
    router as brands_router,
    configure_brands,
    _normalize_url, _normalize_str_list, _normalize_objection_value,
    _normalize_outcome_value, _brand_update_parts, _cap_page_text,
    _fetch_url_text_owned as _fetch_url_text,
    _approval_gaps, _founder_verified_context, _research_profile_sources,
    _serialize_angle_row, _serialize_profile_angles, _public_library_template,
    _public_template,
    _angle_feedback_for_profile, _generation_verdicts, _with_verdicts,
    _generations_table_exists, _with_favorites, _auto_generate_content_angles,
    _ensure_objective_templates, _require_profile_for_studio,
    _component_feedback_for_profile_owned as _component_feedback_for_profile,
    APP_RESEARCH_CAPS, APP_RESEARCH_MAX_SUPPORT_URLS, BRAND_URL_TEXT_MAX_CHARS,
    CONTENT_ANGLE_TEXT_FIELDS,
    create_brand, list_brands, get_active_brand, get_brand, update_brand,
    research_app_profile, list_app_profiles, get_app_profile, update_app_profile,
    list_content_angles,
    approve_app_profile, regenerate_everything, refresh_app_profile,
    delete_app_profile, generate_profile_content_angles,
    create_manual_content_angle, update_content_angle,
    regenerate_content_angles, regenerate_angle_goal_suggestions,
    live_angle_goals, angle_goal_suggestions, profile_direction_options,
    refresh_profile_direction_options, delete_content_angle,
    list_templates, template_facets, recommend_templates,
    ensure_objective_templates,
)
api_router.include_router(brands_router)

# Studio projects, plan, strategy, and the render submit gate (single owner
# in routers.studio), re-exporting the helpers the remaining generation
# code in this file and the tests still call from `server`.
from routers.studio import (
    router as studio_router,
    configure_studio,
    _two_section_repairs, _public_project, _project_strategy,
    _require_spoken_words_fit,
    _require_current_strategy, _guard_render_scene,
    _assert_model_usable, _assert_resolution_offered, _assert_within_single_pass_cap,
    _require_renderable_project, _backfill_two_section_projects,
    list_studio_projects, create_studio_project, get_studio_project,
    update_studio_project, suggest_hook_rewrite, suggest_line_rewrite, generate_plan,
    mark_project_ready, submit_project_generation, generate_project_strategy,
    generate_plan_and_strategy,
    list_studio_video_models,
)
api_router.include_router(studio_router)

# Asset library (per App Profile): uploads, usage history, and the
# attach/detach wiring onto projects. Single owner in routers.assets,
# re-exporting the helpers the media router, the render path, and the tests
# still call from `server` (_public_asset, _asset_usage_index, _asset_dir,
# _ensure_asset_file).
from routers.assets import (
    router as assets_router,
    configure_assets,
    _public_asset, _asset_usage_index, _attach_usage,
    _asset_dir, _ensure_asset_file,
    ASSET_MAX_BYTES, ASSET_IMAGE_TYPES, ASSET_ALLOWED_EXT, ASSET_AUDIO_ROLES,
    list_assets, get_asset_usage, upload_asset, update_asset, delete_asset,
    attach_asset_to_project, detach_asset_from_project,
)
api_router.include_router(assets_router)

# Generation history: list/detail/poll/retry/archive/delete (single owner in
# routers.history), re-exporting the handlers and the durable-save repair the
# stranded-render sweep and the tests still call from `server`.
from routers.history import (
    router as history_router,
    configure_history,
    list_generations, get_generation, poll_generation,
    retry_generation_storage, _run_storage_repair, retry_generation,
    set_generation_tiktok_link, set_generation_tiktok_views,
    set_generation_performance_snapshot, set_generation_video_verdict,
    _posted_performance_rows,
    archive_generation, generation_history, delete_generation,
)
api_router.include_router(history_router)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _request_id() -> str:
    """Correlation id for the in-flight request (G10)."""
    try:
        return observability.current_request_id()
    except Exception:
        return ""


def _with_request_id(detail) -> object:
    """Append the in-flight request id to a refusal detail so support can
    grep the logs for the exact request (G10). Strings get a suffix; other
    types pass through unchanged."""
    rid = _request_id()
    if rid and isinstance(detail, str):
        return f"{detail} [request_id={rid}]"
    return detail

FRAME_COUNT = 8
HOOK_DURATION_SECONDS = 3.0
BRAND_URL_TEXT_MAX_CHARS = 8000

# How much an extension adds when the request does not say. Chosen to sit at
# the provider's render floor so the default needs no trim, and short enough that
# three or four extensions still land inside a normal 20s video.
DEFAULT_EXTENSION_SECONDS = 5

# Public HTTPS base URL this server is reachable at. OpenRouter's video
# generation API requires V2V motion-reference videos (input_references[].video_url)
# to be real HTTPS URLs — base64 data URIs, unlike for images, are rejected with
# "Only HTTPS URLs are allowed". PUBLIC_BASE_URL lets this be set explicitly;
# RENDER_EXTERNAL_URL is populated automatically on Render deployments.
PUBLIC_BASE_URL = (os.environ.get("PUBLIC_BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "").rstrip("/")

# Turso (cloud SQLite) configuration — free tier provides persistent storage
# that survives Render's ephemeral filesystem wipes on redeploy. When
# TURSO_DATABASE_URL is set, the app uses libsql_experimental to connect to
# Turso over HTTP(S). When unset, it falls back to local aiosqlite (for dev).
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL", "").strip()
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "").strip()

# Capped at 1 concurrent yt-dlp/ffmpeg job — each video download + frame
# extraction can use 100-200MB+ of RAM, and this container only has 512MB
# total (shared with Python/Uvicorn/the DB connection). Running these
# serially avoids the OOM restarts seen when multiple analyses overlap.
_ytdlp_semaphore = asyncio.Semaphore(1)

# One local ffmpeg encode at a time, box-wide.
#
# Every ffmpeg argv in this repo is capped at -threads 1, and that bounds each
# spike — but it does not bound overlap: a poll-save trim/rescale/cut and a
# poster encode can still run concurrently across requests, and stacked
# encodes are what OOM-killed the container. This gate serializes
# entry to all of them (trim + rescale + camera cut in _persist_generation_clip,
# poster generation eager and lazy). Network work
# (downloads, R2 uploads) stays outside it — only the encode holds the slot.
# Same single-process assumption as _storage_repairs_in_flight above.
_FFMPEG_SLOT = asyncio.Semaphore(1)

# Storage repairs, in flight right now, by generation id.
#
# Two things make this necessary. The work is heavy -- a full download plus two
# ffmpeg passes -- and the client gives up after 10 minutes while the server can
# legitimately take closer to 22, so a founder who clicks "Retry durable save"
# again after a timeout starts a SECOND repair of the same clip rather than a
# replacement of a failed one. They then share the generation's local file, and
# two concurrent repairs are how a good clip gets replaced by a half-written one.
#
# A plain set is enough rather than a semaphore per id: the handlers are async on
# one event loop, so there is no await between the check and the insert. It does
# assume a single process -- with several workers each would guard its own share.
_storage_repairs_in_flight: set[str] = set()


# ---------------------------------------------------------------------------
# SQLite helpers — owned by backend/db.py. server keeps the mutable config
# (DB_PATH, TURSO_*, _ACTIVE_BACKEND, _TURSO_BOOT_SYNC_DONE) as plain module
# attributes because the test fixtures redirect them here at runtime; db.py
# resolves them through the _server back-reference set below.
# ---------------------------------------------------------------------------
_TURSO_BOOT_SYNC_DONE = False
_ACTIVE_BACKEND = None

import db as _db
_db._server = sys.modules[__name__]

from db import (
    get_db,
    _LibsqlAsyncWrapper,
    _CursorWrapper,
    _fetch_one,
    _fetch_all,
    _execute,
    _database_backend,
    _log_database_backend,
    _record_model_request,
    _record_asset_event,
    _log_model_call,
    _enqueue_job,
    _claim_job,
    _claim_job_by_id,
    _heartbeat_job,
    _complete_job,
    _fail_job,
    _fetch_job,
    init_db,
)


configure_post_kit(_fetch_one, _execute, _log_model_call)


# Health router borrows the row-count read defined above and the live backend
# label; injected here, once, so the router module never imports server.
configure_health(_fetch_one, lambda: _ACTIVE_BACKEND, lambda: bool(TURSO_DATABASE_URL))

# Brands router: configure with the DB helpers just imported plus the server
# module itself so call sites can resolve patched helpers at call time.
configure_brands(
    _fetch_one, _fetch_all, _execute, _log_model_call,
    sys.modules[__name__],
)

# Studio router: configure with the composition root so call sites can
# resolve patched helpers at call time.
configure_studio(sys.modules[__name__])

# Assets router: configure with the composition root so call sites resolve
# patched DB helpers and the server-owned upload-cache/event writers at call
# time.
configure_assets(sys.modules[__name__])

# History router: configure with the composition root so call sites resolve
# the patched DB helpers and the render-lifecycle helpers at call time.
configure_history(sys.modules[__name__])


# The face-swap target is never uploaded by the client. It must be a file this
# server produced itself, from one of exactly two provenances:
#   frames/    — a hook frame extracted from a video in the discovery feed
#   templates/ — the stored thumbnail of a saved hook template (bookmark)
#
# The allowlist is the enforcement point, not the absence of an upload field.
# `/api/media` is a blanket static mount over the whole storage dir, so a bare
# "starts with /api/media/" check would still let a caller launder an arbitrary
# photo into a target by first writing it to uploads/ through another endpoint
# (e.g. a prior source_face, whose URL is returned in this endpoint's own 202
# response, or customize_video's person_photo) and passing that path back here.
ALLOWED_TARGET_PREFIXES = ("/api/media/frames/", "/api/media/templates/")

GENERATED_ID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _restore_generated_image(image_path: Path, image_bytes: bytes) -> None:
    """Validate and atomically restore a durable generated-image backup."""
    if not isinstance(image_bytes, (bytes, bytearray, memoryview)):
        raise ValueError("Generated image backup is invalid.")
    image_bytes = bytes(image_bytes)
    if not image_bytes:
        raise ValueError("Generated image backup is empty.")

    # Never write unvalidated data into the public media directory, even
    # though it came from the database. The original image is normalized to a
    # PNG before persistence; verify the backup still decodes as one.
    with Image.open(io.BytesIO(image_bytes)) as restored_image:
        if restored_image.format != "PNG":
            raise ValueError("Generated image backup is not a PNG.")
        restored_image.verify()

    image_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = image_path.with_suffix(".restore.tmp")
    try:
        temporary_path.write_bytes(image_bytes)
        temporary_path.replace(image_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _template_thumbnail_path(template_id: str) -> Path:
    """Return the only permitted local cache path for a template thumbnail."""
    if not GENERATED_ID_RE.match(template_id or ""):
        raise ValueError("Invalid template thumbnail reference.")
    return pipeline.TEMPLATES_DIR / f"{template_id}.jpg"


def _normalize_template_thumbnail(image_bytes: bytes) -> bytes:
    """Validate arbitrary image bytes and persist a consistent JPEG thumbnail."""
    if not isinstance(image_bytes, (bytes, bytearray, memoryview)):
        raise ValueError("Template thumbnail is invalid.")
    with Image.open(io.BytesIO(bytes(image_bytes))) as image:
        normalized = image.convert("RGB")
        output = io.BytesIO()
        normalized.save(output, format="JPEG", quality=90, optimize=True)
    return output.getvalue()


def _restore_template_thumbnail(image_path: Path, thumbnail_bytes: bytes) -> None:
    """Validate and atomically rehydrate a template thumbnail cache file."""
    normalized_bytes = _normalize_template_thumbnail(thumbnail_bytes)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = image_path.with_suffix(".restore.tmp")
    try:
        temporary_path.write_bytes(normalized_bytes)
        temporary_path.replace(image_path)
    finally:
        temporary_path.unlink(missing_ok=True)


async def _ensure_template_thumbnail(template_id: str) -> Optional[Path]:
    """Resolve a template thumbnail, restoring its durable JPEG backup if needed."""
    try:
        thumbnail_path = _template_thumbnail_path(template_id)
    except ValueError:
        return None

    template = await _fetch_one(
        "SELECT thumbnail_url, thumbnail_bytes FROM hook_templates WHERE id = ?",
        (template_id,),
    )
    expected_url = f"/api/media/templates/{template_id}.jpg"
    if not template or template.get("thumbnail_url") != expected_url:
        return None

    if thumbnail_path.is_file():
        try:
            _normalize_template_thumbnail(thumbnail_path.read_bytes())
            return thumbnail_path
        except (OSError, ValueError) as exc:
            logger.warning("Template thumbnail cache is invalid for %s: %s", template_id, exc)

    try:
        _restore_template_thumbnail(thumbnail_path, template.get("thumbnail_bytes"))
        logger.info("Restored template thumbnail %s from durable backup", template_id)
        return thumbnail_path
    except (OSError, ValueError) as exc:
        logger.warning("Could not restore template thumbnail %s: %s", template_id, exc)
        return None


async def require_frame_derived_image(image_id: str) -> Path:
    """
    Resolve a client-supplied `image_id` to a generated image, proving it
    descends from a permitted target, and return its path.

    Four independent checks, because each catches something the others don't:

    1. Shape. `image_id` is interpolated into a path, so anything but a bare
       UUID is refused. This alone kills "../uploads/<id>", which otherwise
       feeds a raw uploaded photo into video generation with no AI step and no
       frame involved. It also excludes the server-generated `bridge-*.png`
       stills, which are an internal detail of extend-video and are never a
       legitimate client input.
    2. Containment. Belt-and-braces on the resolved path, so any future change
       to the shape rule can't silently reopen traversal.
    3. Provenance. The image must have a generated_images row whose
       target_image_url is an allowlisted frame or template. Uploads have no
       row; previews derived from an uploaded person photo have a row pointing
       at the analysis frame they were built on, which is exactly what we want
       to permit.
    4. Durable recovery. A missing local cache file is restored only from the
       validated PNG backup stored alongside the provenance record. This keeps
       extensions working after deploys and across backend instances without
       treating disk existence as proof of origin.
    """
    if not image_id or not GENERATED_ID_RE.match(image_id.strip()):
        raise HTTPException(
            status_code=400,
            detail="Invalid image reference. Generate a face swap from a hook frame first.",
        )
    image_id = image_id.strip()

    generated_root = pipeline.GENERATED_DIR.resolve()
    image_path = (generated_root / f"{image_id}.png").resolve()
    if generated_root not in image_path.parents:
        raise HTTPException(status_code=400, detail="Invalid image reference.")

    row = await _fetch_one("SELECT * FROM generated_images WHERE id = ?", (image_id,))
    if not row:
        raise HTTPException(
            status_code=400,
            detail=(
                "That image has no recorded source hook, so it can't be turned into a "
                "video. Start from a frame in the discovery feed or a saved template."
            ),
        )
    if not (row.get("target_image_url") or "").startswith(ALLOWED_TARGET_PREFIXES):
        raise HTTPException(
            status_code=400,
            detail=(
                "Videos can only be generated from a hook frame or a saved template, "
                "not from an uploaded image."
            ),
        )

    if not image_path.is_file():
        # The database survives deploys and may be shared by multiple backend
        # instances; the generated/ directory is neither. Rehydrate the exact
        # normalized PNG before submitting the video request.
        try:
            _restore_generated_image(image_path, row.get("image_bytes"))
            logger.info("Restored generated image %s from durable backup", image_id)
        except (OSError, ValueError) as exc:
            logger.warning("Could not restore generated image %s: %s", image_id, exc)
            raise HTTPException(
                status_code=410,
                detail=(
                    "This generated face-swap image is no longer available. Please generate a new "
                    "face swap before creating or extending a video."
                ),
            ) from exc

    return image_path


# ---------------------------------------------------------------------------
# Trending cache helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def frame_media_url(video_hash: str, filename: str) -> str:
    return f"/api/media/frames/{video_hash}/{filename}"


def build_frame_docs(video_hash: str, frame_paths: list) -> list:
    docs = []
    fps = FRAME_COUNT / HOOK_DURATION_SECONDS
    for idx, fp in enumerate(frame_paths):
        docs.append({
            "index": idx + 1,
            "timestamp_seconds": round(idx / fps, 2),
            "media_url": frame_media_url(video_hash, fp.name),
        })
    return docs


FRAME_VIDEO_HASH_RE = re.compile(r"^[0-9a-f]{16}$")
FRAME_FILENAME_RE = re.compile(r"^frame_\d{3}\.jpg$")


def _analysis_frame_path(video_hash: str, filename: str) -> Path:
    """Resolve exactly one expected extracted-frame cache path."""
    if not FRAME_VIDEO_HASH_RE.match(video_hash or ""):
        raise ValueError("Invalid frame video hash.")
    if not FRAME_FILENAME_RE.match(filename or ""):
        raise ValueError("Invalid frame filename.")

    frames_root = pipeline.FRAMES_DIR.resolve()
    frame_path = (frames_root / video_hash / filename).resolve()
    if frames_root not in frame_path.parents:
        raise ValueError("Invalid frame path.")
    return frame_path


def _normalize_analysis_frame(image_bytes: bytes) -> bytes:
    """Validate arbitrary image bytes and persist a consistent JPEG frame."""
    if not isinstance(image_bytes, (bytes, bytearray, memoryview)):
        raise ValueError("Analysis frame is invalid.")
    with Image.open(io.BytesIO(bytes(image_bytes))) as image:
        normalized = image.convert("RGB")
        output = io.BytesIO()
        normalized.save(output, format="JPEG", quality=90, optimize=True)
    return output.getvalue()


def _restore_analysis_frame(frame_path: Path, image_bytes: bytes) -> None:
    """Atomically restore a validated durable extracted-frame backup."""
    normalized_bytes = _normalize_analysis_frame(image_bytes)
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = frame_path.with_suffix(".restore.tmp")
    try:
        temporary_path.write_bytes(normalized_bytes)
        temporary_path.replace(frame_path)
    finally:
        temporary_path.unlink(missing_ok=True)


async def _record_analysis_frame_assets(video_hash: str, frame_paths: list) -> None:
    """Persist normalized extracted frames before exposing their public URLs."""
    assets = []
    for frame_path in frame_paths:
        filename = frame_path.name
        destination = _analysis_frame_path(video_hash, filename)
        image_bytes = _normalize_analysis_frame(frame_path.read_bytes())
        assets.append((filename, destination, image_bytes))

    async with get_db() as conn:
        for filename, _destination, image_bytes in assets:
            await conn.execute(
                """INSERT OR REPLACE INTO analysis_frame_assets
                   (video_hash, filename, image_bytes, created_at)
                   VALUES (?, ?, ?, ?)""",
                (video_hash, filename, image_bytes, now_iso()),
            )
        await conn.commit()

    # The cache may disappear at any time, so it is not the source of truth.
    # Refresh it after the durable write for immediate static/media access.
    for _filename, destination, image_bytes in assets:
        _restore_analysis_frame(destination, image_bytes)


async def _ensure_analysis_frame(video_hash: str, filename: str) -> Optional[Path]:
    """Return a valid frame cache file, restoring it from durable storage if needed."""
    try:
        frame_path = _analysis_frame_path(video_hash, filename)
    except ValueError:
        return None

    if frame_path.is_file():
        try:
            _normalize_analysis_frame(frame_path.read_bytes())
            return frame_path
        except (OSError, ValueError) as exc:
            logger.warning("Extracted frame cache is invalid for %s/%s: %s", video_hash, filename, exc)

    row = await _fetch_one(
        """SELECT image_bytes FROM analysis_frame_assets
           WHERE video_hash = ? AND filename = ?""",
        (video_hash, filename),
    )
    if not row:
        return None

    try:
        _restore_analysis_frame(frame_path, row.get("image_bytes"))
        logger.info("Restored extracted frame %s/%s from durable backup", video_hash, filename)
        return frame_path
    except (OSError, ValueError) as exc:
        logger.warning("Could not restore extracted frame %s/%s: %s", video_hash, filename, exc)
        return None


async def _recover_missing_frame(relative_path: str) -> bool:
    """
    Best-effort self-heal for a missing/corrupt frame cache.

    Prefer the durable JPEG backup. If an older analysis predates that backup,
    only re-extract from an already-cached video file — never re-download a
    remote TikTok video on this RAM-constrained backend.
    """
    parts = relative_path.split("/")
    if len(parts) != 3 or parts[0] != "frames":
        return False
    video_hash, filename = parts[1], parts[2]

    if await _ensure_analysis_frame(video_hash, filename):
        return True

    try:
        target = _analysis_frame_path(video_hash, filename)
    except ValueError:
        return False

    # Only attempt if the video file is already on disk (no download = no OOM risk).
    video_path = pipeline.VIDEOS_DIR / f"{video_hash}.mp4"
    if not video_path.is_file():
        return False

    try:
        frame_paths = await pipeline.extract_hook_frames(
            video_path, num_frames=FRAME_COUNT, duration=HOOK_DURATION_SECONDS
        )
        await _record_analysis_frame_assets(video_hash, frame_paths)
    except Exception as e:
        logger.warning(f"Frame recovery failed for hash {video_hash}: {e}")
        return False

    return target.is_file() and target.stat().st_size > 1024


async def get_video_or_404(video_id: str) -> dict:
    video = await _fetch_one("SELECT * FROM videos WHERE id = ?", (video_id,))
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


async def get_latest_analysis_or_404(video_id: str) -> dict:
    analysis = await _fetch_one(
        "SELECT * FROM analyses WHERE video_id = ? ORDER BY created_at DESC LIMIT 1",
        (video_id,),
    )
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail="No analysis found for this video yet. Analyze the hook first.",
        )
    return analysis


async def _fetch_active_brand(user_id: str) -> Optional[dict]:
    """
    The "active" brand profile for a user: their most recently created *or
    edited* one.

    Single source of truth so every caller agrees on which profile is active.
    Previously the /brand/active endpoint ordered by created_at while the video
    flows ordered by updated_at, so editing an older profile made the Brand page
    and the generators disagree about which brand was in effect.

    user_id is REQUIRED. This query previously had no user filter while the
    /brand/active endpoint did, so the video-generation flows that call this
    could pull a different user's brand profile into someone else's generation
    whenever that other profile happened to be the most recently updated row in
    the table.
    """
    return await _fetch_one(
        "SELECT * FROM brand_profiles WHERE user_id = ? "
        "ORDER BY updated_at DESC, created_at DESC LIMIT 1",
        (user_id,),
    )


async def _resolve_brand_profile(user_id: str, brand_id: str = "") -> Optional[dict]:
    """
    Resolve which saved brand profile to use for a generation.

    Prefers an explicitly chosen brand_id so the creator controls which brand a
    video is built for, instead of it silently depending on which profile was
    edited most recently. Falls back to the active profile when no explicit
    choice was made. Always user-scoped: an unknown or another user's brand_id
    resolves to None rather than leaking across accounts.
    """
    bid = (brand_id or "").strip()
    if bid:
        brand = await _fetch_one(
            "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (bid, user_id)
        )
        if brand:
            return brand
        logger.warning(
            f"brand_id {bid} not found for this user — falling back to the active profile."
        )
    return await _fetch_active_brand(user_id)


async def get_active_brand_or_404(user_id: str) -> dict:
    brand = await _fetch_active_brand(user_id)
    if not brand:
        raise HTTPException(
            status_code=404,
            detail="No brand profile yet. Analyze your website URL first.",
        )
    return brand


# ---------------------------------------------------------------------------
# App Profile helpers (template-studio workflow)
# ---------------------------------------------------------------------------
def public_media_url(local_path) -> Optional[str]:
    """
    Build an absolute HTTPS URL for a file under storage/, for use as a
    video_url V2V motion reference. Returns None if the file isn't under
    storage/ or if PUBLIC_BASE_URL isn't configured (e.g. local dev without
    a public hostname) — callers must treat None as "skip this reference"
    rather than fall back to base64, which the video API rejects outright.
    """
    if not local_path or not PUBLIC_BASE_URL:
        return None
    try:
        storage_root = pipeline.STORAGE_DIR.resolve()
        resolved = Path(local_path).resolve()
        relative_path = resolved.relative_to(storage_root)
    except (ValueError, OSError):
        return None
    return f"{PUBLIC_BASE_URL}/api/media/{relative_path.as_posix()}"


def served_media_path(local_path) -> Optional[str]:
    """
    Build a backend-relative URL for a file under storage/, for the browser.

    Unlike public_media_url this needs no PUBLIC_BASE_URL: the frontend's
    mediaUrl() prefixes the backend origin. That matters for the completion
    path, where the R2 upload can fail and the only durable copy left is the
    local file — and without a URL for it the panel falls back to the
    provider's unsigned link, which expires and leaves an already-generated
    video that will not play.
    """
    if not local_path:
        return None
    try:
        storage_root = pipeline.STORAGE_DIR.resolve()
        resolved = Path(local_path).resolve()
        relative_path = resolved.relative_to(storage_root)
    except (ValueError, OSError):
        return None
    return f"/api/media/{relative_path.as_posix()}"


# React/webpack emit content-hashed bundle names (main.98727cf3.js,
# main.a1b2c3d4e5.chunk.js) and hashed font/media files
# (anton.4c1f0a9b.woff2). A file that is BOTH hashed and one of these build
# outputs can never change meaning, so it is safe to cache forever.
#
# Both halves are required on purpose. Without the extension list, any file
# with a long hex run in its name would be marked immutable — including a
# replaceable asset — and would then take up to a year to reach anyone. Without
# the hash requirement, an unhashed file copied verbatim out of public/ would be
# pinned at deploy time.
_HASHED_ASSET_RE = re.compile(
    r"\.[0-9a-f]{8,}\.(?:[\w-]+\.)*(?:m?js|css|map|woff2?|ttf|eot)$",
    re.IGNORECASE,
)

IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
REVALIDATE_CACHE_CONTROL = "public, max-age=0, must-revalidate"
# index.html must never be cached: it is the only file that points at the
# current bundle hashes, so a stale copy is a stale app.
SPASHELL_CACHE_CONTROL = "no-cache, no-store, must-revalidate"


class _CacheHeaderStaticFiles(StaticFiles):
    """StaticFiles that states how long a file may be cached.

    Without an explicit Cache-Control, browsers fall back to heuristic caching
    against Last-Modified and will happily keep an old index.html — which still
    names the PREVIOUS deploy's bundle hashes. The result is an app that deploys
    cleanly and appears not to have changed, because the shell that decides
    which code to run is the one thing being served from cache. That is not
    hypothetical here: it is why a sidebar reorder was visible in the deployed
    bundle and not on screen.
    """

    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        path = getattr(self, "path", "")
        name = os.path.basename(path) if path else ""
        response.headers["Cache-Control"] = (
            IMMUTABLE_CACHE_CONTROL
            if _HASHED_ASSET_RE.search(name)
            else REVALIDATE_CACHE_CONTROL
        )
        return response


def _spa_response() -> Response:
    return FileResponse(
        str(FRONTEND_BUILD_DIR / "index.html"),
        headers={"Cache-Control": SPASHELL_CACHE_CONTROL},
    )


def require_ai_configured():
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="AI features are not configured yet. Set the OPENROUTER_API_KEY environment "
                   "variable to enable hook analysis, face-swap generation, and video generation.",
        )


def validate_and_normalize_photo(raw_bytes: bytes) -> bytes:
    """Ensure uploaded photo is a real, non-blank image; convert to PNG."""
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        img.seek(0)
    except Exception:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image.")

    if img.mode != "RGB":
        img = img.convert("RGB")

    extrema = img.getextrema()
    if isinstance(extrema[0], tuple):
        flat_range = sum((c[1] - c[0]) for c in extrema)
    else:
        flat_range = extrema[1] - extrema[0]
    if flat_range < 3:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image appears blank/solid-color. Please upload a real photo.",
        )

    max_dim = 1600
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Video Models (available for video generation)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Standalone Face Swap (Higgsfield-style 3-step flow)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Face Swap → Video Generation (Two-Phase: Hook + Extend)
#
# Phase 2a: HOOK VIDEO (5s, silent, movement-focused)
#   Generates a short attention-grabbing clip with pure visual motion —
#   no voice, just character movement to spark curiosity. This is the
#   "scroll-stopper" that TikTok's algorithm tests in the first 2-3 seconds.
#
# Phase 2b: EXTEND VIDEO (optional continuation)
#   After the user approves the hook, generates a longer continuation with
#   voice/narrative that delivers the message. Uses the hook video's last
#   frame as a bridge for visual continuity.
# ---------------------------------------------------------------------------

# Hook-video prompt vocab lives in hook_prompting.py (motion styles,
# style directives, template categories). Only the vocab constants are
# re-exported here so `server.X` keeps working for existing records; the
# prompt builders were removed (no live caller).
from hook_prompting import (
    HOOK_MOTION_STYLES,
    HOOK_TEMPLATE_CATEGORIES,
    HOOK_STYLE_DIRECTIVES,
)


# Keep the original endpoint for backward compatibility


# ---------------------------------------------------------------------------
# Face Swap → Branded Video (Content Remixer integration)
# Generates a brand-customized video prompt from the hook analysis context +
# brand profile (via URL or saved), then submits to video generation with
# the face-swapped image as first_frame.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Remix chat: conversational back-and-forth to turn a viral hook into a
# personalized brief (goal, audience fit, USPs, etc.) before generating the
# video prompt. One chat thread per customization. This complements (rather
# than replaces) the one-click "Content Remixer" brand-profile flow above -
# it's for users who want to describe their goal in their own words and get
# clarifying questions back, instead of relying on a saved brand profile.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Video generation: prompt writing + OpenRouter video job submission/polling
# ---------------------------------------------------------------------------
async def _build_music_context(video: Optional[dict]):
    """
    Given a video record, build (music_context, transcript_text, hashtags) for use in
    AI prompt generation. Returns (None, "", []) if the video has no music/subtitle data.
    """
    music_context = None
    transcript_text = ""
    hashtags = []
    if not video:
        return music_context, transcript_text, hashtags

    if video.get("song_title") or video.get("song_artist"):
        music_context = {
            "song_title": video.get("song_title", ""),
            "song_artist": video.get("song_artist", ""),
            "song_album": video.get("song_album", ""),
            "song_duration": video.get("song_duration", 0),
        }
    if video.get("subtitles_url"):
        raw_vtt = await pipeline.fetch_subtitles(video["subtitles_url"])
        if raw_vtt:
            transcript_text = pipeline.parse_webvtt_to_text(raw_vtt)
    hashtags = video.get("hashtags", []) if isinstance(video.get("hashtags"), list) else []
    return music_context, transcript_text, hashtags


def _build_sound_reference(music_context: Optional[dict], use_original_sound: bool) -> Optional[dict]:
    """
    Build a small persisted record of which sound (if any) the user chose to reuse,
    so the video brief / History can display "Use this sound: <title> by <artist>".
    """
    if not use_original_sound or not music_context:
        return None
    song_title = music_context.get("song_title") or ""
    song_artist = music_context.get("song_artist") or ""
    if not song_title and not song_artist:
        return None
    return {
        "reuse_original_sound": True,
        "song_title": song_title,
        "song_artist": song_artist,
        "song_album": music_context.get("song_album", ""),
    }


# ---------------------------------------------------------------------------
# Brand profile (manual creation)
# ---------------------------------------------------------------------------
# Profiles are created from App Store and Google Play listings via
# POST /app-profiles/research below. The website autofill endpoint
# (POST /brand/analyze-url) was deleted with that whole path: the only way
# to create a profile is a store listing, so there is no website analysis
# left to serve. The website_url column stays dormant for legacy rows.


# Studio projects (guided creation workflow)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Generations (single-pass video production)
# ---------------------------------------------------------------------------
def _playback_url(row: dict) -> Optional[str]:
    """The signed app route can serve local bytes or authorize private R2 reads.

    The response names a possible saved source; only browser decoding proves
    playability. Do not issue a link to a provider-only row without saved bytes.
    """
    if row.get("status") != "completed":
        return None
    if (row.get("r2_url") or str(row.get("video_url") or "").startswith("/api/media/videos/")
            or (pipeline.VIDEOS_DIR / f"{row['id']}.mp4").is_file()):
        return media_signing.build_signed_path(f"{row['id']}.mp4")
    return None


def _poster_url(row: dict) -> Optional[str]:
    """
    Signed poster thumbnail for a completed generation, or None.

    Deterministic from the id (`/api/media/posters/{id}.jpg`) so old rows
    heal without a backfill: the poster route lazily generates/restores on
    first hit. Only completed rows get one; anything else has no frame to
    show. The frontend treats a missing poster as "no thumbnail yet" and the
    <video> still plays — a 404 poster must never break playback.
    """
    try:
        if (row or {}).get("status") != "completed":
            return None
        job_id = str((row or {}).get("id") or "").strip()
        if not job_id:
            return None
        return media_signing.build_signed_poster_path(f"{job_id}.jpg")
    except Exception:
        return None


async def _eager_poster(generation_id: str, user_id: str) -> None:
    """
    Best-effort poster generation right after a save.

    Never raises and never fails the save: History still works without a
    poster (the <video> falls back to metadata preload). Runs ffmpeg off the
    event loop, then uploads the JPEG to R2 for durability.
    """
    try:
        # Shares the box-wide encode gate: a poster encode must never overlap
        # a save trim/rescale/cut, even though it runs after the
        # response and off the event loop.
        async with _FFMPEG_SLOT:
            poster = await asyncio.to_thread(posters.ensure_poster, generation_id)
        if poster is not None:
            try:
                await asyncio.to_thread(
                    storage_service.upload_poster, user_id, generation_id, poster)
            except Exception as exc:
                logger.warning("Poster R2 upload failed for %s (%s)", generation_id, type(exc).__name__)
    except Exception as exc:
        logger.warning("Eager poster failed for %s (%s)", generation_id, type(exc).__name__)


async def _schedule_poster(
    background_tasks: BackgroundTasks, generation_id: str, user_id: str
) -> None:
    """
    Poster work runs after the response, never inside it.

    A save already spends an ffmpeg (trim/rescale) inside the request; running
    the poster encode inline stacks a second one on a 512MB host, which is
    what OOM-killed the container. On HTTP the work is deferred to
    BackgroundTasks; direct (non-HTTP) callers such as tests pass None and run
    it inline, which keeps them asserting the real path.
    """
    if background_tasks is not None:
        background_tasks.add_task(_eager_poster, generation_id, user_id)
        return
    await _eager_poster(generation_id, user_id)


def _parse_quality_report(value):
    """The stored craft report as a dict, or None when absent or unreadable.

    The column is written once, at submit, from our own JSON; a value that
    does not parse is treated as no stored report rather than trusted, so the
    read falls back to recomputing from the project's words.
    """
    if isinstance(value, dict):
        return value
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _quality_report_for_row(row):
    """The craft report for a generation row: stored wins, else recompute.

    The stored report is the score of the words this render actually spoke,
    frozen at submit (ADR 0117). It wins over the project's current words,
    which the founder may have rewritten since. A row from before the column
    existed carries no stored report; when the row also carries its project's
    words (the detail and history reads join them in), the report is
    recomputed from those words so old renders still read with a score. The
    score stays advisory either way: it never gates anything (ADR 0114).
    """
    stored = _parse_quality_report((row or {}).get("quality_report"))
    if stored is not None:
        return stored
    hook = (row or {}).get("hook_line")
    script = (row or {}).get("script")
    if not (hook or script):
        return None
    return creative_quality.assess_spoken_quality(
        hook,
        script,
        hook_seconds=(row.get("hook_seconds") or 3),
        total_seconds=row.get("duration_seconds") or 0,
        app_name=row.get("brand_name") or "",
        allows_question=True,
    )


def _public_generation(row: dict) -> dict:
    """Serialize a generation row, hiding the stored prompt by default.

    The prompt is long and only useful when debugging a specific result, so
    it is returned by the detail endpoint but trimmed from list responses.

    The media URLs are signed here, in the one serializer every generation
    response passes through, rather than at each of the nine places that return
    one. Every list, detail, poll, retry and history response therefore hands
    out links that work, and there is no second path that can forget.
    """
    out = dict(row)
    out["adjustments"] = out.get("adjustments") or []
    out["continuity"] = out.get("continuity") or {}
    out["retryable"] = bool(out.get("retryable"))
    out["approved"] = bool(out.get("approved"))
    out["segment_index"] = int(out.get("segment_index") or 0)
    out["strategy_version"] = int(out.get("strategy_version") or 0)
    out["trim_to_seconds"] = int(out.get("trim_to_seconds") or 0)
    out["post_kit"] = _parse_post_kit(row.get("post_kit"))
    out["quality_report"] = _quality_report_for_row(row)
    # The project's words ride along on the detail/history joins only so the
    # quality fallback above can recompute for pre-column rows; they are not
    # generation fields and do not belong in the payload.
    for _joined_key in ("hook_line", "script", "hook_seconds", "duration_seconds", "brand_name"):
        out.pop(_joined_key, None)
    out["tiktok_url"] = (row.get("tiktok_url") or "").strip() or None
    views = row.get("tiktok_views")
    out["tiktok_views"] = int(views) if views is not None else None
    out["tiktok_views_at"] = row.get("tiktok_views_at")
    out.pop("prompt_used", None)
    # Stored unsigned so a row never holds a signature that outlives its own
    # expiry; signed fresh on every read. video_url and r2_url are both stored
    # media paths, so both are signed here in the single serializer every
    # generation response passes through. A provider render keeps only its
    # temporary provider link in video_url and the durable copy in r2_url; a
    # demo-cta export does the opposite, and signing on the way out makes both
    # fetchable from the browser.
    out["video_url"] = media_signing.sign_stored_path(out.get("video_url"))
    out["r2_url"] = media_signing.sign_stored_path(out.get("r2_url"))
    out["playback_url"] = _playback_url(row)
    out["poster_url"] = _poster_url(row)
    for key in ("video_urls", "unsigned_urls"):
        if isinstance(out.get(key), list):
            out[key] = [media_signing.sign_stored_path(u) for u in out[key]]
    return out


def _public_generation_detail(row: dict) -> dict:
    out = _public_generation(row)
    out["prompt_used"] = row.get("prompt_used") or ""
    return out


def _retired_project_assets(assets: list) -> list:
    """Attachment entries whose kind is no longer part of the product."""
    return [
        a for a in (assets or [])
        if isinstance(a, dict) and (a.get("kind") or "") != "character_reference"
    ]


def _refuse_retired_project_assets(assets: list) -> None:
    """
    Loud 409 for projects still holding retired uploads (screenshots,
    recordings, logos, photos, audio). The founder chose hard-error over
    silent-ignore: these must be detached on the Template & photo step before the
    project can move again, so a generation never silently drops inputs the
    founder thought were in play.
    """
    retired = _retired_project_assets(assets)
    if not retired:
        return
    kinds = sorted({str(a.get("kind") or "file").replace("_", " ") for a in retired})
    raise HTTPException(
        status_code=409,
        detail=(
            f"This project still holds {', '.join(kinds)} from before uploads "
            "went face-only, and nothing but the character reference can be "
            "used anymore. Detach them on the Template & photo step and try again."
        ),
    )


def _identity_reference_payload(face_path: Path) -> dict:
    """One face-cropped photo as an OpenRouter input_references image entry."""
    from ai_service import image_data_uri
    return {
        "type": "image_url",
        "image_url": {"url": image_data_uri(face_path)},
    }


async def _studio_identity_references(
    assets: list, model_key: str, user_id: str, template: Optional[dict] = None
) -> Optional[Path]:
    """Resolve the project's attached character_reference to a face-cropped
    photo on disk, or return None when none is attached.
    The reference is the identity guide; the person-anchor prompt section
    (generation_planning.person_anchor_notes) tells the model whose face it
    is and what to do with it. Legacy face-swap mechanics proved the pairing
    works: image reference in, matching person out.

    Returns the cropped face PATH, not a request payload, because different
    models carry it in different fields: Hailuo 3 and HeyGen take it as an
    input_references identity guide, while Hailuo 3 Max refuses
    input_references outright (proven live) and takes it as the opening frame
    instead. The caller (_submit_generation) picks the field from the model's
    identity_via_first_frame capability — this function only proves which
    photo, loudly.

    Guardrails, all loud:
    - A project still holding retired uploads (anything but the character
      reference) is REFUSED before anything else. Those inputs can no longer
      reach any pipeline stage, so generating around them would silently drop
      what the founder thought was in play.
    - A template that declares character_reference in required_assets is
      REFUSED without one. The requirement used to be decorative: it was
      rendered as "Needs character reference" in the studio and on the
      template, but nothing enforced it, so a render could go out with
      no identity input at all and the model free to invent a presenter.
    - Exactly one character_reference asset may be attached, and it is the one
      used. Several used to be allowed and the first in JSON order silently
      won, which is the worst of both: the founder saw every photo listed as
      attached and had no way to tell which face the render would use. Refusing
      is the only answer that cannot be wrong about someone's face.
    - The asset row must exist, belong to this user, and point at a real
      file on disk; otherwise the submission fails with a 409, never with a
      quietly invented lookalike.
    - Models that cannot take identity images are refused via
      video_providers.accepts_identity_reference, before any spend.
    """
    _refuse_retired_project_assets(assets)
    anchors = [
        a for a in (assets or [])
        if isinstance(a, dict)
        and str(a.get("kind") or "").strip().lower() == "character_reference"
    ]
    if len(anchors) > 1:
        labels = ", ".join(
            f"{(a.get('label') or a.get('name') or a.get('asset_id') or 'photo').strip()}"
            for a in anchors[:3]
        )
        raise HTTPException(
            status_code=409,
            detail=(
                f"This project has {len(anchors)} character references attached "
                f"({labels}). The render uses exactly one, and guessing which would "
                "mean you could pay for a video of the wrong person. Detach all but "
                "the photo you want on camera, then generate again."
            ),
        )
    anchor = anchors[0] if anchors else None
    if anchor is None:
        required = [
            str(a or "").strip().lower()
            for a in ((template or {}).get("required_assets") or [])
        ]
        if "character_reference" in required:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This template puts a person on camera, so it needs a character "
                    "reference. The video is generated from your photograph, so "
                    "without one the model would invent someone who looks nothing "
                    "like you. Attach a character reference on the Template & photo step and "
                    "try again."
                ),
            )
        return None

    if not video_providers.accepts_identity_reference(model_key):
        raise HTTPException(
            status_code=409,
            detail=(
                "The selected video model cannot accept a character reference. "
                "Detach the character reference asset or switch to a model that "
                "supports identity images."
            ),
        )

    asset_id = anchor.get("asset_id") or ""
    row = None
    if asset_id:
        row = await _fetch_one(
            "SELECT * FROM assets WHERE id = ? AND user_id = ?", (asset_id, user_id)
        )
    if isinstance(row, dict):
        # Restored from R2 when this container never saw the upload: refusing
        # to spend a generation over a file the cloud can produce would be
        # wrong, and the identity pass is the last moment to notice.
        restored = await _ensure_asset_file(row)
        path = str(restored) if restored else None
    else:
        path = anchor.get("file_path")
    if not path or not Path(path).is_file():
        logger.warning(f"Character reference {asset_id or '(unresolved)'} has no file on disk; refusing generation")
        raise HTTPException(
            status_code=409,
            detail="The attached character reference image is missing its file. Re-upload it before generating.",
        )
    from ai_service import image_data_uri
    from face_crop import crop_face_from_path, bound_for_submit

    # Crop to the face before sending. The legacy image paths have always done
    # this (ai_service.py:613, 664) because models treat an unframed scene
    # reference as authoritative and reproduce its face — so a full-body upload
    # arrives with a face occupying a few percent of the frame and the model
    # reads the scene instead of the person. face_crop degrades to the original
    # when no face is found, so this can only improve the reference.
    try:
        reference_path = crop_face_from_path(Path(path))
    except Exception as e:  # never fail a render over a crop
        logger.warning(f"Character reference crop failed for {path} ({e}); sending original.")
        reference_path = Path(path)

    # Then bound it. The reference travels as a base64 data URI inside a JSON
    # body, and nothing about that was capped: a 200 MB upload ceiling plus a
    # crop that never resizes means a phone photo can arrive as megabytes of
    # data URI. Bounding after the crop, because the crop is what decides how
    # much of the frame is actually the person.
    reference_path = bound_for_submit(reference_path)

    # Prove the file is a readable image before any spend, even though the
    # caller — not this function — decides which request field carries it.
    try:
        image_data_uri(reference_path)
    except Exception as e:
        logger.warning(f"Character reference at {path} could not be read: {e}")
        raise HTTPException(
            status_code=409,
            detail="The attached character reference image could not be read. Re-upload it before generating.",
        ) from e
    return reference_path


async def _submit_generation(
    project: dict,
    profile: dict,
    template: dict,
    user_id: str,
    model: str = "",
    duration: Optional[int] = None,
    segment_role: str = "primary",
    segment_index: int = 0,
    is_extension: bool = False,
    is_hook: bool = False,
    attempt: int = 1,
    generate_audio: Optional[bool] = None,
    resolution: Optional[str] = None,
    strategy: Optional[dict] = None,
    continuity: Optional[dict] = None,
    continuity_frame: Optional[Path] = None,
    continuity_video_url: str = "",
    previous_summary: str = "",
     hook_trim: int = 0,
     idempotency_key: str = "",
     request_id: str = "",
 ) -> dict:
    """
    Submit ONE video generation job. This is the only render path.

    A video is a hook and a middle in a single pass. It is never assembled from
    a chain: there is no extend call, no approval gate between segments, and no
    join step, so the duration is clamped to one pass and the founder attaches
    their own demo and call to action to the result.

    Two prompt paths, chosen by whether a strategy exists:

    - With a strategy (the normal case) it is build_segment_prompt, carrying the
      app-specific messaging, the locked scene and the two sections. Used even
      though there are no segments to build individually: the strategy is what
      makes the video about THIS app rather than a generic take with a name in
      it, and index 0 renders the whole piece.
    - Without one, build_single_pass_prompt, which works from the plan alone.
      That is the fallback for a project whose strategy was never built.
    """
    # One video is one render, so the piece is clamped to what one pass can
    # actually produce rather than split across jobs. `plan_duration` used to
    # return a primary/extension pair for a long request; that pair is the chain
    # this workflow no longer builds, and honouring it here would spend a second
    # generation for footage the founder is attaching themselves.
    # Correlation id for this render (G10): logged here and threaded into every
    # refusal so the founder's report can be matched to the server line.
    rid = request_id or _request_id()
    logger.info("submit_generation project=%s user=%s model=%s request_id=%s",
                project.get("id"), user_id, model or project.get("model"), rid)
    requested = template_library.clamp_duration(
        duration or project.get("duration_seconds") or 0
    )
    model_key = video_providers.resolve(model)[0]
    cap = video_providers.capability(model_key)
    camera_setup = project.get("camera_setup") or "handheld"
    if camera_setup == "fixed" and cap.get("identity_via_first_frame"):
            raise HTTPException(status_code=409, detail=_with_request_id(
                "This model uses your face photo as its literal first frame, so it cannot "
                "start with fixed-camera head-to-mid-thigh framing. Select a model that "
                "accepts an identity reference image, or choose Handheld selfie."
            ))
    if requested > cap["max_duration"]:
        requested = int(cap["max_duration"])
    seconds = requested

    # A strategy, when present, describes the same single piece the plan does:
    # a hook and a middle. build_segment_prompt is therefore the whole-piece
    # builder now, not a per-beat one — the two-section brief and scene lock are
    # what make the video app-specific, and a video without a strategy is a
    # generic take with a name in it.
    #
    # `segment_role`, `is_extension`, `continuity_frame`
    # and `previous_summary` are accepted and ignored. Every one of them
    # described chaining a second render onto a first, and a video is one
    # render: the rows still record segment_role so
    # existing history stays readable, and nothing sets them but "primary".
    #
    # Resolve the project's own strategy when the caller did not hand one over.
    # The retry path passes none, and without this a retry of an app-specific
    # video silently fell through to build_single_pass_prompt and spent a real
    # render on a generic take with the app's name in it -- the one outcome the
    # strategy exists to prevent, bought precisely when something had already
    # gone wrong once.
    # Validate the two spoken lines and rewrite what the piece cannot speak,
    # BEFORE the strategy is bound and before the prompt is built, so the words
    # this measured are the words the video model receives. No model call and no
    # provider request: the rewrite is arithmetic on the founder's own words — a
    # hook line cut back to its opening sentence, with what came off it spoken at
    # the head of the middle, and a middle cut from its own middle so the
    # sentence that resolves the hook survives the cut. hook_seconds and the
    # piece's seconds are passed exactly as the render gate passes them, so the
    # words that fit here are the words the gate above already agreed fit.
    plan_words, spoken_repair = ai_service.repair_spoken_story(
        {"hook_line": project.get("hook_line"), "script": project.get("script")},
        project.get("hook_seconds") or 3,
        project.get("duration_seconds") or 0,
    )
    if spoken_repair["rewritten"]:
        logger.info(
            f"Spoken words for project {project['id']} were rewritten before the render: "
            f"{json.dumps(spoken_repair['changes'])}"
        )
    # The plan the prompt is built from, with the repaired words in it. The row
    # itself is untouched: this is what this render speaks, not an edit to the
    # plan the founder approved.
    render_plan = {**project, **plan_words}

    strategy = strategy or _project_strategy(project)
    # The stored angle is the third carrier of the place (see
    # build_segment_prompt): its opening moment must agree with the plan
    # Location before the prompt locks the scene. Resolve it here, where the
    # database is, so the pure prompt builder only has to compare two values.
    # A missing row means the angle was regenerated after this strategy was
    # built; there is nothing to compare, and the strategy's own Location audit
    # still runs.
    content_angle = None
    content_angle_id = str(
        (strategy or {}).get("content_angle_id") or project.get("content_angle_id") or ""
    )
    if strategy and content_angle_id:
        content_angle = await _fetch_one(
            "SELECT * FROM content_angles WHERE id = ? AND user_id = ?",
            (content_angle_id, user_id),
        )
    # The strategy carries the spoken words too — the hook in section 0 and the
    # middle in section 1 — so the same repaired words are bound into it. Only
    # when something was rewritten: an untouched plan needs no rebinding, and a
    # strategy the founder wrote by hand keeps the words this otherwise leaves
    # alone.
    if strategy and spoken_repair["rewritten"]:
        strategy, _ = bind_spoken_words(
            strategy,
            plan_words,
            project.get("hook_seconds") or 3,
            project.get("duration_seconds") or 0,
        )
    # One place for the whole render (ADR 0090): every place-bearing direction
    # line is reconciled to the plan's Location before the prompt is built, and
    # spoken words that still name another place refuse the render here — the
    # last point where a contradiction can be caught before money is spent.
    # The same guard makes Location name the place only and completes Props and
    # Movement from the actions and the timeline (ADR 0092), so the prompt's
    # WHERE line and the strategy lock cannot disagree.
    if strategy:
        # The selfie ending rotates with the number of renders this project
        # already has, so consecutive renders do not repeat the same beat
        # (ADR 0093).
        prior_renders = await _fetch_one(
            "SELECT COUNT(*) AS n FROM generations WHERE studio_project_id = ? AND user_id = ?",
            (project.get("id"), user_id),
        )
        render_index = int((prior_renders or {}).get("n") or 0)
        prior_beats = await _fetch_all(
            "SELECT final_beat FROM generations "
            "WHERE studio_project_id = ? AND user_id = ? AND final_beat IS NOT NULL AND final_beat != '' "
            "ORDER BY created_at DESC LIMIT 20",
            (project.get("id"), user_id),
        )
        exclude = [row.get("final_beat") for row in prior_beats if row.get("final_beat")]
        strategy = _guard_render_scene(
            strategy, project, render_index=render_index, exclude=exclude,
            content_angle=content_angle,
        )
        # The prompt's WHERE line names the place only; split_location keeps the
        # original when there is no place to keep (lighting-only text), so an
        # emptied field can never happen here. Object clauses ("a phone
        # beside the person") are dropped as well, in every camera setup.
        place_only, _moved = scene_consistency.split_location(
            render_plan.get("location") or ""
        )
        place_only, _objects = scene_consistency.strip_location_objects(place_only)
        if place_only:
            place_only = scene_consistency.repair_location_fragment(
                place_only,
                " ".join(str((content_angle or {}).get(k) or "")
                         for k in ("hook_promise",))
                + " " + " ".join(str(strategy.get(k) or "")
                                 for k in ("hook_promise", "hook_concept")),
            )
            render_plan["location"] = place_only
    # Each provider has its own prompt ceiling. Hailuo's was measured live at
    # 7,000; others are lower, and sending them a Hailuo-sized prompt 400s
    # after the founder has asked for it. The builder scales every field
    # budget to fit rather than cutting the finished tail. On a tight ceiling
    # the spoken script is additionally sacred: the ceiling tripped the
    # protection withdrawal on ordinary strategies, so only the direction and
    # template wording is trimmed there, never the founder's own words.
    prompt_budget = video_providers.capability(model_key).get("prompt_char_limit")
    if strategy:
        try:
            prompt = generation_planning.build_segment_prompt(
                strategy=strategy,
                profile=profile,
                template=template,
                duration=seconds,
                assets=project.get("assets") or [],
                plan=render_plan,
                prompt_budget=prompt_budget,
                script_sacred=video_providers.script_is_sacred(model_key),
                angle=content_angle,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=_with_request_id(str(exc))) from exc
    else:
        # The no-strategy fallback, and it now takes the same ceiling and the
        # same sacred-script rule as the strategy path. It used to take neither,
        # so nothing in it could fit a tight provider. Unreachable today —
        # _require_current_strategy refuses a strategy-less project first — and
        # wired the same way regardless, so the two builders cannot disagree
        # about a ceiling if that ordering ever changes.
        prompt = generation_planning.build_single_pass_prompt(
            plan=render_plan,
            profile=profile,
            template=template,
            duration=seconds,
            segment=segment_role,
            is_extension=is_extension,
            prompt_budget=prompt_budget,
            script_sacred=video_providers.script_is_sacred(model_key),
        )

    # The fixed instructions in a prompt do not scale with the budget, only the
    # variables do, so a tight ceiling can still land over it. That is knowable
    # here and nowhere else, and it is knowable BEFORE spending — so it is
    # refused here rather than discovered as a provider 400 the founder pays for.
    #
    # The message is built from catalog data, not typed: the alternative model
    # is the roomiest one this deployment actually offers above this ceiling, and
    # the shortfall is compared against the project's own spoken words, so a
    # founder is never told to cut more than their script contains.
    if prompt_budget and len(prompt) > prompt_budget:
        capability = video_providers.capability(model_key)
        alternative = None
        for candidate in video_providers.list_capabilities():
            candidate_ceiling = int(candidate.get("prompt_char_limit") or 0)
            if candidate_ceiling <= int(prompt_budget):
                continue
            if alternative is None or candidate_ceiling > int(
                alternative.get("prompt_char_limit") or 0
            ):
                alternative = candidate
        raise HTTPException(
            status_code=409,
            detail=generation_planning.prompt_ceiling_refusal(
                prompt_chars=len(prompt),
                ceiling=int(prompt_budget),
                model_name=capability.get("name", ""),
                spoken_chars=len(plan_words.get("hook_line") or "")
                + len(plan_words.get("script") or ""),
                alternative=alternative,
            ),
        )

    # Stamp the strategy version whenever the project has one, not only when a
    # strategy was passed in, so the generation record says which strategy it
    # was rendered under.
    project_strategy = _project_strategy(project)
    has_strategy = bool((strategy or project_strategy or {}).get("hook_line"))
    strategy_version = int(project.get("strategy_version") or 0) if has_strategy else 0

    # Avatar influencer: the attached character_reference rides along as the
    # identity guide, following the proven legacy face-swap mechanics (identity
    # image + prompt lock, no V2V video involved). WHICH request field carries
    # it depends on the model, because providers differ: Hailuo 3 and HeyGen
    # take it as an input_references identity guide, while Hailuo 3 Max refuses
    # input_references outright (proven live: the serving provider 400s it)
    # and takes it as the opening frame instead, which OpenRouter documents
    # as supported for that model. Sending the wrong field spends a failed
    # submit at best — this branch is what keeps a Max render submittable.
    # Anything else (missing file, a model that takes no identity image at
    # all) fails the submission loudly rather than spending money on a
    # lookalike.
    face_path = await _studio_identity_references(
        project.get("assets") or [], model_key, user_id, template
    )
    if face_path is not None and video_providers.capability(model_key).get(
        "identity_via_first_frame"
    ):
        reference_image_path = face_path
        studio_references = None
    else:
        reference_image_path = None
        studio_references = (
            [_identity_reference_payload(face_path)] if face_path is not None else None
        )
    # No seam frame, no clip reference, no continuity plan to honour: there is
    # only ever one render, so there is never a previous clip to anchor to.
    # HeyGen used to appear in this list and no longer does: pinning the
    # photograph as its opening frame made the first second of every clip the
    # photo's own room and light instead of the planned scene, so its identity
    # now rides as a reference image and Hailuo 3 Max is the only first-frame
    # renderer left.
    continuity_frame = None

    generation_id = str(uuid.uuid4())
    now = now_iso()
    # `adjustments` recorded how a long request was split across passes. There is
    # one pass now, so the list is always empty; the column stays because
    # generations from before this change still carry a record of how they were
    # built.
    #
    # How long the clip will be cut down to once it lands, 0 for no trim.
    #
    # Always 0 now. The trim existed so a sub-floor HOOK could be rendered at
    # the provider's floor and cut down to the 2-3s the template asked for. There
    # is no separately-rendered hook any more: the piece is one render at one
    # length, already at or above the floor, so nothing is cut. The column and
    # the post-render cut in poll are kept because generations recorded before
    # this change still carry a non-zero value and must still be trimmed.
    trim_to_seconds = 0

    # Idempotency: ONE key means ONE render.
    #
    # The generate endpoint had no key and no in-flight check, so a double-tap,
    # a client-level retry of the same request, or the same project opened in two
    # tabs could each create a real billed job. Two lookups make that safe: the
    # first turns a plain repeat into the generation that already exists, and
    # the unique index catches the genuinely concurrent case that a check-then-
    # insert cannot, so the loser adopts the winner's row instead of running
    # a duplicate.
    #
    # This runs AFTER the gates and the prompt build but BEFORE the provider is
    # called, so a repeat costs no money and reaches no provider.
    claim_key = (idempotency_key or "").strip()[:120]
    if claim_key:
        already = await _fetch_one(
            "SELECT * FROM generations WHERE user_id = ? AND idempotency_key = ?",
            (user_id, claim_key),
        )
        if already:
            logger.info(
                "Idempotent repeat of generation %s (key %s): no second render",
                already.get("id"), claim_key,
            )
            existing = await _with_verdicts(_public_generation(already), user_id)
            existing["idempotent_replay"] = True
            return existing

    # The craft score of the words this render will speak, frozen onto the
    # row (ADR 0117). Scored here, over the repaired plan words, with the
    # same inputs the Review read uses, so the stored report is the score the
    # founder saw for these exact words — and a later performance snapshot
    # can be joined against it. Advisory only: computing it can never refuse
    # the render, and empty words store no report rather than a zero score.
    frozen_quality_report = None
    if plan_words.get("hook_line") or plan_words.get("script"):
        frozen_quality_report = creative_quality.assess_spoken_quality(
            plan_words.get("hook_line"),
            plan_words.get("script"),
            hook_seconds=project.get("hook_seconds") or 3,
            total_seconds=project.get("duration_seconds") or 0,
            app_name=(profile.get("brand_name") or "").strip(),
            allows_question=True,
        )

    try:
        await _execute(
            """INSERT INTO generations
           (id, studio_project_id, brand_profile_id, template_id, template_version,
            script_version, model, model_id, requested_duration, duration, status,
            segment_role, segment_index, strategy_version, continuity, trim_to_seconds,
            attempt, prompt_used, adjustments, retryable, approved,
            requested_at, created_at, updated_at, user_id, idempotency_key, camera_setup, location, final_beat, quality_report)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (generation_id, project["id"], project.get("brand_profile_id"),
         project.get("template_id"), project.get("template_version"),
         project.get("script_version"), model_key, cap["id"],
         requested, seconds, segment_role, int(segment_index or 0), strategy_version,
         json.dumps(continuity) if continuity else None, trim_to_seconds,
         attempt, prompt, json.dumps([]), now, now, now, user_id,
         claim_key or None, camera_setup,
         ((strategy or {}).get("scene") or {}).get("location") or "",
         ((strategy or {}).get("final_beat") or "") or None,
         json.dumps(frozen_quality_report) if frozen_quality_report else None),
        )
    except Exception as exc:
        # The unique index refused this row, which means a concurrent request
        # with the same key won the race between our SELECT and this INSERT.
        # That request is already running, so adopting its row is the correct
        # outcome: the founder asked once and gets one video. Any
        # other failure is a real error and must not be swallowed here.
        if claim_key and "UNIQUE" in str(exc).upper():
            winner = await _fetch_one(
                "SELECT * FROM generations WHERE user_id = ? AND idempotency_key = ?",
                (user_id, claim_key),
            )
            if winner:
                logger.info(
                    "Concurrent idempotent request lost the race for key %s: "
                    "returning generation %s, no second render",
                    claim_key, winner.get("id"),
                )
                adopted = await _with_verdicts(_public_generation(winner), user_id)
                adopted["idempotent_replay"] = True
                return adopted
        raise

    # Behavior: submitting IS moving forward. The render locks in everything
    # that produced it — the goal, the template, the plan and the script — so
    # each is recorded as adopted, the strongest positive signal in the loop.
    # Dedupe keeps repeats (retries, re-renders of the same version) to one
    # row per item per project.
    _adopt_kind = ""
    if project.get("content_angle_id"):
        _adopt_angle = await _fetch_one(
            "SELECT kind FROM content_angles WHERE id = ?", (project["content_angle_id"],))
        _adopt_kind = ((_adopt_angle or {}).get("kind") or "").strip()
    _adopt_objective = template_library.normalize_objective(project.get("objective") or "")
    await _record_behavior(
        "adopted", "goal", user_id,
        brand_profile_id=project.get("brand_profile_id") or "",
        studio_project_id=project["id"],
        detail=f"objective={_adopt_objective};kind={_adopt_kind}")
    if project.get("template_id"):
        await _record_behavior(
            "adopted", "template", user_id,
            brand_profile_id=project.get("brand_profile_id") or "",
            studio_project_id=project["id"],
            template_id=project["template_id"])
    await _record_behavior(
        "adopted", "plan", user_id,
        brand_profile_id=project.get("brand_profile_id") or "",
        studio_project_id=project["id"],
        detail=f"strategy v{int(strategy_version or 0)}")
    await _record_behavior(
        "adopted", "script", user_id,
        brand_profile_id=project.get("brand_profile_id") or "",
        studio_project_id=project["id"],
        detail=f"script v{int(project.get('script_version') or 0)}")

    try:
        submitted = await _log_model_call(
            "video_submit", "video", cap["id"],
            lambda: generate_video(
                prompt=prompt,
                duration=seconds,
                model=model_key,
                reference_image_path=reference_image_path,
                input_references=studio_references,
                # The previous clip's final frame becomes this clip's first
                # frame. This is the mechanism that makes the extension read
                # as a continuation rather than a new scene.
                continuity_frame_path=continuity_frame,
                # Default to native audio when the provider offers it; the plan's
                # sound direction is already written into the prompt.
                generate_audio=(
                    bool(cap.get("supports_native_audio"))
                    if generate_audio is None
                    else bool(generate_audio)
                ),
                # A per-render resolution override, already validated against
                # the model's supported_resolutions by the caller. None means
                # the catalog default.
                resolution=resolution,
            ),
            user_id,
            brand_profile_id=project.get("brand_profile_id"),
            studio_project_id=project["id"],
            generation_id=generation_id,
            template_id=project.get("template_id"),
        )
    except Exception as e:
        message = str(e)
        await _execute(
            "UPDATE generations SET status = 'failed', error = ?, retryable = ?, completed_at = ? WHERE id = ?",
            (message[:2000], 1 if generation_planning.is_recoverable_error(message) else 0,
             now_iso(), generation_id),
        )
        logger.error(f"Generation {generation_id} submission failed: {message}")
        if generation_planning.is_rate_limit_error(message):
            # Throttled before anything started — words owned by planning.
            raise HTTPException(
                status_code=502,
                detail=generation_planning.RATE_LIMIT_SUBMIT_DETAIL,
            )
        # Fail loudly with the provider's own words. The old message[:200] cut
        # the request summary mid-sentence ("The full p…") and hid the provider
        # excerpt ai_service now attaches. 800 chars keeps the summary +
        # excerpt intact; the full text stays in generations.error above.
        raise HTTPException(status_code=502, detail=f"Video generation failed to submit: {message[:800]}")

    job_id = submitted.get("id") or ""
    # Fold in what the provider actually accepted, so the record reflects the
    # real request rather than the intended one.
    reported = dict(continuity or {})
    reported.update(submitted.get("continuity") or {})
    await _execute(
        "UPDATE generations SET openrouter_job_id = ?, polling_url = ?, status = 'generating', "
        "continuity = ?, updated_at = ? WHERE id = ?",
        (job_id, submitted.get("polling_url") or "", json.dumps(reported), now_iso(),
         generation_id),
    )

    # Register with the persistent video store so a completed clip survives a
    # redeploy, exactly like the legacy face-swap path does.
    await _execute(
        """INSERT OR REPLACE INTO video_assets
           (job_id, user_id, r2_url, phase, source_video_id, source_hook_template_id, duration, created_at)
           VALUES (?, ?, '', ?, NULL, ?, ?, ?)""",
        (generation_id, user_id, segment_role, project.get("template_id"), seconds, now),
    )

    logger.info(
        f"Submitted generation {generation_id} ({segment_role}, segment {segment_index}, "
        f"attempt {attempt}) model={model_key} duration={seconds}s "
        f"continuity={reported.get('guarantee') or 'n/a'}"
    )
    detail = await _with_verdicts(_public_generation_detail(
        await _fetch_one("SELECT * FROM generations WHERE id = ?", (generation_id,))
    ), user_id)
    # What was rewritten, when anything was. The words in the render are not
    # quite the approved words, and the founder is told rather than left to hear
    # the difference once the clip comes back.
    if spoken_repair["rewritten"]:
        detail["spoken_repair"] = spoken_repair
    return detail


# --- Native Product Demo + CTA export ----------------------------------------
#
# The editor lives inside HookForge, on the same origin. There is no popup,
# redirect, new tab, iframe, opener, postMessage, or cross-app link: the
# completed Hook + Story generation is the editor's input, and the exported
# file is saved here as a child generation beside the original.
#
# This is storage, not generation. No model is called, nothing is submitted
# upstream, and it does not touch the ready gate — that guards a paid
# render, and this is the founder saving a file they just exported. It
# therefore cannot spend anything, which is why it is safe to leave off every
# gate.


# ---------------------------------------------------------------------------
# Chunked save: one request per part, none of them near the host ceiling
# ---------------------------------------------------------------------------
#
# Cloud Run answers any single HTTP/1 request over 32 MiB with a 413 before
# the app runs, and a 30s+ TikTok export at 8 Mbps clears that line. Past
# 8 MB the browser therefore sends the file in parts: every part stays far
# under the ceiling, the server joins them, and the joined file takes the
# exact same store path as a single-shot save.

DEMO_CTA_PART_MAX_BYTES = 8 * 1024 * 1024  # 8 MB
DEMO_CTA_TOTAL_MAX_BYTES = 200 * 1024 * 1024  # 200 MB ceiling, same as the asset library
DEMO_CTA_MAX_PARTS = 64
DEMO_CTA_PART_TTL_SECONDS = 24 * 3600  # abandoned part dirs are swept after a day


def _write_durable_upload_cache(target: Path, payload: bytes) -> None:
    """Stage bytes for validation/processing before the existing object upload."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as cache_file:
        cache_file.write(payload)


def _demo_cta_upload_dir(upload_id: str) -> Path:
    """Stage dir for one chunked save, resolved from a strict UUID."""
    # GENERATED_ID_RE is the repo's one UUID rule; anything else here is a
    # path traversal attempt, not an upload.
    if not GENERATED_ID_RE.match(upload_id or ""):
        raise HTTPException(
            status_code=400,
            detail="That upload id is not valid. Start the save again for a fresh one.",
        )
    return pipeline.UPLOADS_DIR / "demo-cta-parts" / upload_id


def _demo_cta_claim_upload(upload_dir: Path, user_id: str) -> None:
    """First part stamps the owner; every later part and the complete call must match."""
    owner_file = upload_dir / "owner"
    try:
        owner = owner_file.read_text(encoding="utf-8").strip()
    except OSError:
        owner = ""
    if not owner:
        upload_dir.mkdir(parents=True, exist_ok=True)
        owner_file.write_text(user_id, encoding="utf-8")
        return
    if owner != user_id:
        # 404, not 403: the id is unguessable, so a mismatch means a wrong
        # id rather than a forbidden one, and there is nothing to disclose.
        raise HTTPException(status_code=404, detail="That upload was not found.")


def _sweep_stale_demo_cta_parts() -> None:
    """Best-effort removal of part dirs older than a day."""
    # A closed tab mid-upload strands its parts; without a sweep they
    # accumulate forever on the host.
    base = pipeline.UPLOADS_DIR / "demo-cta-parts"
    try:
        children = list(base.iterdir())
    except OSError:
        return
    cutoff = time.time() - DEMO_CTA_PART_TTL_SECONDS
    for child in children:
        try:
            if child.is_dir() and child.stat().st_mtime < cutoff:
                shutil.rmtree(child, ignore_errors=True)
        except OSError:
            continue


async def _store_demo_cta_result(
    *,
    target: Path,
    filename: str,
    generation_id: str | None,
    user_id: str,
    background_tasks: BackgroundTasks = None,
) -> dict:
    """
    File one finished export into History, from bytes already on disk.

    Both save paths end here: the single-shot endpoint after writing the
    posted file, the chunked complete call after joining the parts. The row,
    the probe, the R2 copy and the signed playback URL are therefore one
    implementation, and a chunked save is indistinguishable on read from one
    that arrived whole.
    """
    result_id = target.stem
    parent = None
    if generation_id:
        parent = await _fetch_one(
            "SELECT id, studio_project_id, brand_profile_id, template_id, template_version, "
            "script_version, duration, model, model_id, segment_role, segment_index, "
            "strategy_version, post_kit, quality_report, location FROM generations WHERE id = ? AND user_id = ?",
            (generation_id, user_id),
        )
        if not parent:
            raise HTTPException(status_code=404, detail="Generation not found")

    if not (filename or "").lower().endswith((".mp4", ".mov", ".webm")):
        raise HTTPException(
            status_code=400, detail="Send a video file (MP4, MOV or WebM)."
        )

    # Measured rather than accepted from the caller. This is the record of what
    # was actually stored, and a client-supplied number would let a wrong length
    # into History.
    try:
        seconds = overlays.probe_duration(target)
    except Exception:
        seconds = 0.0

    # Unstored, exactly like a provider render: the row keeps the plain path and
    # _public_generation signs it on the way out, so it never expires in the row.
    stored_path = f"/api/media/videos/{result_id}.mp4"
    r2_url = ""
    if storage_service.is_configured():
        try:
            r2_url = storage_service.upload_video(user_id, result_id, target) or ""
        except Exception as exc:  # storage must not lose the exported clip
            logger.warning("Could not upload the native Demo + CTA export to R2: %s", exc)

    await _execute(
        """INSERT INTO generations
           (id, studio_project_id, brand_profile_id, template_id, template_version,
            script_version, model, model_id, requested_duration, duration, status,
            segment_role, segment_index, strategy_version, attempt,
            prompt_used, retryable, approved, post_kit, quality_report,
            requested_at, completed_at, created_at, updated_at, user_id, video_url, r2_url, location)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed',
                   ?, ?, ?, ?, ?, 0, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            result_id,
            parent.get("studio_project_id") if parent else None,
            parent.get("brand_profile_id") if parent else None,
            parent.get("template_id") if parent else None,
            parent.get("template_version") if parent else None,
            parent.get("script_version") if parent else None,
            parent.get("model") if parent else None,
            parent.get("model_id") if parent else None,
            seconds,
            seconds,
            # "demo_cta", never the parent's role. This row IS the marker that
            # provider_download_candidates and recovery_report both test to keep
            # the recovery walk off a native export -- substituting the parent
            # render would hand back a different video than the founder exported.
            #
            # It used to inherit the parent's segment_role, which meant a native
            # export was never marked as one and that whole guard was dead: the
            # writer was switched from variation_kind when the variations feature
            # was retired, and the reader followed but the writer did not. Set
            # unconditionally, because a standalone export with no parent is the
            # most clearly native of all.
            "demo_cta",
            int(parent.get("segment_index") or 0) if parent else 0,
            int(parent.get("strategy_version") or 0) if parent else 0,
            1,
            parent["id"] if parent else None,
            (parent.get("post_kit") if parent else None),
            (parent.get("quality_report") if parent else None),
            now_iso(),
            now_iso(),
            now_iso(),
            now_iso(),
            user_id,
            stored_path,
            r2_url,
            parent.get("location") if parent else None,
        ),
    )

    logger.info(
        "Stored native Demo + CTA export %s%s",
        result_id,
        f" for generation {generation_id}" if generation_id else " with no parent",
    )
    await _schedule_poster(background_tasks, result_id, user_id)
    return {
        "id": result_id,
        "status": "completed",
        "video_url": media_signing.build_signed_path(f"{result_id}.mp4"),
        "playback_url": media_signing.build_signed_path(f"{result_id}.mp4"),
        "poster_url": media_signing.build_signed_poster_path(f"{result_id}.jpg"),
        "r2_url": r2_url,
        "post_kit": _parse_post_kit(parent.get("post_kit") if parent else None),
    }


@api_router.post("/generations/{generation_id}/demo-cta-result", status_code=201)
@api_router.post("/demo-cta-result", status_code=201)
@observability.track_demo_cta_export
async def save_demo_cta_export(
    file: UploadFile = File(...),
    generation_id: str | None = None,
    user_id: str = Depends(get_current_user_id),
    background_tasks: BackgroundTasks = None,
):
    """
    Save the native Product Demo + CTA export into History.

    Two mounts on one handler, not two endpoints. The generation-scoped path
    takes the finished Hook + Story as its parent, so the export appears beside
    the original rather than replacing it — both downloads keep working and the
    lineage is recorded. The bare path is the same save with no parent, for
    someone who brought their own footage in through the editor rather than
    generating a hook first.

    Everything else is deliberately inherited from the parent rather than
    invented: template, script version, model and strategy come from the render
    this wrapped. Without one there is nothing to inherit, so those stay null —
    the row is a real finished clip with no ancestry, which History already
    displays without needing a parent.

    Still storage, not generation: no model call, nothing upstream, and none of
    the three spend gates. Those guard a paid render, and this is a file the
    founder already made.
    """
    # Checked again inside _store_demo_cta_result; here it refuses before
    # the bytes are read.
    if not (file.filename or "").lower().endswith((".mp4", ".mov", ".webm")):
        raise HTTPException(
            status_code=400, detail="Send a video file (MP4, MOV or WebM)."
        )

    result_id = str(uuid.uuid4())
    pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    target = pipeline.VIDEOS_DIR / f"{result_id}.mp4"
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="That file was empty.")
    _write_durable_upload_cache(target, payload)
    return await _store_demo_cta_result(
        target=target,
        filename=file.filename or "",
        generation_id=generation_id,
        user_id=user_id,
        background_tasks=background_tasks,
    )


@api_router.post("/demo-cta-uploads/{upload_id}/parts", status_code=201)
async def save_demo_cta_part(
    upload_id: str,
    index: int = Form(...),
    total: int = Form(...),
    chunk: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    """
    Stage one part of a chunked export save.

    The browser slices files past 8 MB so no single request trips the
    host's 32 MB ceiling; parts arrive in any order and the complete call
    joins them. Every refusal here names its remedy, because a part that
    cannot stage must tell the uploader what to re-send.
    """
    upload_dir = _demo_cta_upload_dir(upload_id)
    if not 1 <= total <= DEMO_CTA_MAX_PARTS:
        raise HTTPException(
            status_code=400,
            detail=f"Declare between 1 and {DEMO_CTA_MAX_PARTS} parts; got {total}.",
        )
    if not 0 <= index < total:
        raise HTTPException(
            status_code=400,
            detail=f"Part {index} is outside the declared 0..{total - 1} range.",
        )
    if total * DEMO_CTA_PART_MAX_BYTES > DEMO_CTA_TOTAL_MAX_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Those parts would join past the 200 MB save ceiling. Export a shorter clip.",
        )
    _demo_cta_claim_upload(upload_dir, user_id)
    total_file = upload_dir / "total"
    try:
        declared = int(total_file.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        declared = None
    if declared is None:
        total_file.write_text(str(total), encoding="utf-8")
    elif declared != total:
        raise HTTPException(
            status_code=400,
            detail=f"This upload already declared {declared} parts, not {total}. Start the save again.",
        )
    # Streamed, not read whole: a hostile part must not be able to park
    # arbitrary bytes in this process RAM on a 512 MB host.
    data = bytearray()
    while True:
        piece = await chunk.read(1024 * 1024)
        if not piece:
            break
        data += piece
        if len(data) > DEMO_CTA_PART_MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Part {index} is over 8 MB; keep every part under 8 MB so no single request trips the "
                    "host's 32 MB ceiling."
                ),
            )
    (upload_dir / f"{index:06d}.part").write_bytes(bytes(data))
    _sweep_stale_demo_cta_parts()
    return {"upload_id": upload_id, "index": index, "total": total, "bytes": len(data)}


@api_router.post("/demo-cta-uploads/{upload_id}/complete", status_code=201)
@observability.track_demo_cta_export
async def complete_demo_cta_upload(
    upload_id: str,
    payload: DemoCtaUploadCompleteRequest,
    user_id: str = Depends(get_current_user_id),
    background_tasks: BackgroundTasks = None,
):
    """
    Join a chunked upload's staged parts and file the export into History.

    The join is verified before anything is stored: every declared part
    must be present, in order, under the total ceiling. The joined file
    then takes the exact same store path as a single-shot save.
    """
    upload_dir = _demo_cta_upload_dir(upload_id)
    if not upload_dir.is_dir():
        raise HTTPException(status_code=404, detail="That upload was not found.")
    _demo_cta_claim_upload(upload_dir, user_id)
    try:
        declared = int((upload_dir / "total").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        declared = None
    if declared != payload.total:
        raise HTTPException(
            status_code=400,
            detail="The part count changed mid-save. Send every part again under one count.",
        )
    missing = [i for i in range(payload.total) if not (upload_dir / f"{i:06d}.part").is_file()]
    if missing:
        shown = ", ".join(str(i) for i in missing[:5])
        more = "" if len(missing) <= 5 else f" and {len(missing) - 5} more"
        raise HTTPException(
            status_code=409,
            detail=f"Part {shown}{more} of {payload.total} never arrived. Re-send the missing parts, then complete again.",
        )
    size = sum((upload_dir / f"{i:06d}.part").stat().st_size for i in range(payload.total))
    if size > DEMO_CTA_TOTAL_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail="The joined file is over 200 MB; saves are capped at 200 MB. Export a shorter clip.",
        )
    if size == 0:
        raise HTTPException(status_code=400, detail="No video arrived in those parts.")
    result_id = str(uuid.uuid4())
    pipeline.VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
    target = pipeline.VIDEOS_DIR / f"{result_id}.mp4"
    with target.open("wb") as out:
        for i in range(payload.total):
            with (upload_dir / f"{i:06d}.part").open("rb") as part:
                shutil.copyfileobj(part, out, length=1024 * 1024)
    row = await _store_demo_cta_result(
        target=target,
        filename=payload.filename,
        generation_id=payload.generation_id,
        user_id=user_id,
        background_tasks=background_tasks,
    )
    shutil.rmtree(upload_dir, ignore_errors=True)
    _sweep_stale_demo_cta_parts()
    return row


# Provider-clip download hardening: attempts, per-attempt timeout, and backoff
# between attempts. Bigger than the old single 180s attempt because H3 Max
# renders 2K files that take longer over Render's network.
_DOWNLOAD_ATTEMPTS = 3
_DOWNLOAD_TIMEOUT = 240
_DOWNLOAD_BACKOFF = (2, 5)
# Browser-like headers for the same reason: some provider CDNs refuse
# non-browser clients while the URL plays fine in a browser.
_DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "video/mp4,video/*;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _is_complete_mp4(path: Path) -> bool:
    """
    Whether a file at least claims to be a finished, playable MP4.

    A `moov` atom is the index every player seeks through, and for a
    non-fragmented file the provider writes it at the end -- so its absence is
    the reliable signal that the transfer stopped early. Checking it costs one
    small read and is the difference between "re-fetch this" and "hand the
    founder an unplayable file and call the render saved".

    This used to carry its own probe, and that is how it went wrong twice. The
    probe searched the first and last 4KB for the bytes "moov", but those four
    bytes are the START of a box whose body is the sample tables -- tens of
    kilobytes on a real render -- so on any file big enough to matter the tag
    fell outside the window and a finished, playable clip was reported as
    truncated. It also had no way to notice a file that kept its index but lost
    its media.

    Both problems are storage_service's to solve, so this delegates rather than
    keeping a second copy that can drift again. It also means the download gate,
    the freshness check, the retry pre-check and the upload gate all agree by
    construction, rather than four call sites agreeing by luck.
    """
    return storage_service.is_usable_video(path)


def _http_video_source(value) -> str:
    try:
        parsed = urlsplit(str(value or ""))
        if parsed.scheme in ("http", "https") and parsed.netloc:
            # A missing app-local file must not be fetched from the same dead URL.
            if parsed.path.startswith("/api/media/videos/"):
                return ""
            return str(value)
    except ValueError:
        pass
    return ""


def provider_download_candidates(row: dict, fresh_url: str = "") -> list[tuple[str, str]]:
    """
    Every place this render's bytes could still come from, best first.

    Why a list and not one URL
    --------------------------
    There are three, and they die independently:

      1. the link the poll just handed back,
      2. the `video_url` stored on the row -- a temporary provider link,
      3. the content endpoint re-derived from `openrouter_job_id`.

    (2) is the one that expires, and it is the one this used to pick first and
    commit to. So a row whose stored link had lapsed failed the repair outright
    even though (3) -- a stable path, authenticated with the same bearer token
    the poll used -- would still have served the clip. The failure looked like
    "this video is gone" when the video was sitting behind the next source in
    the list.

    Order is preference: freshest first, derived last because it costs a
    derivation and is the last resort. Duplicates are collapsed, because a fresh
    poll URL is very often byte-identical to the stored one and retrying a dead
    link three times before falling through is exactly the wasted time this
    removes.

    Labels exist so a failure can say WHICH source refused, rather than
    flattening three different answers into one sentence.

    Native exports return nothing at all: a Demo + CTA export has no provider
    rendition, and substituting its parent render would hand back a different
    video than the founder exported. That exclusion is load-bearing.
    """
    if row.get("segment_role") == "demo_cta":
        return []
    ordered = [
        ("fresh poll link", fresh_url),
        ("stored provider link", row.get("video_url")),
        ("provider content endpoint", ai_service.video_content_url(
            row.get("openrouter_job_id") or "")),
    ]
    seen: set[str] = set()
    candidates: list[tuple[str, str]] = []
    for label, raw in ordered:
        url = _http_video_source(raw)
        if not url or url in seen:
            continue
        seen.add(url)
        candidates.append((label, url))
    return candidates


def _recovery_sources(row: dict, fresh_url: str = "") -> tuple:
    """
    The durable copy, and the best provider source.

    Kept as a pair because two callers want a yes/no "is anything reachable at
    all" answer rather than the ordered list. The provider side delegates to
    provider_download_candidates so the pre-check and the repair can never
    disagree about what exists.
    """
    durable = _http_video_source(row.get("r2_url"))
    candidates = provider_download_candidates(row, fresh_url)
    return durable, (candidates[0][1] if candidates else "")


async def _probe_media_source(url: str, timeout: int = 20) -> str:
    """
    Whether a source would serve bytes RIGHT NOW, as one short word.

    For the dry run, so "would repair" is a fact rather than a guess about a
    string being non-empty. Three ways to be wrong in opposite directions, all
    of which this is built against:

      - It must send the same auth the real downloader sends. Without the bearer
        token a perfectly good link answers 403 and the report declares a
        recoverable video lost -- the exact failure this is meant to prevent.
      - It must not pull the file. A server that ignores Range will happily
        start streaming 50MB, so the response is streamed and abandoned after
        the first chunk rather than read.
      - It must distinguish "refused" from "unreachable". A DNS failure and a
        403 need different conclusions about whether to wait.

    Returns one of: alive, refused, missing, server-error, unreachable, unknown.
    """
    headers = dict(_DOWNLOAD_HEADERS)
    headers.update(ai_service.provider_download_headers(url))
    headers["Range"] = "bytes=0-0"
    try:
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, headers=headers
        ) as client:
            async with client.stream("GET", url) as response:
                # Touch the body so a server that only errors on first byte is
                # seen, then stop. One chunk is a few KB at most.
                async for _chunk in response.aiter_bytes():
                    break
                code = response.status_code
    except httpx.HTTPStatusError:
        return "refused"
    except Exception:
        return "unreachable"
    if code in (200, 206):
        return "alive"
    if code in (401, 403):
        return "refused"
    if code in (404, 410):
        return "missing"
    if code == 429:
        # Rate limited is not a verdict on the link.
        return "unknown"
    if 500 <= code < 600:
        return "server-error"
    return "unknown"


async def _download_generation_video(video_url: str, generation_id: str) -> tuple:
    """Download a finished clip into storage/videos for reuse and R2 upload.

    Returns (path, error_detail): path is the saved file, or None when every
    attempt failed — in which case error_detail names the last failure
    (HTTP status or exception) so the stored storage_error is
    self-diagnosing instead of a generic "could not be downloaded".

    Retried with backoff, because a single attempt made any transient blip a
    permanent loss of the finished render's durable copy. Browser-like headers,
    because some provider CDNs refuse non-browser clients (403 to
    python-httpx's default User-Agent) while the same URL plays fine in a
    founder's browser — the failure seen on H3 Max's 2K files. A longer
    timeout than the old 180s, because those 2K files are bigger. 4xx
    responses (other than 429) are not retried: a rejection will not heal
    by asking again.

    The bearer token is the load-bearing part. `unsigned_urls` is a
    misleading name — those URLs are NOT presigned — so when one points back
    at the OpenRouter API the request must authenticate exactly as the poll
    did, and without it every completed render failed here with a 401 while
    the clip itself sat finished and unplayable. provider_download_headers()
    adds it for our own endpoints only, so a third-party storage URL never
    receives the account key. The legacy face-swap download has always sent
    it inline; this is that same header, applied to the studio path.
    """
    if not _http_video_source(video_url):
        return None, "No absolute HTTP(S) download source is available."
    destination = pipeline.VIDEOS_DIR / f"{generation_id}.mp4"
    target = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.download")
    target.parent.mkdir(parents=True, exist_ok=True)
    headers = dict(_DOWNLOAD_HEADERS)
    headers.update(ai_service.provider_download_headers(video_url))
    last_detail = "no attempt made"
    for attempt in range(1, _DOWNLOAD_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(
                timeout=_DOWNLOAD_TIMEOUT,
                follow_redirects=True,
                headers=headers,
            ) as client:
                async with client.stream("GET", video_url) as resp:
                    resp.raise_for_status()
                    with open(target, "wb") as fh:
                        async for chunk in resp.aiter_bytes():
                            fh.write(chunk)
            if target.exists() and target.stat().st_size > 0:
                if await asyncio.to_thread(storage_service.is_usable_video, target):
                    target.replace(destination)
                    return destination, None
                # A truncated container: the stream ended early or the process
                # died mid-write. Serving or uploading this would hand the
                # founder a file that cannot play, and a size check cannot tell
                # it from a good one. Fall through to the backoff rather than
                # `continue`, so a retry does not hammer the endpoint
                # immediately -- and delete the bad file now, so a later attempt
                # that fails before writing cannot leave it looking reusable.
                last_detail = "download was truncated (not a complete MP4)"
                logger.warning(
                    f"Generation {generation_id}: downloaded clip is not a complete "
                    f"MP4 ({target.stat().st_size} bytes, attempt "
                    f"{attempt}/{_DOWNLOAD_ATTEMPTS}); treating as failed."
                )
                try:
                    target.unlink()
                except OSError:
                    pass
            else:
                last_detail = "downloaded file was empty"
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            last_detail = f"HTTP {code} {(e.response.reason_phrase or '').strip()}".strip()
            logger.warning(
                f"Could not download generation video {generation_id} "
                f"(attempt {attempt}/{_DOWNLOAD_ATTEMPTS}): {last_detail} "
                f"auth={'yes' if headers.get('Authorization') else 'no'}"
            )
            # A 401 on a URL we just authenticated for is our bug, not the
            # provider's, and it used to be indistinguishable from a genuinely
            # expired link in the log. Name it so the next occurrence is a
            # two-minute fix instead of an investigation.
            if code in (401, 403) and headers.get("Authorization"):
                logger.error(
                    f"Provider clip for generation {generation_id} was refused WITH a "
                    f"bearer token (HTTP {code}) -- check OPENROUTER_API_KEY and "
                    f"whether this URL belongs to the configured OpenRouter account."
                )
            if code != 429 and 400 <= code < 500:
                break
        except httpx.TransportError as e:
            last_detail = type(e).__name__
            logger.warning(
                f"Could not download generation video {generation_id} "
                f"(attempt {attempt}/{_DOWNLOAD_ATTEMPTS}): {last_detail}"
            )
        except Exception as e:
            last_detail = type(e).__name__
            logger.warning(
                f"Could not download generation video {generation_id} "
                f"(attempt {attempt}/{_DOWNLOAD_ATTEMPTS}): {last_detail}"
            )
            break
        if attempt < _DOWNLOAD_ATTEMPTS:
            await asyncio.sleep(_DOWNLOAD_BACKOFF[attempt - 1])
    if target.exists():
        try:
            target.unlink()
        except OSError:
            pass
    return None, last_detail


async def _persist_generation_clip(row: dict, user_id: str, video_url: str = "") -> tuple:
    """
    Turn a finished provider render into a playable, durable clip.

    Returns (stored_url, storage_error, delivered_seconds):
      - stored_url is where the founder can watch and download it from, or None
        when nothing could be salvaged.
      - storage_error is the founder-facing explanation when the clip is
        degraded rather than lost, else None.
      - delivered_seconds is the length they will actually get, which is the
        trimmed length when a trim applied and the requested one otherwise.

    The whole post-download pipeline lives here — download, hook trim, canvas
    rescale, R2 upload, local-served fallback — because two callers need it to
    agree exactly. poll_generation runs it on the way to 'completed', and
    retry_generation_storage runs it to repair a row that already failed.

    That duplication is what caused the bug this exists to prevent: the studio
    path grew its own downloader without the bearer token the legacy one always
    sent, so a finished render could not be saved, and the only recovery
    endpoint required a local file that the failure had already deleted. One
    function, one downloader, one set of headers.

    `video_url` is the caller's fresh URL when it has one; otherwise the stored
    row's. Falls back to the provider's content endpoint, which is derivable
    from the job id and does not depend on the poll response having included a
    URL list.

    Reuses an existing local copy instead of re-downloading, so retrying after
    a pure upload failure costs one PUT rather than a full fetch, and a second
    poll of an already-saved generation costs nothing. "Existing" means
    container validation, not merely present: a file left truncated by a killed
    process is worthless, and reusing one would persist a clip that cannot
    play. Trim and rescale therefore run ONLY on a fresh download: both are
    idempotent in principle, but running them twice would rewrite the canonical
    file, and an extension bridges its next segment from that file's final
    frame.
    """
    generation_id = row["id"]
    trim_to = int(row.get("trim_to_seconds") or 0)
    local_path = pipeline.VIDEOS_DIR / f"{generation_id}.mp4"
    storage_error = None
    trim_note = ""

    fresh = not await asyncio.to_thread(storage_service.is_usable_video, local_path)
    # Durable only. The provider side is deliberately NOT taken from here: a
    # single "best" URL is what made an expired stored link fatal, and the whole
    # point of the repair is to walk the ordered list further down.
    durable, _first_provider = _recovery_sources(row, video_url)
    cloud_error = None
    durable_error = None
    restored = False
    if fresh and not video_url and storage_service.is_configured():
        try:
            recovered, cloud_error = await asyncio.to_thread(
                storage_service.restore_video, user_id, generation_id, local_path)
            restored = recovered is not None
        except Exception as error:
            cloud_error = "Cloud storage read failed (" + type(error).__name__ + ")."
        if restored:
            # These are already-delivered bytes: do not trim, rescale or upload
            # them again. Keep the stable locator, never a presigned URL in DB.
            return (row.get("r2_url") or storage_service.public_url(user_id, generation_id),
                    None, int(row.get("duration") or 0))
    if fresh:
        # Private R2 locators are not HTTP download sources; authenticated reads
        # above handle them. An external durable copy precedes the provider.
        if durable and not storage_service.is_managed_url(durable):
            recovered, durable_error = await _download_generation_video(durable, generation_id)
            if recovered:
                local_path = recovered
                restored = True
        if not restored:
            # Every remaining source, best first, until one serves bytes. Used
            # to be a single URL: the stored provider link, which is the one
            # that expires. A row whose stored link had lapsed therefore failed
            # here outright even though the content endpoint re-derived from the
            # job id would still have served the clip.
            candidates = provider_download_candidates(row, video_url)
            if not candidates:
                failures = " ".join(value for value in (cloud_error, durable_error) if value)
                if durable_error or (cloud_error and cloud_error not in (
                        "Cloud copy not found.", "Cloud storage is not configured.")):
                    return None, (
                        "The saved copy could not be recovered right now. Retry recovery "
                        "or check cloud storage access; this does not prove the video is lost. "
                        + failures
                    ), 0
                detail = (
                    "This video has no local copy and no recoverable cloud or provider copy, "
                    "so it cannot be recovered. Re-upload your saved export if you have it."
                )
                return None, detail + (f" {failures}" if failures else ""), 0
            attempts: list[str] = []
            for label, url in candidates:
                recovered, source_error = await _download_generation_video(url, generation_id)
                if recovered:
                    local_path = recovered
                    if len(candidates) > 1:
                        logger.info(
                            "Generation %s: recovered via %s after %d earlier source(s) "
                            "did not serve bytes",
                            generation_id, label, len(attempts),
                        )
                    break
                attempts.append(f"{label}: {source_error}")
            else:
                # Name every source and why it refused. One flattened sentence
                # cannot distinguish "wait and retry" from "this is gone", which
                # are the only two things the founder can do about it.
                return None, (
                    "The provider clip could not be downloaded for durable storage ("
                    + "; ".join(attempts) + ")."
                ), 0

    # One encode at a time box-wide (see _FFMPEG_SLOT): trim, rescale and the
    # camera cut are sequential here, but a concurrent poster encode from another
    # request would stack on top of them. R2 upload below stays outside the
    # gate — network, not encode.
    if fresh and not restored:
        async with _FFMPEG_SLOT:
            # Apply the hook trim IN PLACE, before storage and before the row
            # records a length. The canonical path is also what an extension
            # bridges from (the previous clip's FINAL FRAME), so a trimmed
            # hook that sat beside the full render as a sidecar would make
            # every continuation resume from a frame the viewer never saw.
            if trim_to > 0:
                trimmed = await pipeline.replace_with_trimmed(local_path, trim_to)
                if trimmed:
                    local_path = trimmed
                    trim_note = f"Cut down to {trim_to}s."
                    logger.info(
                        f"Generation {generation_id}: hook trimmed to {trim_to}s "
                        f"(rendered at a length the provider cannot go below)"
                    )
                else:
                    # Keep the full render rather than lose it, and say so:
                    # the delivered clip is longer than was asked for.
                    storage_error = (
                        f"Could not cut the hook down to {trim_to}s, so it is "
                        f"delivered at its full rendered length."
                    )
                    logger.warning(
                        f"Generation {generation_id}: trim to {trim_to}s failed; "
                        f"delivering the untrimmed render."
                    )

            # Deliver on the platform's canvas. The cheaper providers render
            # below it -- Grok Imagine Video at 720p -- and a founder posting to
            # TikTok wants 1080x1920 rather than whatever the model emitted.
            # Applied after the trim so the scaled clip is the canonical file:
            # it is what an extension would bridge from, and what the preview
            # and the plain download then serve.
            #
            # Soft by design. The scale resamples and adds no detail, so failing
            # here costs resolution and nothing else, and the un-rescaled clip
            # is still a watchable video.
            rescaled, rescale_warnings = await overlays.rescale_to_canvas(local_path)
            if rescaled:
                local_path = rescaled
            elif rescale_warnings:
                logger.warning(
                    f"Generation {generation_id}: canvas resize failed "
                    f"({rescale_warnings[0]}); the clip is delivered at its "
                    f"rendered size."
                )

            # Apply the single centered 1.10x zoom after canvas resize, before
            # upload. Fresh downloads only: canonical clips must never zoom twice.
            # Start at 70% of hook_seconds, ease for 0.6s, then hold to the end.
            # The model alone generates the orbit; there is no lateral crop.
            # Existing soft-failure behavior still preserves a watchable clip.
            try:
                project_row = await _fetch_one(
                    "SELECT hook_seconds FROM studio_projects WHERE id = ?",
                    (row.get("studio_project_id") or "",),
                )
                # Only hook duration sets the processing timestamp. Legacy
                # strategy.camera_beat.at must not override the 70% ratio.
                move_at = overlays.camera_beat_seconds(
                    (project_row or {}).get("hook_seconds"),
                )
            except (TypeError, ValueError):
                move_at = 0.0
            if move_at > 0 and (row.get("camera_setup") or "handheld") != "fixed":
                moved, move_warnings = await overlays.apply_camera_move(local_path, move_at)
                if moved:
                    local_path = moved
                elif move_warnings:
                    logger.warning(
                        f"Generation {generation_id}: camera move skipped "
                        f"({move_warnings[0]}); delivering without it."
                    )

    stored_url = await asyncio.to_thread(
        storage_service.upload_video, user_id, generation_id, Path(local_path))
    if not stored_url:
        # R2 is unconfigured or the upload failed, but the local copy
        # survived and /api/media serves it. Record that instead of
        # leaving r2_url empty, because an empty r2_url makes the
        # panel fall back to the provider's unsigned link — which
        # expires, and then an already-generated video will not play.
        stored_url = served_media_path(Path(local_path))
        if stored_url:
            storage_error = (
                "Saved to this server's storage rather than durable cloud "
                "storage, because the upload to cloud storage failed."
            )

    # The row records the length the founder will actually get, not the
    # length that was asked of the model.
    delivered_seconds = int(row.get("duration") or 0) if restored else (trim_to or int(row.get("duration") or 0))
    return stored_url, storage_error or trim_note, delivered_seconds


# ---------------------------------------------------------------------------
# Persist jobs: the durable queue in front of _persist_generation_clip
# ---------------------------------------------------------------------------
#
# A finished provider render becomes a durable clip in exactly one place —
# _persist_generation_clip above — but it used to be invoked inline by the
# poll that noticed the finish. If the container died between the provider
# finishing and the save landing, nothing recorded that the persist was
# owed: the row sat at `generating` until the stranded sweep happened to
# re-poll it and ask the provider again.
#
# Now the persist is queued before it is attempted (ADR 0120). Poll records
# a `persist_generation_clip` job, claims it, and runs it; the outcome is
# applied through the one function below, so the queued path and the sweep
# path cannot drift. A restart leaves the job in the table — claimed under
# a lease that lapses, or still pending — and the startup sweep drains it
# without re-asking the provider anything: the provider URL rides in the
# job payload.

_PERSIST_JOB_KIND = "persist_generation_clip"

# The lease holder name for jobs this process claims. Single-process today
# (the same assumption as _storage_repairs_in_flight); the pid keeps two
# processes' claims distinguishable in the jobs table if that ever changes.
_JOB_WORKER = f"proc-{os.getpid()}"


async def _enqueue_persist_job(generation_id: str, user_id: str, video_url: str = "") -> str:
    """Record that a finished render's persist is owed. Deduped per render."""
    return await _enqueue_job(
        _PERSIST_JOB_KIND,
        {"generation_id": generation_id, "user_id": user_id, "video_url": video_url},
        dedupe_key=f"persist:{generation_id}",
    )


async def _execute_persist_job(job: dict) -> tuple:
    """Run one persist job's work: _persist_generation_clip for its row."""
    payload = json.loads(job.get("payload") or "{}")
    generation_id = payload.get("generation_id") or ""
    row = await _fetch_one("SELECT * FROM generations WHERE id = ?", (generation_id,))
    if not row:
        raise RuntimeError(f"persist job names unknown generation {generation_id}")
    return await _persist_generation_clip(
        row, payload.get("user_id") or "anonymous", payload.get("video_url") or ""
    )


async def _execute_claimed_persist_job(job: dict) -> tuple:
    """
    Execute a claimed persist job and settle its bookkeeping.

    Returns the persist outcome. A raised persist fails the job (requeue or
    park, per attempts) and re-raises, so the caller keeps the error for
    its own reporting — poll turns it into the row's storage_error exactly
    as it did when the persist ran inline.
    """
    try:
        outcome = await _execute_persist_job(job)
    except Exception as e:
        await _fail_job(job["id"], _JOB_WORKER, f"{type(e).__name__}: {e}")
        raise
    payload = json.loads(job.get("payload") or "{}")
    await _complete_job(job["id"], _JOB_WORKER, result={
        "generation_id": payload.get("generation_id"),
        "stored_url": outcome[0],
        "storage_error": outcome[1],
        "delivered_seconds": outcome[2],
    })
    return outcome


async def _apply_persist_outcome(generation_id: str, user_id: str, video_url: str,
                                 stored_url, storage_error, delivered_seconds,
                                 background_tasks: BackgroundTasks = None) -> None:
    """
    Write a persist outcome onto the generation row — the one copy of this.

    Poll and the sweep's queue drain both land here, so a completion looks
    identical no matter which process ran the save: status flip, durable
    URL, delivered length, the frozen post kit and the poster scheduled
    the same way.
    """
    now = now_iso()
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
        # without it. Scheduled after the response so the save never stacks
        # two ffmpegs; with no BackgroundTasks (the sweep) it runs inline.
        await _schedule_poster(background_tasks, generation_id, user_id)


async def _persist_via_queue(generation_id: str, user_id: str, video_url: str,
                             background_tasks: BackgroundTasks = None):
    """
    Poll's path: record the persist job, claim it, run it, apply the outcome.

    Returns the persist outcome, or None when another worker already holds
    the job (the startup sweep draining in this same process) — that worker
    applies the outcome when it finishes, and the caller answers with the
    row's current state, exactly as for a throttled status check.
    """
    job_id = await _enqueue_persist_job(generation_id, user_id, video_url)
    job = await _claim_job_by_id(job_id, _JOB_WORKER)
    if job is None:
        return None
    outcome = await _execute_claimed_persist_job(job)
    await _apply_persist_outcome(
        generation_id, user_id, video_url,
        outcome[0], outcome[1], outcome[2], background_tasks,
    )
    return outcome


async def _drain_pending_persist_jobs(limit: int = 10) -> int:
    """
    Run queued persist jobs to completion. Returns jobs completed.

    The startup sweep calls this before re-polling stranded rows: a render
    whose persist was recorded before a restart is finished here from the
    job payload alone. Self-guarding by design — a queue that cannot be
    read (a test double's database, a missing table) drains nothing rather
    than failing the sweep it rides in.
    """
    done = 0
    try:
        for _ in range(max(1, int(limit))):
            job = await _claim_job(_JOB_WORKER, kind=_PERSIST_JOB_KIND)
            if job is None:
                break
            payload = json.loads(job.get("payload") or "{}")
            generation_id = payload.get("generation_id") or ""
            try:
                outcome = await _execute_claimed_persist_job(job)
            except Exception as e:
                logger.warning(
                    "Persist queue: job for %s did not run (%s: %s)",
                    generation_id, type(e).__name__, str(e)[:200],
                )
                continue
            await _apply_persist_outcome(
                generation_id, payload.get("user_id") or "anonymous",
                payload.get("video_url") or "",
                outcome[0], outcome[1], outcome[2], None,
            )
            done += 1
            logger.info(
                "Persist queue: completed the durable save for %s", generation_id
            )
    except Exception as e:
        logger.warning(
            "Persist queue drain did not complete (%s: %s)",
            type(e).__name__, str(e)[:200],
        )
    return done


# ---------------------------------------------------------------------------
# Stranded-render sweep
# ---------------------------------------------------------------------------
#
# A render is only ever resolved by polling: poll_generation is the single path
# that turns a finished provider job into a durable clip (download, trim/rescale,
# R2 upload, status flip). Nothing else does it.
#
# That left a real gap. Polling happens in exactly one place -- the studio
# GenerationPanel, on a project page, for that project's newest row -- so a
# render whose container died mid-flight was never polled again by anything. The
# provider finished it, the money was spent, the bytes existed at the provider,
# and the row sat at `generating` indefinitely. Two paid renders (a HeyGen and a
# Grok Lite) spent four days that way, invisible in History: no error, no retry
# affordance, because `retry_generation_storage` refuses any row that has not
# completed, and the UI's repair button is gated on a durable copy existing.
#
# So the reconcile has to be server-side and cannot depend on anyone visiting the
# right page. This runs once per container start, which on Cloud Run means every
# cold start -- and with min-instances 0 that is exactly when a killed render
# needs picking up.
#
# The threshold is deliberately far above the slowest render (~22 min). Polling
# sooner would call the provider for rows that are legitimately still rendering,
# for no gain: a sweep that races the real thing teaches nothing and spends calls.

_STRANDED_SWEEP_MIN_AGE_SECONDS = 30 * 60

# A sweep runs against the whole table, so it is bounded. A backlog larger than
# this drains across successive starts rather than in one pass -- a single cold
# start firing dozens of repairs at once is the exact overload the ffmpeg gate
# exists to prevent.
_STRANDED_SWEEP_MAX_ROWS = 10


async def _sweep_stranded_generations(
    min_age_seconds: int = _STRANDED_SWEEP_MIN_AGE_SECONDS,
    limit: int = _STRANDED_SWEEP_MAX_ROWS,
) -> int:
    """
    Poll renders stranded in `generating` by a dead container. Returns rows fixed.

    Oldest first, deliberately. A row that has been stranded longest has the
    highest chance its provider link has lapsed, so the rows most at risk are the
    ones worth spending the limited passes on. `created_at` rather than
    `updated_at`: a poll bumps `updated_at` on every visit, so a row polled
    repeatedly would look fresh forever and never qualify again.

    Only rows that actually reached the provider are considered. A row with no
    `openrouter_job_id` was never submitted, so there is nothing to reconcile --
    polling it would fail forever and burn a slot.
    """
    # Queued persist jobs first (ADR 0120): a render whose provider job
    # finished and whose persist was recorded before the container died is
    # completed from the job payload, without re-asking the provider.
    fixed = await _drain_pending_persist_jobs(limit=limit)

    cutoff = (
        datetime.now(timezone.utc) - timedelta(seconds=max(0, int(min_age_seconds)))
    ).isoformat()
    rows = await _fetch_all(
        "SELECT id, user_id, openrouter_job_id, status, created_at FROM generations "
        "WHERE status IN ('submitted', 'generating') "
        "AND COALESCE(created_at, requested_at, started_at) < ? "
        "ORDER BY COALESCE(created_at, requested_at, started_at) ASC LIMIT ?",
        (cutoff, max(1, int(limit))),
    )
    if not rows:
        return fixed

    logger.info(
        "Stranded-render sweep: %d row(s) in flight for over %ds",
        len(rows),
        int(min_age_seconds),
    )

    for row in rows:
        generation_id = row.get("id")
        # A `submitted` row with no job id was never submitted to the
        # provider — the container died between the insert and the call.
        # Mark it failed/retryable here so idempotency's next attempt with
        # the same intent key reconciles to a fresh provider call instead
        # of keeping the zombie row.
        if not (row.get("openrouter_job_id") or "").strip():
            if row.get("status") == "submitted":
                await _execute(
                    "UPDATE generations SET status = 'failed', "
                    "error = ?, retryable = 1, completed_at = ? WHERE id = ?",
                    ("Stranded before provider submission (container died between "
                     "row insert and provider call). This row never reached the "
                     "provider and was never charged. Retrying this render is safe.",
                     now_iso(), generation_id),
                )
                fixed += 1
                logger.info(
                    "Stranded sweep: marked %s failed (submitted, no job id)",
                    generation_id,
                )
            continue
        # Skip anything a founder is already repairing by hand. _run_storage_repair
        # holds this set for the same reason; two passes over one clip is how a
        # good download becomes a half-written file.
        if generation_id in _storage_repairs_in_flight:
            logger.info("Stranded sweep: %s already being repaired, skipping", generation_id)
            continue
        _storage_repairs_in_flight.add(generation_id)
        try:
            # poll_generation owns the whole resolve path, including the ffmpeg
            # gate via _persist_generation_clip -- so this inherits every guard
            # rather than re-implementing a lighter, unsafe version of it.
            # The row's own user_id, not the caller's. poll_generation reads and
            # writes rows scoped by user_id, so passing the wrong owner would find
            # nothing and report the row as unreconciled. Literal "anonymous"
            # matches what auth.py falls back to when no key is configured.
            updated = await poll_generation(
                generation_id, user_id=row.get("user_id") or "anonymous"
            )
            if updated and updated.get("status") == "completed":
                fixed += 1
                logger.info("Stranded sweep: recovered %s from the provider", generation_id)
        except Exception as e:
            # One bad row must not abandon the rest of the sweep, and must not
            # propagate into startup -- an exception here would mark the deploy
            # failed for a reconciliation nicety.
            logger.warning(
                "Stranded sweep: %s did not reconcile (%s: %s)",
                generation_id, type(e).__name__, str(e)[:200],
            )
        finally:
            _storage_repairs_in_flight.discard(generation_id)

    if fixed:
        logger.info("Stranded sweep: recovered %d of %d stranded render(s)", fixed, len(rows))
    return fixed


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------
@api_router.get("/feedback/catalog")
async def feedback_catalog():
    """Events, permitted reasons, and the automatic triggers, for the UI."""
    return feedback_mod.catalog()


async def _behavior_exists(user_id: str, event: str, step: str,
                           brand_profile_id: str = "", studio_project_id: str = "",
                           generation_id: str = "", template_id: str = "",
                           detail: str = "") -> str:
    """The id of an identical behavior row, or '' when this is new."""
    row = await _fetch_one(
        """SELECT id FROM feedback_events
           WHERE user_id = ? AND event = ? AND step = ?
             AND COALESCE(brand_profile_id, '') = COALESCE(?, '')
             AND COALESCE(studio_project_id, '') = COALESCE(?, '')
             AND COALESCE(generation_id, '') = COALESCE(?, '')
             AND COALESCE(template_id, '') = COALESCE(?, '')
             AND COALESCE(detail, '') = COALESCE(?, '')
           LIMIT 1""",
        (user_id, event, step, brand_profile_id, studio_project_id,
         generation_id, template_id, detail),
    )
    return (row or {}).get("id") or ""


async def _record_behavior(event: str, step: str, user_id: str,
                           brand_profile_id: str = "", studio_project_id: str = "",
                           generation_id: str = "", template_id: str = "",
                           detail: str = "") -> dict:
    """
    Server-side behavior emission: adopted/abandoned/generated with dedupe.

    These rows are written by the seams that know the founder moved forward,
    dropped something, or passed it over — the project update that switches a
    template, the plan overwrite of an unrendered script, the submit that
    renders. Never raises: a feedback row must not fail the render, plan or
    update it describes. Failures are logged loudly instead.
    """
    try:
        clean_step = feedback_mod.normalize_component(step)
        if event not in ("adopted", "abandoned", "generated") or not clean_step:
            logger.error("Refusing to record behavior %s on '%s': invalid pair", event, step)
            return {"recorded": False}
        clean_detail = (detail or "")[:500]
        existing = await _behavior_exists(
            user_id, event, clean_step, brand_profile_id, studio_project_id,
            generation_id, template_id, clean_detail)
        if existing:
            return {"id": existing, "deduped": True, "recorded": False}
        event_id = str(uuid.uuid4())
        await _execute(
            """INSERT INTO feedback_events
               (id, brand_profile_id, studio_project_id, generation_id, template_id,
                event, signal, reason, detail, step, created_at, user_id)
               VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?)""",
            (event_id, brand_profile_id or None, studio_project_id or None,
             generation_id or None, template_id or None,
             event, clean_detail, clean_step, now_iso(), user_id),
        )
        return {"id": event_id, "deduped": False, "recorded": True}
    except Exception:
        logger.exception("Behavior feedback insert failed for %s/%s", event, step)
        return {"recorded": False}


@api_router.post("/feedback", status_code=201)
async def record_feedback(payload: FeedbackRequest, user_id: str = Depends(get_current_user_id)):
    """
    Record feedback: an automatic trigger, an explicit reason, or both.

    Either half is valid on its own. An automatic signal carries no reason,
    because nothing knows the founder's judgment. An explicit reason carries no
    signal. Storing a guessed reason against a trigger would corrupt the
    "common regeneration reasons" aggregate, so it is never inferred here.

    A reason that does not belong to its event is refused rather than stored,
    so the table only ever holds codes that can be grouped meaningfully.
    """
    event = feedback_mod.normalize_event(payload.event)
    if not event:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown event '{payload.event}'. Known: {', '.join(feedback_mod.EVENTS)}.",
        )

    signal = feedback_mod.normalize_signal(payload.signal)
    declared_signal = (payload.signal or "").strip()
    if declared_signal and not signal:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown signal '{payload.signal}'.",
        )
    # A signal and an event must agree, otherwise the event is untrustworthy.
    if signal and feedback_mod.signal_event(signal) != event:
        raise HTTPException(
            status_code=400,
            detail=f"Signal '{signal}' belongs to "
                   f"'{feedback_mod.signal_event(signal)}', not '{event}'.",
        )

    reason = feedback_mod.normalize_reason(event, payload.reason)
    if (payload.reason or "").strip() and not reason:
        allowed = [r["key"] for r in feedback_mod.allowed_reasons(event)]
        raise HTTPException(
            status_code=400,
            detail=f"Reason '{payload.reason}' is not valid for {event}. "
                   f"Allowed: {', '.join(allowed) or 'none'}.",
        )
    # Thumbs verdicts judge one component (goal, template, plan, script or
    # video) and carry no signal or reason, so a thumb can never be miscounted
    # as an automatic trigger or a stated cause. Behavior events (adopted,
    # abandoned, generated) are the same shape: the behavior names its
    # component, and the behavior itself is the fact, so no signal or reason
    # is accepted on them either.
    is_thumb = event in ("thumb_up", "thumb_down")
    is_behavior = event in ("adopted", "abandoned", "generated")
    step = feedback_mod.normalize_component(payload.step)
    if is_thumb or is_behavior:
        if not step:
            raise HTTPException(
                status_code=400,
                detail=f"{'Thumbs' if is_thumb else 'Behavior'} feedback needs a valid component. "
                       f"Known: {', '.join(feedback_mod.COMPONENTS)}.",
            )
        if signal or reason:
            raise HTTPException(
                status_code=400,
                detail=f"{'Thumbs' if is_thumb else 'Behavior'} feedback carries no signal or reason; the step is the context.",
            )
    elif (payload.step or "").strip():
        if not step:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown step '{payload.step}'.",
            )
    if not signal and not reason and not is_thumb and not is_behavior:
        raise HTTPException(
            status_code=400,
            detail="Feedback needs a signal or a reason.",
        )

    # A reshown candidate is not new evidence: the same item filed again for
    # the same project collapses into the row already there, so a list that
    # re-renders does not spam the loop. The replay answers with the kept row.
    if is_behavior:
        dup_id = await _behavior_exists(
            user_id, event, step,
            (payload.brand_profile_id or "").strip(),
            (payload.studio_project_id or "").strip(),
            (payload.generation_id or "").strip(),
            (payload.template_id or "").strip(),
            (payload.detail or "")[:500],
        )
        if dup_id:
            return {"id": dup_id, "event": event, "signal": "", "reason": "",
                    "step": step, "deduped": True}

    event_id = str(uuid.uuid4())
    await _execute(
        """INSERT INTO feedback_events
           (id, brand_profile_id, studio_project_id, generation_id, template_id,
            event, signal, reason, detail, step, created_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (event_id, (payload.brand_profile_id or "").strip() or None,
         (payload.studio_project_id or "").strip() or None,
         (payload.generation_id or "").strip() or None,
         (payload.template_id or "").strip() or None,
         event, signal or None, reason or None, (payload.detail or "")[:500],
         step or None, now_iso(), user_id),
    )
    return {"id": event_id, "event": event, "signal": signal, "reason": reason,
            "step": step, "deduped": False}


@api_router.get("/feedback")
async def list_feedback(
    brand_profile_id: str = "", limit: int = 100, user_id: str = Depends(get_current_user_id)
):
    clauses = ["user_id = ?"]
    params: list = [user_id]
    if brand_profile_id.strip():
        clauses.append("brand_profile_id = ?")
        params.append(brand_profile_id.strip())
    rows = await _fetch_all(
        f"SELECT * FROM feedback_events WHERE {' AND '.join(clauses)} "
        "ORDER BY created_at DESC LIMIT ?",
        tuple(params) + (max(1, min(int(limit or 100), 500)),),
    )
    return {
        "feedback": rows,
        "summary": feedback_mod.summarize(rows),
        "components": feedback_mod.summarize_component_feedback(rows),
    }


# GET /api/dashboard is gone with the Dashboard page. It aggregated totals,
# unapproved profiles, research drafts and recent failures, all of which
# are already served where the work happens: GET /api/generations with a
# Failed badge and a Retry button for failures, and GET /api/app-profiles
# for approvals. Nothing read it but the page.
#
# GET /api/analytics went with the Analytics page for the same reason. It was
# an internal report on this operator's own activity, cost included, and the
# product does not meter that. Nothing else read it.
#
# What went dark with the Dashboard: the single line telling a founder their
# video is published by hand and never posted automatically. That line was
# moved to the studio footer rather than dropped, and TestNoPlatformAutomation
# is what actually guarantees the behaviour.
#


@api_router.get("/")
async def root():
    return {
        "message": "HookForge API",
        "ai_configured": bool(os.environ.get("OPENROUTER_API_KEY")),
    }


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------
def _log_storage_durability() -> None:
    """
    Say, once per boot, whether finished renders will persist.

    The media counterpart of _log_database_backend, with the same rule:
    report the configuration as it is, at an alarm level that matches what
    it costs. R2 unconfigured is a fine local default and a data-loss
    configuration in production — renders are the product, and on an
    ephemeral host an unconfigured R2 means every finished clip vanishes
    with the next deploy (ADR 0120).
    """
    if storage_service.is_configured():
        logger.info(
            "Cloud storage: R2 configured — finished renders persist across deploys."
        )
        return
    if hosted_environment():
        logger.critical(
            "Cloud storage (R2) is NOT configured in a production environment: "
            "finished renders will not persist across deploys. Set R2_ACCOUNT_ID, "
            "R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME."
        )
    else:
        logger.info(
            "Cloud storage (R2) is not configured; finished renders are served "
            "from local disk and will not persist across deploys. "
            "(fine for local dev)"
        )


@app.on_event("startup")
async def on_startup():
    # Retry init_db up to 3 times — Turso or network hiccups during a cold
    # deploy must not permanently kill the container (uvicorn exits with code 3
    # if this handler raises, and Render marks the deploy as failed).
    last_error: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            await init_db()
            break
        except Exception as e:
            last_error = e
            logger.error(f"init_db attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                await asyncio.sleep(2 * attempt)
    else:
        # All retries exhausted — log but do NOT re-raise. The app can still
        # serve non-DB requests; database requests fail loudly until Turso recovers.
        logger.critical(
            f"init_db failed after 3 attempts, starting anyway: {last_error}"
        )
    # AFTER init_db, deliberately: the disclosure reports the backend init_db
    # actually established (module global), never the configured one. Logging
    # it before would repeat the old lie — "Turso cloud" from config while the
    # connection had fallen back to ephemeral.
    _log_database_backend()
    _log_storage_durability()
    if not os.environ.get("OPENROUTER_API_KEY"):
        logger.warning(
            "OPENROUTER_API_KEY is not set. The app will run, but AI features "
            "(hook analysis, face swap, video generation) will return 503 until it is set."
        )
    # What OpenRouter will actually accept, compared against what the catalog
    # claims. Unauthenticated and free, so it costs nothing to run on every boot.
    # Last, because it is the only step here that touches the network for a
    # non-essential reason — and it cannot raise, so a slow provider delays the
    # log line and nothing else.
    try:
        await provider_capabilities.check_provider_drift()
    except Exception as e:  # defensive: the helper already swallows its own
        logger.warning(f"Provider capability check did not complete: {e}")

    # Whether the chat endpoints accept a `temperature` field is read from
    # OpenRouter's own per-endpoint listing rather than guessed from the model
    # family, so swapping AI_TEXT_MODEL / AI_VISION_MODEL to a model that takes
    # one (or does not) needs no code change. ANGLE_MODEL is in the list for the
    # same reason and because it is the one slug that can be swapped alone: left
    # out, its first angle call would pay a rejected-temperature round trip.
    # Same shape as the check above: free, unauthenticated, best-effort, and
    # never able to fail the boot — a failed lookup just leaves the offline
    # fallback in place.
    try:
        await ai_service.refresh_temperature_support(
            [ai_service.TEXT_MODEL, ai_service.VISION_MODEL, ai_service.ANGLE_MODEL]
        )
    except Exception as e:  # defensive: the helper already swallows its own
        logger.warning(f"Temperature support lookup did not complete: {e}")

    # Reconcile renders stranded by a dead container (see _sweep_stranded_generations).
    # As a background task, NOT awaited, for two reasons: a sweep that polls a
    # provider and runs ffmpeg would hold the cold start open for minutes and
    # Cloud Run counts request-serving latency, and it must never be able to fail
    # a deploy. Worst case it is skipped, exactly as it was before this existed.
    asyncio.create_task(_sweep_stranded_generations_safely())


async def _sweep_stranded_generations_safely():
    """
    The startup entry point: the sweep, with nothing able to escape it.

    Every uncaught exception in a task is logged by the loop and otherwise lost
    with a traceback that never reaches the deploy log — which is how a sweep bug
    would present as "the feature just silently doesn't run". A crash here is
    logged as one line, and startup continues regardless.
    """
    try:
        await _sweep_stranded_generations()
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.warning(f"Stranded-render sweep did not complete ({type(e).__name__}: {e})")


# ---------------------------------------------------------------------------
# Thumbnail proxy — serves TikTok cover images through our server to bypass
# CORS/referrer blocking. Frontend uses /api/proxy-thumb?url=<encoded_url>
# ---------------------------------------------------------------------------
@api_router.get("/proxy-thumb")
async def proxy_thumbnail(url: str = ""):
    """Proxy a thumbnail image to bypass TikTok's CORS/referrer restrictions."""
    if not url or not url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.tiktok.com/",
        }
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            from fastapi.responses import Response
            content_type = resp.headers.get("content-type", "image/jpeg")
            return Response(content=resp.content, media_type=content_type, headers={"Cache-Control": "public, max-age=86400"})
    except Exception:
        raise HTTPException(status_code=404, detail="Could not fetch thumbnail")


# Exact-match creation is disabled at the router boundary. The Discover,
# Saved Hooks, analysis, and legacy-history pages are gone too, so their
# endpoints were deleted outright rather than merely unregistered; what remains
# below is brand research and durable media. The implementation functions for
# the disabled creation paths are retained for existing records and shared
# media helpers, but none of these paths can create a face swap,
# customization, remix, or legacy video job.
DISABLED_LEGACY_CREATION_ROUTES = frozenset({
    "/face-swap",
    "/face-swap/status/{job_id}",
    "/face-swap/jobs",
    "/face-swap/generate-hook-video",
    "/face-swap/extend-video",
    "/face-swap/generate-video",
    "/face-swap/video-status/{job_id}",
    "/face-swap/generate-branded-prompt",
    "/videos/{video_id}/customize",
    "/videos/{video_id}/hook-engine",
    "/hook-motion-styles",
    "/video-models",
    "/customizations",
    "/customizations/{customization_id}",
    "/customizations/{customization_id}/remix-chat",
    "/customizations/{customization_id}/generate-video-prompt",
    "/customizations/{customization_id}/generate-remix-script",
    "/customizations/{customization_id}/video-jobs",
    "/video-jobs/{job_id}/generate-video",
    "/video-jobs/{job_id}/submit-video",
    "/video-jobs/{job_id}/poll",
    "/video-jobs/{job_id}",
})
api_router.routes[:] = [
    route for route in api_router.routes
    if getattr(route, "path", "") not in {
        f"/api{path}" for path in DISABLED_LEGACY_CREATION_ROUTES
    }
]


app.include_router(api_router)

# Signed media routes live in routers.media (single owner) but must register
# here, before the StaticFiles mount at the bottom, so they shadow it — and
# under the /api prefix, because every URL the backend mints for them
# (playback, poster, asset, frame, template) is /api/media/*. Mounted
# without the prefix they sat at /media/* and never matched: /api/media/*
# fell through to StaticFiles, so posters 404'd unless an eager hook had
# written the file (History previews rendered black), videos were served
# as unsigned static files with no byte ranges, and the lazy poster and
# cloud-restore paths never ran. test_architecture.py pins the mount.
from routers.media import (
    router as media_router,
    configure_media,
    serve_frame, serve_template_thumbnail, serve_video, download_video_clip,
    serve_poster, serve_asset,
    _parse_byte_range, _iter_file_range, _iter_r2_object,
    _VIDEO_FILENAME_RE, _POSTER_FILENAME_RE,
)
configure_media(
    _fetch_one, _ensure_analysis_frame, _ensure_template_thumbnail,
    _recover_missing_frame, _ensure_asset_file, _http_video_source,
    ffmpeg_slot=_FFMPEG_SLOT, generated_id_re=GENERATED_ID_RE,
)
app.include_router(media_router, prefix="/api")

app.mount("/api/media", StaticFiles(directory=str(pipeline.STORAGE_DIR)), name="media")

# An empty CORS_ORIGINS means "*", not "nobody". os.environ.get with a "*"
# default only covers the variable being unset; backend/.env ships the key
# with an empty value, and "".split(",") is [""], which matches no origin
# and fails every browser call with an opaque "Network Error" while curl
# keeps working. Strip blanks and fall back to open CORS rather than none.
_CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Structured request logs (method, path, status, request id, duration) live
# in observability.py. Registered here so CORS stays outermost and every
# request — including preflights — gets its one log line.
app.middleware("http")(observability.request_logging_middleware)

# Serve frontend static build (present in container/production deployments).
FRONTEND_BUILD_DIR = Path(__file__).parent.parent / "frontend_build"
if FRONTEND_BUILD_DIR.exists():
    app.mount(
        "/static",
        _CacheHeaderStaticFiles(directory=str(FRONTEND_BUILD_DIR / "static")),
        name="frontend_static",
    )

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = FRONTEND_BUILD_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return _spa_response()

