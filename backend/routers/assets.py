"""Asset library routes for one App Profile: single owner.

The founder's photograph — the one permitted upload — its usage history, and
the attach/detach wiring onto studio projects all live here. server.py stays
thin composition: it includes this router and re-exports the helpers its
serializers and the render path still call (`_public_asset`,
`_asset_usage_index`, `_asset_dir`, `_ensure_asset_file`).

Shared stateless deps (auth, models, media_signing, pipeline, storage_service,
template_library) import here directly. The DB helpers and the couple of
server-owned utilities (`_write_durable_upload_cache`, `_record_asset_event`)
are resolved at call time through the composition root, because every test
redirects `server.DB_PATH` and monkeypatches `server.<name>` — a value captured
at configure time would miss both. No import of server here, in either
direction: an unconfigured call fails loudly instead of half-working.
"""

import asyncio
import json
import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

import media_signing
import pipeline
import storage_service
import template_library
from auth import get_current_user_id
from models import AttachAssetRequest, UpdateAssetRequest, now_iso

logger = logging.getLogger(__name__)

router = APIRouter()

_server = None


def configure_assets(server_module):
    """Give the router its composition root. Called once at include time."""
    global _server
    _server = server_module


def _cfg(name):
    if _server is None:
        raise RuntimeError("assets router used before configure_assets ran")
    return getattr(_server, name)


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
    rows = await _cfg("_fetch_all")(
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
        await _cfg("_execute")(
            "UPDATE assets SET file_path = ? WHERE id = ?", (str(target), row["id"])
        )
    return target


@router.get("/app-profiles/{profile_id}/assets")
async def list_assets(
    profile_id: str,
    kind: str = "",
    include_archived: bool = False,
    user_id: str = Depends(get_current_user_id),
):
    """Library assets for one App Profile. Always scoped to that profile."""
    profile = await _cfg("_fetch_one")(
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
    rows = await _cfg("_fetch_all")(
        f"SELECT * FROM assets WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT 300",
        tuple(params),
    )
    # One index for the whole page rather than a lookup per asset.
    index = await _asset_usage_index(profile_id)
    return {
        "assets": [_attach_usage(_public_asset(r), index) for r in rows]
    }


@router.get("/assets/{asset_id}/usage")
async def get_asset_usage(asset_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Which projects have used this asset, and which videos came out of them.

    Scoped to the asset's own App Profile, so a user cannot read another
    profile's project names by guessing an asset id.
    """
    asset = await _cfg("_fetch_one")(
        "SELECT * FROM assets WHERE id = ? AND user_id = ?", (asset_id, user_id)
    )
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    index = await _asset_usage_index(asset.get("brand_profile_id"))
    uses = index.get(asset_id, [])
    for use in uses:
        gens = await _cfg("_fetch_all")(
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


@router.post("/app-profiles/{profile_id}/assets", status_code=201)
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
    profile = await _cfg("_fetch_one")(
        "SELECT id FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")

    asset_kind = template_library.normalize_asset_kind(kind)
    if asset_kind != "character_reference":
        await _cfg("_record_asset_event")(
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
        await _cfg("_record_asset_event")(
            "upload_rejected", "Uploaded file is empty.", user_id,
            brand_profile_id=profile_id, asset_kind=asset_kind,
            filename=file.filename or "",
        )
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(raw) > ASSET_MAX_BYTES:
        await _cfg("_record_asset_event")(
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
        await _cfg("_record_asset_event")(
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
    _cfg("_write_durable_upload_cache")(target, raw)

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
    await _cfg("_execute")(
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
    created = _public_asset(await _cfg("_fetch_one")("SELECT * FROM assets WHERE id = ?", (asset_id,)))
    if face_count is not None and face_count != 1:
        created["face_warning"] = (
            "No face detected in this photo — the video provider is likely to refuse it. "
            "Use a clear, front-facing shot."
            if face_count == 0 else
            f"{face_count} faces detected — the provider may flag photos with more than "
            "one person. Use a solo shot if generation is refused."
        )
    return created


@router.patch("/assets/{asset_id}")
async def update_asset(
    asset_id: str, payload: UpdateAssetRequest, user_id: str = Depends(get_current_user_id)
):
    row = await _cfg("_fetch_one")(
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
    await _cfg("_execute")(
        f"UPDATE assets SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?",
        tuple(values),
    )
    return _public_asset(await _cfg("_fetch_one")("SELECT * FROM assets WHERE id = ?", (asset_id,)))


@router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: str, user_id: str = Depends(get_current_user_id)):
    row = await _cfg("_fetch_one")(
        "SELECT * FROM assets WHERE id = ? AND user_id = ?", (asset_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")
    # Deleting the file does not rewrite the projects that referenced it, so
    # their usage history survives as a record of what happened. Surfacing the
    # count lets the caller warn instead of silently orphaning them.
    index = await _asset_usage_index(row.get("brand_profile_id"))
    still_used = index.get(asset_id, [])
    await _cfg("_execute")("DELETE FROM assets WHERE id = ? AND user_id = ?", (asset_id, user_id))
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


@router.post("/studio/projects/{project_id}/assets", status_code=201)
async def attach_asset_to_project(
    project_id: str, payload: AttachAssetRequest, user_id: str = Depends(get_current_user_id)
):
    """
    Attach the character reference to a project.

    Enforces that the asset belongs to the SAME App Profile as the project.
    This is the cross-app guard: without it, one app's photograph could
    anchor another app's video.
    """
    project = await _cfg("_fetch_one")(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?", (project_id, user_id)
    )
    if not project:
        raise HTTPException(status_code=404, detail="Studio project not found")

    asset = await _cfg("_fetch_one")(
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
        await _cfg("_record_asset_event")(
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

    await _cfg("_execute")(
        "UPDATE studio_projects SET assets = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (json.dumps(current), now_iso(), project_id, user_id),
    )
    return {"assets": current}


@router.delete("/studio/projects/{project_id}/assets/{asset_id}")
async def detach_asset_from_project(
    project_id: str, asset_id: str, user_id: str = Depends(get_current_user_id)
):
    project = await _cfg("_fetch_one")(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?", (project_id, user_id)
    )
    if not project:
        raise HTTPException(status_code=404, detail="Studio project not found")
    current = project.get("assets") or []
    if not isinstance(current, list):
        current = []
    remaining = [a for a in current if a.get("asset_id") != asset_id]
    await _cfg("_execute")(
        "UPDATE studio_projects SET assets = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (json.dumps(remaining), now_iso(), project_id, user_id),
    )
    return {"assets": remaining}
