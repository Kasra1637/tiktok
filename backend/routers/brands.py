"""Brand profiles, content angles, and the hook template library.

One router owns every profile, angle, and template-library endpoint under
`/brand`, `/brands`, `/app-profiles`, and `/templates`. Routes are moved
verbatim from `server.py`; the wrapper is an `APIRouter` included under the
existing `/api` prefix.

Shared stateless deps (ai_service, template_library, video_providers,
angle_scene, final_beat, feedback, httpx, models, auth) import here directly.
DB helpers are injected once via `configure_brands`; the helpers tests patch
on `server` (`_fetch_active_brand`, `_fetch_url_text`, `_asset_dir`) are
resolved at call time through `_cfg` over the `_server` back-reference —
same mechanism as `db._server`/`db._cfg`. No import of server here, in
either direction: an unconfigured call fails loudly instead of
half-working. `server.py` re-exports the helpers so existing test and
caller imports keep working.
"""

import asyncio
import json
import logging
import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

import ai_service
import angle_scene
import final_beat
import template_library
import video_providers
import feedback as feedback_mod
from ai_service import (
    ANGLE_MODEL,
    TEXT_MODEL,
    analyze_app_profile,
    page_text_with_metadata,
    generate_angle_goals,
    generate_brand_templates,
    generate_content_angles,
)
from template_recommendations import (
    diversify_template_recommendations as _diversify_template_recommendations,
    score_template_for_angle as _score_template_for_angle,
    split_shared_notes as _split_shared_notes,
    filter_relevant_templates as _filter_relevant_templates,
    check_template_relevance as _check_template_relevance,
)
from auth import get_current_user_id
from models import (
    APP_PROFILE_EDITABLE_FIELDS,
    APP_PROFILE_LIST_FIELDS,
    AppProfileResearchRequest,
    ApproveAppProfileRequest,
    BrandProfileCreateRequest,
    BrandProfileUpdateRequest,
    CreateContentAngleRequest,
    GenerateContentAnglesRequest,
    ObjectiveTemplatesRequest,
    OpeningMessagesRequest,
    RefreshDirectionOptionsRequest,
    UpdateContentAngleRequest,
    now_iso,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_fetch_one = None
_fetch_all = None
_execute = None
_log_model_call = None
_server = None


def _cfg(name, default=None):
    """Read a live binding from the composition root.

    For the helpers tests patch on `server` (`_fetch_active_brand`,
    `_asset_dir`, `_fetch_url_text`), call-site resolution must see the
    CURRENT attribute, not the function captured at configure time. This
    mirrors db._server/_cfg exactly.
    """
    return getattr(_server, name, default) if _server is not None else default


def configure_brands(fetch_one, fetch_all, execute, log_model_call, server):
    """Inject the composition root's DB helpers. Called once at include time."""
    global _fetch_one, _fetch_all, _execute, _log_model_call, _server
    _fetch_one = fetch_one
    _fetch_all = fetch_all
    _execute = execute
    _log_model_call = log_model_call
    _server = server


def _require_configured():
    if _server is None:
        raise RuntimeError("brands router used before configure_brands ran")


def _require_ai_configured():
    """Fail loudly when the AI adapter is unconfigured."""
    import os
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise HTTPException(
            status_code=503,
            detail="AI features are not configured yet. Set the OPENROUTER_API_KEY environment "
                   "variable to enable hook analysis, face-swap generation, and video generation.",
        )


async def _require_profile_for_studio(profile_id: str, user_id: str) -> dict:
    """
    Load a profile and enforce that it is APPROVED.

    Every studio step funnels through here. Generating a script from an
    unreviewed profile would let unverified AI research invent features and
    claims, which is exactly what the approval gate exists to prevent.
    """
    _require_configured()
    profile = await _cfg("_fetch_one")(
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


async def _ensure_objective_templates(profile: dict, objective: str, user_id: str,
                                        angle: Optional[dict] = None) -> list:
    """
    Generate this profile's tailored templates for one selected objective and
    — when the wizard has one — one selected angle. Move-only; the body is
    identical to `server._ensure_objective_templates` (re-exported there).
    """
    _require_configured()
    profile_id = profile.get("id") or ""
    want_objective = template_library.normalize_objective(objective)
    if not profile_id or not want_objective:
        return []
    angle_id = str((angle or {}).get("id") or "")
    if angle_id:
        angles = [angle]
    else:
        angles = await _cfg("_fetch_all")(
            "SELECT * FROM content_angles WHERE brand_profile_id = ? AND user_id = ?",
            (profile_id, user_id),
        )
    try:
        # No component_feedback: template thumbs stopped steering
        # generation (ADR 0124) — the whole-video verdict is the only
        # feedback a prompt learns from now.
        drafts = await _cfg("_log_model_call")(
            "brand_templates", "text", TEXT_MODEL,
            lambda: _cfg("generate_brand_templates")(
                profile, angles, objective=want_objective, angle=angle),
            user_id,
            brand_profile_id=profile_id,
        )
    except Exception as e:
        logger.error(
            f"Brand template generation failed for profile {profile_id} "
            f"objective {want_objective} angle {angle_id or '-'}: {e!r}")
        return []
    drafts = _filter_relevant_templates(drafts, angle)
    if not drafts:
        return []
    now = now_iso()
    await _cfg("_execute")(
        "DELETE FROM hook_templates WHERE brand_profile_id = ? AND objective = ? "
        "AND user_id = ? AND COALESCE(angle_id, '') = ?",
        (profile_id, want_objective, user_id, angle_id),
    )
    for draft in drafts:
        await _cfg("_execute")(
            """INSERT INTO hook_templates
               (id, name, category, app_categories, audiences, objective,
                 opening_structure, hook_seconds, middle_structure,
                 visual_style, camera_pacing, required_assets,
                 default_duration, content_slots, evidence_note, outcome, version,
                 archived, is_favorite, origin, review_status, times_used,
                 brand_profile_id, angle_id, created_at, updated_at, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0,
                       'custom', 'approved', 0, ?, ?, ?, ?, ?)""",
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
              profile_id, angle_id or None, now, now, user_id),
        )
    logger.info(
        f"Generated {len(drafts)} brand templates for profile {profile_id} "
        f"objective {want_objective} angle {angle_id or '-'}")
    return drafts


# ---------------------------------------------------------------------------
# Pure helpers (no DB) — owned here; re-exported by server for existing callers.
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


def _cap_page_text(text: str, max_chars: int) -> str:
    """Cap page text while keeping the footer, not just the head.

    Audience positioning (who the app is for, conditions it names) often lives
    late on a page — FAQ, footer, "who it's for" sections. A blind head slice
    keeps the hero copy and drops exactly that. When over budget, keep the head
    plus a marked tail window instead.
    """
    text = text or ""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    tail_window = min(1500, max_chars // 4)
    head_window = max_chars - tail_window
    return text[:head_window] + "\n\n[... snipped for length ...]\n\n" + text[-tail_window:]


async def _fetch_url_text_owned(url: str, max_chars: int) -> str:
    """Fetch a public page and return cleaned text, capped at max_chars.

    Returns an empty string when the page cannot be fetched or yields no
    readable text — research across multiple sources must tolerate individual
    failures rather than aborting the whole run.
    """
    import httpx
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
            return _cap_page_text(page_text_with_metadata(resp.text), max_chars)
    except Exception as e:
        logger.warning(f"App research: could not fetch {url}: {e}")
        return ""


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


def _founder_verified_context(existing: dict) -> str:
    """Founder-verified positioning that re-research must not wipe.

    A founder who hand-adds "people with ADHD" and then hits regenerate
    used to watch the model rebuild from sources only and overwrite the edit
    — when the sources state it, the model now keeps it, but when the
    positioning lives only in the founder's edit there is nothing in the
    sources to keep. Passing the existing audience back as verified context
    makes regenerate/refresh incorporate it instead of erasing it.
    """
    parts = []
    notes = (existing.get("notes") or "").strip()
    if notes:
        parts.append(f"Founder notes: {notes}")
    audience = (existing.get("target_audience") or "").strip()
    if audience:
        parts.append(f"Founder-verified audience (do not drop): {audience}")
    icp = (existing.get("ideal_customer_profile") or "").strip()
    if icp:
        parts.append(f"Founder-verified customer: {icp}")
    segments = existing.get("icp_segments") or []
    if isinstance(segments, str):
        try:
            segments = json.loads(segments)
        except (json.JSONDecodeError, TypeError):
            segments = []
    segments = [str(s).strip() for s in (segments or []) if str(s).strip()]
    if segments:
        parts.append("Founder-verified segments (do not drop): " + " | ".join(segments[:6]))
    return "\n".join(parts)


def _serialize_angle_row(row: dict, evidence: Optional[dict] = None,
                         profile: Optional[dict] = None) -> dict:
    """Shape a content_angles row for the API (kind is already normalized).

    `evidence` is this kind's own verdict tally from
    `_angle_feedback_for_profile`. Counts only — never a rate or a score:
    a percentage over one verdict would present a coin flip as a measurement.
    Keyed by KIND, not by angle id, so the counts survive an angle
    regeneration that replaces every row id. `adoptions` rides beside the
    verdicts as momentum — projects the founder moved forward with on this
    kind — so the picker can show commitment without any score reading it.

    `profile` tailors the goal order: the same six curated goals, demoting
    ones the profile gives nothing to stand on (no named alternative, no
    recorded objection) instead of letting them lead the row.
    """
    # Stored angles written before screen-interaction stripping still
    # promise unfilmable scroll/chart openings. The serialized row is the
    # picker’s view, so strip the screen clause here rather than asking
    # the founder to discard an angle a rebuild already fixed elsewhere.
    # The same holds for a phone in hand (ADR 0097): rows stored before
    # the promise strip still name the device, so the picker would show a
    # promise the render refuses. Strip the phrase; a promise that was
    # nothing but the phone keeps its stored text here (the shape falls
    # back to the template opening) rather than blanking the angle row.
    _promise = str(row.get("hook_promise") or "")
    if _promise:
        _kept, _removed = final_beat.split_screen_clauses(_promise)
        if _removed and _kept:
            _promise = _kept
        _stripped = final_beat.strip_phone_phrases(_promise)
        if _stripped:
            _promise = _stripped
    return {
        "id": row.get("id"),
        "brand_profile_id": row.get("brand_profile_id"),
        "kind": row.get("kind"),
        "label": row.get("label") or "",
        "target_audience": row.get("target_audience") or "",
        "user_problem": row.get("user_problem") or "",
        "hook_promise": _promise,
        "app_feature": row.get("app_feature") or "",
        "desired_emotion": row.get("desired_emotion") or "",
        "viewer_outcome": row.get("viewer_outcome") or "",
        "claims_to_respect": row.get("claims_to_respect") or [],
        "rank": row.get("rank") or 0,
        "goal_variant": int(row.get("goal_variant") or 0),
        "origin": row.get("origin") or "generated",
        # The six suggestions in THIS row's saved variant order, tailored to
        # the profile and computed server-side so every consumer (wizard,
        # review recovery) agrees without each client re-deriving it.
        "goal_suggestions": template_library.goal_suggestions_for_profile(
            row.get("kind"), profile, int(row.get("goal_variant") or 0)
        ),
        "created_at": row.get("created_at"),
        "evidence": evidence or {"wins": 0, "flops": 0, "adoptions": 0,
                                   "posted": 0, "views": 0},
    }


def _public_template(template: dict) -> dict:
    """Remove storage-only thumbnail bytes before serializing a template."""
    public_template = dict(template)
    public_template.pop("thumbnail_bytes", None)
    return public_template


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


async def _fetch_one_source(label: str, url: str, cap: int) -> tuple[str, str]:
    """One labeled fetch that never raises: _fetch_url_text already swallows
    fetch failures into "", and this guards the gather itself."""
    try:
        return label, await _cfg("_fetch_url_text")(url, cap)
    except Exception as e:
        logger.warning(f"App research: source {label} ({url}) failed outside the fetcher: {e}")
        return label, ""


# ---------------------------------------------------------------------------
# DB-touching helpers (owned here; injected by server, re-exported by server)
# ---------------------------------------------------------------------------
async def _angle_feedback_for_profile(brand_profile_id: str, user_id: str) -> dict:
    """
    Goal thumbs attributed to the angle kind and objective the founder picked,
    plus posted-performance from linked TikTok clips on this app's renders.

    A goal verdict names its project, so attribution walks project -> angle
    kind + objective. Verdicts on templates, plans and scripts are filtered
    out by the summarizer and never steer goal generation. Posted clips walk
    the other way: generation -> project -> angle kind + objective. Only
    renders with a TikTok link count — an unposted render is commitment,
    not audience evidence.
    """
    _require_configured()
    rows = await _cfg("_fetch_all")(
        """SELECT ca.kind AS kind, sp.objective AS objective, f.event AS event,
                  f.step AS step, f.detail AS detail, f.created_at AS created_at
           FROM feedback_events f
           LEFT JOIN studio_projects sp ON sp.id = f.studio_project_id
           LEFT JOIN content_angles ca ON ca.id = sp.content_angle_id
           WHERE f.brand_profile_id = ? AND f.user_id = ?
             AND f.event IN ('thumb_up', 'thumb_down', 'adopted', 'abandoned')
           ORDER BY f.created_at DESC LIMIT 200""",
        (brand_profile_id, user_id),
    )
    posted = await _cfg("_fetch_all")(
        """SELECT ca.kind AS kind, sp.objective AS objective,
                  g.tiktok_views AS views, g.tiktok_views_at AS at
           FROM generations g
           LEFT JOIN studio_projects sp ON sp.id = g.studio_project_id
           LEFT JOIN content_angles ca ON ca.id = sp.content_angle_id
           WHERE g.brand_profile_id = ? AND g.user_id = ?
             AND g.tiktok_url IS NOT NULL AND TRIM(g.tiktok_url) != ''
           ORDER BY g.tiktok_views_at DESC LIMIT 200""",
        (brand_profile_id, user_id),
    )
    return feedback_mod.summarize_angle_feedback(rows, posted_rows=posted)


async def _verdict_rows_for_profile(brand_profile_id: str, user_id: str) -> list:
    """This profile's whole-video verdict rows, bundles parsed (ADR 0124).

    The one read behind every verdict surface: verdict rows joined to
    their generations' profile, newest first, each carrying the bundle
    frozen when the verdict was cast. Defensive by design — a read
    failure or an unparseable bundle yields an empty/partial list
    rather than failing the surface the founder asked for, because
    every consumer treats "no rows" as "no signal yet".
    """
    try:
        rows = await _cfg("_fetch_all")(
            "SELECT vv.verdict AS verdict, vv.bundle AS bundle "
            "FROM video_verdicts vv "
            "JOIN generations g ON g.id = vv.generation_id "
            "WHERE g.brand_profile_id = ? AND vv.user_id = ? "
            "ORDER BY vv.updated_at DESC LIMIT 200",
            (brand_profile_id, user_id),
        )
    except Exception:
        rows = []
    parsed = []
    for row in rows or []:
        bundle = row.get("bundle")
        if isinstance(bundle, str):
            try:
                bundle = json.loads(bundle)
            except (TypeError, ValueError):
                bundle = None
        parsed.append({"verdict": row.get("verdict"),
                       "bundle": bundle if isinstance(bundle, dict) else {}})
    return parsed


async def _verdict_objective_evidence(brand_profile_id: str, user_id: str) -> dict:
    """Whole-video verdicts tallied per objective for this profile (ADR 0126).

    The ADR 0124 signal, read for display beside the goal picker: each
    verdict's frozen bundle names the objective its video was made for,
    so the tally speaks for the goal itself and survives later project
    edits — unlike the goal-thumb record above, which attributes by the
    project's CURRENT objective. The read mirrors the studio steering
    read (same join, same defensive bundle parsing) and is pure: it
    never generates anything (ADR 0122), and a read failure yields an
    empty map rather than failing the list the founder asked for.
    """
    parsed = await _verdict_rows_for_profile(brand_profile_id, user_id)
    return feedback_mod.verdict_objective_evidence(parsed)


async def _component_feedback_for_profile_owned(
    brand_profile_id: str, user_id: str, component: str
) -> dict:
    """One component's thumbs for this app, as {component: {up, down, total}}."""
    _require_configured()
    rows = await _cfg("_fetch_all")(
        "SELECT event, step FROM feedback_events"
        " WHERE brand_profile_id = ? AND user_id = ?"
        " AND event IN ('thumb_up', 'thumb_down', 'adopted', 'abandoned', 'generated')"
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
    _require_configured()
    ids = [g for g in (generation_ids or []) if g]
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = await _cfg("_fetch_all")(
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
    _require_configured()
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
    skipped_support = (stored_support or [])[APP_RESEARCH_MAX_SUPPORT_URLS:]
    if skipped_support:
        logger.warning(
            "App research ignoring %d support URL(s) past the cap of %d: %s",
            len(skipped_support), APP_RESEARCH_MAX_SUPPORT_URLS,
            ", ".join(skipped_support),
        )
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
    for u in skipped_support:
        report.append({"label": f"skipped (over cap): {u}", "url": u,
                       "chars": 0, "ok": False, "skipped": True})
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


async def _serialize_profile_angles(profile_id: str, user_id: str) -> dict:
    """Re-read this profile's angles and shape the audience-step payload.

    The same shape as GET /content-angles: serialized rows (kind evidence
    plus each row's goal suggestions in its saved variant order), the
    profile-wide objective_evidence map, and the whole-video verdict
    tally per objective (verdict_objective_evidence, ADR 0126).
    POST generate/regenerate return
    this instead of the raw model rows, so the wizard never adopts a row
    shape the list endpoint would not serve — the old raw return dropped
    goal_suggestions (the goal picker silently fell back to the static
    order), evidence (verdict chips vanished), and objective_evidence
    (goal chips vanished) until the next reload.
    """
    _require_configured()
    rows = await _cfg("_fetch_all")(
        "SELECT * FROM content_angles WHERE brand_profile_id = ? AND user_id = ? "
        "ORDER BY rank ASC, created_at ASC",
        (profile_id, user_id),
    )
    profile = await _cfg("_fetch_one")(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    verdicts = await _angle_feedback_for_profile(profile_id, user_id)
    by_kind = {
        str(entry.get("name") or ""): {"wins": int(entry.get("wins") or 0), "flops": int(entry.get("flops") or 0),
                                            "adoptions": int(entry.get("adoptions") or 0),
                                            "posted": int(entry.get("posted") or 0),
                                            "views": int(entry.get("views") or 0)}
        for entry in (verdicts.get("kinds") or [])
    }
    objective_evidence = {
        str(entry.get("name") or ""): {"wins": int(entry.get("wins") or 0), "flops": int(entry.get("flops") or 0),
                                            "adoptions": int(entry.get("adoptions") or 0),
                                            "posted": int(entry.get("posted") or 0),
                                            "views": int(entry.get("views") or 0)}
        for entry in (verdicts.get("objectives") or [])
    }
    # The intersection axis: kind × objective, keyed "kind‖objective". The
    # goal card knows both (its goal + the selected angle's kind), so it can
    # name the most specific evidence available — a proven pairing — without
    # the card re-deriving anything.
    pair_evidence = {
        f"{entry.get('kind') or ''}‖{entry.get('objective') or ''}":
            {"wins": int(entry.get("wins") or 0), "flops": int(entry.get("flops") or 0),
             "adoptions": int(entry.get("adoptions") or 0),
             "posted": int(entry.get("posted") or 0),
             "views": int(entry.get("views") or 0)}
        for entry in (verdicts.get("pairs") or [])
        if entry.get("kind") and entry.get("objective")
    }
    return {
        "angles": [
            _serialize_angle_row(r, by_kind.get(str(r.get("kind") or "")), profile)
            for r in rows
        ],
        "objective_evidence": objective_evidence,
        "pair_evidence": pair_evidence,
        # The live whole-video verdict axis (ADR 0124/0126), keyed by
        # objective like objective_evidence but tallied from the frozen
        # verdict bundles — the goal card shows it beside the record axes.
        "verdict_objective_evidence": await _verdict_objective_evidence(profile_id, user_id),
    }


async def _generations_table_exists() -> bool:
    """Whether the Phase 7 `generations` table has been created yet.

    Lets usage history degrade to an empty list before that phase lands
    instead of erroring on every template detail request.
    """
    _require_configured()
    row = await _cfg("_fetch_one")(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'generations'"
    )
    return row is not None


async def _with_favorites(rows: list, user_id: str) -> list:
    """Overlay this user's favorite state onto template rows.

    The stored is_favorite column is only meaningful for an operator's own
    template; shared curated rows are favorited via template_favorites.
    """
    _require_configured()
    ids = [r["id"] for r in rows if r.get("id")]
    favorited = set()
    if ids:
        placeholders = ",".join("?" for _ in ids)
        favs = await _cfg("_fetch_all")(
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


async def _auto_generate_content_angles(profile: dict, user_id: str) -> None:
    """
    Best-effort content angle generation after a profile is approved.

    Awaited inline by the caller, but failures never block the response:
    angles are derived data — if generation fails the founder can still use
    the profile and regenerate later (or fill the section from its own
    Generate button; the listing itself never generates, ADR 0122).
    """
    _require_configured()
    try:
        # No angle_feedback: goal thumbs stopped steering generation
        # (ADR 0124). The summary still exists as the founder's record —
        # it just no longer teaches the angle writer.
        angles = await _cfg("_log_model_call")(
            "content_angles", "text", ANGLE_MODEL,
            lambda: _cfg("generate_content_angles")(profile),
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

    await _cfg("_execute")("DELETE FROM content_angles WHERE brand_profile_id = ?", (profile.get("id"),))
    now = now_iso()
    for rank, angle in enumerate(angles):
        angle_id = str(uuid.uuid4())
        await _cfg("_execute")(
            """INSERT INTO content_angles
               (id, brand_profile_id, kind, label, target_audience, user_problem,
                 hook_promise, app_feature, desired_emotion, viewer_outcome,
                 claims_to_respect, rank, created_at, user_id, origin)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'generated')""",
            (angle_id, profile.get("id"), angle["kind"], angle["label"],
             angle["target_audience"], angle["user_problem"], angle["hook_promise"],
             angle["app_feature"], angle["desired_emotion"],
             angle.get("viewer_outcome") or "",
             json.dumps(angle["claims_to_respect"]), rank, now, user_id),
        )
    logger.info(f"Auto-generated %d content angle(s) for profile {profile.get('id')}", len(angles))


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
BRAND_URL_TEXT_MAX_CHARS = 8000

# `recommended_cta` was here and is now gone: an angle describes the hook and
# the middle, and neither has a closing beat. The `recommended_cta TEXT` column
# survives in the schema for rows written before this and is neither written
# nor read.
CONTENT_ANGLE_TEXT_FIELDS = (
    "label", "target_audience", "user_problem", "hook_promise",
    "app_feature", "desired_emotion", "viewer_outcome",
)


@router.post("/brand", status_code=201)
async def create_brand(payload: BrandProfileCreateRequest, user_id: str = Depends(get_current_user_id)):
    """
    Create a brand profile from manually entered fields.

    Deliberately does NOT require the URL-analysis step (or an AI key): a user
    with no website, or whose site can't be fetched, must still be able to set
    up a brand profile by hand.
    """
    _require_configured()
    name = (payload.brand_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Brand name is required.")

    website = (payload.website_url or "").strip()
    if website and not website.lower().startswith(("http://", "https://")):
        website = f"https://{website}"

    brand_id = str(uuid.uuid4())
    created_at = now_iso()
    await _cfg("_execute")(
        """INSERT INTO brand_profiles
           (id, website_url, brand_name, brand_description, niche,
             target_audience, ideal_customer_profile, differentiation, tone_voice,
             raw_extracted_text, created_at, updated_at, user_id,
             appstore_url, play_url, support_urls, notes, app_category, platforms,
             core_features, primary_use_cases, problems_solved,
             icp_segments, desired_outcomes, known_limitations,
             must_not_show, usage_moments, proof_moment, viewer_objections,
             outcome_statements,
             status, version)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
         "draft", 1),
    )
    logger.info(f"Created brand profile {brand_id} ('{name}') from manual entry")
    return await _cfg("_fetch_one")("SELECT * FROM brand_profiles WHERE id = ?", (brand_id,))


@router.get("/brands")
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
    _require_configured()
    rows = await _cfg("_fetch_all")(
        "SELECT id, brand_name, website_url, niche, updated_at, created_at "
        "FROM brand_profiles WHERE user_id = ? "
        "ORDER BY updated_at DESC, created_at DESC",
        (user_id,),
    )
    return {"brands": rows or []}


@router.get("/brand/active")
async def get_active_brand(user_id: str = Depends(get_current_user_id)):
    _require_configured()
    row = await _cfg("_fetch_one")(
        "SELECT * FROM brand_profiles WHERE user_id = ? ORDER BY updated_at DESC, created_at DESC LIMIT 1",
        (user_id,)
    )
    if not row:
        raise HTTPException(status_code=404, detail="No brand profile found. Set one up first.")
    return row


@router.get("/brand/{brand_id}")
async def get_brand(brand_id: str, user_id: str = Depends(get_current_user_id)):
    # Scoped to the caller. This endpoint predates the App Profile routes and
    # used to look the row up by id alone, which let any authenticated user read
    # (or, via the PATCH below, rewrite) someone else's profile -- including the
    # scraped raw_extracted_text. A miss is a 404 rather than a 403 so a
    # stranger cannot probe for which profile ids exist.
    _require_configured()
    brand = await _cfg("_fetch_one")(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (brand_id, user_id)
    )
    if not brand:
        raise HTTPException(status_code=404, detail="Brand profile not found")
    return brand


@router.patch("/brand/{brand_id}")
async def update_brand(brand_id: str, payload: BrandProfileUpdateRequest, user_id: str = Depends(get_current_user_id)):
    # Scoped to the caller for the same reason as the GET above: an id-only
    # lookup let one user edit another user's profile. Both the read and the
    # UPDATE carry the predicate so the write can never land on a row the caller
    # does not own.
    _require_configured()
    existing = await _cfg("_fetch_one")(
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

    await _cfg("_execute")(
        f"UPDATE brand_profiles SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?",
        tuple(values) + (brand_id, user_id),
    )
    return await _cfg("_fetch_one")(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (brand_id, user_id)
    )


@router.post("/app-profiles/research", status_code=201)
async def research_app_profile(payload: AppProfileResearchRequest, user_id: str = Depends(get_current_user_id)):
    """Research a mobile app from its public pages and draft an App Profile.

    Fetches the website, App Store and Google Play pages plus up to 5 support
    URLs, then asks OpenRouter to draft the full profile. The result is stored
    as status='draft' — the founder must review and approve it (POST
    /app-profiles/{id}/approve) before it drives video generation.
    """
    _require_configured()
    _require_ai_configured()
    website = _normalize_url(payload.website_url or "")
    appstore = _normalize_url(payload.appstore_url or "")
    play = _normalize_url(payload.play_url or "")
    support: list = []
    for u in payload.support_urls or []:
        n = _normalize_url(u)
        if n and n not in support:
            support.append(n)
    skipped_support = support[APP_RESEARCH_MAX_SUPPORT_URLS:]
    support = support[:APP_RESEARCH_MAX_SUPPORT_URLS]
    if skipped_support:
        logger.warning(
            "App research ignoring %d support URL(s) past the cap of %d: %s",
            len(skipped_support), APP_RESEARCH_MAX_SUPPORT_URLS,
            ", ".join(skipped_support),
        )
    if not (website or appstore or play):
        raise HTTPException(
            status_code=400,
            detail="Provide your app's website, App Store URL, Google Play URL, or a combination.",
        )

    sources: dict = {}
    # What was asked for, and what actually came back. A source can fail --
    # a store listing behind a bot check, a support page that 404s -- and the
    # only all-failed case raises. research_sources used to record every
    # SUPPLIED url, so a profile built from one of five sources claimed five,
    # and a founder reading the list had no way to know the rest were empty.
    requested_sources: list = []
    source_failures: list = []
    if website:
        requested_sources.append("website")
        sources["website"] = await _cfg("_fetch_url_text")(website, APP_RESEARCH_CAPS["website"])
    if appstore:
        requested_sources.append("app_store")
        sources["app_store"] = await _cfg("_fetch_url_text")(appstore, APP_RESEARCH_CAPS["app_store"])
    if play:
        requested_sources.append("google_play")
        sources["google_play"] = await _cfg("_fetch_url_text")(play, APP_RESEARCH_CAPS["google_play"])
    for i, u in enumerate(support):
        label = f"support_{i + 1} ({u})"
        requested_sources.append(label)
        sources[label] = await _cfg("_fetch_url_text")(u, APP_RESEARCH_CAPS["support"])
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
        profile = await _cfg("_log_model_call")(
            "app_profile_research", "text", TEXT_MODEL,
            # Only the sources that returned text. Passing the full dict handed
            # the model empty entries labelled as sources, which invites it to
            # write as though it had read a page it never saw.
            lambda: _cfg("analyze_app_profile")(read_sources, payload.notes or ""),
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
    await _cfg("_execute")(
        """INSERT INTO brand_profiles
           (id, website_url, brand_name, brand_description, niche,
             target_audience, ideal_customer_profile, differentiation, tone_voice,
             raw_extracted_text, created_at, updated_at, user_id,
             appstore_url, play_url, support_urls, notes, app_category, platforms,
             core_features, primary_use_cases, problems_solved,
             icp_segments, desired_outcomes, known_limitations,
             must_not_show, usage_moments, proof_moment, viewer_objections,
             outcome_statements,
             status, version, last_research_at, research_sources)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (brand_id, website or None, profile.get("brand_name") or "Untitled app",

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
         # Only the sources that actually returned text. `combined_raw` above is
    # already built from the same set, so the recorded list and the text the
    # model saw now agree.
    "draft", 1, now, json.dumps(sorted(read_sources))),
    )
    logger.info(
        "Researched app profile %s from %d of %d requested source(s)",
        brand_id, len(read_sources), len(requested_sources),
    )
    return await _cfg("_fetch_one")("SELECT * FROM brand_profiles WHERE id = ?", (brand_id,))


@router.get("/app-profiles")
async def list_app_profiles(user_id: str = Depends(get_current_user_id)):
    """All App Profiles for this user, most recently active first.

    Trimmed projection for pickers — excludes raw page text and the pending
    refresh proposal, which live on the detail endpoint.
    """
    _require_configured()
    rows = await _cfg("_fetch_all")(
        "SELECT id, brand_name, website_url, appstore_url, play_url, niche, "
        "app_category, status, version, approved_at, updated_at, created_at "
        "FROM brand_profiles WHERE user_id = ? "
        "ORDER BY updated_at DESC, created_at DESC",
        (user_id,),
    )
    return {"profiles": rows or []}


@router.post("/demo-cta/opening-messages")
async def generate_opening_messages(
    payload: OpeningMessagesRequest, user_id: str = Depends(get_current_user_id)
):
    _require_configured()
    profile = (
        await _cfg("_fetch_one")("SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?",
                         (payload.profile_id, user_id))
        if payload.profile_id else await _cfg("_fetch_active_brand")(user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Choose or research an App Profile before generating opening text.")
    if profile.get("status") != "approved":
        raise HTTPException(status_code=409, detail="Approve this App Profile before generating opening text.")
    if not ai_service.OPENROUTER_API_KEY:
        raise HTTPException(status_code=503, detail="Opening text needs the server's OpenRouter API key. Configure OPENROUTER_API_KEY and restart the backend, then try Surprise me again.")
    try:
        messages = await _cfg("_log_model_call")(
            "opening_messages", "text", TEXT_MODEL,
            lambda: ai_service.generate_opening_messages(profile, payload.previous),
            user_id, brand_profile_id=profile["id"],
        )
    except Exception as e:
        logger.warning("Opening message generation failed: %s", e)
        raise HTTPException(status_code=502, detail="Could not generate fresh opening text. Try Surprise me again.")
    return {"messages": messages}


@router.get("/app-profiles/{profile_id}")
async def get_app_profile(profile_id: str, user_id: str = Depends(get_current_user_id)):
    _require_configured()
    profile = await _cfg("_fetch_one")(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")
    return profile


@router.patch("/app-profiles/{profile_id}")
async def update_app_profile(
    profile_id: str, payload: BrandProfileUpdateRequest, user_id: str = Depends(get_current_user_id)
):
    """Edit any App Profile field. Editing never changes approval status — a
    founder re-approves explicitly via the approve endpoint."""
    _require_configured()
    existing = await _cfg("_fetch_one")(
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
    await _cfg("_execute")(
        f"UPDATE brand_profiles SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?",
        tuple(values) + (user_id,),
    )
    return await _cfg("_fetch_one")(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )


@router.post("/app-profiles/{profile_id}/approve")
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
    _require_configured()
    existing = await _cfg("_fetch_one")(
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
            await _cfg("_execute")(
                f"UPDATE brand_profiles SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?",
                tuple(values) + (user_id,),
            )
            logger.info(f"Approved App Profile {profile_id} (version {(existing.get('version') or 1) + 1})")
            approved_profile = await _cfg("_fetch_one")(
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
    await _cfg("_execute")(
        "UPDATE brand_profiles SET status = 'approved', approved_at = ?, updated_at = ? "
        "WHERE id = ? AND user_id = ?",
        (now, now, profile_id, user_id),
    )
    logger.info(f"Approved App Profile {profile_id} (draft as-is, version {existing.get('version') or 1})")
    approved_profile = await _cfg("_fetch_one")(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    await _auto_generate_content_angles(approved_profile, user_id)
    return approved_profile


@router.post("/app-profiles/{profile_id}/regenerate-everything", status_code=201)
async def regenerate_everything(profile_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Regenerate everything for an App Profile: re-research, re-approve, regenerate angles.

    This is the single "regenerate everything" action. It:
    1. Re-runs research from the profile's URLs
    2. Applies the fresh research (bumps version, clears pending)
    3. Auto-generates content angles from the updated profile

    Replaces the need for per-section regenerate buttons.
    """
    _require_configured()
    _require_ai_configured()
    existing = await _cfg("_fetch_one")(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="App Profile not found")

    # Step 1: Re-research from the same sources a refresh would read.
    sources, report = await _research_profile_sources(existing)

    try:
        proposal = await _cfg("_log_model_call")(
            "app_profile_refresh", "text", TEXT_MODEL,
            lambda: _cfg("analyze_app_profile")(sources, _founder_verified_context(existing)),
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
        await _cfg("_execute")(
            f"UPDATE brand_profiles SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?",
            tuple(values) + (user_id,),
        )
    else:
        # Still bump version and refresh timestamps even if no fields changed
        await _cfg("_execute")(
            "UPDATE brand_profiles SET version = ?, approved_at = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            ((existing.get("version") or 1) + 1, now, now, profile_id, user_id),
        )

    # Step 3: Auto-generate content angles from the updated profile
    updated_profile = await _cfg("_fetch_one")(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    await _auto_generate_content_angles(updated_profile, user_id)

    logger.info(f"Regenerated everything for App Profile {profile_id}")
    updated_profile["research_sources"] = report
    return updated_profile


@router.post("/app-profiles/{profile_id}/refresh")
async def refresh_app_profile(profile_id: str, user_id: str = Depends(get_current_user_id)):
    """Re-research an App Profile from its stored URLs without touching live fields.

    The fresh analysis is stored as pending_research for founder review — the
    approved profile stays exactly as it was until approve applies it.
    """
    _require_configured()
    _require_ai_configured()
    existing = await _cfg("_fetch_one")(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not existing:
        raise HTTPException(status_code=404, detail="App Profile not found")

    sources, report = await _research_profile_sources(existing)

    try:
        proposal = await _cfg("_log_model_call")(
            "app_profile_refresh", "text", TEXT_MODEL,
            lambda: _cfg("analyze_app_profile")(sources, _founder_verified_context(existing)),
            user_id,
            brand_profile_id=profile_id,
        )
    except Exception as e:
        logger.error(f"App refresh failed for {profile_id}: {e}")
        raise HTTPException(status_code=502, detail=f"AI app research failed. Please try again. ({str(e)[:150]})")

    now = now_iso()
    await _cfg("_execute")(
        "UPDATE brand_profiles SET pending_research = ?, last_research_at = ?, updated_at = ? "
        "WHERE id = ? AND user_id = ?",
        (json.dumps(proposal), now, now, profile_id, user_id),
    )
    logger.info(f"Refreshed app profile {profile_id} into pending review")
    refreshed = await _cfg("_fetch_one")(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    refreshed["research_sources"] = report
    return refreshed


@router.get("/app-profiles/{profile_id}/content-angles")
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
    _require_configured()
    profile = await _cfg("_fetch_one")(
        "SELECT id, status FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")
    # A pure read (ADR 0122): the listing returns the rows that are stored
    # and never generates. An approved profile with zero angles — approved
    # before auto-generation existed, or its approval-time generation
    # returned nothing — lists empty here, and the angle section's own
    # Generate click is what fills it. Before 0122 this handler backfilled
    # that case itself, so opening the wizard, picking the profile or
    # following a deep link spent a model call nobody asked for.
    #
    # One summary for the whole profile, indexed by kind and shared by every
    # angle of that kind -- two angles of the same kind carry the same counts,
    # which is honest (the attribution is per kind) and is never presented as
    # belonging to one specific angle. Serialized through the shared helper
    # so the list and the generate/regenerate responses can never drift
    # apart in shape again.
    return await _serialize_profile_angles(profile_id, user_id)


@router.delete("/app-profiles/{profile_id}")
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
    _require_configured()
    row = await _cfg("_fetch_one")(
        "SELECT id FROM brand_profiles WHERE id = ? AND user_id = ?",
        (profile_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="App Profile not found")

    in_flight = await _cfg("_fetch_one")(
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
        for r in await _cfg("_fetch_all")(
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
        await _cfg("_execute")(f"DELETE FROM {table} WHERE brand_profile_id = ?", (profile_id,))
    await _cfg("_execute")(
        "DELETE FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )

    # Best-effort file cleanup. A leaked file must never fail the delete.
    shutil.rmtree(_cfg("_asset_dir")(profile_id), ignore_errors=True)
    for gen_id in gen_ids:
        try:
            (pipeline.STORAGE_DIR / "videos" / f"{gen_id}.mp4").unlink(missing_ok=True)
        except OSError as e:
            logger.warning(f"Could not remove cached video for generation {gen_id}: {e}")

    logger.info(f"Deleted App Profile {profile_id} ({len(gen_ids)} generation(s) removed)")
    return {"deleted": True, "id": profile_id, "generations_removed": len(gen_ids)}


import pipeline


@router.post("/app-profiles/{profile_id}/content-angles", status_code=201)
async def generate_profile_content_angles(profile_id: str, payload: Optional[GenerateContentAnglesRequest] = None, user_id: str = Depends(get_current_user_id)):
    """
    Generate content angles from an APPROVED App Profile.

    Requires approval deliberately: angles are derived from the profile's
    verified facts, so generating them from an unreviewed draft would let
    unverified research steer the video plan. Regenerating replaces the
    existing set (they are derived data, not founder-authored content).
    An optional objective aims the set at the video already chosen.
    """
    _require_configured()
    _require_ai_configured()
    profile = await _cfg("_fetch_one")(
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
        objective = ((payload.objective if payload else "") or "").strip()
        angles = await _cfg("_log_model_call")(
            "content_angles", "text", ANGLE_MODEL,
            lambda: _cfg("generate_content_angles")(profile, objective=objective),
            user_id,
            brand_profile_id=profile_id,
        )
    except Exception as e:
        logger.error(f"Content angle generation failed for profile {profile_id}: {e}")
        raise HTTPException(status_code=502, detail=f"AI content angle generation failed. Please try again. ({str(e)[:150]})")

    await _cfg("_execute")("DELETE FROM content_angles WHERE brand_profile_id = ?", (profile_id,))
    now = now_iso()
    for rank, angle in enumerate(angles):
        angle_id = str(uuid.uuid4())
        await _cfg("_execute")(
            """INSERT INTO content_angles
               (id, brand_profile_id, kind, label, target_audience, user_problem,
                 hook_promise, app_feature, desired_emotion, viewer_outcome,
                 claims_to_respect, rank, created_at, user_id, origin)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'generated')""",
            (angle_id, profile_id, angle["kind"], angle["label"],
             angle["target_audience"], angle["user_problem"], angle["hook_promise"],
             angle["app_feature"], angle["desired_emotion"],
             angle.get("viewer_outcome") or "",
             json.dumps(angle["claims_to_respect"]), rank, now, user_id),
        )
    # Re-read, never echo the model rows: the wizard adopts this response
    # into the same state the list endpoint feeds, so it must carry the
    # serialized shape (goal suggestions, evidence, origin) or the goal
    # picker and verdict chips degrade until the next reload.
    payload = await _serialize_profile_angles(profile_id, user_id)
    logger.info(f"Generated %d content angle(s) for profile {profile_id}", len(payload["angles"]))
    return payload


@router.post("/app-profiles/{profile_id}/content-angles/manual", status_code=201)
async def create_manual_content_angle(
    profile_id: str, payload: CreateContentAngleRequest, user_id: str = Depends(get_current_user_id)
):
    """Add one hand-written content angle. Founder-authored, never overwritten
    by a regeneration pass (regeneration only replaces AI-generated rows)."""
    _require_configured()
    profile = await _cfg("_fetch_one")(
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

    cursor = await _cfg("_fetch_one")(
        "SELECT COALESCE(MAX(rank), -1) AS max_rank FROM content_angles WHERE brand_profile_id = ?",
        (profile_id,),
    )
    rank = int((cursor or {}).get("max_rank") or -1) + 1
    angle_id = str(uuid.uuid4())
    now = now_iso()
    claims = _normalize_str_list(payload.claims_to_respect)
    await _cfg("_execute")(
        """INSERT INTO content_angles
           (id, brand_profile_id, kind, label, target_audience, user_problem,
             hook_promise, app_feature, desired_emotion, viewer_outcome,
             claims_to_respect, rank, created_at, user_id, origin)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual')""",
        (angle_id, profile_id, template_library.normalize_angle_kind(payload.kind), label,
         (payload.target_audience or "").strip(), (payload.user_problem or "").strip(),
         (payload.hook_promise or "").strip(), (payload.app_feature or "").strip(),
         (payload.desired_emotion or "").strip(),
         (payload.viewer_outcome or "").strip(),
         json.dumps(claims), rank, now, user_id),
    )
    row = await _cfg("_fetch_one")("SELECT * FROM content_angles WHERE id = ?", (angle_id,))
    return _serialize_angle_row(row)


@router.patch("/app-profiles/{profile_id}/content-angles/{angle_id}")
async def update_content_angle(
    profile_id: str, angle_id: str, payload: UpdateContentAngleRequest, user_id: str = Depends(get_current_user_id)
):
    _require_configured()
    row = await _cfg("_fetch_one")(
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
    await _cfg("_execute")(
        f"UPDATE content_angles SET {', '.join(set_clauses)} WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
        tuple(values),
    )
    return _serialize_angle_row(
        await _cfg("_fetch_one")("SELECT * FROM content_angles WHERE id = ?", (angle_id,))
    )


@router.post("/app-profiles/{profile_id}/content-angles/regenerate")
async def regenerate_content_angles(profile_id: str, payload: Optional[GenerateContentAnglesRequest] = None, user_id: str = Depends(get_current_user_id)):
    """
    Regenerate the AI-derived audience angles for an APPROVED App Profile.

    An optional objective aims the fresh set at the video already chosen.

    Same generate-then-replace flow as POST /content-angles, with one
    deliberate difference: hand-written angles survive. Rows tagged
    origin='manual' are founder-authored content, not derived data — the
    model writes nothing like them, and a regen the founder asked for must
    not delete writing they did. Generate runs BEFORE any delete, so a
    model failure leaves the previous set (generated and manual alike)
    fully intact.
    """
    _require_configured()
    _require_ai_configured()
    profile = await _cfg("_fetch_one")(
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
        objective = ((payload.objective if payload else "") or "").strip()
        angles = await _cfg("_log_model_call")(
            "content_angles", "text", ANGLE_MODEL,
            lambda: _cfg("generate_content_angles")(profile, objective=objective),
            user_id,
            brand_profile_id=profile_id,
        )
    except Exception as e:
        logger.error(f"Content angle regeneration failed for profile {profile_id}: {e}")
        raise HTTPException(status_code=502, detail=f"AI content angle generation failed. Please try again. ({str(e)[:150]})")

    # Manual rows first -- their ids are needed after the replacement set is
    # written. Nothing is deleted yet.
    manual_rows = await _cfg("_fetch_all")(
        "SELECT * FROM content_angles WHERE brand_profile_id = ? AND user_id = ? AND origin = 'manual' "
        "ORDER BY rank ASC, created_at ASC",
        (profile_id, user_id),
    )

    # Projects referencing the derived angles about to be removed keep their
    # row (LEFT JOIN degrades to a null angle later) but lose the story they
    # were built around. Counting them BEFORE the delete turns that quiet
    # break into a number the founder can be told about.
    affected = await _cfg("_fetch_one")(
        "SELECT COUNT(*) AS n FROM studio_projects WHERE brand_profile_id = ? AND user_id = ? "
        "AND content_angle_id IN (SELECT id FROM content_angles WHERE brand_profile_id = ? "
        "AND (origin IS NULL OR origin != 'manual'))",
        (profile_id, user_id, profile_id),
    )
    projects_affected = int((affected or {}).get("n") or 0)

    # The guarded delete: only derived rows are replaced. A manual row can
    # still be removed through the ordinary DELETE endpoint, by its founder.
    await _cfg("_execute")(
        "DELETE FROM content_angles WHERE brand_profile_id = ? AND (origin IS NULL OR origin != 'manual')",
        (profile_id,),
    )
    now = now_iso()
    for rank, angle in enumerate(angles):
        angle_id = str(uuid.uuid4())
        await _cfg("_execute")(
            """INSERT INTO content_angles
               (id, brand_profile_id, kind, label, target_audience, user_problem,
                 hook_promise, app_feature, desired_emotion, viewer_outcome,
                 claims_to_respect, rank, created_at, user_id, origin)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'generated')""",
            (angle_id, profile_id, angle["kind"], angle["label"],
             angle["target_audience"], angle["user_problem"], angle["hook_promise"],
             angle["app_feature"], angle["desired_emotion"],
             angle.get("viewer_outcome") or "",
             json.dumps(angle["claims_to_respect"]), rank, now, user_id),
        )
    # Manual rows move to the back of the generated set's rank range -- the
    # same back-of-list position the manual endpoint gives a newly hand-written
    # angle -- so the fresh AI set presents first.
    for offset, row in enumerate(manual_rows):
        await _cfg("_execute")(
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


@router.post("/app-profiles/{profile_id}/content-angles/{angle_id}/regenerate-goals")
async def regenerate_angle_goal_suggestions(
    profile_id: str, angle_id: str, user_id: str = Depends(get_current_user_id)
):
    """
    Show a different ordering of this angle's six goal suggestions.

    No model call and no model_requests row: the suggestions are the same six
    curated goals every time — what changes is their ORDER, advanced one
    deterministic variant step over the profile-tailored order
    (template_library.goal_suggestions_for_profile). The picked variant is
    persisted on the angle row, so a reload re-shows the exact ordering the
    founder last asked for rather than silently reverting — the same
    cache-stability rule the goal picker's existing "selected goal outside
    the suggestions" state already relies on.

    Not gated on profile approval deliberately: the variant is presentation
    state, not derived data — reordering suggestions for an angle the founder
    can already see changes no claim, no fact, and no plan.
    """
    _require_configured()
    row = await _cfg("_fetch_one")(
        "SELECT id, kind, goal_variant FROM content_angles "
        "WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
        (angle_id, profile_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Content angle not found")

    next_variant = template_library.next_goal_suggestion_variant(row.get("goal_variant"))
    profile = await _cfg("_fetch_one")(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    suggestions = template_library.goal_suggestions_for_profile(
        row.get("kind"), profile, next_variant)
    await _cfg("_execute")(
        "UPDATE content_angles SET goal_variant = ? WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
        (next_variant, angle_id, profile_id, user_id),
    )
    return {
        "goal_variant": next_variant,
        "suggestions": suggestions,
    }


@router.post("/app-profiles/{profile_id}/content-angles/{angle_id}/live-goals")
async def live_angle_goals(
    profile_id: str, angle_id: str, user_id: str = Depends(get_current_user_id)
):
    """
    Six live video goals for one selected angle, generated from the angle's
    full context (audience, problem, promise, outcome, emotion, feature).

    Billed and click-gated: the wizard only calls this when the founder
    clicks Generate goals — switching goals or picking an angle queues
    nothing (ADR 0098). The goals are returned, never persisted; the
    facet-ordered suggestions remain the fallback when this fails.
    """
    _require_configured()
    _require_ai_configured()
    profile = await _cfg("_fetch_one")(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")
    if profile.get("status") != "approved":
        raise HTTPException(
            status_code=409,
            detail="Review and approve this App Profile before generating goals.",
        )
    angle = await _cfg("_fetch_one")(
        "SELECT * FROM content_angles WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
        (angle_id, profile_id, user_id),
    )
    if not angle:
        raise HTTPException(status_code=404, detail="Content angle not found")
    try:
        goals = await _cfg("_log_model_call")(
            "angle_goals", "text", ANGLE_MODEL,
            lambda: _cfg("generate_angle_goals")(profile, angle),
            user_id,
            brand_profile_id=profile_id,
        )
    except Exception as e:
        logger.error(f"Live goal generation failed for angle {angle_id}: {e}")
        raise HTTPException(status_code=502, detail=f"AI goal generation failed. Please try again. ({str(e)[:150]})")
    # The verdict tally rides along so freshly generated goals render
    # with the same evidence line as the persisted set (ADR 0126). It is
    # a read attached to this click-gated response, never a trigger.
    return {"angle_id": angle_id, "goals": goals,
            "verdict_objective_evidence": await _verdict_objective_evidence(profile_id, user_id)}


@router.get("/app-profiles/{profile_id}/content-angles/{angle_id}/goal-suggestions")
async def angle_goal_suggestions(
    profile_id: str, angle_id: str, user_id: str = Depends(get_current_user_id)
):
    """Read-only view of the same six suggestions in the angle's saved variant
    order, for a step that renders the picker without a full angles reload."""
    _require_configured()
    row = await _cfg("_fetch_one")(
        "SELECT kind, goal_variant FROM content_angles "
        "WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
        (angle_id, profile_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Content angle not found")
    variant = int(row.get("goal_variant") or 0)
    profile = await _cfg("_fetch_one")(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    return {
        "goal_variant": variant,
        "suggestions": template_library.goal_suggestions_for_profile(
            row.get("kind"), profile, variant
        ),
    }


@router.get("/app-profiles/{profile_id}/direction-options")
async def profile_direction_options(
    profile_id: str, angle_id: str = "", user_id: str = Depends(get_current_user_id)
):
    """The Review-step direction dropdowns for one App Profile.

    Deterministic category mapping, no model call: the same profile always
    gets the same five option lists (Location, lighting, wardrobe, voice,
    tone). Options are pre-vetted by construction — none describes the
    presenter's face or body — but saving still runs the normal claim
    check, since the dropdown is a UX constraint, not a trust boundary.
    """
    _require_configured()
    profile = await _cfg("_fetch_one")(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")
    options = template_library.direction_options_for_profile(profile)
    angle = None
    if (angle_id or "").strip():
        angle = await _cfg("_fetch_one")(
            "SELECT * FROM content_angles WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
            (angle_id.strip(), profile_id, user_id),
        )
    # The angle owns where and when the video happens (ADR 0084), so no option
    # that contradicts its opening moment is ever offered.
    return angle_scene.fit_direction_options(options, angle)


@router.post("/app-profiles/{profile_id}/direction-options/refresh")
async def refresh_profile_direction_options(
    profile_id: str, payload: RefreshDirectionOptionsRequest, user_id: str = Depends(get_current_user_id)
):
    """Four fresh options for one Review-step dropdown, still profile-shaped.

    The static category lists repeat themselves across videos; a refresh
    spends one text model call for four new options for ONE field, grounded
    in the profile and the selected angle, avoiding the options already
    shown. Pre-vetted by instruction like the static lists — and saving
    still runs the normal claim check, since the dropdown is a UX
    constraint, not a trust boundary.
    """
    _require_configured()
    _require_ai_configured()
    profile = await _cfg("_fetch_one")(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?", (profile_id, user_id)
    )
    if not profile:
        raise HTTPException(status_code=404, detail="App Profile not found")
    field = (payload.field or "").strip().lower()
    if field not in ("location", "lighting", "wardrobe", "voice", "tone"):
        raise HTTPException(status_code=400, detail=f"Unknown direction field: {payload.field!r}.")
    angle = None
    if (payload.angle_id or "").strip():
        angle = await _cfg("_fetch_one")(
            "SELECT * FROM content_angles WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
            (payload.angle_id.strip(), profile_id, user_id),
        )
    try:
        options = await _cfg("_log_model_call")(
            "direction_options", "text", TEXT_MODEL,
            lambda: ai_service.refresh_direction_options(profile, field,
                                                          payload.avoid or [], angle),
            user_id,
            brand_profile_id=profile_id,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"AI direction options failed. Please try again. ({str(e)[:150]})")
    scene = angle_scene.angle_scene(angle)
    options = [o for o in options if not angle_scene.conflict_reason(o, scene)]
    return {"field": field, "options": options}


@router.delete("/app-profiles/{profile_id}/content-angles/{angle_id}")
async def delete_content_angle(profile_id: str, angle_id: str, user_id: str = Depends(get_current_user_id)):
    _require_configured()
    row = await _cfg("_fetch_one")(
        "SELECT id FROM content_angles WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
        (angle_id, profile_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="Content angle not found")
    await _cfg("_execute")(
        "DELETE FROM content_angles WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
        (angle_id, profile_id, user_id),
    )
    return {"deleted": angle_id}


@router.get("/templates")
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
    _require_configured()
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

    rows = await _cfg("_fetch_all")(
        f"""SELECT * FROM hook_templates WHERE {' AND '.join(clauses)}
            ORDER BY name ASC LIMIT 300""",
        tuple(params),
    )
    return {"templates": await _with_favorites(rows, user_id)}


@router.get("/templates/facets")
async def template_facets(user_id: str = Depends(get_current_user_id)):
    """Controlled vocabularies + observed categories, for building filter UI."""
    _require_configured()
    rows = await _cfg("_fetch_all")(
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


@router.get("/app-profiles/{profile_id}/template-recommendations")
async def recommend_templates(
    profile_id: str,
    angle_id: str = "",
    objective: str = "",
    hook_line: str = "",
    middle: str = "",
    limit: int = 3,
    user_id: str = Depends(get_current_user_id),
):
    """
    Recommend library templates for an App Profile, optionally narrowed to one
    content angle and objective.

    `hook_line` and `middle` carry the approved plan's spoken words when a
    plan exists, so each card's shape and development quote what this video
    actually opens and develops with instead of paraphrasing a promise into
    words nobody speaks (ADR 0108). They only shape the display; ranking is
    unchanged.

    The picker shows exactly three rows (ADR 0096): the scored top three,
    backfilled from the longest list available when fewer than three are
    active — so the count below is a product rule, not a page parameter.
    A client-supplied limit is clamped to at most three.

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
    _require_configured()
    profile = await _cfg("_fetch_one")(
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
        angle = await _cfg("_fetch_one")(
            "SELECT * FROM content_angles WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
            (angle_id.strip(), profile_id, user_id),
        )
        if not angle:
            raise HTTPException(status_code=404, detail="Content angle not found for this App Profile")

    norm_objective = template_library.normalize_objective(objective) if objective else ""
    templates = await _cfg("_fetch_all")(
        """SELECT * FROM hook_templates
           WHERE (user_id = ? OR user_id = 'system')
             AND archived = 0 AND review_status = 'approved'
             AND opening_structure IS NOT NULL AND opening_structure != ''""",
        (user_id,),
    )
    if not templates:
        return {"recommendations": [], "angle": _serialize_angle_row(angle) if angle else None}

    # The one learning input ranking reads (ADR 0127): the founder's
    # whole-video verdicts for this profile, each verdict attributed by
    # the template frozen in its bundle. The per-element record and the
    # posted outcomes used to be fetched here too; ranking stopped
    # reading them (the record itself is untouched — it still serves
    # History, Analytics and the profile summary).
    verdict_rows = await _verdict_rows_for_profile(profile_id, user_id)
    verdict_evidence = feedback_mod.verdict_template_evidence(verdict_rows)
    scored = []
    for tpl in templates:
        result = _score_template_for_angle(
            tpl, profile, angle, norm_objective, verdict_rows,
            hook_line=hook_line or None, middle=middle or None,
        )
        # A tailored row generated for a different problem is not a candidate
        # for this video at all: dropping it is the difference between "fewer
        # cards" and "cards about someone else's problem" (ADR 0089). Curated
        # rows stay — a curated template is a shape the plan fills with this
        # angle's problem — so a failed generation never leaves the picker empty.
        if (
            angle
            and (tpl.get("brand_profile_id") or "") == (profile.get("id") or "")
            and not result["relevance"]["passes"]
        ):
            continue
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
            "verdicts": result["verdicts"],
            "verdict_evidence": verdict_evidence.get(tpl.get("id") or ""),
            "retired": result["retired"],
            "relevance": result["relevance"],
            "angle_scene": result["angle_scene"],
        })
    scored.sort(key=lambda r: (r["retired"], -r["score"], r["template"]["name"]))
    # Exactly three rows, always (ADR 0096): the scored top three from the
    # longest list available, so the picker never shows fewer (some templates
    # are retired) and never more — a client-supplied limit can only ask for
    # fewer, and the product never offers a "show more". Within that rule the
    # set prefers structurally distinct templates (ADR 0127): two cards on
    # one shape under two names is one choice presented twice, so a
    # duplicate yields to the next distinct shape and backfills only when
    # nothing distinct remains.
    want = max(1, min(int(limit or 3), 3))
    visible = _diversify_template_recommendations(scored, want)
    # Shared across the visible set, not the whole table: the section line
    # must describe exactly the cards beside it.
    shared = _split_shared_notes(visible)
    return {
        "recommendations": visible,
        "shared_reasons": shared["shared_reasons"],
        "shared_limitations": shared["shared_limitations"],
        "angle": _serialize_angle_row(angle) if angle else None,
        "objective": norm_objective,
    }


@router.post("/app-profiles/{profile_id}/objective-templates")
async def ensure_objective_templates(
    profile_id: str, payload: ObjectiveTemplatesRequest, user_id: str = Depends(get_current_user_id)
):
    """
    Tailored templates for this profile, this objective and this angle.

    The objective is chosen per video in the wizard — it does not exist at
    approve time — so generation lives here, called when the founder's click
    asks for it. A cached set returns immediately without a model call;
    otherwise the set generates synchronously (same in-request precedent as
    strategy and plan builds) and replaces any previous set for that
    (profile, objective, angle) key.

    The angle is the video's own source of truth (Problem, First 3 Seconds
    Promise, Audience, Bounded By), so a cached set only counts when it was
    generated from this angle and still shares this Problem and Promise. A
    legacy set that does not is regenerated rather than shown, which is what
    stops the picker drifting away from the problem the founder picked
    (ADR 0089).

    Never 500s on a model failure: the previous set (or an empty list)
    returns with the error attached, and the curated picks keep working.
    """
    _require_configured()
    profile = await _require_profile_for_studio(profile_id, user_id)
    want_objective = template_library.normalize_objective(
        (payload.objective if payload else "") or "")
    if not want_objective:
        raise HTTPException(
            status_code=400,
            detail="Pick an objective first — tailored templates are generated per objective.",
        )
    angle = None
    angle_id = str((payload.angle_id if payload else "") or "").strip()
    if angle_id:
        angle = await _cfg("_fetch_one")(
            "SELECT * FROM content_angles WHERE id = ? AND brand_profile_id = ? AND user_id = ?",
            (angle_id, profile_id, user_id),
        )
        if not angle:
            raise HTTPException(status_code=404, detail="Content angle not found for this App Profile")
        angle = _serialize_angle_row(angle)
    cached = await _cfg("_fetch_all")(
        """SELECT * FROM hook_templates
           WHERE brand_profile_id = ? AND objective = ? AND user_id = ?
             AND archived = 0 AND review_status = 'approved'""",
        (profile_id, want_objective, user_id),
    )
    # Only rows generated from THIS angle, and only rows still about its
    # problem. A set with nothing left in scope is not a set.
    existing = [
        row for row in cached
        if str(row.get("angle_id") or "") == angle_id
        and _check_template_relevance(row, angle)["passes"]
    ]
    # Regenerate means regenerate: an explicit ask replaces the set even
    # when one exists. Anything else serves the cache without a model call.
    if existing and not (payload.regenerate or False):
        return {
            "templates": [_public_library_template(t) for t in existing],
            "generated": False,
            "objective": want_objective,
            "angle_id": angle_id,
            "error": None,
        }
    try:
        drafts = await _ensure_objective_templates(profile, want_objective, user_id, angle)
    except Exception as e:  # defensive: _ensure already swallows model errors
        logger.error(f"Objective template generation failed: {e!r}")
        drafts = []
    rows = await _cfg("_fetch_all")(
        """SELECT * FROM hook_templates
           WHERE brand_profile_id = ? AND objective = ? AND user_id = ?
             AND archived = 0 AND review_status = 'approved'""",
        (profile_id, want_objective, user_id),
    )
    rows = [
        row for row in rows
        if str(row.get("angle_id") or "") == angle_id
        and _check_template_relevance(row, angle)["passes"]
    ]
    return {
        "templates": [_public_library_template(t) for t in rows],
        "generated": bool(drafts),
        "objective": want_objective,
        "angle_id": angle_id,
        "error": None if drafts else (
            "Tailoring failed — the curated picks below still work. "
            "Reopening this step retries."
        ),
    }
