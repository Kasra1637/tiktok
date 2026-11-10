"""Durable media serving: frames, templates, posters, videos and assets.

One router owns every signed `/api/media/*` read. The six routes were
formerly `@app.get` handlers in `server.py`; they are now `APIRouter` routes
included under the existing `/api` prefix, preserving the exact paths. They
must register before the blanket StaticFiles mount in `server.py`: Starlette
matches in registration order, so these routes still shadow `/api/media/*`
while every other media path stays with StaticFiles.

Shared stateless deps (pipeline, posters, storage_service, media_signing)
import here directly. DB-touching reads and the asset helper stay owned by
the composition root and are injected here once via `configure_media`.
No import of server here, in either direction: an unconfigured call fails
loudly instead of half-working. `server.py` re-exports the helpers its
tests and generation code still call.
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response, RedirectResponse, StreamingResponse

import media_signing
import pipeline
import posters
import storage_service

logger = logging.getLogger(__name__)

router = APIRouter()

_fetch_one = None
_ensure_analysis_frame = None
_ensure_template_thumbnail = None
_recover_missing_frame = None
_ensure_asset_file = None
_http_video_source = None
_ffmpeg_slot = None
_generated_id_re = None


def configure_media(fetch_one, ensure_analysis_frame, ensure_template_thumbnail,
                    recover_missing_frame, ensure_asset_file, http_video_source,
                    ffmpeg_slot=None, generated_id_re=None):
    """Inject the composition root's DB and media helpers. Once, at include."""
    global _fetch_one, _ensure_analysis_frame, _ensure_template_thumbnail
    global _recover_missing_frame, _ensure_asset_file, _http_video_source
    global _ffmpeg_slot, _generated_id_re
    _fetch_one = fetch_one
    _ensure_analysis_frame = ensure_analysis_frame
    _ensure_template_thumbnail = ensure_template_thumbnail
    _recover_missing_frame = recover_missing_frame
    _ensure_asset_file = ensure_asset_file
    _http_video_source = http_video_source
    _ffmpeg_slot = ffmpeg_slot
    _generated_id_re = generated_id_re


def _require_configured():
    if any(v is None for v in (_fetch_one, _ensure_analysis_frame,
                                _ensure_template_thumbnail, _recover_missing_frame,
                                _ensure_asset_file, _http_video_source,
                                _ffmpeg_slot, _generated_id_re)):
        raise RuntimeError("media router used before configure_media ran")


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


@router.get("/media/frames/{video_hash}/{filename}")
async def serve_frame(video_hash: str, filename: str):
    """
    Serve an extracted analysis frame from its local cache or durable JPEG
    backup. Older analyses may still have only a cached MP4, which remains a
    final no-network re-extraction fallback.
    """
    _require_configured()
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


@router.get("/media/templates/{template_id}.jpg")
async def serve_template_thumbnail(template_id: str):
    """Serve a durable bookmark thumbnail, restoring its local cache if needed."""
    _require_configured()
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


@router.get("/media/videos/{filename}")
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
    _require_configured()
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


@router.get("/media/videos/{filename}/download")
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
    _require_configured()
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


@router.get("/media/posters/{filename}")
async def serve_poster(filename: str, sig: str = "", exp: str = ""):
    """
    Serve a generation's poster thumbnail so History can render it as an image.

    Signed like video (an <img src> cannot carry auth either, and posters are
    thumbnails of paid renders). Lazy: if no cached JPEG exists, build one
    from the local clip, or restore the clip/poster from R2 via the row's
    owner and then build it. A missing poster is a 404 the frontend treats as
    "no thumbnail yet" — playback must never depend on it.
    """
    _require_configured()
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
    async with _ffmpeg_slot:
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


@router.get("/media/assets/{asset_id}")
async def serve_asset(asset_id: str, request: Request, sig: str = "", exp: str = ""):
    """
    Serve a character reference asset so the template card and Review step
    can display the founder's photo. Signed like videos so a raw URL cannot
    be guessed — the filename IS the asset id, and the signature proves
    the founder authorized this specific asset view.
    """
    _require_configured()
    if not _generated_id_re.match(asset_id or ""):
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
