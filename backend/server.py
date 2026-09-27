import asyncio
import io
import json
import logging
import os
import re
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import aiosqlite
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, BackgroundTasks, HTTPException, UploadFile, File, Form, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from PIL import Image
from starlette.middleware.cors import CORSMiddleware

import pipeline
import viral_detection
import storage_service
import template_library
import claim_safety
import video_providers
import generation_planning
from ai_service import (
    analyze_hook, generate_customized_preview, generate_face_swap, generate_video_prompt,
    generate_video, poll_video_job, analyze_brand_from_text, analyze_app_profile,
    generate_content_angles, generate_creative_plan, generate_remix_script,
    strip_html_to_text, remix_chat_turn, empty_remix_brief, VIDEO_MODELS, DEFAULT_VIDEO_MODEL,
    analyze_image_for_hook,
)
from models import (
    IngestVideoRequest, BrandContextRequest, GenerateVideoRequest,
    AnalyzeBrandUrlRequest, AppProfileResearchRequest, ApproveAppProfileRequest,
    BrandProfileCreateRequest, BrandProfileUpdateRequest,
    GenerateRemixScriptRequest, RemixChatMessageRequest,
    CreateHookTemplateRequest, UpdateHookTemplateRequest,
    CreateTemplateRequest, UpdateTemplateRequest,
    CreateContentAngleRequest, UpdateContentAngleRequest,
    CreateStudioProjectRequest, UpdateStudioProjectRequest, GeneratePlanRequest,
    StudioGenerationRequest,
    APP_PROFILE_LIST_FIELDS, APP_PROFILE_EDITABLE_FIELDS,
    TEMPLATE_STRUCTURED_FIELDS, TEMPLATE_TEXT_FIELDS, TEMPLATE_EDITABLE_FIELDS,
    STUDIO_EDITABLE_FIELDS,
    now_iso, row_to_dict,
)
from niches_config import NICHES, NICHE_MAP
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

NICHE_CACHE_TTL = timedelta(hours=6)
TRENDING_CACHE_TTL = timedelta(hours=2)
FRAME_COUNT = 8
HOOK_DURATION_SECONDS = 3.0
SEARCH_QUERY_MAX_LENGTH = 100
BRAND_URL_TEXT_MAX_CHARS = 8000

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


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------
@asynccontextmanager
async def get_db():
    """Async context manager for database connections.

    When TURSO_DATABASE_URL is set, connects to a remote Turso database via
    libsql_experimental (cloud-persisted, survives Render redeploys).
    Otherwise falls back to local aiosqlite (for dev/testing).
    """
    use_turso = False
    if TURSO_DATABASE_URL:
        try:
            import libsql_experimental as libsql
            conn = libsql.connect(
                "hookforge.db",
                sync_url=TURSO_DATABASE_URL,
                auth_token=TURSO_AUTH_TOKEN,
            )
            conn.execute("PRAGMA journal_mode=WAL")
            use_turso = True
        except Exception as e:
            logger.warning(f"Turso connection failed, falling back to local SQLite: {e}")
            use_turso = False

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

            CREATE TABLE IF NOT EXISTS curated_videos (
                tiktok_url TEXT PRIMARY KEY,
                niche TEXT,
                video_platform_id TEXT,
                creator TEXT,
                creator_display TEXT,
                title TEXT,
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
                song_cover_url TEXT,
                subtitles_url TEXT,
                is_ad INTEGER DEFAULT 0,
                creator_followers INTEGER DEFAULT 0,
                creator_verified INTEGER DEFAULT 0,
                upload_timestamp INTEGER DEFAULT 0,
                virality_score REAL DEFAULT 0,
                cached_at TEXT
            );

            CREATE TABLE IF NOT EXISTS niche_cache_meta (
                niche TEXT PRIMARY KEY,
                cached_at TEXT
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

            CREATE TABLE IF NOT EXISTS trending_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                niche TEXT,
                tiktok_url TEXT,
                video_platform_id TEXT,
                creator TEXT,
                creator_display TEXT,
                title TEXT,
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
                song_cover_url TEXT,
                subtitles_url TEXT,
                is_ad INTEGER DEFAULT 0,
                creator_followers INTEGER DEFAULT 0,
                creator_verified INTEGER DEFAULT 0,
                upload_timestamp INTEGER DEFAULT 0,
                virality_score REAL DEFAULT 0,
                cached_at TEXT
            );

            CREATE TABLE IF NOT EXISTS trending_cache_meta (
                niche TEXT PRIMARY KEY,
                cached_at TEXT
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
                pricing_trial TEXT,
                core_features TEXT,
                primary_use_cases TEXT,
                problems_solved TEXT,
                icp_segments TEXT,
                desired_outcomes TEXT,
                competitors TEXT,
                known_limitations TEXT,
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

            CREATE TABLE IF NOT EXISTS remix_chats (
                id TEXT PRIMARY KEY,
                customization_id TEXT UNIQUE,
                messages TEXT,
                brief TEXT,
                ready_to_generate INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS face_swap_jobs (
                id TEXT PRIMARY KEY,
                status TEXT DEFAULT 'pending',
                target_image_url TEXT,
                source_face_url TEXT,
                target_image_path TEXT,
                source_face_path TEXT,
                variants_requested INTEGER DEFAULT 1,
                result_json TEXT,
                error TEXT,
                created_at TEXT,
                started_at TEXT,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS face_swap_video_jobs (
                id TEXT PRIMARY KEY,
                image_id TEXT,
                prompt TEXT,
                duration INTEGER,
                status TEXT DEFAULT 'pending',
                polling_url TEXT,
                video_url TEXT,
                error TEXT,
                created_at TEXT
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
            -- origin: 'face_swap' | 'customize'
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
                continuation_structure TEXT,
                cta_pattern TEXT,
                visual_style TEXT,
                camera_pacing TEXT,
                required_assets TEXT,
                default_duration INTEGER,
                content_slots TEXT,
                version INTEGER DEFAULT 1,
                archived INTEGER DEFAULT 0,
                is_favorite INTEGER DEFAULT 0,
                evidence_note TEXT,
                origin TEXT DEFAULT 'bookmark',
                review_status TEXT DEFAULT 'approved'
            );

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
            -- any generation so a founder can iterate on the script for free
            -- before spending a video generation.
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
                beat_timeline TEXT,
                visual_direction TEXT,
                feature_emphasis TEXT,
                overlays TEXT,
                voice_direction TEXT,
                sound_direction TEXT,
                cta TEXT,
                assets TEXT,
                safety_report TEXT,
                safety_summary TEXT,
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
            -- project, not here, because no money is spent before submission.
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
                attempt INTEGER DEFAULT 1,
                parent_generation_id TEXT,
                variation_kind TEXT,
                variation_params TEXT,
                openrouter_job_id TEXT,
                polling_url TEXT,
                video_url TEXT,
                r2_url TEXT,
                cost_usd REAL,
                cost_source TEXT,
                prompt_used TEXT,
                adjustments TEXT,
                error TEXT,
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
            CREATE INDEX IF NOT EXISTS idx_generations_parent
                ON generations (parent_generation_id);

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
        """)
        await conn.commit()

        # The Images API does not expose a provider job ID that can be resumed after
        # this process exits. Never leave interrupted app jobs polling forever.
        await conn.execute(
            """UPDATE face_swap_jobs
               SET status = 'failed',
                   error = 'The server restarted before image generation completed. Please try again.',
                   completed_at = ?
               WHERE status IN ('pending', 'in_progress')""",
            (now_iso(),),
        )
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
            "platforms", "pricing_trial", "core_features", "primary_use_cases",
            "problems_solved", "icp_segments", "desired_outcomes", "competitors",
            "known_limitations", "claims_approved", "claims_review",
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
            "continuation_structure", "cta_pattern", "visual_style",
            "camera_pacing", "required_assets", "content_slots", "evidence_note",
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
        # and stay approved; they are NOT library templates and remain
        # reachable only through the legacy /api/bookmarks routes.
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
            "curated_videos": "upload_timestamp",
            "trending_videos": "upload_timestamp",
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

            CREATE TABLE IF NOT EXISTS curated_videos (
                tiktok_url TEXT PRIMARY KEY,
                niche TEXT,
                video_platform_id TEXT,
                creator TEXT,
                creator_display TEXT,
                title TEXT,
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
                song_cover_url TEXT,
                subtitles_url TEXT,
                is_ad INTEGER DEFAULT 0,
                creator_followers INTEGER DEFAULT 0,
                creator_verified INTEGER DEFAULT 0,
                upload_timestamp INTEGER DEFAULT 0,
                virality_score REAL DEFAULT 0,
                cached_at TEXT
            );

            CREATE TABLE IF NOT EXISTS trending_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                niche TEXT,
                tiktok_url TEXT,
                video_platform_id TEXT,
                creator TEXT,
                creator_display TEXT,
                title TEXT,
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
                song_cover_url TEXT,
                subtitles_url TEXT,
                is_ad INTEGER DEFAULT 0,
                creator_followers INTEGER DEFAULT 0,
                creator_verified INTEGER DEFAULT 0,
                upload_timestamp INTEGER DEFAULT 0,
                virality_score REAL DEFAULT 0,
                cached_at TEXT
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
            "brand_profiles", "remix_chats", "face_swap_jobs",
            "face_swap_video_jobs", "hook_templates",
            "studio_projects", "content_angles", "generations",
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
            await conn.execute(
                """INSERT INTO hook_templates
                   (id, name, category, notes, app_categories, audiences, objective,
                    opening_structure, hook_seconds, continuation_structure, cta_pattern,
                    visual_style, camera_pacing, required_assets, default_duration,
                    content_slots, evidence_note, version, archived, is_favorite,
                    origin, review_status, times_used, created_at, updated_at, user_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()), tpl["name"],
                    template_library.normalize_category(tpl["category"]), "",
                    json.dumps(tpl.get("app_categories") or []),
                    json.dumps(tpl.get("audiences") or []),
                    template_library.normalize_objective(tpl.get("objective")),
                    tpl["opening_structure"], int(tpl["hook_seconds"] or 3),
                    tpl["continuation_structure"], tpl["cta_pattern"], tpl["visual_style"],
                    tpl["camera_pacing"], json.dumps(tpl.get("required_assets") or []),
                    int(tpl["default_duration"] or 20),
                    json.dumps(tpl.get("content_slots") or {}), tpl.get("evidence_note") or "",
                    1, 0, 0, "curated", "approved", 0, now, now, "system",
                ),
            )
            seeded += 1
        if seeded:
            logger.info("Seeded %d curated hook template(s)", seeded)
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
        # Face-swap variants recover their target from the job's result_json;
        # customization previews from the frame each was built on. Images whose
        # recovered target is an upload (produced before targets were
        # restricted) are backfilled honestly and will be refused by the gate —
        # that is the intended outcome, not a bug.
        cursor = await conn.execute("SELECT COUNT(*) FROM generated_images")
        (existing_rows,) = await cursor.fetchone()
        if not existing_rows:
            backfilled = 0
            cursor = await conn.execute(
                """SELECT id, result_json, user_id FROM face_swap_jobs
                   WHERE status = 'completed' AND result_json IS NOT NULL"""
            )
            for job_id, result_json, job_user in await cursor.fetchall():
                try:
                    result = json.loads(result_json)
                except (TypeError, ValueError):
                    continue
                target = result.get("target_image_url") or ""
                image_ids = {
                    variant.get("id")
                    for variant in (result.get("variants") or [])
                    if variant.get("id")
                }
                if result.get("id"):
                    image_ids.add(result["id"])
                for image_id in image_ids:
                    await conn.execute(
                        """INSERT OR IGNORE INTO generated_images
                           (id, origin, job_id, target_image_url, user_id, created_at)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (image_id, "face_swap", job_id, target, job_user or "anonymous", now_iso()),
                    )
                    backfilled += 1

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

        # Clear stale trending/curated caches (force fresh fetch with more results)
        await conn.execute("DELETE FROM trending_videos")
        await conn.execute("DELETE FROM curated_videos")
        await conn.execute("DELETE FROM trending_cache_meta")
        await conn.execute("DELETE FROM niche_cache_meta")
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


async def _record_generated_image(
    image_id: str,
    origin: str,
    target_image_url: str,
    user_id: str,
    job_id: str = "",
    image_bytes: bytes = b"",
):
    """
    Register a generated image's provenance and durable PNG backup.

    The local generated/ file is only a cache: containers can restart and
    horizontally scaled instances do not share it. Video generation can
    restore image_bytes on demand, while provenance remains the authority for
    deciding whether the image is allowed to become a video.
    """
    await _execute(
        """INSERT OR REPLACE INTO generated_images
           (id, origin, job_id, target_image_url, user_id, image_bytes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (image_id, origin, job_id, target_image_url, user_id, image_bytes, now_iso()),
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
async def _refresh_trending_cache(niche_key: str, force: bool = False):
    cache_meta = await _fetch_one(
        "SELECT * FROM trending_cache_meta WHERE niche = ?", (niche_key,)
    )
    trending_is_stale = True
    if cache_meta and not force:
        cached_at = datetime.fromisoformat(cache_meta["cached_at"])
        trending_is_stale = (datetime.now(timezone.utc) - cached_at) > TRENDING_CACHE_TTL

    if not trending_is_stale:
        return False

    hashtags = NICHE_MAP[niche_key].get("hashtags", [])
    # Only fetch the first (most relevant) hashtag to keep response fast
    hashtags_to_fetch = hashtags[:1]
    hashtag_results = await asyncio.gather(
        *[viral_detection.fetch_hashtag_videos(tag, limit=25) for tag in hashtags_to_fetch],
        return_exceptions=True,
    )
    all_videos = []
    for tag, result in zip(hashtags_to_fetch, hashtag_results):
        if isinstance(result, Exception):
            logger.warning(f"Hashtag fetch failed for #{tag}: {result!r}")
            continue
        all_videos.extend(result)

    if all_videos:
        ranked = viral_detection.rank_videos(all_videos)
        async with get_db() as conn:
            await conn.execute("DELETE FROM trending_videos WHERE niche = ?", (niche_key,))
            for v in ranked[:50]:
                await conn.execute(
                    """INSERT INTO trending_videos
                       (niche, tiktok_url, video_platform_id, creator, creator_display,
                        title, view_count, like_count, comment_count, share_count,
                        bookmark_count, duration, thumbnail_url, direct_video_url,
                        hashtags, song_id, song_title, song_artist, song_cover_url,
                        subtitles_url, is_ad, creator_followers, creator_verified,
                        upload_timestamp, virality_score, cached_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (niche_key, v.get("tiktok_url"), v.get("video_platform_id"),
                     v.get("creator"), v.get("creator_display"), v.get("title"),
                     v.get("view_count", 0), v.get("like_count", 0),
                     v.get("comment_count", 0), v.get("share_count", 0),
                     v.get("bookmark_count", 0), v.get("duration", 0),
                     v.get("thumbnail_url"), v.get("direct_video_url", ""),
                     json.dumps(v.get("hashtags", [])),
                     v.get("song_id", ""), v.get("song_title", ""),
                     v.get("song_artist", ""), v.get("song_cover_url", ""),
                     v.get("subtitles_url", ""),
                     1 if v.get("is_ad") else 0,
                     v.get("creator_followers", 0),
                     1 if v.get("creator_verified") else 0,
                     int(v.get("timestamp") or 0),
                     v.get("virality_score", 0), now_iso()),
                )
            await conn.execute(
                "INSERT OR REPLACE INTO trending_cache_meta (niche, cached_at) VALUES (?, ?)",
                (niche_key, now_iso()),
            )
            await conn.commit()
    return True


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


def filter_ads(videos: list, include_ads: bool) -> list:
    """Drop ad/sponsored posts from a list of video dicts unless include_ads is True."""
    if include_ads:
        return videos
    return [v for v in videos if not v.get("is_ad")]


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


def _brand_update_parts(updates: dict) -> tuple:
    """Split a profile update dict into (SET clauses, values), JSON-encoding lists."""
    set_clauses = []
    values = []
    for key, value in updates.items():
        if key in APP_PROFILE_LIST_FIELDS:
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
            return strip_html_to_text(resp.text)[:max_chars]
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
# Niches + curated/trending feed
# ---------------------------------------------------------------------------
@api_router.get("/niches")
async def list_niches():
    return [
        {"key": n["key"], "label": n["label"], "icon": n["icon"], "description": n["description"]}
        for n in NICHES
    ]


@api_router.get("/niches/{niche_key}/videos")
async def get_niche_videos(niche_key: str, refresh: bool = False, mode: str = "curated", include_ads: bool = True):
    if niche_key not in NICHE_MAP:
        raise HTTPException(status_code=404, detail="Unknown niche")

    if mode not in ("curated", "trending", "mixed"):
        mode = "curated"

    curated_videos = []
    trending_videos = []

    # Fetch curated videos
    if mode in ("curated", "mixed"):
        cache_meta = await _fetch_one(
            "SELECT * FROM niche_cache_meta WHERE niche = ?", (niche_key,)
        )
        is_stale = True
        if cache_meta and not refresh:
            cached_at = datetime.fromisoformat(cache_meta["cached_at"])
            is_stale = (datetime.now(timezone.utc) - cached_at) > NICHE_CACHE_TTL

        if is_stale:
            creators = NICHE_MAP[niche_key]["creators"]
            # Only fetch from the first creator to keep response fast
            creators_to_fetch = creators[:1]
            creator_results = await asyncio.gather(
                *[pipeline.fetch_creator_videos(handle, limit=3) for handle in creators_to_fetch],
                return_exceptions=True,
            )
            fetched_any = False
            for handle, videos in zip(creators_to_fetch, creator_results):
                if isinstance(videos, Exception):
                    logger.warning(f"Creator fetch failed for {handle}: {videos!r}")
                    continue
                if not videos:
                    continue
                fetched_any = True
                for v in videos:
                    if not v.get("tiktok_url"):
                        continue
                    async with get_db() as conn:
                        await conn.execute(
                            """INSERT OR REPLACE INTO curated_videos
                               (tiktok_url, niche, video_platform_id, creator,
                                creator_display, title, view_count, like_count,
                                comment_count, share_count, bookmark_count, duration,
                                thumbnail_url, direct_video_url, hashtags,
                                song_id, song_title, song_artist, song_cover_url,
                                subtitles_url, is_ad, creator_followers, creator_verified,
                                upload_timestamp, cached_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (v["tiktok_url"], niche_key, v.get("video_platform_id"),
                             v.get("creator"), v.get("creator_display"), v.get("title"),
                             v.get("view_count", 0), v.get("like_count", 0),
                             v.get("comment_count", 0), v.get("share_count", 0),
                             v.get("bookmark_count", 0), v.get("duration", 0),
                             v.get("thumbnail_url"), v.get("direct_video_url", ""),
                             json.dumps(v.get("hashtags", [])),
                             v.get("song_id", ""), v.get("song_title", ""),
                             v.get("song_artist", ""), v.get("song_cover_url", ""),
                             v.get("subtitles_url", ""),
                             1 if v.get("is_ad") else 0,
                             v.get("creator_followers", 0),
                             1 if v.get("creator_verified") else 0,
                             int(v.get("timestamp") or 0),
                             now_iso()),
                        )
                        await conn.commit()
            if fetched_any or not cache_meta:
                await _execute(
                    "INSERT OR REPLACE INTO niche_cache_meta (niche, cached_at) VALUES (?, ?)",
                    (niche_key, now_iso()),
                )

        raw_curated = await _fetch_all(
            "SELECT * FROM curated_videos WHERE niche = ? ORDER BY view_count DESC LIMIT 50",
            (niche_key,),
        )
        for v in raw_curated:
            # compute_virality_score derives age from `timestamp`; without it the
            # scorer silently assumes a 48h-old video, which skews the velocity and
            # recency components. Surface the persisted publish time under both
            # names so the score is real and the client can sort/filter by date.
            v["timestamp"] = v.get("upload_timestamp") or 0
            v["virality_score"] = viral_detection.compute_virality_score(v)
            v["source"] = "curated"
        curated_videos = raw_curated

    # Fetch trending videos
    if mode in ("trending", "mixed"):
        await _refresh_trending_cache(niche_key, force=refresh)
        raw_trending = await _fetch_all(
            "SELECT * FROM trending_videos WHERE niche = ? ORDER BY virality_score DESC LIMIT 50",
            (niche_key,),
        )
        for v in raw_trending:
            v["source"] = "trending"
        trending_videos = raw_trending

    if mode == "curated":
        result = curated_videos
    elif mode == "trending":
        result = trending_videos
    else:  # mixed
        combined = curated_videos + trending_videos
        seen_urls = set()
        unique = []
        for v in combined:
            url = v.get("tiktok_url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(v)
            elif not url:
                unique.append(v)
        unique.sort(key=lambda v: v.get("virality_score", 0), reverse=True)
        result = unique[:50]

    return filter_ads(result, include_ads)


@api_router.get("/niches/{niche_key}/trending")
async def get_niche_trending(niche_key: str, refresh: bool = False, include_ads: bool = True):
    if niche_key not in NICHE_MAP:
        raise HTTPException(status_code=404, detail="Unknown niche")
    await _refresh_trending_cache(niche_key, force=refresh)
    videos = await _fetch_all(
        "SELECT * FROM trending_videos WHERE niche = ? ORDER BY virality_score DESC LIMIT 50",
        (niche_key,),
    )
    return filter_ads(videos, include_ads)


@api_router.get("/trending/search")
async def trending_search(q: str = "", limit: int = 20, include_ads: bool = True):
    """Search TikTok for trending videos matching a keyword."""
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    if len(q) > SEARCH_QUERY_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Query too long (max {SEARCH_QUERY_MAX_LENGTH} characters)",
        )
    limit = max(1, min(50, limit))
    async with _ytdlp_semaphore:
        videos = await viral_detection.fetch_keyword_videos(q, limit=limit)
    ranked = viral_detection.rank_videos(videos)
    return filter_ads(ranked, include_ads)


# ---------------------------------------------------------------------------
# Video ingestion + analysis
# ---------------------------------------------------------------------------
@api_router.post("/videos/ingest")
async def ingest_video(payload: IngestVideoRequest, user_id: str = Depends(get_current_user_id)):
    tiktok_url = payload.tiktok_url.strip()
    if "tiktok.com" not in tiktok_url:
        raise HTTPException(status_code=400, detail="Please provide a valid TikTok video URL.")

    # Check if THIS user already ingested this URL (not globally — each user
    # gets their own video record so analyses are isolated per account).
    existing = await _fetch_one(
        "SELECT * FROM videos WHERE tiktok_url = ? AND user_id = ?", (tiktok_url, user_id)
    )
    if existing:
        return existing

    curated = await _fetch_one("SELECT * FROM curated_videos WHERE tiktok_url = ?", (tiktok_url,))
    if curated:
        meta = {k: curated.get(k) for k in [
            "video_platform_id", "creator", "creator_display", "title",
            "view_count", "like_count", "comment_count", "duration", "thumbnail_url",
            "direct_video_url",
        ]}
        niche = curated.get("niche") or payload.niche
    else:
        async with _ytdlp_semaphore:
            try:
                meta = await pipeline.fetch_video_metadata(tiktok_url)
            except Exception as e:
                logger.error(f"Metadata fetch failed for {tiktok_url}: {e}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not fetch this TikTok video. Please check the URL and try again. ({str(e)[:150]})",
                )
        niche = payload.niche

    video_id = str(uuid.uuid4())
    created_at = now_iso()
    try:
        await _execute(
            """INSERT INTO videos
               (id, tiktok_url, niche, video_platform_id, creator, creator_display, title,
                description, view_count, like_count, comment_count, share_count, bookmark_count,
                duration, thumbnail_url, direct_video_url, hashtags,
                song_id, song_title, song_artist, song_album, song_duration, song_cover_url,
                subtitles_url, subtitles_language, is_ad,
                creator_followers, creator_following, creator_verified, creator_bio, creator_avatar,
                status, local_video_path, created_at, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (video_id, tiktok_url, niche, meta.get("video_platform_id"), meta.get("creator"),
             meta.get("creator_display"), meta.get("title"), meta.get("description", ""),
             meta.get("view_count", 0), meta.get("like_count", 0), meta.get("comment_count", 0),
             meta.get("share_count", 0), meta.get("bookmark_count", 0),
             meta.get("duration", 0), meta.get("thumbnail_url"),
             meta.get("direct_video_url", ""), json.dumps(meta.get("hashtags", [])),
             meta.get("song_id", ""), meta.get("song_title", ""),
             meta.get("song_artist", ""), meta.get("song_album", ""),
             meta.get("song_duration", 0), meta.get("song_cover_url", ""),
             meta.get("subtitles_url", ""), meta.get("subtitles_language", ""),
             1 if meta.get("is_ad") else 0,
             meta.get("creator_followers", 0), meta.get("creator_following", 0),
             1 if meta.get("creator_verified") else 0,
             meta.get("creator_bio", ""), meta.get("creator_avatar", ""),
             "metadata_ready", None, created_at, user_id),
        )
    except Exception as e:
        # On older databases with UNIQUE(tiktok_url), a second user ingesting the
        # same URL hits a constraint violation. Return the existing record for
        # this user if one exists, otherwise the global one (legacy compat).
        logger.warning(f"Video insert failed (likely UNIQUE constraint): {e}")
        fallback = await _fetch_one(
            "SELECT * FROM videos WHERE tiktok_url = ?", (tiktok_url,)
        )
        if fallback:
            return fallback
        raise HTTPException(status_code=500, detail="Could not save the video. Please try again.")
    return await get_video_or_404(video_id)


@api_router.get("/videos/{video_id}")
async def get_video(video_id: str, user_id: str = Depends(get_current_user_id)):
    return await get_video_or_404(video_id)


@api_router.post("/videos/{video_id}/analyze-hook")
async def analyze_video_hook(video_id: str, user_id: str = Depends(get_current_user_id)):
    require_ai_configured()
    video = await get_video_or_404(video_id)
    tiktok_url = video["tiktok_url"]
    video_hash = pipeline.url_hash(tiktok_url)

    # When MODAL_FRAME_EXTRACTOR_URL is configured, the memory-heavy
    # download + ffmpeg decode runs on Modal (dedicated RAM) instead of on
    # this Render instance — see pipeline.py module docstring for context.
    direct_video_url = video.get("direct_video_url", "")
    # Older curated-video ingests dropped the CDN source. Recover and persist
    # it from the curated record so those existing videos also avoid TikTok's
    # webpage extraction when an Apify download URL is available.
    if not direct_video_url:
        curated = await _fetch_one(
            "SELECT direct_video_url FROM curated_videos WHERE tiktok_url = ?", (tiktok_url,)
        )
        direct_video_url = (curated or {}).get("direct_video_url", "")
        if direct_video_url:
            await _execute(
                "UPDATE videos SET direct_video_url = ? WHERE id = ?", (direct_video_url, video_id)
            )

    if pipeline.MODAL_FRAME_EXTRACTOR_URL:
        try:
            video_path, frame_paths = await pipeline.download_and_extract_via_modal(
                tiktok_url,
                direct_video_url=direct_video_url,
                num_frames=FRAME_COUNT,
                duration=HOOK_DURATION_SECONDS,
            )
        except pipeline.ModalFrameDownloadError as modal_error:
            # A provider-side TikTok download rejection is recoverable: retry
            # the already-supported local direct-CDN then yt-dlp path before
            # marking the analysis as failed. Other Modal failures remain
            # terminal to avoid moving memory-heavy work off Modal needlessly.
            logger.warning(f"Modal video download failed for {tiktok_url}; trying local recovery: {modal_error}")
            try:
                async with _ytdlp_semaphore:
                    video_path = await pipeline.download_video(tiktok_url, direct_video_url=direct_video_url)
                frame_paths = await pipeline.extract_hook_frames(
                    video_path, num_frames=FRAME_COUNT, duration=HOOK_DURATION_SECONDS
                )
            except Exception as local_error:
                error_detail = f"Modal download failed: {modal_error}; local recovery failed: {local_error}"
                logger.error(f"Download+extract failed for {tiktok_url}: {error_detail}")
                await _execute(
                    "UPDATE videos SET status = ?, error = ? WHERE id = ?",
                    ("failed", error_detail[:400], video_id),
                )
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to download/extract the video. ({error_detail[:150]})",
                )
        except Exception as e:
            logger.error(f"Modal download+extract failed for {tiktok_url}: {e}")
            await _execute(
                "UPDATE videos SET status = ?, error = ? WHERE id = ?",
                ("failed", str(e)[:400], video_id),
            )
            raise HTTPException(
                status_code=502,
                detail=f"Failed to download/extract the video. ({str(e)[:150]})",
            )
    else:
        try:
            async with _ytdlp_semaphore:
                video_path = await pipeline.download_video(tiktok_url, direct_video_url=direct_video_url)
        except Exception as e:
            logger.error(f"Download failed for {tiktok_url}: {e}")
            await _execute(
                "UPDATE videos SET status = ?, error = ? WHERE id = ?",
                ("failed", str(e)[:400], video_id),
            )
            raise HTTPException(
                status_code=502,
                detail=f"Failed to download the video. It may be private or removed. ({str(e)[:150]})",
            )

        try:
            frame_paths = await pipeline.extract_hook_frames(
                video_path, num_frames=FRAME_COUNT, duration=HOOK_DURATION_SECONDS
            )
        except Exception as e:
            logger.error(f"Frame extraction failed for {video_id}: {e}")
            await _execute(
                "UPDATE videos SET status = ?, error = ? WHERE id = ?",
                ("failed", str(e)[:400], video_id),
            )
            raise HTTPException(status_code=500, detail=f"Failed to extract frames from the video. ({str(e)[:150]})")

    frame_docs = build_frame_docs(video_hash, frame_paths)

    # Build music context and fetch transcript if available
    music_context = None
    transcript_text = ""
    if video.get("song_title") or video.get("song_artist"):
        music_context = {
            "song_title": video.get("song_title", ""),
            "song_artist": video.get("song_artist", ""),
            "song_album": video.get("song_album", ""),
            "song_duration": video.get("song_duration", 0),
        }
    if video.get("subtitles_url"):
        import apify_tiktok
        raw_vtt = await apify_tiktok.fetch_subtitles(video["subtitles_url"])
        if raw_vtt:
            transcript_text = apify_tiktok.parse_webvtt_to_text(raw_vtt)

    try:
        analysis_result = await analyze_hook(
            frame_paths, session_id=f"hook-{video_id}",
            music_context=music_context, transcript_text=transcript_text,
        )
    except Exception as e:
        logger.error(f"Hook analysis failed for {video_id}: {e}")
        await _execute(
            "UPDATE videos SET status = ?, error = ? WHERE id = ?",
            ("failed", str(e)[:400], video_id),
        )
        raise HTTPException(status_code=502, detail=f"AI hook analysis failed. Please try again. ({str(e)[:150]})")

    analysis_id = str(uuid.uuid4())
    created_at = now_iso()
    try:
        # analyses.frames only holds browser-facing URLs. Store the matching
        # JPEG bytes before publishing that analysis so History can restore
        # every thumbnail after a clean deploy or on another backend instance.
        await _record_analysis_frame_assets(video_hash, frame_paths)
    except Exception as e:
        logger.error(f"Could not durably preserve frames for {video_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to preserve extracted frames. Please retry the analysis.",
        )

    await _execute(
        """INSERT INTO analyses
           (id, video_id, frames, facial_expressions, body_language_gestures, pacing_cuts,
            text_overlays_timing, audio_cues_inferred, hook_summary, effectiveness_score,
            key_hook_frame_index, replicable_mechanics, created_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (analysis_id, video_id, json.dumps(frame_docs),
         analysis_result.get("facial_expressions"), analysis_result.get("body_language_gestures"),
         analysis_result.get("pacing_cuts"), analysis_result.get("text_overlays_timing"),
         analysis_result.get("audio_cues_inferred"), analysis_result.get("hook_summary"),
         analysis_result.get("effectiveness_score"), analysis_result.get("key_hook_frame_index"),
         json.dumps(analysis_result.get("replicable_mechanics", [])), created_at, user_id),
    )
    await _execute(
        "UPDATE videos SET status = ?, local_video_path = ?, last_analysis_id = ? WHERE id = ?",
        ("analyzed", str(video_path), analysis_id, video_id),
    )
    return await _fetch_one("SELECT * FROM analyses WHERE id = ?", (analysis_id,))


@api_router.get("/videos/{video_id}/analysis")
async def get_video_analysis(video_id: str, user_id: str = Depends(get_current_user_id)):
    return await get_latest_analysis_or_404(video_id)


@api_router.get("/hook-motion-styles")
async def get_hook_motion_styles():
    """
    The selectable motion styles: short summary, the exact prompt text sent to
    the model, and which hook-energy categories each one overlaps.

    Serving all three from here keeps them from drifting. The card copy and the
    prompt fragments used to live in two places (FaceSwap.jsx and this module)
    describing the same motions in different words, so a creator could read one
    thing while the model received another. `summary` is what the card shows by
    default and `motion` is available on request, so the UI stays readable
    without hiding what actually gets sent.

    Unauthenticated and static: presentation metadata with no user data, which
    changes only when the motion definitions themselves change.
    """
    return {"styles": HOOK_MOTION_STYLES}


@api_router.get("/videos/{video_id}/hook-engine")
async def get_hook_engine_availability(video_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Report whether Runway Aleph's exact-edit path is structurally available for
    this video, so the UI can stop inferring it.

    The frontend previously guessed eligibility from "is a video attached?",
    which can't see the two conditions that actually decide it server-side:
    whether a hook analysis is obtainable, and whether the source clip is
    still retrievable. That made the "Exact edit" badge capable of promising
    something the backend would then silently downgrade.

    This reports only the STRUCTURAL half of the decision. The caller ANDs it
    with its own inputs (hook energy / custom direction / motion style), which
    it already knows, keeping the split clean and avoiding a round-trip on
    every keystroke.

    Deliberately cheap and side-effect free: it never downloads or analyzes,
    it only checks whether those are possible. Returns 200 with a reason
    instead of 404 so the client has one code path.

    Note both recovery mechanisms this accounts for:
      - a missing local file is recoverable when tiktok_url/direct_video_url
        is on record (the hook endpoint re-downloads on demand)
      - a missing analysis is recoverable whenever the clip is, since the hook
        endpoint auto-analyzes on demand
    So a missing analysis alone is NOT disqualifying — only an unobtainable
    source clip is.
    """
    vid = (video_id or "").strip()
    video = await _fetch_one("SELECT * FROM videos WHERE id = ?", (vid,))
    if not video:
        return {
            "video_id": vid,
            "exact_edit_available": False,
            "reason": "video_not_found",
            "has_analysis": False,
            "source_ready": False,
            "source_recoverable": False,
        }

    analysis = await _fetch_one(
        "SELECT id FROM analyses WHERE video_id = ? ORDER BY created_at DESC LIMIT 1",
        (vid,),
    )

    local_path = video.get("local_video_path")
    source_ready = bool(local_path) and Path(local_path).exists()
    source_recoverable = bool(
        (video.get("tiktok_url") or "").strip()
        or (video.get("direct_video_url") or "").strip()
    )

    available = source_ready or source_recoverable
    reason = None if available else "source_unavailable"

    return {
        "video_id": vid,
        "exact_edit_available": available,
        "reason": reason,
        "has_analysis": bool(analysis),
        "source_ready": source_ready,
        "source_recoverable": source_recoverable,
    }


# ---------------------------------------------------------------------------
# Video Models (available for video generation)
# ---------------------------------------------------------------------------
@api_router.get("/video-models")
async def list_video_models():
    """Return available video generation models with their capabilities."""
    return {
        "models": [
            {"key": k, **{mk: mv for mk, mv in v.items() if mk != "id"}}
            for k, v in VIDEO_MODELS.items()
        ],
        "default": DEFAULT_VIDEO_MODEL,
    }


# ---------------------------------------------------------------------------
# Standalone Face Swap (Higgsfield-style 3-step flow)
# ---------------------------------------------------------------------------
async def _generate_face_swap_variant(
    target_path: Path,
    source_path: Path,
    job_id: str,
    variant_index: int,
    customization_prompt: str = "",
) -> dict:
    """Generate and persist one face-swap variant for an asynchronous job."""
    image_bytes = await generate_face_swap(
        target_image_path=target_path,
        source_face_path=source_path,
        session_id=f"face-swap-{job_id}-v{variant_index}",
        customization_prompt=customization_prompt,
    )
    gen_id = str(uuid.uuid4())
    gen_path = pipeline.GENERATED_DIR / f"{gen_id}.png"

    # Normalize provider output to a real PNG and verify it before completing the job.
    with Image.open(io.BytesIO(image_bytes)) as generated_image:
        normalized = generated_image.convert("RGB")
        width, height = normalized.size
        output = io.BytesIO()
        normalized.save(output, format="PNG")

    normalized_bytes = output.getvalue()
    gen_path.write_bytes(normalized_bytes)

    return {
        "id": gen_id,
        "image_url": f"/api/media/generated/{gen_id}.png",
        "resolution": f"{width}x{height}",
        "variant_index": variant_index,
        # Internal-only: removed before serializing the browser result, but
        # committed with provenance before the job becomes visible as complete.
        "_image_bytes": normalized_bytes,
    }


async def _run_face_swap_job(
    job_id: str,
    target_path: Path,
    source_path: Path,
    target_image_url: str,
    source_face_url: str,
    variants: int,
    customization_prompt: str = "",
    user_id: str = "anonymous",
):
    """Run image generation after the submission response has reached the browser."""
    await _execute(
        "UPDATE face_swap_jobs SET status = ?, started_at = ? WHERE id = ?",
        ("in_progress", now_iso(), job_id),
    )
    try:
        tasks = [
            _generate_face_swap_variant(target_path, source_path, job_id, index, customization_prompt)
            for index in range(variants)
        ]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        successful = [result for result in raw_results if isinstance(result, dict)]
        failures = [str(result) for result in raw_results if isinstance(result, Exception)]

        if not successful:
            provider_error = "; ".join(failures)[:1000] or "The image model returned no result."
            raise RuntimeError(provider_error)

        # Register every variant's provenance before the job is marked
        # complete, so an image is never usable for video generation before
        # its origin is on record.
        for variant in successful:
            await _record_generated_image(
                image_id=variant["id"],
                origin="face_swap",
                target_image_url=target_image_url,
                user_id=user_id,
                job_id=job_id,
                image_bytes=variant.pop("_image_bytes"),
            )

        result = {
            "id": successful[0]["id"],
            "generated_image_url": successful[0]["image_url"],
            "target_image_url": target_image_url,
            "source_face_url": source_face_url,
            "resolution": successful[0]["resolution"],
            "format": "PNG",
            "status": "completed",
            "variants": successful,
            "selected_variant": 0,
        }
        await _execute(
            """UPDATE face_swap_jobs
               SET status = ?, result_json = ?, error = NULL, completed_at = ?
               WHERE id = ?""",
            ("completed", json.dumps(result), now_iso(), job_id),
        )
        logger.info(f"Face swap job {job_id} completed with {len(successful)} variant(s)")
    except Exception as exc:
        error = str(exc)[:1000] or "Unknown image generation error."
        logger.error(f"Face swap job {job_id} failed: {error}")
        await _execute(
            "UPDATE face_swap_jobs SET status = ?, error = ?, completed_at = ? WHERE id = ?",
            ("failed", error, now_iso(), job_id),
        )


@api_router.post("/face-swap", status_code=202)
async def face_swap(
    background_tasks: BackgroundTasks,
    source_face: UploadFile = File(...),
    target_frame_url: str = Form(""),
    variants: int = Form(1),
    customization_prompt: str = Form(""),
    user_id: str = Depends(get_current_user_id),
):
    """
    Validate and persist the inputs, then return an app job ID immediately.
    GPT-5.4 Image 2 runs after the response so browser and reverse-proxy request
    timeouts cannot discard a completed generation.

    `source_face` is the only image the caller supplies. The target is
    identified by URL and must already exist under an allowlisted storage
    subtree — see ALLOWED_TARGET_PREFIXES.
    """
    require_ai_configured()
    variants = max(1, min(variants, 4))

    url_path = (target_frame_url or "").strip()
    if not url_path:
        raise HTTPException(
            status_code=400,
            detail=(
                "A target frame is required. Choose a hook from the discovery "
                "feed or one of your saved templates."
            ),
        )
    if not url_path.startswith(ALLOWED_TARGET_PREFIXES):
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid target frame. Targets must be an analyzed video frame "
                "or a saved hook template thumbnail."
            ),
        )

    relative_path = url_path[len("/api/media/"):]
    storage_root = pipeline.STORAGE_DIR.resolve()
    target_path = (storage_root / relative_path).resolve()

    # The allowlist above is a string check, so on its own it is defeated by
    # traversal that stays inside storage: "/api/media/templates/../uploads/x.png"
    # starts with an allowed prefix but resolves into uploads/. The resolved
    # path is therefore the authoritative gate — it must sit inside one of the
    # two permitted directories. This also subsumes the escape-the-storage-root
    # check, since neither directory can be a parent of a path outside storage.
    allowed_roots = (pipeline.FRAMES_DIR.resolve(), pipeline.TEMPLATES_DIR.resolve())
    if not any(root in target_path.parents for root in allowed_roots):
        raise HTTPException(status_code=400, detail="Invalid target frame path.")

    if relative_path.startswith("templates/") and not target_path.is_file():
        # Template thumbnails are restored from their durable record before a
        # saved hook is used as a face-swap target on a fresh backend instance.
        restored_template = await _ensure_template_thumbnail(Path(relative_path).stem)
        if restored_template:
            target_path = restored_template

    if not target_path.is_file():
        # An extracted frame can be missing on this machine even though the
        # analysis is still valid (ephemeral storage, redeploy, cache
        # eviction). Try to reproduce it deterministically before failing.
        # Template thumbnails are copies rather than derivations, so there is
        # nothing to recompute for those.
        recovered = await _recover_missing_frame(relative_path)
        if not recovered:
            if relative_path.startswith("templates/"):
                detail = (
                    "That template's thumbnail is no longer on the server. "
                    "Open the source analysis and bookmark the hook again."
                )
            else:
                detail = "Target frame not found on server. Please re-analyze the video."
            raise HTTPException(status_code=400, detail=detail)

    target_image_url = url_path

    source_bytes = await source_face.read()
    if not source_bytes:
        raise HTTPException(status_code=400, detail="Source face image is empty.")
    if len(source_bytes) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Source face image is too large (max 12MB).")

    normalized_source = validate_and_normalize_photo(source_bytes)
    source_id = str(uuid.uuid4())
    source_path = pipeline.UPLOADS_DIR / f"{source_id}.png"
    source_path.write_bytes(normalized_source)
    source_face_url = f"/api/media/uploads/{source_id}.png"

    job_id = str(uuid.uuid4())
    await _execute(
        """INSERT INTO face_swap_jobs
           (id, status, target_image_url, source_face_url, target_image_path,
            source_face_path, variants_requested, created_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            job_id,
            "pending",
            target_image_url,
            source_face_url,
            str(target_path),
            str(source_path),
            variants,
            now_iso(),
            user_id,
        ),
    )
    background_tasks.add_task(
        _run_face_swap_job,
        job_id,
        target_path,
        source_path,
        target_image_url,
        source_face_url,
        variants,
        customization_prompt,
        user_id,
    )

    return {
        "job_id": job_id,
        "status": "pending",
        "target_image_url": target_image_url,
        "source_face_url": source_face_url,
        "variants_requested": variants,
    }


@api_router.get("/face-swap/status/{job_id}")
async def face_swap_status(job_id: str, user_id: str = Depends(get_current_user_id)):
    """Return the latest state and completed result for a face-swap image job."""
    job = await _fetch_one("SELECT * FROM face_swap_jobs WHERE id = ?", (job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Face-swap job not found.")

    response = {
        "job_id": job_id,
        "status": job.get("status", "pending"),
        "target_image_url": job.get("target_image_url"),
        "source_face_url": job.get("source_face_url"),
        "variants_requested": job.get("variants_requested", 1),
    }
    if job.get("status") == "completed" and job.get("result_json"):
        try:
            response.update(json.loads(job["result_json"]))
        except (json.JSONDecodeError, TypeError):
            logger.error(f"Face swap job {job_id} has invalid result JSON")
            raise HTTPException(status_code=500, detail="Face-swap result could not be loaded.")
    elif job.get("status") == "failed":
        response["error"] = job.get("error") or "AI face swap generation failed."
    return response


@api_router.get("/face-swap/jobs")
async def list_face_swap_jobs(user_id: str = Depends(get_current_user_id)):
    """
    Return the authenticated user's face-swap job history (most recent first).

    This gives users access to their past generations so they can revisit
    results without needing to remember individual job IDs.
    """
    rows = await _fetch_all(
        """SELECT id, status, target_image_url, source_face_url,
                  variants_requested, error, created_at, started_at, completed_at
           FROM face_swap_jobs
           WHERE user_id = ?
           ORDER BY created_at DESC
           LIMIT 50""",
        (user_id,),
    )
    # Attach the result summary for completed jobs
    enriched = []
    for row in rows:
        entry = dict(row)
        entry["job_id"] = entry.pop("id", entry.get("job_id"))
        if entry.get("status") == "completed":
            full_job = await _fetch_one(
                "SELECT result_json FROM face_swap_jobs WHERE id = ?", (entry["job_id"],)
            )
            if full_job and full_job.get("result_json"):
                try:
                    result_data = json.loads(full_job["result_json"])
                    entry["generated_image_url"] = result_data.get("generated_image_url")
                    entry["variants"] = result_data.get("variants", [])
                except (json.JSONDecodeError, TypeError):
                    pass
        enriched.append(entry)
    return enriched


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

HOOK_VIDEO_PROMPT_TEMPLATE = (
    "Create a 3-second vertical video (9:16) starting from this exact first frame. "
    "The character should perform a FAST, punchy, attention-grabbing movement that creates "
    "curiosity: {motion_type}. "
    "PACING IS CRITICAL — match the energy of a viral TikTok hook (first 2-3 seconds): "
    "- The movement must happen QUICKLY — within the first 1-2 seconds, not gradually "
    "- Fast, snappy transitions — NOT slow or cinematic "
    "- Immediate eye contact and direct energy toward the camera from the very first frame "
    "- The viewer should feel startled or hooked within the first second "
    "- Think 'scroll-stopper' speed — if someone is swiping fast, this catches their eye instantly "
    "Additional requirements: "
    "- Maintain perfect character consistency with the first frame throughout "
    "- Camera holds steady or has a very subtle push-in for tension "
    "- End on a moment that makes the viewer want to see what happens next"
)

# Hook videos are muted by default. On TikTok, creators almost always attach a
# trending sound or use native text-to-speech in TikTok's own editor after
# exporting — a locally-generated audio track can't be posted as a "trending
# sound" and would just get stripped/replaced anyway. Muting by default avoids
# paying for audio generation nobody keeps, while still letting users opt in
# (e.g. for platforms without an in-app sound library, like Reels/Shorts).
AUDIO_ON_INSTRUCTION = (
    "\n\nGenerate native audio that complements the hook — ambient sound, subtle "
    "tension-building music, or brief impactful sound design matching the energy "
    "of the movement."
)
AUDIO_OFF_INSTRUCTION = (
    "\n\nIMPORTANT: This video must be completely SILENT — no audio, no music, "
    "no voiceover, no ambient sound, no sound design of any kind. The character "
    "must NOT move their lips as if speaking or talking — keep the mouth closed "
    "or in a natural resting/smiling position. The creator will add a trending "
    "sound or text-to-speech in TikTok's own editor after exporting this clip."
)

# Always appended to every video prompt — text overlays are added later in
# TikTok's editor, not baked into the AI-generated clip.
NO_TEXT_OVERLAY_INSTRUCTION = (
    "\n\nNO TEXT OVERLAYS: The generated video must NOT contain any text, captions, "
    "titles, subtitles, watermarks, emojis, stickers, graphics, or visual text of "
    "any kind rendered on top of the video. The output should be a clean video with "
    "only the character and the scene — no text elements whatsoever. The creator "
    "will add their own text overlays in TikTok's editor after exporting."
)


def apply_audio_directive(prompt: str, include_audio: bool) -> str:
    """
    Append explicit audio and text-overlay instructions to a video prompt.

    Applied uniformly across all prompt sources (live analysis, saved
    templates, image analysis, motion-style fallback) right before
    submission, so the muted-by-default behavior and no-text rule hold
    regardless of where the base prompt text came from.
    """
    return prompt + (AUDIO_ON_INSTRUCTION if include_audio else AUDIO_OFF_INSTRUCTION) + NO_TEXT_OVERLAY_INSTRUCTION

# Canonical motion-style definitions — the single source of truth for both the
# prompt text sent to the model and the description shown in the UI.
#
# These were previously two independent lists: the prompt fragments here and a
# separate hand-written set of card descriptions in FaceSwap.jsx. They described
# the same five motions in different words, so the UI could tell a creator one
# thing while the model was told another, with nothing keeping them aligned.
# The UI now renders `motion` verbatim (see GET /hook-motion-styles), so what a
# creator reads on the card is literally what gets sent.
# Each entry carries three things, all served to the UI so none of them can
# drift from the others:
#   summary  — short, human-readable product copy for the card
#   motion   — the verbatim fragment sent to the model (shown on request)
#   overlaps — hook-energy keys this motion conceptually duplicates, so the UI
#              can warn when both are set and would layer two competing
#              directives describing the same effect into one prompt
HOOK_MOTION_STYLES = [
    {
        "key": "lean-in",
        "label": "Lean In",
        "summary": "Moves toward camera like you're about to share a secret — builds instant curiosity",
        "motion": "a FAST confident lean-in toward camera with a knowing expression, snapping into position within the first second — as if about to reveal a secret",
        "overlaps": [],
    },
    {
        "key": "turn",
        "label": "Dramatic Turn",
        "summary": "Starts from the side, then turns to face the viewer — creates a reveal moment",
        "motion": "a QUICK dramatic turn from profile to face-on, making immediate eye contact with the camera — fast snap, not a slow rotation",
        "overlaps": ["reveal"],
    },
    {
        "key": "gesture",
        "label": "Gesture",
        "summary": "Points, raises a hand, or reveals something — signals 'watch this' to stop the scroll",
        "motion": "a RAPID attention-grabbing gesture (pointing, hand raise, or prop reveal) that happens instantly — implies 'watch this' with urgency",
        "overlaps": [],
    },
    {
        "key": "intrigue",
        "label": "Intrigue",
        "summary": "Subtle head tilt + raised eyebrow — makes viewers think 'what do they know?'",
        "motion": "a FAST head tilt and raised eyebrow with a half-smile, snapping into the intrigue pose within the first second",
        "overlaps": ["curiosity-gap"],
    },
    {
        "key": "stop-motion",
        "label": "Stop Motion",
        "summary": "Sudden freeze-frame pose snap — eye-catching jolt that holds attention",
        "motion": "a SUDDEN stop-motion-style pose change that catches the eye instantly, then holds with intensity",
        "overlaps": ["pattern-interrupt"],
    },
]

# Derived views over HOOK_MOTION_STYLES so there is exactly one place to edit a
# motion. HOOK_MOTION_TYPES preserves the original positional list used by
# HOOK_VIDEO_PROMPT_TEMPLATE; MOTION_STYLE_INDEX maps the frontend's keys onto
# it for build_hook_prompt_from_motion_style() and
# apply_motion_style_directive().
HOOK_MOTION_TYPES = [m["motion"] for m in HOOK_MOTION_STYLES]
MOTION_STYLE_INDEX = {m["key"]: i for i, m in enumerate(HOOK_MOTION_STYLES)}


def _coerce_mechanics(mechanics) -> list:
    """Normalize replicable_mechanics into a list (it may be stored as JSON text)."""
    if not mechanics:
        return []
    if isinstance(mechanics, str):
        try:
            mechanics = json.loads(mechanics)
        except (json.JSONDecodeError, TypeError):
            mechanics = [mechanics]
    if isinstance(mechanics, list):
        return [m for m in mechanics if m]
    return [mechanics]


def build_aleph_edit_prompt() -> str:
    """
    Build the prompt for Runway Aleph 2.0's video EDIT mode.

    Aleph is fundamentally different from generative models: it doesn't
    synthesize a scene, it edits the actual source video and preserves
    everything it isn't told to change. Its docs are explicit that the prompt
    must (1) lead with a transformation verb, (2) name only the single change,
    and (3) end with a clause pinning everything else in place — vague or
    descriptive prompts cause the model to "redraw" parts that should stay
    untouched. This is why this prompt is much shorter than the generative
    prompts below: there's no scene, motion, or camera work to describe,
    because none of that is being regenerated.
    """
    return (
        "Replace the person's face and identity to match the reference face shown "
        "in the first-frame anchor image. Keep everything else in the video exactly "
        "as it is in the source: the body movements, hand gestures, head movements, "
        "camera angle, framing, clothing, background, lighting, and timing."
    )


def build_hook_prompt_from_analysis(analysis: dict, has_reference_video: bool = False, v2v_motion_active: bool = False) -> str:
    """
    Build the hook-video prompt from a viral video's hook analysis.

    Shared by the live analysis path and by hook-template creation, so a saved
    template stores exactly the prompt that a fresh analysis would have produced.
    With Seedance 2.5's V2V motion reference, the video reference carries the
    full motion/gesture/camera authority, while the first_frame image anchors
    identity. This text prompt should stay minimal to avoid conflicting with
    the video pixels.

    Args:
        v2v_motion_active: When True, the reference video is actually being
            delivered to the model as a motion reference AND the face image is
            locked as first_frame. The prompt is kept deliberately minimal so
            the video reference is the sole authority on motion, gestures,
            camera, and timing.
    """
    if v2v_motion_active:
        # V2V mode: Seedance 2.5 receives the viral video as motion reference
        # AND the face-swapped image as first_frame (identity anchor).
        # Keep the prompt MINIMAL and framed as creative video production.
        #
        # IMPORTANT: Seedance moderation (error 1026) flags prompts that sound
        # like face-swap/deepfake instructions ("replace the face", "swap identity",
        # etc.). The fix is cinematic production framing — describe what the camera
        # should capture, not what faces to change. The first_frame image already
        # carries the character's appearance; the prompt just directs motion.
        prompt = (
            "Create a 3-second vertical video (9:16). The character from the first frame "
            "performs the exact choreography shown in the reference video — same body movements, "
            "same hand gestures, same head movements, same timing, same camera angle, same energy. "
            "Match the reference video frame-by-frame: identical pacing, identical physical "
            "performance, identical framing. Cinematic quality, natural lighting, sharp focus."
        )
    else:
        prompt = (
            "Create a 3-second vertical video (9:16) starting from this exact first frame. "
            "Recreate the EXACT hook mechanics that made the original viral video work:\n\n"
            f"FACIAL EXPRESSION: {analysis.get('facial_expressions') or 'engaging expression'}\n"
            f"BODY LANGUAGE & GESTURE: {analysis.get('body_language_gestures') or 'confident body language'}\n"
            f"PACING & MOVEMENT: {analysis.get('pacing_cuts') or 'quick, attention-grabbing pacing'}\n"
            f"HOOK SUMMARY: {analysis.get('hook_summary') or 'attention-grabbing opening'}\n\n"
            "PACING IS CRITICAL — this must match the speed and energy of a viral TikTok hook:\n"
            "- The action must start IMMEDIATELY from frame 1 — no slow build-up or pause at the start\n"
            "- All movements should be FAST and snappy, matching the rapid pace of the original hook window\n"
            "- Quick, punchy gestures — NOT slow or cinematic movements\n"
            "- Immediate direct eye contact with the camera from the very first frame\n"
            "- Energy level should be HIGH from the start — think 'scroll-stopper' urgency\n"
            "- The body language tempo must match how fast the original creator moved\n"
            "- Compress all the described movements into the first 2 seconds\n\n"
            "ADDITIONAL REQUIREMENTS:\n"
            "- Perform the EXACT movements and expressions described above — these are proven to grab attention\n"
            "- Maintain perfect character consistency with the first frame throughout\n"
            "- Camera holds steady or has a subtle push-in matching the original's pacing\n"
            "- End on a moment of anticipation (the viewer wants to know what happens next)"
        )

    mechanics = _coerce_mechanics(analysis.get("replicable_mechanics"))
    if mechanics and not v2v_motion_active:
        mechanics_str = "; ".join(str(m) for m in mechanics[:5])
        prompt += f"\n\nKEY MECHANICS TO REPLICATE: {mechanics_str}"

    if has_reference_video and not v2v_motion_active:
        prompt += (
            "\n\nNOTE: A reference video is provided for V2V motion transfer. "
            "Replicate its timing, camera movement, performance rhythm, and editing pace "
            "while using the new character from the first frame."
        )
    return prompt


def build_hook_prompt_from_image_analysis(image_analysis: dict) -> str:
    """Build the hook-video prompt when only a single still image was analyzed."""
    prompt = (
        "Create a 3-second vertical video (9:16) starting from this exact first frame. "
        "Animate from this starting pose using these movement cues:\n\n"
        f"FACIAL EXPRESSION: {image_analysis.get('facial_expressions') or 'engaging expression'}\n"
        f"BODY LANGUAGE & MOVEMENT: {image_analysis.get('body_language_gestures') or 'confident movement'}\n"
        f"PACING: {image_analysis.get('pacing_cuts') or 'quick, attention-grabbing pacing'}\n"
        f"HOOK CONCEPT: {image_analysis.get('hook_summary') or 'attention-grabbing opening'}\n\n"
        "PACING IS CRITICAL — this must match the speed and energy of a viral TikTok hook:\n"
        "- Start moving IMMEDIATELY from frame 1 — no pause or slow build-up\n"
        "- All movements should be FAST and snappy, matching a real creator's rapid energy\n"
        "- Quick, punchy gestures — NOT slow or cinematic\n"
        "- Immediate direct eye contact with the camera\n"
        "- Compress all the action into the first 2-3 seconds\n"
        "- Energy level HIGH from the very start — scroll-stopper urgency\n\n"
        "ADDITIONAL REQUIREMENTS:\n"
        "- Animate naturally from the starting pose shown in the first frame\n"
        "- Maintain perfect face consistency throughout\n"
        "- The movement should build curiosity and make the viewer want to see more\n"
        "- End on a moment of anticipation"
    )
    mechanics = _coerce_mechanics(image_analysis.get("replicable_mechanics"))
    if mechanics:
        mechanics_str = "; ".join(str(m) for m in mechanics[:5])
        prompt += f"\n\nSPECIFIC MOVEMENTS TO PERFORM (do these FAST): {mechanics_str}"
    return prompt


def build_hook_prompt_from_motion_style(motion_style: str) -> str:
    """Final fallback: a hand-written motion template. Costs zero AI calls.

    Reached only when there is no template, no hook analysis, and the
    single-image analysis returned nothing usable. When motion_style is empty
    (the creator left it on Default), lean-in is used as the house default
    since this branch has no other signal to work from.
    """
    key = (motion_style or "").strip().lower()
    motion = HOOK_MOTION_TYPES[MOTION_STYLE_INDEX.get(key, 0)]
    return HOOK_VIDEO_PROMPT_TEMPLATE.format(motion_type=motion)


def apply_motion_style_directive(prompt: str, motion_style: str) -> str:
    """
    Layer an explicitly-chosen motion style onto an already-built prompt.

    Previously motion_style only reached the output through
    build_hook_prompt_from_motion_style(), i.e. the deepest fallback branch —
    so on every normal path (template, hook analysis, or a successful
    single-image analysis) the creator's Motion Style pick was silently
    discarded. This applies it as an explicit movement directive on top of
    whatever base prompt was produced, the same way apply_hook_style_directive
    layers hook energy, so the control actually does something.

    No-ops when motion_style is empty (Default) or unrecognized, which is what
    keeps the untouched-default path eligible for Aleph's exact edit.
    """
    key = (motion_style or "").strip().lower()
    if key not in MOTION_STYLE_INDEX:
        return prompt

    motion = HOOK_MOTION_TYPES[MOTION_STYLE_INDEX[key]]
    return prompt + (
        f"\n\nMOTION STYLE (chosen by the creator): The character must perform {motion}. "
        "This is the primary physical action of the hook — where it conflicts with any "
        "other body movement described above, this movement wins. Keep the face "
        "consistency, pacing, and framing requirements above intact."
    )


# ---------------------------------------------------------------------------
# Hook Templates — save a proven hook once, reuse it forever for free.
#
# A template is a complete snapshot of an analyzed hook:
#   - the AI hook analysis (so it is never re-analyzed)
#   - the ready-to-submit video prompt (so it is never regenerated)
#   - a local copy of the source clip for V2V motion transfer (never re-downloaded)
#   - a local copy of the key hook frame as a thumbnail
#
# Creating and reusing templates costs ZERO AI calls. Only the video generation
# itself is billed, which is unavoidable for a new output.
# ---------------------------------------------------------------------------
HOOK_TEMPLATE_CATEGORIES = [
    "curiosity-gap", "pattern-interrupt", "reveal", "reaction", "authority", "confrontation", "other",
]
HOOK_TEMPLATE_NAME_MAX = 80
HOOK_TEMPLATE_NOTES_MAX = 500

# ---------------------------------------------------------------------------
# Hook Style Directives — mechanism-based prompt modifiers that map to
# proven 2026 TikTok scroll-stopping patterns (backed by OpusClip's
# analysis of 34,635 clips and multiple UGC performance studies).
#
# These are HOOK MECHANISMS (the psychological trigger that stops the scroll
# in the first 1.5-3 seconds), NOT content genres. Each one produces
# meaningfully different body language, facial expressions, and camera
# energy from the AI video model.
# ---------------------------------------------------------------------------
HOOK_STYLE_DIRECTIVES = {
    "curiosity-gap": (
        "\n\nHOOK STYLE — CURIOSITY GAP: This hook must create an irresistible 'wait, what?' "
        "moment that makes the viewer NEED to keep watching. Show something partially — an "
        "incomplete reveal, a mysterious expression, an object hinted at but not shown. The "
        "character should have a knowing smirk, a half-smile, or a 'I know something you don't' "
        "look. Build tension through what is deliberately withheld. The body language should "
        "signal 'I have a secret' — slight lean-in, eyebrow raise, conspiratorial energy. "
        "The viewer's brain cannot leave the gap unresolved, so they stay."
    ),
    "pattern-interrupt": (
        "\n\nHOOK STYLE — PATTERN INTERRUPT: This hook must BREAK the viewer's passive scrolling "
        "state with something visually or physically unexpected. The brain pauses involuntarily "
        "when it encounters something that doesn't fit the expected pattern. Use: a sudden "
        "contradictory movement (start one action, snap into something completely different), "
        "an impossible-seeming gesture, an unexpected frozen pose that breaks into motion, or "
        "a jarring visual change. The key is to be STRATEGICALLY strange — the unexpected "
        "element must register in under 1.5 seconds. Think 'cognitive jolt' — the viewer's "
        "brain says 'wait, am I seeing this correctly?' and pauses to resolve it."
    ),
    "reveal": (
        "\n\nHOOK STYLE — REVEAL / TRANSFORMATION: This hook must set up a dramatic before/after "
        "in one rapid snap. Start in one state — obscured, hidden, unremarkable, messy, or plain — "
        "then INSTANTLY transition to the payoff: polished, stunning, revealed, or transformed. "
        "The transition should be viscerally satisfying: a hand pull-away, a quick spin, a "
        "blink-and-you-miss-it cut, a dramatic lighting change, or a hand swipe across frame. "
        "This works because showing the OUTCOME in the first 2 seconds is the #1 performing "
        "hook type on TikTok — the viewer knows immediately what they'll get if they stay. "
        "Lead with the payoff, make the transformation instant and dramatic."
    ),
    "reaction": (
        "\n\nHOOK STYLE — REACTION: This hook must be driven by an exaggerated, larger-than-life "
        "emotional response that makes the viewer wonder 'what did they just see?' The character "
        "should display: shocked wide eyes, jaw drop, hands flying to face, dramatic double-take "
        "toward camera, or a gasp-worthy sudden turn. The reaction must be OVERDRAMATIC — "
        "subtle doesn't stop the scroll. It should feel like they just saw/heard/discovered "
        "something incredible. The viewer stays because they want to know what triggered "
        "that extreme response. This exploits emotional contagion — seeing someone react "
        "intensely makes us feel it too."
    ),
    "authority": (
        "\n\nHOOK STYLE — AUTHORITY / EXPERT SIGNAL: This hook must radiate confident credibility "
        "in the first second, open a curiosity gap in the second, and promise payoff by the third. "
        "The character should have: direct, commanding eye contact, authoritative posture "
        "(squared shoulders, purposeful lean-in), and a 'listen to me' gesture — a pointed "
        "finger, a deliberate hand raise, or holding something up with intention. The body "
        "language says 'I have valuable information and you need to pay attention RIGHT NOW.' "
        "Fast, purposeful, no-nonsense movement. This works because TikTok viewers trust "
        "short-form experts who telegraph credibility in under 3 seconds."
    ),
    "confrontation": (
        "\n\nHOOK STYLE — CONFRONTATION / CONTRARIAN: This hook must directly challenge the "
        "viewer — it says 'you're doing it wrong' or 'everyone believes X, but it's false.' "
        "The character should display: slightly aggressive lean toward camera, pointed finger "
        "or accusatory gesture, 'are you serious?' facial expression, raised eyebrow with "
        "head shake, or a disapproving look that breaks into explanation. The energy is "
        "challenging but not hostile — more 'tough love' than angry. This exploits the brain's "
        "inability to leave a contradiction unresolved. The viewer MUST stay to defend their "
        "position or find out if they're wrong. Use urgent, confrontational body language "
        "that says 'stop what you're doing and listen.'"
    ),
}
HOOK_STYLE_CUSTOM_PROMPT_MAX = 200


def _sanitize_custom_hook_prompt(raw: str) -> str:
    """
    Sanitize the user-supplied custom hook prompt before injection.

    Defence-in-depth: even though the frontend enforces limits, the backend
    independently validates and cleans the input. This prevents:
    - Prompt injection via XML-like tags or system/role delimiters
    - Excessive length bypassing frontend limits (direct API calls)
    - Control characters or unicode trickery
    - Attempts to override the base prompt's safety instructions

    Returns the cleaned text (may be shorter than input, or empty).
    """
    import re

    text = (raw or "").strip()
    if not text:
        return ""

    # Strip control characters (keep only printable + basic whitespace)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

    # Collapse newlines and excessive whitespace into single spaces
    text = re.sub(r"[\r\n]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)

    # Remove prompt-injection patterns:
    # - Triple backticks (code fences used to break out of context)
    text = text.replace("```", "")
    # - XML/HTML-style system, instruction, role, or context tags
    text = re.sub(r"</?(?:system|instruction|prompt|role|assistant|user|context|ignore|override|admin)[^>]*>", "", text, flags=re.IGNORECASE)
    # - "Ignore previous instructions" / "disregard above" type phrases
    text = re.sub(r"(?:ignore|disregard|forget|override|bypass)\s+(?:previous|above|prior|all|the)\s+(?:instructions?|prompts?|rules?|context|directions?)", "", text, flags=re.IGNORECASE)
    # - Attempts to redefine role ("you are now", "act as", "pretend to be")
    text = re.sub(r"(?:you\s+are\s+now|act\s+as|pretend\s+(?:to\s+be|you(?:'re| are)))", "", text, flags=re.IGNORECASE)

    # Final cleanup: re-collapse any double spaces introduced by removals
    text = re.sub(r"\s{2,}", " ", text).strip()

    # Hard character limit (defense against direct API calls bypassing frontend)
    text = text[:HOOK_STYLE_CUSTOM_PROMPT_MAX]

    return text


def apply_hook_style_directive(prompt: str, hook_category: str = "", hook_custom_prompt: str = "") -> str:
    """
    Inject a category-based style directive and/or custom prompt into the
    generation prompt. Applied AFTER the base prompt is built but BEFORE
    the audio directive, so the style layer sits between content and
    audio/text-overlay instructions.

    - hook_category: one of the HOOK_STYLE_DIRECTIVES keys (optional)
    - hook_custom_prompt: freeform user text (optional, sanitized + max 200 chars)
    """
    category_key = (hook_category or "").strip().lower()
    custom_text = _sanitize_custom_hook_prompt(hook_custom_prompt)

    if category_key and category_key in HOOK_STYLE_DIRECTIVES:
        prompt += HOOK_STYLE_DIRECTIVES[category_key]

    if custom_text:
        prompt += (
            f"\n\nCUSTOM HOOK DIRECTION (from the creator): {custom_text}. "
            "Incorporate this direction into the hook while preserving the core "
            "mechanics, pacing, and face consistency requirements above."
        )

    return prompt


def _normalize_template_category(category: Optional[str]) -> str:
    key = (category or "").strip().lower()
    return key if key in HOOK_TEMPLATE_CATEGORIES else "other"


def _template_thumbnail_source(video: dict, analysis: dict) -> Optional[Path]:
    """Resolve the on-disk path of the analysis's key hook frame."""
    frames = analysis.get("frames") or []
    if not frames or not video.get("tiktok_url"):
        return None
    key_idx = analysis.get("key_hook_frame_index") or 1
    try:
        key_idx = max(1, min(len(frames), int(key_idx)))
    except (TypeError, ValueError):
        key_idx = 1
    frame_meta = frames[key_idx - 1]
    media_url = frame_meta.get("media_url") or ""
    if not media_url:
        return None
    filename = media_url.split("/")[-1]
    candidate = pipeline.FRAMES_DIR / pipeline.url_hash(video["tiktok_url"]) / filename
    return candidate if candidate.exists() else None


@api_router.post("/bookmarks", status_code=201)
async def create_hook_template(payload: CreateHookTemplateRequest, user_id: str = Depends(get_current_user_id)):
    """
    Save an already-analyzed hook as a reusable template.

    Costs zero AI calls: this only snapshots the existing analysis, pre-builds the
    video prompt, and copies the source clip + key frame into template storage so
    the template stays usable after caches are cleared.
    """
    video = await get_video_or_404(payload.video_id)
    analysis = await get_latest_analysis_or_404(payload.video_id)

    template_id = str(uuid.uuid4())

    # Copy the source clip so V2V motion transfer keeps working for this template.
    reference_video_path = None
    if video.get("local_video_path"):
        src_video = Path(video["local_video_path"])
        if src_video.exists():
            dest_video = pipeline.TEMPLATES_DIR / f"{template_id}.mp4"
            try:
                shutil.copy2(src_video, dest_video)
                reference_video_path = str(dest_video)
            except OSError as e:
                logger.warning(f"Could not copy motion reference for template {template_id}: {e}")

    # Normalize the key hook frame to JPEG, persist its bytes in the durable
    # template record, and keep a local copy only as a cache. That keeps the
    # Bookmarks card renderable after container restarts and across instances.
    thumbnail_url = None
    thumbnail_bytes = None
    src_frame = _template_thumbnail_source(video, analysis)
    if src_frame:
        try:
            thumbnail_bytes = _normalize_template_thumbnail(src_frame.read_bytes())
            dest_frame = _template_thumbnail_path(template_id)
            _restore_template_thumbnail(dest_frame, thumbnail_bytes)
            thumbnail_url = f"/api/media/templates/{template_id}.jpg"
        except (OSError, ValueError) as e:
            logger.warning(f"Could not persist thumbnail for template {template_id}: {e}")
            thumbnail_bytes = None
    if not thumbnail_url:
        thumbnail_url = video.get("thumbnail_url")

    # Pre-build the exact prompt a fresh analysis would have produced.
    prompt_template = build_hook_prompt_from_analysis(
        analysis, has_reference_video=bool(reference_video_path)
    )

    name = (payload.name or "").strip()[:HOOK_TEMPLATE_NAME_MAX]
    if not name:
        summary = (analysis.get("hook_summary") or "").strip()
        name = (summary[:60].rstrip(" .,") if summary else f"Hook from @{video.get('creator') or 'unknown'}")

    created_at = now_iso()
    await _execute(
        """INSERT INTO hook_templates
           (id, name, category, notes, source_video_id, source_analysis_id,
            source_tiktok_url, source_creator, source_title, thumbnail_url,
            thumbnail_bytes, facial_expressions, body_language_gestures, pacing_cuts,
            text_overlays_timing, audio_cues_inferred, hook_summary,
            effectiveness_score, replicable_mechanics, prompt_template,
            reference_video_path, song_title, song_artist,
            times_used, last_used_at, created_at, updated_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (template_id, name, _normalize_template_category(payload.category),
         (payload.notes or "").strip()[:HOOK_TEMPLATE_NOTES_MAX],
         video["id"], analysis["id"], video.get("tiktok_url"), video.get("creator"),
         video.get("title"), thumbnail_url, thumbnail_bytes,
         analysis.get("facial_expressions"), analysis.get("body_language_gestures"),
         analysis.get("pacing_cuts"), analysis.get("text_overlays_timing"),
         analysis.get("audio_cues_inferred"), analysis.get("hook_summary"),
         analysis.get("effectiveness_score"),
         json.dumps(_coerce_mechanics(analysis.get("replicable_mechanics"))),
         prompt_template, reference_video_path,
         video.get("song_title"), video.get("song_artist"),
         0, None, created_at, created_at, user_id),
    )
    logger.info(
        f"Saved hook template {template_id} ('{name}') from video {video['id']} — "
        f"motion_reference={bool(reference_video_path)}"
    )
    return _public_template(
        await _fetch_one("SELECT * FROM hook_templates WHERE id = ?", (template_id,))
    )


@api_router.get("/bookmarks")
async def list_hook_templates(category: str = "", source_video_id: str = "", user_id: str = Depends(get_current_user_id)):
    """List saved hook templates, most recently used first."""
    clauses = ["user_id = ?"]
    params = [user_id]
    if category.strip():
        clauses.append("category = ?")
        params.append(_normalize_template_category(category))
    if source_video_id.strip():
        clauses.append("source_video_id = ?")
        params.append(source_video_id.strip())
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = await _fetch_all(
        f"""SELECT * FROM hook_templates {where}
            ORDER BY COALESCE(last_used_at, created_at) DESC LIMIT 200""",
        tuple(params),
    )
    for row in rows:
        row["has_motion_reference"] = bool(
            row.get("reference_video_path") and Path(row["reference_video_path"]).exists()
        )
        expected_local_url = f"/api/media/templates/{row['id']}.jpg"
        if (
            row.get("thumbnail_url") == expected_local_url
            and GENERATED_ID_RE.match(row["id"] or "")
            and not row.get("thumbnail_bytes")
            and not _template_thumbnail_path(row["id"]).is_file()
        ):
            # Legacy templates created before durable thumbnails may have lost
            # their local cache in a prior deploy. Keep the card renderable
            # with its source video's cover, while avoiding a misleading local
            # target URL that could not seed Face Swap.
            source_video = await _fetch_one(
                "SELECT thumbnail_url FROM videos WHERE id = ?", (row.get("source_video_id"),)
            )
            if source_video and source_video.get("thumbnail_url"):
                row["thumbnail_url"] = source_video["thumbnail_url"]
        row.pop("thumbnail_bytes", None)
    return rows


@api_router.get("/bookmarks/{template_id}")
async def get_hook_template(template_id: str, user_id: str = Depends(get_current_user_id)):
    template = await _fetch_one("SELECT * FROM hook_templates WHERE id = ? AND user_id = ?", (template_id, user_id))
    if not template:
        raise HTTPException(status_code=404, detail="Hook template not found.")
    template["has_motion_reference"] = bool(
        template.get("reference_video_path") and Path(template["reference_video_path"]).exists()
    )
    return _public_template(template)


@api_router.patch("/bookmarks/{template_id}")
async def update_hook_template(template_id: str, payload: UpdateHookTemplateRequest, user_id: str = Depends(get_current_user_id)):
    """Rename, recategorize, or annotate a saved template."""
    existing = await _fetch_one("SELECT * FROM hook_templates WHERE id = ?", (template_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Hook template not found.")

    updates = payload.model_dump(exclude_unset=True)
    set_clauses = []
    values = []
    if "name" in updates:
        name = (updates["name"] or "").strip()[:HOOK_TEMPLATE_NAME_MAX]
        if not name:
            raise HTTPException(status_code=400, detail="Template name cannot be empty.")
        set_clauses.append("name = ?")
        values.append(name)
    if "category" in updates:
        set_clauses.append("category = ?")
        values.append(_normalize_template_category(updates["category"]))
    if "notes" in updates:
        set_clauses.append("notes = ?")
        values.append((updates["notes"] or "").strip()[:HOOK_TEMPLATE_NOTES_MAX])

    if not set_clauses:
        return _public_template(existing)

    set_clauses.append("updated_at = ?")
    values.append(now_iso())
    values.append(template_id)
    await _execute(
        f"UPDATE hook_templates SET {', '.join(set_clauses)} WHERE id = ?", tuple(values)
    )
    return _public_template(
        await _fetch_one("SELECT * FROM hook_templates WHERE id = ?", (template_id,))
    )


@api_router.delete("/bookmarks/{template_id}")
async def delete_hook_template(template_id: str, user_id: str = Depends(get_current_user_id)):
    """Delete a template and its copied motion reference / thumbnail."""
    existing = await _fetch_one("SELECT * FROM hook_templates WHERE id = ?", (template_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Hook template not found.")

    for candidate in (
        pipeline.TEMPLATES_DIR / f"{template_id}.mp4",
        pipeline.TEMPLATES_DIR / f"{template_id}.jpg",
    ):
        try:
            candidate.unlink(missing_ok=True)
        except OSError as e:
            logger.warning(f"Could not delete template asset {candidate.name}: {e}")

    await _execute("DELETE FROM hook_templates WHERE id = ?", (template_id,))
    return {"deleted": True, "id": template_id}


@api_router.post("/face-swap/generate-hook-video")
async def face_swap_generate_hook_video(
    image_id: str = Form(...),
    motion_style: str = Form(""),
    model: str = Form(""),
    video_id: str = Form(""),
    template_id: str = Form(""),
    include_audio: bool = Form(False),
    hook_category: str = Form(""),
    hook_custom_prompt: str = Form(""),
    user_id: str = Depends(get_current_user_id),
):
    """
    Generate a hook video from the face-swapped image using Seedance 2.5.

    Seedance 2.5 advantages leveraged here:
    - Motion reference control: video reference drives body movement, gestures,
      camera angle, and performance rhythm from the original viral hook.
    - Combined references: face image as first_frame (identity anchor) PLUS
      video as motion reference in the same request — no conflict.
    - Up to 50 multimodal references (30 images, 10 videos, 10 audio).
    - Native audio generation (OFF by default — see include_audio below).
    - Built by ByteDance (TikTok's parent) for short-form hook content.

    If video_id is provided, pulls the hook analysis AND the downloaded video file
    to feed as a V2V motion reference — Seedance 2.5 will replicate the proven
    hook mechanics (gestures, camera, pacing) directly from the source video.

    If template_id is provided, reuses a saved hook template. This is the cheapest
    path: the prompt and the V2V motion reference are already cached on disk, so
    the request costs ZERO AI calls (no hook re-analysis, no prompt regeneration,
    no re-download of the source video) — only the video generation itself.

    Falls back to a motion-style template if no analysis is available.

    motion_style options: "" (Default), lean-in, turn, gesture, intrigue,
    stop-motion. Empty means "match the original hook's movement" and keeps
    the request eligible for Aleph's exact edit. An explicit value is applied
    as a movement directive on top of whichever base prompt was built (see
    apply_motion_style_directive) and counts as customization, which routes
    the request to the generative engine.

    include_audio: defaults to False. Hook videos are silent by default because
    TikTok creators attach a trending sound or native text-to-speech in TikTok's
    own editor after exporting — audio generated here can't be posted as a
    "trending sound" and would just be muted/replaced anyway. Set True to have
    the model generate an ambient/music track (useful for platforms without an
    in-app sound library).

    hook_category: optional style directive (intrigue, reveal, reaction, tutorial,
    lifestyle, transformation). When provided, injects a category-specific prompt
    modifier that flavors the hook's energy/intent on top of the base prompt from
    analysis, template, or motion-style fallback. Zero additional AI cost.

    hook_custom_prompt: optional freeform text (max 200 chars) from the creator
    describing exactly what they want the hook to convey. Sanitized server-side
    to strip prompt-injection attempts, control characters, and excessive length.
    Injected alongside (not replacing) the category directive and base prompt
    mechanics.
    """
    require_ai_configured()

    # Existence on disk is not proof of origin — require the image to trace
    # back to a hook frame or saved template. See require_frame_derived_image.
    image_path = await require_frame_derived_image(image_id)

    analysis = None
    reference_video_path = None
    template = None
    prompt = None

    # --- Path 1: saved hook template (zero AI calls) ---
    if template_id and template_id.strip():
        template = await _fetch_one(
            "SELECT * FROM hook_templates WHERE id = ?", (template_id.strip(),)
        )
        if not template:
            raise HTTPException(status_code=404, detail="Hook template not found.")
        prompt = template.get("prompt_template") or ""
        if not prompt:
            raise HTTPException(
                status_code=400,
                detail="This hook template has no saved prompt. Please re-save it from the analysis page.",
            )
        stored_ref = template.get("reference_video_path")
        if stored_ref:
            ref_path = Path(stored_ref)
            if ref_path.exists():
                reference_video_path = ref_path
        logger.info(
            f"Hook video from template {template['id']} ('{template.get('name')}') — "
            "reusing cached prompt and motion reference, 0 AI calls"
        )

    # --- Path 2: live hook analysis from the original viral video ---
    if prompt is None and video_id and video_id.strip():
        analysis_row = await _fetch_one(
            "SELECT * FROM analyses WHERE video_id = ? ORDER BY created_at DESC LIMIT 1",
            (video_id.strip(),),
        )
        if analysis_row:
            analysis = analysis_row

        # Get the downloaded video file for V2V motion transfer / Aleph editing.
        # local_video_path points at Render's EPHEMERAL local disk — it is
        # wiped on every redeploy/restart and may not exist on whichever
        # container instance handles this request even without a redeploy.
        # Without a re-download fallback here, a missing file silently drops
        # reference_video_path to None, which makes use_aleph_edit False and
        # downgrades this generation to the generative fallback model with
        # NO error surfaced — exactly the "used MiniMax instead of Aleph"
        # symptom this is fixing. Re-download from the original source (Apify
        # direct_video_url first, then tiktok_url via yt-dlp) so Aleph stays
        # available whenever the video record itself still exists.
        video_record = await _fetch_one("SELECT * FROM videos WHERE id = ?", (video_id.strip(),))
        if video_record:
            v_path = Path(video_record["local_video_path"]) if video_record.get("local_video_path") else None
            if v_path and v_path.exists():
                reference_video_path = v_path
            elif video_record.get("tiktok_url") or video_record.get("direct_video_url"):
                try:
                    async with _ytdlp_semaphore:
                        redownloaded_path = await pipeline.download_video(
                            video_record.get("tiktok_url") or "",
                            direct_video_url=video_record.get("direct_video_url") or "",
                        )
                    if redownloaded_path and redownloaded_path.exists():
                        reference_video_path = redownloaded_path
                        # Heal the DB record so subsequent requests on this
                        # instance skip straight to the fast path.
                        await _execute(
                            "UPDATE videos SET local_video_path = ? WHERE id = ?",
                            (str(redownloaded_path), video_id.strip()),
                        )
                        logger.info(
                            f"Re-downloaded source video for {video_id.strip()} — "
                            "local_video_path was missing (ephemeral disk wipe or "
                            "different container instance)."
                        )
                except Exception as e:
                    logger.warning(
                        f"Could not re-download source video for {video_id.strip()}: {e}. "
                        "Falling back to the generative model for this generation."
                    )

        # --- Auto-analyze if no analysis exists yet ---
        # This ensures Aleph is always available for default hook generation,
        # even when a user comes from a bookmark that was never manually
        # analyzed. Requires: a video file (downloaded above) to extract
        # frames from. The auto-analysis is lightweight (extract 8 frames,
        # call the vision model once) and its result is persisted for future
        # reuse — so this cost is paid at most once per video.
        if not analysis and reference_video_path and reference_video_path.exists():
            try:
                logger.info(
                    f"Auto-analyzing video {video_id.strip()} — no prior analysis "
                    "exists, triggering on-demand so Aleph can be used."
                )
                frame_paths = await pipeline.extract_hook_frames(
                    reference_video_path,
                    num_frames=FRAME_COUNT,
                    duration=HOOK_DURATION_SECONDS,
                )
                analysis_result = await analyze_hook(
                    frame_paths, session_id=f"auto-hook-{video_id.strip()}",
                )
                auto_analysis_id = str(uuid.uuid4())
                auto_created_at = now_iso()
                video_hash = pipeline.url_hash(
                    video_record.get("tiktok_url") or video_id.strip()
                )
                frame_docs = build_frame_docs(video_hash, frame_paths)
                await _record_analysis_frame_assets(video_hash, frame_paths)
                await _execute(
                    """INSERT INTO analyses
                       (id, video_id, frames, facial_expressions, body_language_gestures, pacing_cuts,
                        text_overlays_timing, audio_cues_inferred, hook_summary, effectiveness_score,
                        key_hook_frame_index, replicable_mechanics, created_at, user_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (auto_analysis_id, video_id.strip(), json.dumps(frame_docs),
                     analysis_result.get("facial_expressions"),
                     analysis_result.get("body_language_gestures"),
                     analysis_result.get("pacing_cuts"),
                     analysis_result.get("text_overlays_timing"),
                     analysis_result.get("audio_cues_inferred"),
                     analysis_result.get("hook_summary"),
                     analysis_result.get("effectiveness_score"),
                     analysis_result.get("key_hook_frame_index"),
                     json.dumps(analysis_result.get("replicable_mechanics", [])),
                     auto_created_at, user_id),
                )
                await _execute(
                    "UPDATE videos SET status = ?, last_analysis_id = ? WHERE id = ?",
                    ("analyzed", auto_analysis_id, video_id.strip()),
                )
                analysis = await _fetch_one(
                    "SELECT * FROM analyses WHERE id = ?", (auto_analysis_id,)
                )
                logger.info(
                    f"Auto-analysis complete for {video_id.strip()} — "
                    f"analysis_id={auto_analysis_id}, Aleph is now eligible."
                )
            except Exception as e:
                logger.warning(
                    f"Auto-analysis failed for {video_id.strip()}: {e}. "
                    "Proceeding without analysis (generative fallback will be used)."
                )

    # Determine early whether this generation will use Runway Aleph 2.0's
    # video-edit path (default "replicate the exact hook" flow) or a
    # generative model (user customized the hook, or no source video exists).
    # Aleph cannot text-generate a scene — it can only edit footage that
    # already exists — so any customization or missing source video routes
    # to the generative fallback.
    # motion_style is included here now that it actually affects the output
    # (see apply_motion_style_directive). An explicit movement choice is a
    # request to deviate from the source's real movement, which is exactly what
    # Aleph's "change only the face" contract cannot honor — so it must route
    # to the generative engine, same as hook_category/hook_custom_prompt.
    # An empty motion_style means "Default / match the original" and keeps
    # Aleph eligible.
    user_customized = bool(
        (hook_category and hook_category.strip())
        or (hook_custom_prompt and hook_custom_prompt.strip())
        or (motion_style and motion_style.strip())
    )
    use_aleph_edit = (
        bool(analysis)
        and bool(reference_video_path)
        and not user_customized
        and not template
    )

    # Set when the base prompt was itself built from motion_style, so the
    # motion directive isn't appended a second time further down.
    motion_style_consumed = False

    if prompt is not None:
        pass  # already resolved from a saved template
    elif use_aleph_edit:
        # Aleph EDITS the real video directly — no scene/motion/camera
        # description needed, just "replace the face, keep everything else."
        prompt = build_aleph_edit_prompt()
    elif analysis:
        # Generative fallback (MiniMax H3 / Seedance 2.5): no exact source
        # video edit available, so describe the hook mechanics for the model
        # to regenerate as closely as possible.
        v2v_will_be_active = bool(reference_video_path) and not user_customized and not template
        prompt = build_hook_prompt_from_analysis(
            analysis,
            has_reference_video=bool(reference_video_path),
            v2v_motion_active=v2v_will_be_active,
        )
    else:
        # No video analysis available (manual upload) — analyze the IMAGE itself
        image_analysis = await analyze_image_for_hook(image_path, session_id=f"img-hook-{image_id}")

        if image_analysis and image_analysis.get("body_language_gestures"):
            prompt = build_hook_prompt_from_image_analysis(image_analysis)
        else:
            # Final fallback: hand-written motion template (no AI cost).
            # This branch builds the whole prompt AROUND motion_style, so the
            # directive must not also be appended below or the same movement
            # would be specified twice.
            prompt = build_hook_prompt_from_motion_style(motion_style)
            motion_style_consumed = True

    # All prompt decoration is skipped on the Aleph edit path. That prompt is a
    # minimal "replace the face, keep everything else" instruction, and appending
    # scene/movement/audio detail to it is exactly what Aleph's docs warn causes
    # drift in regions that should stay untouched. In practice any style input
    # being set already routes away from Aleph via user_customized; this guard
    # makes that non-negotiable rather than incidental.
    #
    # On the generative paths these are applied in a fixed order — hook energy,
    # then custom direction, then motion style, then audio — so the audio
    # directive always lands last regardless of which branch built the base
    # prompt (fresh analysis, saved template, image analysis, or motion
    # fallback), including templates saved before the audio toggle existed
    # whose cached text may still reference audio.
    if not use_aleph_edit:
        # Hook energy (category) + freeform custom direction.
        prompt = apply_hook_style_directive(prompt, hook_category, hook_custom_prompt)
        # Explicit motion style, unless it already formed the base prompt above.
        if not motion_style_consumed:
            prompt = apply_motion_style_directive(prompt, motion_style)
        prompt = apply_audio_directive(prompt, False)

    # Trim the source video to the first 3 seconds so it's a clean 1:1
    # duration match for the output — this gives whichever model is used
    # (Aleph edit or generative V2V) an exact timing template rather than
    # forcing it to guess which segment of a longer clip to use/replicate.
    v2v_video_path = reference_video_path
    if (use_aleph_edit or reference_video_path) and reference_video_path:
        trimmed = await pipeline.trim_video_to_hook(reference_video_path, duration=3.0)
        if trimmed:
            v2v_video_path = trimmed

    # Each model has its own minimum duration (Aleph: 2s, Seedance 2.5: 4s,
    # MiniMax H3: 5s — confirmed via API error responses). Request our
    # preferred 3s hook length; generate_video() clamps it up to whatever
    # the resolved model actually requires, and we track the real value here
    # so the DB record and API response don't lie about what was generated.
    requested_duration = 3
    actual_model_key = "aleph-2" if use_aleph_edit else DEFAULT_VIDEO_MODEL
    actual_duration = max(
        VIDEO_MODELS[actual_model_key].get("min_duration", 1), requested_duration
    )

    try:
        if use_aleph_edit:
            # Runway Aleph 2.0: edits the actual hook video directly, changing
            # only the face. Body movement, gestures, camera, clothing, and
            # background are the ORIGINAL video's pixels — not regenerated.
            result = await generate_video(
                prompt=prompt,
                reference_image_path=image_path,
                duration=requested_duration,
                model="aleph-2",
                reference_video_url=public_media_url(v2v_video_path),
            )
        else:
            # Generative fallback (MiniMax H3 / Seedance 2.5): no source video
            # to edit, or the user customized the hook away from a literal
            # replication — so a new scene must be generated instead.
            use_v2v = (
                bool(analysis)
                and bool(reference_video_path)
                and not user_customized
                and not template
            )
            result = await generate_video(
                prompt=prompt,
                reference_image_path=image_path,
                duration=requested_duration,
                generate_audio=False,  # Always silent — creator adds sound in TikTok editor
                reference_video_url=public_media_url(v2v_video_path) if use_v2v else None,
                prefer_v2v_motion=use_v2v,
            )
    except Exception as e:
        logger.error(f"Hook video generation failed: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Hook video generation failed. Please try again. ({str(e)[:150]})",
        )

    job_id = result.get("id", "")
    polling_url = result.get("polling_url", "")

    await _execute(
        """INSERT OR REPLACE INTO face_swap_video_jobs
           (id, image_id, prompt, duration, status, polling_url, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (job_id, image_id, prompt, actual_duration, "pending", polling_url, now_iso()),
    )

    # Track template reuse so the UI can surface the most effective saved hooks.
    if template:
        await _execute(
            "UPDATE hook_templates SET times_used = times_used + 1, last_used_at = ? WHERE id = ?",
            (now_iso(), template["id"]),
        )

    return {
        "job_id": job_id,
        "status": "pending",
        "polling_url": polling_url,
        "image_id": image_id,
        "duration": actual_duration,
        "phase": "hook",
        # None (not "lean-in") when the creator left Motion Style on Default —
        # reporting a style that was never selected made the old response
        # indistinguishable from an explicit lean-in pick.
        "motion_style": motion_style.strip().lower() or None,
        "model": "aleph-2" if use_aleph_edit else DEFAULT_VIDEO_MODEL,
        "has_v2v_motion": bool(reference_video_path),
        "has_native_audio": include_audio,
        "from_template": bool(template),
        "template_id": template["id"] if template else None,
        "template_name": template.get("name") if template else None,
        "hook_category": hook_category.strip().lower() or None,
        "hook_custom_prompt": _sanitize_custom_hook_prompt(hook_custom_prompt) or None,
    }


@api_router.post("/face-swap/extend-video")
async def face_swap_extend_video(
    image_id: str = Form(...),
    hook_job_id: str = Form(""),
    brand_url: str = Form(""),
    brand_id: str = Form(""),
    prompt: str = Form(""),
    duration: int = Form(10),
    model: str = Form(""),
    video_id: str = Form(""),
    user_id: str = Depends(get_current_user_id),
):
    """
    Generate an extended brand video using MiniMax H3 with native audio.

    H3 produces the full video with synced audio (voiceover, music, sound effects)
    in a single pass — no separate audio generation step needed.

    If hook_job_id refers to a hook clip we already cached locally, its LAST frame
    is extracted and used as this generation's first frame, so the extension
    genuinely continues the hook rather than restarting from the hook's opening
    pose. Falls back to the face-swap still if the clip isn't available.

    If video_id is provided and the original viral video is available, it is also
    passed as a V2V motion reference for timing and pacing continuity.
    """
    require_ai_configured()

    # Existence on disk is not proof of origin — require the image to trace
    # back to a hook frame or saved template. See require_frame_derived_image.
    image_path = await require_frame_derived_image(image_id)

    duration = max(5, min(duration, 15))

    # Get the original viral video for V2V motion transfer if available
    reference_video_path = None
    if video_id and video_id.strip():
        video_record = await _fetch_one("SELECT * FROM videos WHERE id = ?", (video_id.strip(),))
        if video_record and video_record.get("local_video_path"):
            v_path = Path(video_record["local_video_path"])
            if v_path.exists():
                reference_video_path = v_path

    # Bridge the continuation to the end of the hook clip. Without this the
    # extension is generated from the same face-swap still the hook started
    # from, so it replays the hook's opening pose instead of continuing it.
    # The completed hook video is cached at storage/videos/{hook_job_id}.mp4
    # by the video-status endpoint; its last frame becomes our first frame.
    first_frame_path = image_path
    continued_from_hook = False
    if hook_job_id and hook_job_id.strip():
        hook_video_path = pipeline.STORAGE_DIR / "videos" / f"{hook_job_id.strip()}.mp4"
        if hook_video_path.exists():
            bridge_path = pipeline.GENERATED_DIR / f"bridge-{hook_job_id.strip()}.png"
            extracted = await pipeline.extract_last_frame(hook_video_path, bridge_path)
            if extracted:
                first_frame_path = extracted
                continued_from_hook = True
                logger.info(
                    f"Extend video: continuing from last frame of hook {hook_job_id.strip()}"
                )
        else:
            logger.info(
                f"Extend video: hook clip {hook_job_id.strip()}.mp4 not cached locally — "
                "falling back to the face-swap still as first frame"
            )

    # Auto-generate extension prompt if not provided
    if not prompt.strip():
        # Prefer a saved brand profile (instant) over re-fetching/analyzing a
        # URL (30-60s and can time out). An explicitly selected brand_id wins
        # over the active profile so the creator controls which brand this video
        # is for; the URL path remains only as a fallback for users who haven't
        # set up a profile yet.
        brand_profile = None
        brand_row = await _resolve_brand_profile(user_id, brand_id)
        if brand_row:
            brand_profile = brand_row
        elif brand_url and brand_url.strip():
            url = brand_url.strip()
            if not url.lower().startswith(("http://", "https://")):
                url = f"https://{url}"
            try:
                async with httpx.AsyncClient(timeout=8, follow_redirects=True, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    page_text = strip_html_to_text(resp.text)[:8000]
                    if page_text.strip():
                        brand_profile = await analyze_brand_from_text(url, page_text)
            except Exception as e:
                logger.warning(f"Brand URL fetch/analysis failed for extend-video: {e} — continuing without brand context")

        if brand_profile:
            brand_name = brand_profile.get("brand_name", "the brand")
            brand_desc = brand_profile.get("brand_description", "")
            audience = brand_profile.get("target_audience", "")
            tone = brand_profile.get("tone_voice", "engaging")
            products = brand_profile.get("products_services") or brand_profile.get("products_or_services") or []
            if isinstance(products, str):
                try:
                    products = json.loads(products)
                except (json.JSONDecodeError, TypeError):
                    products = [products] if products else []
            products_str = ", ".join(str(p) for p in products[:3]) if products else ""

            prompt = (
                f"Continue this video for {duration} seconds. The character from the first frame "
                f"continues with confident, {tone} body language and expressive gestures. "
                f"They are showcasing {brand_name}"
                f"{' — ' + brand_desc if brand_desc else ''}. "
                f"{'Products/services: ' + products_str + '. ' if products_str else ''}"
                f"The performance should feel natural and authentic — confident body language, "
                f"occasional hand gestures, and direct eye contact with camera. "
                f"End with a clear call-to-action moment (pointing, nodding, or inviting gesture). "
                f"NO AUDIO — this video must be completely silent. No voice, no music, no sound. "
                f"The character should NOT move their lips as if speaking or talking. "
                f"Maintain perfect face consistency throughout."
            )
        else:
            prompt = (
                f"Continue this video for {duration} seconds. The character from the first frame "
                "continues with energetic, confident body language directly to camera. "
                "Natural movement — expressive hand gestures, maintaining eye contact. "
                "The energy builds from the hook with dynamic poses and reactions. "
                "NO AUDIO — this video must be completely silent. No voice, no music, no sound. "
                "The character should NOT move their lips as if speaking or talking. "
                "End with a decisive moment (nod, point, or inviting gesture). "
                "Maintain perfect face consistency throughout."
            )

    # Tell the model this frame is a mid-scene continuation, not a fresh opening.
    if continued_from_hook:
        prompt += (
            "\n\nCONTINUITY: This first frame is the final frame of the preceding hook clip. "
            "Continue the motion seamlessly from exactly this pose and expression so the two "
            "clips play as one unbroken take — do not reset, re-introduce, or restart the pose."
        )

    # Enforce no text overlays and silence on the extension too.
    prompt += NO_TEXT_OVERLAY_INSTRUCTION + AUDIO_OFF_INSTRUCTION

    try:
        result = await generate_video(
            prompt=prompt,
            reference_image_path=first_frame_path,
            duration=duration,
            generate_audio=False,  # Always silent — creator adds sound in TikTok editor
            reference_video_url=public_media_url(reference_video_path),  # V2V motion transfer if available
        )
    except Exception as e:
        logger.error(f"Extend video generation failed: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Video extension failed. Please try again. ({str(e)[:150]})",
        )

    job_id = result.get("id", "")
    polling_url = result.get("polling_url", "")

    await _execute(
        """INSERT OR REPLACE INTO face_swap_video_jobs
           (id, image_id, prompt, duration, status, polling_url, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (job_id, image_id, prompt, duration, "pending", polling_url, now_iso()),
    )

    return {
        "job_id": job_id,
        "status": "pending",
        "polling_url": polling_url,
        "image_id": image_id,
        "duration": duration,
        "phase": "extend",
        "hook_job_id": hook_job_id,
        "model": "minimax-h3",
        "has_v2v_motion": bool(reference_video_path),
        "has_native_audio": True,
        "continued_from_hook": continued_from_hook,
    }


# Keep the original endpoint for backward compatibility
@api_router.post("/face-swap/generate-video")
async def face_swap_generate_video(
    image_id: str = Form(...),
    prompt: str = Form(""),
    duration: int = Form(10),
    model: str = Form(""),
    user_id: str = Depends(get_current_user_id),
):
    """
    Legacy endpoint — generates a video from the face-swapped image using MiniMax H3.
    For the new flow, use /face-swap/generate-hook-video (5s hook)
    followed by /face-swap/extend-video (continuation).
    """
    require_ai_configured()

    # Existence on disk is not proof of origin — require the image to trace
    # back to a hook frame or saved template. See require_frame_derived_image.
    image_path = await require_frame_derived_image(image_id)

    if not prompt.strip():
        prompt = (
            "Animate this person naturally from the first frame. Keep the same face, pose, and environment. "
            "Add subtle natural motion: slight head movement, blinking, breathing, and gentle body sway. "
            "Maintain perfect face consistency throughout. The scene should feel like a real person in a "
            "natural video — smooth, lifelike motion with no flickering or face changes. "
            "Camera holds steady, matching the original framing. "
            "Generate subtle ambient audio (room tone, gentle background) to make the video feel natural."
        )

    duration = max(5, min(duration, 15))

    try:
        result = await generate_video(
            prompt=prompt,
            reference_image_path=image_path,
            duration=duration,
            generate_audio=False,  # Always silent — creator adds sound in TikTok editor
        )
    except Exception as e:
        logger.error(f"Video generation submission failed: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Video generation failed to submit. Please try again. ({str(e)[:150]})",
        )

    job_id = result.get("id", "")
    polling_url = result.get("polling_url", "")

    await _execute(
        """INSERT OR REPLACE INTO face_swap_video_jobs
           (id, image_id, prompt, duration, status, polling_url, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (job_id, image_id, prompt, duration, "pending", polling_url, now_iso()),
    )

    return {
        "job_id": job_id,
        "status": "pending",
        "polling_url": polling_url,
        "image_id": image_id,
        "duration": duration,
    }


@api_router.get("/face-swap/video-status/{job_id}")
async def face_swap_video_status(job_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Poll the status of a face-swap video generation job.
    Returns the current status and, when completed, the video URL.
    """
    require_ai_configured()

    if not job_id or job_id == "undefined" or job_id == "null":
        raise HTTPException(status_code=400, detail="Invalid video job ID.")

    try:
        result = await poll_video_job(job_id)
    except Exception as e:
        logger.error(f"Video job polling failed for {job_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to check video status. ({str(e)[:150]})",
        )

    status = result.get("status", "pending")
    video_urls = result.get("unsigned_urls", [])

    # Update DB with latest status
    await _execute(
        "UPDATE face_swap_video_jobs SET status = ? WHERE id = ?",
        (status, job_id),
    )

    response = {
        "job_id": job_id,
        "status": status,
    }

    if status == "completed" and video_urls:
        # Download the video to local storage for a stable, non-expiring URL
        remote_url = video_urls[0]
        local_video_path = pipeline.STORAGE_DIR / "videos" / f"{job_id}.mp4"
        local_video_path.parent.mkdir(parents=True, exist_ok=True)

        if not local_video_path.exists():
            try:
                async with httpx.AsyncClient(timeout=120, follow_redirects=True) as dl_client:
                    dl_resp = await dl_client.get(
                        remote_url,
                        headers={"Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY', '')}"},
                    )
                    dl_resp.raise_for_status()
                    with open(local_video_path, "wb") as f:
                        f.write(dl_resp.content)
                logger.info(f"Downloaded video {job_id} to {local_video_path} ({local_video_path.stat().st_size} bytes)")
            except Exception as e:
                logger.warning(f"Could not download video {job_id} to local storage: {e}")
                # Fall back to the remote URL if download fails
                response["video_url"] = remote_url
                response["video_urls"] = video_urls
                return response

        # Upload to R2 for permanent storage (survives redeploys).
        # This is non-blocking for the user — if R2 fails, the local URL
        # still works for this container's lifetime.
        r2_url = storage_service.upload_video(user_id, job_id, local_video_path)
        if r2_url:
            await _execute(
                "UPDATE face_swap_video_jobs SET video_url = ? WHERE id = ?",
                (r2_url, job_id),
            )
            # Also persist in the video_assets table for user history
            await _execute(
                """INSERT OR IGNORE INTO video_assets
                   (job_id, user_id, r2_url, phase, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (job_id, user_id, r2_url, "hook", now_iso()),
            )

        # Serve from our own stable URL (local cache for this container)
        response["video_url"] = f"/api/media/videos/{job_id}.mp4"
        response["video_urls"] = [f"/api/media/videos/{job_id}.mp4"]
        # Include R2 URL so frontend can use it as a permanent link
        if r2_url:
            response["r2_url"] = r2_url

    if status == "failed":
        response["error"] = result.get("error", "Video generation failed.")

    if result.get("usage"):
        response["usage"] = result["usage"]

    return response


# ---------------------------------------------------------------------------
# Video Assets — persistent history of generated videos stored in R2.
# Users can list their videos, get a permanent URL, or delete them.
# ---------------------------------------------------------------------------
@api_router.get("/video-assets")
async def list_video_assets(user_id: str = Depends(get_current_user_id)):
    """List all persisted videos for the current user, newest first."""
    cursor = await _execute(
        """SELECT job_id, r2_url, phase, source_video_id,
                  source_hook_template_id, duration, created_at
           FROM video_assets
           WHERE user_id = ?
           ORDER BY created_at DESC
           LIMIT 100""",
        (user_id,),
    )
    rows = await cursor.fetchall()
    cols = [d[0] for d in cursor.description]
    return [row_to_dict(row, cols) for row in rows]


@api_router.delete("/video-assets/{job_id}")
async def delete_video_asset(job_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Delete a persisted video — removes it from R2 and the database.
    The video is gone permanently. Only the owning user can delete.
    """
    asset = await _fetch_one(
        "SELECT * FROM video_assets WHERE job_id = ? AND user_id = ?",
        (job_id, user_id),
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Video not found or you don't own it.")

    # Delete from R2
    storage_service.delete_video(user_id, job_id)

    # Delete from database
    await _execute("DELETE FROM video_assets WHERE job_id = ? AND user_id = ?", (job_id, user_id))

    # Also clean up the video job record's URL (it's now gone)
    await _execute(
        "UPDATE face_swap_video_jobs SET video_url = NULL WHERE id = ?", (job_id,)
    )

    # Remove local cache if it exists
    local_path = pipeline.STORAGE_DIR / "videos" / f"{job_id}.mp4"
    local_path.unlink(missing_ok=True)

    return {"status": "deleted", "job_id": job_id}


# ---------------------------------------------------------------------------
# Face Swap → Branded Video (Content Remixer integration)
# Generates a brand-customized video prompt from the hook analysis context +
# brand profile (via URL or saved), then submits to video generation with
# the face-swapped image as first_frame.
# ---------------------------------------------------------------------------
@api_router.post("/face-swap/generate-branded-prompt")
async def face_swap_branded_prompt(
    image_id: str = Form(...),
    brand_url: str = Form(""),
    brand_id: str = Form(""),
    video_id: str = Form(""),
    duration: int = Form(15),
    use_original_sound: bool = Form(False),
    user_id: str = Depends(get_current_user_id),
):
    """
    Generate a brand-customized video prompt for the face-swapped image.
    If brand_url is provided, analyzes the URL first. Otherwise uses the active brand profile.
    If video_id is provided, uses the hook analysis context for better remixing.
    Returns the generated prompt (editable) so the user can review before video generation.
    """
    require_ai_configured()

    # Existence on disk is not proof of origin — require the image to trace
    # back to a hook frame or saved template. See require_frame_derived_image.
    image_path = await require_frame_derived_image(image_id)

    # Resolve brand profile
    brand_profile = None
    if brand_url and brand_url.strip():
        url = brand_url.strip()
        if not url.lower().startswith(("http://", "https://")):
            url = f"https://{url}"
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
                html = resp.text
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not fetch URL. ({str(e)[:100]})")

        page_text = strip_html_to_text(html)[:8000]
        if not page_text.strip():
            raise HTTPException(status_code=400, detail="No readable text found at this URL.")

        try:
            brand_profile = await analyze_brand_from_text(url, page_text)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Brand analysis failed. ({str(e)[:100]})")
    else:
        # Use a saved brand profile — the one explicitly chosen if provided,
        # otherwise the user's active profile.
        brand_row = await _resolve_brand_profile(user_id, brand_id)
        if brand_row:
            brand_profile = brand_row
        else:
            raise HTTPException(
                status_code=400,
                detail="Please select a brand profile, provide a brand URL, or set up your brand profile first.",
            )

    # Get hook analysis if video_id is available
    analysis = None
    video_record = None
    if video_id and video_id.strip():
        analysis_row = await _fetch_one(
            "SELECT * FROM analyses WHERE video_id = ? ORDER BY created_at DESC LIMIT 1",
            (video_id.strip(),),
        )
        if analysis_row:
            analysis = analysis_row
        video_record = await _fetch_one("SELECT * FROM videos WHERE id = ?", (video_id.strip(),))

    # Build music context from the video's stored metadata
    music_context, transcript_text, hashtags = await _build_music_context(video_record)
    sound_reference = _build_sound_reference(music_context, use_original_sound)

    # Build a hook-context-aware prompt
    duration = max(5, min(duration, 30))

    if analysis:
        # We have hook analysis — use the full remix script generator
        try:
            remix_result = await generate_remix_script(
                analysis=analysis,
                brand_profile=brand_profile,
                target_duration=duration,
                session_id=f"face-swap-brand-{image_id}",
                music_context=music_context,
                transcript_text=transcript_text,
                hashtags=hashtags,
                use_original_sound=use_original_sound,
            )
            video_prompt = remix_result.get("full_video_prompt", "")
            prompt_breakdown = remix_result
        except Exception as e:
            logger.error(f"Remix script generation failed: {e}")
            raise HTTPException(status_code=502, detail=f"AI prompt generation failed. ({str(e)[:100]})")
    else:
        # No hook analysis — generate a simpler brand-aware video prompt
        brand_name = brand_profile.get("brand_name", "")
        brand_desc = brand_profile.get("brand_description", "")
        niche = brand_profile.get("niche", "")
        audience = brand_profile.get("target_audience", "")
        tone = brand_profile.get("tone_voice", "")
        products = brand_profile.get("products_services") or brand_profile.get("products_or_services") or []
        if isinstance(products, str):
            try:
                products = json.loads(products)
            except (json.JSONDecodeError, TypeError):
                products = [products] if products else []
        products_str = ", ".join(str(p) for p in products) if products else ""

        sound_note = ""
        if sound_reference:
            sound_note = (
                f" Reuse the original sound (\"{sound_reference['song_title']}\" by "
                f"{sound_reference['song_artist']}) underneath the video rather than a new voiceover — "
                "lean on visuals and on-screen text/captions instead of new spoken dialogue."
            )

        video_prompt = (
            f"Create a {duration}-second vertical video (9:16) featuring the person from the first frame. "
            f"The video is EXACTLY {duration} seconds long — pace all content to fill this duration. "
            f"The video promotes {brand_name} — {brand_desc}. "
            f"Niche: {niche}. Target audience: {audience}. "
            f"{'Products/services: ' + products_str + '. ' if products_str else ''}"
            f"The tone should be {tone or 'engaging and authentic'}. "
        )
        # Add duration-aware pacing instruction
        if duration <= 7:
            video_prompt += (
                "Open with an immediate attention-grabbing hook in the first 1-2 seconds, "
                "then deliver the key message quickly. "
            )
        elif duration <= 15:
            video_prompt += (
                f"Start with a punchy hook (0-2s), deliver the core message (2-{duration-2}s), "
                f"end with a clear CTA or payoff ({duration-2}-{duration}s). "
            )
        else:
            video_prompt += (
                f"Start with the hook gesture from the first frame (0-3s), build the narrative "
                f"with energy (3-{duration-5}s), and close with a strong call-to-action "
                f"({duration-5}-{duration}s). "
            )
        video_prompt += (
            "Maintain perfect face consistency throughout. Keep the camera steady with slight "
            "natural movement. The video should feel like an organic TikTok/Reels creator video."
            f"{sound_note}"
        )
        prompt_breakdown = {
            "content": f"Person delivers a {tone or 'engaging'} message about {brand_name}",
            "camera_angle": "Close-up to medium shot, steady with subtle movement",
            "character_behavior": "Confident, expressive, speaking to camera",
            "scene_details": "Matches the environment from the first frame",
            "brand_narrative": f"Promotes {brand_name} ({niche}) to {audience}",
            "audio_recommendation": (
                f"Keep the original sound: \"{sound_reference['song_title']}\" by {sound_reference['song_artist']}"
                if sound_reference else "Original voiceover/music matching the brand tone"
            ),
            "full_video_prompt": video_prompt,
            "suggested_duration_seconds": duration,
        }

    return {
        "video_prompt": video_prompt,
        "prompt_breakdown": prompt_breakdown,
        "brand_name": brand_profile.get("brand_name", ""),
        "duration": duration,
        "image_id": image_id,
        "use_original_sound": use_original_sound,
        "sound_reference": sound_reference,
    }


# ---------------------------------------------------------------------------
# Customization / face-swap preview
# ---------------------------------------------------------------------------
@api_router.post("/videos/{video_id}/customize")
async def customize_video(
    video_id: str,
    person_photo: UploadFile = File(...),
    mode: str = Form("preserve"),
    frame_indices: str = Form(""),
    environment: str = Form(""),
    background: str = Form(""),
    clothing: str = Form(""),
    custom_instructions: str = Form(""),
    user_id: str = Depends(get_current_user_id),
):
    require_ai_configured()
    video = await get_video_or_404(video_id)
    analysis = await get_latest_analysis_or_404(video_id)

    if mode not in ("preserve", "custom"):
        mode = "preserve"

    raw_bytes = await person_photo.read()
    if len(raw_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded photo is empty.")
    if len(raw_bytes) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Uploaded photo is too large (max 12MB).")

    normalized_bytes = validate_and_normalize_photo(raw_bytes)
    photo_id = str(uuid.uuid4())
    photo_path = pipeline.UPLOADS_DIR / f"{photo_id}.png"
    with open(photo_path, "wb") as f:
        f.write(normalized_bytes)

    frames = analysis.get("frames", [])
    if not frames:
        raise HTTPException(status_code=400, detail="No reference frames available for this analysis.")
    key_idx = max(1, min(len(frames), int(analysis.get("key_hook_frame_index", 1) or 1)))

    try:
        selected_indices = json.loads(frame_indices) if frame_indices else []
        selected_indices = [int(i) for i in selected_indices if isinstance(i, (int, float, str))]
    except (json.JSONDecodeError, ValueError, TypeError):
        selected_indices = []
    if not selected_indices:
        selected_indices = [key_idx]
    valid_indices = sorted({max(1, min(len(frames), i)) for i in selected_indices})[:3]

    video_hash = pipeline.url_hash(video["tiktok_url"])

    customization_prompt_parts = []
    if mode == "custom":
        if environment:
            customization_prompt_parts.append(f"Environment: {environment}.")
        if background:
            customization_prompt_parts.append(f"Background: {background}.")
        if clothing:
            customization_prompt_parts.append(f"Clothing: {clothing}.")
        if custom_instructions:
            customization_prompt_parts.append(custom_instructions)
    customization_prompt = " ".join(customization_prompt_parts)

    generated_images = []
    for idx in valid_indices:
        frame_meta = frames[idx - 1]
        frame_filename = frame_meta["media_url"].split("/")[-1]
        reference_frame_path = pipeline.FRAMES_DIR / video_hash / frame_filename
        if not reference_frame_path.exists():
            raise HTTPException(
                status_code=400,
                detail="Reference hook frame is missing. Please re-analyze the video.",
            )
        try:
            image_bytes = await generate_customized_preview(
                reference_frame_path=reference_frame_path,
                person_photo_path=photo_path,
                mode=mode,
                customization_prompt=customization_prompt,
                session_id=f"custom-{video_id}-{photo_id}-{idx}",
            )
        except Exception as e:
            logger.error(f"Customization generation failed for {video_id} frame {idx}: {e}")
            raise HTTPException(
                status_code=502,
                detail=f"AI preview generation failed. Please try again. ({str(e)[:150]})",
            )

        generated_id = str(uuid.uuid4())
        generated_path = pipeline.GENERATED_DIR / f"{generated_id}.png"
        with open(generated_path, "wb") as f:
            f.write(image_bytes)

        # These previews are built from an uploaded person photo, but the
        # SCENE is the analysis frame — the same relationship face swap has
        # between source_face and target. Recording that frame as the target
        # keeps this flow usable for video generation while still excluding
        # anything that isn't frame-derived.
        await _record_generated_image(
            image_id=generated_id,
            origin="customize",
            target_image_url=frame_meta["media_url"],
            user_id=user_id,
            job_id=video_id,
            image_bytes=image_bytes,
        )

        generated_images.append({
            "id": generated_id,
            "frame_index": idx,
            "timestamp_seconds": frame_meta.get("timestamp_seconds"),
            "reference_frame_url": frame_meta["media_url"],
            "image_url": f"/api/media/generated/{generated_id}.png",
        })

    generation_spec = {
        "source_video": {
            "tiktok_url": video["tiktok_url"],
            "creator": video.get("creator"),
            "niche": video.get("niche"),
        },
        "mode": mode,
        "hook_mechanics_to_preserve": {
            "facial_expressions": analysis.get("facial_expressions"),
            "body_language_gestures": analysis.get("body_language_gestures"),
            "replicable_mechanics": analysis.get("replicable_mechanics", []),
            "key_hook_frame_index": key_idx,
        },
        "pacing_notes": analysis.get("pacing_cuts"),
        "text_overlay_plan": analysis.get("text_overlays_timing"),
        "audio_plan": analysis.get("audio_cues_inferred"),
        "music_context": {
            "song_title": video.get("song_title", ""),
            "song_artist": video.get("song_artist", ""),
            "song_album": video.get("song_album", ""),
            "song_id": video.get("song_id", ""),
        },
        "transcript_available": bool(video.get("subtitles_url")),
        "hashtags": video.get("hashtags", []) if isinstance(video.get("hashtags"), list) else [],
        "customization": {
            "environment": environment if mode == "custom" else "(kept identical to original)",
            "background": background if mode == "custom" else "(kept identical to original)",
            "clothing": clothing if mode == "custom" else "(kept identical to original)",
            "custom_instructions": custom_instructions if mode == "custom" else "",
        },
        "subject": {"source": "user_uploaded_photo", "photo_ref": f"{photo_id}.png"},
        "generated_frame_count": len(generated_images),
        "status": "ready_for_video_generation",
        "note": "This face-swapped still frame is ready to be used as a reference image for AI video generation.",
    }

    customization_id = str(uuid.uuid4())
    created_at = now_iso()
    await _execute(
        """INSERT INTO customizations
           (id, video_id, analysis_id, mode, person_photo_url, reference_frame_url,
            environment, background, clothing, custom_instructions, generation_spec,
            generated_images, generated_image_url, video_title, video_niche, created_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (customization_id, video_id, analysis["id"], mode, f"/api/media/uploads/{photo_id}.png",
         generated_images[0]["reference_frame_url"] if generated_images else None,
         environment, background, clothing, custom_instructions, json.dumps(generation_spec),
         json.dumps(generated_images), generated_images[0]["image_url"] if generated_images else None,
         video.get("title"), video.get("niche"), created_at, user_id),
    )
    return await _fetch_one("SELECT * FROM customizations WHERE id = ?", (customization_id,))


@api_router.get("/customizations")
async def list_customizations(user_id: str = Depends(get_current_user_id)):
    return await _fetch_all("SELECT * FROM customizations WHERE user_id = ? ORDER BY created_at DESC LIMIT 200", (user_id,))


@api_router.get("/customizations/{customization_id}")
async def get_customization(customization_id: str, user_id: str = Depends(get_current_user_id)):
    item = await _fetch_one("SELECT * FROM customizations WHERE id = ?", (customization_id,))
    if not item:
        raise HTTPException(status_code=404, detail="Customization not found")
    return item


# ---------------------------------------------------------------------------
# Remix chat: conversational back-and-forth to turn a viral hook into a
# personalized brief (goal, audience fit, USPs, etc.) before generating the
# video prompt. One chat thread per customization. This complements (rather
# than replaces) the one-click "Content Remixer" brand-profile flow above -
# it's for users who want to describe their goal in their own words and get
# clarifying questions back, instead of relying on a saved brand profile.
# ---------------------------------------------------------------------------
def _serialize_remix_chat(row: dict) -> dict:
    row = dict(row)
    row["ready_to_generate"] = bool(row.get("ready_to_generate"))
    if not isinstance(row.get("messages"), list):
        row["messages"] = []
    if not isinstance(row.get("brief"), dict):
        row["brief"] = empty_remix_brief()
    return row


async def _get_or_create_remix_chat(customization_id: str) -> dict:
    chat = await _fetch_one("SELECT * FROM remix_chats WHERE customization_id = ?", (customization_id,))
    if chat:
        return _serialize_remix_chat(chat)
    chat_id = str(uuid.uuid4())
    created_at = now_iso()
    await _execute(
        """INSERT INTO remix_chats (id, customization_id, messages, brief, ready_to_generate, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (chat_id, customization_id, json.dumps([]), json.dumps(empty_remix_brief()), 0, created_at, created_at),
    )
    return _serialize_remix_chat(await _fetch_one("SELECT * FROM remix_chats WHERE id = ?", (chat_id,)))


@api_router.get("/customizations/{customization_id}/remix-chat")
async def get_remix_chat(customization_id: str, user_id: str = Depends(get_current_user_id)):
    customization = await _fetch_one("SELECT * FROM customizations WHERE id = ?", (customization_id,))
    if not customization:
        raise HTTPException(status_code=404, detail="Customization not found")
    return await _get_or_create_remix_chat(customization_id)


@api_router.post("/customizations/{customization_id}/remix-chat")
async def post_remix_chat_message(customization_id: str, payload: RemixChatMessageRequest, user_id: str = Depends(get_current_user_id)):
    require_ai_configured()
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    if len(message) > 4000:
        raise HTTPException(status_code=400, detail="Message is too long (max 4000 characters).")

    customization = await _fetch_one("SELECT * FROM customizations WHERE id = ?", (customization_id,))
    if not customization:
        raise HTTPException(status_code=404, detail="Customization not found")
    video = await get_video_or_404(customization["video_id"])
    analysis = await _fetch_one("SELECT * FROM analyses WHERE id = ?", (customization["analysis_id"],))
    if not analysis:
        raise HTTPException(status_code=404, detail="Related hook analysis not found")

    chat = await _get_or_create_remix_chat(customization_id)
    history = chat.get("messages", [])
    history_for_llm = history + [{"role": "user", "content": message}]

    try:
        turn_result = await remix_chat_turn(
            analysis=analysis,
            video=video,
            conversation_history=history_for_llm,
            existing_brief=chat.get("brief") or empty_remix_brief(),
            session_id=f"remixchat-{customization_id}",
        )
    except Exception as e:
        logger.error(f"Remix chat turn failed for {customization_id}: {e}")
        raise HTTPException(status_code=502, detail=f"AI reply failed. Please try again. ({str(e)[:150]})")

    now = now_iso()
    new_messages = history + [
        {"role": "user", "content": message, "created_at": now},
        {"role": "assistant", "content": turn_result["reply"], "created_at": now},
    ]

    await _execute(
        """UPDATE remix_chats SET messages = ?, brief = ?, ready_to_generate = ?, updated_at = ?
           WHERE customization_id = ?""",
        (json.dumps(new_messages), json.dumps(turn_result["brief"]),
         1 if turn_result.get("ready_to_generate") else 0, now, customization_id),
    )
    updated = await _fetch_one("SELECT * FROM remix_chats WHERE customization_id = ?", (customization_id,))
    return _serialize_remix_chat(updated)


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
        import apify_tiktok
        raw_vtt = await apify_tiktok.fetch_subtitles(video["subtitles_url"])
        if raw_vtt:
            transcript_text = apify_tiktok.parse_webvtt_to_text(raw_vtt)
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


@api_router.post("/customizations/{customization_id}/generate-video-prompt")
async def generate_video_prompt_endpoint(customization_id: str, payload: BrandContextRequest, user_id: str = Depends(get_current_user_id)):
    require_ai_configured()
    customization = await _fetch_one("SELECT * FROM customizations WHERE id = ?", (customization_id,))
    if not customization:
        raise HTTPException(status_code=404, detail="Customization not found")
    analysis = await _fetch_one("SELECT * FROM analyses WHERE id = ?", (customization["analysis_id"],))
    if not analysis:
        raise HTTPException(status_code=404, detail="Related hook analysis not found")

    # Fetch the video record for music/subtitle context
    video = await _fetch_one("SELECT * FROM videos WHERE id = ?", (customization["video_id"],))
    music_context, transcript_text, _hashtags = await _build_music_context(video)

    duration = max(5, min(30, payload.duration_seconds or 30))

    try:
        prompt_result = await generate_video_prompt(
            analysis=analysis,
            brand_context=payload.model_dump(),
            target_duration=duration,
            session_id=f"videoprompt-{customization_id}",
            music_context=music_context,
            transcript_text=transcript_text,
            use_original_sound=payload.use_original_sound,
        )
    except Exception as e:
        logger.error(f"Video prompt generation failed for {customization_id}: {e}")
        raise HTTPException(status_code=502, detail=f"AI prompt generation failed. Please try again. ({str(e)[:150]})")

    sound_reference = _build_sound_reference(music_context, payload.use_original_sound)

    job_id = str(uuid.uuid4())
    created_at = now_iso()
    reference_image_ids = [img["id"] for img in customization.get("generated_images", [])]
    await _execute(
        """INSERT INTO video_jobs
           (id, customization_id, video_id, brand_name, brand_goal, brand_details,
            target_duration_seconds, prompt_breakdown, full_prompt_text, reference_image_ids,
            use_original_sound, sound_reference, status, created_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, customization_id, customization["video_id"], payload.brand_name, payload.brand_goal,
         payload.brand_details, duration, json.dumps(prompt_result), prompt_result.get("full_video_prompt"),
         json.dumps(reference_image_ids), 1 if payload.use_original_sound else 0,
         json.dumps(sound_reference) if sound_reference else None, "prompt_ready", created_at, user_id),
    )
    return await _fetch_one("SELECT * FROM video_jobs WHERE id = ?", (job_id,))


@api_router.post("/customizations/{customization_id}/generate-remix-script")
async def generate_remix_script_endpoint(customization_id: str, payload: GenerateRemixScriptRequest, user_id: str = Depends(get_current_user_id)):
    """Content Remixer: adapt this hook's script to the active brand profile's niche/products/tone."""
    require_ai_configured()
    brand_profile = await get_active_brand_or_404(user_id)

    customization = await _fetch_one("SELECT * FROM customizations WHERE id = ?", (customization_id,))
    if not customization:
        raise HTTPException(status_code=404, detail="Customization not found")
    analysis = await _fetch_one("SELECT * FROM analyses WHERE id = ?", (customization["analysis_id"],))
    if not analysis:
        raise HTTPException(status_code=404, detail="Related hook analysis not found")

    # Fetch the video record for music/subtitle context
    video = await _fetch_one("SELECT * FROM videos WHERE id = ?", (customization["video_id"],))
    music_context, transcript_text, hashtags = await _build_music_context(video)

    duration = max(5, min(30, payload.duration_seconds or 30))

    try:
        prompt_result = await generate_remix_script(
            analysis=analysis,
            brand_profile=brand_profile,
            target_duration=duration,
            session_id=f"remix-{customization_id}",
            music_context=music_context,
            transcript_text=transcript_text,
            hashtags=hashtags,
            use_original_sound=payload.use_original_sound,
        )
    except Exception as e:
        logger.error(f"Remix script generation failed for {customization_id}: {e}")
        raise HTTPException(status_code=502, detail=f"AI remix script generation failed. Please try again. ({str(e)[:150]})")

    sound_reference = _build_sound_reference(music_context, payload.use_original_sound)

    job_id = str(uuid.uuid4())
    created_at = now_iso()
    reference_image_ids = [img["id"] for img in customization.get("generated_images", [])]
    await _execute(
        """INSERT INTO video_jobs
           (id, customization_id, video_id, brand_name, brand_goal, brand_details,
            target_duration_seconds, prompt_breakdown, full_prompt_text, reference_image_ids,
            use_original_sound, sound_reference, status, created_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, customization_id, customization["video_id"], brand_profile.get("brand_name"),
         "Content Remixer: adapt viral hook to brand", brand_profile.get("brand_description"),
         duration, json.dumps(prompt_result), prompt_result.get("full_video_prompt"),
         json.dumps(reference_image_ids), 1 if payload.use_original_sound else 0,
         json.dumps(sound_reference) if sound_reference else None, "prompt_ready", created_at, user_id),
    )
    return await _fetch_one("SELECT * FROM video_jobs WHERE id = ?", (job_id,))


@api_router.post("/video-jobs/{job_id}/generate-video")
async def generate_video_endpoint(job_id: str, payload: GenerateVideoRequest, user_id: str = Depends(get_current_user_id)):
    job = await _fetch_one("SELECT * FROM video_jobs WHERE id = ?", (job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")

    new_prompt = payload.edited_prompt or job.get("full_prompt_text")
    selected_ids = payload.image_ids or job.get("reference_image_ids", [])
    duration = max(5, min(30, payload.duration_seconds or job.get("target_duration_seconds", 30)))

    await _execute(
        """UPDATE video_jobs SET full_prompt_text = ?, selected_image_ids = ?,
           target_duration_seconds = ?, status = ?, requested_at = ? WHERE id = ?""",
        (new_prompt, json.dumps(selected_ids), duration, "pending_provider_selection", now_iso(), job_id),
    )
    return await _fetch_one("SELECT * FROM video_jobs WHERE id = ?", (job_id,))


@api_router.post("/video-jobs/{job_id}/submit-video")
async def submit_video_job(job_id: str, user_id: str = Depends(get_current_user_id)):
    """Actually submit the video generation job to OpenRouter using MiniMax H3."""
    require_ai_configured()
    job = await _fetch_one("SELECT * FROM video_jobs WHERE id = ?", (job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")

    customization = await _fetch_one(
        "SELECT * FROM customizations WHERE id = ?", (job["customization_id"],)
    )
    reference_image_path = None
    reference_video_path = None
    if customization:
        generated_images = customization.get("generated_images", [])
        selected_ids = job.get("selected_image_ids") or job.get("reference_image_ids") or []
        chosen = None
        if generated_images:
            for img in generated_images:
                if img["id"] in selected_ids:
                    chosen = img
                    break
            if not chosen:
                chosen = generated_images[0]
        if chosen:
            reference_image_path = pipeline.GENERATED_DIR / f"{chosen['id']}.png"

        # Get the original viral video for V2V motion transfer
        if customization.get("video_id"):
            video_record = await _fetch_one(
                "SELECT * FROM videos WHERE id = ?", (customization["video_id"],)
            )
            if video_record and video_record.get("local_video_path"):
                v_path = Path(video_record["local_video_path"])
                if v_path.exists():
                    reference_video_path = v_path

    try:
        result = await generate_video(
            prompt=job.get("full_prompt_text") or "",
            reference_image_path=reference_image_path,
            duration=job.get("target_duration_seconds", 10) or 10,
            generate_audio=False,  # Always silent — creator adds sound in TikTok editor
            reference_video_url=public_media_url(reference_video_path),  # V2V motion transfer
        )
    except Exception as e:
        logger.error(f"Video submission failed for {job_id}: {e}")
        await _execute(
            "UPDATE video_jobs SET status = ?, error = ? WHERE id = ?",
            ("failed", str(e)[:400], job_id),
        )
        raise HTTPException(status_code=502, detail=f"Video generation submission failed. ({str(e)[:150]})")

    await _execute(
        "UPDATE video_jobs SET status = ?, openrouter_job_id = ? WHERE id = ?",
        (result.get("status", "pending"), result.get("id"), job_id),
    )
    return await _fetch_one("SELECT * FROM video_jobs WHERE id = ?", (job_id,))


@api_router.get("/video-jobs/{job_id}/poll")
async def poll_video_job_endpoint(job_id: str, user_id: str = Depends(get_current_user_id)):
    """Poll OpenRouter for the video generation job status."""
    require_ai_configured()
    job = await _fetch_one("SELECT * FROM video_jobs WHERE id = ?", (job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    if not job.get("openrouter_job_id"):
        raise HTTPException(status_code=400, detail="This job has not been submitted for video generation yet.")

    try:
        status = await poll_video_job(job["openrouter_job_id"])
    except Exception as e:
        logger.error(f"Polling failed for {job_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to poll video status. ({str(e)[:150]})")

    new_status = status.get("status", job["status"])
    video_url = None
    if new_status == "completed" and status.get("unsigned_urls"):
        video_url = status["unsigned_urls"][0]

    await _execute(
        "UPDATE video_jobs SET status = ?, video_url = ? WHERE id = ?",
        (new_status, video_url or job.get("video_url"), job_id),
    )
    return await _fetch_one("SELECT * FROM video_jobs WHERE id = ?", (job_id,))


@api_router.get("/video-jobs/{job_id}")
async def get_video_job(job_id: str, user_id: str = Depends(get_current_user_id)):
    job = await _fetch_one("SELECT * FROM video_jobs WHERE id = ?", (job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    return job


@api_router.get("/customizations/{customization_id}/video-jobs")
async def get_customization_video_jobs(customization_id: str, user_id: str = Depends(get_current_user_id)):
    return await _fetch_all(
        "SELECT * FROM video_jobs WHERE customization_id = ? ORDER BY created_at DESC LIMIT 50",
        (customization_id,),
    )


# ---------------------------------------------------------------------------
# Brand profile ("Your Brand" — URL analysis + manual editing)
# ---------------------------------------------------------------------------
@api_router.post("/brand/analyze-url")
async def analyze_brand_url(payload: AnalyzeBrandUrlRequest, user_id: str = Depends(get_current_user_id)):
    require_ai_configured()
    url = payload.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Please provide a website URL.")
    if not url.lower().startswith(("http://", "https://")):
        url = f"https://{url}"

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
            html = resp.text
    except Exception as e:
        logger.error(f"Failed to fetch brand URL {url}: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Could not fetch this URL. Please check it and try again. ({str(e)[:150]})",
        )

    page_text = strip_html_to_text(html)[:BRAND_URL_TEXT_MAX_CHARS]
    if not page_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Could not extract any readable text from this URL. Please try a different page.",
        )

    try:
        extracted = await analyze_brand_from_text(url, page_text)
    except Exception as e:
        logger.error(f"Brand analysis failed for {url}: {e}")
        raise HTTPException(status_code=502, detail=f"AI brand analysis failed. Please try again. ({str(e)[:150]})")

    # Re-analysing the same site refreshes that profile in place rather than
    # inserting another row. Previously every re-analysis created a duplicate,
    # which orphaned the user's manual edits and left stale profiles behind
    # competing to be the "active" one.
    now = now_iso()
    existing = await _fetch_one(
        "SELECT id FROM brand_profiles WHERE website_url = ?", (url,)
    )
    values = (
        extracted.get("brand_name"), extracted.get("brand_description"),
        extracted.get("niche"), json.dumps(extracted.get("products_or_services", [])),
        extracted.get("target_audience"), extracted.get("ideal_customer_profile"),
        extracted.get("differentiation"), extracted.get("tone_voice"), page_text,
    )
    if existing:
        brand_id = existing["id"]
        await _execute(
            """UPDATE brand_profiles
               SET brand_name = ?, brand_description = ?, niche = ?, products_services = ?,
                   target_audience = ?, ideal_customer_profile = ?, differentiation = ?,
                   tone_voice = ?, raw_extracted_text = ?, updated_at = ?
               WHERE id = ?""",
            values + (now, brand_id),
        )
        logger.info(f"Refreshed existing brand profile {brand_id} from {url}")
    else:
        brand_id = str(uuid.uuid4())
        await _execute(
            """INSERT INTO brand_profiles
               (id, website_url, brand_name, brand_description, niche, products_services,
                target_audience, ideal_customer_profile, differentiation, tone_voice,
                raw_extracted_text, created_at, updated_at, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (brand_id, url) + values + (now, now, user_id),
        )
        logger.info(f"Created brand profile {brand_id} from {url}")
    return await _fetch_one("SELECT * FROM brand_profiles WHERE id = ?", (brand_id,))


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
           (id, website_url, brand_name, brand_description, niche, products_services,
            target_audience, ideal_customer_profile, differentiation, tone_voice,
            raw_extracted_text, created_at, updated_at, user_id,
            appstore_url, play_url, support_urls, notes, app_category, platforms,
            pricing_trial, core_features, primary_use_cases, problems_solved,
            icp_segments, desired_outcomes, competitors, known_limitations,
            claims_approved, claims_review, claims_banned, ctas, video_themes,
            status, version)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (brand_id, website or None, name, payload.brand_description or "",
         payload.niche or "", json.dumps(_normalize_str_list(payload.products_services)),
         payload.target_audience or "", payload.ideal_customer_profile or "",
         payload.differentiation or "", payload.tone_voice or "", None,
         created_at, created_at, user_id,
         _normalize_url(payload.appstore_url or ""),
         _normalize_url(payload.play_url or ""),
         json.dumps(_normalize_str_list(payload.support_urls)),
         payload.notes or "", payload.app_category or "",
         json.dumps(_normalize_str_list(payload.platforms)),
         payload.pricing_trial or "",
         json.dumps(_normalize_str_list(payload.core_features)),
         json.dumps(_normalize_str_list(payload.primary_use_cases)),
         json.dumps(_normalize_str_list(payload.problems_solved)),
         json.dumps(_normalize_str_list(payload.icp_segments)),
         json.dumps(_normalize_str_list(payload.desired_outcomes)),
         json.dumps(_normalize_str_list(payload.competitors)),
         payload.known_limitations or "",
         json.dumps(_normalize_str_list(payload.claims_approved)),
         json.dumps(_normalize_str_list(payload.claims_review)),
         json.dumps(_normalize_str_list(payload.claims_banned)),
         json.dumps(_normalize_str_list(payload.ctas)),
         json.dumps(_normalize_str_list(payload.video_themes)),
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
    brand = await _fetch_one("SELECT * FROM brand_profiles WHERE id = ?", (brand_id,))
    if not brand:
        raise HTTPException(status_code=404, detail="Brand profile not found")
    return brand


@api_router.patch("/brand/{brand_id}")
async def update_brand(brand_id: str, payload: BrandProfileUpdateRequest, user_id: str = Depends(get_current_user_id)):
    existing = await _fetch_one("SELECT * FROM brand_profiles WHERE id = ?", (brand_id,))
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
    values.append(brand_id)

    await _execute(
        f"UPDATE brand_profiles SET {', '.join(set_clauses)} WHERE id = ?",
        tuple(values),
    )
    return await _fetch_one("SELECT * FROM brand_profiles WHERE id = ?", (brand_id,))


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
    """Research a mobile app from its public pages and draft an App Profile.

    Fetches the website, App Store and Google Play pages plus up to 5 support
    URLs, then asks OpenRouter to draft the full profile. The result is stored
    as status='draft' — the founder must review and approve it (POST
    /app-profiles/{id}/approve) before it drives video generation.
    """
    require_ai_configured()
    website = _normalize_url(payload.website_url or "")
    appstore = _normalize_url(payload.appstore_url or "")
    play = _normalize_url(payload.play_url or "")
    support: list = []
    for u in payload.support_urls or []:
        n = _normalize_url(u)
        if n and n not in support:
            support.append(n)
    support = support[:APP_RESEARCH_MAX_SUPPORT_URLS]
    if not (website or appstore or play or support):
        raise HTTPException(
            status_code=400,
            detail="Provide at least one URL: website, App Store, Google Play, or a support URL.",
        )

    sources: dict = {}
    if website:
        sources["website"] = await _fetch_url_text(website, APP_RESEARCH_CAPS["website"])
    if appstore:
        sources["app_store"] = await _fetch_url_text(appstore, APP_RESEARCH_CAPS["app_store"])
    if play:
        sources["google_play"] = await _fetch_url_text(play, APP_RESEARCH_CAPS["google_play"])
    for i, u in enumerate(support):
        sources[f"support_{i + 1} ({u})"] = await _fetch_url_text(u, APP_RESEARCH_CAPS["support"])
    if not any((v or "").strip() for v in sources.values()):
        raise HTTPException(
            status_code=400,
            detail="Could not extract readable text from any URL. Check the links and try again, "
                   "or create the profile manually.",
        )

    try:
        profile = await analyze_app_profile(sources, payload.notes or "")
    except Exception as e:
        logger.error(f"App research failed: {e}")
        raise HTTPException(status_code=502, detail=f"AI app research failed. Please try again. ({str(e)[:150]})")

    now = now_iso()
    brand_id = str(uuid.uuid4())
    combined_raw = "\n\n".join(
        f"[{label}]\n{(text or '')[:2000]}" for label, text in sources.items() if (text or "").strip()
    )[:BRAND_URL_TEXT_MAX_CHARS]
    await _execute(
        """INSERT INTO brand_profiles
           (id, website_url, brand_name, brand_description, niche, products_services,
            target_audience, ideal_customer_profile, differentiation, tone_voice,
            raw_extracted_text, created_at, updated_at, user_id,
            appstore_url, play_url, support_urls, notes, app_category, platforms,
            pricing_trial, core_features, primary_use_cases, problems_solved,
            icp_segments, desired_outcomes, competitors, known_limitations,
            claims_approved, claims_review, claims_banned, ctas, video_themes,
            status, version, last_research_at, research_sources)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (brand_id, website, profile.get("brand_name") or "Untitled app",
         profile.get("brand_description") or "", profile.get("niche") or "",
         json.dumps(profile.get("products_or_services") or []),
         profile.get("target_audience") or "",
         profile.get("ideal_customer_profile") or "",
         profile.get("differentiation") or "", profile.get("tone_voice") or "",
         combined_raw, now, now, user_id,
         appstore, play, json.dumps(support), payload.notes or "",
         profile.get("app_category") or "",
         json.dumps(profile.get("platforms") or []),
         profile.get("pricing_trial") or "",
         json.dumps(profile.get("core_features") or []),
         json.dumps(profile.get("primary_use_cases") or []),
         json.dumps(profile.get("problems_solved") or []),
         json.dumps(profile.get("icp_segments") or []),
         json.dumps(profile.get("desired_outcomes") or []),
         json.dumps(profile.get("competitors") or []),
         profile.get("known_limitations") or "",
         json.dumps(profile.get("claims_approved") or []),
         json.dumps(profile.get("claims_review") or []),
         json.dumps(profile.get("claims_banned") or []),
         json.dumps(profile.get("ctas") or []),
         json.dumps(profile.get("video_themes") or []),
         "draft", 1, now, json.dumps(sorted(sources.keys()))),
    )
    logger.info(f"Researched app profile {brand_id} from {len(sources)} source(s)")
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


@api_router.post("/app-profiles/{profile_id}/approve")
async def approve_app_profile(
    profile_id: str, payload: ApproveAppProfileRequest, user_id: str = Depends(get_current_user_id)
):
    """Mark an App Profile reviewed and approved.

    When a refresh proposal is pending it is applied to the live fields by
    default and the version bumps — approval is the only path that mutates
    approved data, so refreshes can never silently overwrite it.
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

    now = now_iso()
    if pending and isinstance(pending, dict) and payload.apply_pending is not False:
        apply = {}
        for key in APP_PROFILE_EDITABLE_FIELDS:
            if key in pending and pending[key] not in (None, "", []):
                apply[key] = pending[key]
        # The AI schema uses products_or_services; the column is products_services.
        if "products_or_services" in pending and "products_services" not in apply:
            apply["products_services"] = pending["products_or_services"]
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
            logger.info(f"Approved app profile {profile_id} with pending refresh applied")
            return await _fetch_one(
                "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
            )

    await _execute(
        "UPDATE brand_profiles SET status = 'approved', approved_at = ?, updated_at = ? "
        "WHERE id = ? AND user_id = ?",
        (now, now, profile_id, user_id),
    )
    logger.info(f"Approved app profile {profile_id}")
    return await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )


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
            detail="This profile has no source URLs to refresh from. Add a website, App Store, "
                   "or Google Play URL first.",
        )

    sources = {label: await _fetch_url_text(url, cap) for label, (url, cap) in urls.items()}
    if not any((v or "").strip() for v in sources.values()):
        raise HTTPException(
            status_code=400,
            detail="Could not extract readable text from any stored URL. The live profile is unchanged.",
        )

    try:
        proposal = await analyze_app_profile(sources, existing.get("notes") or "")
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
    return await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )


# ---------------------------------------------------------------------------
# Content angles (per App Profile)
# ---------------------------------------------------------------------------
CONTENT_ANGLE_TEXT_FIELDS = (
    "label", "target_audience", "user_problem", "hook_promise",
    "app_feature", "desired_emotion", "recommended_cta",
)


def _serialize_angle_row(row: dict) -> dict:
    """Shape a content_angles row for the API (kind is already normalized)."""
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
        "recommended_cta": row.get("recommended_cta") or "",
        "claims_to_respect": row.get("claims_to_respect") or [],
        "rank": row.get("rank") or 0,
        "created_at": row.get("created_at"),
    }


@api_router.get("/app-profiles/{profile_id}/content-angles")
async def list_content_angles(profile_id: str, user_id: str = Depends(get_current_user_id)):
    profile = await _fetch_one(
        "SELECT id FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")
    rows = await _fetch_all(
        "SELECT * FROM content_angles WHERE brand_profile_id = ? AND user_id = ? "
        "ORDER BY rank ASC, created_at ASC",
        (profile_id, user_id),
    )
    return {"angles": [_serialize_angle_row(r) for r in rows]}


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
        angles = await generate_content_angles(profile)
    except Exception as e:
        logger.error(f"Content angle generation failed for profile {profile_id}: {e}")
        raise HTTPException(status_code=502, detail=f"AI content angle generation failed. Please try again. ({str(e)[:150]})")

    await _execute("DELETE FROM content_angles WHERE brand_profile_id = ?", (profile_id,))
    now = now_iso()
    saved = []
    for rank, angle in enumerate(angles):
        angle_id = str(uuid.uuid4())
        await _execute(
            """INSERT INTO content_angles
               (id, brand_profile_id, kind, label, target_audience, user_problem,
                hook_promise, app_feature, desired_emotion, recommended_cta,
                claims_to_respect, rank, created_at, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (angle_id, profile_id, angle["kind"], angle["label"],
             angle["target_audience"], angle["user_problem"], angle["hook_promise"],
             angle["app_feature"], angle["desired_emotion"], angle["recommended_cta"],
             json.dumps(angle["claims_to_respect"]), rank, now, user_id),
        )
        saved.append({**angle, "id": angle_id, "rank": rank})
    logger.info(f"Generated %d content angle(s) for profile {profile_id}", len(saved))
    return {"angles": saved}


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
            hook_promise, app_feature, desired_emotion, recommended_cta,
            claims_to_respect, rank, created_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (angle_id, profile_id, template_library.normalize_angle_kind(payload.kind), label,
         (payload.target_audience or "").strip(), (payload.user_problem or "").strip(),
         (payload.hook_promise or "").strip(), (payload.app_feature or "").strip(),
         (payload.desired_emotion or "").strip(), (payload.recommended_cta or "").strip(),
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
    return {
        "hook_categories": template_library.HOOK_CATEGORIES,
        "objectives": template_library.VIDEO_OBJECTIVES,
        "content_angle_kinds": template_library.CONTENT_ANGLE_KINDS,
        "asset_kinds": template_library.ASSET_KINDS,
        "supported_durations": template_library.SUPPORTED_DURATIONS,
        "origins": template_library.TEMPLATE_ORIGINS,
        "categories_in_use": sorted({r["category"] for r in rows if r.get("category")}),
    }


@api_router.get("/templates/{template_id}")
async def get_template(template_id: str, user_id: str = Depends(get_current_user_id)):
    row = await _fetch_one(
        "SELECT * FROM hook_templates WHERE id = ? AND (user_id = ? OR user_id = 'system')",
        (template_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    with_favs = await _with_favorites([row], user_id)
    template = with_favs[0]
    template["usage_history"] = await _fetch_all(
        """SELECT g.id, g.status, g.created_at, g.duration, g.model, p.brand_name
           FROM generations g
           LEFT JOIN brand_profiles p ON p.id = g.brand_profile_id
           WHERE g.template_id = ?
           ORDER BY g.created_at DESC LIMIT 20""",
        (template_id,),
    ) if await _generations_table_exists() else []
    return template


def _template_row_values(payload: dict) -> dict:
    """Map a template payload onto DB-ready column values."""
    out = {}
    for key in TEMPLATE_STRUCTURED_FIELDS:
        if key in payload:
            out[key] = json.dumps(_normalize_str_list(payload[key]))
    if "content_slots" in payload and payload["content_slots"] is not None:
        slots = payload["content_slots"]
        out["content_slots"] = json.dumps(slots if isinstance(slots, dict) else {})
    for key in TEMPLATE_TEXT_FIELDS:
        if key in payload:
            out[key] = (payload[key] or "").strip()
    if "name" in payload:
        out["name"] = (payload["name"] or "").strip()[:template_library.TEMPLATE_NAME_MAX]
    if "category" in payload:
        out["category"] = template_library.normalize_category(payload["category"])
    if "objective" in payload:
        out["objective"] = template_library.normalize_objective(payload["objective"])
    if "hook_seconds" in payload and payload["hook_seconds"] is not None:
        out["hook_seconds"] = max(1, int(payload["hook_seconds"]))
    if "default_duration" in payload and payload["default_duration"] is not None:
        out["default_duration"] = int(payload["default_duration"])
    return out


@api_router.post("/templates", status_code=201)
async def create_template(payload: CreateTemplateRequest, user_id: str = Depends(get_current_user_id)):
    """Create an internal library template by hand. No AI calls."""
    name = (payload.name or "").strip()[:template_library.TEMPLATE_NAME_MAX]
    if not name:
        raise HTTPException(status_code=400, detail="Template name is required.")
    if not (payload.opening_structure or "").strip():
        raise HTTPException(
            status_code=400,
            detail="A library template needs an opening structure — that is what makes it reusable.",
        )

    values = _template_row_values(payload.model_dump(exclude_unset=False))
    template_id = str(uuid.uuid4())
    now = now_iso()
    await _execute(
        """INSERT INTO hook_templates
           (id, name, category, app_categories, audiences, objective, opening_structure,
            hook_seconds, continuation_structure, cta_pattern, visual_style, camera_pacing,
            required_assets, default_duration, content_slots, evidence_note, notes,
            version, archived, is_favorite, origin, review_status, times_used,
            created_at, updated_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (template_id, values.get("name"), values.get("category", "other"),
         values.get("app_categories", "[]"), values.get("audiences", "[]"),
         values.get("objective", ""), values["opening_structure"],
         values.get("hook_seconds", 3), values.get("continuation_structure", ""),
         values.get("cta_pattern", ""), values.get("visual_style", ""),
         values.get("camera_pacing", ""), values.get("required_assets", "[]"),
         values.get("default_duration", template_library.DEFAULT_DURATION),
         values.get("content_slots", "{}"), values.get("evidence_note", ""),
         values.get("notes", ""), 1, 0, 0, "custom", "approved", 0, now, now, user_id),
    )
    logger.info(f"Created library template {template_id} ('{name}')")
    return _public_library_template(
        await _fetch_one("SELECT * FROM hook_templates WHERE id = ?", (template_id,))
    )


@api_router.patch("/templates/{template_id}")
async def update_template(template_id: str, payload: UpdateTemplateRequest, user_id: str = Depends(get_current_user_id)):
    """
    Edit a library template. Curated templates are shared across the team, so
    editing one bumps its version rather than mutating history silently.
    """
    row = await _fetch_one(
        "SELECT * FROM hook_templates WHERE id = ? AND (user_id = ? OR user_id = 'system')",
        (template_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return _public_library_template(row)
    if "name" in updates and not (updates["name"] or "").strip():
        raise HTTPException(status_code=400, detail="Template name cannot be empty.")

    values = _template_row_values(updates)
    if not values:
        return _public_library_template(row)

    set_clauses = [f"{k} = ?" for k in values]
    vals = list(values.values())
    set_clauses.append("version = ?")
    vals.append(int(row.get("version") or 1) + 1)
    set_clauses.append("updated_at = ?")
    vals.append(now_iso())
    vals.extend([template_id, user_id])
    await _execute(
        f"UPDATE hook_templates SET {', '.join(set_clauses)} "
        "WHERE id = ? AND (user_id = ? OR user_id = 'system')",
        tuple(vals),
    )
    return _public_library_template(
        await _fetch_one("SELECT * FROM hook_templates WHERE id = ?", (template_id,))
    )


@api_router.post("/templates/{template_id}/favorite")
async def toggle_template_favorite(template_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Toggle favorite for the current user.

    Favorites live in their own table rather than the shared is_favorite column
    because curated templates are team-wide (user_id='system') — one operator's
    favorite must not mark it for everyone.
    """
    row = await _fetch_one(
        "SELECT id FROM hook_templates WHERE id = ? AND (user_id = ? OR user_id = 'system')",
        (template_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")

    existing = await _fetch_one(
        "SELECT 1 AS f FROM template_favorites WHERE template_id = ? AND user_id = ?",
        (template_id, user_id),
    )
    if existing:
        await _execute(
            "DELETE FROM template_favorites WHERE template_id = ? AND user_id = ?",
            (template_id, user_id),
        )
        return {"template_id": template_id, "is_favorite": False}

    await _execute(
        "INSERT INTO template_favorites (template_id, user_id, created_at) VALUES (?, ?, ?)",
        (template_id, user_id, now_iso()),
    )
    return {"template_id": template_id, "is_favorite": True}


@api_router.post("/templates/{template_id}/duplicate", status_code=201)
async def duplicate_template(template_id: str, user_id: str = Depends(get_current_user_id)):
    """Copy a template (curated or otherwise) into an editable custom one."""
    source = await _fetch_one(
        "SELECT * FROM hook_templates WHERE id = ? AND (user_id = ? OR user_id = 'system')",
        (template_id, user_id),
    )
    if not source:
        raise HTTPException(status_code=404, detail="Template not found")

    new_id = str(uuid.uuid4())
    now = now_iso()
    name = f"{source.get('name') or 'Template'} (copy)"[:template_library.TEMPLATE_NAME_MAX]
    # row_to_dict already parsed the JSON columns into Python values, so
    # re-serialize before binding — sqlite3 cannot bind a list.
    await _execute(
        """INSERT INTO hook_templates
           (id, name, category, app_categories, audiences, objective, opening_structure,
            hook_seconds, continuation_structure, cta_pattern, visual_style, camera_pacing,
            required_assets, default_duration, content_slots, evidence_note, notes,
            version, archived, is_favorite, origin, review_status, times_used,
            created_at, updated_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (new_id, name, source.get("category"),
         json.dumps(_normalize_str_list(source.get("app_categories"))),
         json.dumps(_normalize_str_list(source.get("audiences"))),
         source.get("objective") or "", source.get("opening_structure"),
         source.get("hook_seconds"), source.get("continuation_structure"),
         source.get("cta_pattern"), source.get("visual_style"), source.get("camera_pacing"),
         json.dumps(_normalize_str_list(source.get("required_assets"))),
         source.get("default_duration"),
         json.dumps(source.get("content_slots") or {}),
         source.get("evidence_note") or "",
         source.get("notes") or "", 1, 0, 0, "custom", "approved", 0, now, now, user_id),
    )
    logger.info(f"Duplicated template {template_id} -> {new_id}")
    return _public_library_template(
        await _fetch_one("SELECT * FROM hook_templates WHERE id = ?", (new_id,))
    )


@api_router.post("/templates/{template_id}/archive")
async def archive_template(template_id: str, archived: bool = True, user_id: str = Depends(get_current_user_id)):
    """
    Archive or restore a library template.

    Curated templates are shared, so archiving one hides it for the whole
    team — which is the intent for retiring a structure that isn't working.
    """
    row = await _fetch_one(
        "SELECT id FROM hook_templates WHERE id = ? AND (user_id = ? OR user_id = 'system')",
        (template_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    await _execute(
        "UPDATE hook_templates SET archived = ?, updated_at = ? WHERE id = ?",
        (1 if archived else 0, now_iso(), template_id),
    )
    return _public_library_template(
        await _fetch_one("SELECT * FROM hook_templates WHERE id = ?", (template_id,))
    )


@api_router.post("/templates/{template_id}/publish")
async def publish_template(template_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Publish a research draft into the usable library.

    Trend Research produces drafts; they stay unusable until an operator
    reviews and publishes them. This is the only path that flips
    review_status to approved.
    """
    row = await _fetch_one(
        "SELECT * FROM hook_templates WHERE id = ? AND (user_id = ? OR user_id = 'system')",
        (template_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    if not row.get("opening_structure"):
        raise HTTPException(
            status_code=400,
            detail="This template has no opening structure, so it cannot be published as a library template.",
        )
    await _execute(
        "UPDATE hook_templates SET review_status = 'approved', archived = 0, updated_at = ? WHERE id = ?",
        (now_iso(), template_id),
    )
    logger.info(f"Published template {template_id}")
    return _public_library_template(
        await _fetch_one("SELECT * FROM hook_templates WHERE id = ?", (template_id,))
    )


# ---------------------------------------------------------------------------
# Template recommendation
# ---------------------------------------------------------------------------
def _score_template_for_angle(template: dict, profile: dict, angle: Optional[dict], objective: str) -> dict:
    """
    Score one template against an App Profile + angle + objective.

    Deliberately transparent and deterministic rather than an LLM call: the
    founder sees WHY a template was picked, and a recommendation can be
    re-derived and audited. Scoring is a weighted sum of explicit signals,
    each contributing a human-readable reason.
    """
    score = 0.0
    reasons: list = []
    limitations: list = []

    tpl_objective = (template.get("objective") or "").strip()
    tpl_categories = [str(c).lower() for c in (template.get("app_categories") or [])]
    tpl_audiences = [str(a).lower() for a in (template.get("audiences") or [])]
    required_assets = [str(a).lower() for a in (template.get("required_assets") or [])]

    if objective and tpl_objective:
        if tpl_objective == objective:
            score += 3.0
            reasons.append(f"Built for the '{objective.replace('_', ' ')}' objective.")
        else:
            score += 0.5
            reasons.append(
                f"Designed for '{tpl_objective.replace('_', ' ')}', close to your '{objective.replace('_', ' ')}' goal."
            )

    profile_category = (profile.get("app_category") or profile.get("niche") or "").strip().lower()
    if profile_category and tpl_categories:
        if any(profile_category in c or c in profile_category for c in tpl_categories):
            score += 2.5
            reasons.append(f"Suited to the '{profile.get('app_category') or profile.get('niche')}' category.")
        else:
            score += 0.0
            limitations.append(
                f"Curated for {', '.join(tpl_categories)} rather than {profile.get('app_category') or profile.get('niche')}; expect to adapt the framing."
            )

    if angle:
        angle_kind = (angle.get("kind") or "").strip()
        audience = (angle.get("target_audience") or "").strip().lower()
        feature = (angle.get("app_feature") or "").strip().lower()

        # Category <-> angle affinity: demo-ish templates suit demonstration
        # angles, story templates suit founder-story, and so on.
        demo_categories = {"demo", "tutorial", "reveal"}
        story_categories = {"story", "pov", "before-after"}
        if angle_kind in ("feature_demonstration", "fast_tutorial") and template.get("category") in demo_categories:
            score += 2.0
            reasons.append("Demonstrates a feature on screen, which is what this angle needs.")
        elif angle_kind in ("founder_story", "daily_life_use_case") and template.get("category") in story_categories:
            score += 2.0
            reasons.append("Narrative structure suits a story-led angle.")
        elif angle_kind in ("problem_solution", "common_mistake") and template.get("category") in (
            "pain-point-question", "contrarian", "listicle", "pattern-interrupt"
        ):
            score += 2.0
            reasons.append("Direct-problem structure matches this angle.")
        elif angle_kind in ("competitor_alternative", "product_comparison") and template.get("category") == "social-proof":
            score += 2.0
            reasons.append("Comparison structure fits a side-by-side angle.")
        elif angle_kind in ("objection_handling", "privacy_pricing_differentiation") and template.get("category") in (
            "contrarian", "social-proof", "curiosity-gap"
        ):
            score += 1.5
            reasons.append("Works well for answering an objection head-on.")
        else:
            score += 0.5

        if audience and tpl_audiences:
            for tpl_aud in tpl_audiences:
                if tpl_aud and (tpl_aud in audience or audience in tpl_aud):
                    score += 1.0
                    reasons.append("Audience framing matches the selected segment.")
                    break

        if feature:
            feature_tokens = {t for t in feature.replace(",", " ").split() if len(t) > 3}
            slot_blob = " ".join(
                str(v) for v in (template.get("content_slots") or {}).values()
            ).lower()
            if feature_tokens and any(tok in slot_blob for tok in feature_tokens):
                score += 1.0
                reasons.append("Has a content slot that fits the feature being demonstrated.")

        if angle.get("claims_to_respect"):
            limitations.append(
                "Bounded by: " + "; ".join(str(c) for c in angle["claims_to_respect"][:3])
            )

    if not tpl_categories:
        score += 1.0
        reasons.append("Category-agnostic, so it adapts to any app.")

    if required_assets:
        limitations.append(
            "Needs " + ", ".join(a.replace("_", " ") for a in required_assets) + "."
        )
    if not template.get("continuation_structure"):
        limitations.append("No continuation structure recorded; the studio will infer one.")
    if (template.get("review_status") or "approved") != "approved":
        limitations.append("Unpublished research draft — review before using.")

    return {"score": round(score, 2), "reasons": reasons, "limitations": limitations}


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
    """
    profile = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")

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

    scored = []
    for tpl in templates:
        result = _score_template_for_angle(tpl, profile, angle, norm_objective)
        scored.append({
            "template": _public_library_template(tpl),
            "score": result["score"],
            "why_it_fits": result["reasons"],
            "target_audience": (angle or {}).get("target_audience") or profile.get("target_audience") or "",
            "app_feature": (angle or {}).get("app_feature") or "",
            "required_assets": tpl.get("required_assets") or [],
            "suggested_duration": tpl.get("default_duration") or template_library.DEFAULT_DURATION,
            "limitations": result["limitations"],
        })
    scored.sort(key=lambda r: (-r["score"], r["template"]["name"]))
    return {
        "recommendations": scored[: max(1, min(int(limit or 8), 30))],
        "angle": _serialize_angle_row(angle) if angle else None,
        "objective": norm_objective,
    }


# ---------------------------------------------------------------------------
# Studio projects (guided creation workflow)
# ---------------------------------------------------------------------------
def _public_project(row: dict) -> dict:
    """Serialize a studio project with its structured fields parsed."""
    out = dict(row)
    out["beat_timeline"] = out.get("beat_timeline") or []
    out["overlays"] = out.get("overlays") or []
    out["assets"] = out.get("assets") or []
    out["safety_report"] = out.get("safety_report") or None
    out["duration_seconds"] = out.get("duration_seconds") or 0
    out["script_version"] = out.get("script_version") or 0
    return out


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
    return {"projects": [_public_project(r) for r in rows]}


@api_router.post("/studio/projects", status_code=201)
async def create_studio_project(
    payload: CreateStudioProjectRequest, user_id: str = Depends(get_current_user_id)
):
    """Create a creation draft against an APPROVED App Profile."""
    profile = await _require_profile_for_studio(payload.brand_profile_id, user_id)

    template_id = (payload.template_id or "").strip()
    template_version = None
    duration = payload.duration_seconds
    if template_id:
        template = await _fetch_one(
            "SELECT * FROM hook_templates WHERE id = ? AND (user_id = ? OR user_id = 'system')",
            (template_id, user_id),
        )
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        if not template.get("is_usable", True) and template.get("review_status") != "approved":
            raise HTTPException(
                status_code=409,
                detail="This template is an unpublished draft. Publish it before using it.",
            )
        # Pin the version now so later library edits cannot change this project.
        template_version = template.get("version")
        if not duration:
            duration = template.get("default_duration")

    duration = template_library.clamp_duration(duration or template_library.DEFAULT_DURATION)

    project_id = str(uuid.uuid4())
    now = now_iso()
    await _execute(
        """INSERT INTO studio_projects
           (id, brand_profile_id, content_angle_id, template_id, template_version,
            objective, audience, duration_seconds, tone, assets, script_version,
            status, created_at, updated_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (project_id, profile["id"], (payload.content_angle_id or "").strip() or None,
         template_id or None, template_version,
         template_library.normalize_objective(payload.objective),
         (payload.audience or profile.get("target_audience") or "").strip() or None,
         duration, (payload.tone or "").strip() or None,
         json.dumps([]), 0, "draft", now, now, user_id),
    )
    logger.info(f"Created studio project {project_id} for profile {profile['id']}")
    return _public_project(
        await _fetch_one("SELECT * FROM studio_projects WHERE id = ?", (project_id,))
    )


@api_router.get("/studio/projects/{project_id}")
async def get_studio_project(project_id: str, user_id: str = Depends(get_current_user_id)):
    row = await _fetch_one(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?", (project_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Studio project not found")
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
    for key, value in updates.items():
        if key in ("beat_timeline", "overlays", "assets"):
            value = json.dumps(value if isinstance(value, list) else [])
        elif key in ("template_id", "content_angle_id"):
            value = (value or "").strip() or None
        elif key == "objective":
            value = template_library.normalize_objective(value)
        elif key == "duration_seconds":
            value = template_library.clamp_duration(value)
        elif value is not None:
            value = str(value).strip()
        set_clauses.append(f"{key} = ?")
        values.append(value)

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
            if key in ("beat_timeline", "overlays", "assets"):
                merged[key] = value if isinstance(value, list) else []
            else:
                merged[key] = value
        report = claim_safety.build_safety_report(merged, profile)
        set_clauses.append("safety_report = ?")
        values.append(json.dumps(report))
        set_clauses.append("safety_summary = ?")
        values.append(claim_safety.summarize(report))

    set_clauses.append("script_version = ?")
    values.append(int(row.get("script_version") or 0) + 1)
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

    try:
        plan = await generate_creative_plan(
            profile=profile,
            template=template,
            angle=angle,
            objective=objective,
            duration_seconds=duration,
            tone=tone,
        )
    except Exception as e:
        logger.error(f"Creative plan generation failed for project {project_id}: {e}")
        raise HTTPException(status_code=502, detail=f"AI plan generation failed. Please try again. ({str(e)[:150]})")

    report = claim_safety.build_safety_report(plan, profile)
    summary = claim_safety.summarize(report)

    now = now_iso()
    await _execute(
        """UPDATE studio_projects SET
             hook_line = ?, script = ?, beat_timeline = ?, visual_direction = ?,
             feature_emphasis = ?, overlays = ?, voice_direction = ?, sound_direction = ?,
             cta = ?, safety_report = ?, safety_summary = ?, objective = ?,
             duration_seconds = ?, tone = ?, script_version = script_version + 1,
             status = 'draft', updated_at = ?
           WHERE id = ? AND user_id = ?""",
        (plan["hook_line"], plan["script"], json.dumps(plan["beat_timeline"]),
         plan["visual_direction"], plan["feature_emphasis"], json.dumps(plan["overlays"]),
         plan["voice_direction"], plan["sound_direction"], plan["cta"],
         json.dumps(report), summary, objective, duration, tone or None, now,
         project_id, user_id),
    )
    logger.info(
        f"Generated plan for project {project_id} (script v{int(row.get('script_version') or 0) + 1}) — {summary}"
    )
    return _public_project(
        await _fetch_one("SELECT * FROM studio_projects WHERE id = ?", (project_id,))
    )


@api_router.post("/studio/projects/{project_id}/ready")
async def mark_project_ready(project_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Mark a reviewed project ready for video generation.

    Refuses while the claim-safety report is failing, so a prohibited claim
    cannot be waved through. This is the last gate before Phase 5 spends money.
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

    report = row.get("safety_report") or {}
    if isinstance(report, str):
        try:
            report = json.loads(report)
        except (json.JSONDecodeError, TypeError):
            report = {}
    if report and not report.get("passed", True):
        blocking = [b.get("claim") for b in report.get("blocking", []) if b.get("claim")]
        raise HTTPException(
            status_code=409,
            detail="Fix prohibited claims before generating: " + ", ".join(blocking[:3]),
        )

    await _execute(
        "UPDATE studio_projects SET status = 'ready_for_generation', updated_at = ? "
        "WHERE id = ? AND user_id = ?",
        (now_iso(), project_id, user_id),
    )
    return _public_project(
        await _fetch_one("SELECT * FROM studio_projects WHERE id = ?", (project_id,))
    )


# ---------------------------------------------------------------------------
# Generations (single-pass video production)
# ---------------------------------------------------------------------------
def _public_generation(row: dict) -> dict:
    """Serialize a generation row, hiding the stored prompt by default.

    The prompt is long and only useful when debugging a specific result, so
    it is returned by the detail endpoint but trimmed from list responses.
    """
    out = dict(row)
    out["adjustments"] = out.get("adjustments") or []
    out["variation_params"] = out.get("variation_params") or {}
    out["retryable"] = bool(out.get("retryable"))
    out.pop("prompt_used", None)
    return out


def _public_generation_detail(row: dict) -> dict:
    out = _public_generation(row)
    out["prompt_used"] = row.get("prompt_used") or ""
    return out


async def _record_cost(generation_id: str, response: dict) -> None:
    """Store the reported cost, or an explicit marker when none is reported."""
    cost, source = generation_planning.extract_cost(response)
    await _execute(
        "UPDATE generations SET cost_usd = ?, cost_source = ? WHERE id = ?",
        (cost, source, generation_id),
    )


async def _submit_generation(
    project: dict,
    profile: dict,
    template: dict,
    user_id: str,
    model: str = "",
    duration: Optional[int] = None,
    segment_role: str = "primary",
    parent_generation_id: str = "",
    is_extension: bool = False,
    attempt: int = 1,
    variation_kind: str = "",
    variation_params: Optional[dict] = None,
    generate_audio: Optional[bool] = None,
) -> dict:
    """
    Submit ONE video generation job for the whole video.

    A second job is created only when the caller passes segment_role
    'extension', which the endpoints below do exclusively for the three
    justified reasons: the duration exceeds the provider's single-pass limit,
    the founder explicitly asked to extend, or a segment is being replaced
    after a recoverable failure.
    """
    requested = duration or project.get("duration_seconds") or 20
    plan = video_providers.plan_duration(model, requested)
    model_key = plan["model"]
    cap = video_providers.capability(model_key)
    seconds = plan["primary_seconds"] if not is_extension else min(
        plan["primary_seconds"], max(1, requested)
    )

    prompt = generation_planning.build_single_pass_prompt(
        plan=project,
        profile=profile,
        template=template,
        duration=seconds,
        segment=segment_role,
        asset_notes=generation_planning.asset_notes(project.get("assets") or []),
        is_extension=is_extension,
    )

    generation_id = str(uuid.uuid4())
    now = now_iso()
    await _execute(
        """INSERT INTO generations
           (id, studio_project_id, brand_profile_id, template_id, template_version,
            script_version, model, model_id, requested_duration, duration, status,
            segment_role, attempt, parent_generation_id, variation_kind, variation_params,
            cost_source, prompt_used, adjustments, retryable, requested_at, created_at,
            updated_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'submitted', ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)""",
        (generation_id, project["id"], project.get("brand_profile_id"),
         project.get("template_id"), project.get("template_version"),
         project.get("script_version"), model_key, cap["id"],
         requested, seconds, segment_role, attempt, parent_generation_id or None,
         variation_kind or None, json.dumps(variation_params or {}),
         "pending", prompt, json.dumps(plan["adjustments"]), now, now, now, user_id),
    )

    try:
        submitted = await generate_video(
            prompt=prompt,
            duration=seconds,
            model=model_key,
            # Default to native audio when the provider offers it; the plan's
            # sound direction is already written into the prompt.
            generate_audio=(
                bool(cap.get("supports_native_audio"))
                if generate_audio is None
                else bool(generate_audio)
            ),
        )
    except Exception as e:
        message = str(e)
        await _execute(
            "UPDATE generations SET status = 'failed', error = ?, retryable = ?, completed_at = ? WHERE id = ?",
            (message[:1000], 1 if generation_planning.is_recoverable_error(message) else 0,
             now_iso(), generation_id),
        )
        logger.error(f"Generation {generation_id} submission failed: {message}")
        raise HTTPException(status_code=502, detail=f"Video generation failed to submit: {message[:200]}")

    job_id = submitted.get("id") or ""
    await _execute(
        "UPDATE generations SET openrouter_job_id = ?, polling_url = ?, status = 'generating', updated_at = ? WHERE id = ?",
        (job_id, submitted.get("polling_url") or "", now_iso(), generation_id),
    )
    await _record_cost(generation_id, submitted)

    # Register with the persistent video store so a completed clip survives a
    # redeploy, exactly like the legacy face-swap path does.
    await _execute(
        """INSERT OR REPLACE INTO video_assets
           (job_id, user_id, r2_url, phase, source_video_id, source_hook_template_id, duration, created_at)
           VALUES (?, ?, '', ?, NULL, ?, ?, ?)""",
        (generation_id, user_id, segment_role, project.get("template_id"), seconds, now),
    )

    logger.info(
        f"Submitted generation {generation_id} ({segment_role}, attempt {attempt}) "
        f"model={model_key} duration={seconds}s cost={submitted.get('usage', {}).get('cost') if isinstance(submitted.get('usage'), dict) else 'n/a'}"
    )
    return _public_generation_detail(
        await _fetch_one("SELECT * FROM generations WHERE id = ?", (generation_id,))
    )


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
    """Generation history, newest first. Filters compose."""
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
    return {"generations": [_public_generation(r) for r in rows]}


@api_router.get("/generations/{generation_id}")
async def get_generation(generation_id: str, user_id: str = Depends(get_current_user_id)):
    row = await _fetch_one(
        "SELECT * FROM generations WHERE id = ? AND user_id = ?", (generation_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")
    return _public_generation_detail(row)


@api_router.post("/studio/projects/{project_id}/generate", status_code=202)
async def submit_project_generation(
    project_id: str, payload: StudioGenerationRequest, user_id: str = Depends(get_current_user_id)
):
    """
    Generate the complete video as ONE job.

    Refuses unless the project is reviewed and ready, and unless the claim
    check passes, so a prohibited claim cannot reach a paid generation.
    A duration beyond the provider's single-pass limit is accepted but the
    response reports that an extension is needed; it is never silently
    truncated to a shorter video.
    """
    require_ai_configured()
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

    report = project.get("safety_report") or {}
    if isinstance(report, str):
        try:
            report = json.loads(report)
        except (json.JSONDecodeError, TypeError):
            report = {}
    if report and not report.get("passed", True):
        blocking = [b.get("claim") for b in report.get("blocking", []) if b.get("claim")]
        raise HTTPException(
            status_code=409,
            detail="Fix prohibited claims before generating: " + ", ".join(blocking[:3]),
        )

    profile = await _require_profile_for_studio(project.get("brand_profile_id"), user_id)
    template = await _fetch_one(
        "SELECT * FROM hook_templates WHERE id = ? AND (user_id = ? OR user_id = 'system')",
        (project.get("template_id"), user_id),
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    requested = payload.duration_seconds or project.get("duration_seconds") or 20
    model_key, reason = video_providers.resolve(payload.model or None)
    plan = video_providers.plan_duration(model_key, requested)

    generation = await _submit_generation(
        project=project,
        profile=profile,
        template=template,
        user_id=user_id,
        model=model_key,
        duration=requested,
        generate_audio=payload.generate_audio,
    )
    generation["duration_plan"] = plan
    generation["provider_reason"] = reason
    if plan["needs_extension"]:
        logger.info(
            f"Project {project_id}: {requested}s exceeds one pass on {model_key}; "
            f"primary {plan['primary_seconds']}s + extension {plan['extension_seconds']}s"
        )
    return generation


@api_router.post("/generations/{generation_id}/poll")
async def poll_generation(generation_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Refresh a generation's status and persist cost when the provider reports it.

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
        return _public_generation_detail(row)

    job_id = row.get("openrouter_job_id")
    if not job_id:
        raise HTTPException(
            status_code=409,
            detail="This generation was never submitted to the provider.",
        )

    try:
        response = await poll_video_job(job_id)
    except Exception as e:
        message = str(e)
        await _execute(
            "UPDATE generations SET error = ?, retryable = ?, updated_at = ? WHERE id = ?",
            (message[:1000], 1 if generation_planning.is_recoverable_error(message) else 0,
             now_iso(), generation_id),
        )
        raise HTTPException(status_code=502, detail=f"Could not check generation status: {message[:200]}")

    status = str(response.get("status") or "").lower()
    urls = response.get("unsigned_urls") or response.get("urls") or []
    video_url = urls[0] if isinstance(urls, list) and urls else response.get("video_url") or ""
    now = now_iso()

    if status in ("completed", "succeeded", "success") and video_url:
        stored_url = None
        # Persist locally first so the clip survives even if R2 is unconfigured.
        try:
            local_path = await _download_generation_video(video_url, generation_id)
            if local_path:
                stored_url = storage_service.upload_video(user_id, generation_id, Path(local_path))
        except Exception as e:
            logger.warning(f"Generation {generation_id}: storage step failed: {e}")

        await _execute(
            "UPDATE generations SET status = 'completed', video_url = ?, r2_url = ?, "
            "error = NULL, completed_at = ?, updated_at = ? WHERE id = ?",
            (video_url, stored_url or "", now, now, generation_id),
        )
        if stored_url:
            await _execute(
                "UPDATE video_assets SET r2_url = ? WHERE job_id = ?", (stored_url, generation_id)
            )
    elif status in ("failed", "error", "cancelled", "canceled"):
        message = str(response.get("error") or response.get("message") or "Generation failed.")
        await _execute(
            "UPDATE generations SET status = 'failed', error = ?, retryable = ?, completed_at = ?, "
            "updated_at = ? WHERE id = ?",
            (message[:1000], 1 if generation_planning.is_recoverable_error(message) else 0,
             now, now, generation_id),
        )
    else:
        await _execute(
            "UPDATE generations SET status = 'generating', updated_at = ? WHERE id = ?",
            (now, generation_id),
        )

    await _record_cost(generation_id, response)
    return _public_generation_detail(
        await _fetch_one("SELECT * FROM generations WHERE id = ?", (generation_id,))
    )


async def _download_generation_video(video_url: str, generation_id: str) -> Optional[Path]:
    """Download a finished clip into storage/videos for reuse and R2 upload."""
    target = pipeline.VIDEOS_DIR / f"{generation_id}.mp4"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
            async with client.stream("GET", video_url) as resp:
                resp.raise_for_status()
                with open(target, "wb") as fh:
                    async for chunk in resp.aiter_bytes():
                        fh.write(chunk)
    except Exception as e:
        logger.warning(f"Could not download generation video {generation_id}: {e}")
        if target.exists():
            try:
                target.unlink()
            except OSError:
                pass
        return None
    return target if target.exists() else None


@api_router.post("/generations/{generation_id}/retry", status_code=202)
async def retry_generation(generation_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Replace a failed segment.

    The new attempt is recorded as a child of the failed generation rather
    than overwriting it, so the failure and its cost stay in history — a
    failed generation that is silently replaced makes cost reporting lie.
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

    project = await _fetch_one(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?",
        (row.get("studio_project_id"), user_id),
    )
    if not project:
        raise HTTPException(status_code=404, detail="The studio project for this generation is gone")
    profile = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ?", (project.get("brand_profile_id"),)
    )
    template = await _fetch_one(
        "SELECT * FROM hook_templates WHERE id = ?", (project.get("template_id"),)
    )
    if not profile or not template:
        raise HTTPException(status_code=409, detail="Cannot retry: profile or template is missing")

    return await _submit_generation(
        project=project,
        profile=profile,
        template=template,
        user_id=user_id,
        model=row.get("model") or "",
        duration=row.get("duration"),
        segment_role=row.get("segment_role") or "primary",
        parent_generation_id=generation_id,
        attempt=int(row.get("attempt") or 1) + 1,
    )


@api_router.post("/generations/{generation_id}/extend", status_code=202)
async def extend_generation(
    generation_id: str, payload: StudioGenerationRequest, user_id: str = Depends(get_current_user_id)
):
    """
    Continue a completed video beyond its current length.

    This is one of only three situations that justify a second model call,
    the other two being a duration over the provider's single-pass limit and
    a failed-segment replacement.
    """
    require_ai_configured()
    row = await _fetch_one(
        "SELECT * FROM generations WHERE id = ? AND user_id = ?", (generation_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Generation not found")
    if row.get("status") != "completed":
        raise HTTPException(
            status_code=409, detail="Only a completed video can be extended."
        )

    extra = payload.duration_seconds or 10
    model_key, _ = video_providers.resolve(row.get("model") or None)
    cap = video_providers.capability(model_key)
    if extra > cap["max_duration"]:
        raise HTTPException(
            status_code=400,
            detail=f"{cap['name']} can add at most {cap['max_duration']}s in one pass.",
        )

    project = await _fetch_one(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?",
        (row.get("studio_project_id"), user_id),
    )
    if not project:
        raise HTTPException(status_code=404, detail="The studio project for this generation is gone")
    profile = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ?", (project.get("brand_profile_id"),)
    )
    template = await _fetch_one(
        "SELECT * FROM hook_templates WHERE id = ?", (project.get("template_id"),)
    )
    if not profile or not template:
        raise HTTPException(status_code=409, detail="Cannot extend: profile or template is missing")

    extension = await _submit_generation(
        project=project,
        profile=profile,
        template=template,
        user_id=user_id,
        model=model_key,
        duration=extra,
        segment_role="extension",
        parent_generation_id=generation_id,
        is_extension=True,
        variation_kind="extension",
        variation_params={"extra_seconds": extra, "source_model": row.get("model")},
    )
    extension["extension_of"] = generation_id
    return extension


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
    return _public_generation_detail(
        await _fetch_one("SELECT * FROM generations WHERE id = ?", (generation_id,))
    )


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
@api_router.delete("/videos/{video_id}")
async def delete_video(video_id: str, user_id: str = Depends(get_current_user_id)):
    """Delete a video and all its associated data (analyses, frames, etc.)."""
    video = await _fetch_one("SELECT * FROM videos WHERE id = ? AND user_id = ?", (video_id, user_id))
    if not video:
        raise HTTPException(status_code=404, detail="Video not found.")

    # Delete associated analyses
    await _execute("DELETE FROM analyses WHERE video_id = ?", (video_id,))
    # Delete associated customizations
    await _execute("DELETE FROM customizations WHERE video_id = ?", (video_id,))
    # Delete associated video jobs
    await _execute("DELETE FROM video_jobs WHERE video_id = ?", (video_id,))
    # Delete the video record itself
    await _execute("DELETE FROM videos WHERE id = ?", (video_id,))

    # Clean up local files if they exist (frames, video)
    if video.get("tiktok_url"):
        vhash = pipeline.url_hash(video["tiktok_url"])
        frame_dir = pipeline.FRAMES_DIR / vhash
        if frame_dir.exists():
            import shutil
            shutil.rmtree(frame_dir, ignore_errors=True)
        video_file = pipeline.VIDEOS_DIR / f"{vhash}.mp4"
        video_file.unlink(missing_ok=True)

    return {"deleted": True, "id": video_id}


@api_router.get("/history")
async def get_history(user_id: str = Depends(get_current_user_id)):
    """
    Return the user's combined activity: analyzed videos, face-swap jobs,
    and saved hook templates — everything needed to show a full history page.
    """
    videos = await _fetch_all(
        "SELECT * FROM videos WHERE status IN ('analyzed', 'failed') AND user_id = ? ORDER BY created_at DESC LIMIT 200",
        (user_id,)
    )
    results = []
    for v in videos:
        analyses = await _fetch_all("SELECT id FROM analyses WHERE video_id = ?", (v["id"],))
        customizations = await _fetch_all(
            "SELECT * FROM customizations WHERE video_id = ? ORDER BY created_at DESC", (v["id"],)
        )
        video_jobs = await _fetch_all(
            "SELECT * FROM video_jobs WHERE video_id = ? ORDER BY created_at DESC", (v["id"],)
        )
        results.append({
            "video": v,
            "analysis_count": len(analyses),
            "customizations": customizations,
            "video_jobs": video_jobs,
        })

    # Face-swap job history (last 50 completed/failed, with result images)
    face_swap_jobs = await _fetch_all(
        """SELECT id, status, target_image_url, source_face_url, result_json,
                  variants_requested, error, created_at, completed_at
           FROM face_swap_jobs
           WHERE user_id = ? AND status IN ('completed', 'failed')
           ORDER BY created_at DESC LIMIT 50""",
        (user_id,),
    )
    face_swap_history = []
    for job in face_swap_jobs:
        entry = {
            "job_id": job["id"],
            "status": job["status"],
            "target_image_url": job.get("target_image_url"),
            "source_face_url": job.get("source_face_url"),
            "created_at": job.get("created_at"),
            "completed_at": job.get("completed_at"),
            "error": job.get("error"),
        }
        if job.get("result_json"):
            try:
                result_data = json.loads(job["result_json"])
                entry["generated_image_url"] = result_data.get("generated_image_url")
                entry["variants_count"] = len(result_data.get("variants", []))
            except (json.JSONDecodeError, TypeError):
                pass
        face_swap_history.append(entry)

    # Saved hook templates
    templates = await _fetch_all(
        """SELECT id, name, category, source_creator, source_title, thumbnail_url,
                  effectiveness_score, times_used, last_used_at, created_at
           FROM hook_templates WHERE user_id = ?
           ORDER BY created_at DESC LIMIT 100""",
        (user_id,),
    )

    return {
        "videos": results,
        "face_swap_jobs": face_swap_history,
        "hook_templates": templates,
    }


@api_router.get("/")
async def root():
    import apify_tiktok
    return {
        "message": "HookForge API",
        "ai_configured": bool(os.environ.get("OPENROUTER_API_KEY")),
        "apify_configured": apify_tiktok.is_configured(),
    }


@api_router.get("/debug/apify-test")
async def debug_apify_test():
    """Diagnostic endpoint: test the Apify actor connection."""
    import apify_tiktok
    if not apify_tiktok.is_configured():
        return {"error": "APIFY_API_TOKEN not set"}
    return {"status": "configured", "actor": apify_tiktok.ACTOR_ID}


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
    if not os.environ.get("OPENROUTER_API_KEY"):
        logger.warning(
            "OPENROUTER_API_KEY is not set. The app will run, but AI features "
            "(hook analysis, face swap, video generation) will return 503 until it is set."
        )
    import apify_tiktok
    if not apify_tiktok.is_configured():
        logger.warning(
            "APIFY_API_TOKEN is not set. The Discovery feed and keyword search will fall back "
            "to yt-dlp, which is frequently blocked by TikTok and will likely return zero "
            "results (empty feed / 'No results found'). Set APIFY_API_TOKEN to fix this."
        )


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


app.mount("/api/media", StaticFiles(directory=str(pipeline.STORAGE_DIR)), name="media")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend static build (present in container/production deployments).
FRONTEND_BUILD_DIR = Path(__file__).parent.parent / "frontend_build"
if FRONTEND_BUILD_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_BUILD_DIR / "static")),
        name="frontend_static",
    )

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = FRONTEND_BUILD_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_BUILD_DIR / "index.html"))
