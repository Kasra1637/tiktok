import asyncio
import io
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import aiosqlite
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from PIL import Image
from starlette.middleware.cors import CORSMiddleware

import pipeline
import viral_detection
from ai_service import (
    analyze_hook, generate_customized_preview, generate_video_prompt,
    generate_video, poll_video_job, analyze_brand_from_text, generate_remix_script,
    strip_html_to_text,
)
from models import (
    IngestVideoRequest, BrandContextRequest, GenerateVideoRequest,
    AnalyzeBrandUrlRequest, BrandProfileUpdateRequest, GenerateRemixScriptRequest,
    now_iso, row_to_dict,
)
from niches_config import NICHES, NICHE_MAP

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

_ytdlp_semaphore = asyncio.Semaphore(3)


# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------
@asynccontextmanager
async def get_db():
    """Async context manager for SQLite connections."""
    conn = await aiosqlite.connect(str(DB_PATH))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
    finally:
        await conn.close()


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
                duration REAL DEFAULT 0,
                thumbnail_url TEXT,
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
                duration REAL DEFAULT 0,
                thumbnail_url TEXT,
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
                duration REAL DEFAULT 0,
                thumbnail_url TEXT,
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
                tone_voice TEXT,
                raw_extracted_text TEXT,
                created_at TEXT,
                updated_at TEXT
            );
        """)
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
    hashtag_results = await asyncio.gather(
        *[viral_detection.fetch_hashtag_videos(tag, limit=10) for tag in hashtags],
        return_exceptions=True,
    )
    all_videos = []
    for tag, result in zip(hashtags, hashtag_results):
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
                        title, view_count, like_count, comment_count, duration,
                        thumbnail_url, virality_score, cached_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (niche_key, v.get("tiktok_url"), v.get("video_platform_id"),
                     v.get("creator"), v.get("creator_display"), v.get("title"),
                     v.get("view_count", 0), v.get("like_count", 0),
                     v.get("comment_count", 0), v.get("duration", 0),
                     v.get("thumbnail_url"), v.get("virality_score", 0), now_iso()),
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


async def get_active_brand_or_404() -> dict:
    brand = await _fetch_one("SELECT * FROM brand_profiles ORDER BY created_at DESC LIMIT 1")
    if not brand:
        raise HTTPException(
            status_code=404,
            detail="No brand profile yet. Analyze your website URL first.",
        )
    return brand


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
async def get_niche_videos(niche_key: str, refresh: bool = False, mode: str = "curated"):
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
            creator_results = await asyncio.gather(
                *[pipeline.fetch_creator_videos(handle, limit=2) for handle in creators],
                return_exceptions=True,
            )
            fetched_any = False
            for handle, videos in zip(creators, creator_results):
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
                                comment_count, duration, thumbnail_url, cached_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (v["tiktok_url"], niche_key, v.get("video_platform_id"),
                             v.get("creator"), v.get("creator_display"), v.get("title"),
                             v.get("view_count", 0), v.get("like_count", 0),
                             v.get("comment_count", 0), v.get("duration", 0),
                             v.get("thumbnail_url"), now_iso()),
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
        return curated_videos
    elif mode == "trending":
        return trending_videos
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
        return unique[:50]


@api_router.get("/niches/{niche_key}/trending")
async def get_niche_trending(niche_key: str, refresh: bool = False):
    if niche_key not in NICHE_MAP:
        raise HTTPException(status_code=404, detail="Unknown niche")
    await _refresh_trending_cache(niche_key, force=refresh)
    videos = await _fetch_all(
        "SELECT * FROM trending_videos WHERE niche = ? ORDER BY virality_score DESC LIMIT 50",
        (niche_key,),
    )
    return videos


@api_router.get("/trending/search")
async def trending_search(q: str = "", limit: int = 20):
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
    return ranked


# ---------------------------------------------------------------------------
# Video ingestion + analysis
# ---------------------------------------------------------------------------
@api_router.post("/videos/ingest")
async def ingest_video(payload: IngestVideoRequest):
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
            description, view_count, like_count, comment_count, duration, thumbnail_url,
            status, local_video_path, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (video_id, tiktok_url, niche, meta.get("video_platform_id"), meta.get("creator"),
         meta.get("creator_display"), meta.get("title"), meta.get("description", ""),
         meta.get("view_count", 0), meta.get("like_count", 0), meta.get("comment_count", 0),
         meta.get("duration", 0), meta.get("thumbnail_url"), "metadata_ready", None, created_at),
    )
    return await get_video_or_404(video_id)


@api_router.get("/videos/{video_id}")
async def get_video(video_id: str):
    return await get_video_or_404(video_id)


@api_router.post("/videos/{video_id}/analyze-hook")
async def analyze_video_hook(video_id: str):
    require_ai_configured()
    video = await get_video_or_404(video_id)
    tiktok_url = video["tiktok_url"]
    video_hash = pipeline.url_hash(tiktok_url)

    try:
        async with _ytdlp_semaphore:
            video_path = await pipeline.download_video(tiktok_url)
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

    try:
        analysis_result = await analyze_hook(frame_paths, session_id=f"hook-{video_id}")
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
            key_hook_frame_index, replicable_mechanics, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (analysis_id, video_id, json.dumps(frame_docs),
         analysis_result.get("facial_expressions"), analysis_result.get("body_language_gestures"),
         analysis_result.get("pacing_cuts"), analysis_result.get("text_overlays_timing"),
         analysis_result.get("audio_cues_inferred"), analysis_result.get("hook_summary"),
         analysis_result.get("effectiveness_score"), analysis_result.get("key_hook_frame_index"),
         json.dumps(analysis_result.get("replicable_mechanics", [])), created_at),
    )
    await _execute(
        "UPDATE videos SET status = ?, local_video_path = ?, last_analysis_id = ? WHERE id = ?",
        ("analyzed", str(video_path), analysis_id, video_id),
    )
    return await _fetch_one("SELECT * FROM analyses WHERE id = ?", (analysis_id,))


@api_router.get("/videos/{video_id}/analysis")
async def get_video_analysis(video_id: str):
    return await get_latest_analysis_or_404(video_id)


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
            generated_images, generated_image_url, video_title, video_niche, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (customization_id, video_id, analysis["id"], mode, f"/api/media/uploads/{photo_id}.png",
         generated_images[0]["reference_frame_url"] if generated_images else None,
         environment, background, clothing, custom_instructions, json.dumps(generation_spec),
         json.dumps(generated_images), generated_images[0]["image_url"] if generated_images else None,
         video.get("title"), video.get("niche"), created_at),
    )
    return await _fetch_one("SELECT * FROM customizations WHERE id = ?", (customization_id,))


@api_router.get("/customizations")
async def list_customizations():
    return await _fetch_all("SELECT * FROM customizations ORDER BY created_at DESC LIMIT 200")


@api_router.get("/customizations/{customization_id}")
async def get_customization(customization_id: str):
    item = await _fetch_one("SELECT * FROM customizations WHERE id = ?", (customization_id,))
    if not item:
        raise HTTPException(status_code=404, detail="Customization not found")
    return item


# ---------------------------------------------------------------------------
# Video generation: prompt writing + OpenRouter video job submission/polling
# ---------------------------------------------------------------------------
@api_router.post("/customizations/{customization_id}/generate-video-prompt")
async def generate_video_prompt_endpoint(customization_id: str, payload: BrandContextRequest):
    require_ai_configured()
    customization = await _fetch_one("SELECT * FROM customizations WHERE id = ?", (customization_id,))
    if not customization:
        raise HTTPException(status_code=404, detail="Customization not found")
    analysis = await _fetch_one("SELECT * FROM analyses WHERE id = ?", (customization["analysis_id"],))
    if not analysis:
        raise HTTPException(status_code=404, detail="Related hook analysis not found")

    duration = max(5, min(30, payload.duration_seconds or 30))

    try:
        prompt_result = await generate_video_prompt(
            analysis=analysis,
            brand_context=payload.model_dump(),
            target_duration=duration,
            session_id=f"videoprompt-{customization_id}",
        )
    except Exception as e:
        logger.error(f"Video prompt generation failed for {customization_id}: {e}")
        raise HTTPException(status_code=502, detail=f"AI prompt generation failed. Please try again. ({str(e)[:150]})")

    job_id = str(uuid.uuid4())
    created_at = now_iso()
    reference_image_ids = [img["id"] for img in customization.get("generated_images", [])]
    await _execute(
        """INSERT INTO video_jobs
           (id, customization_id, video_id, brand_name, brand_goal, brand_details,
            target_duration_seconds, prompt_breakdown, full_prompt_text, reference_image_ids,
            status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, customization_id, customization["video_id"], payload.brand_name, payload.brand_goal,
         payload.brand_details, duration, json.dumps(prompt_result), prompt_result.get("full_video_prompt"),
         json.dumps(reference_image_ids), "prompt_ready", created_at),
    )
    return await _fetch_one("SELECT * FROM video_jobs WHERE id = ?", (job_id,))


@api_router.post("/customizations/{customization_id}/generate-remix-script")
async def generate_remix_script_endpoint(customization_id: str, payload: GenerateRemixScriptRequest):
    """Content Remixer: adapt this hook's script to the active brand profile's niche/products/tone."""
    require_ai_configured()
    brand_profile = await get_active_brand_or_404()

    customization = await _fetch_one("SELECT * FROM customizations WHERE id = ?", (customization_id,))
    if not customization:
        raise HTTPException(status_code=404, detail="Customization not found")
    analysis = await _fetch_one("SELECT * FROM analyses WHERE id = ?", (customization["analysis_id"],))
    if not analysis:
        raise HTTPException(status_code=404, detail="Related hook analysis not found")

    duration = max(5, min(30, payload.duration_seconds or 30))

    try:
        prompt_result = await generate_remix_script(
            analysis=analysis,
            brand_profile=brand_profile,
            target_duration=duration,
            session_id=f"remix-{customization_id}",
        )
    except Exception as e:
        logger.error(f"Remix script generation failed for {customization_id}: {e}")
        raise HTTPException(status_code=502, detail=f"AI remix script generation failed. Please try again. ({str(e)[:150]})")

    job_id = str(uuid.uuid4())
    created_at = now_iso()
    reference_image_ids = [img["id"] for img in customization.get("generated_images", [])]
    await _execute(
        """INSERT INTO video_jobs
           (id, customization_id, video_id, brand_name, brand_goal, brand_details,
            target_duration_seconds, prompt_breakdown, full_prompt_text, reference_image_ids,
            status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, customization_id, customization["video_id"], brand_profile.get("brand_name"),
         "Content Remixer: adapt viral hook to brand", brand_profile.get("brand_description"),
         duration, json.dumps(prompt_result), prompt_result.get("full_video_prompt"),
         json.dumps(reference_image_ids), "prompt_ready", created_at),
    )
    return await _fetch_one("SELECT * FROM video_jobs WHERE id = ?", (job_id,))


@api_router.post("/video-jobs/{job_id}/generate-video")
async def generate_video_endpoint(job_id: str, payload: GenerateVideoRequest):
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
async def submit_video_job(job_id: str):
    """Actually submit the video generation job to OpenRouter (HappyHorse)."""
    require_ai_configured()
    job = await _fetch_one("SELECT * FROM video_jobs WHERE id = ?", (job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")

    customization = await _fetch_one(
        "SELECT * FROM customizations WHERE id = ?", (job["customization_id"],)
    )
    reference_image_path = None
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

    try:
        result = await generate_video(
            prompt=job.get("full_prompt_text") or "",
            reference_image_path=reference_image_path,
            duration=job.get("target_duration_seconds", 10) or 10,
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
async def poll_video_job_endpoint(job_id: str):
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
async def get_video_job(job_id: str):
    job = await _fetch_one("SELECT * FROM video_jobs WHERE id = ?", (job_id,))
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    return job


@api_router.get("/customizations/{customization_id}/video-jobs")
async def get_customization_video_jobs(customization_id: str):
    return await _fetch_all(
        "SELECT * FROM video_jobs WHERE customization_id = ? ORDER BY created_at DESC LIMIT 50",
        (customization_id,),
    )


# ---------------------------------------------------------------------------
# Brand profile ("Your Brand" — URL analysis + manual editing)
# ---------------------------------------------------------------------------
@api_router.post("/brand/analyze-url")
async def analyze_brand_url(payload: AnalyzeBrandUrlRequest):
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

    brand_id = str(uuid.uuid4())
    created_at = now_iso()
    await _execute(
        """INSERT INTO brand_profiles
           (id, website_url, brand_name, brand_description, niche, products_services,
            target_audience, tone_voice, raw_extracted_text, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (brand_id, url, extracted.get("brand_name"), extracted.get("brand_description"),
         extracted.get("niche"), json.dumps(extracted.get("products_or_services", [])),
         extracted.get("target_audience"), extracted.get("tone_voice"), page_text,
         created_at, created_at),
    )
    return await _fetch_one("SELECT * FROM brand_profiles WHERE id = ?", (brand_id,))


@api_router.get("/brand/active")
async def get_active_brand():
    return await get_active_brand_or_404()


@api_router.get("/brand/{brand_id}")
async def get_brand(brand_id: str):
    brand = await _fetch_one("SELECT * FROM brand_profiles WHERE id = ?", (brand_id,))
    if not brand:
        raise HTTPException(status_code=404, detail="Brand profile not found")
    return brand


@api_router.patch("/brand/{brand_id}")
async def update_brand(brand_id: str, payload: BrandProfileUpdateRequest):
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
async def get_history():
    videos = await _fetch_all(
        "SELECT * FROM videos WHERE status IN ('analyzed', 'failed') ORDER BY created_at DESC LIMIT 200"
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
    return results


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
    await init_db()
    if not os.environ.get("OPENROUTER_API_KEY"):
        logger.warning(
            "OPENROUTER_API_KEY is not set. The app will run, but AI features "
            "(hook analysis, face swap, video generation) will return 503 until it is set."
        )


app.include_router(api_router)
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
