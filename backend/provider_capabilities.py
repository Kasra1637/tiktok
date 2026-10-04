"""
Compare the video provider catalog against what OpenRouter actually accepts.

Why this exists
---------------
Two providers reached this studio that could not render anything, and both were
found by spending a founder's money on a failed submit rather than by reading a
document:

  - Hailuo 3 Max refuses `input_references` outright, though OpenRouter lists
    the field. Only a live 400 proved it.
  - A HeyGen avatar endpoint 400s any text-driven request unless the caller
    supplies provider.options.heygen.voice_id, then lists candidate voices. The
    studio always renders from the approved script, so that render could never
    succeed.

The second failure was legible in a listing the whole time: that model declared
an EMPTY supported_durations and advertised voice_id under
allowed_passthrough_parameters. Both facts were free to read, before anything was
spent, and neither was checked.

OpenRouter publishes GET /v1/videos/models without authentication. It states,
per model, the durations, resolutions, aspect ratios, frame types, whether
generate_audio is accepted, and which provider-specific passthrough parameters
are allowed. That is the same information which has to be right in
video_providers._CAPABILITY_NOTES, so the two can be compared directly.

This is a WARNING, never a gate
-------------------------------
It runs at startup, logs, and returns. It does not raise, does not block boot,
and does not change which models are offered. A provider narrowing its own
contract mid-session must not be able to take the studio down, and a transient
network failure must never look like a capability problem. The catalog in
video_providers.py stays the authority for what the app sends; this only says
when the two have parted company.
"""
from typing import Optional

import httpx

import video_providers

# Public, unauthenticated, and deliberately short: this runs on the boot path,
# so a slow or hanging provider must not delay the first request.
_MODELS_URL = "https://openrouter.ai/api/v1/videos/models"
_TIMEOUT_SECONDS = 5.0

# Passthrough parameters that are known to be OPTIONAL provider controls rather
# than requirements, so their presence is not drift.
#
# `aigc_watermark` is the case that shaped this list. Both Hailuo entries have
# advertised it since before this check existed, the studio has never sent it,
# and both models render fine — so treating "allows passthrough X" as a warning
# would report both working models on every single boot. A check that always
# fires is a check nobody reads, which is worse than no check at all.
#
# The distinction this module can actually make: a parameter we do not send and
# the provider merely *permits* is not a problem. A parameter the provider
# *requires* shows up as an empty supported_durations or a refusal at submit,
# both of which are already covered above. So anything not listed here is
# surfaced, and adding an entry here is a decision someone has to justify.
_KNOWN_OPTIONAL_PASSTHROUGH = frozenset({"aigc_watermark"})

# Only the fields the studio actually depends on. checked_* below are the
# assertions we make in the catalog; each maps to one field of the live record.
#
# A model absent from the live list is reported too. That is the shape of a
# provider withdrawing a model: still in our catalog, selectable in the
# dropdown, and refused at submit.


def _live_by_id(payload) -> dict:
    """Index the endpoint's data array by model id."""
    rows = (payload or {}).get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    out = {}
    for row in rows:
        if isinstance(row, dict) and row.get("id"):
            out[str(row["id"])] = row
    return out


def compare_catalog_to_live(live: dict) -> list:
    """
    Diff each catalogued model against the live record.

    Returns a list of human-readable warning lines. Empty means no drift.

    Pure and synchronous so it can be tested against a fixture with no network:
    the endpoint call lives in fetch_live_models, not here.
    """
    problems = []
    for key in video_providers.STUDIO_ELIGIBLE:
        cap = video_providers.capability(key)
        model_id = cap.get("id")
        if not model_id:
            problems.append(f"{key}: catalog entry has no provider id")
            continue

        row = live.get(model_id)
        if row is None:
            problems.append(
                f"{key} ({model_id}): no longer listed by OpenRouter. It is still "
                f"selectable, and every render on it will be refused. Remove it from "
                f"STUDIO_ELIGIBLE or pin a different model."
            )
            continue

        # Resolution. The one that costs a render per attempt when wrong.
        ours = cap.get("resolution")
        theirs = row.get("supported_resolutions") or []
        if ours and theirs and ours not in theirs:
            problems.append(
                f"{key} ({model_id}): catalog requests {ours} but OpenRouter now "
                f"lists only {', '.join(theirs)}. Every render would 400."
            )

        # Duration floor/ceiling.
        durations = row.get("supported_durations") or []
        if durations:
            low, high = min(durations), max(durations)
            if cap.get("min_duration", 0) < low:
                problems.append(
                    f"{key} ({model_id}): catalog allows {cap['min_duration']}s but "
                    f"OpenRouter's shortest is {low}s."
                )
            if cap.get("max_duration", 0) > high:
                problems.append(
                    f"{key} ({model_id}): catalog allows {cap['max_duration']}s but "
                    f"OpenRouter's longest is {high}s."
                )
        else:
            problems.append(
                f"{key} ({model_id}): OpenRouter lists NO supported durations. This "
                f"is what a text-driven-only provider looks like from here, and it "
                f"cannot be driven by the studio's script."
            )

        # Frame types. A first_frame we send to a model that accepts none is the
        # Hailuo 3 Max failure in a different field.
        frames = row.get("supported_frame_images")
        if isinstance(frames, list):
            if cap.get("supports_first_frame") and "first_frame" not in frames:
                problems.append(
                    f"{key} ({model_id}): catalog sends the photo as first_frame but "
                    f"OpenRouter lists only {frames or 'none'}."
                )
            if cap.get("supports_last_frame") and "last_frame" not in frames:
                problems.append(
                    f"{key} ({model_id}): catalog claims last_frame support but "
                    f"OpenRouter lists only {frames}."
                )

        # Audio. generate_audio is null when the field is not accepted at all, so
        # supports_native_audio must be False or the studio sends a 400.
        if row.get("generate_audio") is None and cap.get("supports_native_audio"):
            problems.append(
                f"{key} ({model_id}): catalog requests native audio but OpenRouter "
                f"does not list generate_audio for it. Sending it would 400."
            )

        # Passthrough. Nothing is sent today. A model that suddenly REQUIRES one
        # is the Avatar IV shape, and this is the only free warning available --
        # but a parameter the provider merely permits is not drift, so known
        # optional controls are filtered out rather than reported every boot.
        passthrough = [
            p for p in (row.get("allowed_passthrough_parameters") or [])
            if p not in _KNOWN_OPTIONAL_PASSTHROUGH
        ]
        if passthrough:
            problems.append(
                f"{key} ({model_id}): OpenRouter now allows provider passthrough "
                f"({', '.join(passthrough)}). The studio sends none, so if any is "
                f"required this model will refuse every render."
            )

    return problems


async def fetch_live_models() -> Optional[dict]:
    """
    GET the public model list, or None if it cannot be read.

    No API key: this endpoint is unauthenticated, which is the point — the check
    has to be runnable in any environment, including one with no OpenRouter
    credentials at all.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.get(_MODELS_URL)
            if resp.status_code != 200:
                return None
            payload = resp.json()
            return payload if isinstance(payload, dict) else None
    except Exception:
        # A network blip, a proxy, a DNS failure: none of that is drift.
        return None


async def check_provider_drift() -> list:
    """
    Read the live list and log anything that disagrees with our catalog.

    Returns the warning lines so a caller (or a test) can see them; the caller
    is expected to ignore the value. Never raises.
    """
    payload = await fetch_live_models()
    if payload is None:
        return []

    problems = compare_catalog_to_live(_live_by_id(payload))
    if problems:
        import logging
        log = logging.getLogger("provider_capabilities")
        log.warning(
            "Video provider catalog disagrees with OpenRouter on %d point(s). "
            "Each one means a render can fail after the founder has committed to "
            "spending:",
            len(problems),
        )
        for line in problems:
            log.warning("  %s", line)
    return problems