"""Hook + CTA: one router owns the hook-cta draft, its hook, and its
render submit (ADR 0244).

A hook-cta draft is a studio project row (kind='video', surface=
'hook_cta', ADR 0244): its renders are ordinary video generations, so
History, post kits and analytics treat them as video renders, and this
router is deliberately thin in the shape the retired stories router
had — project creation writes the same table the wizard writes, the
hook is one ai_service call, and the render submits through the
composition root's `_submit_generation`, the only render path, at the
pick's exact duration so the ADR 0239 beat trim (re-homed) cuts the
saved file back to the pick below the provider floor.

The DB-touching and render helpers stay owned by the composition root
(server.py) and are injected via `configure_hook_cta` at include time,
resolved at CALL time through `_cfg` — the same pattern
routers/studio.py uses, so a test that patches `server.<name>`
intercepts the call here too. Stateless deps (auth, models,
ai_service, ai_spoken) import directly. No import of server here: an
unconfigured call fails loudly instead of half-working.
"""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

import ai_service
import video_providers
from ai_service import TEXT_MODEL
from ai_spoken import SHORT_HOOK_SECONDS
from auth import get_current_user_id
from models import (
    CreateHookCtaProjectRequest,
    GenerateHookLineRequest,
    GenerateHookRequest,
    now_iso,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_server = None


def configure_hook_cta(server_module):
    """Inject the composition root. Called once at include time."""
    global _server
    _server = server_module


def _cfg(name):
    if _server is None:
        raise RuntimeError("hook_cta router used before configure_hook_cta ran")
    return getattr(_server, name)


def _fetch_one(*a, **k):
    return _cfg("_fetch_one")(*a, **k)


def _execute(*a, **k):
    return _cfg("_execute")(*a, **k)


def _log_model_call(*a, **k):
    return _cfg("_log_model_call")(*a, **k)


def _submit_generation(*a, **k):
    return _cfg("_submit_generation")(*a, **k)


def _public_project(*a, **k):
    return _cfg("_public_project")(*a, **k)


def _project_strategy(*a, **k):
    return _cfg("_project_strategy")(*a, **k)


def _require_profile_for_studio(*a, **k):
    return _cfg("_require_profile_for_studio")(*a, **k)


def _request_id(*a, **k):
    return _cfg("_request_id")(*a, **k)


def require_ai_configured(*a, **k):
    return _cfg("require_ai_configured")(*a, **k)


def _refuse_retired_project_assets(*a, **k):
    return _cfg("_refuse_retired_project_assets")(*a, **k)


def _assert_model_usable(*a, **k):
    return _cfg("_assert_model_usable")(*a, **k)


def _assert_resolution_offered(*a, **k):
    return _cfg("_assert_resolution_offered")(*a, **k)


def _assert_within_single_pass_cap(*a, **k):
    return _cfg("_assert_within_single_pass_cap")(*a, **k)


# ---------------------------------------------------------------------------
# Hook + CTA projects
# ---------------------------------------------------------------------------

@router.post("/hook-cta/projects", status_code=201)
async def create_hook_cta_project(
    payload: CreateHookCtaProjectRequest, user_id: str = Depends(get_current_user_id)
):
    """Create a Hook + CTA draft against an APPROVED App Profile.

    The row is an ordinary studio project with kind='video' and the
    surface marker 'hook_cta' (ADR 0244, migration step 9): same table,
    same PATCH, same reads — only the create path and the hook/generate
    endpoints are page-shaped. The wizard's create cannot be reused:
    its duration clamp floors at 8 seconds, and a hook runs 4 or 5.
    hook_seconds is stored at 4, the shared machinery's widest hook
    window: the render counts the hook's words first against that
    window's ceiling, and the line is generated under the frame's own
    tighter character budget, so the words always fit the hook section
    whole and are never re-sliced into a script on read — this page
    has no script.
    """
    profile = await _require_profile_for_studio(payload.brand_profile_id, user_id)

    seconds = payload.frame_seconds or 5
    if seconds not in SHORT_HOOK_SECONDS:
        raise HTTPException(
            status_code=400,
            detail="A hook runs 4 or 5 seconds.",
        )

    project_id = str(uuid.uuid4())
    now = now_iso()
    await _execute(
        """INSERT INTO studio_projects
           (id, brand_profile_id, content_angle_id, template_id, template_version,
             objective, audience, duration_seconds, hook_seconds, extend_intent, tone, assets,
             script_version, status, created_at, updated_at, user_id, camera_setup, kind,
             surface, frame_count)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (project_id, profile["id"], None,
         None, None, None,
         (profile.get("target_audience") or "").strip() or None,
         seconds, 4, 1, None,
         json.dumps([]), 0, "draft", now, now, user_id, payload.camera_setup,
         "video", "hook_cta", 1),
    )
    logger.info(f"Created hook-cta project {project_id} for profile {profile['id']}")
    return _public_project(
        await _fetch_one("SELECT * FROM studio_projects WHERE id = ?", (project_id,)),
        brand_name=(profile.get("brand_name") or "").strip(),
    )


async def _hook_cta_project_row(project_id: str, user_id: str) -> dict:
    """The hook-cta row for a page endpoint: 404 when missing, 400 when
    the row belongs to another surface — a hook-cta endpoint answering
    a wizard project (or a legacy story draft) in this page's words
    would be a silent surface mix-up, so the refusal names the page
    the project actually belongs to."""
    row = await _fetch_one(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?",
        (project_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Hook + CTA project not found")
    if (row.get("surface") or "") != "hook_cta":
        if (row.get("kind") or "video") == "story":
            raise HTTPException(
                status_code=400,
                detail=(
                    "This project is a story draft from the retired Stories "
                    "page — its renders stay in History, and it cannot be "
                    "opened here."
                ),
            )
        raise HTTPException(
            status_code=400,
            detail=(
                "This project is a hook video — it opens in Create Video "
                "instead."
            ),
        )
    return row


@router.post("/hook-cta/projects/{project_id}/hook")
async def generate_hook_cta_hook(
    project_id: str, payload: GenerateHookLineRequest,
    user_id: str = Depends(get_current_user_id),
):
    """
    Write the draft's one hook line and its render direction.

    One generation, saved as the project's hook plus the strategy the
    render reads (ADR 0244): the strategy is assembled here,
    deterministically, from the hook's own beats and the saved
    direction picks — this page has no separate strategy step, because
    its review surface is the hook itself. The scene is locked from
    the direction the founder saved (ADR 0220's rule: camera and
    location are chosen before the words, and the words respect them);
    only an untouched draft takes the hook call's own location. No
    script is written, ever: the middle segment is direction only —
    the closing beat the demo cuts away from.
    """
    require_ai_configured()
    row = await _hook_cta_project_row(project_id, user_id)
    profile = await _require_profile_for_studio(row.get("brand_profile_id"), user_id)
    _refuse_retired_project_assets(row.get("assets"))

    seconds = payload.frame_seconds or int(row.get("duration_seconds") or 0)
    if seconds not in SHORT_HOOK_SECONDS:
        raise HTTPException(
            status_code=400,
            detail="A hook runs 4 or 5 seconds.",
        )

    hook_project = dict(row)
    hook_project["duration_seconds"] = seconds
    try:
        hook = await _log_model_call(
            "hook_line", "text", TEXT_MODEL,
            lambda: ai_service.generate_hook_line(hook_project, profile),
            user_id,
            brand_profile_id=row.get("brand_profile_id"),
            studio_project_id=project_id,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Hook failed: {str(e)[:800]}")

    location = (row.get("location") or "").strip() or hook.get("location") or ""
    strategy = {
        "hook_concept": hook.get("hook_line") or "",
        "hook_promise": "",
        "strategy_summary": "",
        "audience_problem": "",
        "segments": [
            {
                "index": 0, "role": "hook", "seconds": 4,
                "goal": "Open on the goal",
                "script": hook.get("hook_line") or "",
                "action": hook.get("hook_action") or "",
            },
            {
                "index": 1, "role": "middle", "seconds": max(1, seconds - 4),
                "goal": "Hold the moment for the demo",
                "script": "",
                "action": hook.get("closing_action") or "",
            },
        ],
        "scene": {
            "location": location,
            "camera_angle": "", "framing": "", "lighting": "",
            "visual_style": "", "character_positioning": "",
            "wardrobe": (row.get("visual_direction") or "").strip(),
            "props": "", "color_palette": "",
        },
        "camera_setup": row.get("camera_setup") or "handheld",
    }
    await _execute(
        "UPDATE studio_projects SET hook_line = ?, "
        "duration_seconds = ?, location = ?, strategy = ?, "
        "script_version = script_version + 1, updated_at = ? "
        "WHERE id = ? AND user_id = ?",
        (
            hook.get("hook_line") or "",
            seconds, location or None,
            json.dumps(strategy), now_iso(), project_id, user_id,
        ),
    )
    return _public_project(
        await _fetch_one("SELECT * FROM studio_projects WHERE id = ?", (project_id,)),
        brand_name=(profile.get("brand_name") or "").strip(),
    )


@router.post("/hook-cta/projects/{project_id}/generate", status_code=202)
async def generate_hook_cta(
    project_id: str, payload: GenerateHookRequest,
    user_id: str = Depends(get_current_user_id),
    request: Request = None,
):
    """
    Render ONE hook as ONE job, through the only render path.

    The hook has no ready-marking gate: its readiness is the hook line
    itself — no line, no render — plus the same model, resolution and
    single-pass checks every submit makes. The hook submits at its own
    seconds (exact_duration: the hook-video clamp floors at 8 and
    would silently rewrite a 4-second hook), with the stored strategy
    rebound to the project's current words, so an edit made after the
    hook was written is what renders.
    """
    require_ai_configured()
    row = await _hook_cta_project_row(project_id, user_id)
    profile = await _require_profile_for_studio(row.get("brand_profile_id"), user_id)
    _refuse_retired_project_assets(row.get("assets"))

    if not (row.get("hook_line") or "").strip():
        raise HTTPException(
            status_code=409,
            detail="Generate the hook first — the render speaks its line.",
        )

    _assert_model_usable(payload.model or "")
    _assert_resolution_offered(payload.model or "", payload.resolution)

    seconds = int(payload.duration_seconds or row.get("duration_seconds") or 0)
    if seconds not in SHORT_HOOK_SECONDS:
        raise HTTPException(
            status_code=400,
            detail="A hook runs 4 or 5 seconds.",
        )
    _assert_within_single_pass_cap(
        video_providers.resolve(payload.model or None)[0], seconds)

    strategy = _project_strategy(row)
    if strategy:
        # Rebind the current words, the same discipline the wizard's
        # render applies: the strategy's sections carry the hook's
        # line, and a founder edit since must be what the render says.
        # The middle segment's script rebinds from the row too — always
        # empty on this page, so the closing beat stays direction only.
        segments = [dict(s) for s in (strategy.get("segments") or [])]
        for segment in segments:
            if segment.get("role") == "hook":
                segment["script"] = row.get("hook_line") or ""
            elif segment.get("role") == "middle":
                segment["script"] = row.get("script") or ""
        strategy = {**strategy, "segments": segments}
        scene = dict(strategy.get("scene") or {})
        if (row.get("location") or "").strip():
            scene["location"] = (row.get("location") or "").strip()
        strategy = {**strategy, "scene": scene}

    project = dict(row)
    project["duration_seconds"] = seconds
    generation = await _submit_generation(
        project=project,
        profile=profile,
        template={},
        user_id=user_id,
        model=payload.model or "",
        duration=seconds,
        segment_index=payload.segment_index,
        generate_audio=payload.generate_audio,
        resolution=payload.resolution,
        strategy=strategy or None,
        exact_duration=True,
        idempotency_key=payload.idempotency_key or "",
        request_id=(request.state.request_id if request is not None and getattr(request, "state", None) else "") or _request_id(),
    )
    generation["provider_reason"] = video_providers.resolve(payload.model or None)[1]
    return generation
