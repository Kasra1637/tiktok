import asyncio
import io
import json
import logging
import os
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
from ai_service import (
    analyze_hook, generate_customized_preview, generate_face_swap, generate_video_prompt,
    generate_video, poll_video_job, analyze_brand_from_text, generate_remix_script,
    strip_html_to_text, remix_chat_turn, empty_remix_brief, VIDEO_MODELS, DEFAULT_VIDEO_MODEL,
    analyze_image_for_hook,
)
from models import (
    IngestVideoRequest, BrandContextRequest, GenerateVideoRequest,
    AnalyzeBrandUrlRequest, BrandProfileCreateRequest, BrandProfileUpdateRequest,
    GenerateRemixScriptRequest, RemixChatMessageRequest,
    CreateHookTemplateRequest, UpdateHookTemplateRequest,
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

_ytdlp_semaphore = asyncio.Semaphore(3)


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
    if TURSO_DATABASE_URL:
        import libsql_experimental as libsql
        conn = libsql.connect(
            "hookforge.db",
            sync_url=TURSO_DATABASE_URL,
            auth_token=TURSO_AUTH_TOKEN,
        )
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield _LibsqlAsyncWrapper(conn)
        finally:
            conn.close()
    else:
        conn = await aiosqlite.connect(str(DB_PATH))
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
        finally:
            await conn.close()


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

    async def commit(self):
        self._conn.commit()
        # Sync local embedded replica to/from Turso cloud
        if hasattr(self._conn, "sync"):
            self._conn.sync()

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
                tiktok_url TEXT UNIQUE,
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
                updated_at TEXT
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

            -- Saved hook templates. Each row is a full snapshot of a proven
            -- hook: the AI analysis, the ready-to-submit video prompt, and a
            -- local copy of the source clip for V2V motion transfer. Reusing a
            -- template costs zero AI calls -- no re-analysis, no prompt
            -- regeneration, no re-download of the source video.
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
                updated_at TEXT
            );
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
                tiktok_url TEXT UNIQUE,
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


async def _recover_missing_frame(relative_path: str) -> bool:
    """
    Best-effort self-heal for a frame file that's missing on this machine
    (ephemeral storage after a redeploy, cache eviction, multi-instance
    deploys, etc.) even though the DB still has a valid analysis row
    referencing it.

    Frame media URLs look like "frames/<video_hash>/<filename>". Re-download
    the source video (a no-op if it's already on disk) and re-extract its
    hook frames — `pipeline.download_video` names the file deterministically
    from `url_hash(tiktok_url)`, and `pipeline.extract_hook_frames` reuses
    that same hash for the frame directory, so this reproduces the exact
    frame paths the original analysis stored, without needing a full
    re-analysis (no new AI call).

    Returns True if recovery succeeded (the file exists now), False otherwise.
    """
    parts = relative_path.split("/")
    if len(parts) != 3 or parts[0] != "frames":
        return False
    video_hash = parts[1]

    analysis = await _fetch_one(
        "SELECT * FROM analyses WHERE frames LIKE ? ORDER BY created_at DESC LIMIT 1",
        (f"%/frames/{video_hash}/%",),
    )
    if not analysis:
        return False

    video = await _fetch_one("SELECT * FROM videos WHERE id = ?", (analysis["video_id"],))
    if not video or not video.get("tiktok_url"):
        return False

    try:
        async with _ytdlp_semaphore:
            video_path = await pipeline.download_video(
                video["tiktok_url"], direct_video_url=video.get("direct_video_url", "")
            )
        await pipeline.extract_hook_frames(
            video_path, num_frames=FRAME_COUNT, duration=HOOK_DURATION_SECONDS
        )
    except Exception as e:
        logger.warning(f"Frame recovery failed for hash {video_hash}: {e}")
        return False

    return (pipeline.FRAMES_DIR / video_hash / parts[2]).is_file()


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


async def _fetch_active_brand() -> Optional[dict]:
    """
    The "active" brand profile: the most recently created *or edited* one.

    Single source of truth so every caller agrees on which profile is active.
    Previously the /brand/active endpoint ordered by created_at while the video
    flows ordered by updated_at, so editing an older profile made the Brand page
    and the generators disagree about which brand was in effect.
    """
    return await _fetch_one(
        "SELECT * FROM brand_profiles ORDER BY updated_at DESC, created_at DESC LIMIT 1"
    )


async def get_active_brand_or_404() -> dict:
    brand = await _fetch_active_brand()
    if not brand:
        raise HTTPException(
            status_code=404,
            detail="No brand profile yet. Analyze your website URL first.",
        )
    return brand


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

    existing = await _fetch_one("SELECT * FROM videos WHERE tiktok_url = ?", (tiktok_url,))
    if existing:
        return existing

    curated = await _fetch_one("SELECT * FROM curated_videos WHERE tiktok_url = ?", (tiktok_url,))
    if curated:
        meta = {k: curated.get(k) for k in [
            "video_platform_id", "creator", "creator_display", "title",
            "view_count", "like_count", "comment_count", "duration", "thumbnail_url",
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

    try:
        async with _ytdlp_semaphore:
            video_path = await pipeline.download_video(tiktok_url, direct_video_url=video.get("direct_video_url", ""))
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
        normalized.save(gen_path, format="PNG")

    return {
        "id": gen_id,
        "image_url": f"/api/media/generated/{gen_id}.png",
        "resolution": f"{width}x{height}",
        "variant_index": variant_index,
    }


async def _run_face_swap_job(
    job_id: str,
    target_path: Path,
    source_path: Path,
    target_image_url: str,
    source_face_url: str,
    variants: int,
    customization_prompt: str = "",
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
    target_image: UploadFile = File(None),
    source_face: UploadFile = File(...),
    target_frame_url: str = Form(""),
    variants: int = Form(1),
    customization_prompt: str = Form(""),
    user_id: str = Depends(get_current_user_id),
):
    """
    Validate and persist both inputs, then return an app job ID immediately.
    GPT-5.4 Image 2 runs after the response so browser and reverse-proxy request
    timeouts cannot discard a completed generation.
    """
    require_ai_configured()
    variants = max(1, min(variants, 4))

    if target_frame_url and target_frame_url.strip():
        url_path = target_frame_url.strip()
        if not url_path.startswith("/api/media/"):
            raise HTTPException(status_code=400, detail="Invalid target frame URL.")
        relative_path = url_path[len("/api/media/"):]
        storage_root = pipeline.STORAGE_DIR.resolve()
        target_path = (storage_root / relative_path).resolve()
        if storage_root not in target_path.parents:
            raise HTTPException(
                status_code=400,
                detail="Target frame not found on server. Please re-analyze the video.",
            )
        if not target_path.is_file():
            # The frame file may be missing on this machine even though the
            # analysis is still valid (ephemeral storage, redeploy, cache
            # eviction). Try to reproduce it deterministically before failing.
            recovered = await _recover_missing_frame(relative_path)
            if not recovered:
                raise HTTPException(
                    status_code=400,
                    detail="Target frame not found on server. Please re-analyze the video.",
                )
        target_image_url = url_path
    elif target_image:
        target_bytes = await target_image.read()
        if not target_bytes:
            raise HTTPException(status_code=400, detail="Target image is empty.")
        if len(target_bytes) > 12 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Target image is too large (max 12MB).")
        normalized_target = validate_and_normalize_photo(target_bytes)
        target_id = str(uuid.uuid4())
        target_path = pipeline.UPLOADS_DIR / f"{target_id}.png"
        target_path.write_bytes(normalized_target)
        target_image_url = f"/api/media/uploads/{target_id}.png"
    else:
        raise HTTPException(
            status_code=400,
            detail="Please provide either a target image upload or a target frame URL.",
        )

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
    "Create a 5-second vertical video (9:16) starting from this exact first frame. "
    "The character should perform a single attention-grabbing movement that creates "
    "curiosity: {motion_type}. "
    "Requirements: "
    "- Maintain perfect face consistency with the first frame throughout "
    "- Smooth, natural motion — no jerky or artificial movement "
    "- Camera holds steady or has a very subtle push-in for tension "
    "- The movement should feel like it's building up to something (creates anticipation) "
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

HOOK_MOTION_TYPES = [
    "a confident lean-in toward camera with a knowing expression, as if about to reveal a secret",
    "a slow dramatic turn from profile to face-on, making eye contact with the camera",
    "a quick attention-grabbing gesture (pointing, hand raise, or prop reveal) that implies 'watch this'",
    "a subtle head tilt and raised eyebrow with a half-smile, building intrigue",
    "a sudden stop-motion-style pose change that catches the eye, then holds",
]


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


def build_hook_prompt_from_analysis(analysis: dict, has_reference_video: bool = False) -> str:
    """
    Build the hook-video prompt from a viral video's hook analysis.

    Shared by the live analysis path and by hook-template creation, so a saved
    template stores exactly the prompt that a fresh analysis would have produced.
    With H3's V2V motion transfer the video reference carries timing and camera
    work, while this text reinforces expressions and intent.
    """
    prompt = (
        "Create a 5-second vertical video (9:16) starting from this exact first frame. "
        "Recreate the EXACT hook mechanics that made the original viral video work:\n\n"
        f"FACIAL EXPRESSION: {analysis.get('facial_expressions') or 'engaging expression'}\n"
        f"BODY LANGUAGE & GESTURE: {analysis.get('body_language_gestures') or 'confident body language'}\n"
        f"PACING & MOVEMENT: {analysis.get('pacing_cuts') or 'quick, attention-grabbing pacing'}\n"
        f"HOOK SUMMARY: {analysis.get('hook_summary') or 'attention-grabbing opening'}\n\n"
        "CRITICAL REQUIREMENTS:\n"
        "- Perform the EXACT movements and expressions described above — these are proven to grab attention\n"
        "- Maintain perfect face consistency with the first frame throughout\n"
        "- Smooth, natural motion — no jerky or artificial movement\n"
        "- Camera holds steady or has a subtle push-in matching the original's pacing\n"
        "- The movement should build curiosity and make the viewer want to see more\n"
        "- End on a moment of anticipation (the viewer wants to know what happens next)"
    )

    mechanics = _coerce_mechanics(analysis.get("replicable_mechanics"))
    if mechanics:
        mechanics_str = "; ".join(str(m) for m in mechanics[:5])
        prompt += f"\n\nKEY MECHANICS TO REPLICATE: {mechanics_str}"

    if has_reference_video:
        prompt += (
            "\n\nNOTE: A reference video is provided for V2V motion transfer. "
            "Replicate its timing, camera movement, performance rhythm, and editing pace "
            "while using the new character from the first frame."
        )
    return prompt


def build_hook_prompt_from_image_analysis(image_analysis: dict) -> str:
    """Build the hook-video prompt when only a single still image was analyzed."""
    prompt = (
        "Create a 5-second vertical video (9:16) starting from this exact first frame. "
        "Animate from this starting pose using these movement cues:\n\n"
        f"FACIAL EXPRESSION: {image_analysis.get('facial_expressions') or 'engaging expression'}\n"
        f"BODY LANGUAGE & MOVEMENT: {image_analysis.get('body_language_gestures') or 'confident movement'}\n"
        f"PACING: {image_analysis.get('pacing_cuts') or 'quick, attention-grabbing pacing'}\n"
        f"HOOK CONCEPT: {image_analysis.get('hook_summary') or 'attention-grabbing opening'}\n\n"
        "CRITICAL REQUIREMENTS:\n"
        "- Animate naturally from the starting pose shown in the first frame\n"
        "- Maintain perfect face consistency throughout\n"
        "- Smooth, natural motion — no jerky or artificial movement\n"
        "- The movement should build curiosity and make the viewer want to see more\n"
        "- End on a moment of anticipation"
    )
    mechanics = _coerce_mechanics(image_analysis.get("replicable_mechanics"))
    if mechanics:
        mechanics_str = "; ".join(str(m) for m in mechanics[:5])
        prompt += f"\n\nSPECIFIC MOVEMENTS TO PERFORM: {mechanics_str}"
    return prompt


def build_hook_prompt_from_motion_style(motion_style: str) -> str:
    """Final fallback: a hand-written motion template. Costs zero AI calls."""
    motion_map = {
        "lean-in": HOOK_MOTION_TYPES[0],
        "turn": HOOK_MOTION_TYPES[1],
        "gesture": HOOK_MOTION_TYPES[2],
        "intrigue": HOOK_MOTION_TYPES[3],
        "stop-motion": HOOK_MOTION_TYPES[4],
    }
    key = (motion_style or "").strip()
    motion = motion_map.get(key, HOOK_MOTION_TYPES[0])
    return HOOK_VIDEO_PROMPT_TEMPLATE.format(motion_type=motion)


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
    "intrigue", "reveal", "reaction", "tutorial", "lifestyle", "transformation", "other",
]
HOOK_TEMPLATE_NAME_MAX = 80
HOOK_TEMPLATE_NOTES_MAX = 500


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

    # Copy the key hook frame as a stable thumbnail.
    thumbnail_url = None
    src_frame = _template_thumbnail_source(video, analysis)
    if src_frame:
        dest_frame = pipeline.TEMPLATES_DIR / f"{template_id}.jpg"
        try:
            shutil.copy2(src_frame, dest_frame)
            thumbnail_url = f"/api/media/templates/{template_id}.jpg"
        except OSError as e:
            logger.warning(f"Could not copy thumbnail for template {template_id}: {e}")
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
            facial_expressions, body_language_gestures, pacing_cuts,
            text_overlays_timing, audio_cues_inferred, hook_summary,
            effectiveness_score, replicable_mechanics, prompt_template,
            reference_video_path, song_title, song_artist,
            times_used, last_used_at, created_at, updated_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (template_id, name, _normalize_template_category(payload.category),
         (payload.notes or "").strip()[:HOOK_TEMPLATE_NOTES_MAX],
         video["id"], analysis["id"], video.get("tiktok_url"), video.get("creator"),
         video.get("title"), thumbnail_url,
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
    return await _fetch_one("SELECT * FROM hook_templates WHERE id = ?", (template_id,))


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
    return rows


@api_router.get("/bookmarks/{template_id}")
async def get_hook_template(template_id: str, user_id: str = Depends(get_current_user_id)):
    template = await _fetch_one("SELECT * FROM hook_templates WHERE id = ? AND user_id = ?", (template_id, user_id))
    if not template:
        raise HTTPException(status_code=404, detail="Hook template not found.")
    template["has_motion_reference"] = bool(
        template.get("reference_video_path") and Path(template["reference_video_path"]).exists()
    )
    return template


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
        return existing

    set_clauses.append("updated_at = ?")
    values.append(now_iso())
    values.append(template_id)
    await _execute(
        f"UPDATE hook_templates SET {', '.join(set_clauses)} WHERE id = ?", tuple(values)
    )
    return await _fetch_one("SELECT * FROM hook_templates WHERE id = ?", (template_id,))


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
    user_id: str = Depends(get_current_user_id),
):
    """
    Generate a hook video from the face-swapped image using MiniMax H3.

    H3 advantages leveraged here:
    - Native audio generation in one pass (OFF by default — see include_audio below).
    - V2V motion transfer: if a viral video was analyzed, passes it as a reference
      so H3 replicates the exact timing, camera movement, and performance rhythm.
    - Omni-reference: face-swapped image as first_frame + viral video as motion ref.
    - 2K resolution output.

    If video_id is provided, pulls the hook analysis AND the downloaded video file
    to feed as a V2V motion reference — H3 will replicate the proven hook mechanics
    directly from the source video rather than relying on text descriptions alone.

    If template_id is provided, reuses a saved hook template. This is the cheapest
    path: the prompt and the V2V motion reference are already cached on disk, so
    the request costs ZERO AI calls (no hook re-analysis, no prompt regeneration,
    no re-download of the source video) — only the video generation itself.

    Falls back to a motion-style template if no analysis is available.

    motion_style options: lean-in, turn, gesture, intrigue, stop-motion
    (used as fallback when no hook analysis exists)

    include_audio: defaults to False. Hook videos are silent by default because
    TikTok creators attach a trending sound or native text-to-speech in TikTok's
    own editor after exporting — audio generated here can't be posted as a
    "trending sound" and would just be muted/replaced anyway. Set True to have
    H3 generate an ambient/music track in the same pass (useful for platforms
    without an in-app sound library).
    """
    require_ai_configured()

    image_path = pipeline.GENERATED_DIR / f"{image_id}.png"
    if not image_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Generated face-swap image not found. Please generate the image first.",
        )

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

        # Get the downloaded video file for V2V motion transfer
        video_record = await _fetch_one("SELECT * FROM videos WHERE id = ?", (video_id.strip(),))
        if video_record and video_record.get("local_video_path"):
            v_path = Path(video_record["local_video_path"])
            if v_path.exists():
                reference_video_path = v_path

    if prompt is not None:
        pass  # already resolved from a saved template
    elif analysis:
        # USE THE PROVEN HOOK STRUCTURE from the analyzed viral video.
        prompt = build_hook_prompt_from_analysis(
            analysis, has_reference_video=bool(reference_video_path)
        )
    else:
        # No video analysis available (manual upload) — analyze the IMAGE itself
        image_analysis = await analyze_image_for_hook(image_path, session_id=f"img-hook-{image_id}")

        if image_analysis and image_analysis.get("body_language_gestures"):
            prompt = build_hook_prompt_from_image_analysis(image_analysis)
        else:
            # Final fallback: hand-written motion template (no AI cost)
            prompt = build_hook_prompt_from_motion_style(motion_style)

    # Apply the audio directive last, uniformly, regardless of which branch
    # produced the base prompt (fresh analysis, saved template, image
    # analysis, or motion fallback) — including templates saved before this
    # toggle existed, whose cached text may still reference audio.
    prompt = apply_audio_directive(prompt, False)

    try:
        result = await generate_video(
            prompt=prompt,
            reference_image_path=image_path,
            duration=5,
            generate_audio=False,  # Always silent — creator adds sound in TikTok editor
            reference_video_url=public_media_url(reference_video_path),  # V2V motion transfer
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
        (job_id, image_id, prompt, 5, "pending", polling_url, now_iso()),
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
        "duration": 5,
        "phase": "hook",
        "motion_style": motion_style.strip() or "lean-in",
        "model": "minimax-h3",
        "has_v2v_motion": bool(reference_video_path),
        "has_native_audio": include_audio,
        "from_template": bool(template),
        "template_id": template["id"] if template else None,
        "template_name": template.get("name") if template else None,
    }


@api_router.post("/face-swap/extend-video")
async def face_swap_extend_video(
    image_id: str = Form(...),
    hook_job_id: str = Form(""),
    brand_url: str = Form(""),
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

    image_path = pipeline.GENERATED_DIR / f"{image_id}.png"
    if not image_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Face-swap image not found. Please generate the image first.",
        )

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
        # Try to get brand context
        brand_profile = None
        if brand_url and brand_url.strip():
            url = brand_url.strip()
            if not url.lower().startswith(("http://", "https://")):
                url = f"https://{url}"
            try:
                async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    page_text = strip_html_to_text(resp.text)[:8000]
                    if page_text.strip():
                        brand_profile = await analyze_brand_from_text(url, page_text)
            except Exception as e:
                logger.warning(f"Brand URL fetch failed for extend-video: {e}")

        if not brand_profile:
            brand_row = await _fetch_active_brand()
            if brand_row:
                brand_profile = brand_row

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

    image_path = pipeline.GENERATED_DIR / f"{image_id}.png"
    if not image_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Generated face-swap image not found. Please generate the image first.",
        )

    if not prompt.strip():
        prompt = (
            "Animate this person naturally from the first frame. Keep the same face, pose, and environment. "
            "Add subtle natural motion: slight head movement, blinking, breathing, and gentle body sway. "
            "Maintain perfect face consistency throughout. The scene should feel like a real person in a "
            "natural video — smooth, lifelike motion with no flickering or face changes. "
            "Camera holds steady, matching the original framing. "
            "Generate subtle ambient audio (room tone, gentle background) to make the video feel natural."
        )

    duration = max(3, min(duration, 15))

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

        # Serve from our own stable URL
        response["video_url"] = f"/api/media/videos/{job_id}.mp4"
        response["video_urls"] = [f"/api/media/videos/{job_id}.mp4"]

    if status == "failed":
        response["error"] = result.get("error", "Video generation failed.")

    if result.get("usage"):
        response["usage"] = result["usage"]

    return response


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

    # Validate image exists
    image_path = pipeline.GENERATED_DIR / f"{image_id}.png"
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Face-swap image not found.")

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
        # Try to use saved brand profile
        brand_row = await _fetch_active_brand()
        if brand_row:
            brand_profile = brand_row
        else:
            raise HTTPException(
                status_code=400,
                detail="Please provide a brand URL or set up your brand profile first.",
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
    brand_profile = await get_active_brand_or_404()

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
            raw_extracted_text, created_at, updated_at, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (brand_id, website or None, name, payload.brand_description or "",
         payload.niche or "", json.dumps(payload.products_services or []),
         payload.target_audience or "", payload.ideal_customer_profile or "",
         payload.differentiation or "", payload.tone_voice or "", None,
         created_at, created_at, user_id),
    )
    logger.info(f"Created brand profile {brand_id} ('{name}') from manual entry")
    return await _fetch_one("SELECT * FROM brand_profiles WHERE id = ?", (brand_id,))


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

    set_clauses = []
    values = []
    for key, value in updates.items():
        if key == "products_services":
            value = json.dumps(value if isinstance(value, list) else [value] if value else [])
        set_clauses.append(f"{key} = ?")
        values.append(value)
    set_clauses.append("updated_at = ?")
    values.append(now_iso())
    values.append(brand_id)

    await _execute(
        f"UPDATE brand_profiles SET {', '.join(set_clauses)} WHERE id = ?",
        tuple(values),
    )
    return await _fetch_one("SELECT * FROM brand_profiles WHERE id = ?", (brand_id,))


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
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
    await init_db()
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
    Serve an extracted frame, recovering it on-the-fly if the file is missing
    (ephemeral storage after a redeploy). This takes priority over the static
    mount for frame paths specifically so users always see their filmstrip.
    """
    frame_path = pipeline.FRAMES_DIR / video_hash / filename
    if not frame_path.is_file():
        relative_path = f"frames/{video_hash}/{filename}"
        recovered = await _recover_missing_frame(relative_path)
        if not recovered:
            raise HTTPException(status_code=404, detail="Frame not found.")
    return FileResponse(str(frame_path), media_type="image/jpeg")


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
