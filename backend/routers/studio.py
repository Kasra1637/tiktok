"""Studio projects: drafts, plan, strategy, and the render submit path.

One router owns the studio workflow endpoints: project CRUD, plan
generation, readiness marking, strategy building, and the submit gate that
funnels through `_submit_generation` (which stays the sole submit path in
`server.py` — only its module address changes; `server` re-exports it).

Shared stateless deps (ai_service, scene_consistency, template_library,
video_providers, final_beat, opening_move, generation_planning,
feedback) import here directly. DB helpers and the render-composition
helpers (`_fetch_one`, `_fetch_all`, `_execute`, `_log_model_call`,
`_submit_generation`, `_public_generation`, `_public_asset`,
`_asset_usage_index`, `_public_generation_detail`, `_record_behavior`,
`_component_feedback_for_profile`, `_require_profile_for_studio`,
`_with_verdicts`, `require_ai_configured`, `_request_id`) are owned by the
composition root and injected here once via `configure_studio`. No import
of server here, in either direction: an unconfigured call fails loudly
instead of half-working. Call sites resolve the patched helpers at call
time through `_cfg` over the `_server` back-reference — same mechanism as
`db._server`/`db._cfg` and `routers.brands._server`/`_cfg` — so the many
tests that patch `server.<name>` keep intercepting.
"""

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request

import ai_service
import angle_scene
import creative_quality
import scene_consistency
import template_library
import video_providers
import final_beat
import opening_move
import generation_planning
import feedback as feedback_mod
from ai_service import (
    TEXT_MODEL,
    normalize_strategy,
    generate_video_strategy,
    bind_spoken_words,
    spoken_budget,
    generate_creative_plan,
    rewrite_hook_line,
    check_spoken_story,
)
from auth import get_current_user_id
from models import (
    CreateStudioProjectRequest,
    UpdateStudioProjectRequest,
    GeneratePlanRequest,
    GeneratePlanAndStrategyRequest,
    GenerateStrategyRequest,
    RewriteHookRequest,
    RewriteLineRequest,
    StudioGenerationRequest,
    STUDIO_EDITABLE_FIELDS,
    STUDIO_TEXT_FIELDS,
    now_iso,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_server = None


def _cfg(name, default=None):
    """Read a live binding from the composition root."""
    return getattr(_server, name, default) if _server is not None else default


def configure_studio(server):
    """Inject the composition root (DB helpers + render composition).

    Called once at include time. Call sites resolve through `_cfg` so test
    monkeypatching of `server.<name>` is seen at call time.
    """
    global _server
    _server = server


def _require_configured():
    if _server is None:
        raise RuntimeError("studio router used before configure_studio ran")


def _fetch_one(*a, **k):
    return _cfg("_fetch_one")(*a, **k)


def _fetch_all(*a, **k):
    return _cfg("_fetch_all")(*a, **k)


def _execute(*a, **k):
    return _cfg("_execute")(*a, **k)


def _log_model_call(*a, **k):
    return _cfg("_log_model_call")(*a, **k)


def _submit_generation(*a, **k):
    return _cfg("_submit_generation")(*a, **k)


def _public_generation(*a, **k):
    return _cfg("_public_generation")(*a, **k)


def _with_verdicts(*a, **k):
    return _cfg("_with_verdicts")(*a, **k)


def _record_behavior(*a, **k):
    return _cfg("_record_behavior")(*a, **k)


def _component_feedback_for_profile(*a, **k):
    return _cfg("_component_feedback_for_profile")(*a, **k)


def _posted_performance_rows(*a, **k):
    return _cfg("_posted_performance_rows")(*a, **k)


def _require_profile_for_studio(*a, **k):
    return _cfg("_require_profile_for_studio")(*a, **k)


def require_ai_configured(*a, **k):
    return _cfg("require_ai_configured")(*a, **k)


def _request_id(*a, **k):
    return _cfg("_request_id")(*a, **k)


async def _verdict_feedback_for_profile(brand_profile_id, user_id):
    """This profile's whole-video verdicts, summarized for prompt steering.

    The only feedback that reaches the plan and strategy prompts (ADR
    0124): verdict rows joined to their generations' profile, newest
    first, each carrying the bundle frozen when the verdict was cast.
    A read failure yields an empty summary — no steering — rather than
    failing the generation the founder asked for.
    """
    try:
        rows = await _fetch_all(
            "SELECT vv.verdict AS verdict, vv.bundle AS bundle FROM video_verdicts vv "
            "JOIN generations g ON g.id = vv.generation_id "
            "WHERE g.brand_profile_id = ? AND vv.user_id = ? "
            "ORDER BY vv.updated_at DESC LIMIT 50",
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
        parsed.append({
            "verdict": row.get("verdict"),
            "bundle": bundle if isinstance(bundle, dict) else {},
        })
    return feedback_mod.summarize_video_verdicts(parsed)


def _verdict_summary_payload(verdict_feedback) -> dict:
    """The Review evidence counts (ADR 0127), or {} when there are none.

    Display only: the same verdict summary the plan and strategy prompts
    steer from, projected to the three counts the Analytics headline
    uses — total, worked, didn't. Projected here so every project
    payload that carries it carries the same shape; when the profile
    has no verdicts yet the dict is empty and the payload simply has no
    verdict_summary key, so Review renders nothing.
    """
    summary = verdict_feedback or {}
    if not summary.get("total"):
        return {}
    return {"verdict_summary": {
        "total": int(summary.get("total") or 0),
        "up": int(summary.get("up") or 0),
        "down": int(summary.get("down") or 0),
    }}


# ---------------------------------------------------------------------------
# Pure helpers (no DB) — owned here; re-exported by server for existing callers.
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
    # The claim-safety system is gone (ADR 0119): its stored columns stay in
    # the schema, but no project response carries the verdict fields anymore.
    out.pop("safety_report", None)
    out.pop("safety_summary", None)
    out["beat_timeline"] = out.get("beat_timeline") or []
    out["overlays"] = out.get("overlays") or []
    out["assets"] = out.get("assets") or []
    out["duration_seconds"] = out.get("duration_seconds") or 0
    out["script_version"] = out.get("script_version") or 0
    out["camera_setup"] = out.get("camera_setup") or "handheld"
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
    if isinstance(strategy, dict) and strategy:
        normalized = normalize_strategy(strategy)
        strategy = {**strategy, **normalized}
    # The plan's camera move is carried into the panel's Framing and Movement
    # (ADR 0108), so Render & result shows the push-in the plan promises. The
    # lighting split stays a save/render repair — splitting time out of
    # Location on read would rewrite the founder's Location before they ever
    # edited it (the legacy-read contract).
    if isinstance(strategy, dict) and strategy:
        _carry = scene_consistency.carry_camera_movement(strategy, out)
        if _carry:
            logger.debug(
                "Project %s panel carry: %s",
                out.get("id"),
                ", ".join(_carry),
            )
    out["strategy"] = strategy if isinstance(strategy, dict) else {}
    if not (out.get("location") or "").strip():
        out["location"] = ((out["strategy"].get("scene") or {}).get("location") or "").strip()
    # The Location editor shows the place only: object clauses ("a phone
    # beside the person") are dropped from the display even though the
    # lighting split still only runs on save and render. A continuation
    # fragment ("with ...") is prepended with the strategy prose's own
    # anchor so the editor never shows a tail without its place.
    if (out.get("location") or "").strip():
        displayed_location, _objects = scene_consistency.strip_location_objects(out["location"])
        if _objects:
            out["location"] = displayed_location
        _anchor_text = " ".join(str(out["strategy"].get(k) or "")
                                for k in ("hook_promise", "hook_concept", "strategy_summary"))
        out["location"] = scene_consistency.repair_location_fragment(
            out.get("location"), _anchor_text
        )
    out["strategy_is_current"] = out["strategy_is_current"] and (
        (out["strategy"].get("camera_setup") or "handheld") == out["camera_setup"]
    )
    # A strategy stamped with a different objective/template than the project
    # now carries is stale, but a strategy predating the stamp (an empty value
    # — a live fake, an older build) is missing history, not a mismatch, the
    # same missing-history rule as the script_version stamp above.
    _strategy_objective = out["strategy"].get("objective")
    out["strategy_is_current"] = out["strategy_is_current"] and (
        _strategy_objective is None or _strategy_objective == (out.get("objective") or "")
    )
    _strategy_template = out["strategy"].get("template_id")
    out["strategy_is_current"] = out["strategy_is_current"] and (
        _strategy_template is None or _strategy_template == (out.get("template_id") or "")
    )
    # A strategy predating the template_version stamp (live-generated fakes and
    # pre-stamp projects) is missing history, not a mismatch — do not block it.
    _strategy_tv = out["strategy"].get("template_version")
    out["strategy_is_current"] = out["strategy_is_current"] and (
        _strategy_tv is None or int(_strategy_tv) == int(out.get("template_version") or 1)
    )
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
    out["spoken_check"] = check_spoken_story(
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
    # The craft score is advisory and recomputed on read, like spoken_check:
    # it describes the words currently saved, not the words a previous version
    # scored. It never gates a render; `QualityReport` is the founder's mirror,
    # not a submit condition.
    out["quality_report"] = (
        creative_quality.assess_spoken_quality(
            out.get("hook_line"),
            out.get("script"),
            hook_seconds=out.get("hook_seconds") or 3,
            total_seconds=out.get("duration_seconds") or 0,
            app_name=brand_name,
            spoken_check=out["spoken_check"],
            # A question hook is a craft choice the plan's template can request;
            # the deterministic spoken check already knows the plan's policy.
            # The quality score should not call the form itself a trust defect.
            allows_question=True,
        )
        if (out.get("hook_line") or out.get("script"))
        else None
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

    The plan's camera move is carried into Framing and Movement here (ADR
    0108), matching what the Review panel showed. The lighting split and the
    fuller scene repair stay with the render guard, which re-runs them before
    the prompt is built and refuses anything repair cannot fix.
    """
    strategy = (project or {}).get("strategy")
    if isinstance(strategy, dict):
        merged = {**strategy, **normalize_strategy(strategy)} if strategy else {}
    elif not strategy:
        return {}
    else:
        try:
            parsed = json.loads(strategy)
        except (json.JSONDecodeError, TypeError):
            return {}
        merged = {**parsed, **normalize_strategy(parsed)} if isinstance(parsed, dict) and parsed else {}
    if not merged:
        return {}
    _carry = scene_consistency.carry_camera_movement(merged, project)
    if _carry:
        logger.debug(
            "Project %s render-path carry: %s",
            (project or {}).get("id"),
            ", ".join(_carry),
        )
    return merged


def _require_spoken_words_fit(project: dict) -> dict:
    """
    Refuse a render whose approved script cannot be spoken within the piece.

    The middle's seconds hold a fixed number of characters; anything past that
    would be silently dropped from the words reaching the video model — and the
    tail is usually the payoff sentence. This is recomputed from the live row,
    not read from a stored verdict, so App Profile and plan edits cannot
    strand an approval. Returns the overflow record ({} when everything fits).
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
    if (built_from and current and built_from != current) or (
        (strategy.get("camera_setup") or "handheld") != (project.get("camera_setup") or "handheld")
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "The plan changed after this strategy was built, so the strategy no "
                "longer describes what you reviewed. Rebuild it on the Hook + Story "
                "step, then generate."
            ),
        )
    # The strategy is built around one audience angle, and the version stamp
    # above does not track it: changing the angle leaves script_version
    # untouched, so without this check a direct caller could render a strategy
    # describing the wrong video. The studio buttons already refuse this case
    # (angleStale, judged the same way); the spend boundary answers the same
    # question rather than trusting the caller to have asked it.
    if (strategy.get("content_angle_id") or "") != (project.get("content_angle_id") or ""):
        raise HTTPException(
            status_code=409,
            detail=(
                "The audience angle changed after this strategy was built, so the "
                "strategy describes a different video than the one now picked. "
                "Rebuild it on the Hook + Story step for the current angle, then "
                "generate."
            ),
        )
    # The goal, the template identity and the template's version are stamped on
    # the strategy at build (ai_service 6195-6198) and are NOT in _CONTENT_KEYS,
    # so the script_version stamp alone never sees them drift: changing the goal
    # after a plan/strategy lets the render speak words built for the old goal,
    # and switching the template mixes the new template's structure with the old
    # strategy's words. The spend boundary compares them the same way the angle
    # check above does, rather than trusting the caller to have asked.
    # Missing-history rule: a strategy whose stamp never landed (empty value,
    # pre-stamp build) is unstamped, not mismatched — a truly unstamped
    # strategy this project still has to rebuild once, and refusing it here
    # would block every pre-stamp project forever.
    _strategy_objective = strategy.get("objective")
    if _strategy_objective is not None and _strategy_objective != (project.get("objective") or ""):
        raise HTTPException(
            status_code=409,
            detail=(
                "The video goal changed after this strategy was built, so the "
                "strategy describes a different intent than the one now picked. "
                "Rebuild it on the Hook + Story step for the current goal, then "
                "generate."
            ),
        )
    _strategy_template = strategy.get("template_id")
    if _strategy_template is not None and _strategy_template != (project.get("template_id") or ""):
        raise HTTPException(
            status_code=409,
            detail=(
                "The template changed after this strategy was built, so the "
                "strategy describes a different structure than the template now "
                "picked. Rebuild it on the Hook + Story step for the current "
                "template, then generate."
            ),
        )
    # A strategy predating the template_version stamp (live-generated fakes and
    # pre-stamp projects) is missing history, not a mismatch — the same
    # missing-history rule as the script_version stamp above.
    _strategy_tv = strategy.get("template_version")
    if _strategy_tv is not None and int(_strategy_tv) != int(project.get("template_version") or 1):
        raise HTTPException(
            status_code=409,
            detail=(
                "The template changed after this strategy was built, so the "
                "strategy describes a different structure than the template now "
                "picked. Rebuild it on the Hook + Story step for the current "
                "template, then generate."
            ),
        )
    return strategy


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


def _guard_render_scene(strategy: dict, project: dict, render_index: int = 0, exclude=(), content_angle=None) -> dict:
    """
    Make a strategy's scene fields agree before the prompt is built, and refuse
    a render that still carries a contradiction.

    This is the second net under the save-time rewrite (ADRs 0090, 0092): a
    strategy built before the founder's Location existed, edited through
    another client, or patched by a caller that skipped
    `update_studio_project` still renders ONE consistent scene.

    - Direction lines that contradict the Location are rewritten — same rules
      as the save — because the founder already chose the place and the render
      should show it. Spoken words are never rewritten, so a hook line or a
      section script that still names another place fails the render with the
      field named and nothing charged.
    - Location is split so it names the place only, with its lighting and time
      of day moved into Lighting.
    - Props and Movement are completed from the hook/middle actions and the
      shot timeline's action clauses; a list that can be shortened without
      losing those actions is compacted, and one that cannot hold everything
      it must is refused rather than cut.
    - A selfie render ends on a physical beat, never a phone (ADR 0093): the
      character can never reach toward, hold, raise or show a phone or camera
      at any point, and no action may need a second free hand — one hand
      holds the camera. Clauses that do are removed from the strategy's
      fields, and `render_index` picks the ending for THIS render so
      consecutive renders do not repeat it. A fixed-camera render keeps the
      phone handoff. `exclude` carries the endings this project already
      used, so consecutive renders do not repeat a recent ending. If
      stripping would empty the opening or middle action, or a forbidden
      clause still remains, the render is refused with the field named
      instead of sending it to the provider; spoken words are never
      rewritten or refused for this.
    """
    # The plan's Location is the canonical field; `visual_direction` is the
    # legacy mirror a pre-rename row still carries.
    location = str(project.get("location") or project.get("visual_direction") or "").strip()
    if location and content_angle is not None:
        location = scene_consistency.repair_location_fragment(
            location,
            " ".join(str((content_angle or {}).get(k) or "")
                     for k in ("hook_promise", "user_problem"))
            + " " + " ".join(str((strategy or {}).get(k) or "")
                             for k in ("hook_promise", "hook_concept")),
        )
    if not location or not isinstance(strategy, dict) or not strategy:
        return strategy
    audit = angle_scene.reconcile_location(strategy, location, thorough=True)
    if audit["blocked"]:
        named = "; ".join(f"{b['field']} {b['reason']}" for b in audit["blocked"])
        raise HTTPException(
            status_code=409,
            detail=(
                f"Your Location is \u201c{location}\u201d, but the spoken words still name another "
                f"place: {named}. Spoken words are never rewritten automatically \u2014 edit "
                "them on Review & submit to match the Location (or change the Location), "
                "then generate again. Nothing has been charged."
            ),
        )
    strategy = audit["strategy"]
    # Selfie renders end on a physical beat, never a phone (ADR 0093): the
    # forbidden clauses are removed from the strategy's own fields first,
    # so the scene pass below cannot copy them back into Props or Movement,
    # and the chosen ending is applied afterwards.
    selfie = final_beat.is_selfie(strategy)
    strip_changed = []
    orig_hook_action = str(strategy.get("hook_action") or "").strip()
    orig_middle_action = ""
    for section in strategy.get("segments") or []:
        if isinstance(section, dict) and str(section.get("role") or "").lower() == "middle":
            orig_middle_action = str(section.get("action") or "").strip()
            break
    if selfie:
        strip_audit = final_beat.strip_fields(strategy)
        strategy = strip_audit["strategy"]
        strip_changed = strip_audit["changed"]
    scene_audit = scene_consistency.reconcile_scene(strategy, project)
    if scene_audit["blocked"]:
        named = "; ".join(f"{b['field']} {b['reason']}" for b in scene_audit["blocked"])
        raise HTTPException(
            status_code=409,
            detail=(
                f"This render was stopped before it cost anything: {named}. Edit the script "
                "plan or the strategy on Review & submit so the scene fields agree, then "
                "generate again. Nothing has been charged."
            ),
        )
    strategy = scene_audit["strategy"]
    if selfie:
        # Fix only what survives as an action: a field whose entire content
        # was the forbidden reach/phone has nothing left to film, so refuse
        # with the field named instead of rendering an empty action.
        emptied = []
        if orig_hook_action and not str(strategy.get("hook_action") or "").strip():
            emptied.append("Opening action")
        middle_action = ""
        for section in strategy.get("segments") or []:
            if isinstance(section, dict) and str(section.get("role") or "").lower() == "middle":
                middle_action = str(section.get("action") or "").strip()
                break
        if orig_middle_action and not middle_action:
            emptied.append("Middle — what they do")
        if emptied:
            named = ", ".join(emptied)
            raise HTTPException(
                status_code=409,
                detail=(
                    f"This render was stopped before it cost anything: {named} only "
                    "named a phone or camera, or reached toward the lens, which a "
                    "handheld selfie cannot film (one hand holds the camera). Edit that "
                    "line on Review & submit to name a physical action the filming hand "
                    "can do, then generate again. Nothing has been charged."
                ),
            )
    # Opening movement (ADR 0090, enforced): every setup — selfie or fixed —
    # must open on a visible movement, gesture or position change, never on
    # standing still or speaking alone. A static opening is repaired
    # additively here; only an opening that names no action at all is
    # refused.
    opening_changed = []
    opening_verdict = opening_move.validate_opening(strategy)
    if not opening_verdict["ok"]:
        repaired = opening_move.repair(strategy)
        strategy = repaired["strategy"]
        opening_changed = repaired["changed"]
        if not opening_move.validate_opening(strategy)["ok"]:
            raise HTTPException(
                status_code=409,
                detail=(
                    "This render was stopped before it cost anything: the "
                    "opening names no physical action, so the first beat cannot "
                    "be filmed as a visible move. Edit the opening action on "
                    "Review & submit so the viewer watches the person move first, "
                    "then generate again. Nothing has been charged."
                ),
            )

    ending_changed = []
    if selfie:
        ending = final_beat.pick(strategy, exclude=exclude, index=render_index)
        ending_audit = final_beat.apply_ending(strategy, ending)
        strategy = ending_audit["strategy"]
        ending_changed = ending_audit["changed"]
        hits = final_beat.forbidden_hits(strategy)
        if hits:
            named = ", ".join(sorted(set(hits)))
            raise HTTPException(
                status_code=409,
                detail=(
                    f"This render was stopped before it cost anything: {named} still "
                    "reaches toward, holds, raises or shows a phone or camera, or "
                    "needs a second free hand, which a handheld selfie cannot film. "
                    "Edit that line on Review & submit so the action needs only the "
                    "filming hand, then generate again. Nothing has been charged."
                ),
            )
    if audit["changed"] or strip_changed or scene_audit["changed"] or ending_changed or opening_changed:
        logger.info(
            "Render for project %s: strategy scene reconciled before prompt build: %s",
            project.get("id"),
            ", ".join(list(dict.fromkeys(
                audit["changed"] + strip_changed + scene_audit["changed"] + ending_changed + opening_changed
            ))),
        )
    return strategy


# ---------------------------------------------------------------------------
# Routes — moved verbatim from `server.py`; the wrapper is an `APIRouter`.
# ---------------------------------------------------------------------------
@router.get("/studio/video-models")
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


@router.get("/studio/projects")
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

@router.post("/studio/projects", status_code=201)
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
             script_version, status, created_at, updated_at, user_id, camera_setup)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (project_id, profile["id"], (payload.content_angle_id or "").strip() or None,
         template_id or None, template_version,
         template_library.normalize_objective(payload.objective),
         (payload.audience or profile.get("target_audience") or "").strip() or None,
         duration, hook_seconds, 1, (payload.tone or "").strip() or None,
         json.dumps([]), 0, "draft", now, now, user_id, payload.camera_setup),
    )
    logger.info(f"Created studio project {project_id} for profile {profile['id']}")
    return _public_project(
        await _fetch_one("SELECT * FROM studio_projects WHERE id = ?", (project_id,)),
        brand_name=(profile.get("brand_name") or "").strip(),
    )

@router.get("/studio/projects/{project_id}")
async def get_studio_project(project_id: str, user_id: str = Depends(get_current_user_id)):
    row = await _fetch_one(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?", (project_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Studio project not found")
    # A project from before one-render generation is brought forward here, so
    # reopening it is what repairs it — see _backfill_two_section_projects.
    await _backfill_two_section_projects([row])
    payload = _public_project(row)
    # The Review step's verdict evidence (ADR 0127): a pure read of the
    # profile's verdict summary, attached for display only — it never
    # generates anything (ADR 0122) and is absent when there are none.
    payload.update(_verdict_summary_payload(
        await _verdict_feedback_for_profile(row.get("brand_profile_id"), user_id)))
    return payload

@router.patch("/studio/projects/{project_id}")
async def update_studio_project(
    project_id: str, payload: UpdateStudioProjectRequest, user_id: str = Depends(get_current_user_id)
):
    """
    Edit a draft. This is the founder's review step, so every generated field
    is editable and editing bumps script_version so a later generation can be
    traced to the exact text that was approved.
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
    _CONTENT_KEYS = set(STUDIO_TEXT_FIELDS) | {"beat_timeline", "assets", "strategy", "camera_setup"}
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
            if isinstance(existing, dict) and existing:
                existing = {**existing, **normalize_strategy(existing)}
            incoming = value if isinstance(value, dict) else {}
            merged_strategy = {**existing, **incoming} if isinstance(existing, dict) else incoming
            if isinstance(existing, dict) and isinstance(incoming.get("scene"), dict):
                merged_strategy["scene"] = {**(existing.get("scene") or {}), **incoming["scene"]}
            normalized = normalize_strategy(merged_strategy)
            value = {**merged_strategy, **normalized}
            value["camera_setup"] = (existing.get("camera_setup") or "handheld") if isinstance(existing, dict) else "handheld"
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

    # The Location is the single source of truth for where the video happens
    # (ADR 0090). The strategy keeps its own copy of the place in
    # scene.location and in its direction lines, and that copy is what the
    # render lock reads — so before this rewrite existed, editing the Location
    # could not change the video: the older strategy text won at the lock every
    # time. A Location edit now rewrites the strategy's place-bearing lines in
    # the same save (angle_scene.reconcile_location), and re-stamps the
    # strategy to the new plan version, so changing one place name does not
    # force a paid text rebuild whose only job is to repeat it. Spoken words
    # are deliberately not rewritten; anything they still contradict is
    # reported back for the founder to fix.
    #
    # `location` is the canonical field and `visual_direction` the legacy
    # mirror; a client may send either, and both columns are kept in sync so
    # every reader — old and new — sees the same place.
    #
    # The Location is also split on the way in (ADR 0092): it stores the place
    # only, and any lighting or time of day it carried moves into the
    # strategy's Lighting — or, before a strategy exists, into the plan's scene
    # notes so the strategy prompt still receives it.
    location_change = None
    location_key = ""
    if "strategy" not in updates:
        if "location" in updates:
            location_key = "location"
        elif "visual_direction" in updates:
            location_key = "visual_direction"
    if location_key:
        new_location = str(updates.get(location_key) or "").strip()
        old_location = str(
            row.get("location") or row.get("visual_direction") or ""
        ).strip()
        if new_location != old_location:
            place, moved = scene_consistency.split_location(new_location)
            # The Location column itself names the place only, in every
            # camera setup: object clauses ("a phone beside the person") are
            # dropped on save, not only in the strategy copy.
            place, _objects = scene_consistency.strip_location_objects(place)
            # A continuation fragment ("with ...") names no place head.
            # Prepend the angle's own anchor so the saved place is the
            # fixture the scene hangs off. Angle prose is preferred so a
            # deliberate founder place (non-fragment) is never rewritten;
            # a stored strategy usually carries it already.
            _existing_for_anchor = row.get("strategy")
            if isinstance(_existing_for_anchor, str):
                try:
                    _existing_for_anchor = json.loads(_existing_for_anchor)
                except (json.JSONDecodeError, TypeError):
                    _existing_for_anchor = {}
            if not isinstance(_existing_for_anchor, dict):
                _existing_for_anchor = {}
            _anchor_source = " ".join(str(_existing_for_anchor.get(k) or "")
                                      for k in ("hook_promise", "hook_concept"))
            if not _anchor_source.strip() and row.get("content_angle_id"):
                _angle_row = await _fetch_one(
                    "SELECT hook_promise, user_problem FROM content_angles WHERE id = ?",
                    (row.get("content_angle_id"),),
                )
                if _angle_row:
                    _anchor_source = " ".join(str(_angle_row.get(k) or "")
                                              for k in ("hook_promise", "user_problem"))
            place = scene_consistency.repair_location_fragment(place, _anchor_source)
            mirror_key = "visual_direction" if location_key == "location" else "location"
            existing_strategy = row.get("strategy")
            if isinstance(existing_strategy, str):
                try:
                    existing_strategy = json.loads(existing_strategy)
                except (json.JSONDecodeError, TypeError):
                    existing_strategy = None
            has_strategy = isinstance(existing_strategy, dict) and bool(existing_strategy)
            # The client's own key stores the place only. Before a strategy
            # exists there is no Lighting field yet, so a legacy
            # visual_direction keeps the moved lighting text as scene notes.
            own_value = place
            if not has_strategy and moved and location_key == "visual_direction":
                own_value = scene_consistency.append_clause(place, moved)
            if own_value != new_location:
                set_clauses.append(f"{location_key} = ?")
                values.append(own_value)
            mirror_value = (
                place
                if has_strategy or not moved
                else scene_consistency.append_clause(place, moved)
            )
            if mirror_key not in updates:
                set_clauses.append(f"{mirror_key} = ?")
                values.append(mirror_value)
            if has_strategy:
                audit = angle_scene.reconcile_location(existing_strategy, new_location)
                strategy_out = audit["strategy"]
                scene_audit = scene_consistency.reconcile_scene(strategy_out, row)
                changed = list(dict.fromkeys(audit["changed"] + scene_audit["changed"]))
                if audit["changed"] or scene_audit["changed"]:
                    updates["strategy"] = scene_audit["strategy"]
                    set_clauses.append("strategy = ?")
                    values.append(json.dumps(scene_audit["strategy"]))
                    set_clauses.append("strategy_version = strategy_version + 1")
                # The strategy now describes the saved plan: keep it current
                # instead of blocking the render on a version number this same
                # save has already reconciled.
                set_clauses.append("strategy_script_version = ?")
                values.append(
                    int(row.get("script_version") or 0) + (1 if content_changed else 0)
                )
                location_change = {
                    "changed": changed,
                    "blocked": audit["blocked"] + scene_audit["blocked"],
                }

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
    # Behavior: switching away from a template or goal that never rendered
    # drops it without proceeding, so the orphan is abandoned. Something that
    # already rendered was moved forward with — its adoption is recorded at
    # submit — so only a renderless switch counts as abandonment.
    _old_template = (row.get("template_id") or "").strip()
    _new_template = updates.get("template_id", row.get("template_id")) or ""
    _new_template = _new_template.strip() if isinstance(_new_template, str) else _new_template
    if "template_id" in updates and _new_template != _old_template and _old_template:
        _old_template_rendered = await _fetch_one(
            "SELECT id FROM generations WHERE studio_project_id = ?"
            " AND template_id = ? AND user_id = ? LIMIT 1",
            (project_id, _old_template, user_id),
        )
        if not _old_template_rendered:
            await _record_behavior(
                "abandoned", "template", user_id,
                brand_profile_id=row.get("brand_profile_id") or "",
                studio_project_id=project_id,
                template_id=_old_template)
    _old_angle = (row.get("content_angle_id") or "").strip()
    _new_angle = updates.get("content_angle_id", row.get("content_angle_id")) or ""
    _new_angle = _new_angle.strip() if isinstance(_new_angle, str) else _new_angle
    _old_objective = template_library.normalize_objective(row.get("objective") or "")
    _new_objective = updates.get("objective", row.get("objective")) or ""
    if (("content_angle_id" in updates and _new_angle != _old_angle)
            or ("objective" in updates and _new_objective != _old_objective)):
        _any_render = await _fetch_one(
            "SELECT id FROM generations WHERE studio_project_id = ? AND user_id = ? LIMIT 1",
            (project_id, user_id),
        )
        if not _any_render:
            _old_kind = ""
            if _old_angle:
                _old_angle_row = await _fetch_one(
                    "SELECT kind FROM content_angles WHERE id = ?", (_old_angle,))
                _old_kind = ((_old_angle_row or {}).get("kind") or "").strip()
            await _record_behavior(
                "abandoned", "goal", user_id,
                brand_profile_id=row.get("brand_profile_id") or "",
                studio_project_id=project_id,
                detail=f"objective={_old_objective};kind={_old_kind}")
    result = _public_project(
        await _fetch_one("SELECT * FROM studio_projects WHERE id = ?", (project_id,))
    )
    if location_change is not None:
        # What the Location rewrite did, for the panel that asked for it: the
        # labels of the fields rewritten to match, and any spoken field that
        # still names the old place and must be edited by hand.
        result["location_change"] = location_change
    return result

@router.post("/studio/projects/{project_id}/rewrite-hook")
async def suggest_hook_rewrite(
    project_id: str, payload: RewriteHookRequest, user_id: str = Depends(get_current_user_id)
):
    """A clearer hook the founder may accept (ADR 0084). Advisory: writes nothing."""
    require_ai_configured()
    row = await _fetch_one(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?", (project_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Studio project not found")
    original = (payload.hook_line or row.get("hook_line") or "").strip()
    if not original:
        raise HTTPException(status_code=400, detail="Write a hook line first, then ask for a clearer one.")
    profile = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?",
        (row.get("brand_profile_id"), user_id),
    ) if row.get("brand_profile_id") else None
    angle = await _fetch_one(
        "SELECT * FROM content_angles WHERE id = ? AND user_id = ?",
        (row["content_angle_id"], user_id),
    ) if row.get("content_angle_id") else None
    try:
        line = await _log_model_call(
            "hook_rewrite", "text", TEXT_MODEL,
            lambda: ai_service.rewrite_hook_line(
                profile or {}, angle, original, row.get("objective") or ""
            ),
            user_id, studio_project_id=project_id,
        )
    except ai_service.RewriteRefusal as e:
        # Same rule as the line rewrite: a refusal the service named
        # reaches the founder as-is; the generic line is only for
        # provider/network failures.
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Hook rewrite failed: {e}")
        raise HTTPException(
            status_code=502,
            detail="Couldn't write a clearer hook just now. Try again, or edit the line yourself.",
        )
    return {"hook_line": line, "original": original}

@router.post("/studio/projects/{project_id}/rewrite-line")
async def suggest_line_rewrite(
    project_id: str, payload: RewriteLineRequest, user_id: str = Depends(get_current_user_id)
):
    """A clearer version of any spoken line the founder may accept.

    Advisory like the hook rewrite (ADR 0084): writes nothing. The hook
    role runs the hook rewrite unchanged; a middle line is rewritten inside
    the room the rest of the script leaves in the middle's seconds, plus
    the line's own length, which replacing it frees — so an accepted
    suggestion can never lengthen the script, and a shorter one can pull
    an over-ceiling body back under. When no room is left, the refusal
    says to shorten the script first instead of offering a rewrite that
    could never fit.
    """
    require_ai_configured()
    row = await _fetch_one(
        "SELECT * FROM studio_projects WHERE id = ? AND user_id = ?", (project_id, user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="Studio project not found")
    role = str(payload.role or "").strip().lower()
    if role not in ("hook", "middle"):
        raise HTTPException(
            status_code=400,
            detail="Say which line it is — the hook or a script line — then ask for a clearer one.",
        )
    original = (payload.line or "").strip()
    if role == "hook" and not original:
        original = (row.get("hook_line") or "").strip()
    if not original:
        raise HTTPException(status_code=400, detail="Write the line first, then ask for a clearer one.")
    profile = await _fetch_one(
        "SELECT * FROM brand_profiles WHERE id = ? AND user_id = ?",
        (row.get("brand_profile_id"), user_id),
    ) if row.get("brand_profile_id") else None
    angle = await _fetch_one(
        "SELECT * FROM content_angles WHERE id = ? AND user_id = ?",
        (row["content_angle_id"], user_id),
    ) if row.get("content_angle_id") else None
    hook_line = (payload.hook_line or row.get("hook_line") or "").strip()
    script = (payload.script or row.get("script") or "").strip()
    max_chars = 0
    if role == "middle":
        # A missing duration falls back to fifteen seconds, the same reading
        # the craft score gives an old project: it must not be measured
        # against a one-second middle.
        ceiling = check_spoken_story(
            hook_line, script, row.get("hook_seconds") or 3, row.get("duration_seconds") or 15,
        )["script"]["ceiling"]
        # Replacing a line frees the line's own length, so the room is
        # never less than the line itself. The plain remainder alone
        # would leave an over-ceiling body no room at all: each line
        # would get less space than it takes up today, and even a
        # shorter rewrite — the kind that pulls the body back under —
        # would be refused as too long.
        max_chars = max(ceiling - (len(script) - len(original)), len(original))
        if max_chars < 16:
            raise HTTPException(
                status_code=400,
                detail="The rest of the script already fills its seconds — shorten it first, then rewrite this line.",
            )
    try:
        line = await _log_model_call(
            "line_rewrite", "text", TEXT_MODEL,
            lambda: ai_service.rewrite_spoken_line(
                profile or {}, angle, original, role,
                hook_line=hook_line, script=script,
                objective=row.get("objective") or "", max_chars=max_chars,
            ),
            user_id, studio_project_id=project_id,
        )
    except ai_service.RewriteRefusal as e:
        # The model answered but produced no usable clearer line, and its
        # message already names why in the founder's words — surface it.
        # The generic line below stays for provider/network failures,
        # where there is no reason to name.
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Line rewrite failed: {e}")
        raise HTTPException(
            status_code=502,
            detail="Couldn't write a clearer line just now. Try again, or edit the line yourself.",
        )
    return {"line": line, "original": original, "role": role}

@router.post("/studio/projects/{project_id}/plan")
async def generate_plan(
    project_id: str, payload: GeneratePlanRequest, user_id: str = Depends(get_current_user_id)
):
    """
    Generate (or regenerate) the creative plan for a project.

    Gated twice on purpose:
      1. The App Profile must be approved.
      2. A template must be chosen, since the template supplies the creative
         structure the plan adapts.
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

    # The one history that constrains the next draft (ADR 0124): the
    # founder's verdicts on whole finished videos, each with the bundle
    # frozen when the verdict was cast. Per-element thumbs and posted
    # metrics used to travel into this prompt too; neither can say which
    # element made a video work, so both stopped steering — the metrics
    # stay as the founder's record in History and Analytics.
    verdict_feedback = await _verdict_feedback_for_profile(
        row.get("brand_profile_id"), user_id)
    # Recent hook forms constrain the next draft: the model varies the form
    # instead of repeating the last few generations. Wording is data to
    # avoid, never instructions.
    recent_hooks = []
    try:
        recent_rows = await _fetch_all(
            "SELECT hook_line FROM studio_projects WHERE brand_profile_id = ? AND user_id = ? "
            "AND hook_line IS NOT NULL AND TRIM(hook_line) != '' ORDER BY created_at DESC LIMIT 3",
            (row.get("brand_profile_id"), user_id),
        )
        recent_hooks = [str(r.get("hook_line") or "").strip() for r in recent_rows]
    except Exception:
        recent_hooks = []
    # The goal's angle-specific fit reason: the angle kind's curated reason
    # from the library. The render uses it as the goal's angle-specific job
    # line in the plan and strategy prompts.
    goal_rationale = ""
    if angle and objective:
        goal_rationale = template_library.angle_goal_fit_reason(angle.get("kind"), objective) or ""
    # The angle owns where and when the video happens (ADR 0084): a saved look
    # naming another place or time is adjusted before the plan sees it, and the
    # founder is told what changed.
    look = angle_scene.reconcile_look(row.get("visual_direction") or "", angle)
    try:
        plan = await _log_model_call(
            "creative_plan", "text", TEXT_MODEL,
            lambda: _cfg("generate_creative_plan")(
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
                location=(row.get("location") or "").strip(),
                visual_direction=look["visual_direction"],
                # Selfie plans must not write a phone ending into the timeline
                # (ADR 0093); fixed-camera plans may.
                camera_setup=row.get("camera_setup") or "handheld",
                brand_voice=(profile.get("tone_voice") or "").strip(),
                verdict_feedback=verdict_feedback,
                recent_hooks=recent_hooks,
                goal_rationale=goal_rationale,
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
    # Storage must see the same accepted spoken words.
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
             hook_line = ?, script = ?, beat_timeline = ?, location = ?, visual_direction = ?,
             demo_brief = ?, overlays = ?, voice_direction = ?, sound_direction = ?,
             objective = ?,
             duration_seconds = ?, tone = ?, script_version = script_version + 1,
             plan_trimmed_chars = ?, angle_scene_note = ?,
             status = 'draft', updated_at = ?
           WHERE id = ? AND user_id = ?""",
        (plan["hook_line"], plan["script"], json.dumps(plan["beat_timeline"]),
         plan.get("location") or "", plan["visual_direction"], plan["demo_brief"], json.dumps([]),
         plan["voice_direction"], plan["sound_direction"],
         objective, duration, tone or None,
         trimmed_chars, look["note"] or None, now, project_id, user_id),
    )
    # Behavior, both directions. Writing this plan means moving forward with
    # the goal and template behind it, so both are adopted. Overwriting a
    # script that never rendered means dropping it without proceeding, so the
    # orphaned plan and script are abandoned.
    _plan_objective = template_library.normalize_objective(objective or "")
    _plan_kind = ((angle or {}).get("kind") or "").strip()
    if _plan_objective or _plan_kind or row.get("content_angle_id"):
        await _record_behavior(
            "adopted", "goal", user_id,
            brand_profile_id=row.get("brand_profile_id") or "",
            studio_project_id=project_id,
            detail=f"objective={_plan_objective};kind={_plan_kind}")
    if template.get("id"):
        await _record_behavior(
            "adopted", "template", user_id,
            brand_profile_id=row.get("brand_profile_id") or "",
            studio_project_id=project_id,
            template_id=template.get("id"))
    if (row.get("script") or "").strip():
        _old_rendered = await _fetch_one(
            "SELECT id FROM generations WHERE studio_project_id = ?"
            " AND script_version = ? AND user_id = ? LIMIT 1",
            (project_id, int(row.get("script_version") or 0), user_id),
        )
        if not _old_rendered:
            await _record_behavior(
                "abandoned", "plan", user_id,
                brand_profile_id=row.get("brand_profile_id") or "",
                studio_project_id=project_id,
                detail=f"strategy v{int(row.get('strategy_version') or 0)}")
            await _record_behavior(
                "abandoned", "script", user_id,
                brand_profile_id=row.get("brand_profile_id") or "",
                studio_project_id=project_id,
                detail=f"script v{int(row.get('script_version') or 0)}")
    logger.info(
        f"Generated plan for project {project_id} (script v{int(row.get('script_version') or 0) + 1})"
    )
    payload = _public_project(
        await _fetch_one("SELECT * FROM studio_projects WHERE id = ?", (project_id,)),
        brand_name=(profile.get("brand_name") or "").strip(),
    )
    # Review's verdict evidence rides the plan response (ADR 0127): the
    # summary this plan just steered from, shown — never re-derived.
    payload.update(_verdict_summary_payload(verdict_feedback))
    return payload

@router.post("/studio/projects/{project_id}/ready")
async def mark_project_ready(project_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Mark a reviewed project ready for video generation.

    This is the last gate before Phase 5 renders: the script, the presenter
    photo (when the template needs one) and the objective must all be in
    place, so the Generate button never enables on a project that can only
    refuse at the click.
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

    await _execute(
        "UPDATE studio_projects SET status = 'ready_for_generation', "
        "updated_at = ? WHERE id = ? AND user_id = ?",
        (now_iso(), project_id, user_id),
    )
    return _public_project(
        await _fetch_one("SELECT * FROM studio_projects WHERE id = ?", (project_id,)),
        brand_name=(profile.get("brand_name") or "").strip(),
    )

@router.post("/studio/projects/{project_id}/generate", status_code=202)
async def submit_project_generation(
    project_id: str, payload: StudioGenerationRequest, user_id: str = Depends(get_current_user_id),
    request: Request = None,
):
    """
    Generate the complete video as ONE job.

    Refuses unless the project is reviewed and ready.

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
         request_id=(request.state.request_id if request is not None and getattr(request, "state", None) else "") or _request_id(),
     )
    generation["provider_reason"] = video_providers.resolve(payload.model or None)[1]
    return generation

@router.post("/studio/projects/{project_id}/strategy")
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
    _cfg("_refuse_retired_project_assets")(row.get("assets"))

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

    # The strategy prompt learns from the same whole-video verdicts as
    # the plan prompt (ADR 0124) — the founder's calls on finished videos,
    # bundles frozen at verdict time — and from nothing else: per-element
    # thumbs and posted metrics no longer steer either stage.
    verdict_feedback = await _verdict_feedback_for_profile(
        row.get("brand_profile_id"), user_id)

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
            "location": row.get("location") or "",
            "visual_direction": angle_scene.reconcile_look(
                row.get("visual_direction") or "", angle
            )["visual_direction"],
            "voice_direction": row.get("voice_direction") or "",
            "sound_direction": row.get("sound_direction") or "",
            "beat_timeline": row.get("beat_timeline") or [],
        }
    recent_hooks = []
    try:
        recent_rows = await _fetch_all(
            "SELECT hook_line FROM studio_projects WHERE brand_profile_id = ? AND user_id = ? "
            "AND hook_line IS NOT NULL AND TRIM(hook_line) != '' ORDER BY created_at DESC LIMIT 3",
            (row.get("brand_profile_id"), user_id),
        )
        recent_hooks = [str(r.get("hook_line") or "").strip() for r in recent_rows]
    except Exception:
        recent_hooks = []

    # The goal's angle-specific fit reason, for the strategy's ANGLE + GOAL rule.
    goal_rationale = ""
    if angle and objective:
        goal_rationale = template_library.angle_goal_fit_reason(angle.get("kind"), objective) or ""

    try:
        strategy = await _log_model_call(
            "video_strategy", "text", TEXT_MODEL,
            lambda: _cfg("generate_video_strategy")(
                profile=profile,
                template=template,
                angle=angle,
                objective=objective,
                hook_seconds=hook_seconds,
                total_duration=total_duration,
                tone=tone,
                brand_voice=profile.get("tone_voice") or "",
                verdict_feedback=verdict_feedback,
                plan=approved_plan,
                camera_setup=row.get("camera_setup") or "handheld",
                recent_hooks=recent_hooks,
                goal_rationale=goal_rationale,
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

    # The spoken words are rewritten from the founder's approved
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

    # Strategy owns only the generated orbit direction and actor gesture.
    # Zoom timing belongs to processing: start at 70% of hook_seconds and
    # finish about 0.6s later. Never promise generated spoken-word sync.
    strategy = dict(strategy or {})
    strategy["camera_beat"] = normalize_strategy(strategy)["camera_beat"]
    strategy["camera_setup"] = row.get("camera_setup") or "handheld"

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
             updated_at = ?
           WHERE id = ? AND user_id = ?""",
        (json.dumps(strategy), version, script_version_at_build, hook_seconds,
         now, project_id, user_id),
    )
    # Behavior: building the strategy moves forward with the goal behind it,
    # so the goal is adopted. Replacing a strategy that never rendered drops
    # it without proceeding, so the orphaned plan is abandoned.
    _strategy_kind = ((angle or {}).get("kind") or "").strip()
    _strategy_objective = template_library.normalize_objective(objective or "")
    if _strategy_objective or _strategy_kind or row.get("content_angle_id"):
        await _record_behavior(
            "adopted", "goal", user_id,
            brand_profile_id=row.get("brand_profile_id") or "",
            studio_project_id=project_id,
            detail=f"objective={_strategy_objective};kind={_strategy_kind}")
    if int(row.get("strategy_version") or 0) > 0:
        _old_strategy_rendered = await _fetch_one(
            "SELECT id FROM generations WHERE studio_project_id = ?"
            " AND strategy_version = ? AND user_id = ? LIMIT 1",
            (project_id, int(row.get("strategy_version") or 0), user_id),
        )
        if not _old_strategy_rendered:
            await _record_behavior(
                "abandoned", "plan", user_id,
                brand_profile_id=row.get("brand_profile_id") or "",
                studio_project_id=project_id,
                detail=f"strategy v{int(row.get('strategy_version') or 0)}")
    logger.info(
        f"Generated strategy for project {project_id} (v{version}) — hook "
        f"{hook_seconds}s, middle {total_duration - hook_seconds}s, "
        f"{len(strategy.get('segments') or [])} section(s)"
    )
    payload = _public_project(
        await _fetch_one("SELECT * FROM studio_projects WHERE id = ?", (project_id,))
    )
    # The one-pass plan+strategy flow returns this response, so Review's
    # verdict evidence (ADR 0127) rides it the same way it rides the plan.
    payload.update(_verdict_summary_payload(verdict_feedback))
    return payload

@router.post("/studio/projects/{project_id}/plan-and-strategy")
async def generate_plan_and_strategy(
    project_id: str, payload: GeneratePlanAndStrategyRequest, user_id: str = Depends(get_current_user_id)
):
    """
    Write the plan and build the strategy in ONE pass.

    The founder used to wait twice here: generate the plan, read it, then
    wait again while the strategy was built from it — two requests, two
    failure surfaces, for a pair of stages where the second is defined as a
    function of the first's output. This endpoint runs the two existing
    stages back to back server-side and answers once, with the project
    carrying both. Neither stage changed: the plan stage is generate_plan
    (same gates, same prompt, same writes, script_version bump included)
    and the strategy stage is generate_project_strategy, which re-reads the
    row, so the strategy is built from the plan this pass just wrote and is
    stamped current against it.

    One error surface, honestly staged: whichever stage fails is the error
    the founder sees, and the later stage is never attempted on a plan that
    does not exist. If the strategy stage fails, the plan it was building
    from stays written — retrying the pass (or the strategy panel's own
    rebuild) starts from that plan rather than from nothing. Approving
    nothing extra happens here: the App Profile approval gate and the
    template gate are the stages' own, applied in the same order as when
    the founder called them one at a time.
    """
    await generate_plan(
        project_id,
        GeneratePlanRequest(
            objective=payload.objective,
            duration_seconds=payload.duration_seconds,
            tone=payload.tone,
            audience=payload.audience,
        ),
        user_id,
    )
    return await generate_project_strategy(
        project_id,
        GenerateStrategyRequest(
            objective=payload.objective,
            duration_seconds=payload.duration_seconds,
            tone=payload.tone,
            hook_seconds=payload.hook_seconds,
        ),
        user_id,
    )


async def _require_renderable_project(project_id: str, user_id: str) -> tuple:
    """
    Prove a project may be rendered RIGHT NOW, and return (project, profile, template).

    Shared by the fresh-submit path and the retry path. Retry used to load the
    project, profile and template and call _submit_generation directly, which
    meant it inherited none of the checks below. A retry could therefore spend
    real money on a project that had been edited back to draft since, or on an
    App Profile that was no longer approved. Retrying is not a cheaper way
    around the gates; it is the same render, so it answers to the same
    questions.
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
