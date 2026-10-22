import asyncio
import hashlib
import io
import json
import logging
import os
import re
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

import aiosqlite
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
import claim_safety
import media_signing
import video_providers
import generation_planning
import recommendation_tags
import overlays
import provider_capabilities
import ai_service
import feedback as feedback_mod
from ai_service import (
    generate_video,
    poll_video_job, analyze_app_profile,
    generate_content_angles, generate_creative_plan,
    page_text_with_metadata,
    TEXT_MODEL,
    generate_video_strategy, normalize_strategy, generate_brand_templates,
    bind_spoken_words, spoken_budget,
)
from models import (
    AppProfileResearchRequest, ApproveAppProfileRequest,
    BrandProfileCreateRequest, BrandProfileUpdateRequest,
    CreateContentAngleRequest, UpdateContentAngleRequest,
    CreateStudioProjectRequest, UpdateStudioProjectRequest, GeneratePlanRequest,
    ObjectiveTemplatesRequest,
    StudioGenerationRequest,     UpdateAssetRequest, AttachAssetRequest,
    FeedbackRequest,
    GenerateStrategyRequest,
    APP_PROFILE_LIST_FIELDS,
    APP_PROFILE_EDITABLE_FIELDS,
    STUDIO_EDITABLE_FIELDS, STUDIO_TEXT_FIELDS,
    now_iso, row_to_dict,
)
from auth import get_current_user_id, get_optional_user_id

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

DB_PATH = ROOT_DIR / "storage" / "hookforge.db"

app = FastAPI(title="HookForge API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

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
# SQLite helpers
# ---------------------------------------------------------------------------
_TURSO_BOOT_SYNC_DONE = False

# What the last get_db() call actually established, as opposed to what the
# config asks for. "turso" is only ever set after a real connect+pull
# succeeded; anything that reports the backend reads this first, so the deploy
# log can never again claim cloud persistence while running ephemeral.
_ACTIVE_BACKEND = None


def _database_backend() -> str:
    """
    Which store this process is actually writing user data to.

    "turso" means the cloud database (survives redeploys); "local-sqlite"
    means a file on this machine's disk. The distinction is the difference
    between a profile surviving a deploy and silently vanishing with it, so
    anything that reports on the health of the deployment reads this rather
    than guessing from config.
    """
    return "turso" if TURSO_DATABASE_URL else "local-sqlite"


def _log_database_backend() -> None:
    """
    Say, once per boot and impossible to miss, where user data is going.

    Profiles vanishing on every deploy is exactly what local SQLite on an
    ephemeral host does, and it looks from the outside like the app "deleting"
    things. If that is the configuration, the deploy log must say so in plain
    language instead of letting the next data-loss report be the discovery.

    Reports the ACTUAL backend established by get_db (module global), not the
    configured one: a previous version logged "Turso cloud" from config while
    the connection had in fact fallen back to ephemeral, which is precisely
    backwards. Call only after init_db has run, so the actual value exists.
    """
    actual = _ACTIVE_BACKEND
    if actual == "turso" or (actual is None and _database_backend() == "turso"):
        # "turso" as an actual value is only ever set after a real
        # connect+pull succeeded, so this line can no longer claim cloud
        # persistence while running ephemeral. (The None branch covers a call
        # before any connection was opened; init_db always connects first.)
        logger.info("Database backend: Turso cloud — user data survives redeploys.")
        return
    if actual == "local-ephemeral-fallback":
        message = (
            "Database backend: EPHEMERAL local SQLite — Turso is configured but "
            "unreachable, so user data (profiles, projects, generations) will "
            "NOT survive a redeploy or restart."
        )
    else:
        message = (
            f"Database backend: local SQLite at {DB_PATH}. User data (profiles, "
            "projects, generations) will NOT survive a redeploy or restart."
        )
    if os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_NAME"):
        # Render sets these itself, so their presence means this process is on
        # Render's ephemeral filesystem rather than a dev laptop. Local SQLite
        # here is a data-loss configuration, not a dev default.
        logger.critical(
            message + " Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN (see render.yaml) "
            "or every deploy wipes the database."
        )
    elif actual == "local-ephemeral-fallback":
        logger.error(message)
    else:
        logger.info(message + " (fine for local dev)")


@asynccontextmanager
async def get_db():
    """Async context manager for database connections.

    When TURSO_DATABASE_URL is set, connects to a remote Turso database via
    libsql_experimental (cloud-persisted, survives Render redeploys).
    Otherwise falls back to local aiosqlite (for dev/testing).
    """
    use_turso = False
    global _TURSO_BOOT_SYNC_DONE, _ACTIVE_BACKEND
    if TURSO_DATABASE_URL:
        conn = None
        try:
            import libsql_experimental as libsql
            conn = libsql.connect(
                "hookforge.db",
                sync_url=TURSO_DATABASE_URL,
                auth_token=TURSO_AUTH_TOKEN,
            )
            # No PRAGMA journal_mode=WAL here, deliberately — and it must stay
            # out. Journal mode is a local-SQLite concern (kept on the local
            # branch below); on a libsql embedded replica the statement is
            # unsupported, and issuing it took down the whole Turso branch, so
            # every boot fell back to ephemeral storage while the config said
            # "Turso cloud". Durability on a replica comes from sync, not from
            # pragmas.
            #
            # Pull cloud state into the replica before anything reads it. A
            # freshly deployed container starts with an empty replica file, and
            # without this the first reads see no profiles at all — which looks
            # exactly like "the deploy deleted everything" even when the cloud
            # copy is intact. Retried on every connection until one succeeds
            # (flag stays False), so recovery from a blip is automatic; a
            # failed pull is FATAL to this attempt and falls back loudly below,
            # because an unsynced replica is operationally identical to local
            # SQLite while reporting as Turso — the worst combination.
            if not _TURSO_BOOT_SYNC_DONE:
                conn.sync()
                _TURSO_BOOT_SYNC_DONE = True
            use_turso = True
            _ACTIVE_BACKEND = "turso"
        except Exception as e:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
            # ERROR, not warning: from here on every write lands in an ephemeral
            # local file that the next redeploy wipes. Falling back keeps the
            # app serving, but it must never look routine in the logs.
            logger.error(
                f"Turso connection failed, falling back to EPHEMERAL local SQLite "
                f"(user data will not survive a restart): {e}"
            )
            use_turso = False
            _ACTIVE_BACKEND = "local-ephemeral-fallback"
    else:
        _ACTIVE_BACKEND = "local-sqlite"

    if use_turso:
        try:
            yield _LibsqlAsyncWrapper(conn)
        finally:
            conn.close()
    else:
        local_conn = await aiosqlite.connect(str(DB_PATH))
        local_conn.row_factory = aiosqlite.Row
        await local_conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield local_conn
        finally:
            await local_conn.close()


class _LibsqlAsyncWrapper:
    """
    Thin wrapper that gives a libsql_experimental sync connection the same
    async interface that aiosqlite provides (await conn.execute(), await
    conn.commit(), etc.) so the rest of the codebase doesn't need changes.
    """

    def __init__(self, conn):
        self._conn = conn

    async def execute(self, sql, params=()):
        return _CursorWrapper(self._conn.execute(sql, params))

    async def executescript(self, sql):
        self._conn.executescript(sql)
        self._conn.commit()
        if hasattr(self._conn, "sync"):
            try:
                self._conn.sync()
            except Exception as e:
                logger.warning(f"Turso sync after executescript failed (local replica is safe): {e}")

    async def commit(self):
        self._conn.commit()
        # Sync local embedded replica to/from Turso cloud.
        # Network hiccups during sync must not crash the caller — unsynced
        # writes are still durable in the local embedded replica and will be
        # pushed on the next successful sync.
        if hasattr(self._conn, "sync"):
            try:
                self._conn.sync()
            except Exception as e:
                logger.warning(f"Turso sync failed (writes are safe in local replica): {e}")

    async def close(self):
        pass  # handled by get_db's finally block


class _CursorWrapper:
    """Wraps a libsql cursor to provide awaitable fetchone/fetchall + description."""

    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def description(self):
        return self._cursor.description

    async def fetchone(self):
        return self._cursor.fetchone()

    async def fetchall(self):
        return self._cursor.fetchall()


async def init_db():
    """Create tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with get_db() as conn:
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                tiktok_url TEXT,
                niche TEXT,
                video_platform_id TEXT,
                creator TEXT,
                creator_display TEXT,
                title TEXT,
                description TEXT,
                view_count INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                share_count INTEGER DEFAULT 0,
                bookmark_count INTEGER DEFAULT 0,
                duration REAL DEFAULT 0,
                thumbnail_url TEXT,
                direct_video_url TEXT,
                hashtags TEXT,
                song_id TEXT,
                song_title TEXT,
                song_artist TEXT,
                song_album TEXT,
                song_duration INTEGER DEFAULT 0,
                song_cover_url TEXT,
                subtitles_url TEXT,
                subtitles_language TEXT,
                is_ad INTEGER DEFAULT 0,
                creator_followers INTEGER DEFAULT 0,
                creator_following INTEGER DEFAULT 0,
                creator_verified INTEGER DEFAULT 0,
                creator_bio TEXT,
                creator_avatar TEXT,
                status TEXT DEFAULT 'metadata_ready',
                local_video_path TEXT,
                last_analysis_id TEXT,
                error TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                video_id TEXT,
                frames TEXT,
                facial_expressions TEXT,
                body_language_gestures TEXT,
                pacing_cuts TEXT,
                text_overlays_timing TEXT,
                audio_cues_inferred TEXT,
                hook_summary TEXT,
                effectiveness_score INTEGER,
                key_hook_frame_index INTEGER,
                replicable_mechanics TEXT,
                created_at TEXT
            );

            -- Durable backups for the small extracted JPEGs listed in
            -- analyses.frames. The public frame URLs are metadata only; the
            -- actual files otherwise disappear on a clean container deploy.
            CREATE TABLE IF NOT EXISTS analysis_frame_assets (
                video_hash TEXT NOT NULL,
                filename TEXT NOT NULL,
                image_bytes BLOB NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (video_hash, filename)
            );
            CREATE INDEX IF NOT EXISTS idx_analysis_frame_assets_lookup
                ON analysis_frame_assets (video_hash, filename);

            CREATE TABLE IF NOT EXISTS customizations (
                id TEXT PRIMARY KEY,
                video_id TEXT,
                analysis_id TEXT,
                mode TEXT,
                person_photo_url TEXT,
                reference_frame_url TEXT,
                environment TEXT,
                background TEXT,
                clothing TEXT,
                custom_instructions TEXT,
                generation_spec TEXT,
                generated_images TEXT,
                generated_image_url TEXT,
                video_title TEXT,
                video_niche TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS video_jobs (
                id TEXT PRIMARY KEY,
                customization_id TEXT,
                video_id TEXT,
                brand_name TEXT,
                brand_goal TEXT,
                brand_details TEXT,
                target_duration_seconds INTEGER,
                prompt_breakdown TEXT,
                full_prompt_text TEXT,
                reference_image_ids TEXT,
                selected_image_ids TEXT,
                use_original_sound INTEGER DEFAULT 0,
                sound_reference TEXT,
                status TEXT DEFAULT 'prompt_ready',
                openrouter_job_id TEXT,
                video_url TEXT,
                error TEXT,
                created_at TEXT,
                requested_at TEXT
            );

            CREATE TABLE IF NOT EXISTS brand_profiles (
                id TEXT PRIMARY KEY,
                website_url TEXT,
                brand_name TEXT,
                brand_description TEXT,
                niche TEXT,
                products_services TEXT,
                target_audience TEXT,
                ideal_customer_profile TEXT,
                differentiation TEXT,
                tone_voice TEXT,
                raw_extracted_text TEXT,
                created_at TEXT,
                updated_at TEXT,
                -- App Profile extensions (template-studio workflow). Added to the
                -- fresh-install schema here; pre-existing DBs get them via the
                -- ADD COLUMN migration below.
                appstore_url TEXT,
                play_url TEXT,
                support_urls TEXT,
                notes TEXT,
                app_category TEXT,
                platforms TEXT,
                core_features TEXT,
                primary_use_cases TEXT,
                problems_solved TEXT,
                icp_segments TEXT,
                desired_outcomes TEXT,
                known_limitations TEXT,
                must_not_show TEXT,
                usage_moments TEXT,
                proof_moment TEXT,
                viewer_objections TEXT,
                outcome_statements TEXT,
                claims_approved TEXT,
                claims_review TEXT,
                claims_banned TEXT,
                ctas TEXT,
                video_themes TEXT,
                status TEXT DEFAULT 'draft',
                version INTEGER DEFAULT 1,
                approved_at TEXT,
                last_research_at TEXT,
                research_sources TEXT,
                pending_research TEXT
            );

            -- Provenance registry for every image written to storage/generated.
            --
            -- Video generation takes an `image_id` and loads
            -- generated/{image_id}.png. Existence on disk is not evidence of
            -- origin: storage/generated also receives previews derived from
            -- uploaded person photos, and a raw upload can be reached from
            -- there by traversal. This table is the record of what each
            -- generated image was actually derived FROM, so the video
            -- endpoints can require that the chain starts at a hook frame
            -- (frames/) or a saved template thumbnail (templates/) rather
            -- than at an arbitrary upload.
            --
            -- origin: 'customize' for previews derived from a saved hook frame.
            CREATE TABLE IF NOT EXISTS generated_images (
                id TEXT PRIMARY KEY,
                origin TEXT,
                job_id TEXT,
                target_image_url TEXT,
                user_id TEXT DEFAULT 'anonymous',
                -- Durable PNG backup. The working filesystem can disappear on
                -- a redeploy or differ between backend instances, while this
                -- database record remains available to restore the asset.
                image_bytes BLOB,
                created_at TEXT
            );

            -- Hook Template Library. Rows are ABSTRACT creative structures
            -- (opening mechanic, continuation shape, CTA pattern, required
            -- assets) that drive generation without any source video.
            --
            -- The legacy columns below (source_*, prompt_template,
            -- reference_video_path, facial_expressions, ...) belong to the
            -- older exact-match bookmark flow and are retained so existing
            -- saved templates and Face Swap keep working. Library templates
            -- leave them NULL and are driven by the structured_* columns.
            --
            -- Deliberately no `proven` flag: no template has internal
            -- performance data until the app's own history supplies it.
            CREATE TABLE IF NOT EXISTS hook_templates (
                id TEXT PRIMARY KEY,
                name TEXT,
                category TEXT,
                notes TEXT,
                source_video_id TEXT,
                source_analysis_id TEXT,
                source_tiktok_url TEXT,
                source_creator TEXT,
                source_title TEXT,
                thumbnail_url TEXT,
                -- Durable JPEG backup for the bookmark card. Template media is
                -- otherwise only a per-container cache and disappears on redeploy.
                thumbnail_bytes BLOB,
                facial_expressions TEXT,
                body_language_gestures TEXT,
                pacing_cuts TEXT,
                text_overlays_timing TEXT,
                audio_cues_inferred TEXT,
                hook_summary TEXT,
                effectiveness_score INTEGER,
                replicable_mechanics TEXT,
                prompt_template TEXT,
                reference_video_path TEXT,
                song_title TEXT,
                song_artist TEXT,
                times_used INTEGER DEFAULT 0,
                last_used_at TEXT,
                created_at TEXT,
                updated_at TEXT,
                -- Template Library fields (template-studio workflow).
                app_categories TEXT,
                audiences TEXT,
                objective TEXT,
                opening_structure TEXT,
                hook_seconds INTEGER,
                -- continuation_structure and cta_pattern are retired: a
                -- generated video is a hook and a middle, and the CTA is the
                -- founder's own. middle_structure replaces the first; nothing
                -- needs the second. Both stay in the schema because SQLite
                -- cannot cheaply drop a column across deployments.
                middle_structure TEXT,
                continuation_structure TEXT,
                cta_pattern TEXT,
                visual_style TEXT,
                camera_pacing TEXT,
                required_assets TEXT,
                default_duration INTEGER,
                content_slots TEXT,
                example_preview TEXT,
                -- Viewer-facing outcome line for the picker card. Display
                -- only: never read into a plan or render prompt.
                outcome TEXT,
                version INTEGER DEFAULT 1,
                archived INTEGER DEFAULT 0,
                is_favorite INTEGER DEFAULT 0,
                evidence_note TEXT,
                trend_evidence TEXT,
                origin TEXT DEFAULT 'bookmark',
                review_status TEXT DEFAULT 'approved',
                -- Brand that owns this template, for brand-tailored customs
                -- generated on profile approval. NULL means shared or legacy
                -- (curated rows, pre-scoping customs): visible everywhere.
                brand_profile_id TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_templates_brand
                ON hook_templates (brand_profile_id, archived);

            -- Content angles for one App Profile. Generated per app from the
            -- approved profile, each carrying the seven planning fields the
            -- studio needs: audience, problem, hook promise, feature, emotion,
            -- CTA, and the claims/limitations to respect.
            CREATE TABLE IF NOT EXISTS content_angles (
                id TEXT PRIMARY KEY,
                brand_profile_id TEXT,
                kind TEXT,
                label TEXT,
                target_audience TEXT,
                user_problem TEXT,
                hook_promise TEXT,
                app_feature TEXT,
                desired_emotion TEXT,
                recommended_cta TEXT,
                claims_to_respect TEXT,
                evidence TEXT,
                rank INTEGER DEFAULT 0,
                created_at TEXT,
                user_id TEXT DEFAULT 'anonymous'
            );
            CREATE INDEX IF NOT EXISTS idx_content_angles_profile
                ON content_angles (brand_profile_id, rank);

            -- Per-user favorites for shared library templates. Curated
            -- templates are team-wide (user_id='system'), so a favorite flag
            -- on the template row would leak one operator's preference to
            -- everyone. This table keeps it per user.
            CREATE TABLE IF NOT EXISTS template_favorites (
                template_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                created_at TEXT,
                PRIMARY KEY (template_id, user_id)
            );

            -- A studio project is one founder's in-progress video: the chosen
            -- App Profile, angle, objective, template (pinned to a version),
            -- assets, and the editable creative plan. The plan is separate from
            -- any generation so a founder can iterate on the script on text
            -- alone before generating a video.
            CREATE TABLE IF NOT EXISTS studio_projects (
                id TEXT PRIMARY KEY,
                brand_profile_id TEXT,
                content_angle_id TEXT,
                template_id TEXT,
                -- Pinned so a later library edit cannot silently change what
                -- this project was built against.
                template_version INTEGER,
                objective TEXT,
                audience TEXT,
                duration_seconds INTEGER,
                tone TEXT,
                hook_line TEXT,
                script TEXT,
                -- How many characters the arrival clamp cut from the model's
                -- script because it would not fit the middle's seconds. Kept so
                -- the Review step can say the script is shorter than the model
                -- wrote rather than leaving the founder to wonder. 0 or NULL
                -- means the plan fitted as written.
                plan_trimmed_chars INTEGER DEFAULT 0,
                beat_timeline TEXT,
                visual_direction TEXT,
                feature_emphasis TEXT,
                -- Replaces feature_emphasis: one sentence telling the founder what
                -- to record for their own demo. Stored on the project and shown on
                -- the Review step, and deliberately never passed to a render -- a
                -- feature instruction that reaches the prompt is a product demo
                -- being generated, and this workflow generates a hook and a middle
                -- only. feature_emphasis and cta stay in the schema because SQLite
                -- cannot cheaply drop a column across deployments; nothing reads
                -- or writes them.
                demo_brief TEXT,
                overlays TEXT,
                voice_direction TEXT,
                sound_direction TEXT,
                cta TEXT,
                assets TEXT,
                safety_report TEXT,
                safety_summary TEXT,
                -- The app-specific video strategy: hook concept, messaging,
                -- locked persona and scene, per-segment plan, and the
                -- continuity contract every later segment is held to. Stored
                -- on the project (not the generation) because both the hook
                -- and every extension read the SAME strategy — that shared
                -- read is what keeps an extension on-message.
                strategy TEXT,
                strategy_version INTEGER DEFAULT 0,
                -- The hook length the founder wants for the opening segment, in
                -- seconds. 0 means "not chosen yet", in which case the selected
                -- template's own hook_seconds decides. Kept separate from
                -- duration_seconds, which is the TOTAL video length: the hook is
                -- the first segment of it, not a shorter version of it.
                hook_seconds INTEGER DEFAULT 0,
                -- Whether the founder has declared they intend to extend this
                -- hook into a full video. 1 by default: the hook is the opening
                -- of a video, not a deliverable in its own right. Deliberately
                -- NOT load-bearing for generation — it changes what the studio
                -- offers and displays, never what gets rendered, so flipping it
                -- cannot invalidate a strategy and force a rebuild.
                extend_intent INTEGER DEFAULT 1,
                script_version INTEGER DEFAULT 0,
                status TEXT DEFAULT 'draft',
                created_at TEXT,
                updated_at TEXT,
                user_id TEXT DEFAULT 'anonymous'
            );
            CREATE INDEX IF NOT EXISTS idx_studio_projects_user
                ON studio_projects (user_id, updated_at);

            -- One row per submitted video generation.
            --
            -- The normal case is a SINGLE row per video: the hook and its
            -- continuation are produced by one model call so the clip is
            -- coherent. Additional rows only exist for a genuine second pass
            -- (duration beyond the provider's single-pass limit, an explicit
            -- extension, or a segment replacement after a recoverable
            -- failure), recorded via segment_role + parent_generation_id.
            --
            -- status ladder: submitted -> generating -> completed | failed,
            -- plus 'archived'. draft/ready_for_generation live on the studio
            -- project, not here, because no render is submitted before the
            -- founder asks for one.
            --
            -- There is deliberately no cost column. This app does not meter
            -- what a render costs the operator. Deployments created before
            -- that still carry the old cost_usd / cost_source columns; SQLite
            -- cannot drop them cheaply, so nothing reads or writes them and
            -- they stay dormant.
            CREATE TABLE IF NOT EXISTS generations (
                id TEXT PRIMARY KEY,
                studio_project_id TEXT,
                brand_profile_id TEXT,
                template_id TEXT,
                -- Provenance: which exact inputs produced this video.
                template_version INTEGER,
                script_version INTEGER,
                model TEXT,
                model_id TEXT,
                requested_duration INTEGER,
                duration INTEGER,
                status TEXT DEFAULT 'submitted',
                segment_role TEXT DEFAULT 'primary',
                -- What KIND of row this is: 'primary' for a rendered piece,
                -- 'demo_cta' for a native export filed in the editor. A native
                -- export has no provider rendition, so recovery must never
                -- substitute its parent render for it -- that guard tests this
                -- value. Distinct from segment_index below.
                segment_index INTEGER DEFAULT 0,
                -- Which strategy version produced this segment. A segment
                -- generated against a stale strategy is refused as a
                -- continuation, so an extension can never quietly disagree
                -- with the approved hook.
                strategy_version INTEGER DEFAULT 0,
                -- The continuity record for this submission: which anchors
                -- were wanted, which were actually attached, and what was
                -- degraded and why. Persisted so a founder can always see
                -- what the provider was actually given, rather than trusting
                -- a prompt that merely asked for continuity.
                continuity TEXT,
                -- Set once the founder approves this segment. Only approved
                -- segments are used as continuity anchors and included in the
                -- assembled video.
                approved INTEGER DEFAULT 0,
                approved_at TEXT,
                -- Seconds the finished clip was cut down to, 0 when it is the
                -- render as delivered. Set when the wanted hook length is below
                -- the provider's minimum, so the record shows the real length
                -- rather than only the length that was asked of the model.
                trim_to_seconds INTEGER DEFAULT 0,
                attempt INTEGER DEFAULT 1,
                openrouter_job_id TEXT,
                polling_url TEXT,
                video_url TEXT,
                r2_url TEXT,
                prompt_used TEXT,
                adjustments TEXT,
                error TEXT,
                storage_error TEXT,
                retryable INTEGER DEFAULT 1,
                requested_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                created_at TEXT,
                updated_at TEXT,
                user_id TEXT DEFAULT 'anonymous'
            );
            CREATE INDEX IF NOT EXISTS idx_generations_user
                ON generations (user_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_generations_project
                ON generations (studio_project_id, created_at);

            -- Asset library, scoped to one App Profile.
            --
            -- Scoping is what prevents an app's screenshots, logo, or
            -- character reference from leaking into another app's video: an
            -- asset is only resolvable through a project that points at the
            -- same brand_profile_id. Cross-app use is refused at generation
            -- time, not merely discouraged in the UI.
            CREATE TABLE IF NOT EXISTS assets (
                id TEXT PRIMARY KEY,
                brand_profile_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                name TEXT,
                notes TEXT,
                file_path TEXT NOT NULL,
                preview_path TEXT,
                content_type TEXT,
                duration_seconds REAL,
                -- Faces counted by the local detector at upload time. NULL
                -- means unknown (pre-existing rows, or detection unavailable);
                -- 0 or 2+ warns the founder before the provider's privacy
                -- filter refuses the photo at generation time.
                face_count INTEGER,
                -- Rights are the operator's assertion, recorded so a reviewer
                -- can see it was considered. Unconfirmed assets can be stored
                -- but are refused for production use.
                rights_confirmed INTEGER DEFAULT 0,
                -- Short human label used in prompts and the overlay report,
                -- e.g. "Onboarding" for a screenshot.
                label TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT,
                updated_at TEXT,
                user_id TEXT DEFAULT 'anonymous'
            );
            CREATE INDEX IF NOT EXISTS idx_assets_profile
                ON assets (brand_profile_id, status);

            -- (Retired: overlay_compositions lived here while burned-in
            -- captions were composited onto Hook + Story clips. The table is
            -- intentionally NOT created for fresh databases; rows left behind
            -- on older ones are inert and read by nothing.)
            -- (Retired: performance_entries held hand-typed views/likes/etc.
            -- per generation while manual result logging existed. The table is
            -- intentionally NOT created for fresh databases; rows left behind
            -- on older ones are inert and read by nothing.)

            -- Structured feedback, captured at the moment something happened so
            -- it can steer later recommendations and prompts for that app.
            --
            -- Two columns with deliberately different jobs:
            --   signal: a FACTUAL trigger, captured automatically
            --           (template_changed, regenerated, downloaded...). Always
            --           knowable without asking the founder anything.
            --   reason: a JUDGMENT about why, supplied explicitly
            --           (hook_too_weak, too_promotional...). Optional.
            --
            -- Keeping them apart matters: guessing a reason from a trigger
            -- would poison the "common regeneration reasons" aggregate with
            -- counterfactuals, since nothing knows the founder was unhappy
            -- with the hook specifically.
            --
            -- reason is a fixed vocabulary, not free text, so it can be
            -- aggregated at all.
            CREATE TABLE IF NOT EXISTS feedback_events (
                id TEXT PRIMARY KEY,
                brand_profile_id TEXT,
                studio_project_id TEXT,
                generation_id TEXT,
                template_id TEXT,
                event TEXT,
                signal TEXT,
                reason TEXT,
                detail TEXT,
                step TEXT,
                created_at TEXT,
                user_id TEXT DEFAULT 'anonymous'
            );
            CREATE INDEX IF NOT EXISTS idx_feedback_app
                ON feedback_events (brand_profile_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_feedback_event
                ON feedback_events (event, reason);
            CREATE INDEX IF NOT EXISTS idx_feedback_generation
                ON feedback_events (user_id, generation_id, created_at);

            -- Persistent video storage registry. Each row tracks a generated
            -- video uploaded to Cloudflare R2 so it survives container redeploys
            -- and remains accessible in the user's history until they delete it.
            CREATE TABLE IF NOT EXISTS video_assets (
                job_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'anonymous',
                r2_url TEXT NOT NULL,
                phase TEXT DEFAULT 'hook',
                source_video_id TEXT,
                source_hook_template_id TEXT,
                duration INTEGER,
                created_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_video_assets_user
                ON video_assets (user_id, created_at);

            -- Internal model-request ledger. Generations already carry status,
            -- but text/vision calls otherwise leave no trace. This table answers
            -- which model operation ran, whether it worked, and how long it took,
            -- without storing prompts or generated copy.
            CREATE TABLE IF NOT EXISTS model_requests (
                id TEXT PRIMARY KEY,
                operation TEXT NOT NULL,
                modality TEXT NOT NULL,
                model TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'completed',
                latency_ms INTEGER,
                error TEXT,
                brand_profile_id TEXT,
                studio_project_id TEXT,
                generation_id TEXT,
                template_id TEXT,
                research_run_id TEXT,
                created_at TEXT,
                user_id TEXT DEFAULT 'anonymous'
            );
            CREATE INDEX IF NOT EXISTS idx_model_requests_user
                ON model_requests (user_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_model_requests_operation
                ON model_requests (operation, status);

            -- Asset failures that would otherwise exist only as an HTTP error.
            -- Successful uploads need no event; a failed validation, missing
            -- file, rights refusal, or composition rejection does.
            CREATE TABLE IF NOT EXISTS asset_events (
                id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                reason TEXT NOT NULL,
                brand_profile_id TEXT,
                studio_project_id TEXT,
                generation_id TEXT,
                asset_id TEXT,
                asset_kind TEXT,
                filename TEXT,
                created_at TEXT,
                user_id TEXT DEFAULT 'anonymous'
            );
            CREATE INDEX IF NOT EXISTS idx_asset_events_user
                ON asset_events (user_id, created_at);
        """)
        # The Images API does not expose a provider job ID that can be resumed after
        # this process exits. Never leave interrupted app jobs polling forever.
        await conn.commit()

        # Migration: add columns that may be missing on a pre-existing DB (e.g. on Render's
        # persistent-ish free-tier disk from a previous deploy of this table).
        cursor = await conn.execute("PRAGMA table_info(brand_profiles)")
        existing_cols = {row[1] for row in await cursor.fetchall()}
        for col in ("ideal_customer_profile", "differentiation"):
            if col not in existing_cols:
                await conn.execute(f"ALTER TABLE brand_profiles ADD COLUMN {col} TEXT")
        # App Profile extensions for the template-studio workflow. TEXT columns
        # first, then the version/status bookkeeping with safe defaults.
        for col in (
            "appstore_url", "play_url", "support_urls", "notes", "app_category",
            "platforms", "core_features", "primary_use_cases",
            "problems_solved", "icp_segments", "desired_outcomes",
            "known_limitations", "must_not_show", "usage_moments", "proof_moment",
            "viewer_objections", "outcome_statements", "claims_approved", "claims_review",
            "claims_banned", "ctas", "video_themes", "status",
            "approved_at", "last_research_at", "research_sources",
            "pending_research",
        ):
            if col not in existing_cols:
                default = " DEFAULT 'draft'" if col == "status" else ""
                await conn.execute(f"ALTER TABLE brand_profiles ADD COLUMN {col} TEXT{default}")
        if "version" not in existing_cols:
            await conn.execute("ALTER TABLE brand_profiles ADD COLUMN version INTEGER DEFAULT 1")
        await conn.commit()

        # Migration: Template Library columns for hook_templates. TEXT first,
        # then INTEGER/flag columns with safe defaults so pre-existing saved
        # bookmarks keep working and simply gain NULL library fields.
        cursor = await conn.execute("PRAGMA table_info(hook_templates)")
        template_cols = {row[1] for row in await cursor.fetchall()}
        for col in (
            "app_categories", "audiences", "objective", "opening_structure",
            # middle_structure replaces continuation_structure. The retired pair
            # stay in the ADD list too: a database created before this change
            # has neither, and the seeding and listing queries below still name
            # both columns, so a fresh one has to match.
            "middle_structure", "continuation_structure", "cta_pattern", "visual_style",
            "camera_pacing", "required_assets", "content_slots", "evidence_note",
            "trend_evidence", "outcome",
            "origin", "review_status",
        ):
            if col not in template_cols:
                await conn.execute(f"ALTER TABLE hook_templates ADD COLUMN {col} TEXT")
        for col, decl in (
            ("hook_seconds", "INTEGER"),
            ("default_duration", "INTEGER"),
            ("version", "INTEGER DEFAULT 1"),
            ("archived", "INTEGER DEFAULT 0"),
            ("is_favorite", "INTEGER DEFAULT 0"),
        ):
            if col not in template_cols:
                await conn.execute(f"ALTER TABLE hook_templates ADD COLUMN {col} {decl}")
        # Saved bookmarks predate the library, so they are 'bookmark' origin
        # and stay approved. The Saved Hooks page and its endpoints are gone,
        # so these rows are dormant — reachable by nothing, deleted by nothing.
        # They are left in place deliberately: dropping user rows in a
        # migration is irreversible, and dormant rows cost nothing.
        await conn.execute(
            "UPDATE hook_templates SET origin = 'bookmark' "
            "WHERE origin IS NULL OR origin = ''"
        )
        await conn.commit()

        # Migration: drop and recreate cache tables if they're missing new columns
        # (these are just caches that rebuild on next request — no data loss).
        cache_tables_to_check = {
            # upload_timestamp is the newest column on these cache tables; if it's
            # missing the table predates publish-date support and is rebuilt.
            "videos": "is_ad",
            "video_jobs": "use_original_sound",
        }
        for table, required_col in cache_tables_to_check.items():
            cursor = await conn.execute(f"PRAGMA table_info({table})")
            cols = {row[1] for row in await cursor.fetchall()}
            if cols and required_col not in cols:
                logger.info(f"Migration: dropping and recreating {table} (missing column '{required_col}')")
                await conn.execute(f"DROP TABLE IF EXISTS {table}")
        await conn.commit()

        # Retired feed caches. The Discover feed is gone, so the tables that
        # fed it (trending/curated video caches and their TTL metadata) have
        # no readers and no writers. They were pure rebuildable caches — the
        # codebase already dropped and recreated them on schema drift — so
        # dropping is data-loss-free by construction. Anything holding user
        # content (videos, analyses, hook_templates incl. dormant bookmark
        # rows, face-swap jobs) is deliberately NOT dropped here.
        for table in (
            "trending_videos", "trending_cache_meta",
            "niche_cache_meta", "curated_videos",
        ):
            await conn.execute(f"DROP TABLE IF EXISTS {table}")
            logger.info(f"Migration: dropped retired feed-cache table {table}")
        await conn.commit()

        # Recreate any tables that were just dropped
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                tiktok_url TEXT,
                niche TEXT,
                video_platform_id TEXT,
                creator TEXT,
                creator_display TEXT,
                title TEXT,
                description TEXT,
                view_count INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                share_count INTEGER DEFAULT 0,
                bookmark_count INTEGER DEFAULT 0,
                duration REAL DEFAULT 0,
                thumbnail_url TEXT,
                direct_video_url TEXT,
                hashtags TEXT,
                song_id TEXT,
                song_title TEXT,
                song_artist TEXT,
                song_album TEXT,
                song_duration INTEGER DEFAULT 0,
                song_cover_url TEXT,
                subtitles_url TEXT,
                subtitles_language TEXT,
                is_ad INTEGER DEFAULT 0,
                creator_followers INTEGER DEFAULT 0,
                creator_following INTEGER DEFAULT 0,
                creator_verified INTEGER DEFAULT 0,
                creator_bio TEXT,
                creator_avatar TEXT,
                status TEXT DEFAULT 'metadata_ready',
                local_video_path TEXT,
                last_analysis_id TEXT,
                error TEXT,
                created_at TEXT
            );

            CREATE TABLE IF NOT EXISTS video_jobs (
                id TEXT PRIMARY KEY,
                customization_id TEXT,
                video_id TEXT,
                brand_name TEXT,
                brand_goal TEXT,
                brand_details TEXT,
                target_duration_seconds INTEGER,
                prompt_breakdown TEXT,
                full_prompt_text TEXT,
                reference_image_ids TEXT,
                selected_image_ids TEXT,
                use_original_sound INTEGER DEFAULT 0,
                sound_reference TEXT,
                status TEXT DEFAULT 'prompt_ready',
                openrouter_job_id TEXT,
                video_url TEXT,
                error TEXT,
                created_at TEXT,
                requested_at TEXT
            );
        """)
        await conn.commit()

        # Migration: add user_id column to all per-user tables for Clerk auth
        # isolation. Existing rows get user_id = 'anonymous' (the default for
        # unauthenticated/dev-mode usage), so the app stays backward-compatible
        # with databases created before auth was added.
        user_id_tables = [
            "videos", "analyses", "customizations", "video_jobs",
            "brand_profiles", "hook_templates",
            "studio_projects", "content_angles", "generations",
            "assets",
            "feedback_events",
        ]
        for table in user_id_tables:
            cursor = await conn.execute(f"PRAGMA table_info({table})")
            cols = {row[1] for row in await cursor.fetchall()}
            if "user_id" not in cols:
                logger.info(f"Migration: adding user_id column to {table}")
                await conn.execute(
                    f"ALTER TABLE {table} ADD COLUMN user_id TEXT DEFAULT 'anonymous'"
                )
        await conn.commit()

        # Migration: the app-specific influencer workflow.
        #
        # Adds the strategy to studio_projects and the chain/continuity
        # bookkeeping to generations. Both are additive with safe defaults, so
        # an existing database gains the columns and every pre-existing row
        # reads as "no strategy" / "segment 0, not approved" — which is the
        # truth, since those videos were produced before this workflow existed.
        # The one-shot single-pass path keeps working unchanged.
        influencer_migrations = [
            ("studio_projects", "strategy", "TEXT"),
            ("studio_projects", "strategy_version", "INTEGER DEFAULT 0"),
            # The script_version the current strategy was built FROM.
            #
            # The strategy is generated from the founder's approved creative
            # plan, so it is only true of that plan's words. A script edit bumps
            # script_version and leaves the strategy describing the previous
            # hook line, and nothing detected it. 0 means "built before this
            # was recorded" and is treated as unknown rather than as a mismatch,
            # so existing drafts keep working and are simply unprotected until
            # the strategy is rebuilt.
            ("studio_projects", "strategy_script_version", "INTEGER DEFAULT 0"),
            ("studio_projects", "hook_seconds", "INTEGER DEFAULT 0"),
            ("studio_projects", "extend_intent", "INTEGER DEFAULT 1"),
            ("generations", "segment_index", "INTEGER DEFAULT 0"),
            ("generations", "strategy_version", "INTEGER DEFAULT 0"),
            ("generations", "continuity", "TEXT"),
            ("generations", "approved", "INTEGER DEFAULT 0"),
            ("generations", "approved_at", "TEXT"),
            ("generations", "trim_to_seconds", "INTEGER DEFAULT 0"),
            # A video is a hook and a middle, so the plan carries a brief for the
            # founder's own demo instead of the feature instruction the render
            # used to receive. Additive: existing rows get NULL, which reads as
            # "no brief recorded" and simply shows an empty field on Review.
            ("studio_projects", "demo_brief", "TEXT"),
            # How many characters the arrival clamp removed from the model's
            # script to fit the middle's seconds, so Review can report the trim.
            # Existing rows get NULL, which reads as 0: nothing was trimmed.
            # Written only by the plan endpoint, and never by a project PATCH,
            # so a founder edit cannot quietly clear the record of a trim.
            ("studio_projects", "plan_trimmed_chars", "INTEGER DEFAULT 0"),
            # Idempotency for the one render. A repeated key returns the
            # generation already created for it instead of running a second
            # job. Existing rows get NULL, which means "no key supplied" and
            # keeps every historical render re-submittable exactly as before.
            ("generations", "idempotency_key", "TEXT"),
            # Which variant of the six goal suggestions this angle shows.
            # 0 is the curated ranking; the Shuffle button cycles 1..3.
            # Persisted on the angle so a page reload re-shows the exact order
            # the founder last asked for instead of silently reverting it.
            ("content_angles", "goal_variant", "INTEGER DEFAULT 0"),
            # Authorship of the row: 'manual' rows are founder-authored and
            # survive every regeneration pass; 'generated' rows are derived
            # data and are replaced. The backfill below marks every
            # pre-column row 'generated', which is the truth: manual rows
            # used to go through the same INSERT as generated ones, and a
            # row that predates the column degrades to the derived-data rule
            # rather than being wrongly protected from a rewrite.
            ("content_angles", "origin", "TEXT DEFAULT 'generated'"),
        ]
        for table, column, decl in influencer_migrations:
            cursor = await conn.execute(f"PRAGMA table_info({table})")
            cols = {r[1] for r in await cursor.fetchall()}
            if column not in cols:
                logger.info(f"Migration: adding {table}.{column}")
                await conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        await conn.commit()

        # Backfill content_angles.origin after the column above added it:
        # every row this table has accumulated so far came through the AI
        # generation INSERT, so 'generated' is correct for all of them;
        # only NEW manual rows are written with origin='manual'. Empty on a
        # fresh database; a no-op after the first run.
        await conn.execute(
            "UPDATE content_angles SET origin = 'generated' WHERE origin IS NULL OR origin = ''"
        )
        await conn.commit()

        # Migration: generations gains an index on the segment chain so the
        # assembler can order a project's approved segments cheaply.
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_generations_chain "
            "ON generations (studio_project_id, segment_index)"
        )
        # And a UNIQUE index on (user_id, idempotency_key) for callers that
        # supply one. Partial, so the many NULL keys of keyless callers are
        # untouched -- SQLite treats NULLs as distinct in a unique index, so
        # this constrains only the rows that actually claim an intent. This is
        # what makes the guarantee hold under two genuinely concurrent requests
        # rather than only when they are politely sequential.
        await conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_generations_idempotency "
            "ON generations (user_id, idempotency_key) "
            "WHERE idempotency_key IS NOT NULL AND idempotency_key != ''"
        )
        await conn.commit()

        # Seed the curated template library once. Runs AFTER the user_id
        # migration above because seeded rows set user_id='system' to mark
        # them shared. Idempotent: matches on (name, origin='curated') so
        # re-running init_db never duplicates.
        cursor = await conn.execute("SELECT name FROM hook_templates WHERE origin = 'curated'")
        seeded_names = {(r[0] or "").strip().lower() for r in await cursor.fetchall()}
        seeded = 0
        for tpl in template_library.curated_template_rows():
            if tpl["name"].strip().lower() in seeded_names:
                continue
            now = now_iso()
            # Seeded by name, so an existing database keeps its rows and their
            # pinned versions. That means a database seeded before this change
            # still holds the old three-beat-arcs-with-a-CTA rows; they are
            # updated in place below so the library is not half old-shape.
            await conn.execute(
                """INSERT INTO hook_templates
                   (id, name, category, notes, app_categories, audiences, objective,
                     opening_structure, hook_seconds, middle_structure, visual_style,
                     camera_pacing, required_assets, default_duration,
                     content_slots, evidence_note, outcome, version, archived, is_favorite,
                     origin, review_status, times_used, created_at, updated_at, user_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()), tpl["name"],
                    template_library.normalize_category(tpl["category"]), "",
                    json.dumps(tpl.get("app_categories") or []),
                    json.dumps(tpl.get("audiences") or []),
                    template_library.normalize_objective(tpl.get("objective")),
                    tpl["opening_structure"], int(tpl["hook_seconds"] or 3),
                    tpl["middle_structure"], tpl["visual_style"],
                    tpl["camera_pacing"], json.dumps(tpl.get("required_assets") or []),
                    int(tpl["default_duration"] or 10),
                    json.dumps(tpl.get("content_slots") or {}), tpl.get("evidence_note") or "",
                    tpl.get("outcome") or "",
                    1, 0, 0, "curated", "approved", 0, now, now, "system",
                ),
            )
            seeded += 1
        if seeded:
            logger.info("Seeded %d curated hook template(s)", seeded)

        # Curated rows are seeded by name and never re-seeded, so a database that
        # predates the two-section change keeps its old rows: a three-beat arc
        # ending in a CTA, a `cta_pattern`, and a default_duration of 20 or 30.
        # Those descriptions are read straight into the plan and render prompts,
        # so leaving them would have the prompts contradicting the two-section
        # model. Rewritten in place, ONCE, by name — which is stable, unlike the
        # generated ids. Version is bumped so a project pinned to the old row
        # can be identified as built against a different structure.
        #
        # An operator's own templates and every research draft are untouched:
        # this only touches rows this module authored.
        #
        # The rewrite is guarded on the row actually differing from the curated
        # definition. Unconditionally rewriting here meant every deploy bumped
        # every curated template's version by one forever, so the very signal the
        # bump exists to carry — "this project was built against a different
        # structure" — was destroyed by any restart, and a redeploy with no
        # schema change still looked like a content change to every project.
        now = now_iso()
        for tpl in template_library.CURATED_TEMPLATES:
            desired_slots = json.dumps(tpl.get("content_slots") or {})
            cursor = await conn.execute(
                """SELECT opening_structure, hook_seconds, middle_structure,
                          visual_style, camera_pacing, content_slots, default_duration,
                          outcome
                     FROM hook_templates
                    WHERE origin = 'curated' AND LOWER(TRIM(name)) = ?""",
                (tpl["name"].strip().lower(),),
            )
            current = await cursor.fetchone()
            if current is not None:
                stored_slots = current[5]
                if isinstance(stored_slots, str):
                    try:
                        stored_slots = json.loads(stored_slots)
                    except (json.JSONDecodeError, TypeError):
                        stored_slots = None
                already_current = (
                    current[0] == tpl["opening_structure"]
                    and int(current[1] or 0) == int(tpl["hook_seconds"] or 3)
                    and (current[2] or "") == tpl["middle_structure"]
                    and (current[3] or "") == tpl["visual_style"]
                    and (current[4] or "") == tpl["camera_pacing"]
                    and stored_slots == (tpl.get("content_slots") or {})
                    and int(current[6] or 0) == int(tpl["default_duration"] or 10)
                )
                if already_current:
                    continue
            await conn.execute(
                """UPDATE hook_templates
                   SET opening_structure = ?, hook_seconds = ?, middle_structure = ?,
                       visual_style = ?, camera_pacing = ?, content_slots = ?,
                       default_duration = ?, version = COALESCE(version, 1) + 1,
                       updated_at = ?
                   WHERE origin = 'curated' AND LOWER(TRIM(name)) = ?""",
                (
                    tpl["opening_structure"], int(tpl["hook_seconds"] or 3),
                    tpl["middle_structure"], tpl["visual_style"], tpl["camera_pacing"],
                    desired_slots,
                    int(tpl["default_duration"] or 10),
                    now, tpl["name"].strip().lower(),
                ),
            )
            # Outcome copy is display-only: it never reaches a plan or render
            # prompt, so it converges here WITHOUT the version bump above. A
            # bump would mark every project built against the old row as built
            # against a different structure over a card headline. Guarded the
            # same way, so a converged row costs one comparison per boot.
            # (A missing row cannot happen — the seed loop above inserts it —
            # and an UPDATE matching nothing is a harmless no-op anyway.)
            desired_outcome = tpl.get("outcome") or ""
            stored_outcome = current[7] if current is not None else None
            if stored_outcome != desired_outcome:
                await conn.execute(
                    """UPDATE hook_templates
                        SET outcome = ?, updated_at = ?
                        WHERE origin = 'curated' AND LOWER(TRIM(name)) = ?""",
                    (desired_outcome, now, tpl["name"].strip().lower()),
                )

        # Face-only library. Every curated template requires exactly
        # ["character_reference"] — the face that anchors every video — and
        # nothing else can be uploaded, attached, or composited. The seed loop
        # above only inserts missing names, so rows seeded before this rule
        # would keep stale requirements and retired templates forever. This
        # migration runs on every boot and is idempotent.
        #
        # Two moves, both limited to origin='curated' (an operator's own rows
        # are never rewritten here):
        #   1. Templates whose whole mechanic was real app footage are
        #      archived, never deleted: existing projects keep their foreign
        #      keys and history, but the picker (archived = 0) hides them.
        #      Retired stays retired: an operator un-archiving one of these
        #      gets it re-archived on the next boot.
        #   2. Surviving templates get required_assets = ["character_reference"].
        retired_names = (
            "Before and After",
            "Quick App Demonstration",
            "Feature Reveal",
            "Competitor Alternative",
            "Fast Tutorial",
            "Screen-Recording Reveal",
            "Problem, App, Result",
            "Three Taps to Solve This",
        )
        face_only = json.dumps(["character_reference"])
        cursor = await conn.execute(
            "SELECT name, required_assets, archived FROM hook_templates "
            "WHERE origin = 'curated'"
        )
        for row in await cursor.fetchall():
            name, current_raw, archived = (row[0] or ""), (row[1] or "[]"), (row[2] or 0)
            if name in retired_names:
                if not archived:
                    await conn.execute(
                        "UPDATE hook_templates SET archived = 1 WHERE name = ? "
                        "AND origin = 'curated'",
                        (name,),
                    )
                    logger.info("Archived retired template %s", name)
                continue
            try:
                current = json.loads(current_raw)
            except (json.JSONDecodeError, TypeError):
                current = None
            if current != ["character_reference"]:
                await conn.execute(
                    "UPDATE hook_templates SET required_assets = ? "
                    "WHERE name = ? AND origin = 'curated'",
                    (face_only, name),
                )
                logger.info(
                    "Backfilled %s: required_assets %s -> %s", name, current, face_only
                )

        await conn.commit()

        # Migration: feedback_events gains a `signal` column for automatically
        # captured triggers, distinct from the optional founder-supplied
        # `reason`. Existing rows predate automatic capture, so they keep a
        # NULL signal rather than being backfilled with a guess.
        cursor = await conn.execute("PRAGMA table_info(feedback_events)")
        if "signal" not in {row[1] for row in await cursor.fetchall()}:
            logger.info("Migration: adding signal column to feedback_events")
            await conn.execute("ALTER TABLE feedback_events ADD COLUMN signal TEXT")
        await conn.commit()
        # Migration: feedback_events gains a `step` column naming the
        # CreateVideo step a thumbs verdict was given on (audience_goal,
        # template_photo, review, hook_story). Existing rows predate the
        # thumbs loop, so they keep NULL rather than a fabricated step.
        cursor = await conn.execute("PRAGMA table_info(feedback_events)")
        if "step" not in {row[1] for row in await cursor.fetchall()}:
            logger.info("Migration: adding step column to feedback_events")
            await conn.execute("ALTER TABLE feedback_events ADD COLUMN step TEXT")
        await conn.commit()

        # Migration: assets gains a face count. Existing image/video rows
        # keep NULL rather than a fabricated zero; audio duration is probed at
        # upload time going forward.
        cursor = await conn.execute("PRAGMA table_info(assets)")
        if "duration_seconds" not in {row[1] for row in await cursor.fetchall()}:
            logger.info("Migration: adding duration_seconds column to assets")
            await conn.execute("ALTER TABLE assets ADD COLUMN duration_seconds REAL")
        await conn.commit()

        # Migration: hook_templates gains brand scoping for brand-tailored
        # customs generated on profile approval. Existing rows keep NULL
        # (shared/legacy: visible everywhere), never a fabricated link.
        cursor = await conn.execute("PRAGMA table_info(hook_templates)")
        if "brand_profile_id" not in {row[1] for row in await cursor.fetchall()}:
            logger.info("Migration: adding brand_profile_id column to hook_templates")
            await conn.execute("ALTER TABLE hook_templates ADD COLUMN brand_profile_id TEXT")
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_templates_brand "
                "ON hook_templates (brand_profile_id, archived)"
            )
        await conn.commit()

        # Migration: assets gains a face count. Existing rows keep NULL
        # (unknown) rather than a fabricated zero; the detector runs at
        # upload time going forward.
        cursor = await conn.execute("PRAGMA table_info(assets)")
        if "face_count" not in {row[1] for row in await cursor.fetchall()}:
            logger.info("Migration: adding face_count column to assets")
            await conn.execute("ALTER TABLE assets ADD COLUMN face_count INTEGER")
        await conn.commit()

        # Migration: a generation can render successfully while its durable
        # copy fails. That failure must be stored on the row rather than only
        # logged, or operations cannot show or retry it.
        cursor = await conn.execute("PRAGMA table_info(generations)")
        if "storage_error" not in {row[1] for row in await cursor.fetchall()}:
            logger.info("Migration: adding storage_error column to generations")
            await conn.execute("ALTER TABLE generations ADD COLUMN storage_error TEXT")
        await conn.commit()

        # Best-effort backfill for analyses whose local extracted frames still
        # exist at this deployment. Existing rows whose frames were already
        # lost cannot be reconstructed safely without re-downloading TikTok.
        frame_backfilled = 0
        cursor = await conn.execute("SELECT frames FROM analyses WHERE frames IS NOT NULL")
        for (frames_json,) in await cursor.fetchall():
            try:
                frame_docs = json.loads(frames_json)
            except (TypeError, ValueError):
                continue
            for frame_doc in frame_docs if isinstance(frame_docs, list) else []:
                media_url = frame_doc.get("media_url") if isinstance(frame_doc, dict) else ""
                match = re.fullmatch(r"/api/media/frames/([0-9a-f]{16})/(frame_\d{3}\.jpg)", media_url or "")
                if not match:
                    continue
                video_hash, filename = match.groups()
                try:
                    frame_path = _analysis_frame_path(video_hash, filename)
                    if not frame_path.is_file():
                        continue
                    image_bytes = _normalize_analysis_frame(frame_path.read_bytes())
                    await conn.execute(
                        """INSERT OR IGNORE INTO analysis_frame_assets
                           (video_hash, filename, image_bytes, created_at)
                           VALUES (?, ?, ?, ?)""",
                        (video_hash, filename, image_bytes, now_iso()),
                    )
                    frame_backfilled += 1
                except (OSError, ValueError) as exc:
                    logger.warning("Could not backfill extracted frame %s/%s: %s", video_hash, filename, exc)
        if frame_backfilled:
            logger.info("Migration: backfilled %s durable extracted frame(s)", frame_backfilled)
        await conn.commit()

        # Migration: generated face-swap files previously existed only on the
        # local container filesystem. Persist their normalized PNG bytes with
        # provenance so a new backend instance can restore a selected image
        # before generating or extending a video.
        cursor = await conn.execute("PRAGMA table_info(generated_images)")
        generated_image_cols = {row[1] for row in await cursor.fetchall()}
        if "image_bytes" not in generated_image_cols:
            logger.info("Migration: adding durable image_bytes backup to generated_images")
            await conn.execute("ALTER TABLE generated_images ADD COLUMN image_bytes BLOB")
        await conn.commit()

        # Migration: templates are durable database records, but their local
        # thumbnail files are not. Keep a normalized JPEG backup with each
        # template so cards remain renderable after a redeploy or on another
        # backend instance.
        cursor = await conn.execute("PRAGMA table_info(hook_templates)")
        template_cols = {row[1] for row in await cursor.fetchall()}
        if "thumbnail_bytes" not in template_cols:
            logger.info("Migration: adding durable thumbnail_bytes backup to hook_templates")
            await conn.execute("ALTER TABLE hook_templates ADD COLUMN thumbnail_bytes BLOB")
        if "example_preview" not in template_cols:
            logger.info("Migration: adding example_preview column to hook_templates")
            await conn.execute("ALTER TABLE hook_templates ADD COLUMN example_preview TEXT")
        await conn.commit()

        # Best-effort backfill for templates whose cache file still exists at
        # this deployment. Files already lost before this change cannot be
        # reconstructed locally, so the listing will use the source cover when
        # available rather than rendering a broken image.
        cursor = await conn.execute(
            "SELECT id FROM hook_templates WHERE thumbnail_bytes IS NULL"
        )
        for (template_id,) in await cursor.fetchall():
            if not GENERATED_ID_RE.match(template_id or ""):
                continue
            thumbnail_path = pipeline.TEMPLATES_DIR / f"{template_id}.jpg"
            if not thumbnail_path.is_file():
                continue
            try:
                thumbnail_bytes = _normalize_template_thumbnail(thumbnail_path.read_bytes())
                await conn.execute(
                    "UPDATE hook_templates SET thumbnail_bytes = ? WHERE id = ?",
                    (thumbnail_bytes, template_id),
                )
            except (OSError, ValueError) as exc:
                logger.warning("Could not backfill thumbnail for template %s: %s", template_id, exc)
        await conn.commit()

        # Migration: backfill the generated_images provenance registry for
        # databases created before it existed. Without this, every image a user
        # already generated would be unusable for video generation after the
        # deploy, because the gate requires a provenance row.
        #
        # Customization previews recover their target from the frame each was
        # built on. Images whose recovered target is an upload (produced before
        # targets were restricted) are backfilled honestly and will be refused
        # by the gate — that is the intended outcome, not a bug.
        cursor = await conn.execute("SELECT COUNT(*) FROM generated_images")
        (existing_rows,) = await cursor.fetchone()
        if not existing_rows:
            backfilled = 0
            cursor = await conn.execute(
                """SELECT id, generated_images, user_id FROM customizations
                   WHERE generated_images IS NOT NULL"""
            )
            for cust_id, images_json, cust_user in await cursor.fetchall():
                try:
                    images = json.loads(images_json)
                except (TypeError, ValueError):
                    continue
                if not isinstance(images, list):
                    continue
                for image in images:
                    if not isinstance(image, dict) or not image.get("id"):
                        continue
                    await conn.execute(
                        """INSERT OR IGNORE INTO generated_images
                           (id, origin, job_id, target_image_url, user_id, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            image["id"],
                            "customize",
                            cust_id,
                            image.get("reference_frame_url") or "",
                            cust_user or "anonymous",
                            now_iso(),
                        ),
                    )
                    backfilled += 1

            if backfilled:
                logger.info(
                    f"Migration: backfilled provenance for {backfilled} generated image(s)"
                )
            await conn.commit()


async def _fetch_one(query: str, params: tuple = ()) -> Optional[dict]:
    """Fetch one row as a dict, or None."""
    async with get_db() as conn:
        cursor = await conn.execute(query, params)
        cols = [d[0] for d in cursor.description]
        row = await cursor.fetchone()
        if row is None:
            return None
        return row_to_dict(row, cols)


async def _fetch_all(query: str, params: tuple = ()) -> list:
    """Fetch all rows as list of dicts."""
    async with get_db() as conn:
        cursor = await conn.execute(query, params)
        cols = [d[0] for d in cursor.description]
        rows = await cursor.fetchall()
        return [row_to_dict(r, cols) for r in rows]


async def _execute(query: str, params: tuple = ()):
    """Execute a write query and commit."""
    async with get_db() as conn:
        await conn.execute(query, params)
        await conn.commit()


async def _record_model_request(
    operation: str,
    modality: str,
    model: str,
    status: str,
    latency_ms: int,
    user_id: str,
    error: str = "",
    brand_profile_id: str = "",
    studio_project_id: str = "",
    generation_id: str = "",
    template_id: str = "",
    research_run_id: str = "",
):
    """
    Persist one provider interaction for operations visibility.

    Prompts and generated copy are deliberately not stored. Operations needs to
    know that a request happened, which model handled it, and whether it
    worked — not the creative material itself.
    """
    await _execute(
        """INSERT INTO model_requests
           (id, operation, modality, model, status, latency_ms, error,
            brand_profile_id, studio_project_id, generation_id, template_id,
            research_run_id, created_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), operation, modality, model, status, int(latency_ms),
         (error or "")[:500],
         brand_profile_id or None, studio_project_id or None,
         generation_id or None, template_id or None, research_run_id or None,
         now_iso(), user_id),
    )


async def _record_asset_event(
    kind: str,
    reason: str,
    user_id: str,
    brand_profile_id: str = "",
    studio_project_id: str = "",
    generation_id: str = "",
    asset_id: str = "",
    asset_kind: str = "",
    filename: str = "",
):
    """Persist an asset failure that would otherwise exist only as an HTTP error."""
    await _execute(
        """INSERT INTO asset_events
           (id, kind, reason, brand_profile_id, studio_project_id, generation_id,
            asset_id, asset_kind, filename, created_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), kind, reason[:500],
         brand_profile_id or None, studio_project_id or None,
         generation_id or None, asset_id or None, asset_kind or None,
         (filename or "")[:200], now_iso(), user_id),
    )


async def _log_model_call(operation, modality, model, call, user_id, **refs):
    """
    Run one retained provider call and ledger its outcome.

    Centralizing this keeps operations honest: a failed research, plan, or poll
    is recorded with its latency before the route converts it into an HTTP
    error. Only metadata is stored; prompts and generated copy are not, and
    nothing about what the call cost is recorded.
    """
    started = time.perf_counter()
    try:
        result = await call()
    except Exception as exc:
        await _record_model_request(
            operation, modality, model, "failed",
            int((time.perf_counter() - started) * 1000), user_id,
            error=str(exc), **refs,
        )
        raise
    await _record_model_request(
        operation, modality, model, "completed",
        int((time.perf_counter() - started) * 1000), user_id,
        **refs,
    )
    return result


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


def _public_template(template: dict) -> dict:
    """Remove storage-only thumbnail bytes before serializing a template."""
    public_template = dict(template)
    public_template.pop("thumbnail_bytes", None)
    return public_template


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
def _normalize_url(value: str) -> Optional[str]:
    """Trim a URL and ensure it has a scheme. Returns None when empty."""
    v = (value or "").strip()
    if not v:
        return None
    if not v.lower().startswith(("http://", "https://")):
        v = f"https://{v}"
    return v


def _normalize_str_list(value) -> list:
    """Accept a list or comma-separated string; always return clean strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [s.strip() for s in value.split(",") if s.strip()]
    if isinstance(value, list):
        out = []
        for v in value:
            if isinstance(v, dict):
                v = v.get("label") or v.get("name") or ""
            s = str(v).strip()
            if s:
                out.append(s)
        return out
    return []


def _normalize_objection_value(value) -> list:
    """
    Coerce a client-supplied viewer_objections value into stored triples.

    The API accepts a list of ViewerObjection-shaped dicts, a list of dicts with
    missing keys, or a JSON string of either (the editor round-trips the field
    through text, and older clients sent a string). A malformed entry is dropped
    whole rather than kept as a half-answer, for the same reason the extraction
    path does: an objection without an honest reply gives the arc nothing to
    aim at.

    Deliberately NOT _normalize_str_list: that flattens a dict to its
    "label"/"name" key, which these triples do not have, so every entry would
    serialize to "".
    """
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(value, list):
        return []
    kept = []
    for item in value[:6]:
        # FastAPI hands us pydantic models, not dicts: dump first, or every
        # entry from a real request fails the isinstance check below and the
        # field saves as empty despite the founder filling it in.
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        if not isinstance(item, dict):
            continue
        triple = {
            "objection": str(item.get("objection") or "").strip()[:200],
            "what_they_do_now": str(item.get("what_they_do_now") or "").strip()[:200],
            "honest_answer": str(item.get("honest_answer") or "").strip()[:300],
        }
        if not triple["objection"] or not triple["honest_answer"]:
            continue
        kept.append(triple)
    return kept


def _normalize_outcome_value(value) -> list:
    """
    Coerce a client-supplied outcome_statements value into stored entries.

    The API accepts a list of OutcomeStatement-shaped dicts, a list of dicts
    with missing keys, or a JSON string of either (the editor round-trips the
    field through text). A malformed entry is dropped whole rather than kept
    as a half-answer: an outcome with no source feature leaves every later
    prompt guessing the mapping, which is how pitches decay into feature
    lists — and a how_it_helps that only restates the spec is a feature
    wearing benefit clothes.

    Deliberately NOT _normalize_str_list, for the same reason as the
    objection triples above.
    """
    if value is None:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    if not isinstance(value, list):
        return []
    kept = []
    for item in value[:6]:
        # Same pydantic reality as the objection triples above: a real
        # request carries models, so dump before the dict check.
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        if not isinstance(item, dict):
            continue
        entry = {
            "outcome": str(item.get("outcome") or "").strip()[:300],
            "who_feels_it": str(item.get("who_feels_it") or "").strip()[:200],
            "from_feature": str(item.get("from_feature") or "").strip()[:200],
            "how_it_helps": str(item.get("how_it_helps") or "").strip()[:300],
        }
        if not entry["outcome"] or not entry["from_feature"]:
            continue
        kept.append(entry)
    return kept


def _brand_update_parts(updates: dict) -> tuple:
    """Split a profile update dict into (SET clauses, values), JSON-encoding lists."""
    set_clauses = []
    values = []
    for key, value in updates.items():
        # Object lists each have their own normalizer: the objection triples
        # and the outcome entries share a shape (list of dicts) but not a
        # contract, so one normalizer cannot serve both.
        if key == "viewer_objections":
            value = json.dumps(_normalize_objection_value(value))
        elif key == "outcome_statements":
            value = json.dumps(_normalize_outcome_value(value))
        elif key in APP_PROFILE_LIST_FIELDS:
            value = json.dumps(_normalize_str_list(value))
        set_clauses.append(f"{key} = ?")
        values.append(value)
    return set_clauses, values


async def _fetch_url_text(url: str, max_chars: int) -> str:
    """Fetch a public page and return cleaned text, capped at max_chars.

    Returns an empty string when the page cannot be fetched or yields no
    readable text — research across multiple sources must tolerate individual
    failures rather than aborting the whole run.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return page_text_with_metadata(resp.text)[:max_chars]
    except Exception as e:
        logger.warning(f"App research: could not fetch {url}: {e}")
        return ""


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

# Hook-video prompt construction lives in hook_prompting.py (motion styles,
# style directives, template constants and their builders). Every name is
# re-exported here so existing `server.X` references keep working.
from hook_prompting import (
    HOOK_VIDEO_PROMPT_TEMPLATE,
    AUDIO_ON_INSTRUCTION,
    AUDIO_OFF_INSTRUCTION,
    NO_TEXT_OVERLAY_INSTRUCTION,
    apply_audio_directive,
    HOOK_MOTION_STYLES,
    HOOK_MOTION_TYPES,
    MOTION_STYLE_INDEX,
    _coerce_mechanics,
    build_hook_prompt_from_analysis,
    build_hook_prompt_from_image_analysis,
    build_hook_prompt_from_motion_style,
    apply_motion_style_directive,
    HOOK_TEMPLATE_CATEGORIES,
    HOOK_TEMPLATE_NAME_MAX,
    HOOK_TEMPLATE_NOTES_MAX,
    HOOK_STYLE_DIRECTIVES,
    HOOK_STYLE_CUSTOM_PROMPT_MAX,
    _sanitize_custom_hook_prompt,
    apply_hook_style_directive,
    _normalize_template_category,
    _template_thumbnail_source,
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


@api_router.post("/brand", status_code=201)
async def create_brand(payload: BrandProfileCreateRequest, user_id: str = Depends(get_current_user_id)):
    """
    Create a brand profile from manually entered fields.

    Deliberately does NOT require the URL-analysis step (or an AI key): a user
    with no website, or whose site can't be fetched, must still be able to set
    up a brand profile by hand.
    """
    name = (payload.brand_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Brand name is required.")

    website = (payload.website_url or "").strip()
    if website and not website.lower().startswith(("http://", "https://")):
        website = f"https://{website}"

    brand_id = str(uuid.uuid4())
    created_at = now_iso()
    await _execute(
        """INSERT INTO brand_profiles
           (id, website_url, brand_name, brand_description, niche,
             target_audience, ideal_customer_profile, differentiation, tone_voice,
             raw_extracted_text, created_at, updated_at, user_id,
             appstore_url, play_url, support_urls, notes, app_category, platforms,
             core_features, primary_use_cases, problems_solved,
             icp_segments, desired_outcomes, known_limitations,
             must_not_show, usage_moments, proof_moment, viewer_objections,
             outcome_statements,
             claims_approved, claims_review, claims_banned,
             status, version)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (brand_id, website or None, name, payload.brand_description or "",
         payload.niche or "",
         payload.target_audience or "", payload.ideal_customer_profile or "",
         payload.differentiation or "", payload.tone_voice or "", None,
         created_at, created_at, user_id,
         _normalize_url(payload.appstore_url or ""),
         _normalize_url(payload.play_url or ""),
         json.dumps(_normalize_str_list(payload.support_urls)),
         payload.notes or "", payload.app_category or "",
         json.dumps(_normalize_str_list(payload.platforms)),
         json.dumps(_normalize_str_list(payload.core_features)),
         json.dumps(_normalize_str_list(payload.primary_use_cases)),
         json.dumps(_normalize_str_list(payload.problems_solved)),
         json.dumps(_normalize_str_list(payload.icp_segments)),
         json.dumps(_normalize_str_list(payload.desired_outcomes)),
         payload.known_limitations or "",
         json.dumps(_normalize_str_list(payload.must_not_show)),
         json.dumps(_normalize_str_list(payload.usage_moments)),
         payload.proof_moment or "",
          json.dumps(_normalize_objection_value(payload.viewer_objections)),
         json.dumps(_normalize_outcome_value(payload.outcome_statements)),
         json.dumps(_normalize_str_list(payload.claims_approved)),
         json.dumps(_normalize_str_list(payload.claims_review)),
         json.dumps(_normalize_str_list(payload.claims_banned)),
         "draft", 1),
    )
    logger.info(f"Created brand profile {brand_id} ('{name}') from manual entry")
    return await _fetch_one("SELECT * FROM brand_profiles WHERE id = ?", (brand_id,))


@api_router.get("/brands")
async def list_brands(user_id: str = Depends(get_current_user_id)):
    """
    All brand profiles belonging to this user, most recently active first.

    Exists so generation flows can offer a real choice of saved brand instead of
    making the creator re-enter a website URL. Ordering matches
    _fetch_active_brand, so the first item is the same profile that would be
    used by default when no explicit brand_id is sent.

    Returns a trimmed projection rather than full rows — this feeds a picker, so
    it doesn't need raw_extracted_text (which can be several KB per brand).
    """
    rows = await _fetch_all(
        "SELECT id, brand_name, website_url, niche, updated_at, created_at "
        "FROM brand_profiles WHERE user_id = ? "
        "ORDER BY updated_at DESC, created_at DESC",
        (user_id,),
    )
    return {"brands": rows or []}


@api_router.get("/brand/active")
async def get_active_brand(user_id: str = Depends(get_current_user_id)):
    row = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE user_id = ? ORDER BY updated_at DESC, created_at DESC LIMIT 1",
        (user_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail="No brand profile found. Set one up first.")
    return row


@api_router.get("/brand/{brand_id}")
async def get_brand(brand_id: str, user_id: str = Depends(get_current_user_id)):
    # Scoped to the caller. This endpoint predates the App Profile routes and
    # used to look the row up by id alone, which let any authenticated user read
    # (or, via the PATCH below, rewrite) someone else's profile -- including the
    # scraped raw_extracted_text. A miss is a 404 rather than a 403 so a
    # stranger cannot probe for which profile ids exist.
    brand = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (brand_id, user_id)
    )
    if not brand:
        raise HTTPException(status_code=404, detail="Brand profile not found")
    return brand


@api_router.patch("/brand/{brand_id}")
async def update_brand(brand_id: str, payload: BrandProfileUpdateRequest, user_id: str = Depends(get_current_user_id)):
    # Scoped to the caller for the same reason as the GET above: an id-only
    # lookup let one user edit another user's profile. Both the read and the
    # UPDATE carry the predicate so the write can never land on a row the caller
    # does not own.
    existing = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (brand_id, user_id)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Brand profile not found")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return existing

    # Drop unknown keys defensively so a client sending a newer schema never
    # breaks the UPDATE against an older database missing those columns.
    # raw_extracted_text stays writable here for the legacy analyze-url flow.
    updates = {k: v for k, v in updates.items() if k in APP_PROFILE_EDITABLE_FIELDS + ("raw_extracted_text",)}
    if not updates:
        return existing

    set_clauses, values = _brand_update_parts(updates)
    set_clauses.append("updated_at = ?")
    values.append(now_iso())

    await _execute(
        f"UPDATE brand_profiles SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?",
        tuple(values) + (brand_id, user_id),
    )
    return await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (brand_id, user_id)
    )


# ---------------------------------------------------------------------------
# App Profiles (template-studio workflow: research -> review/approve -> refresh)
# ---------------------------------------------------------------------------
# Per-source page-text caps for multi-URL research. Store listings are dense
# with reviews; support pages are supplementary — keep them small so the
# combined prompt stays well within the text model's context.
APP_RESEARCH_CAPS = {
    "website": 6000,
    "app_store": 6000,
    "google_play": 6000,
    "support": 2000,
}
APP_RESEARCH_MAX_SUPPORT_URLS = 5


@api_router.post("/app-profiles/research", status_code=201)
async def research_app_profile(payload: AppProfileResearchRequest, user_id: str = Depends(get_current_user_id)):
    """Research a mobile app from its store listings and draft an App Profile.

    Fetches the App Store and Google Play pages plus up to 5 support
    URLs, then asks OpenRouter to draft the full profile. The result is stored
    as status='draft' — the founder must review and approve it (POST
    /app-profiles/{id}/approve) before it drives video generation.
    """
    require_ai_configured()
    appstore = _normalize_url(payload.appstore_url or "")
    play = _normalize_url(payload.play_url or "")
    support: list = []
    for u in payload.support_urls or []:
        n = _normalize_url(u)
        if n and n not in support:
            support.append(n)
    support = support[:APP_RESEARCH_MAX_SUPPORT_URLS]
    if not (appstore or play):
        raise HTTPException(
            status_code=400,
            detail="Provide your app's App Store URL, Google Play URL, or both.",
        )

    sources: dict = {}
    # What was asked for, and what actually came back. A source can fail --
    # a store listing behind a bot check, a support page that 404s -- and the
    # only all-failed case raises. research_sources used to record every
    # SUPPLIED url, so a profile built from one of five sources claimed five,
    # and a founder reading the list had no way to know the rest were empty.
    requested_sources: list = []
    source_failures: list = []
    if appstore:
        requested_sources.append("app_store")
        sources["app_store"] = await _fetch_url_text(appstore, APP_RESEARCH_CAPS["app_store"])
    if play:
        requested_sources.append("google_play")
        sources["google_play"] = await _fetch_url_text(play, APP_RESEARCH_CAPS["google_play"])
    for i, u in enumerate(support):
        label = f"support_{i + 1} ({u})"
        requested_sources.append(label)
        sources[label] = await _fetch_url_text(u, APP_RESEARCH_CAPS["support"])
    read_sources = {k: v for k, v in sources.items() if (v or "").strip()}
    source_failures = [k for k in sources if k not in read_sources]
    if not read_sources:
        raise HTTPException(
            status_code=400,
            detail="Could not extract readable text from any URL. Check the links and try again.",
        )
    if source_failures:
        # Loud, not silent. A partial profile built from the sources that did
        # load is still worth having; pretending it came from all of them is
        # not.
        logger.warning(
            "App research read %d of %d source(s); unreadable: %s",
            len(read_sources), len(sources), ", ".join(source_failures),
        )

    try:
        profile = await _log_model_call(
            "app_profile_research", "text", TEXT_MODEL,
            # Only the sources that returned text. Passing the full dict handed
            # the model empty entries labelled as sources, which invites it to
            # write as though it had read a page it never saw.
            lambda: analyze_app_profile(read_sources, payload.notes or ""),
            user_id,
        )
    except Exception as e:
        logger.error(f"App research failed: {e}")
        raise HTTPException(status_code=502, detail=f"AI app research failed. Please try again. ({str(e)[:150]})")

    now = now_iso()
    brand_id = str(uuid.uuid4())
    combined_raw = "\n\n".join(
        f"[{label}]\n{text[:2000]}" for label, text in read_sources.items()
    )[:BRAND_URL_TEXT_MAX_CHARS]
    await _execute(
        """INSERT INTO brand_profiles
           (id, website_url, brand_name, brand_description, niche,
             target_audience, ideal_customer_profile, differentiation, tone_voice,
             raw_extracted_text, created_at, updated_at, user_id,
             appstore_url, play_url, support_urls, notes, app_category, platforms,
             core_features, primary_use_cases, problems_solved,
             icp_segments, desired_outcomes, known_limitations,
             must_not_show, usage_moments, proof_moment, viewer_objections,
             outcome_statements,
             claims_approved, claims_review, claims_banned,
             status, version, last_research_at, research_sources)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        # website_url is always "" here: research no longer accepts a website,
        # and the column itself stays for legacy rows SQLite cannot cheaply
        # drop it from.
        (brand_id, "", profile.get("brand_name") or "Untitled app",

         profile.get("brand_description") or "", profile.get("niche") or "",
         profile.get("target_audience") or "",
         profile.get("ideal_customer_profile") or "",
         profile.get("differentiation") or "", profile.get("tone_voice") or "",
         combined_raw, now, now, user_id,
         appstore, play, json.dumps(support), payload.notes or "",
         profile.get("app_category") or "",
         json.dumps(profile.get("platforms") or []),
         json.dumps(profile.get("core_features") or []),
         json.dumps(profile.get("primary_use_cases") or []),
         json.dumps(profile.get("problems_solved") or []),
         json.dumps(profile.get("icp_segments") or []),
         json.dumps(profile.get("desired_outcomes") or []),
         profile.get("known_limitations") or "",
         json.dumps(profile.get("must_not_show") or []),
         json.dumps(profile.get("usage_moments") or []),
         profile.get("proof_moment") or "",
          json.dumps(_normalize_objection_value(profile.get("viewer_objections"))),
         json.dumps(_normalize_outcome_value(profile.get("outcome_statements"))),
         json.dumps(profile.get("claims_approved") or []),
         json.dumps(profile.get("claims_review") or []),
         json.dumps(profile.get("claims_banned") or []),
         # Only the sources that actually returned text. `combined_raw` above is
    # already built from the same set, so the recorded list and the text the
    # model saw now agree.
    "draft", 1, now, json.dumps(sorted(read_sources))),
    )
    logger.info(
        "Researched app profile %s from %d of %d requested source(s)",
        brand_id, len(read_sources), len(requested_sources),
    )
    return await _fetch_one("SELECT * FROM brand_profiles WHERE id = ?", (brand_id,))


@api_router.get("/app-profiles")
async def list_app_profiles(user_id: str = Depends(get_current_user_id)):
    """All App Profiles for this user, most recently active first.

    Trimmed projection for pickers — excludes raw page text and the pending
    refresh proposal, which live on the detail endpoint.
    """
    rows = await _fetch_all(
        "SELECT id, brand_name, website_url, appstore_url, play_url, niche, "
        "app_category, status, version, approved_at, updated_at, created_at "
        "FROM brand_profiles WHERE user_id = ? "
        "ORDER BY updated_at DESC, created_at DESC",
        (user_id,),
    )
    return {"profiles": rows or []}


@api_router.get("/app-profiles/{profile_id}")
async def get_app_profile(profile_id: str, user_id: str = Depends(get_current_user_id)):
    profile = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")
    return profile


@api_router.patch("/app-profiles/{profile_id}")
async def update_app_profile(
    profile_id: str, payload: BrandProfileUpdateRequest, user_id: str = Depends(get_current_user_id)
):
    """Edit any App Profile field. Editing never changes approval status — a
    founder re-approves explicitly via the approve endpoint."""
    existing = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="App Profile not found")

    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items()
               if k in APP_PROFILE_EDITABLE_FIELDS}
    if not updates:
        return existing

    set_clauses, values = _brand_update_parts(updates)
    set_clauses.append("updated_at = ?")
    values.append(now_iso())
    values.append(profile_id)
    await _execute(
        f"UPDATE brand_profiles SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?",
        tuple(values) + (user_id,),
    )
    return await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )


async def _ensure_objective_templates(
    profile: dict, objective: str, user_id: str
) -> list:
    """
    Generate this profile's tailored templates for one selected objective,
    replacing any previous set for that same (profile, objective) key.

    The objective comes from the founder's wizard choice, never from the
    model: every stored row carries the requested objective, which is what
    makes the set worth generating per objective rather than once per
    profile. Generate-then-replace, never delete-then-generate — a model
    failure must leave the previous working set intact rather than zeroing
    it. Any failure is logged and swallowed: the caller returns the empty
    set with a reason instead of a 500.
    """
    profile_id = profile.get("id") or ""
    want_objective = template_library.normalize_objective(objective)
    if not profile_id or not want_objective:
        return []
    angles = await _fetch_all(
        "SELECT * FROM content_angles WHERE brand_profile_id = ? AND user_id = ?",
        (profile_id, user_id),
    )
    template_feedback = await _component_feedback_for_profile(
        profile_id, user_id, "template")
    try:
        drafts = await _log_model_call(
            "brand_templates", "text", TEXT_MODEL,
            lambda: generate_brand_templates(
                profile, angles, objective=want_objective,
                component_feedback=template_feedback),
            user_id,
            brand_profile_id=profile_id,
        )
    except Exception as e:
        logger.error(
            f"Brand template generation failed for profile {profile_id} "
            f"objective {want_objective}: {e!r}")
        return []
    if not drafts:
        return []
    now = now_iso()
    await _execute(
        "DELETE FROM hook_templates WHERE brand_profile_id = ? AND objective = ? AND user_id = ?",
        (profile_id, want_objective, user_id),
    )
    for draft in drafts:
        await _execute(
            """INSERT INTO hook_templates
                (id, name, category, app_categories, audiences, objective,
                 opening_structure, hook_seconds, middle_structure,
                 visual_style, camera_pacing, required_assets,
                 default_duration, content_slots, evidence_note, outcome, version,
                 archived, is_favorite, origin, review_status, times_used,
                 brand_profile_id, created_at, updated_at, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0,
                        'custom', 'approved', 0, ?, ?, ?, ?)""",
            (str(uuid.uuid4()), draft["name"], draft["category"],
             json.dumps([profile.get("app_category") or ""] if profile.get("app_category") else []),
             json.dumps([profile.get("target_audience") or ""] if profile.get("target_audience") else []),
             want_objective, draft["opening_structure"],
             draft.get("hook_seconds") or 3, draft.get("middle_structure") or "",
             draft.get("visual_style") or "",
             draft.get("camera_pacing") or "", json.dumps(["character_reference"]),
             draft.get("default_duration") or template_library.DEFAULT_DURATION,
              json.dumps(draft.get("content_slots") or {}),
              f"Generated for {profile.get('brand_name') or 'this app'} from its approved profile.",
              str(draft.get("outcome") or "")[:300],
              profile_id, now, now, user_id),
        )
    logger.info(
        f"Generated {len(drafts)} brand templates for profile {profile_id} "
        f"objective {want_objective}")
    return drafts


def _approval_gaps(profile: dict, pending: Optional[dict] = None) -> list:
    """
    What this App Profile is missing that a founder must fill before approving.

    Approval is the only thing standing between unreviewed AI research and a
    render, so it has to mean something. It used to flip the status on a
    bare request: a profile whose research had failed, or had only populated a
    couple of fields, could be approved and then steer the plan and strategy --
    with the gaps invisible, because AppProfileDetail renders only the fields
    that have values, so "not researched" and "intentionally blank" look alike.

    Website autofill made this reachable in ordinary use rather than as an edge
    case: it fills a handful of fields and reports success, so the profile looks
    researched and is approvable while most of what a plan needs is absent.

    Only the fields a plan actually depends on are required. Not requiring
    everything keeps a legitimate sparse profile -- an app with no proof
    moment, say -- approvable instead of forcing invented filler.
    """
    merged = dict(profile or {})
    for key, value in (pending or {}).items():
        if value not in (None, "", []):
            merged[key] = value

    def _text(key: str) -> bool:
        return bool(str(merged.get(key) or "").strip())

    def _list(key: str) -> bool:
        value = merged.get(key)
        if isinstance(value, str):
            value = [value]
        return bool(value and [v for v in value if str(v or "").strip()])

    def _any_list(*keys: str) -> bool:
        for key in keys:
            if _list(key):
                return True
        return False

    def _outcome_statements(key: str) -> bool:
        # The outcome layer is stored as a JSON list of linked entries, but a
        # founder editing by hand (or an older client) may send a JSON string,
        # so both shapes count. What matters is at least one entry with both
        # halves of the link: an outcome nobody can trace to a feature leaves
        # every later prompt guessing the mapping.
        value = merged.get(key)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return False
        if not isinstance(value, list):
            return False
        return any(
            isinstance(item, dict)
            and str(item.get("outcome") or "").strip()
            and str(item.get("from_feature") or "").strip()
            for item in value
        )

    checks = (
        ("a one-line description of what the app does", _text("brand_description")),
        ("at least one core feature", _list("core_features")),
        # Any of the three counts. usage_moments is the field the research
        # fills, but a founder writing the profile by hand describes what an app
        # is for under primary_use_cases or problems_solved just as naturally,
        # and refusing those would train them to type filler into the one field
        # the check happens to read.
        (
            "at least one thing people use it for",
            _any_list("usage_moments", "primary_use_cases", "problems_solved"),
        ),
        # The outcome layer is what lets the strategy pitch benefits instead
        # of listing features, so a profile without a single linked outcome
        # would approve straight into the fallback path. One linked entry is
        # the minimum — the research prompt asks for 3-6.
        (
            "at least one outcome statement linking a feature to its benefit",
            _outcome_statements("outcome_statements"),
        ),
    )
    return [label for label, ok in checks if not ok]


async def _angle_feedback_for_profile(brand_profile_id: str, user_id: str) -> dict:
    """
    Goal thumbs attributed to the angle kind and objective the founder picked.

    A goal verdict names its project, so attribution walks project -> angle
    kind + objective. Verdicts on templates, plans and scripts are filtered
    out by the summarizer and never steer goal generation.
    """
    rows = await _fetch_all(
        """SELECT ca.kind AS kind, sp.objective AS objective, f.event AS event,
                  f.step AS step, f.detail AS detail
           FROM feedback_events f
           LEFT JOIN studio_projects sp ON sp.id = f.studio_project_id
           LEFT JOIN content_angles ca ON ca.id = sp.content_angle_id
           WHERE f.brand_profile_id = ? AND f.user_id = ?
             AND f.event IN ('thumb_up', 'thumb_down')
           ORDER BY f.created_at DESC LIMIT 200""",
        (brand_profile_id, user_id),
    )
    return feedback_mod.summarize_angle_feedback(rows)


async def _component_feedback_for_profile(
    brand_profile_id: str, user_id: str, component: str
) -> dict:
    """One component's thumbs for this app, as {component: {up, down, total}}."""
    rows = await _fetch_all(
        "SELECT event, step FROM feedback_events"
        " WHERE brand_profile_id = ? AND user_id = ?"
        " AND event IN ('thumb_up', 'thumb_down')"
        " ORDER BY created_at DESC LIMIT 200",
        (brand_profile_id, user_id),
    )
    return {component: feedback_mod.summarize_component_feedback(rows)[component]}


async def _generation_verdicts(generation_ids: list, user_id: str) -> dict:
    """
    Each generation's saved thumb verdicts, as {generation_id: {component: 1|-1}}.

    One query for the whole page: rows come back newest-first so the first row
    seen per (generation, component) is the founder's current verdict. Only
    rows naming a generation count — wizard-time thumbs without one stay in
    the aggregates but never highlight a render. Scoped to the caller so one
    account's votes can never light up another's buttons.
    """
    ids = [g for g in (generation_ids or []) if g]
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = await _fetch_all(
        "SELECT generation_id, step, event FROM feedback_events"
        f" WHERE user_id = ? AND generation_id IN ({placeholders})"
        " AND event IN ('thumb_up', 'thumb_down')"
        " ORDER BY created_at DESC",
        tuple([user_id] + ids),
    )
    out: dict = {}
    for row in rows or []:
        gen_id = row.get("generation_id") or ""
        component = feedback_mod.normalize_component(row.get("step") or "")
        if not gen_id or not component:
            continue
        bucket = out.setdefault(gen_id, {})
        if component in bucket:
            continue
        bucket[component] = 1 if (row.get("event") or "") == "thumb_up" else -1
    return out


async def _with_verdicts(entries, user_id: str):
    """Attach each generation's saved thumb verdicts for thumb-state restore."""
    single = isinstance(entries, dict)
    items = [entries] if single else list(entries or [])
    verdicts = await _generation_verdicts([e.get("id") for e in items], user_id)
    for entry in items:
        entry["verdicts"] = verdicts.get(entry.get("id") or "", {})
    return entries


async def _auto_generate_content_angles(profile: dict, user_id: str) -> None:
    """
    Best-effort content angle generation after a profile is approved.

    Awaited inline by the caller, but failures never block the response:
    angles are derived data — if generation fails the founder can still use
    the profile and regenerate later (or the next listing backfills them).
    """
    try:
        angle_feedback = await _angle_feedback_for_profile(profile.get("id"), user_id)
        angles = await _log_model_call(
            "content_angles", "text", TEXT_MODEL,
            lambda: generate_content_angles(profile, angle_feedback=angle_feedback),
            user_id,
            brand_profile_id=profile.get("id"),
        )
    except Exception as e:
        logger.warning(f"Auto content angle generation failed for profile {profile.get('id')}: {e}")
        return

    if not angles:
        # An empty model reply must not silently wipe the section: without
        # this the listing shows nothing and nobody is told why.
        logger.warning(f"Auto content angle generation returned no angles for profile {profile.get('id')}")
        return

    await _execute("DELETE FROM content_angles WHERE brand_profile_id = ?", (profile.get("id"),))
    now = now_iso()
    for rank, angle in enumerate(angles):
        angle_id = str(uuid.uuid4())
        await _execute(
            """INSERT INTO content_angles
               (id, brand_profile_id, kind, label, target_audience, user_problem,
                 hook_promise, app_feature, desired_emotion,
                 claims_to_respect, rank, created_at, user_id, origin)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'generated')""",
            (angle_id, profile.get("id"), angle["kind"], angle["label"],
             angle["target_audience"], angle["user_problem"], angle["hook_promise"],
             angle["app_feature"], angle["desired_emotion"],
             json.dumps(angle["claims_to_respect"]), rank, now, user_id),
        )
    logger.info(f"Auto-generated %d content angle(s) for profile {profile.get('id')}", len(angles))


@api_router.post("/app-profiles/{profile_id}/approve")
async def approve_app_profile(
    profile_id: str, payload: ApproveAppProfileRequest, user_id: str = Depends(get_current_user_id)
):
    """Mark an App Profile reviewed and approved.

    When a refresh proposal is pending it is applied to the live fields by
    default and the version bumps — approval is the only path that mutates
    approved data, so refreshes can never silently overwrite it.

    Refused while the profile is too empty to approve, and the response names
    the gaps. See _approval_gaps for why a bare status flip was not enough.
    """
    existing = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="App Profile not found")

    pending = existing.get("pending_research")
    if isinstance(pending, str):
        try:
            pending = json.loads(pending)
        except (json.JSONDecodeError, TypeError):
            pending = None

    gaps = _approval_gaps(existing, pending)
    if gaps:
        raise HTTPException(
            status_code=409,
            detail=(
                "Fill in a few things before approving this App Profile: "
                + "; ".join(gaps)
                + ". It steers the plan and the video, so approving it half-filled "
                "means the render fills the blanks itself."
            ),
        )

    now = now_iso()
    if pending and isinstance(pending, dict) and payload.apply_pending is not False:
        apply = {}
        for key in APP_PROFILE_EDITABLE_FIELDS:
            if key in pending and pending[key] not in (None, "", []):
                apply[key] = pending[key]
        if apply:
            set_clauses, values = _brand_update_parts(apply)
            set_clauses.append("pending_research = NULL")
            set_clauses.append("version = ?")
            values.append((existing.get("version") or 1) + 1)
            set_clauses.append("status = 'approved'")
            set_clauses.append("approved_at = ?")
            values.append(now)
            set_clauses.append("updated_at = ?")
            values.append(now)
            values.append(profile_id)
            await _execute(
                f"UPDATE brand_profiles SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?",
                tuple(values) + (user_id,),
            )
            logger.info(f"Approved App Profile {profile_id} (version {(existing.get('version') or 1) + 1})")
            approved_profile = await _fetch_one(
                "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
            )
            await _auto_generate_content_angles(approved_profile, user_id)
            return approved_profile

    # No pending proposal (or the founder skipped applying it): approving the
    # draft as it stands is itself a legal UPDATE, so the status flip commits
    # even when nothing else changed. Without this, approving a freshly
    # researched or hand-created profile — both of which have no
    # pending_research — silently does nothing, the profile stays a draft,
    # and data appears to vanish on the next login.
    await _execute(
        "UPDATE brand_profiles SET status = 'approved', approved_at = ?, updated_at = ? "
        "WHERE id = ? AND user_id = ?",
        (now, now, profile_id, user_id),
    )
    logger.info(f"Approved App Profile {profile_id} (draft as-is, version {existing.get('version') or 1})")
    approved_profile = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    await _auto_generate_content_angles(approved_profile, user_id)
    return approved_profile


@api_router.post("/app-profiles/{profile_id}/regenerate-everything", status_code=201)
async def regenerate_everything(profile_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Regenerate everything for an App Profile: re-research, re-approve, regenerate angles.

    This is the single "regenerate everything" action. It:
    1. Re-runs research from the profile's URLs
    2. Applies the fresh research (bumps version, clears pending)
    3. Auto-generates content angles from the updated profile

    Replaces the need for per-section regenerate buttons.
    """
    require_ai_configured()
    existing = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="App Profile not found")

    # Step 1: Re-research from the same sources a refresh would read.
    sources, report = await _research_profile_sources(existing)

    try:
        proposal = await _log_model_call(
            "app_profile_refresh", "text", TEXT_MODEL,
            lambda: analyze_app_profile(sources, existing.get("notes") or ""),
            user_id,
            brand_profile_id=profile_id,
        )
    except Exception as e:
        logger.error(f"App regenerate failed for {profile_id}: {e}")
        raise HTTPException(status_code=502, detail=f"AI app research failed. Please try again. ({str(e)[:150]})")
    if not proposal or not isinstance(proposal, dict):
        raise HTTPException(status_code=502, detail="Research returned no usable data.")

    # Step 2: Apply the research the way approve applies a pending proposal.
    apply = {k: v for k, v in proposal.items() if k in APP_PROFILE_EDITABLE_FIELDS and v not in (None, "", [])}
    now = now_iso()
    if apply:
        set_clauses, values = _brand_update_parts(apply)
        set_clauses.append("pending_research = NULL")
        set_clauses.append("version = ?")
        values.append((existing.get("version") or 1) + 1)
        set_clauses.append("status = 'approved'")
        set_clauses.append("approved_at = ?")
        values.append(now)
        set_clauses.append("updated_at = ?")
        values.append(now)
        values.append(profile_id)
        await _execute(
            f"UPDATE brand_profiles SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?",
            tuple(values) + (user_id,),
        )
    else:
        # Still bump version and refresh timestamps even if no fields changed
        await _execute(
            "UPDATE brand_profiles SET version = ?, approved_at = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            ((existing.get("version") or 1) + 1, now, now, profile_id, user_id),
        )

    # Step 3: Auto-generate content angles from the updated profile
    updated_profile = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    await _auto_generate_content_angles(updated_profile, user_id)

    logger.info(f"Regenerated everything for App Profile {profile_id}")
    updated_profile["research_sources"] = report
    return updated_profile


async def _fetch_one_source(label: str, url: str, cap: int) -> tuple[str, str]:
    """One labeled fetch that never raises: _fetch_url_text already swallows
    fetch failures into "", and this guards the gather itself."""
    try:
        return label, await _fetch_url_text(url, cap)
    except Exception as e:
        logger.warning(f"App research: source {label} ({url}) failed outside the fetcher: {e}")
        return label, ""


async def _research_profile_sources(existing: dict) -> tuple[dict, list]:
    """
    Fetch readable text for an App Profile's stored URLs, concurrently.

    Returns (sources, report): sources maps label -> text for research;
    report lists {label, url, chars, ok} per source so the founder can see
    what was actually read and what failed, instead of a silent partial run.

    Shared by refresh (which stages the result as pending_research) and
    regenerate (which applies it directly): the two must read the same
    sources, or "regenerate everything" would rebuild the profile from
    different evidence than a refresh proposes.
    """
    urls: dict = {}
    if existing.get("website_url"):
        urls["website"] = (existing["website_url"], APP_RESEARCH_CAPS["website"])
    if existing.get("appstore_url"):
        urls["app_store"] = (existing["appstore_url"], APP_RESEARCH_CAPS["app_store"])
    if existing.get("play_url"):
        urls["google_play"] = (existing["play_url"], APP_RESEARCH_CAPS["google_play"])
    stored_support = existing.get("support_urls") or []
    if isinstance(stored_support, str):
        try:
            stored_support = json.loads(stored_support)
        except (json.JSONDecodeError, TypeError):
            stored_support = []
    for i, u in enumerate((stored_support or [])[:APP_RESEARCH_MAX_SUPPORT_URLS]):
        urls[f"support_{i + 1} ({u})"] = (u, APP_RESEARCH_CAPS["support"])
    if not urls:
        raise HTTPException(
            status_code=400,
            detail="This profile has no source URLs to research from. Add a website, App Store, "
                   "or Google Play URL first.",
        )

    results = await asyncio.gather(
        *(_fetch_one_source(label, url, cap) for label, (url, cap) in urls.items())
    )
    sources = dict(results)
    report = [
        {"label": label, "url": url, "chars": len(sources.get(label) or ""),
         "ok": bool((sources.get(label) or "").strip())}
        for label, (url, cap) in urls.items()
    ]
    read = sum(1 for r in report if r["ok"])
    logger.info(
        f"App research: read {read}/{len(report)} sources "
        f"({sum(r['chars'] for r in report)} chars)")
    if not any((v or "").strip() for v in sources.values()):
        raise HTTPException(
            status_code=400,
            detail="Could not extract readable text from any stored URL. The profile is unchanged.",
        )
    return sources, report


@api_router.post("/app-profiles/{profile_id}/refresh")
async def refresh_app_profile(profile_id: str, user_id: str = Depends(get_current_user_id)):
    """Re-research an App Profile from its stored URLs without touching live fields.

    The fresh analysis is stored as pending_research for founder review — the
    approved profile stays exactly as it was until approve applies it.
    """
    require_ai_configured()
    existing = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="App Profile not found")

    sources, report = await _research_profile_sources(existing)

    try:
        proposal = await _log_model_call(
            "app_profile_refresh", "text", TEXT_MODEL,
            lambda: analyze_app_profile(sources, existing.get("notes") or ""),
            user_id,
            brand_profile_id=profile_id,
        )
    except Exception as e:
        logger.error(f"App refresh failed for {profile_id}: {e}")
        raise HTTPException(status_code=502, detail=f"AI app research failed. Please try again. ({str(e)[:150]})")

    now = now_iso()
    await _execute(
        "UPDATE brand_profiles SET pending_research = ?, last_research_at = ?, updated_at = ? "
        "WHERE id = ? AND user_id = ?",
        (json.dumps(proposal), now, now, profile_id, user_id),
    )
    logger.info(f"Refreshed app profile {profile_id} into pending review")
    refreshed = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    refreshed["research_sources"] = report
    return refreshed


# ---------------------------------------------------------------------------
# Content angles (per App Profile)
# ---------------------------------------------------------------------------
# `recommended_cta` was here and is now gone: an angle describes the hook and
# the middle, and neither has a closing beat. The `recommended_cta TEXT` column
# survives in the schema for rows written before this and is neither written
# nor read.
CONTENT_ANGLE_TEXT_FIELDS = (
    "label", "target_audience", "user_problem", "hook_promise",
    "app_feature", "desired_emotion",
)


def _serialize_angle_row(row: dict, evidence: Optional[dict] = None) -> dict:
    """Shape a content_angles row for the API (kind is already normalized).

    `evidence` is this kind's own verdict tally from
    `_angle_feedback_for_profile`. Counts only — never a rate or a score:
    a percentage over one verdict would present a coin flip as a measurement.
    Keyed by KIND, not by angle id, so the counts survive an angle
    regeneration that replaces every row id.
    """
    return {
        "id": row.get("id"),
        "brand_profile_id": row.get("brand_profile_id"),
        "kind": row.get("kind"),
        "label": row.get("label") or "",
        "target_audience": row.get("target_audience") or "",
        "user_problem": row.get("user_problem") or "",
        "hook_promise": row.get("hook_promise") or "",
        "app_feature": row.get("app_feature") or "",
        "desired_emotion": row.get("desired_emotion") or "",
        "claims_to_respect": row.get("claims_to_respect") or [],
        "rank": row.get("rank") or 0,
        "goal_variant": int(row.get("goal_variant") or 0),
        "origin": row.get("origin") or "generated",
        # The six suggestions in THIS row's saved variant order, computed
        # server-side so every consumer (wizard, review recovery) agrees
        # without each client re-deriving the rotation.
        "goal_suggestions": template_library.goal_suggestions_for_kind(
            row.get("kind"), int(row.get("goal_variant") or 0)
        ),
        "created_at": row.get("created_at"),
        "evidence": evidence or {"wins": 0, "flops": 0},
    }


async def _serialize_profile_angles(profile_id: str, user_id: str) -> dict:
    """Re-read this profile's angles and shape the audience-step payload.

    The same shape as GET /content-angles: serialized rows (kind evidence
    plus each row's goal suggestions in its saved variant order) and the
    profile-wide objective_evidence map. POST generate/regenerate return
    this instead of the raw model rows, so the wizard never adopts a row
    shape the list endpoint would not serve — the old raw return dropped
    goal_suggestions (the goal picker silently fell back to the static
    order), evidence (verdict chips vanished), and objective_evidence
    (goal chips vanished) until the next reload.
    """
    rows = await _fetch_all(
        "SELECT * FROM content_angles WHERE brand_profile_id = ? AND user_id = ? "
        "ORDER BY rank ASC, created_at ASC",
        (profile_id, user_id),
    )
    verdicts = await _angle_feedback_for_profile(profile_id, user_id)
    by_kind = {
        str(entry.get("name") or ""): {"wins": int(entry.get("wins") or 0), "flops": int(entry.get("flops") or 0)}
        for entry in (verdicts.get("kinds") or [])
    }
    objective_evidence = {
        str(entry.get("name") or ""): {"wins": int(entry.get("wins") or 0), "flops": int(entry.get("flops") or 0)}
        for entry in (verdicts.get("objectives") or [])
    }
    return {
        "angles": [
            _serialize_angle_row(r, by_kind.get(str(r.get("kind") or "")))
            for r in rows
        ],
        "objective_evidence": objective_evidence,
    }


@api_router.get("/app-profiles/{profile_id}/content-angles")
async def list_content_angles(profile_id: str, user_id: str = Depends(get_current_user_id)):
    """
    This app's angles, each carrying its kind's own verdict tally.

    The tally is the same aggregate the generation prompt already reads
    (`_angle_feedback_for_profile`), so the founder picks from angles scored
    by their own history rather than by model confidence alone. It is counts,
    never a rate: one win is one verdict, and the UI says so. Ordering is
    still the generation rank — the counts annotate, they do not reorder.

    Both axes of the summary travel: `angles[].evidence` is the ANGLE KIND's
    tally (one chip per angle row), and `objective_evidence` is the video
    GOAL's tally for the whole profile (one count per goal card). The goal
    axis is the one that answers "what wins at the goal I am about to pick",
    which the kind axis cannot — a goal is shared across kinds, so its verdicts
    are the only evidence that speaks to that choice.
    """
    profile = await _fetch_one(
        "SELECT id, status FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")
    rows = await _fetch_all(
        "SELECT * FROM content_angles WHERE brand_profile_id = ? AND user_id = ? "
        "ORDER BY rank ASC, created_at ASC",
        (profile_id, user_id),
    )
    if not rows and profile.get("status") == "approved" and os.environ.get("OPENROUTER_API_KEY"):
        # Self-heal profiles approved before auto-generation existed — and
        # recover from a generation that returned nothing. The next view
        # fills the section instead of leaving it blank forever. Profiles
        # with hand-written angles (count > 0) and drafts never reach here.
        await _auto_generate_content_angles(
            await _fetch_one(
                "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
            ),
            user_id,
        )
        rows = await _fetch_all(
            "SELECT * FROM content_angles WHERE brand_profile_id = ? AND user_id = ? "
            "ORDER BY rank ASC, created_at ASC",
            (profile_id, user_id),
        )
    # One summary for the whole profile, indexed by kind and shared by every
    # angle of that kind -- two angles of the same kind carry the same counts,
    # which is honest (the attribution is per kind) and is never presented as
    # belonging to one specific angle. Serialized through the shared helper
    # so the list and the generate/regenerate responses can never drift
    # apart in shape again.
    return await _serialize_profile_angles(profile_id, user_id)


@api_router.delete("/app-profiles/{profile_id}")
async def delete_app_profile(profile_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Delete an App Profile and everything scoped to it.

    Cascades to the profile's content angles, studio projects, generations,
    assets, feedback events, and
    asset event logs. The model_requests ledger is deliberately kept: it is
    the audit trail of which provider calls ran, and its orphaned rows are
    harmless.

    Deletion is refused while a generation is still in flight, so a run that
    finishes or fails on its own is never left without the profile it belongs
    to.

    Files are removed best-effort: the profile's asset folder and any locally
    cached generation videos. R2 copies are left in place; they are
    content-addressed orphans that harm nothing.
    """
    row = await _fetch_one(
        "SELECT id FROM brand_profiles WHERE id = ? AND user_id = ?",
        (profile_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="App Profile not found")

    in_flight = await _fetch_one(
        """SELECT id FROM generations
           WHERE brand_profile_id = ? AND status IN ('submitted', 'generating')
           LIMIT 1""",
        (profile_id,),
    )
    if in_flight:
        raise HTTPException(
            status_code=409,
            detail="This profile has a generation still running. Wait for it to finish, then delete.",
        )

    gen_ids = [
        r["id"]
        for r in await _fetch_all(
            "SELECT id FROM generations WHERE brand_profile_id = ?", (profile_id,)
        )
    ]

    for table in (
        "content_angles",
        "studio_projects",
        "generations",
        "assets",
        "feedback_events",
        "asset_events",
    ):
        await _execute(f"DELETE FROM {table} WHERE brand_profile_id = ?", (profile_id,))
    await _execute(
        "DELETE FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )

    # Best-effort file cleanup. A leaked file must never fail the delete.
    shutil.rmtree(_asset_dir(profile_id), ignore_errors=True)
    for gen_id in gen_ids:
        try:
            (pipeline.STORAGE_DIR / "videos" / f"{gen_id}.mp4").unlink(missing_ok=True)
        except OSError as e:
            logger.warning(f"Could not remove cached video for generation {gen_id}: {e}")

    logger.info(f"Deleted App Profile {profile_id} ({len(gen_ids)} generation(s) removed)")
    return {"deleted": True, "id": profile_id, "generations_removed": len(gen_ids)}


@api_router.post("/app-profiles/{profile_id}/content-angles", status_code=201)
async def generate_profile_content_angles(profile_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Generate content angles from an APPROVED App Profile.

    Requires approval deliberately: angles are derived from the profile's
    verified facts, so generating them from an unreviewed draft would let
    unverified research steer the video plan. Regenerating replaces the
    existing set (they are derived data, not founder-authored content).
    """
    require_ai_configured()
    profile = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")
    if profile.get("status") != "approved":
        raise HTTPException(
            status_code=409,
            detail="Review and approve this App Profile before generating content angles.",
        )

    try:
        angle_feedback = await _angle_feedback_for_profile(profile_id, user_id)
        angles = await _log_model_call(
            "content_angles", "text", TEXT_MODEL,
            lambda: generate_content_angles(profile, angle_feedback=angle_feedback),
            user_id,
            brand_profile_id=profile_id,
        )
    except Exception as e:
        logger.error(f"Content angle generation failed for profile {profile_id}: {e}")
        raise HTTPException(status_code=502, detail=f"AI content angle generation failed. Please try again. ({str(e)[:150]})")

    await _execute("DELETE FROM content_angles WHERE brand_profile_id = ?", (profile_id,))
    now = now_iso()
    for rank, angle in enumerate(angles):
        angle_id = str(uuid.uuid4())
        await _execute(
"""INSERT INTO content_angles
               (id, brand_profile_id, kind, label, target_audience, user_problem,
                 hook_promise, app_feature, desired_emotion,
                 claims_to_respect, rank, created_at, user_id, origin)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'generated')""",
            (angle_id, profile_id, angle["kind"], angle["label"],
             angle["target_audience"], angle["user_problem"], angle["hook_promise"],
             angle["app_feature"], angle["desired_emotion"],
             json.dumps(angle["claims_to_respect"]), rank, now, user_id),
        )
    # Re-read, never echo the model rows: the wizard adopts this response
    # into the same state the list endpoint feeds, so it must carry the
    # serialized shape (goal suggestions, evidence, origin) or the goal
    # picker and verdict chips degrade until the next reload.
    payload = await _serialize_profile_angles(profile_id, user_id)
    logger.info(f"Generated %d content angle(s) for profile {profile_id}", len(payload["angles"]))
    return payload


@api_router.post("/app-profiles/{profile_id}/content-angles/manual", status_code=201)
async def create_manual_content_angle(
    profile_id: str, payload: CreateContentAngleRequest, user_id: str = Depends(get_current_user_id)
):
    """Add one hand-written content angle. Founder-authored, never overwritten
    by a regeneration pass (regeneration only replaces AI-generated rows)."""
    profile = await _fetch_one(
        "SELECT id FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")
    label = (payload.label or "").strip()
    if not label:
        raise HTTPException(status_code=400, detail="A short label is required for a content angle.")
    if not (payload.target_audience or "").strip() or not (payload.user_problem or "").strip():
        raise HTTPException(
            status_code=400,
            detail="A content angle needs both a target audience and a user problem.",
        )

    cursor = await _fetch_one(
        "SELECT COALESCE(MAX(rank), -1) AS max_rank FROM content_angles WHERE brand_profile_id = ?",
        (profile_id,),
    )
    rank = int((cursor or {}).get("max_rank") or -1) + 1
    angle_id = str(uuid.uuid4())
    now = now_iso()
    claims = _normalize_str_list(payload.claims_to_respect)
    await _execute(
        """INSERT INTO content_angles
           (id, brand_profile_id, kind, label, target_audience, user_problem,
             hook_promise, app_feature, desired_emotion,
             claims_to_respect, rank, created_at, user_id, origin)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual')""",
        (angle_id, profile_id, template_library.normalize_angle_kind(payload.kind), label,
         (payload.target_audience or "").strip(), (payload.user_problem or "").strip(),
         (payload.hook_promise or "").strip(), (payload.app_feature or "").strip(),
         (payload.desired_emotion or "").strip(),
         json.dumps(claims), rank, now, user_id),
    )
    row = await _fetch_one("SELECT * FROM content_angles WHERE id = ?", (angle_id,))
    return _serialize_angle_row(row)


@api_router.patch("/app-profiles/{profile_id}/content-angles/{angle_id}")
async def update_content_angle(
    profile_id: str, angle_id: str, payload: UpdateContentAngleRequest, user_id: str = Depends(get_current_user_id)
):
    row = await _fetch_one(
        "SELECT * FROM content_angles WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
        (angle_id, profile_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Content angle not found")

    updates = payload.model_dump(exclude_unset=True)
    set_clauses, values = [], []
    if "kind" in updates:
        set_clauses.append("kind = ?")
        values.append(template_library.normalize_angle_kind(updates["kind"]))
    for key in CONTENT_ANGLE_TEXT_FIELDS:
        if key in updates:
            set_clauses.append(f"{key} = ?")
            values.append((updates[key] or "").strip())
    if "claims_to_respect" in updates:
        set_clauses.append("claims_to_respect = ?")
        values.append(json.dumps(_normalize_str_list(updates["claims_to_respect"])))
    if not set_clauses:
        return _serialize_angle_row(row)

    values.extend([angle_id, profile_id, user_id])
    await _execute(
        f"UPDATE content_angles SET {', '.join(set_clauses)} WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
        tuple(values),
    )
    return _serialize_angle_row(
        await _fetch_one("SELECT * FROM content_angles WHERE id = ?", (angle_id,))
    )


@api_router.post("/app-profiles/{profile_id}/content-angles/regenerate")
async def regenerate_content_angles(profile_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Regenerate the AI-derived audience angles for an APPROVED App Profile.

    Same generate-then-replace flow as POST /content-angles, with one
    deliberate difference: hand-written angles survive. Rows tagged
    origin='manual' are founder-authored content, not derived data — the
    model writes nothing like them, and a regen the founder asked for must
    not delete writing they did. Generate runs BEFORE any delete, so a
    model failure leaves the previous set (generated and manual alike)
    fully intact.
    """
    require_ai_configured()
    profile = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")
    if profile.get("status") != "approved":
        raise HTTPException(
            status_code=409,
            detail="Review and approve this App Profile before regenerating content angles.",
        )

    try:
        angle_feedback = await _angle_feedback_for_profile(profile_id, user_id)
        angles = await _log_model_call(
            "content_angles", "text", TEXT_MODEL,
            lambda: generate_content_angles(profile, angle_feedback=angle_feedback),
            user_id,
            brand_profile_id=profile_id,
        )
    except Exception as e:
        logger.error(f"Content angle regeneration failed for profile {profile_id}: {e}")
        raise HTTPException(status_code=502, detail=f"AI content angle generation failed. Please try again. ({str(e)[:150]})")

    # Manual rows first -- their ids are needed after the replacement set is
    # written. Nothing is deleted yet.
    manual_rows = await _fetch_all(
        "SELECT * FROM content_angles WHERE brand_profile_id = ? AND user_id = ? AND origin = 'manual' "
        "ORDER BY rank ASC, created_at ASC",
        (profile_id, user_id),
    )

    # Projects referencing the derived angles about to be removed keep their
    # row (LEFT JOIN degrades to a null angle later) but lose the story they
    # were built around. Counting them BEFORE the delete turns that quiet
    # break into a number the founder can be told about.
    affected = await _fetch_one(
        "SELECT COUNT(*) AS n FROM studio_projects WHERE brand_profile_id = ? AND user_id = ? "
        "AND content_angle_id IN (SELECT id FROM content_angles WHERE brand_profile_id = ? "
        "AND (origin IS NULL OR origin != 'manual'))",
        (profile_id, user_id, profile_id),
    )
    projects_affected = int((affected or {}).get("n") or 0)

    # The guarded delete: only derived rows are replaced. A manual row can
    # still be removed through the ordinary DELETE endpoint, by its founder.
    await _execute(
        "DELETE FROM content_angles WHERE brand_profile_id = ? AND (origin IS NULL OR origin != 'manual')",
        (profile_id,),
    )
    now = now_iso()
    for rank, angle in enumerate(angles):
        angle_id = str(uuid.uuid4())
        await _execute(
            """INSERT INTO content_angles
               (id, brand_profile_id, kind, label, target_audience, user_problem,
                 hook_promise, app_feature, desired_emotion,
                 claims_to_respect, rank, created_at, user_id, origin)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'generated')""",
            (angle_id, profile_id, angle["kind"], angle["label"],
             angle["target_audience"], angle["user_problem"], angle["hook_promise"],
             angle["app_feature"], angle["desired_emotion"],
             json.dumps(angle["claims_to_respect"]), rank, now, user_id),
        )
    # Manual rows move to the back of the generated set's rank range -- the
    # same back-of-list position the manual endpoint gives a newly hand-written
    # angle -- so the fresh AI set presents first.
    for offset, row in enumerate(manual_rows):
        await _execute(
            "UPDATE content_angles SET rank = ? WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
            (len(angles) + offset, row.get("id"), profile_id, user_id),
        )
    logger.info(
        "Regenerated %d content angle(s) (kept %d manual) for profile %s",
        len(angles), len(manual_rows), profile_id,
    )
    # Re-read, never echo the model rows: same serialized shape as the list
    # (goal suggestions, evidence, origin), or the wizard's goal picker and
    # verdict chips degrade until the next reload. Manual rows ride along in
    # rank order, which is also what keeps a hand-picked manual selection
    # alive across the replacement.
    payload = await _serialize_profile_angles(profile_id, user_id)
    return {**payload, "manual_kept": len(manual_rows), "projects_affected": projects_affected}


@api_router.post("/app-profiles/{profile_id}/content-angles/{angle_id}/regenerate-goals")
async def regenerate_angle_goal_suggestions(
    profile_id: str, angle_id: str, user_id: str = Depends(get_current_user_id)
):
    """
    Show a different ordering of this angle's six goal suggestions.

    No model call and no model_requests row: the suggestions are the same six
    curated goals every time — what changes is their ORDER, advanced one
    deterministic variant step (template_library.goal_suggestions_for_kind).
    The picked variant is persisted on the angle row, so a reload re-shows
    the exact ordering the founder last asked for rather than silently
    reverting — the same cache-stability rule the goal picker's existing
    "selected goal outside the suggestions" state already relies on.

    Not gated on profile approval deliberately: the variant is presentation
    state, not derived data — reordering suggestions for an angle the founder
    can already see changes no claim, no fact, and no plan.
    """
    row = await _fetch_one(
        "SELECT id, kind, goal_variant FROM content_angles "
        "WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
        (angle_id, profile_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Content angle not found")

    next_variant = template_library.next_goal_suggestion_variant(row.get("goal_variant"))
    suggestions = template_library.goal_suggestions_for_kind(row.get("kind"), next_variant)
    await _execute(
        "UPDATE content_angles SET goal_variant = ? WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
        (next_variant, angle_id, profile_id, user_id),
    )
    return {
        "goal_variant": next_variant,
        "suggestions": suggestions,
    }


@api_router.get("/app-profiles/{profile_id}/content-angles/{angle_id}/goal-suggestions")
async def angle_goal_suggestions(
    profile_id: str, angle_id: str, user_id: str = Depends(get_current_user_id)
):
    """Read-only view of the same six suggestions in the angle's saved variant
    order, for a step that renders the picker without a full angles reload."""
    row = await _fetch_one(
        "SELECT kind, goal_variant FROM content_angles "
        "WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
        (angle_id, profile_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Content angle not found")
    variant = int(row.get("goal_variant") or 0)
    return {
        "goal_variant": variant,
        "suggestions": template_library.goal_suggestions_for_kind(
            row.get("kind"), variant
        ),
    }


@api_router.delete("/app-profiles/{profile_id}/content-angles/{angle_id}")
async def delete_content_angle(profile_id: str, angle_id: str, user_id: str = Depends(get_current_user_id)):
    row = await _fetch_one(
        "SELECT id FROM content_angles WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
        (angle_id, profile_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Content angle not found")
    await _execute(
        "DELETE FROM content_angles WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
        (angle_id, profile_id, user_id),
    )
    return {"deleted": angle_id}


# ---------------------------------------------------------------------------
# Hook Template Library
# ---------------------------------------------------------------------------
def _public_library_template(template: dict) -> dict:
    """Serialize a library template: no storage bytes, structure fields parsed."""
    public = _public_template(template)
    public["archived"] = bool(public.get("archived"))
    public["is_favorite"] = bool(public.get("is_favorite"))
    public["app_categories"] = public.get("app_categories") or []
    public["audiences"] = public.get("audiences") or []
    public["required_assets"] = public.get("required_assets") or []
    public["content_slots"] = public.get("content_slots") or {}
    # Rows written before the outcome column existed (and tailored rows from
    # before it was generated) carry NULL: the card falls back rather than
    # rendering nothing where the headline goes.
    public["outcome"] = public.get("outcome") or ""
    # A library template is usable only once reviewed. Curated rows ship
    # approved; research drafts must be published by an operator.
    public["is_library_template"] = bool(public.get("opening_structure"))
    public["is_usable"] = (
        public["is_library_template"]
        and public.get("review_status") == "approved"
        and not public["archived"]
    )
    return public


@api_router.get("/templates")
async def list_templates(
    q: str = "",
    category: str = "",
    objective: str = "",
    app_category: str = "",
    origin: str = "",
    favorites_only: bool = False,
    include_archived: bool = False,
    user_id: str = Depends(get_current_user_id),
):
    """
    Browse the Hook Template Library.

    Curated templates are shared (user_id='system'); an operator's own custom
    and research-draft templates are scoped to them. `q` matches name and
    opening structure. Filters are ANDed.
    """
    clauses = ["(user_id = ? OR user_id = 'system')"]
    params: list = [user_id]
    if not include_archived:
        clauses.append("archived = 0")
    if q.strip():
        clauses.append("(LOWER(name) LIKE ? OR LOWER(COALESCE(opening_structure, '')) LIKE ?)")
        needle = f"%{q.strip().lower()}%"
        params.extend([needle, needle])
    if category.strip():
        clauses.append("category = ?")
        params.append(template_library.normalize_category(category))
    if objective.strip():
        norm_obj = template_library.normalize_objective(objective)
        if norm_obj:
            clauses.append("objective = ?")
            params.append(norm_obj)
    if app_category.strip():
        # app_categories is a JSON array; match the needle inside the text.
        clauses.append("LOWER(COALESCE(app_categories, '')) LIKE ?")
        params.append(f"%{app_category.strip().lower()}%")
    if origin.strip():
        clauses.append("origin = ?")
        params.append(origin.strip().lower())
    if favorites_only:
        clauses.append(
            "id IN (SELECT template_id FROM template_favorites WHERE user_id = ?)"
        )
        params.append(user_id)

    rows = await _fetch_all(
        f"""SELECT * FROM hook_templates WHERE {' AND '.join(clauses)}
            ORDER BY name ASC LIMIT 300""",
        tuple(params),
    )
    return {"templates": await _with_favorites(rows, user_id)}


async def _generations_table_exists() -> bool:
    """Whether the Phase 7 `generations` table has been created yet.

    Lets usage history degrade to an empty list before that phase lands
    instead of erroring on every template detail request.
    """
    row = await _fetch_one(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'generations'"
    )
    return row is not None


async def _with_favorites(rows: list, user_id: str) -> list:
    """Overlay this user's favorite state onto template rows.

    The stored is_favorite column is only meaningful for an operator's own
    template; shared curated rows are favorited via template_favorites.
    """
    ids = [r["id"] for r in rows if r.get("id")]
    favorited = set()
    if ids:
        placeholders = ",".join("?" for _ in ids)
        favs = await _fetch_all(
            f"SELECT template_id FROM template_favorites WHERE user_id = ? AND template_id IN ({placeholders})",
            tuple([user_id] + ids),
        )
        favorited = {f["template_id"] for f in favs}
    out = []
    for row in rows:
        public = _public_library_template(row)
        is_own = row.get("user_id") == user_id
        public["is_favorite"] = bool(
            row["id"] in favorited or (is_own and row.get("is_favorite"))
        )
        out.append(public)
    return out


@api_router.get("/templates/facets")
async def template_facets(user_id: str = Depends(get_current_user_id)):
    """Controlled vocabularies + observed categories, for building filter UI."""
    rows = await _fetch_all(
        "SELECT DISTINCT category FROM hook_templates "
        "WHERE (user_id = ? OR user_id = 'system') AND archived = 0",
        (user_id,),
    )
    # How many renders a total length actually takes, so the length picker can
    # say so before the founder chooses rather than after it has run.
    # Derived from the default studio model's real single-pass ceiling -- today
    # minimax-h3 caps at 15s, which makes the 20s and 30s options two passes.
    # Read per request rather than baked in, so pointing VIDEO_MODEL_DEFAULT at
    # a longer model relabels the options instead of quietly lying.
    default_cap = video_providers.capability()
    max_pass = max(1, int(default_cap.get("max_duration") or 30))
    return {
        "hook_categories": template_library.HOOK_CATEGORIES,
        "objectives": template_library.VIDEO_OBJECTIVES,
        "angle_goal_recommendations": {
            kind: list(goals)
            for kind, goals in template_library.ANGLE_GOAL_RECOMMENDATIONS.items()
        },
        "objective_outcomes": template_library.OBJECTIVE_OUTCOMES,
        "angle_goal_fit_reasons": {
            kind: dict(reasons)
            for kind, reasons in template_library.ANGLE_GOAL_FIT_REASONS.items()
        },
        "content_angle_kinds": template_library.CONTENT_ANGLE_KINDS,
        "asset_kinds": template_library.ASSET_KINDS,
        "supported_durations": template_library.SUPPORTED_DURATIONS,
        "duration_segments": {
            d: max(1, -(-int(d) // max_pass)) for d in template_library.SUPPORTED_DURATIONS
        },
        "origins": template_library.TEMPLATE_ORIGINS,
        "categories_in_use": sorted({r["category"] for r in rows if r.get("category")}),
    }


# ---------------------------------------------------------------------------
# Template recommendation
# ---------------------------------------------------------------------------
# Terminal punctuation for an objective outcome spliced into a reason.
#
# OBJECTIVE_OUTCOMES are complete sentences with no trailing period, because the
# goal picker shows them as a standalone line where a trailing dot would be
# noise. The scorer composes them INTO a sentence, so it has to close the one it
# opens -- hence this. It is not a bare f"{outcome}." because an outcome ending
# in "?" or "!" would then come out as "?." / "!.".
def _outcome_as_sentence(outcome: str) -> str:
    text = str(outcome or "").strip()
    if not text:
        return ""
    return text if text[-1] in ".!?" else text + "."


def _score_template_for_angle(
    template: dict,
    profile: dict,
    angle: Optional[dict],
    objective: str,
    feedback_events=(),
) -> dict:
    """
    Score one template against an App Profile + angle + objective.

    Deliberately transparent and deterministic rather than an LLM call: the
    founder sees WHY a template was picked, and a recommendation can be
    re-derived and audited. Scoring is a weighted sum of explicit signals;
    reasons are ranked by weight so the first one shown is the strongest
    factor. The founder-facing scale is 0–10 (the template step shows
    "Fit X/10"), so the sum is clamped into that range at the single return
    below — after feedback, which would otherwise push strong matches above
    10 or heavily rejected ones below 0. Clamping is monotonic, so the
    ranking the sort uses is unchanged.

    URL-analysis factors are real inputs, with the angle taking precedence
    and the profile as fallback: app category, target audience (normalized
    to tags, plus funnel stages implied by the angle kind), the core problem
    (normalized to problem tags), and the main feature. Matching is tag
    overlap via recommendation_tags, never brittle full-string equality.
    Reasons describe what the footage DOES for the viewer — where it leaves
    them — which is still a structural claim about the video, not a promise
    about what it will earn. No performance claims, ever.
    """
    score = 0.0
    weighted = []  # (weight, reason), sorted by weight at the end
    limitations = []
    matched = {"category": None, "audience_tags": [], "problem_tags": [], "feature_keyword": ""}

    def add(weight, reason):
        weighted.append((weight, reason))

    # Brand-tailored templates were generated from this exact profile, so
    # they start with a head start. The bonus is silent now: the tailored
    # set is already labelled "Tailored for this app" on the template step,
    # so a per-card bullet repeating it was noise, not evidence. Ranking is
    # unchanged — the +2.0 still applies, it just no longer narrates itself.
    if (template.get("brand_profile_id") or "") and template.get("brand_profile_id") == (profile.get("id") or ""):
        score += 2.0

    angle = angle or {}
    tpl_objective = (template.get("objective") or "").strip()
    tpl_categories = [
        recommendation_tags.category_key(c)
        for c in (template.get("app_categories") or [])
        if recommendation_tags.category_key(c)
    ]
    tpl_audience_tags = set(
        recommendation_tags.audience_tags(*[str(a) for a in (template.get("audiences") or [])])
    )
    required_assets = [str(a).lower() for a in (template.get("required_assets") or [])]

    if objective and tpl_objective:
        if tpl_objective == objective:
            score += 3.0
            # The objective name stays in the sentence: it is the goal the
            # founder picked, and what follows is what the footage does about
            # that goal. See OBJECTIVE_OUTCOMES.
            #
            # A full stop, not an em dash, between the two: those outcomes are
            # capitalized sentences in their own right (they are shown that way
            # on the goal picker), so splicing one in after a dash produced
            # "Built for 'create curiosity' — Leaves them wanting the answer."
            add(3.0, f"Built for '{objective.replace('_', ' ')}'. "
                     f"{_outcome_as_sentence(template_library.OBJECTIVE_OUTCOMES.get(objective)) or 'Serves the goal you picked.'}")
        else:
            score += 0.5
            add(
                0.5,
                f"Made for '{tpl_objective.replace('_', ' ')}'. "
                f"{_outcome_as_sentence(template_library.OBJECTIVE_OUTCOMES.get(tpl_objective)) or 'Serves that goal.'} "
                f"Close to your '{objective.replace('_', ' ')}' goal.",
            )

    profile_category = (profile.get("app_category") or profile.get("niche") or "").strip()
    if profile_category and tpl_categories:
        key = recommendation_tags.category_key(profile_category)
        hit = next((c for c in tpl_categories if c in key or key in c), None)
        if hit:
            score += 2.5
            add(2.5, f"Lands with {profile_category} viewers before the app is even named — "
                     f"framed for how they talk about the problem.")
            matched["category"] = hit
        else:
            limitations.append(
                f"Framed for {', '.join(tpl_categories)} rather than {profile_category} — "
                f"the opening will need rewording."
            )
    if profile_category and not tpl_categories:
        score += 1.0
        add(1.0, "Carries no category assumptions, so it fits this app without reframing.")

    # ---- Audience: people from the profile/angle, plus the funnel stage
    # the angle kind implies. Curated templates tag funnel stage; profiles
    # describe people; recommendation_tags normalizes both to one axis.
    audience_texts = [angle.get("target_audience") or profile.get("target_audience") or ""]
    audience_texts += recommendation_tags.text_list(profile.get("icp_segments"))
    app_audience_tags = set(recommendation_tags.audience_tags(*audience_texts))
    app_audience_tags |= set(recommendation_tags.angle_funnel_tags(angle.get("kind") or ""))
    if app_audience_tags and tpl_audience_tags:
        overlap = sorted(app_audience_tags & tpl_audience_tags)
        if overlap:
            score += 1.0
            add(1.0, f"Aimed at {', '.join(overlap)} — they're already in the situation this opens on.")
            matched["audience_tags"] = overlap
            if len(overlap) >= 2:
                score += 0.5
    elif app_audience_tags and not tpl_audience_tags:
        score += 0.5
        add(0.5, "Open to anyone, so it reaches viewers outside your usual audience too.")

    # ---- Problem: the core problem from the angle or the profile research.
    problem_text = (angle.get("user_problem") or "").strip()
    if not problem_text:
        problem_text = "; ".join(recommendation_tags.text_list(profile.get("problems_solved")))
    app_problem_tags = set(recommendation_tags.problem_tags(problem_text)) if problem_text else set()
    if app_problem_tags:
        # cta_pattern is gone and continuation_structure is only read as a
        # fallback for a row seeded before middle_structure existed. Matching
        # against a retired CTA string would let a template be recommended for
        # containing the words of a call to action it no longer has.
        template_blob = " ".join(
            [str(template.get("name") or ""), str(template.get("category") or ""),
             str(tpl_objective), str(template.get("opening_structure") or ""),
             str(template.get("middle_structure")
                 or template.get("continuation_structure") or "")]
            + [f"{k} {v}" for k, v in (template.get("content_slots") or {}).items()]
        )
        overlap = sorted(app_problem_tags & set(recommendation_tags.problem_tags(template_blob)))
        foreground = (template.get("category") or "") in (
            "pain-point-question", "contrarian", "before-after",
        ) or tpl_objective == "address_user_problem"
        if overlap:
            score += 1.0
            add(1.0, f"Names {', '.join(overlap)} in the first seconds, so the viewer "
                     f"recognises themselves before your app appears.")
            matched["problem_tags"] = overlap
            if len(overlap) >= 2:
                score += 0.5
        elif foreground:
            score += 0.5
            add(0.5, "Opens on the viewer's problem, which is what this angle leads with.")

    # ---- Angle-kind / structure affinity. The weights are unchanged; only
    # the sentences changed. Each one now leads with what the viewer gets
    # rather than the name of the structure that delivers it.
    angle_kind = (angle.get("kind") or "").strip()
    if angle_kind:
        demo_categories = {"demo", "tutorial", "reveal"}
        story_categories = {"story", "pov", "before-after"}
        if angle_kind in ("feature_demonstration", "fast_tutorial") and template.get("category") in demo_categories:
            score += 2.0
            add(2.0, "Opens where your feature lives, so the demo you attach answers a question the viewer is already holding.")
        elif angle_kind in ("founder_story", "daily_life_use_case") and template.get("category") in story_categories:
            score += 2.0
            add(2.0, "Someone on camera lives it rather than describing it — a story-led angle needs a person, not a pitch.")
        elif angle_kind in ("problem_solution", "common_mistake") and template.get("category") in (
            "pain-point-question", "contrarian", "listicle", "pattern-interrupt"
        ):
            score += 2.0
            add(2.0, "Your angle leads with the problem, and so does the first line of this.")
        elif angle_kind in ("competitor_alternative", "product_comparison") and template.get("category") == "social-proof":
            score += 2.0
            add(2.0, "Leaves the two options side by side on screen, which is what a side-by-side angle needs.")
        elif angle_kind in ("objection_handling", "privacy_pricing_differentiation") and template.get("category") in (
            "contrarian", "social-proof", "curiosity-gap"
        ):
            score += 1.5
            add(1.5, "Asks the doubt out loud and leaves it standing — your demo is what answers it.")
        else:
            score += 0.5

    # ---- Main feature: the angle's feature, or the top core feature from
    # the URL analysis when no angle is selected.
    main_feature = (angle.get("app_feature") or "").strip()
    if not main_feature:
        feats = recommendation_tags.text_list(profile.get("core_features"))
        main_feature = feats[0] if feats else ""
    if main_feature:
        feature_tokens = {t for t in main_feature.replace(",", " ").split() if len(t) > 3}
        slot_blob = " ".join(str(v) for v in (template.get("content_slots") or {}).values()).lower()
        name_blob = f"{template.get('name') or ''} {template.get('category') or ''}".lower()
        hit = next(
            (tok for tok in feature_tokens if tok.lower() in slot_blob or tok.lower() in name_blob),
            None,
        )
        if hit:
            score += 1.0
            # The match is still a token hit on the slot values — that is the
            # honest signal. What changed is the sentence: it names what the
            # viewer gets (the feature as the reason they stayed) instead of
            # naming the field that matched (the content slot).
            add(1.0, f"Puts '{hit}' at the centre of the piece — your main feature "
                     f"arrives as the reason they stayed, not as a bullet.")
            matched["feature_keyword"] = hit

    if angle.get("claims_to_respect"):
        limitations.append(
            "Bounded by: " + "; ".join(str(c) for c in angle["claims_to_respect"][:3])
        )

    if required_assets:
        limitations.append(
            "Needs " + ", ".join(a.replace("_", " ") for a in required_assets) + "."
        )
    if not (template.get("middle_structure") or template.get("continuation_structure")):
        limitations.append("No middle structure recorded; the studio will infer one.")
    if (template.get("review_status") or "approved") != "approved":
        limitations.append("Unpublished research draft - review before using.")

    # Strongest factor first. Stable sort keeps same-weight reasons in
    # insertion order, and feedback still lands at the very top below.
    weighted.sort(key=lambda item: -item[0])
    reasons = [reason for _, reason in weighted]

    feedback = feedback_mod.template_feedback_adjustment(
        feedback_events, template.get("id") or ""
    )
    if feedback["delta"]:
        score += feedback["delta"]
        if feedback["explicit_rejections"] or feedback["automatic_changes"]:
            rejections = feedback["explicit_rejections"] + feedback["automatic_changes"]
            limitations.insert(
                0,
                f"Rejected or replaced {rejections} time(s) for this app.",
            )
        if feedback["thumb_downs"]:
            limitations.insert(
                0,
                f"Rated a poor template {feedback['thumb_downs']} time(s) for this app.",
            )
        if feedback["thumb_ups"]:
            reasons.insert(
                0,
                f"Rated a good template {feedback['thumb_ups']} time(s) for this app.",
            )

    # The 0–10 bound lives here, not in the caller: this is the single
    # return every recommendation flows through, so no consumer can ever
    # show a fit outside the scale the template step advertises.
    score = max(0.0, min(10.0, score))
    return {
        "score": round(score, 2),
        "reasons": reasons,
        "limitations": limitations,
        "feedback": feedback,
        "matched": matched,
    }

@api_router.get("/app-profiles/{profile_id}/template-recommendations")
async def recommend_templates(
    profile_id: str,
    angle_id: str = "",
    objective: str = "",
    limit: int = 8,
    user_id: str = Depends(get_current_user_id),
):
    """
    Recommend library templates for an App Profile, optionally narrowed to one
    content angle and objective.

    The founder can always ignore this and pick any compatible template
    manually — recommendations are a starting point, not a gate. Only usable
    (approved, non-archived) library templates are returned.

    The App Profile itself must be approved. Ranking templates against
    unreviewed research would steer the founder's pick with claims nobody has
    verified, which is the same reason every other studio step funnels through
    the approval check. The studio only offers approved profiles in its picker,
    and the profile page already explains that recommendations appear after
    approval, so this is unreachable from the normal flow rather than a new
    dead end in it.
    """
    profile = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")
    if profile.get("status") != "approved":
        raise HTTPException(
            status_code=409,
            detail="Review and approve this App Profile before ranking templates against it.",
        )

    angle = None
    if angle_id.strip():
        angle = await _fetch_one(
            "SELECT * FROM content_angles WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
            (angle_id.strip(), profile_id, user_id),
        )
        if not angle:
            raise HTTPException(status_code=404, detail="Content angle not found for this App Profile")

    norm_objective = template_library.normalize_objective(objective) if objective else ""
    templates = await _fetch_all(
        """SELECT * FROM hook_templates
           WHERE (user_id = ? OR user_id = 'system')
             AND archived = 0 AND review_status = 'approved'
             AND opening_structure IS NOT NULL AND opening_structure != ''""",
        (user_id,),
    )
    if not templates:
        return {"recommendations": [], "angle": _serialize_angle_row(angle) if angle else None}

    # Past behavior informs the order, but it is bounded and explainable: the
    # exact adjustment and its factual basis travel with each recommendation.
    feedback_events = await _fetch_all(
        "SELECT event, signal, reason, template_id, step FROM feedback_events "
        "WHERE brand_profile_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 200",
        (profile_id, user_id),
    )
    scored = []
    for tpl in templates:
        result = _score_template_for_angle(
            tpl, profile, angle, norm_objective, feedback_events
        )
        scored.append({
            "template": _public_library_template(tpl),
            "score": result["score"],
            "why_it_fits": result["reasons"],
            "matched_factors": result["matched"],
            "target_audience": (angle or {}).get("target_audience") or profile.get("target_audience") or "",
            "app_feature": (angle or {}).get("app_feature") or "",
            "required_assets": tpl.get("required_assets") or [],
            "suggested_duration": tpl.get("default_duration") or template_library.DEFAULT_DURATION,
            "limitations": result["limitations"],
            "feedback": result["feedback"],
        })
    scored.sort(key=lambda r: (-r["score"], r["template"]["name"]))
    return {
        "recommendations": scored[: max(1, min(int(limit or 8), 30))],
        "angle": _serialize_angle_row(angle) if angle else None,
        "objective": norm_objective,
    }


@api_router.post("/app-profiles/{profile_id}/objective-templates")
async def ensure_objective_templates(
    profile_id: str, payload: ObjectiveTemplatesRequest, user_id: str = Depends(get_current_user_id)
):
    """
    Tailored templates for this profile AND the founder's selected objective.

    The objective is chosen per video in the wizard — it does not exist at
    approve time — so generation lives here, called when the template step
    loads with both profile and objective set. A cached set returns
    immediately without a model call; otherwise the set generates
    synchronously (same in-request precedent as strategy and plan builds)
    and replaces any previous set for that (profile, objective) key.

    Never 500s on a model failure: the previous set (or an empty list)
    returns with the error attached, and the curated picks keep working.
    """
    profile = await _require_profile_for_studio(profile_id, user_id)
    want_objective = template_library.normalize_objective(
        (payload.objective if payload else "") or "")
    if not want_objective:
        raise HTTPException(
            status_code=400,
            detail="Pick an objective first — tailored templates are generated per objective.",
        )
    existing = await _fetch_all(
        """SELECT * FROM hook_templates
           WHERE brand_profile_id = ? AND objective = ? AND user_id = ?
             AND archived = 0 AND review_status = 'approved'""",
        (profile_id, want_objective, user_id),
    )
    # Regenerate means regenerate: an explicit ask replaces the set even
    # when one exists. Anything else serves the cache without a model call.
    if existing and not (payload.regenerate or False):
        return {
            "templates": [_public_library_template(t) for t in existing],
            "generated": False,
            "objective": want_objective,
            "error": None,
        }
    try:
        drafts = await _ensure_objective_templates(profile, want_objective, user_id)
    except Exception as e:  # defensive: _ensure already swallows model errors
        logger.error(f"Objective template generation failed: {e!r}")
        drafts = []
    rows = await _fetch_all(
        """SELECT * FROM hook_templates
           WHERE brand_profile_id = ? AND objective = ? AND user_id = ?
             AND archived = 0 AND review_status = 'approved'""",
        (profile_id, want_objective, user_id),
    )
    return {
        "templates": [_public_library_template(t) for t in rows],
        "generated": bool(drafts),
        "objective": want_objective,
        "error": None if drafts else (
            "Tailoring failed — the curated picks below still work. "
            "Reopening this step retries."
        ),
    }


# ---------------------------------------------------------------------------
# Studio projects (guided creation workflow)
# ---------------------------------------------------------------------------
def _two_section_repairs(row: dict) -> dict:
    """
    The columns on a project that predate one-render generation, brought into range.

    A project saved by the previous version can carry a 20s or 30s target and a
    hook length of 5. Neither is reachable now: a piece is one render, so a 20s
    target cannot be produced at all and would be refused at the generate
    endpoint, and 5s is a second past the longest a hook has to land in.

    Returns only the keys that need moving, so a caller can tell "nothing to do"
    from "a length was clamped", and can write just the column that changed. A
    project within range returns {}.
    """
    repairs: dict = {}
    stored_duration = int(row.get("duration_seconds") or 0)
    if stored_duration > template_library.MAX_SUPPORTED_DURATION:
        repairs["duration_seconds"] = template_library.clamp_duration(stored_duration)
    stored_hook = int(row.get("hook_seconds") or 0)
    if stored_hook and not (
        template_library.MIN_HOOK_SECONDS <= stored_hook <= template_library.MAX_HOOK_SECONDS
    ):
        repairs["hook_seconds"] = max(
            template_library.MIN_HOOK_SECONDS,
            min(template_library.MAX_HOOK_SECONDS, stored_hook),
        )
    return repairs


def _public_project(row: dict, brand_name: str = "") -> dict:
    """Serialize a studio project with its structured fields parsed.

    `brand_name` is the app's own name, when the caller already has the profile.
    It is the one thing the spoken lines can be checked against that is not
    knowable from the project row, so `_public_project` accepts it rather than
    reading the profile again: the check below reports whether the customer's
    own line names the product. Callers without a profile in hand leave it
    empty and the flag is simply not set — the row never carried a name, and
    adding one column to pin it was not worth a migration.
    """
    out = dict(row)
    out["beat_timeline"] = out.get("beat_timeline") or []
    out["overlays"] = out.get("overlays") or []
    out["assets"] = out.get("assets") or []
    out["safety_report"] = out.get("safety_report") or None
    out["duration_seconds"] = out.get("duration_seconds") or 0
    out["script_version"] = out.get("script_version") or 0
    out["hook_seconds"] = int(out.get("hook_seconds") or 0)
    out["strategy_version"] = int(out.get("strategy_version") or 0)
    # Which script the strategy was built from, and whether the script has moved
    # on since. 0 on both sides means either side predates the other, which is
    # not a mismatch — it is missing history, and the founder is not blocked for
    # it. The studio reads `strategy_is_current` to warn before generating
    # rather than to refuse silently.
    built_from = int(out.get("strategy_script_version") or 0)
    current_script = int(out.get("script_version") or 0)
    out["strategy_script_version"] = built_from
    out["strategy_is_current"] = not (built_from and current_script and built_from != current_script)
    # Bring a pre-two-section project forward on read, so an old draft is not
    # silently unrenderable.
    #
    # A project saved by the previous version can carry a 20s or 30s target and a
    # hook length of 5. Both are now out of range: the piece is one render, so a
    # 20s target cannot be produced at all and would be refused at the generate
    # endpoint, and 5 is a second past the longest a hook has to land in. Reporting
    # the stored value would show the founder a length the studio will refuse, so
    # the clamped value is written back and returned. Persisted, not just
    # recomputed per response, so the plan they already approved and the value the
    # render reads agree.
    out.update(_two_section_repairs(row))
    # A strategy parsed out of its JSON column, or {} when the project has none.
    # The render reads this to decide whether the video is app-specific or falls
    # back to the plan alone.
    strategy = out.get("strategy")
    if isinstance(strategy, str):
        try:
            strategy = json.loads(strategy)
        except (json.JSONDecodeError, TypeError):
            strategy = {}
    out["strategy"] = strategy if isinstance(strategy, dict) else {}
    # How much of the approved script cannot be spoken in the middle's seconds.
    # Recomputed, never stored: it is a pure function of (plan, seconds), so a
    # hand-edited strategy cannot drop it and the founder edits that change the
    # answer are reflected immediately. Empty when everything fits — or when
    # there is nothing to speak.
    plan_words = {
        "hook_line": out.get("hook_line"),
        "script": out.get("script"),
    }
    if (plan_words["hook_line"] or plan_words["script"]) and out["strategy"]:
        _bound, overflow = bind_spoken_words(
            dict(out["strategy"]),
            plan_words,
            out.get("hook_seconds") or 3,
            out.get("duration_seconds") or 0,
        )
        out["spoken_overflow"] = overflow
        # The middle's spoken words, exactly as the render will receive them.
        # The Review step shows this partition and trims to it, so it has to be
        # the bound text rather than a second implementation of the rule.
        _sections = _bound.get("segments") or []
        out["spoken_middle"] = (
            _sections[1].get("script", "")
            if len(_sections) > 1 and isinstance(_sections[1], dict)
            else ""
        )
    else:
        out["spoken_overflow"] = {}
        out["spoken_middle"] = ""
    # Both spoken lines counted against the lengths they aim at, and read as one
    # story: the measurement the render path acts on before it builds a prompt,
    # reported here so the founder sees the same numbers the render will. A pure
    # function of (plan, seconds), so it is recomputed rather than stored — a
    # hand-edited script or a changed hook length is reflected immediately.
    out["spoken_check"] = ai_service.check_spoken_story(
        out.get("hook_line"),
        out.get("script"),
        out.get("hook_seconds") or 3,
        out.get("duration_seconds") or 0,
        # Whether the customer's own line names the product is measurable, and
        # it is the one promotion the prompt cannot reliably police: it depends
        # on the app's name, which the project row does not carry -- so it is
        # passed in by the callers that already fetched the profile, and is
        # absent everywhere it is not knowable.
        app_name=brand_name,
    )
    # What the arrival clamp cut from this plan, and the budget it cut against.
    # Reported from the stored count rather than recomputed from the script,
    # because after the clamp the stored script fits by construction: the count
    # is the only record that anything was removed.
    trimmed = int(out.get("plan_trimmed_chars") or 0)
    if trimmed:
        middle_seconds = max(1, (out.get("duration_seconds") or 0) - (out.get("hook_seconds") or 3))
        out["plan_trim"] = {
            "dropped_chars": trimmed,
            "middle_seconds": middle_seconds,
            "budget": spoken_budget(middle_seconds),
        }
    else:
        out["plan_trim"] = {}
    return out


def _project_strategy(project: dict) -> dict:
    """The project's strategy dict, parsed, or {} when it has none.

    A project row carries `strategy` as a JSON string, so every reader would
    otherwise repeat the same parse-and-discard-on-error. An unparseable value
    is treated as no strategy rather than crashing a real render: the fallback
    path produces a working video from the plan, and a hard failure here would
    strand a project the founder has already paid to review.
    """
    strategy = (project or {}).get("strategy")
    if isinstance(strategy, dict):
        return strategy
    if not strategy:
        return {}
    try:
        parsed = json.loads(strategy)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


async def _require_profile_for_studio(profile_id: str, user_id: str) -> dict:
    """
    Load a profile and enforce that it is APPROVED.

    Every studio step funnels through here. Generating a script from an
    unreviewed profile would let unverified AI research invent features and
    claims, which is exactly what the approval gate exists to prevent.
    """
    profile = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")
    if profile.get("status") != "approved":
        raise HTTPException(
            status_code=409,
            detail="Review and approve this App Profile before creating a video plan.",
        )
    return profile


@api_router.get("/studio/projects")
async def list_studio_projects(
    brand_profile_id: str = "", limit: int = 50, user_id: str = Depends(get_current_user_id)
):
    """Creation drafts for this user, most recently updated first."""
    clauses = ["user_id = ?"]
    params: list = [user_id]
    if brand_profile_id.strip():
        clauses.append("brand_profile_id = ?")
        params.append(brand_profile_id.strip())
    rows = await _fetch_all(
        f"""SELECT * FROM studio_projects WHERE {' AND '.join(clauses)}
            ORDER BY updated_at DESC LIMIT ?""",
        tuple(params) + (max(1, min(int(limit or 50), 200)),),
    )
    await _backfill_two_section_projects(rows)
    return {"projects": [_public_project(r) for r in rows]}


async def _backfill_two_section_projects(rows: list) -> None:
    """
    Persist the clamp `_public_project` reports, for rows a previous version wrote.

    `_public_project` already returns a clamped `duration_seconds` and
    `hook_seconds` for a project that predates one-render generation, and sets a
    private flag when it had to. This writes those values back, so a 20s project
    is stored as the 12s it can actually be rendered at.

    Without the write, the clamp is cosmetic: the founder sees 15s, the plan's
    beat timeline was written to 20s, and the render reads 20 off the row and is
    refused by the single-pass ceiling. The two would disagree in the one place
    a founder is about to pay.

    Each row is repaired in place as well as written, because the caller's row
    object is what gets serialized afterwards — patching only the database would
    leave the response showing the unrepaired values.
    """
    for row in rows:
        repairs = _two_section_repairs(row)
        if not repairs:
            continue
        await _execute(
            "UPDATE studio_projects SET duration_seconds = ?, hook_seconds = ?,"
            " updated_at = ? WHERE id = ? AND user_id = ?",
            (
                int(repairs.get("duration_seconds", row.get("duration_seconds")) or 0),
                int(repairs.get("hook_seconds", row.get("hook_seconds")) or 0),
                now_iso(),
                row.get("id"),
                row.get("user_id"),
            ),
        )
        # Keep the caller's row consistent with what was just written.
        row.update(repairs)


@api_router.post("/studio/projects", status_code=201)
async def create_studio_project(
    payload: CreateStudioProjectRequest, user_id: str = Depends(get_current_user_id)
):
    """Create a creation draft against an APPROVED App Profile."""
    profile = await _require_profile_for_studio(payload.brand_profile_id, user_id)

    template_id = (payload.template_id or "").strip()
    template_version = None
    template = None
    duration = payload.duration_seconds
    if template_id:
        template = await _fetch_one(
            "SELECT * FROM hook_templates WHERE id = ? AND (user_id = ? OR user_id = 'system')",
            (template_id, user_id),
        )
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        # Check review_status directly: `is_usable` is a computed field that
        # only exists on a serialized template, so testing it against a raw
        # row silently passed and let unpublished drafts through.
        if (template.get("review_status") or "approved") != "approved":
            raise HTTPException(
                status_code=409,
                detail="This template is an unpublished research draft. Review and "
                       "publish it before using it.",
            )
        # Pin the version now so later library edits cannot change this project.
        template_version = template.get("version")
        if not duration:
            duration = template.get("default_duration")

    duration = template_library.clamp_duration(duration or template_library.DEFAULT_DURATION)

    project_id = str(uuid.uuid4())
    now = now_iso()
    # The opening section's length, from the template. DIRECTORIAL, not a render
    # length: the whole piece is one render, and this is where the hook stops and
    # the middle begins. Clamped to 2-4s because a hook that needs longer to land
    # is not a hook.
    hook_seconds = int(payload.hook_seconds or 0)
    if not hook_seconds and template:
        hook_seconds = int(template.get("hook_seconds") or 0)
    hook_seconds = max(
        template_library.MIN_HOOK_SECONDS,
        min(template_library.MAX_HOOK_SECONDS, hook_seconds or 3),
    )

    # extend_intent is gone. The column stays (SQLite cannot cheaply drop it and
    # existing rows carry a value) but is written as 1 and read by nothing: a
    # video is one render, so there is no "hook only" mode to record.

    await _execute(
        """INSERT INTO studio_projects
           (id, brand_profile_id, content_angle_id, template_id, template_version,
             objective, audience, duration_seconds, hook_seconds, extend_intent, tone, assets,
             script_version, status, created_at, updated_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (project_id, profile["id"], (payload.content_angle_id or "").strip() or None,
         template_id or None, template_version,
         template_library.normalize_objective(payload.objective),
         (payload.audience or profile.get("target_audience") or "").strip() or None,
         duration, hook_seconds, 1, (payload.tone or "").strip() or None,
         json.dumps([]), 0, "draft", now, now, user_id),
    )
    logger.info(f"Created studio project {project_id} for profile {profile['id']}")
    return _public_project(
        await _fetch_one("SELECT * FROM studio_projects WHERE id = ?", (project_id,)),
        brand_name=(profile.get("brand_name") or "").strip(),
    )


@api_router.get("/studio/projects/{project_id}")
async def get_studio_project(project_id: str, user_id: str = Depends(get_current_user_id)):
    row = await _fetch_one(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?", (project_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Studio project not found")
    # A project from before one-render generation is brought forward here, so
    # reopening it is what repairs it — see _backfill_two_section_projects.
    await _backfill_two_section_projects([row])
    return _public_project(row)


@api_router.patch("/studio/projects/{project_id}")
async def update_studio_project(
    project_id: str, payload: UpdateStudioProjectRequest, user_id: str = Depends(get_current_user_id)
):
    """
    Edit a draft. This is the founder's review step, so every generated field
    is editable and editing bumps script_version so a later generation can be
    traced to the exact text that was approved.

    Re-running claim safety on every edit is deliberate: a founder could
    otherwise paste a prohibited claim into the script field and generate.
    """
    row = await _fetch_one(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?", (project_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Studio project not found")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return _public_project(row)
    updates = {k: v for k, v in updates.items() if k in STUDIO_EDITABLE_FIELDS}
    if not updates:
        return _public_project(row)

    set_clauses, values = [], []
    strategy_edited = False
    # Whether a content field's WRITTEN value actually changed. The background
    # draft sync resends tone/objective/template on every selection change, so
    # bumping on key presence alone minted phantom "Plan v1/v2..." versions
    # with blank fields: Review then saw script_version > 0, concluded a plan
    # existed, and never auto-generated — a blank form only a manual
    # regenerate could recover. Presence is not a change; compare the
    # normalized value about to be stored against the stored row.
    content_changed = False
    _CONTENT_KEYS = set(STUDIO_TEXT_FIELDS) | {"beat_timeline", "assets", "strategy"}
    for key, value in updates.items():
        if key in ("beat_timeline", "assets"):
            value = json.dumps(value if isinstance(value, list) else [])
        elif key == "strategy":
            # A hand-edited strategy is re-validated and version-bumped, the
            # same as a generated one. Bumping the version is what stops a
            # later extension from being built against a strategy the founder
            # has since changed underneath an already-approved hook.
            existing = row.get("strategy") or {}
            if isinstance(existing, str):
                try:
                    existing = json.loads(existing)
                except (json.JSONDecodeError, TypeError):
                    existing = {}
            if not isinstance(value, dict):
                value = existing if isinstance(existing, dict) else {}
            value = normalize_strategy({**existing, **value} if isinstance(existing, dict) else value)
            set_clauses.append("strategy_version = strategy_version + 1")
            strategy_edited = True
            value = json.dumps(value)
        elif key in ("template_id", "content_angle_id"):
            value = (value or "").strip() or None
        elif key == "objective":
            value = template_library.normalize_objective(value)
        elif key == "duration_seconds":
            value = template_library.clamp_duration(value)
            # The plan's beat timeline is built for the length the plan was
            # generated at, and _normalize_beats clamps every beat to that
            # length. So changing the duration on a project that already has a
            # plan leaves a timeline that no longer adds up to the stated
            # runtime — and nothing in the UI could tell the founder, because
            # the shot timeline is displayed read-only.
            #
            # The length is chosen on the Audience & goal step and consumed by
            # the plan step, which writes it in the same statement as the beats
            # it clamped to it. Changing it means regenerating the plan, and
            # that is the only honest way to get a timeline that fits.
            if (
                int(row.get("script_version") or 0) > 0
                and int(value or 0) != int(row.get("duration_seconds") or 0)
            ):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"This project already has a script written to "
                        f"{int(row.get('duration_seconds') or 0)}s, and its shot timeline is "
                        f"built to that length. Change the total length on the Audience & goal "
                        f"step and regenerate the plan, which rewrites the timeline to match."
                    ),
                )
        elif key == "hook_seconds":
            # Where the middle begins. Directorial, not a render length: the whole
            # piece is one render. 0 means "follow the template", and anything out
            # of range is clamped rather than refused — a hand-typed 9s here would
            # leave the middle with nothing to film, which is a worse outcome than
            # moving the boundary to a length a hook can actually land in.
            try:
                want = int(value or 0)
            except (TypeError, ValueError):
                want = 0
            value = (
                max(
                    template_library.MIN_HOOK_SECONDS,
                    min(template_library.MAX_HOOK_SECONDS, want),
                )
                if want
                else 0
            )
        elif value is not None:
            value = str(value).strip()
        set_clauses.append(f"{key} = ?")
        values.append(value)
        if key in _CONTENT_KEYS:
            new_norm = (
                "" if value is None
                else (value if isinstance(value, str) else json.dumps(value, sort_keys=True))
            )
            old_raw = row.get(key)
            old_norm = (
                "" if old_raw is None
                else (old_raw if isinstance(old_raw, str) else json.dumps(old_raw, sort_keys=True))
            )
            if new_norm != old_norm:
                content_changed = True

    if "template_id" in updates and updates["template_id"]:
        tpl = await _fetch_one(
            "SELECT version FROM hook_templates WHERE id = ? AND (user_id = ? OR user_id = 'system')",
            (updates["template_id"], user_id),
        )
        if not tpl:
            raise HTTPException(status_code=404, detail="Template not found")
        set_clauses.append("template_version = ?")
        values.append(tpl.get("version"))

    # Re-check claims against the profile after any edit.
    profile = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ?", (row.get("brand_profile_id"),)
    )
    if profile:
        merged = dict(row)
        for key, value in updates.items():
            if key in ("beat_timeline", "assets"):
                merged[key] = value if isinstance(value, list) else []
            elif key == "strategy":
                # Already serialized above; claim checking walks the structure,
                # so give it the dict rather than the JSON string.
                try:
                    merged[key] = json.loads(value) if isinstance(value, str) else (value or {})
                except (json.JSONDecodeError, TypeError):
                    merged[key] = {}
            else:
                merged[key] = value
        report = claim_safety.build_safety_report(merged, profile)
        set_clauses.append("safety_report = ?")
        values.append(json.dumps(report))
        set_clauses.append("safety_summary = ?")
        values.append(claim_safety.summarize(report))

    # script_version tracks the WRITTEN content, so only a content edit that
    # actually changes a value bumps it. It previously bumped on key presence
    # alone — resending an unchanged tone minted phantom versions with blank
    # fields (see content_changed above) — and before that on every edit at
    # all, which meant a preference change such as the extend-intent toggle or
    # the hook length looked like a rewrite.
    if content_changed:
        set_clauses.append("script_version = ?")
        values.append(int(row.get("script_version") or 0) + 1)
        # A content edit un-readies the project.
        #
        # Without this, a founder who had already marked a project ready could
        # rewrite the hook line, beat timeline or strategy, save, and spend again
        # immediately -- the studio never asked them to look at the revision they
        # had just written. It also left the Mark-ready button permanently
        # disabled, because the status never left ready_for_generation, so there
        # was no way to re-review at all.
        #
        # The approval being withdrawn is the one the founder gave to the PREVIOUS
        # text. The edit is not the review step: plan regeneration and Mark-ready
        # are, and both are still available from the studio.
        if row.get("status") == "ready_for_generation":
            set_clauses.append("status = ?")
            values.append("draft")
            logger.info(
                "Project %s was ready for generation; a content edit returned it to draft",
                project_id,
            )
    set_clauses.append("updated_at = ?")
    values.append(now_iso())
    values.extend([project_id, user_id])
    await _execute(
        f"UPDATE studio_projects SET {', '.join(set_clauses)} "
        "WHERE id = ? AND user_id = ?",
        tuple(values),
    )
    return _public_project(
        await _fetch_one("SELECT * FROM studio_projects WHERE id = ?", (project_id,))
    )


@api_router.post("/studio/projects/{project_id}/plan")
async def generate_plan(
    project_id: str, payload: GeneratePlanRequest, user_id: str = Depends(get_current_user_id)
):
    """
    Generate (or regenerate) the creative plan for a project.

    Gated twice on purpose:
      1. The App Profile must be approved.
      2. A template must be chosen, since the template supplies the creative
         structure the plan adapts.

    The claim-safety report is computed here and stored. A plan that trips a
    banned claim is still RETURNED — the founder can see and fix it — but the
    report marks it failed so Phase 5 generation refuses to run it.
    """
    require_ai_configured()
    row = await _fetch_one(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?", (project_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Studio project not found")

    profile = await _require_profile_for_studio(row.get("brand_profile_id"), user_id)

    if not row.get("template_id"):
        raise HTTPException(
            status_code=400,
            detail="Choose a hook template before generating a plan.",
        )
    template = await _fetch_one(
        "SELECT * FROM hook_templates WHERE id = ? AND (user_id = ? OR user_id = 'system')",
        (row["template_id"], user_id),
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    angle = None
    if row.get("content_angle_id"):
        angle = await _fetch_one(
            "SELECT * FROM content_angles WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
            (row["content_angle_id"], row.get("brand_profile_id"), user_id),
        )
        if not angle:
            raise HTTPException(
                status_code=404, detail="Content angle not found for this App Profile"
            )

    objective = template_library.normalize_objective(
        payload.objective or row.get("objective") or ""
    )
    duration = template_library.clamp_duration(
        payload.duration_seconds or row.get("duration_seconds")
    )
    tone = (payload.tone or row.get("tone") or "").strip()

    # The same explicit history that moves recommendations also constrains the
    # next draft. Only counts and fixed reason codes travel into the prompt;
    # free-text detail never does.
    profile_feedback = feedback_mod.summarize_profile_feedback(
        await _fetch_all(
            "SELECT event, signal, reason, template_id FROM feedback_events "
            "WHERE brand_profile_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 200",
            (row.get("brand_profile_id"), user_id),
        ),
        template.get("id") or "",
    )
    plan_feedback = await _component_feedback_for_profile(
        row.get("brand_profile_id"), user_id, "plan")
    try:
        plan = await _log_model_call(
            "creative_plan", "text", TEXT_MODEL,
            lambda: generate_creative_plan(
                profile=profile,
                # Draft to the SAME opening length used by storage and render.
                # A project override used to reach only the arrival clamp, so
                # a 4s draft could be cut again to a 3s sentence fragment.
                template={**template, "hook_seconds": int(row.get("hook_seconds") or 3)},
                angle=angle,
                objective=objective,
                duration_seconds=duration,
                tone=tone,
                # The founder's own words for this render. A regeneration
                # ignored all three and could answer a different audience with a
                # different look than the one on the project, which is the plan
                # overwriting their decisions instead of drafting the script.
                audience=(payload.audience or row.get("audience") or "").strip(),
                visual_direction=(row.get("visual_direction") or "").strip(),
                brand_voice=(profile.get("tone_voice") or "").strip(),
                profile_feedback=profile_feedback,
                component_feedback=plan_feedback,
            ),
            user_id,
            brand_profile_id=row.get("brand_profile_id"),
            studio_project_id=project_id,
            template_id=template.get("id"),
        )
    except Exception as e:
        logger.error(f"Creative plan generation failed for project {project_id}: {e}")
        raise HTTPException(status_code=502, detail=f"AI plan generation failed. Please try again. ({str(e)[:150]})")

    # The real plan generator now validates and editorially rewrites oversized
    # drafts before returning them, using this project's exact hook length.
    # Such drafts pass this legacy partition unchanged: it remains for old
    # whole-piece callers that include a duplicate hook at the script's head.
    # Claim safety and storage must see the same accepted spoken words.
    #
    # hook_seconds and total_seconds are passed exactly as _require_spoken_words_fit
    # passes them. A clamp that assumed a different section split would produce
    # a plan the gate still calls over-length.
    clamp = ai_service.partition_spoken_words(
        plan, int(row.get("hook_seconds") or 3), duration
    )
    # The hook's own cut counts here too: a hook line longer than its opening
    # beat is sized back by the same rule, and what comes off it is spoken at
    # the head of the middle rather than dropped. Either way the founder is
    # told, because a shorter opening line than the model wrote otherwise reads
    # as the studio losing words.
    trimmed_chars = int(clamp["dropped_chars"] or 0) + int(clamp["hook_dropped_chars"] or 0)
    if trimmed_chars or clamp["middle_text"] != (plan.get("script") or "").strip():
        # `script` is stored as the MIDDLE only. The prompt asks the model for
        # the whole piece, which is right for the words and wrong for the
        # field: the hook line is already its own column, so keeping a copy at
        # the head of the script showed the founder the same sentence twice on
        # Review and left them unable to tell what the middle would actually
        # say. Stored this way, the two boxes hold one sentence between them and
        # the renderer reads the middle as-is.
        #
        # The hook survives in hook_line, and bind_spoken_words still binds it
        # into the strategy's opening section, so nothing is dropped from the
        # video -- it is simply written once.
        fitted = dict(plan)
        fitted["hook_line"] = clamp["hook_line"]
        fitted["script"] = clamp["kept"]
        plan = fitted
        logger.info(
            f"Plan for project {project_id} was {trimmed_chars} characters over the "
            f"{clamp['middle_seconds']}s spoken budget ({clamp['budget']}); trimmed on arrival"
        )

    report = claim_safety.build_safety_report(plan, profile)
    summary = claim_safety.summarize(report)

    now = now_iso()
    # `cta` is no longer written: a call to action is the founder's own, added in
    # their editor after the demo they record. `feature_emphasis` is replaced by
    # `demo_brief` — the founder still needs to know what to record for their own
    # demo, so the plan works it out, but it is deliberately never passed to a
    # render. Both old columns stay in the schema; nothing reads them.
    # `overlays` joins them: burned-in captions are gone, so a fresh plan
    # always clears the column (legacy rows may still carry text, which nothing
    # renders anymore).
    await _execute(
        """UPDATE studio_projects SET
             hook_line = ?, script = ?, beat_timeline = ?, visual_direction = ?,
             demo_brief = ?, overlays = ?, voice_direction = ?, sound_direction = ?,
             safety_report = ?, safety_summary = ?, objective = ?,
             duration_seconds = ?, tone = ?, script_version = script_version + 1,
             plan_trimmed_chars = ?,
             status = 'draft', updated_at = ?
           WHERE id = ? AND user_id = ?""",
        (plan["hook_line"], plan["script"], json.dumps(plan["beat_timeline"]),
         plan["visual_direction"], plan["demo_brief"], json.dumps([]),
         plan["voice_direction"], plan["sound_direction"],
         json.dumps(report), summary, objective, duration, tone or None,
         trimmed_chars, now, project_id, user_id),
    )
    logger.info(
        f"Generated plan for project {project_id} (script v{int(row.get('script_version') or 0) + 1}) — {summary}"
    )
    return _public_project(
        await _fetch_one("SELECT * FROM studio_projects WHERE id = ?", (project_id,)),
        brand_name=(profile.get("brand_name") or "").strip(),
    )


@api_router.post("/studio/projects/{project_id}/ready")
async def mark_project_ready(project_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Mark a reviewed project ready for video generation.

    Refuses while the claim-safety report is failing, so a prohibited claim
    cannot be waved through. This is the last gate before Phase 5 renders.

    The verdict is recomputed against the live App Profile and written back,
    rather than read from the row. The stored copy was computed when the plan was
    written; if the founder has since added a claim to claims_banned, approving
    on the stale "passed" would show them a green SafetyPanel and then block at
    the generate button, which reads as a bug rather than a rule. Recomputing
    here keeps the panel and the spend gate telling the same story.
    """
    row = await _fetch_one(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?", (project_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Studio project not found")
    if not (row.get("script") or "").strip():
        raise HTTPException(
            status_code=400, detail="Generate or write a script before marking this ready."
        )
    if not row.get("template_id"):
        raise HTTPException(status_code=400, detail="Choose a hook template first.")

    # Every template that puts a person on camera needs the founder's
    # photograph. This was enforced only at the generate endpoint, which is the
    # wrong place: marking ready is what enables the Generate button, so a
    # project with no photo sailed through approval, showed an enabled button,
    # and only refused at the click -- reading as the app breaking rather than a
    # rule the founder had not met yet.
    #
    # Checked here so the founder is stopped at the step that can still fix it,
    # with the photo already attachable on the step the message names. The
    # generate endpoint keeps its own check: this one is about the button, that
    # one is about never spending on a model inventing a presenter.
    anchors = [
        a for a in (row.get("assets") or [])
        if isinstance(a, dict)
        and str(a.get("kind") or "").strip().lower() == "character_reference"
    ]
    if not anchors:
        template = await _fetch_one(
            "SELECT required_assets FROM hook_templates WHERE id = ?", (row["template_id"],)
        )
        required = [
            str(a or "").strip().lower()
            for a in ((template or {}).get("required_assets") or [])
        ]
        if "character_reference" in required:
            raise HTTPException(
                status_code=400,
                detail=(
                    "This template puts a person on camera, so it needs a character "
                    "reference. The video is generated from your photograph, so "
                    "without one the model would invent someone who looks nothing "
                    "like you. Attach a character reference on the Template & photo "
                    "step, then mark this ready again."
                ),
            )

    # The objective is what the whole creative job is for, and it steers the
    # plan, the strategy and which templates even rank. The wizard requires it,
    # but that was a client-side check only: a direct caller could approve and
    # spend on a project with no stated objective, and the plan fell back to
    # whatever the template scored. Enforced here so it holds for every path
    # that can spend, not just the one the browser takes.
    if not template_library.normalize_objective(row.get("objective")):
        raise HTTPException(
            status_code=400,
            detail=(
                "Choose what this video is for on the Audience & goal step before "
                "marking it ready. It decides the hook, the plan and which templates "
                "fit."
            ),
        )

    profile = await _require_profile_for_studio(row.get("brand_profile_id"), user_id)
    report = _require_claims_clear(row, profile)

    await _execute(
        "UPDATE studio_projects SET status = 'ready_for_generation', safety_report = ?, "
        "safety_summary = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (json.dumps(report), claim_safety.summarize(report), now_iso(), project_id, user_id),
    )
    return _public_project(
        await _fetch_one("SELECT * FROM studio_projects WHERE id = ?", (project_id,)),
        brand_name=(profile.get("brand_name") or "").strip(),
    )


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
    requested = template_library.clamp_duration(
        duration or project.get("duration_seconds") or 0
    )
    model_key = video_providers.resolve(model)[0]
    cap = video_providers.capability(model_key)
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
    # Each provider has its own prompt ceiling. Hailuo's was measured live at
    # 7,000; others are lower, and sending them a Hailuo-sized prompt 400s
    # after the founder has asked for it. The builder scales every field
    # budget to fit rather than cutting the finished tail. On a tight ceiling
    # the spoken script is additionally sacred: the ceiling tripped the
    # protection withdrawal on ordinary strategies, so only the direction and
    # template wording is trimmed there, never the founder's own words.
    prompt_budget = video_providers.capability(model_key).get("prompt_char_limit")
    if strategy:
        prompt = generation_planning.build_segment_prompt(
            strategy=strategy,
            profile=profile,
            template=template,
            duration=seconds,
            assets=project.get("assets") or [],
            plan=render_plan,
            prompt_budget=prompt_budget,
            script_sacred=video_providers.script_is_sacred(model_key),
        )
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
    if prompt_budget and len(prompt) > prompt_budget:
        raise HTTPException(
            status_code=409,
            detail=(
                f"This script and photo produce a {len(prompt)}-character prompt, over "
                f"the {prompt_budget} {video_providers.capability(model_key).get('name', '')} "
                f"accepts. Shorten the script or the app's own wording, or pick another "
                f"model — nothing has been charged."
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

    try:
        await _execute(
            """INSERT INTO generations
           (id, studio_project_id, brand_profile_id, template_id, template_version,
            script_version, model, model_id, requested_duration, duration, status,
            segment_role, segment_index, strategy_version, continuity, trim_to_seconds,
            attempt, prompt_used, adjustments, retryable, approved,
            requested_at, created_at, updated_at, user_id, idempotency_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?, ?, ?, ?)""",
        (generation_id, project["id"], project.get("brand_profile_id"),
         project.get("template_id"), project.get("template_version"),
         project.get("script_version"), model_key, cap["id"],
         requested, seconds, segment_role, int(segment_index or 0), strategy_version,
         json.dumps(continuity) if continuity else None, trim_to_seconds,
         attempt, prompt, json.dumps([]), now, now, now, user_id,
         claim_key or None),
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


@api_router.get("/studio/video-models")
async def list_studio_video_models():
    """
    Provider capabilities for the studio.

    Distinct from the legacy /api/video-models used by the exact-match flow:
    this one reports what the template workflow can actually drive, including
    single-pass duration limits that decide whether a second job is needed.
    """
    default_key = video_providers.default_model_key()
    return {
        "default": default_key,
        "models": video_providers.list_capabilities(),
        "ineligible": [
            c for c in video_providers.list_capabilities(include_ineligible=True)
            if not c.get("studio_eligible")
        ],
    }


@api_router.get("/generations")
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


@api_router.get("/generations/{generation_id}")
async def get_generation(generation_id: str, user_id: str = Depends(get_current_user_id)):
    row = await _fetch_one(
        "SELECT * FROM generations WHERE id = ? AND user_id = ?", (generation_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")
    return await _with_verdicts(_public_generation_detail(row), user_id)


def health_database_report(active_backend: str | None) -> dict:
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


@api_router.get("/health")
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
    counts below on purpose: `get_db` re-establishes `_ACTIVE_BACKEND` on every
    connection, so the value that matters is the store THIS request just used,
    not whatever the previous one happened to leave behind.

    The counts are the other half — "ephemeral, and empty" and "ephemeral, and
    holding 40 generations" need different responses, and only the numbers
    distinguish them. Scoped to the caller's own rows so this cannot be used to
    size up another account.

    Authenticated, because it reports inventory. A founder can read it from the
    browser console while signed in; an anonymous visitor learns nothing.
    """
    counts = {}
    for table in ("brand_profiles", "studio_projects", "generations"):
        try:
            row = await _fetch_one(
                f"SELECT COUNT(*) AS n FROM {table} WHERE user_id = ?", (user_id,)
            )
            counts[table] = int((row or {}).get("n") or 0)
        except Exception as exc:  # a missing table is itself the answer
            counts[table] = f"unavailable: {type(exc).__name__}"
    return {"status": "ok", **health_database_report(_ACTIVE_BACKEND), "your_rows": counts}


# --- Native Product Demo + CTA export ----------------------------------------
#
# The editor lives inside HookForge, on the same origin. There is no popup,
# redirect, new tab, iframe, opener, postMessage, or cross-app link: the
# completed Hook + Story generation is the editor's input, and the exported
# file is saved here as a child generation beside the original.
#
# This is storage, not generation. No model is called, nothing is submitted
# upstream, and it does not touch the ready/claim gates — those guard a paid
# render, and this is the founder saving a file they just exported. It
# therefore cannot spend anything, which is why it is safe to leave off every
# gate.


@api_router.post("/generations/{generation_id}/demo-cta-result", status_code=201)
@api_router.post("/demo-cta-result", status_code=201)
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
    parent = None
    if generation_id:
        parent = await _fetch_one(
            "SELECT id, studio_project_id, brand_profile_id, template_id, template_version, "
            "script_version, duration, model, model_id, segment_role, segment_index, "
            "strategy_version FROM generations WHERE id = ? AND user_id = ?",
            (generation_id, user_id),
        )
        if not parent:
            raise HTTPException(status_code=404, detail="Generation not found")

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
    target.write_bytes(payload)

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
            prompt_used, retryable, approved,
            requested_at, completed_at, created_at, updated_at, user_id, video_url, r2_url)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed',
                   ?, ?, ?, ?, ?, 0, 1, ?, ?, ?, ?, ?, ?, ?)""",
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
            now_iso(),
            now_iso(),
            now_iso(),
            now_iso(),
            user_id,
            stored_path,
            r2_url,
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
    }


def _safety_report_for(project: dict, profile: dict) -> dict:
    """
    The claim verdict for this project as it stands RIGHT NOW.

    Every stored safety_report is a cache: it was computed at plan time, at
    strategy time, or at edit time, against the profile as it was then.
    App Profile edits deliberately do not revoke approval, so a founder can ban a
    claim on the profile months later and every previously-approved project keeps
    its old "passed" verdict cached. Reading that cache at the spend boundary
    renders the banned claim for money.

    Recomputing is deterministic and cheap, and it walks the project dict, so it
    also picks up a hook line that arrived in the strategy after the cached
    report was written.
    """
    return claim_safety.build_safety_report(project or {}, profile or {})


def _require_claims_clear(project: dict, profile: dict) -> dict:
    """Refuse a render whose live claim verdict is failing. Returns the report."""
    report = _safety_report_for(project, profile)
    if report and not report.get("passed", True):
        blocking = [b.get("claim") for b in report.get("blocking", []) if b.get("claim")]
        raise HTTPException(
            status_code=409,
            detail="Fix the wording before generating: " + ", ".join(blocking[:3]),
        )
    return report


def _require_spoken_words_fit(project: dict) -> dict:
    """
    Refuse a render whose approved script cannot be spoken within the piece.

    The middle's seconds hold a fixed number of characters; anything past that
    would be silently dropped from the words reaching the video model — and the
    tail is usually the payoff sentence. This is recomputed from the live row,
    not read from a stored verdict, for the same reason the claim verdict is:
    App Profile and plan edits must not be able to strand an approval. Returns
    the overflow record ({} when everything fits).
    """
    _bound, overflow = bind_spoken_words(
        _project_strategy(project),
        {"hook_line": (project or {}).get("hook_line"), "script": (project or {}).get("script")},
        ((project or {}).get("hook_seconds") or 3),
        ((project or {}).get("duration_seconds") or 0),
    )
    if overflow.get("dropped_chars"):
        raise HTTPException(
            status_code=409,
            detail=(
                f"{overflow['dropped_chars']} characters of your approved script do not fit "
                f"in a {overflow['middle_seconds']}s middle (spoken budget: "
                f"{overflow['budget']} characters). Regenerate the plan — it is trimmed to "
                "fit on arrival — or shorten the script on the Review step and rebuild the "
                "strategy so the spoken words come from the shorter script."
            ),
        )
    return overflow


def _require_current_strategy(project: dict) -> dict:
    """
    Refuse a render that has no app-specific strategy, or one built from a plan
    that has since been edited. Returns the strategy.

    Both used to be silent. The studio built a strategy in the browser before
    the first render, so the server never checked for one and a direct caller,
    a stale bundle, or the retry path could buy a generic take. And a plan edit
    bumped script_version without invalidating the strategy, so a founder could
    approve one plan and pay to render another -- the strategy carried the old
    hook line, the messaging and the scene lock.

    Refusing is what makes the strategy a real part of the workflow rather than
    a suggestion. Both messages name the fix, because the founder's next action
    is one click away.
    """
    strategy = _project_strategy(project)
    if not strategy:
        raise HTTPException(
            status_code=409,
            detail=(
                "This project has no video strategy yet. Build the strategy on the "
                "Hook + Story step, then generate."
            ),
        )
    built_from = int(project.get("strategy_script_version") or 0)
    current = int(project.get("script_version") or 0)
    # Both sides zero means one predates the other. That is missing history, not
    # a mismatch, and the founder is not blocked for it -- matching
    # _public_project's own reading of the same two columns.
    if built_from and current and built_from != current:
        raise HTTPException(
            status_code=409,
            detail=(
                "The plan changed after this strategy was built, so the strategy no "
                "longer describes what you reviewed. Rebuild it on the Hook + Story "
                "step, then generate."
            ),
        )
    return strategy


async def _require_renderable_project(project_id: str, user_id: str) -> tuple:
    """
    Prove a project may be rendered RIGHT NOW, and return (project, profile, template).

    Shared by the fresh-submit path and the retry path. Retry used to load the
    project, profile and template and call _submit_generation directly, which
    meant it inherited none of the checks below. A retry could therefore spend
    real money on a project that had been edited back to draft since, on an App
    Profile that was no longer approved, and past a claim block the founder had
    been shown. Retrying is not a cheaper way around the gates; it is the same
    render, so it answers to the same questions.

    The claim verdict is recomputed here rather than read from the row, because
    the row's copy is a cache computed against the profile as it was when the
    plan was last written, and App Profile edits do not revoke approval.
    """
    project = await _fetch_one(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?", (project_id, user_id)
    )
    if not project:
        raise HTTPException(status_code=404, detail="Studio project not found")
    if project.get("status") != "ready_for_generation":
        raise HTTPException(
            status_code=409,
            detail="Review the plan and mark this project ready for generation first.",
        )
    if not (project.get("script") or "").strip():
        raise HTTPException(status_code=400, detail="This project has no script to generate.")

    # _require_profile_for_studio also enforces that the profile is APPROVED,
    # which the retry path skipped entirely: it loaded the profile by id and
    # rendered against whatever state the profile happened to be in.
    profile = await _require_profile_for_studio(project.get("brand_profile_id"), user_id)
    _require_claims_clear(project, profile)

    template = await _fetch_one(
        "SELECT * FROM hook_templates WHERE id = ? AND (user_id = ? OR user_id = 'system')",
        (project.get("template_id"), user_id),
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    _require_current_strategy(project)
    # After the strategy's freshness, because a strategy built from an older
    # script is describing words this one replaces: refusing on overflow first
    # would blame the script for a strategy that is about to be invalidated
    # anyway. Without a strategy the fallback path speaks the plan verbatim,
    # so there is nothing to drop and nothing to gate.
    _require_spoken_words_fit(project)
    return project, profile, template


def _assert_model_usable(model_key: str) -> str:
    """
    Refuse an unrecognised model key instead of quietly rendering on the default.

    video_providers.resolve() falls back to Hailuo 3 with a reason string, but the
    reason is informational: without this guard a stale key would still spend a
    real render on a model the founder did not choose, and the returned clip
    would not match the model on the row. A key that is known but not allowed
    (an editor, or one outside the allowlist) still falls back with its reason,
    because that is a configuration outcome the studio already reports, not a typo.
    """
    if model_key and not video_providers.is_known(model_key):
        usable = ", ".join(c["key"] for c in video_providers.list_capabilities())
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown video model {model_key!r}. Choose one of: {usable}. "
                "Leave the model unset to use the default."
            ),
        )
    return model_key


def _assert_resolution_offered(model_key: str, resolution: str | None) -> str | None:
    """
    Refuse a render resolution the model does not offer, naming what it does.

    Only models that list supported_resolutions take the field at all: an
    unlisted value would either 400 at the provider after billing the attempt
    or, worse, silently render at the default while the founder believes they
    are testing another resolution. Omitted stays omitted — the catalog
    default applies.
    """
    if not resolution:
        return None
    cap = video_providers.capability(model_key)
    offered = cap.get("supported_resolutions") or []
    if resolution not in offered:
        allowed = ", ".join(offered) if offered else "none — this model renders at its default"
        raise HTTPException(
            status_code=400,
            detail=(
                f"{cap['name']} does not offer {resolution}. "
                f"Choose one of: {allowed}. Omit it to use the default."
            ),
        )
    return resolution


def _assert_within_single_pass_cap(model_key: str, wanted: int) -> None:
    """
    Refuse a one-pass request the model cannot fill rather than shortening it.

    The generated piece is a hook and a middle; anything longer is the founder's
    own demo, recorded separately. Silently clamping here would hand back a file
    that is not the video the plan describes, on a spend the founder approved for
    a different length.
    """
    cap = video_providers.capability(model_key)
    if int(wanted or 0) > int(cap["max_duration"]):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{cap['name']} produces at most {cap['max_duration']}s in one pass, and this "
                f"video is {int(wanted)}s. The generated piece is a hook and a middle — record "
                "anything longer as your own demo and attach it afterwards."
            ),
        )


@api_router.post("/studio/projects/{project_id}/generate", status_code=202)
async def submit_project_generation(
    project_id: str, payload: StudioGenerationRequest, user_id: str = Depends(get_current_user_id)
):
    """
    Generate the complete video as ONE job.

    Refuses unless the project is reviewed and ready, and unless the claim
    check passes, so a prohibited claim cannot reach a paid generation.

    The result is ONE clip: a hook and a middle. There is no extension, no
    per-segment approval and no join, so a request longer than a single pass is
    refused outright rather than split or silently shortened.
    """
    require_ai_configured()
    project, profile, template = await _require_renderable_project(project_id, user_id)

    # An unrecognised model key is refused rather than quietly rendered on the
    # default. See _assert_model_usable for why resolve()'s fallback reason is
    # not enough on its own.
    _assert_model_usable(payload.model or "")

    # A resolution the model does not offer is refused with the allowed
    # values, for the same reason as an unknown model key: silently rendering
    # at the default would bill a test the founder thought was at 480p.
    _assert_resolution_offered(payload.model or "", payload.resolution)

    # _require_renderable_project already proved a current strategy exists, so
    # this can only fail if the row changed underneath us. Resolving it through
    # the same helper keeps the prompt and the gate reading the same object.
    strategy = _require_current_strategy(project)

    # Computed, not requested. The template declares a length its mechanic
    # suits and the founder does not pick one, so a request longer than a single
    # pass is refused rather than quietly shortened — the founder would be
    # handed a file that is not the video the plan describes.
    wanted = payload.duration_seconds or project.get("duration_seconds") or 0
    _assert_within_single_pass_cap(video_providers.resolve(payload.model or None)[0], wanted)

    generation = await _submit_generation(
        project=project,
        profile=profile,
        template=template,
        user_id=user_id,
        model=payload.model or "",
        duration=int(wanted or 0) or None,
        generate_audio=payload.generate_audio,
        resolution=payload.resolution,
        strategy=strategy or None,
        idempotency_key=payload.idempotency_key or "",
    )
    generation["provider_reason"] = video_providers.resolve(payload.model or None)[1]
    return generation


@api_router.post("/generations/{generation_id}/poll")
async def poll_generation(
    generation_id: str,
    user_id: str = Depends(get_current_user_id),
    background_tasks: BackgroundTasks = None,
):
    """
    Refresh a generation's status and resolve a finished clip to a URL.

    Poll is the only place a completed clip is resolved to a URL and handed to
    persistent storage, so a completed generation always has a durable copy
    even if the provider's links later expire.
    """
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

            # Bake the hook-boundary camera move into the canonical file, right
            # here after the canvas resize and before the R2 upload, so the
            # preview and the download carry it -- not just captioned
            # composites, the only place it used to run (which is why changing
            # its magnitude never showed on a raw clip). Fresh downloads only,
            # like trim and rescale above: re-running it on an already-moved
            # canonical file would punch twice. Soft by design: an unmoved clip
            # is still a watchable video.
            try:
                project_row = await _fetch_one(
                    "SELECT hook_seconds, strategy FROM studio_projects WHERE id = ?",
                    (row.get("studio_project_id") or "",),
                )
                # The same beat the render prompt was given, read out of the
                # strategy rather than re-derived here -- see
                # overlays.camera_beat_seconds for why the two must not each
                # compute their own.
                move_at = overlays.camera_beat_seconds(
                    (project_row or {}).get("hook_seconds"),
                    _project_strategy(project_row or {}),
                )
            except (TypeError, ValueError):
                move_at = 0.0
            if move_at > 0:
                moved, move_warnings = await overlays.apply_camera_move(
                    local_path, move_at,
                    overlays.move_direction_for(generation_id),
                )
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


@api_router.post("/generations/{generation_id}/storage/retry")
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
    if generation_id in _storage_repairs_in_flight:
        # Not an error so much as an answer: the work is already happening, and a
        # second run would fight the first one for the same file.
        raise HTTPException(
            status_code=409,
            detail=(
                "A durable save for this render is already running. It can take a "
                "few minutes; wait for it to finish rather than starting another."
            ),
        )
    _storage_repairs_in_flight.add(generation_id)
    try:
        return await _run_storage_repair(row, generation_id, user_id, local_path, background_tasks)
    finally:
        _storage_repairs_in_flight.discard(generation_id)


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


@api_router.post("/generations/{generation_id}/retry", status_code=202)
async def retry_generation(generation_id: str, user_id: str = Depends(get_current_user_id)):
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
            status_code=409, detail="Cannot retry: this generation is not tied to a studio project."
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
                detail=(
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
    cutoff = (
        datetime.now(timezone.utc) - timedelta(seconds=max(0, int(min_age_seconds)))
    ).isoformat()
    rows = await _fetch_all(
        "SELECT id, user_id, openrouter_job_id FROM generations "
        "WHERE status IN ('submitted', 'generating') "
        "AND openrouter_job_id IS NOT NULL AND openrouter_job_id != '' "
        "AND COALESCE(created_at, requested_at, started_at) < ? "
        "ORDER BY COALESCE(created_at, requested_at, started_at) ASC LIMIT ?",
        (cutoff, max(1, int(limit))),
    )
    if not rows:
        return 0

    logger.info(
        "Stranded-render sweep: %d row(s) in flight for over %ds",
        len(rows),
        int(min_age_seconds),
    )

    fixed = 0
    for row in rows:
        generation_id = row.get("id")
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


def _current_safety_report(project: dict, profile: dict) -> dict:
    """
    Recompute the claim verdict from the project as it stands right now.

    The stored report is a cache, and the hook endpoint must not trust it: the
    strategy is the newest place a claim can appear, and a report computed
    before the strategy existed would let a banned hook line through a paid
    render. Recomputing is cheap and deterministic, so the gate is always
    evaluated against the text that is actually about to be sent to the model.
    """
    return claim_safety.build_safety_report(project or {}, profile or {})


@api_router.post("/studio/projects/{project_id}/strategy")
async def generate_project_strategy(
    project_id: str, payload: GenerateStrategyRequest, user_id: str = Depends(get_current_user_id)
):
    """
    Build the app-specific video strategy for a project.

    This is the step that makes the influencer workflow app-specific rather
    than generic. It reads the approved App Profile, the selected hook
    mechanism, the content angle and the objective, and returns a strategy
    that fixes the hook concept, the messaging, the exact words, the
    on-camera person's action and the scene they stand in — plus a
    continuity contract that every later segment is held to. The person's
    appearance is never described anywhere in the strategy; it comes from
    the founder's photograph.

    Free: no video is generated here, only text. The founder reviews and edits
    the strategy, then generates the 3-4 second hook from it.

    Regenerating bumps strategy_version, which invalidates unapproved segments
    built against the previous version so a hook can never be extended with a
    strategy that no longer matches it.
    """
    require_ai_configured()
    row = await _fetch_one(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?", (project_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Studio project not found")

    profile = await _require_profile_for_studio(row.get("brand_profile_id"), user_id)

    # Face-only product: retired uploads attached before the rule must be
    # detached before the project can move again — strategy included.
    _refuse_retired_project_assets(row.get("assets"))

    if not row.get("template_id"):
        raise HTTPException(
            status_code=400,
            detail="Choose a hook template first — the strategy must serve the selected mechanism.",
        )
    template = await _fetch_one(
        "SELECT * FROM hook_templates WHERE id = ? AND (user_id = ? OR user_id = 'system')",
        (row["template_id"], user_id),
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    angle = None
    if row.get("content_angle_id"):
        angle = await _fetch_one(
            "SELECT * FROM content_angles WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
            (row["content_angle_id"], row.get("brand_profile_id"), user_id),
        )
        if not angle:
            raise HTTPException(status_code=404, detail="Content angle not found for this App Profile")

    objective = template_library.normalize_objective(
        payload.objective or row.get("objective") or ""
    )
    total_duration = template_library.clamp_duration(
        payload.duration_seconds or row.get("duration_seconds")
    )
    tone = (payload.tone or row.get("tone") or "").strip()

    # The hook length the founder wants for the opening segment. Resolution
    # order: explicit request, the project's saved choice, then the selected
    # template's own declared hook_seconds (2-3s for every curated template) —
    # which is what makes a "Stop Doing This" template and a "Pain-Point
    # Question" template produce differently-paced hooks.
    #
    # Clamped to 2-4s, which is the whole window a hook has to land in, and the
    # same clamp create_studio_project and update_studio_project apply. Without
    # it a client could put anything here: the value seeds the strategy's own
    # segment budget, so the hook the founder is shown reviewing would disagree
    # with the boundary the render actually uses — and a hook_seconds at or
    # beyond the piece's length would collapse the middle to a second.
    #
    # The fallback is 3, NOT video_providers.DEFAULT_HOOK_SECONDS. That constant
    # is 5, left over from when the hook was a separately-rendered clip that had
    # to clear the provider's 5s floor before being trimmed down — a
    # sub-floor-hook problem this no longer has, and a value one second above
    # MAX_HOOK_SECONDS. Every curated template declares its own hook_seconds, so
    # the fallback only fires on a template saved with a NULL one.
    requested_hook = (
        payload.hook_seconds
        or row.get("hook_seconds")
        or template.get("hook_seconds")
        or 3
    )
    try:
        hook_seconds = int(requested_hook)
    except (TypeError, ValueError):
        hook_seconds = 3
    hook_seconds = max(
        template_library.MIN_HOOK_SECONDS,
        min(template_library.MAX_HOOK_SECONDS, hook_seconds),
    )

    profile_feedback = feedback_mod.summarize_profile_feedback(
        await _fetch_all(
            "SELECT event, signal, reason, template_id FROM feedback_events "
            "WHERE brand_profile_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 200",
            (row.get("brand_profile_id"), user_id),
        ),
        template.get("id") or "",
    )

    # The founder-approved creative plan, when one exists. The plan is written
    # and reviewed before the first render, so the strategy has to produce
    # THAT video. Without this the founder approved a script and then got a
    # different one.
    #
    # `cta` and `feature_emphasis` are not read. Both used to be here, and both
    # were the route by which a closing beat and a product demo reached the render
    # prompt. `demo_brief` is the replacement for the second: the founder needs to
    # know what to record, and passing it on would put a feature instruction back
    # into a video that is not allowed to demonstrate anything.
    approved_plan = None
    if int(row.get("script_version") or 0) > 0 and (
        str(row.get("script") or "").strip() or str(row.get("hook_line") or "").strip()
    ):
        approved_plan = {
            "hook_line": row.get("hook_line") or "",
            "script": row.get("script") or "",
            "visual_direction": row.get("visual_direction") or "",
            "voice_direction": row.get("voice_direction") or "",
            "sound_direction": row.get("sound_direction") or "",
            "beat_timeline": row.get("beat_timeline") or [],
        }
    script_feedback = await _component_feedback_for_profile(
        row.get("brand_profile_id"), user_id, "script")

    try:
        strategy = await _log_model_call(
            "video_strategy", "text", TEXT_MODEL,
            lambda: generate_video_strategy(
                profile=profile,
                template=template,
                angle=angle,
                objective=objective,
                hook_seconds=hook_seconds,
                total_duration=total_duration,
                tone=tone,
                brand_voice=profile.get("tone_voice") or "",
                profile_feedback=profile_feedback,
                component_feedback=script_feedback,
                plan=approved_plan,
            ),
            user_id,
            brand_profile_id=row.get("brand_profile_id"),
            studio_project_id=project_id,
            template_id=template.get("id"),
        )
    except Exception as e:
        # Distinguish a truncated response from every other failure, because
        # they need different fixes: truncation means the token budget is wrong,
        # anything else means the model or the request is. Both are already
        # logged with the raw text, so this only has to be honest in the UI.
        from ai_service import TruncatedResponse, ModelRefusal

        logger.error(f"Strategy generation failed for project {project_id}: {e!r}")
        if isinstance(e, TruncatedResponse):
            raise HTTPException(
                status_code=502,
                detail=(
                    "The strategy reply was cut off before it finished, so it could not be "
                    "read. This is a length problem, not a bad request — please try again."
                ),
            )
        if isinstance(e, ModelRefusal):
            raise HTTPException(
                status_code=502,
                detail=(
                    "The model declined to answer instead of returning a strategy — "
                    "usually its safety filter reacting to the app's topic, not a "
                    "bad request. Please try again once; if it repeats, report it "
                    "rather than retrying."
                ),
            )
        raise HTTPException(
            status_code=502,
            detail=f"AI strategy generation failed. Please try again. ({str(e)[:150]})",
        )

    # The strategy carries the words that will actually be spoken, so it goes
    # through exactly the same claim check as the plan. A banned claim in the
    # hook line is still a banned claim, and generation is gated on this.
    #
    # Before that, the spoken words are rewritten from the founder's approved
    # plan. The model writes its own section drafts, and those drafts reached
    # the provider as "spoken, performed naturally" — so a founder could
    # approve outcome-framed words on the Review step and hear the model's
    # paraphrase in the render. Binding here makes the checked words and the
    # spoken words the same words, and makes a regenerated strategy the fix for
    # an old or drifted one.
    if approved_plan:
        strategy, _overflow = bind_spoken_words(
            strategy, approved_plan, hook_seconds, total_duration
        )

    # The camera move's beat is stamped here rather than left to the model or
    # re-derived at finalize, because two readers that each compute "when" will
    # eventually disagree -- and when they do, the lean the model performs and
    # the reframe ffmpeg applies are two different events, which is precisely
    # the post-processing read this move exists to avoid. The model contributes
    # the gesture (already trimmed by normalize_strategy); this decides the
    # second, and both consumers read it back.
    strategy = dict(strategy or {})
    existing_beat = strategy.get("camera_beat")
    existing_beat = existing_beat if isinstance(existing_beat, dict) else {}
    strategy["camera_beat"] = {
        **existing_beat,
        "at": overlays.camera_beat_seconds(hook_seconds),
    }

    merged = dict(row)
    merged["strategy"] = strategy
    report = claim_safety.build_safety_report(merged, profile)
    summary = claim_safety.summarize(report)

    version = int(row.get("strategy_version") or 0) + 1
    now = now_iso()
    # Coverage used to be recorded here so the studio could say "the plan covers
    # N more segments" and warn before a founder extended past the end. There is
    # no extending: one render, two sections, and the founder attaches the rest
    # themselves. `planned_segments` and `max_planned_index` are no longer
    # written, and the length below is the whole piece rather than a hook that
    # has to be reconciled with later segments.
    # The script version this strategy was built from. The strategy is generated
    # from the founder's approved plan, so it is only true of that plan's words:
    # stamping the version is what lets a later script edit be detected instead
    # of silently leaving a strategy describing a hook line the founder has
    # since replaced. Stamped on the project rather than inside the strategy JSON
    # so a hand-edited strategy cannot overwrite it.
    # Deliberately does NOT touch `status`. This endpoint re-derives the
    # strategy from the founder's already-approved plan and changes nothing they
    # read -- unlike generate_plan, which rewrites the script and genuinely does
    # send the project back to draft. Demoting it here made the "Mark ready for
    # generation" button on the Review step spring back into existence, so a
    # founder who built their strategy was bounced a step to re-approve a
    # project they had not changed.
    #
    # `hook_seconds` is written back so the render splits the piece at the same
    # boundary the plan and strategy both agreed on, rather than each
    # re-deriving it from the template and risking a disagreement.
    script_version_at_build = int(row.get("script_version") or 0)
    await _execute(
        """UPDATE studio_projects SET strategy = ?, strategy_version = ?,
             strategy_script_version = ?,
             hook_seconds = ?,
             safety_report = ?, safety_summary = ?, updated_at = ?
           WHERE id = ? AND user_id = ?""",
        (json.dumps(strategy), version, script_version_at_build, hook_seconds,
         json.dumps(report), summary, now, project_id, user_id),
    )
    logger.info(
        f"Generated strategy for project {project_id} (v{version}) — hook "
        f"{hook_seconds}s, middle {total_duration - hook_seconds}s, "
        f"{len(strategy.get('segments') or [])} section(s) — {summary}"
    )
    return _public_project(
        await _fetch_one("SELECT * FROM studio_projects WHERE id = ?", (project_id,))
    )


@api_router.post("/generations/{generation_id}/archive")
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


# ---------------------------------------------------------------------------
# Asset library (per App Profile)
# ---------------------------------------------------------------------------
ASSET_MAX_BYTES = 200 * 1024 * 1024  # 200 MB ceiling
ASSET_IMAGE_TYPES = {
    "character_reference": "image",
}
ASSET_ALLOWED_EXT = {
    "image": {".png", ".jpg", ".jpeg", ".webp", ".gif"},
}
ASSET_AUDIO_ROLES = ("background", "voiceover")
GENERATED_ID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _public_asset(row: dict) -> dict:
    out = dict(row)
    out["rights_confirmed"] = bool(out.get("rights_confirmed"))
    if out.get("file_path"):
        out["media_url"] = media_signing.build_signed_asset_path(out["id"])
    return out


async def _asset_usage_index(profile_id: str) -> dict:
    """
    Map each asset id to the studio projects that reference it.

    Resolved in Python rather than SQL. The attachment list lives in a JSON
    column on studio_projects, so SQLite would need json_each to join against
    it. At this tool's volumes -- a founder's own handful of projects per app --
    one query and a dict build is simpler, and far easier to read than a
    correlated subquery, which matters because "which videos used this asset"
    is the kind of question that gets audited.

    Attachments are snapshots, not foreign keys: detaching an asset leaves the
    history intact, which is the point. A project whose asset file has since
    been deleted still counts as a use.
    """
    index: dict = {}
    if not profile_id:
        return index
    rows = await _fetch_all(
        "SELECT id, hook_line, status, script_version, assets FROM studio_projects "
        "WHERE brand_profile_id = ?",
        (profile_id,),
    )
    for row in rows:
        # The connection's row factory already decodes JSON columns, but a
        # hand-written or older row can still arrive as a string, and junk in
        # the column must not break the listing for every other asset.
        attached = row.get("assets")
        if isinstance(attached, str):
            try:
                attached = json.loads(attached or "[]")
            except ValueError:
                continue
        if not isinstance(attached, list):
            continue
        for item in attached:
            if not isinstance(item, dict):
                continue
            asset_id = str(item.get("asset_id") or "").strip()
            if not asset_id:
                continue
            # A project has no name of its own, so the hook line stands in. A
            # draft that has not been planned yet has no hook, and is labelled
            # by its stage instead of pretending to have a title.
            label = (row.get("hook_line") or "").strip()
            if not label:
                label = "Planned project" if row.get("script_version") else "Unplanned draft"
            index.setdefault(asset_id, []).append({
                "studio_project_id": row["id"],
                "name": label,
                "status": row.get("status") or "draft",
            })
    return index


def _attach_usage(asset: dict, index: dict) -> dict:
    """Add usage history to one asset, newest project first."""
    uses = index.get(asset.get("id"), [])
    out = dict(asset)
    out["usage_count"] = len(uses)
    out["used_in"] = uses
    return out


def _asset_dir(profile_id: str) -> Path:
    """Per-App-Profile asset folder, resolved safely from a known UUID."""
    safe = profile_id if GENERATED_ID_RE.match(profile_id or "") else "unscoped"
    target = pipeline.ASSETS_DIR / safe
    target.mkdir(parents=True, exist_ok=True)
    return target


async def _ensure_asset_file(row: dict) -> Path | None:
    """
    The asset's bytes on this disk, restored from R2 when they are gone.

    A Cloud Run container gets a fresh disk on every deploy, so a photograph
    that uploaded fine yesterday can be missing today even though R2 still
    holds it. Everything that needs the file — the preview route, attaching,
    and generation's identity pass — comes through here, so one restore
    covers all three instead of each refusing on a file the cloud can
    produce. Returns None when there is genuinely nothing to serve.
    """
    stored = row.get("file_path") or ""
    if not stored:
        return None
    file_path = Path(stored)
    if file_path.is_file():
        return file_path
    if not storage_service.is_configured():
        return None
    profile_id = str(row.get("brand_profile_id") or "")
    if not GENERATED_ID_RE.match(profile_id):
        return None
    target = _asset_dir(profile_id) / f"{row['id']}{file_path.suffix}"
    try:
        restored = await asyncio.to_thread(
            storage_service.download_asset, row.get("user_id") or "", row["id"], target
        )
    except Exception as error:
        logger.warning("Cloud asset restore failed for %s (%s)", row["id"], type(error).__name__)
        return None
    if not restored or not target.is_file():
        return None
    # Keep the row in step with where the file actually is: attach and
    # generation read `file_path` directly, so a restored copy at a
    # different path would still look missing to them.
    if str(target) != stored:
        await _execute("UPDATE assets SET file_path = ? WHERE id = ?", (str(target), row["id"]))
    return target


@api_router.get("/app-profiles/{profile_id}/assets")
async def list_assets(
    profile_id: str,
    kind: str = "",
    include_archived: bool = False,
    user_id: str = Depends(get_current_user_id),
):
    """Library assets for one App Profile. Always scoped to that profile."""
    profile = await _fetch_one(
        "SELECT id FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")
    clauses = ["brand_profile_id = ?", "user_id = ?"]
    params: list = [profile_id, user_id]
    if not include_archived:
        clauses.append("status = 'active'")
    if kind.strip():
        clauses.append("kind = ?")
        params.append(template_library.normalize_asset_kind(kind))
    rows = await _fetch_all(
        f"SELECT * FROM assets WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT 300",
        tuple(params),
    )
    # One index for the whole page rather than a lookup per asset.
    index = await _asset_usage_index(profile_id)
    return {
        "assets": [_attach_usage(_public_asset(r), index) for r in rows]
    }


@api_router.get("/assets/{asset_id}/usage")
async def get_asset_usage(asset_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Which projects have used this asset, and which videos came out of them.

    Scoped to the asset's own App Profile, so a user cannot read another
    profile's project names by guessing an asset id.
    """
    asset = await _fetch_one(
        "SELECT * FROM assets WHERE id = ? AND user_id = ?", (asset_id, user_id)
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    index = await _asset_usage_index(asset.get("brand_profile_id"))
    uses = index.get(asset_id, [])
    for use in uses:
        gens = await _fetch_all(
            "SELECT id, status, video_url, r2_url, created_at FROM generations "
            "WHERE studio_project_id = ? ORDER BY created_at DESC LIMIT 20",
            (use["studio_project_id"],),
        )
        # Signed for the same reason as everywhere else: this endpoint returns
        # raw generation rows rather than going through _public_generation, and
        # the media route rejects an unsigned one. Both fields, so a consumer
        # that reaches for r2_url (the durable copy) cannot be handed a 404 by
        # a row that was signed on one field only.
        gens = [
            {
                **g,
                "video_url": media_signing.sign_stored_path(g.get("video_url")),
                "r2_url": media_signing.sign_stored_path(g.get("r2_url")),
            }
            for g in gens
        ]
        use["generations"] = gens
    return {
        "asset": _attach_usage(_public_asset(asset), index),
        "usage_count": len(uses),
        "used_in": uses,
    }


@api_router.post("/app-profiles/{profile_id}/assets", status_code=201)
async def upload_asset(
    profile_id: str,
    kind: str = Form(...),
    file: UploadFile = File(...),
    label: str = Form(""),
    notes: str = Form(""),
    rights_confirmed: bool = Form(False),
    user_id: str = Depends(get_current_user_id),
):
    """
    Upload the founder's photograph into one App Profile's library.

    Face-only product: the character reference is the single permitted
    upload. Every video is generated from that photograph plus App Profile
    facts, so screenshots, recordings, logos, photos, and audio are refused
    here rather than accepted into a pipeline that can no longer use them.

    The file extension must match. That check exists because a video file
    declared as a photograph would make the identity pass feed the wrong
    input and produce a silently broken submission.
    """
    profile = await _fetch_one(
        "SELECT id FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")

    asset_kind = template_library.normalize_asset_kind(kind)
    if asset_kind != "character_reference":
        await _record_asset_event(
            "upload_rejected",
            f"Only the character reference can be uploaded (asked for: {kind}).",
            user_id,
            brand_profile_id=profile_id, asset_kind=kind,
            filename=file.filename or "",
        )
        raise HTTPException(
            status_code=400,
            detail=(
                "Only the character reference can be uploaded. Every video is "
                "generated from your photograph plus the App Profile — "
                "screenshots, recordings, logos, and audio are not accepted."
            ),
        )
    expected_type = ASSET_IMAGE_TYPES.get(asset_kind)

    raw = await file.read()
    if not raw:
        await _record_asset_event(
            "upload_rejected", "Uploaded file is empty.", user_id,
            brand_profile_id=profile_id, asset_kind=asset_kind,
            filename=file.filename or "",
        )
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(raw) > ASSET_MAX_BYTES:
        await _record_asset_event(
            "upload_rejected",
            f"Asset is larger than {ASSET_MAX_BYTES // (1024 * 1024)} MB.",
            user_id, brand_profile_id=profile_id, asset_kind=asset_kind,
            filename=file.filename or "",
        )
        raise HTTPException(
            status_code=400,
            detail=f"Asset is larger than {ASSET_MAX_BYTES // (1024 * 1024)} MB.",
        )

    ext = Path(file.filename or "").suffix.lower()
    allowed = ASSET_ALLOWED_EXT[expected_type]
    if ext not in allowed:
        await _record_asset_event(
            "upload_rejected",
            f"A {asset_kind.replace('_', ' ')} must be one of: "
            f"{', '.join(sorted(allowed))}",
            user_id, brand_profile_id=profile_id, asset_kind=asset_kind,
            filename=file.filename or "",
        )
        raise HTTPException(
            status_code=400,
            detail=f"A {asset_kind.replace('_', ' ')} must be one of: "
                   f"{', '.join(sorted(allowed))}",
        )

    asset_id = str(uuid.uuid4())
    target = _asset_dir(profile_id) / f"{asset_id}{ext}"
    target.write_bytes(raw)

    # No playability probe: the only uploadable kind is a still photograph,
    # so there is no audio whose decodability would need verifying up front.
    duration_seconds = None

    # Pre-flight face count. The provider's privacy filter fires on photos
    # where no single face anchors the frame, so count locally and warn now
    # rather than at generation time. Never blocks the upload: the detector
    # can be wrong (stylised photo, sunglasses), and a warning the founder
    # can overrule beats a refusal they cannot.
    face_count = None
    try:
        from face_crop import count_faces_from_path
        face_count = count_faces_from_path(target)
    except Exception as e:  # never fail an upload over detection
        logger.warning(f"Face count skipped for {asset_id} ({e}).")
        face_count = None

    now = now_iso()
    await _execute(
        """INSERT INTO assets
           (id, brand_profile_id, kind, name, label, notes, file_path, content_type,
            duration_seconds, face_count, rights_confirmed, status, created_at, updated_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)""",
        (asset_id, profile_id, asset_kind, (file.filename or "")[:200],
         (label or "")[:120], (notes or "")[:500], str(target), file.content_type,
         duration_seconds, face_count, 1 if rights_confirmed else 0, now, now, user_id),
    )
    logger.info(f"Uploaded {asset_kind} asset {asset_id} for profile {profile_id}")
    # Durable copy, best effort: the local file serves this instance, but a
    # Cloud Run deploy throws the disk away, and without this the photograph
    # would be gone from the library — and unusable by attach and generation —
    # the next morning. Failure only logs: the upload itself already succeeded.
    try:
        await asyncio.to_thread(storage_service.upload_asset, user_id, asset_id, target)
    except Exception as exc:
        logger.warning("Asset R2 upload failed for %s (%s)", asset_id, type(exc).__name__)
    created = _public_asset(await _fetch_one("SELECT * FROM assets WHERE id = ?", (asset_id,)))
    if face_count is not None and face_count != 1:
        created["face_warning"] = (
            "No face detected in this photo — the video provider is likely to refuse it. "
            "Use a clear, front-facing shot."
            if face_count == 0 else
            f"{face_count} faces detected — the provider may flag photos with more than "
            "one person. Use a solo shot if generation is refused."
        )
    return created


@api_router.patch("/assets/{asset_id}")
async def update_asset(
    asset_id: str, payload: UpdateAssetRequest, user_id: str = Depends(get_current_user_id)
):
    row = await _fetch_one(
        "SELECT * FROM assets WHERE id = ? AND user_id = ?", (asset_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")

    updates = payload.model_dump(exclude_unset=True)
    if "kind" in updates:
        # Face-only library: a retired or mistyped kind normalizes to "" and
        # must not be written, or the row would advertise an asset the
        # product can no longer accept.
        kind = template_library.normalize_asset_kind(updates["kind"])
        if kind != "character_reference":
            raise HTTPException(
                status_code=400,
                detail="Only the character reference can be stored in the library.",
            )
        updates["kind"] = kind
    set_clauses, values = [], []
    for key, value in updates.items():
        if key == "rights_confirmed":
            value = 1 if value else 0
        elif key == "kind":
            value = template_library.normalize_asset_kind(value)
        elif key == "status":
            value = "archived" if str(value or "").lower() == "archived" else "active"
        elif value is not None:
            value = str(value).strip()
        set_clauses.append(f"{key} = ?")
        values.append(value)
    if not set_clauses:
        return _public_asset(row)

    set_clauses.append("updated_at = ?")
    values.append(now_iso())
    values.extend([asset_id, user_id])
    await _execute(
        f"UPDATE assets SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?",
        tuple(values),
    )
    return _public_asset(await _fetch_one("SELECT * FROM assets WHERE id = ?", (asset_id,)))


@api_router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: str, user_id: str = Depends(get_current_user_id)):
    row = await _fetch_one(
        "SELECT * FROM assets WHERE id = ? AND user_id = ?", (asset_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")
    # Deleting the file does not rewrite the projects that referenced it, so
    # their usage history survives as a record of what happened. Surfacing the
    # count lets the caller warn instead of silently orphaning them.
    index = await _asset_usage_index(row.get("brand_profile_id"))
    still_used = index.get(asset_id, [])
    await _execute("DELETE FROM assets WHERE id = ? AND user_id = ?", (asset_id, user_id))
    path = Path(row.get("file_path") or "")
    try:
        if path.is_file() and pipeline.ASSETS_DIR.resolve() in path.resolve().parents:
            path.unlink()
    except OSError as e:
        logger.warning(f"Could not remove asset file {path}: {e}")
    # The durable copy too, or a deleted photograph would outlive its row in
    # R2 with nothing left to delete it.
    try:
        await asyncio.to_thread(storage_service.delete_asset, user_id, asset_id)
    except Exception as e:
        logger.warning(f"Could not remove asset object from R2 for {asset_id}: {e}")
    return {
        "deleted": asset_id,
        "usage_count": len(still_used),
        "note": (
            f"{len(still_used)} project(s) still reference this asset."
            if still_used else None
        ),
    }


@api_router.post("/studio/projects/{project_id}/assets", status_code=201)
async def attach_asset_to_project(
    project_id: str, payload: AttachAssetRequest, user_id: str = Depends(get_current_user_id)
):
    """
    Attach the character reference to a project.

    Enforces that the asset belongs to the SAME App Profile as the project.
    This is the cross-app guard: without it, one app's photograph could
    anchor another app's video.
    """
    project = await _fetch_one(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?", (project_id, user_id)
    )
    if not project:
        raise HTTPException(status_code=404, detail="Studio project not found")

    asset = await _fetch_one(
        "SELECT * FROM assets WHERE id = ? AND user_id = ?", (payload.asset_id, user_id)
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset["brand_profile_id"] != project.get("brand_profile_id"):
        raise HTTPException(
            status_code=400,
            detail="That asset belongs to a different app. Assets can only be used in "
                   "their own App Profile's projects.",
        )
    # The disk this container booted with may be younger than the upload, so
    # restore from R2 before refusing — a photo the cloud still holds is not
    # missing, and telling the founder to re-upload it would be wrong.
    if await _ensure_asset_file(asset) is None:
        await _record_asset_event(
            "file_missing", "The asset file is missing on disk.", user_id,
            brand_profile_id=project.get("brand_profile_id"),
            studio_project_id=project_id, asset_id=asset["id"],
            asset_kind=asset.get("kind"),
        )
        raise HTTPException(status_code=409, detail="The asset file is missing on disk.")

    # Face-only product: a retired upload (screenshot, recording, logo,
    # photo, audio) can still sit in the library from before, but it can
    # never join a project again. Refused here, at attach time, rather than
    # failing later inside generation.
    if (asset.get("kind") or "") != "character_reference":
        raise HTTPException(
            status_code=400,
            detail=(
                "Only the character reference can be attached to a project. "
                f"This asset is a {(asset.get('kind') or 'file').replace('_', ' ')} "
                "from before uploads went face-only."
            ),
        )

    current = project.get("assets") or []
    if not isinstance(current, list):
        current = []
    is_audio = asset.get("kind") == "audio"
    audio_role = (payload.audio_role or "background").strip().lower()
    if audio_role not in ASSET_AUDIO_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"audio_role must be one of: {', '.join(ASSET_AUDIO_ROLES)}.",
        )
    if not is_audio and (payload.audio_role is not None or payload.audio_gain is not None):
        raise HTTPException(
            status_code=400,
            detail="Audio role and gain apply only to audio assets.",
        )
    try:
        audio_gain = float(payload.audio_gain) if payload.audio_gain is not None else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="audio_gain must be a number.")
    if audio_gain is not None and not 0.0 <= audio_gain <= 2.0:
        raise HTTPException(status_code=400, detail="audio_gain must be between 0 and 2.")
    entry = {
        "asset_id": asset["id"],
        "kind": asset["kind"],
        "label": asset.get("label") or asset.get("name") or "",
        "file_path": asset["file_path"],
    }
    for key in ("start", "end", "position", "scale"):
        value = getattr(payload, key, None)
        if value is not None:
            entry[key] = value
    if is_audio:
        entry["audio_role"] = audio_role
        entry["audio_gain"] = audio_gain if audio_gain is not None else (
            1.0 if audio_role == "voiceover" else 0.25
        )
    current.append(entry)

    await _execute(
        "UPDATE studio_projects SET assets = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (json.dumps(current), now_iso(), project_id, user_id),
    )
    return {"assets": current}


@api_router.delete("/studio/projects/{project_id}/assets/{asset_id}")
async def detach_asset_from_project(
    project_id: str, asset_id: str, user_id: str = Depends(get_current_user_id)
):
    project = await _fetch_one(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?", (project_id, user_id)
    )
    if not project:
        raise HTTPException(status_code=404, detail="Studio project not found")
    current = project.get("assets") or []
    if not isinstance(current, list):
        current = []
    remaining = [a for a in current if a.get("asset_id") != asset_id]
    await _execute(
        "UPDATE studio_projects SET assets = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (json.dumps(remaining), now_iso(), project_id, user_id),
    )
    return {"assets": remaining}


# ---------------------------------------------------------------------------
# Deterministic overlay composition (retired)
# ---------------------------------------------------------------------------
# Burned-in captions were removed from the Hook + Story path: the compose
@api_router.get("/history/generations")
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
        entry["composition"] = None
        out.append(entry)
    await _with_verdicts(out, user_id)
    return {"generations": out}


@api_router.delete("/generations/{generation_id}")
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


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------
@api_router.get("/feedback/catalog")
async def feedback_catalog():
    """Events, permitted reasons, and the automatic triggers, for the UI."""
    return feedback_mod.catalog()


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
    # as an automatic trigger or a stated cause.
    is_thumb = event in ("thumb_up", "thumb_down")
    step = feedback_mod.normalize_component(payload.step)
    if is_thumb:
        if not step:
            raise HTTPException(
                status_code=400,
                detail="Thumbs feedback needs a valid component. "
                       f"Known: {', '.join(feedback_mod.COMPONENTS)}.",
            )
        if signal or reason:
            raise HTTPException(
                status_code=400,
                detail="Thumbs feedback carries no signal or reason; the step is the context.",
            )
    elif (payload.step or "").strip():
        if not step:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown step '{payload.step}'.",
            )
    if not signal and not reason and not is_thumb:
        raise HTTPException(
            status_code=400,
            detail="Feedback needs a signal or a reason.",
        )

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
    return {"id": event_id, "event": event, "signal": signal, "reason": reason, "step": step}


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
        # serve non-DB requests, and the next inbound request will trigger
        # lazy table creation via get_db's fallback path.
        logger.critical(
            f"init_db failed after 3 attempts, starting anyway: {last_error}"
        )
    # AFTER init_db, deliberately: the disclosure reports the backend init_db
    # actually established (module global), never the configured one. Logging
    # it before would repeat the old lie — "Turso cloud" from config while the
    # connection had fallen back to ephemeral.
    _log_database_backend()
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
    # one (or does not) needs no code change. Same shape as the check above:
    # free, unauthenticated, best-effort, and never able to fail the boot — a
    # failed lookup just leaves the offline fallback in place.
    try:
        await ai_service.refresh_temperature_support(
            [ai_service.TEXT_MODEL, ai_service.VISION_MODEL]
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


@app.get("/api/media/frames/{video_hash}/{filename}")
async def serve_frame(video_hash: str, filename: str):
    """
    Serve an extracted analysis frame from its local cache or durable JPEG
    backup. Older analyses may still have only a cached MP4, which remains a
    final no-network re-extraction fallback.
    """
    frame_path = await _ensure_analysis_frame(video_hash, filename)
    if frame_path:
        return FileResponse(
            str(frame_path),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    # Legacy analysis with no durable frame record: use an already-local video
    # only. This never downloads a remote TikTok clip during an image request.
    if await _recover_missing_frame(f"frames/{video_hash}/{filename}"):
        frame_path = await _ensure_analysis_frame(video_hash, filename)
        if frame_path:
            return FileResponse(
                str(frame_path),
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"},
            )

    raise HTTPException(
        status_code=404,
        detail="Extracted frame is unavailable. Please re-analyze the video.",
    )


@app.get("/api/media/templates/{template_id}.jpg")
async def serve_template_thumbnail(template_id: str):
    """Serve a durable bookmark thumbnail, restoring its local cache if needed."""
    thumbnail_path = await _ensure_template_thumbnail(template_id)
    if not thumbnail_path:
        raise HTTPException(
            status_code=404,
            detail="Bookmark thumbnail is unavailable. Open the source analysis and save the hook again.",
        )
    return FileResponse(
        str(thumbnail_path),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# A generated clip's filename, accepted or refused whole.
#
# The blanket StaticFiles mount below happily serves any readable path under
# storage/, which is fine for a file that already exists on disk. This route
# resolves a name supplied in the URL instead, so it validates the name itself
# rather than trusting the filesystem: one segment, a UUID-ish id, an .mp4
# suffix, nothing else. That rules out traversal ("../"), absolute paths,
# separators, and query tricks without having to reason about what
# Path.resolve() would do with each of them.
_VIDEO_FILENAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}\.mp4$")


def _parse_byte_range(range_header: str, total: int):
    """
    Classify a `Range: bytes=...` header against a known file size.

    Returns ("ok", (start, end_inclusive)) for a usable range,
    ("unsatisfiable", None) for a syntactically valid one that lies outside the
    file, and ("none", None) when there is nothing to honour — no header, an
    unrecognised unit, or a form this does not answer.

    The three are kept apart because they are three different answers: a 206, a
    416 that tells the player how long the file actually is, and an ordinary
    200. Collapsing "unsatisfiable" into "none" would answer a request the
    player believed it had satisfied with a body it did not ask for.

    Only the single-range forms a media element sends are honoured: `bytes=a-`,
    `bytes=a-b`, `bytes=-suffix`. A multi-range request (`bytes=0-9,20-29`)
    returns "none" rather than a partial answer.
    """
    if not range_header:
        return "none", None
    header = range_header.strip()
    if not header.lower().startswith("bytes="):
        return "none", None
    spec = header[6:].strip()
    if "," in spec:  # multi-range: not supported, fall back to a full 200
        return "none", None
    start_text, _, end_text = spec.partition("-")
    start_text, end_text = start_text.strip(), end_text.strip()
    try:
        if not start_text:
            if not end_text:
                return "none", None
            # Suffix form: the last N bytes.
            suffix = int(end_text)
            if suffix <= 0:
                return "unsatisfiable", None
            start = max(0, total - suffix)
            end = total - 1
        else:
            start = int(start_text)
            end = int(end_text) if end_text else total - 1
    except ValueError:
        return "none", None
    if start >= total or end < start:
        return "unsatisfiable", None
    return "ok", (start, min(end, total - 1))


def _iter_file_range(path: Path, start: int, end: int, chunk_size: int = 256 * 1024):
    """
    Yield exactly bytes[start..end] of a file, in chunks.

    Deliberately not FileResponse. On this Starlette version FileResponse always
    streams the WHOLE file and, when a caller supplies its own Content-Length,
    sends that header anyway — so a 206 built from it claims to be a 100-byte
    range and then delivers the entire clip. A player that trusts the header is
    worse off than one that got a 200: it is told the response was truncated
    partway through. The bytes therefore have to be counted here.
    """
    remaining = end - start + 1
    with open(path, "rb") as fh:
        fh.seek(start)
        while remaining > 0:
            chunk = fh.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@app.get("/api/media/videos/{filename}")
async def serve_video(filename: str, request: Request, sig: str = "", exp: str = ""):
    """
    Serve a generated clip so a <video> element can actually play it.

    Every other file under /api/media is served by the StaticFiles mount below,
    which is fine for images. It is not fine for video: Starlette's StaticFiles
    has no byte-range support, so it answers a media element's request with a
    plain 200 and no `Accept-Ranges`. Chrome needs ranges to start playback and
    to report a duration, which is why these clips rendered their first frame,
    showed 0:00, and had a play button that did nothing — while "Download MP4"
    beside them, a plain GET that saves bytes, worked perfectly. The file was
    never the problem; the response headers were.

    Declared above the mount on purpose: Starlette matches routes in
    registration order, so this shadows StaticFiles for /api/media/videos/*
    while leaving every other media path untouched.

    Authenticated by signature, not by header. A `<video src>` and an
    `<a download>` cannot carry an Authorization header, so requiring one would
    mean the player never worked — which is what this route exists to prevent.
    Instead every clip is fetched through a signed URL (see media_signing.py),
    and an unsigned or expired one is refused. Without that, this route was
    world-readable: the filename IS the generation id, so every paid render
    could be pulled by anyone who guessed one.

    The refusal is a 404 with the same body as a missing file, on purpose. A
    403 would confirm the clip exists, which turns this route into a way to
    enumerate other people's paid renders.
    """
    if not _VIDEO_FILENAME_RE.match(filename or ""):
        raise HTTPException(status_code=404, detail="Clip not found")

    if not media_signing.verify(filename, exp, sig):
        raise HTTPException(status_code=404, detail="Clip not found")

    video_path = pipeline.VIDEOS_DIR / filename
    if not video_path.is_file() or video_path.stat().st_size <= 0:
        # Signature verification precedes all DB/object access. Derive owner and
        # key from our records, not from an arbitrary URL supplied by a client.
        row = await _fetch_one(
            "SELECT id, user_id, r2_url FROM generations WHERE id = ?",
            (filename[:-4],),
        )
        if row and storage_service.is_configured():
            # Local bytes are gone, so the durable R2 copy is served through
            # this same-origin route, exactly as the download route already
            # does. A 307 to the presigned cloud URL stood here, but reading
            # its body needs CORS on the bucket, which R2 does not grant by
            # default — fetch().blob() in the Demo + CTA editor (and any
            # cross-origin <video> read) then failed as "Failed to fetch"
            # for a clip that was never missing. Proxying costs container
            # egress instead; at this app's volume it is immaterial.
            try:
                head = await asyncio.to_thread(
                    storage_service.cloud_video_head, row["user_id"], row["id"])
            except storage_service.CloudObjectMissing:
                head = None
            except Exception as error:
                logger.warning("Cloud playback failed for %s (%s)", row["id"], type(error).__name__)
                raise HTTPException(status_code=503, detail="Cloud video is temporarily unavailable")
            if head is not None:
                total, content_type = head
                cloud_headers = {
                    "Accept-Ranges": "bytes",
                    "Content-Type": content_type,
                    "Cache-Control": "private, max-age=31536000, immutable",
                }
                verdict, span = _parse_byte_range(request.headers.get("range"), total)
                if verdict == "unsatisfiable":
                    return Response(
                        status_code=416,
                        headers={**cloud_headers, "Content-Range": f"bytes */{total}"},
                    )
                try:
                    if verdict == "none":
                        _, body = await asyncio.to_thread(
                            storage_service.open_video_for_download, row["user_id"], row["id"])
                        return StreamingResponse(
                            _iter_r2_object(body),
                            headers={**cloud_headers, "Content-Length": str(total)},
                        )
                    start, end = span
                    body = await asyncio.to_thread(
                        storage_service.open_cloud_range, row["user_id"], row["id"], start, end)
                    return StreamingResponse(
                        _iter_r2_object(body),
                        status_code=206,
                        headers={
                            **cloud_headers,
                            "Content-Range": f"bytes {start}-{end}/{total}",
                            "Content-Length": str(end - start + 1),
                        },
                    )
                except storage_service.CloudObjectMissing:
                    # Vanished between HEAD and GET; fall through to the
                    # external copy and the 404 below.
                    pass
                except HTTPException:
                    raise
                except Exception as error:
                    logger.warning("Cloud playback failed for %s (%s)", row["id"], type(error).__name__)
                    raise HTTPException(status_code=503, detail="Cloud video is temporarily unavailable")
        if row:
            external = _http_video_source(row.get("r2_url"))
            if external and not storage_service.is_managed_url(external):
                return RedirectResponse(external, status_code=307,
                                        headers={"Cache-Control": "private, no-store"})
        raise HTTPException(status_code=404, detail="Clip not found")
    total = video_path.stat().st_size
    if total <= 0:
        raise HTTPException(status_code=404, detail="Clip is empty")

    base_headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": storage_service.video_content_type(video_path) or "video/mp4",
        # Private, not public: the bytes never change, so the response can be
        # cached hard, but only by the client that was given a signed link.
        # `public` here would let a shared cache keep serving a paid render to
        # whoever asked next.
        "Cache-Control": "private, max-age=31536000, immutable",
    }

    verdict, span = _parse_byte_range(request.headers.get("range"), total)
    if verdict == "unsatisfiable":
        # A 416 has to say how long the file is, or the player cannot tell a
        # stale request from a wrong one.
        return Response(
            status_code=416,
            headers={**base_headers, "Content-Range": f"bytes */{total}"},
        )
    if verdict == "none":
        # No range, or one we decline to answer: the whole file, and still
        # advertising that ranges exist so the player can seek.
        return FileResponse(str(video_path), headers=base_headers)
    start, end = span
    return StreamingResponse(
        _iter_file_range(video_path, start, end),
        status_code=206,
        headers={
            **base_headers,
            "Content-Range": f"bytes {start}-{end}/{total}",
            "Content-Length": str(end - start + 1),
        },
    )


def _iter_r2_object(body, chunk_size: int = 256 * 1024):
    """
    Stream an open boto3 body in fixed chunks.

    `body.read()` with no size would pull the whole clip into this process at
    once, which on a 4GiB instance is real money for a file that may not even be
    playable. Chunked, so memory stays flat no matter the clip size. The body is
    always closed, including on a client disconnect mid-stream.
    """
    try:
        while True:
            chunk = body.read(chunk_size)
            if not chunk:
                break
            yield chunk
    finally:
        body.close()


@app.get("/api/media/videos/{filename}/download")
async def download_video_clip(filename: str, sig: str = "", exp: str = ""):
    """
    Send a clip to the browser as a file save rather than a page load.

    Why this route exists rather than an <a download> on the playback URL: a
    durable clip usually lives in R2, so `r2_url` is an ABSOLUTE cross-origin
    URL. Browsers ignore the `download` attribute on cross-origin hrefs, so that
    button opened the file in a tab (or navigated away) instead of saving it --
    the one action the row exists to offer, silently not doing its job.

    A same-origin path through here fixes that unconditionally: `download` is
    honored, and Content-Disposition: attachment makes it a save even if the
    attribute is ignored.

    Bytes transit this process, which they did not when R2 redirected straight to
    the browser. That is the deliberate trade: it costs egress from the container
    instead of a client-side blob (which buffers the same bytes in the tab and
    leaks an object URL per download), and at this app's volume it is immaterial.

    Signature auth and the 404-on-refusal rule are identical to serve_video --
    the filename IS the generation id, so this must not be enumerable. Declared
    after it for the same registration-order reason, and it is a longer path, so
    the video route matches first for plain playback requests.
    """
    if not _VIDEO_FILENAME_RE.match(filename or ""):
        raise HTTPException(status_code=404, detail="Clip not found")
    if not media_signing.verify(filename, exp, sig):
        raise HTTPException(status_code=404, detail="Clip not found")

    disposition = f'attachment; filename="{Path(filename).name}"'
    # Local copy first: it is the same bytes the player just streamed, and it
    # avoids an R2 round trip entirely when the container still holds the clip.
    local_path = pipeline.VIDEOS_DIR / filename
    if local_path.is_file() and local_path.stat().st_size > 0:
        total = local_path.stat().st_size
        return StreamingResponse(
            _iter_file_range(local_path, 0, total - 1),
            media_type=storage_service.video_content_type(local_path) or "video/mp4",
            headers={
                "Content-Length": str(total),
                "Content-Disposition": disposition,
                # Private, immutable, and explicitly not a byte range: a download
                # is always the whole file. Advertising ranges here would let a
                # client resume mid-file and assemble something that was never
                # the stored object.
                "Cache-Control": "private, max-age=3600",
                "Accept-Ranges": "none",
            },
        )

    row = await _fetch_one(
        "SELECT id, user_id, r2_url FROM generations WHERE id = ?",
        (filename[:-4],),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Clip not found")

    try:
        opened = await asyncio.to_thread(
            storage_service.open_video_for_download, row["user_id"], row["id"]
        )
    except storage_service.CloudObjectMissing:
        raise HTTPException(status_code=404, detail="Clip not found")
    if opened is None:
        raise HTTPException(status_code=404, detail="Clip not found")

    total, body = opened
    return StreamingResponse(
        _iter_r2_object(body),
        media_type="video/mp4",
        headers={
            "Content-Length": str(total),
            "Content-Disposition": disposition,
            "Cache-Control": "private, max-age=3600",
            "Accept-Ranges": "none",
        },
    )


# A poster filename, accepted or refused whole — same traversal discipline as
# the video route: one segment, an id, a .jpg suffix, nothing else.
_POSTER_FILENAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}\.jpg$")


@app.get("/api/media/posters/{filename}")
async def serve_poster(filename: str, sig: str = "", exp: str = ""):
    """
    Serve a generation's poster thumbnail so History can render it as an image.

    Signed like video (an <img src> cannot carry auth either, and posters are
    thumbnails of paid renders). Lazy: if no cached JPEG exists, build one
    from the local clip, or restore the clip/poster from R2 via the row's
    owner and then build it. A missing poster is a 404 the frontend treats as
    "no thumbnail yet" — playback must never depend on it.
    """
    if not _POSTER_FILENAME_RE.match(filename or ""):
        raise HTTPException(status_code=404, detail="Poster not found")
    if not media_signing.verify(filename, exp, sig):
        raise HTTPException(status_code=404, detail="Poster not found")

    job_id = filename[:-4]
    poster = posters.poster_path(job_id)
    if posters.is_usable_poster(poster):
        return FileResponse(
            str(poster),
            media_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=31536000, immutable"},
        )

    # Owner comes from our rows, never from the URL, like the video route.
    row = await _fetch_one(
        "SELECT id, user_id FROM generations WHERE id = ?", (job_id,))
    if row and storage_service.is_configured():
        try:
            restored_poster = await asyncio.to_thread(
                storage_service.download_poster, row["user_id"], row["id"], poster)
            if restored_poster and posters.is_usable_poster(poster):
                return FileResponse(
                    str(poster),
                    media_type="image/jpeg",
                    headers={"Cache-Control": "private, max-age=31536000, immutable"},
                )
        except Exception as error:
            logger.warning("Cloud poster read failed for %s (%s)", job_id, type(error).__name__)

    video = pipeline.VIDEOS_DIR / f"{job_id}.mp4"
    if not video.is_file() and row and storage_service.is_configured():
        try:
            await asyncio.to_thread(
                storage_service.restore_video, row["user_id"], row["id"], video)
        except Exception as error:
            logger.warning("Cloud video restore for poster failed for %s (%s)", job_id, type(error).__name__)
    # Gated (see _FFMPEG_SLOT): a lazy poster from a History stampede must
    # queue behind an in-flight save encode rather than stack on it.
    async with _FFMPEG_SLOT:
        generated = await asyncio.to_thread(posters.generate_poster, video, poster)
    if generated and posters.is_usable_poster(poster):
        # Cache it in the cloud for the next instance, but serve now even if
        # the upload fails — the local file is what this response needs.
        if row:
            try:
                await asyncio.to_thread(
                    storage_service.upload_poster, row["user_id"], row["id"], poster)
            except Exception as error:
                logger.warning("Poster upload failed for %s (%s)", job_id, type(error).__name__)
        return FileResponse(
            str(poster),
            media_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=31536000, immutable"},
        )
    raise HTTPException(status_code=404, detail="Poster not found")


@app.get("/api/media/assets/{asset_id}")
async def serve_asset(asset_id: str, request: Request, sig: str = "", exp: str = ""):
    """
    Serve a character reference asset so the template card and Review step
    can display the founder's photo. Signed like videos so a raw URL cannot
    be guessed — the filename IS the asset id, and the signature proves
    the founder authorized this specific asset view.
    """
    if not GENERATED_ID_RE.match(asset_id or ""):
        raise HTTPException(status_code=404, detail="Asset not found")
    if not media_signing.verify(asset_id, exp, sig):
        raise HTTPException(status_code=404, detail="Asset not found")

    # First check if the asset exists in DB and belongs to the requester.
    # We don't have a user_id in the URL, so we derive owner from the row.
    row = await _fetch_one(
        "SELECT id, brand_profile_id, user_id, file_path, content_type "
        "FROM assets WHERE id = ?",
        (asset_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")

    # The asset belongs to a brand profile. The founder can view it if they
    # own that profile. Since the URL is signed, the signature itself is
    # the authorization — the signer must have known the asset id.
    # But we also verify the row exists and the file is present.
    path = await _ensure_asset_file(row)
    if path is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(
        str(path),
        media_type=row.get("content_type") or "image/jpeg",
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )


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

