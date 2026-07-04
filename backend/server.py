import asyncio
import io
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient
from PIL import Image
from starlette.middleware.cors import CORSMiddleware

import pipeline
import viral_detection
from ai_service import analyze_hook, generate_customized_preview, generate_video_prompt
from models import IngestVideoRequest, BrandContextRequest, GenerateVideoRequest, now_iso, serialize_doc
from niches_config import NICHES, NICHE_MAP

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="HookForge API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

NICHE_CACHE_TTL = timedelta(hours=6)
TRENDING_CACHE_TTL = timedelta(hours=2)
FRAME_COUNT = 8
HOOK_DURATION_SECONDS = 3.0
SEARCH_QUERY_MAX_LENGTH = 100

# Limit concurrent yt-dlp subprocesses to prevent resource exhaustion
_ytdlp_semaphore = asyncio.Semaphore(3)


# ---------------------------------------------------------------------------
# Trending cache helper
# ---------------------------------------------------------------------------
async def _refresh_trending_cache(niche_key: str, force: bool = False):
    """
    Refresh the trending video cache for a niche by fetching from its hashtags,
    scoring, ranking, and bulk-writing results to MongoDB.
    Returns True if a refresh was performed, False if cache is still fresh.
    """
    trending_cache = await db.trending_videos.find_one({"niche": niche_key, "type": "cache_meta"})
    trending_is_stale = True
    if trending_cache and not force:
        cached_at = datetime.fromisoformat(trending_cache["cached_at"])
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
        # Store in trending_videos collection using bulk insert
        await db.trending_videos.delete_many({"niche": niche_key, "type": {"$ne": "cache_meta"}})
        docs = [
            {**v, "niche": niche_key, "cached_at": now_iso()}
            for v in ranked[:50]
        ]
        await db.trending_videos.insert_many(docs)
        # Update cache meta
        await db.trending_videos.update_one(
            {"niche": niche_key, "type": "cache_meta"},
            {"$set": {"niche": niche_key, "type": "cache_meta", "cached_at": now_iso()}},
            upsert=True,
        )

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
    video = await db.videos.find_one({"id": video_id})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


async def get_latest_analysis_or_404(video_id: str) -> dict:
    analysis = await db.analyses.find_one({"video_id": video_id}, sort=[("created_at", -1)])
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found for this video yet. Analyze the hook first.")
    return analysis


def validate_and_normalize_photo(raw_bytes: bytes) -> bytes:
    """Ensure uploaded photo is a real, non-blank JPEG/PNG/WEBP; convert to PNG if needed."""
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        img.seek(0)  # first frame if animated
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
        raise HTTPException(status_code=400, detail="Uploaded image appears blank/solid-color. Please upload a real photo.")

    max_dim = 1600
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Niches + curated feed
# ---------------------------------------------------------------------------
@api_router.get("/niches")
async def list_niches():
    return [{"key": n["key"], "label": n["label"], "icon": n["icon"], "description": n["description"]} for n in NICHES]


@api_router.get("/niches/{niche_key}/videos")
async def get_niche_videos(niche_key: str, refresh: bool = False, mode: str = "curated"):
    if niche_key not in NICHE_MAP:
        raise HTTPException(status_code=404, detail="Unknown niche")

    if mode not in ("curated", "trending", "mixed"):
        mode = "curated"

    curated_videos = []
    trending_videos = []

    # Fetch curated videos (existing behavior)
    if mode in ("curated", "mixed"):
        cache_meta = await db.niche_cache_meta.find_one({"niche": niche_key})
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
                    doc = {
                        **v,
                        "niche": niche_key,
                        "cached_at": now_iso(),
                    }
                    await db.curated_videos.update_one(
                        {"tiktok_url": v["tiktok_url"]}, {"$set": doc}, upsert=True
                    )
            if fetched_any or not cache_meta:
                await db.niche_cache_meta.update_one(
                    {"niche": niche_key}, {"$set": {"niche": niche_key, "cached_at": now_iso()}}, upsert=True
                )

        raw_curated = await db.curated_videos.find({"niche": niche_key}).sort("view_count", -1).to_list(50)
        # Add virality_score to curated videos
        for v in raw_curated:
            v["virality_score"] = viral_detection.compute_virality_score(v)
            v["source"] = "curated"
        curated_videos = raw_curated

    # Fetch trending videos
    if mode in ("trending", "mixed"):
        await _refresh_trending_cache(niche_key, force=refresh)

        raw_trending = await db.trending_videos.find(
            {"niche": niche_key, "type": {"$ne": "cache_meta"}}
        ).sort("virality_score", -1).to_list(50)
        for v in raw_trending:
            v["source"] = "trending"
        trending_videos = raw_trending

    # Build response based on mode
    if mode == "curated":
        return [serialize_doc(v) for v in curated_videos]
    elif mode == "trending":
        return [serialize_doc(v) for v in trending_videos]
    else:  # mixed
        # Merge and re-rank by virality_score
        combined = curated_videos + trending_videos
        # Deduplicate by tiktok_url
        seen_urls = set()
        unique = []
        for v in combined:
            url = v.get("tiktok_url")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(v)
            elif not url:
                unique.append(v)
        # Sort by virality_score descending
        unique.sort(key=lambda v: v.get("virality_score", 0), reverse=True)
        return [serialize_doc(v) for v in unique[:50]]


@api_router.get("/niches/{niche_key}/trending")
async def get_niche_trending(niche_key: str, refresh: bool = False):
    """Fetch trending videos for a niche from its hashtags, scored and cached."""
    if niche_key not in NICHE_MAP:
        raise HTTPException(status_code=404, detail="Unknown niche")

    await _refresh_trending_cache(niche_key, force=refresh)

    videos = await db.trending_videos.find(
        {"niche": niche_key, "type": {"$ne": "cache_meta"}}
    ).sort("virality_score", -1).to_list(50)
    return [serialize_doc(v) for v in videos]


@api_router.get("/trending/search")
async def trending_search(q: str = "", limit: int = 20):
    """Search TikTok for videos matching a keyword, return scored results."""
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")

    if len(q) > SEARCH_QUERY_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Query too long (max {SEARCH_QUERY_MAX_LENGTH} characters)"
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

    existing = await db.videos.find_one({"tiktok_url": tiktok_url})
    if existing:
        return serialize_doc(existing)

    curated = await db.curated_videos.find_one({"tiktok_url": tiktok_url})
    if curated:
        meta = {k: curated.get(k) for k in [
            "video_platform_id", "creator", "creator_display", "title",
            "view_count", "like_count", "comment_count", "duration", "thumbnail_url",
        ]}
        niche = curated.get("niche") or payload.niche
    else:
        try:
            meta = await pipeline.fetch_video_metadata(tiktok_url)
        except Exception as e:
            logger.error(f"Metadata fetch failed for {tiktok_url}: {e}")
            raise HTTPException(status_code=400, detail=f"Could not fetch this TikTok video. Please check the URL and try again. ({str(e)[:150]})")
        niche = payload.niche

    video_doc = {
        "id": str(uuid.uuid4()),
        "tiktok_url": tiktok_url,
        "niche": niche,
        **meta,
        "status": "metadata_ready",
        "local_video_path": None,
        "created_at": now_iso(),
    }
    await db.videos.insert_one(video_doc)
    return serialize_doc(video_doc)


@api_router.get("/videos/{video_id}")
async def get_video(video_id: str):
    video = await get_video_or_404(video_id)
    return serialize_doc(video)


@api_router.post("/videos/{video_id}/analyze-hook")
async def analyze_video_hook(video_id: str):
    video = await get_video_or_404(video_id)
    tiktok_url = video["tiktok_url"]
    video_hash = pipeline.url_hash(tiktok_url)

    try:
        video_path = await pipeline.download_video(tiktok_url)
    except Exception as e:
        logger.error(f"Download failed for {tiktok_url}: {e}")
        await db.videos.update_one({"id": video_id}, {"$set": {"status": "failed", "error": str(e)[:400]}})
        raise HTTPException(status_code=502, detail=f"Failed to download the video. It may be private or removed. ({str(e)[:150]})")

    try:
        frame_paths = await pipeline.extract_hook_frames(video_path, num_frames=FRAME_COUNT, duration=HOOK_DURATION_SECONDS)
    except Exception as e:
        logger.error(f"Frame extraction failed for {video_id}: {e}")
        await db.videos.update_one({"id": video_id}, {"$set": {"status": "failed", "error": str(e)[:400]}})
        raise HTTPException(status_code=500, detail=f"Failed to extract frames from the video. ({str(e)[:150]})")

    frame_docs = build_frame_docs(video_hash, frame_paths)

    try:
        analysis_result = await analyze_hook(frame_paths, session_id=f"hook-{video_id}")
    except Exception as e:
        logger.error(f"Hook analysis failed for {video_id}: {e}")
        await db.videos.update_one({"id": video_id}, {"$set": {"status": "failed", "error": str(e)[:400]}})
        raise HTTPException(status_code=502, detail=f"AI hook analysis failed. Please try again. ({str(e)[:150]})")

    analysis_doc = {
        "id": str(uuid.uuid4()),
        "video_id": video_id,
        "frames": frame_docs,
        **analysis_result,
        "created_at": now_iso(),
    }
    await db.analyses.insert_one(analysis_doc)
    await db.videos.update_one(
        {"id": video_id},
        {"$set": {"status": "analyzed", "local_video_path": str(video_path), "last_analysis_id": analysis_doc["id"]}},
    )
    return serialize_doc(analysis_doc)


@api_router.get("/videos/{video_id}/analysis")
async def get_video_analysis(video_id: str):
    analysis = await get_latest_analysis_or_404(video_id)
    return serialize_doc(analysis)


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
    key_idx = max(1, min(len(frames), int(analysis.get("key_hook_frame_index", 1))))

    try:
        selected_indices = json.loads(frame_indices) if frame_indices else []
        selected_indices = [int(i) for i in selected_indices if isinstance(i, (int, float, str))]
    except (json.JSONDecodeError, ValueError, TypeError):
        selected_indices = []
    if not selected_indices:
        selected_indices = [key_idx]
    # De-dupe, clamp to valid range, cap at 3 images per user request (generate 1-3 images)
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
            raise HTTPException(status_code=400, detail="Reference hook frame is missing. Please re-analyze the video.")
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
            raise HTTPException(status_code=502, detail=f"AI preview generation failed. Please try again. ({str(e)[:150]})")

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
        "note": "This face-swapped still frame is ready to be used as a reference image for AI video generation once a provider is connected.",
    }

    customization_doc = {
        "id": str(uuid.uuid4()),
        "video_id": video_id,
        "analysis_id": analysis["id"],
        "mode": mode,
        "person_photo_url": f"/api/media/uploads/{photo_id}.png",
        "reference_frame_url": generated_images[0]["reference_frame_url"] if generated_images else None,
        "environment": environment,
        "background": background,
        "clothing": clothing,
        "custom_instructions": custom_instructions,
        "generation_spec": generation_spec,
        "generated_images": generated_images,
        # Kept for backwards-compat with any UI that expects a single result image.
        "generated_image_url": generated_images[0]["image_url"] if generated_images else None,
        "video_title": video.get("title"),
        "video_niche": video.get("niche"),
        "created_at": now_iso(),
    }
    await db.customizations.insert_one(customization_doc)
    return serialize_doc(customization_doc)


@api_router.get("/customizations")
async def list_customizations():
    items = await db.customizations.find().sort("created_at", -1).to_list(200)
    return [serialize_doc(i) for i in items]


@api_router.get("/customizations/{customization_id}")
async def get_customization(customization_id: str):
    item = await db.customizations.find_one({"id": customization_id})
    if not item:
        raise HTTPException(status_code=404, detail="Customization not found")
    return serialize_doc(item)


# ---------------------------------------------------------------------------
# Step 4: Video generation (prompt auto-generation + provider-pending job)
# ---------------------------------------------------------------------------
@api_router.post("/customizations/{customization_id}/generate-video-prompt")
async def generate_video_prompt_endpoint(customization_id: str, payload: BrandContextRequest):
    customization = await db.customizations.find_one({"id": customization_id})
    if not customization:
        raise HTTPException(status_code=404, detail="Customization not found")
    analysis = await db.analyses.find_one({"id": customization["analysis_id"]})
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

    video_job_doc = {
        "id": str(uuid.uuid4()),
        "customization_id": customization_id,
        "video_id": customization["video_id"],
        "brand_name": payload.brand_name,
        "brand_goal": payload.brand_goal,
        "brand_details": payload.brand_details,
        "target_duration_seconds": duration,
        "prompt_breakdown": prompt_result,
        "full_prompt_text": prompt_result.get("full_video_prompt"),
        "reference_image_ids": [img["id"] for img in customization.get("generated_images", [])],
        "status": "prompt_ready",
        "created_at": now_iso(),
    }
    await db.video_jobs.insert_one(video_job_doc)
    return serialize_doc(video_job_doc)


@api_router.post("/video-jobs/{job_id}/generate-video")
async def generate_video_endpoint(job_id: str, payload: GenerateVideoRequest):
    job = await db.video_jobs.find_one({"id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")

    update = {
        "full_prompt_text": payload.edited_prompt or job.get("full_prompt_text"),
        "selected_image_ids": payload.image_ids or job.get("reference_image_ids", []),
        "target_duration_seconds": max(5, min(30, payload.duration_seconds or job.get("target_duration_seconds", 30))),
        "status": "pending_provider_selection",
        "requested_at": now_iso(),
    }
    await db.video_jobs.update_one({"id": job_id}, {"$set": update})
    updated = await db.video_jobs.find_one({"id": job_id})
    return serialize_doc(updated)


@api_router.get("/video-jobs/{job_id}")
async def get_video_job(job_id: str):
    job = await db.video_jobs.find_one({"id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    return serialize_doc(job)


@api_router.get("/customizations/{customization_id}/video-jobs")
async def get_customization_video_jobs(customization_id: str):
    jobs = await db.video_jobs.find({"customization_id": customization_id}).sort("created_at", -1).to_list(50)
    return [serialize_doc(j) for j in jobs]


@api_router.get("/history")
async def get_history():
    videos = await db.videos.find({"status": {"$in": ["analyzed", "failed"]}}).sort("created_at", -1).to_list(200)
    video_ids = [v["id"] for v in videos]
    analyses = await db.analyses.find({"video_id": {"$in": video_ids}}).to_list(500)
    analyses_by_video = {}
    for a in analyses:
        analyses_by_video.setdefault(a["video_id"], []).append(a)
    customizations = await db.customizations.find({"video_id": {"$in": video_ids}}).to_list(500)
    customizations_by_video = {}
    for c in customizations:
        customizations_by_video.setdefault(c["video_id"], []).append(serialize_doc(c))
    video_jobs = await db.video_jobs.find({"video_id": {"$in": video_ids}}).to_list(500)
    video_jobs_by_video = {}
    for j in video_jobs:
        video_jobs_by_video.setdefault(j["video_id"], []).append(serialize_doc(j))

    results = []
    for v in videos:
        results.append({
            "video": serialize_doc(v),
            "analysis_count": len(analyses_by_video.get(v["id"], [])),
            "customizations": customizations_by_video.get(v["id"], []),
            "video_jobs": video_jobs_by_video.get(v["id"], []),
        })
    return results


@api_router.get("/")
async def root():
    return {"message": "HookForge API"}


app.include_router(api_router)
app.mount("/api/media", StaticFiles(directory=str(pipeline.STORAGE_DIR)), name="media")

# ---------------------------------------------------------------------------
# Serve frontend static build (in container deployment)
# ---------------------------------------------------------------------------
FRONTEND_BUILD_DIR = Path(__file__).parent.parent / "frontend_build"
if FRONTEND_BUILD_DIR.exists():
    from starlette.responses import FileResponse

    app.mount("/static", StaticFiles(directory=str(FRONTEND_BUILD_DIR / "static")), name="frontend_static")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve index.html for any non-API, non-static path (SPA routing)."""
        file_path = FRONTEND_BUILD_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_BUILD_DIR / "index.html"))

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
