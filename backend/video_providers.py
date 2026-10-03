"""
Video provider capability layer.

The application must not be coupled to one video model. Everything the rest
of the codebase needs to know about a provider lives here as data: what it
can produce, how long it can produce it for, and whether it is available
right now. Swapping providers is an environment change, not a redesign.

Capability records are derived from ai_service.VIDEO_MODELS so there is one
source of truth for model ids, and enriched with the planning facts the
studio needs (vertical support, reference limits, audio).

Configuration (all optional):
    VIDEO_MODEL_DEFAULT   model key to use when none is requested
    VIDEO_MODEL_ALLOWLIST comma-separated keys the app may use; anything else
                          is refused so a bad config cannot silently route
                          spend to an unvetted model
"""

import functools
import logging
import os
import shutil
from typing import Optional

from ai_service import VIDEO_MODELS

logger = logging.getLogger(__name__)

# Factual limits of each provider, kept here so the studio can plan around
# them instead of discovering them from a failed generation.
#
# max_duration: longest single coherent generation. Anything longer needs a
# second job, which is why the studio warns instead of silently truncating.
# supports_combined_refs: whether one request can carry both a first-frame
# image and other references. False means we must pick one.
_CAPABILITY_NOTES = {
    "minimax-h3": {
        "vertical": True,
        "max_reference_images": 9,
        "max_reference_videos": 3,
        "max_reference_audio": 3,
        "supports_first_frame": True,
        "supports_last_frame": False,
        "notes": (
            "2K, native audio, 5-15s per generation. Cannot combine "
            "frame_images with input_references in one request. Durations "
            "above 15s need a second job."
        ),
    },
    "minimax-h3-max": {
        "vertical": True,
        # Proven REFUSED live: the serving provider 400s input_references with
        # "does not support image input references", even though OpenRouter
        # lists the field for this model. The count below is input_references
        # capacity specifically, so it is 0 — accepts_identity_reference() must
        # not read it as permission to send any. Identity rides as the opening
        # frame instead (documented supported: https URL or base64 data URL),
        # which _submit_generation selects via identity_via_first_frame.
        "max_reference_images": 0,
        "max_reference_videos": 3,
        "max_reference_audio": 3,
        "supports_first_frame": True,
        "supports_last_frame": True,
        "identity_via_first_frame": True,
        "notes": (
            "768p (not 2K), 5-15s per generation. Faster than Hailuo 3 with "
            "tighter prompt adherence, which makes it useful for testing a "
            "script quickly. Picture is softer, and native audio is not "
            "requested because the provider does not document the flag for "
            "this model. Your photo opens the video as its first frame rather "
            "than riding alongside as a reference image. Opt-in: Hailuo 3 is "
            "still the default."
        ),
    },
    "aleph-2": {
        "vertical": True,
        "max_reference_images": 0,
        "max_reference_videos": 1,
        "max_reference_audio": 0,
        "supports_first_frame": False,
        "supports_last_frame": False,
        "notes": (
            "In-context video EDITOR, not a generator: it edits a supplied "
            "clip and preserves everything the prompt does not name. Cannot "
            "create a video from a prompt, and has no native audio. Retained "
            "for the legacy exact-match flow only; not usable by the studio."
        ),
    },
}

# Providers the template workflow can actually drive. Aleph is excluded
# because it edits an existing clip, which is exactly the dependency the
# template workflow removed. Any other configured key resolves back to the
# default with a logged reason.
#
# H3 Max sits alongside H3 rather than replacing it: both are generative and
# both take the same face reference, so the founder can render the same script
# on either and compare. Order here does not decide the default — that is
# ai_service.DEFAULT_VIDEO_MODEL, and it stays Hailuo 3. Listing a second model
# only makes it selectable in the studio's model dropdown.
STUDIO_ELIGIBLE = ("minimax-h3", "minimax-h3-max")

# The hook length used when nothing states one. 5s is the lowest length the
# current provider can render, so it needs no trim; a template's own
# hook_seconds overrides this wherever one is set.
DEFAULT_HOOK_SECONDS = 5

# Hook lengths the studio works with. 2s to 4s are below the provider's
# render floor and are therefore always delivered as a trim, which the UI says
# out loud rather than presenting them as native.
HOOK_LENGTH_CHOICES = (2, 3, 4, 5, 6)

_FALLBACK_NOTES = {
    "vertical": True,
    "max_reference_images": 5,
    "max_reference_videos": 1,
    "max_reference_audio": 1,
    "supports_first_frame": True,
    "supports_last_frame": False,
    "notes": "Unrecognised provider; conservative limits applied.",
}


def _allowlist() -> list:
    raw = (os.environ.get("VIDEO_MODEL_ALLOWLIST") or "").strip()
    if not raw:
        return list(STUDIO_ELIGIBLE)
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    valid = [k for k in keys if k in VIDEO_MODELS]
    if len(valid) != len(keys):
        dropped = sorted(set(keys) - set(valid))
        logger.warning("VIDEO_MODEL_ALLOWLIST contains unknown model keys, ignoring: %s", dropped)
    return valid or list(STUDIO_ELIGIBLE)


def default_model_key() -> str:
    """
    The provider used when a caller does not name one.

    Resolves in order: the VIDEO_MODEL_DEFAULT env var, then the app's
    long-standing default (ai_service.DEFAULT_VIDEO_MODEL), then the first
    allowed model. This keeps the existing behaviour the team chose while
    still letting the provider be switched with an environment change alone.
    """
    from ai_service import DEFAULT_VIDEO_MODEL

    allowed = _allowlist()
    configured = (os.environ.get("VIDEO_MODEL_DEFAULT") or "").strip()
    if configured:
        if configured in VIDEO_MODELS and configured in allowed:
            return configured
        logger.warning(
            "VIDEO_MODEL_DEFAULT=%s is not a usable provider; ignoring it.", configured
        )
    if DEFAULT_VIDEO_MODEL in allowed and is_studio_eligible(DEFAULT_VIDEO_MODEL):
        return DEFAULT_VIDEO_MODEL
    return allowed[0] if allowed else DEFAULT_VIDEO_MODEL


def is_known(key: str) -> bool:
    return bool(key) and key in VIDEO_MODELS


def is_allowed(key: str) -> bool:
    return is_known(key) and key in _allowlist()


def is_studio_eligible(key: str) -> bool:
    """Whether the template studio can drive this provider.

    Editors (Aleph) are excluded: they need an existing source clip, which
    the template workflow deliberately does not have.
    """
    if not is_allowed(key):
        return False
    return not VIDEO_MODELS[key].get("is_video_editor", False)


def accepts_identity_reference(key: str) -> bool:
    """Whether the provider can take the founder's identity image at all.

    MiniMax H3 accepts up to 9 reference images as input_references with no
    source video. Hailuo 3 Max refuses input_references outright (proven live:
    the serving provider 400s it), but takes the photo as the opening frame,
    so it still accepts the identity — through a different field, selected by
    identity_via_first_frame. Editors (Aleph) need a real clip to edit — the
    template workflow has none — so they are refused here too.
    """
    if not is_known(key):
        return False
    cap = capability(key)
    if cap.get("is_video_editor", False):
        return False
    if cap.get("identity_via_first_frame"):
        return True
    return int(cap.get("max_reference_images", 0) or 0) > 0


def capability(key: Optional[str] = None) -> dict:
    """
    Full capability record for a provider.

    Never raises for an unknown key: it falls back to the configured default
    so a stale model id in the database degrades to a working generation
    rather than a 500.
    """
    key = key if is_known(key) else default_model_key()
    base = VIDEO_MODELS[key]
    notes = _CAPABILITY_NOTES.get(key, _FALLBACK_NOTES)
    return {
        "key": key,
        "id": base["id"],
        "name": base["name"],
        "description": base.get("description", ""),
        "min_duration": base.get("min_duration", 1),
        "max_duration": base.get("max_duration", 30),
        "resolution": base.get("resolution", "1080p"),
        "supports_references": base.get("supports_references", False),
        "supports_native_audio": base.get("supports_native_audio", False),
        "supports_v2v_motion": base.get("supports_v2v_motion", False),
        "supports_combined_refs": base.get("supports_combined_refs", False),
        "is_video_editor": base.get("is_video_editor", False),
        **notes,
    }


def list_capabilities(include_ineligible: bool = False) -> list:
    """Capability records for every provider the app may use."""
    keys = _allowlist() if not include_ineligible else list(VIDEO_MODELS)
    out = []
    for key in keys:
        if not is_known(key):
            continue
        cap = capability(key)
        if not include_ineligible and not is_studio_eligible(key):
            continue
        cap["available"] = True
        cap["studio_eligible"] = is_studio_eligible(key)
        out.append(cap)
    return out


def resolve(key: Optional[str] = None) -> tuple:
    """
    Pick the provider to use and explain the choice.

    Returns (model_key, reason). An explicitly requested, allowed, eligible
    model wins. An explicit request that is not usable falls back to the
    default WITH a reason, because silently generating with a different
    model would make cost and quality non-reproducible.
    """
    allowed = _allowlist()
    default = default_model_key()

    if not key:
        return default, f"default provider ({default})"

    if not is_known(key):
        return default, f"unknown provider {key!r}; using {default}"

    # Report the editor limitation before the allowlist, because "cannot
    # generate from a prompt" is the actionable reason for an editor model.
    if VIDEO_MODELS[key].get("is_video_editor", False):
        return default, (
            f"{key} edits an existing clip and cannot generate from a prompt; using {default}"
        )

    if key not in allowed:
        return default, f"{key} is not in VIDEO_MODEL_ALLOWLIST; using {default}"

    return key, f"requested provider {key}"


# Continuity anchors, ordered strongest-first. A provider can only carry so
# much, so the order IS the priority rule: when a limit forces a choice, the
# earliest anchor is the one that survives.
#
#   frame  — the previous clip's final frame, sent as the next clip's first
#            frame. Pins the exact pose, framing, lighting and wardrobe at the
#            seam, and because the face is already in that frame it also
#            carries identity for free.
#   clip   — the previous clip itself as a video reference, so the model can
#            read the motion, pacing and performance rhythm that led into the
#            seam rather than having to be told them.
#   identity— the founder's original character_reference image. Strongest
#            identity signal on its own, but the weakest continuity signal: it
#            says who the person is, never where the last shot ended.
#
# This ordering is why a provider that can only take one anchor takes the frame
# and not the face: a bridge frame is both a continuity anchor AND an identity
# anchor, while a face reference is only the latter.
CONTINUITY_ANCHOR_ORDER = ("frame", "clip", "identity")

# What we are actually able to promise the founder, derived from what was
# attached rather than from what was requested.
CONTINUITY_GUARANTEES = {
    "frame_exact": (
        "The next clip opens on the previous clip's final frame, so the seam is "
        "frame-identical. The model animates forward from a real frame of the "
        "approved video rather than re-imagining the scene."
    ),
    "frame_exact_plus_refs": (
        "The next clip opens on the previous clip's final frame AND carries the "
        "previous clip and the character reference alongside it, so identity, "
        "wardrobe and motion continuity are all anchored at the seam."
    ),
    "text_only": (
        "This provider cannot receive the previous clip as a visual anchor, so "
        "continuity is carried by the written scene lock only. The character and "
        "setting are re-described rather than reproduced pixel-for-pixel, and "
        "the result may not match the approved hook exactly."
    ),
}


def continuity_plan(
    key: Optional[str],
    has_bridge_frame: bool = False,
    has_parent_clip_url: bool = False,
    has_character_reference: bool = False,
) -> dict:
    """
    Decide which continuity anchors a provider can carry, and say what it lost.

    This is the single source of truth for continuity. Both the prompt builder
    and the submission path read it, so the prompt can never claim a level of
    continuity the request does not actually deliver — which is the difference
    between an extension that continues a video and one that quietly becomes a
    different clip with a similar prompt.

    Every anchor that was wanted but not attached is returned in `degraded`
    with the reason, so the caller can surface it instead of pretending.

    Args:
        key: provider key.
        has_bridge_frame: the previous clip's final frame could be extracted.
        has_parent_clip_url: the previous clip is reachable over public HTTPS.
        has_character_reference: a character_reference asset is attached.

    Returns:
        {
          "provider", "provider_name", "guarantee", "notes",
          "use_frame", "use_clip_reference", "use_identity_reference",
          "wanted": [...], "attached": [...], "degraded": [{"anchor", "reason"}],
        }
    """
    # An editor is rejected here, BEFORE resolve() normalizes it away, because
    # resolve() falls back to a generator and would otherwise hide the real
    # problem: an editor cannot produce the next segment at all, no matter how
    # many anchors it is offered.
    if key and is_known(key) and VIDEO_MODELS[key].get("is_video_editor", False):
        editor = capability(key)
        return {
            "provider": key,
            "provider_name": editor["name"],
            "guarantee": "unsupported",
            "notes": (
                f"{editor['name']} is a video editor, not a generator. It cannot produce the "
                "next segment of a chain. Choose a generative provider for the influencer "
                "workflow."
            ),
            "use_frame": False,
            "use_clip_reference": False,
            "use_identity_reference": False,
            "wanted": ["frame", "clip", "identity"],
            "attached": [],
            "degraded": [
                {
                    "anchor": anchor,
                    "reason": f"{editor['name']} edits an existing clip and cannot generate a new segment.",
                }
                for anchor in ("frame", "clip", "identity")
            ],
        }

    model_key, _resolve_reason = resolve(key)
    cap = capability(model_key)

    wanted: list = []
    if has_bridge_frame:
        wanted.append("frame")
    if has_parent_clip_url:
        wanted.append("clip")
    if has_character_reference:
        wanted.append("identity")

    use_frame = False
    use_clip = False
    use_identity = False
    degraded: list = []

    def drop(anchor: str, reason: str) -> None:
        degraded.append({"anchor": anchor, "reason": reason})

    if not wanted:
        return {
            "provider": model_key,
            "provider_name": cap["name"],
            "guarantee": "single_segment",
            "notes": (
                "Nothing to continue from — this is the opening segment, so no continuity "
                "anchor is needed. Identity is carried by the character reference alone."
                if has_character_reference
                else "Nothing to continue from, and no character reference is attached."
            ),
            "use_frame": False,
            "use_clip_reference": False,
            "use_identity_reference": bool(has_character_reference) and accepts_identity_reference(model_key),
            "wanted": wanted,
            "attached": (
                ["identity"] if has_character_reference and accepts_identity_reference(model_key) else []
            ),
            "degraded": (
                []
                if has_character_reference or accepts_identity_reference(model_key)
                else [{"anchor": "identity", "reason": f"{cap['name']} cannot accept reference images."}]
            ),
        }

    # A bridge frame is the whole ballgame. Without it there is nothing to
    # continue from, and saying so is the difference between an honest
    # text-only warning and a silently different character.
    if not has_bridge_frame:
        # The seam frame is a CONTINUITY anchor. Its absence says nothing about
        # the identity reference, which is attached independently below, so
        # `identity` is never degraded here.
        #
        # Degrading it anyway was worse than cosmetic. build_segment_prompt()
        # copies `degraded` into the prompt, so the HOOK request told the model
        # the character reference had not arrived — in the very request that
        # carried it. That is a self-inflicted likeness loss on the one segment
        # the founder judges first.
        for anchor in wanted:
            if anchor == "identity":
                continue
            drop(
                anchor,
                "The previous clip's final frame could not be extracted, so there is no "
                "visual seam to continue from. Continuity is text-only and the scene may "
                "be re-imagined.",
            )
        attached = []
        if has_character_reference and accepts_identity_reference(model_key):
            use_identity = True
            attached = ["identity"]

        # Downgrade the guarantee only when something was genuinely lost. An
        # opening segment has no previous clip by definition, so its absent seam
        # is not a degradation — and calling it one raised a destructive
        # "text-only" warning on the first segment, where nothing is wrong.
        if degraded:
            guarantee = "text_only"
            notes = CONTINUITY_GUARANTEES["text_only"]
        else:
            guarantee = "single_segment"
            notes = (
                "Nothing to continue from, so there is no seam to pin. Identity is carried "
                "by the character reference alone."
                if attached
                else "Nothing to continue from, so there is no seam to pin."
            )

        return {
            "provider": model_key,
            "provider_name": cap["name"],
            "guarantee": guarantee,
            "notes": notes,
            "use_frame": False,
            "use_clip_reference": False,
            "use_identity_reference": use_identity,
            "wanted": wanted,
            "attached": attached,
            "degraded": degraded,
        }

    use_frame = True
    attached = ["frame"]

    # Can this provider also carry the other two references?
    if cap.get("supports_combined_refs"):
        if has_parent_clip_url:
            use_clip = True
            attached.append("clip")
        if has_character_reference and accepts_identity_reference(model_key):
            use_identity = True
            attached.append("identity")
        if has_character_reference and not accepts_identity_reference(model_key):
            drop("identity", f"{cap['name']} cannot accept reference images.")
        return {
            "provider": model_key,
            "provider_name": cap["name"],
            "guarantee": "frame_exact_plus_refs",
            "notes": CONTINUITY_GUARANTEES["frame_exact_plus_refs"],
            "use_frame": use_frame,
            "use_clip_reference": use_clip,
            "use_identity_reference": use_identity,
            "wanted": wanted,
            "attached": attached,
            "degraded": degraded,
        }

    # One anchor only. The frame wins on the ordering above, and it already
    # contains the face, so dropping the identity reference costs less than it
    # appears to — but it is still a real limitation and is reported as one.
    if not cap.get("supports_last_frame"):
        use_frame = False
        drop(
            "frame",
            f"{cap['name']} reports no last-frame/first-frame continuation support, so the "
            "seam frame cannot be pinned even though it was extracted.",
        )
    else:
        if has_parent_clip_url:
            drop(
                "clip",
                f"{cap['name']} cannot combine a first-frame image with video references in one "
                "request. The seam frame was kept because it pins the scene and the identity at once.",
            )
        if has_character_reference:
            drop(
                "identity",
                f"{cap['name']} accepts one visual anchor per request, and the seam frame already "
                "carries the founder's face. The separate character reference was not sent.",
            )

    if not use_frame:
        # This provider will not pin a seam frame, so fall back to whatever
        # single anchor it does accept. The promise drops to text_only because
        # the model is being asked to reproduce a scene it cannot see.
        attached = []
        if has_parent_clip_url and int(cap.get("max_reference_videos", 0) or 0) > 0:
            use_clip = True
            attached.append("clip")
        if has_character_reference and accepts_identity_reference(model_key):
            if not use_clip:
                use_identity = True
                attached.append("identity")
            else:
                drop(
                    "identity",
                    f"{cap['name']} takes one anchor per request; the previous clip was kept "
                    "because it carries both identity and continuity.",
                )
        return {
            "provider": model_key,
            "provider_name": cap["name"],
            "guarantee": "text_only",
            "notes": CONTINUITY_GUARANTEES["text_only"],
            "use_frame": use_frame,
            "use_clip_reference": use_clip,
            "use_identity_reference": use_identity,
            "wanted": wanted,
            "attached": attached,
            "degraded": degraded,
        }

    return {
        "provider": model_key,
        "provider_name": cap["name"],
        "guarantee": "frame_exact",
        "notes": CONTINUITY_GUARANTEES["frame_exact"],
        "use_frame": use_frame,
        "use_clip_reference": False,
        "use_identity_reference": False,
        "wanted": wanted,
        "attached": attached,
        "degraded": degraded,
    }


def resolve_length(target: Optional[int], model_key: Optional[str] = None) -> dict:
    """
    Reconcile a wanted segment length with what a provider can actually render.

    These are genuinely different numbers and the gap is not small: the
    provider's minimum render length is 5s, while the hook a template
    declares (and the product promises) is 2-3s. So a 3-second hook is not
    something that can be RENDERED - it is something that has to be rendered
    longer and then cut down.

    Applies to the hook and to extensions alike; it was originally written for
    the hook only, and the misleading name is a fair part of why a 2-4s hook
    read as a contradiction against a 10s minimum.

    Returns:
        {
          "target": int,             # what was asked for
          "render_seconds": int,     # what we must ask the model for
          "trim_to": int,            # what we cut the render down to (0 = none)
          "guarantee": "as_rendered" | "trimmed" | "clamped_down" | "trim_unavailable",
          "provider", "provider_name", "note": str, "adjustments": [str],
        }

    `trim_unavailable` is returned when a trim is required but ffmpeg is not on
    PATH, so the caller can say so BEFORE spending a paid render rather than
    discovering it afterwards and silently handing back a 4s clip for a 3s
    request.
    """
    model_key, _reason = resolve(model_key)
    cap = capability(model_key)

    # 0 is the "not chosen yet" sentinel on studio_projects.hook_seconds, so it
    # has to mean the same as None here — otherwise a cleared choice silently
    # becomes a 1-second hook.
    if target in (None, "", 0):
        want = DEFAULT_HOOK_SECONDS
    else:
        try:
            want = int(target)
        except (TypeError, ValueError):
            want = DEFAULT_HOOK_SECONDS
    # Kept for the "you asked for X" wording, since `want` is mutated below.
    requested = want
    adjustments: list = []

    ceiling = cap["max_duration"]
    floor = cap["min_duration"]
    clamped_down = False
    if want > ceiling:
        adjustments.append(
            f"{cap['name']} renders at most {ceiling}s, so a {want}s hook was "
            f"requested at {ceiling}s."
        )
        want = ceiling
        clamped_down = True
    if want < 1:
        want = 1

    render_seconds = max(want, floor)
    trim_to = want if render_seconds > want else 0

    if trim_to:
        adjustments.append(
            f"{cap['name']} cannot render under {floor}s, so the hook is rendered at "
            f"{render_seconds}s and cut down to {trim_to}s."
        )

    if trim_to:
        guarantee = "trimmed"
    elif clamped_down:
        guarantee = "clamped_down"
    else:
        guarantee = "as_rendered"

    if trim_to and not ffmpeg_available():
        guarantee = "trim_unavailable"
        note = (
            f"A {trim_to}s clip needs a re-encode to cut it down, but ffmpeg is not "
            f"available on this host. It would come back at {render_seconds}s. "
            f"Install ffmpeg, or choose {floor}s or longer."
        )
    elif trim_to:
        note = (
            f"Delivered as a {trim_to}s clip, cut from a {render_seconds}s render "
            f"because {cap['name']} cannot render under {floor}s."
        )
    elif clamped_down:
        note = (
            f"{cap['name']} renders at most {ceiling}s, so this is {ceiling}s "
            f"rather than the {requested}s that was asked for."
        )
    else:
        note = f"Rendered directly at {render_seconds}s; no trimming needed."

    return {
        "target": want,
        "render_seconds": render_seconds,
        "trim_to": trim_to,
        "guarantee": guarantee,
        "provider": model_key,
        "provider_name": cap["name"],
        "note": note,
        "adjustments": adjustments,
    }


# Kept so existing callers and tests keep working. The function is not
# hook-specific any more: extensions resolve their length the same way, and a
# "hook" name on a function serving both is how the 3-vs-4s confusion started.
resolve_hook_length = resolve_length


@functools.lru_cache(maxsize=1)
def ffmpeg_available() -> bool:
    """
    Whether ffmpeg is on PATH.

    Cached because it cannot change during a process's life, and it is consulted
    on every hook render.
    """
    return shutil.which("ffmpeg") is not None


def plan_duration(key: Optional[str], requested: int) -> dict:
    """
    Fit a requested duration to what the provider can actually do.

    Returns:
        {
          "model": key,
          "requested_seconds": int,
          "primary_seconds": int,     # what the single job will render
          "needs_extension": bool,     # a second job is required
          "extension_seconds": int,    # remaining length for that job
          "adjustments": [str],        # human-readable reasons
        }

    A second job is only ever planned when the duration genuinely exceeds the
    provider's single-pass limit, never for preference or padding.
    """
    model_key, reason = resolve(key)
    cap = capability(model_key)
    want = int(requested or cap["max_duration"])
    ceiling = cap["max_duration"]
    floor = cap["min_duration"]

    adjustments = []
    if reason and not reason.startswith("requested"):
        adjustments.append(reason)

    primary = want
    if primary > ceiling:
        primary = ceiling
        adjustments.append(
            f"{cap['name']} generates at most {ceiling}s in one pass; "
            f"{want}s needs a second job for the remainder."
        )
    if primary < floor:
        primary = floor
        adjustments.append(f"{cap['name']} cannot go below {floor}s; raised to {floor}s.")

    extension = max(0, want - primary)
    return {
        "model": model_key,
        "requested_seconds": want,
        "primary_seconds": primary,
        "needs_extension": extension > 0,
        "extension_seconds": extension,
        "adjustments": adjustments,
    }


def clamp_for_single_pass(key: Optional[str], requested: int) -> int:
    """Duration a single job can cover, ignoring any remainder."""
    return plan_duration(key, requested)["primary_seconds"]
