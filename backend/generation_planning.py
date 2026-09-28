"""
Planning for a single-pass video generation.

Three jobs live here, all pure functions so they can be tested without a
network or a model:

- build_single_pass_prompt(): turns a reviewed creative plan into ONE prompt
  that covers the hook AND its continuation, so the video is a single
  coherent take rather than two unrelated clips.
- extract_cost(): reads cost out of whatever shape OpenRouter returns.
- is_recoverable_error(): decides whether a failure is worth retrying.

The prompt contract matters for the product rule that the model must never
render app UI, small text, pricing, or logos — those are composited
deterministically afterwards from real assets. The model is told to leave
clean space for them instead of inventing an interface.
"""
from typing import Optional

# Words the model must not attempt to draw. Listed so the instruction can be
# explicit rather than relying on the model inferring "don't fake the UI".
_UI_RENDERING_WARNING = (
    "Do NOT draw or render: app interface elements, app screenshots, button "
    "labels, prices, ratings, review counts, download counts, logos, or any "
    "small on-screen text. Those are composited afterwards from real app "
    "assets. Leave clean, uncluttered space where they will be placed."
)


def _format_beats(beats, duration: int) -> str:
    if not beats:
        return (
            f"- 0-3s: hook — {duration}s total video, hook in the first 3 seconds\n"
            f"- 3-8s: problem or transition\n"
            f"- 8-{max(8, duration - 3)}s: app demonstration and payoff\n"
            f"- final {max(2, min(4, duration // 6))}s: call to action"
        )
    lines = []
    for beat in beats[:10]:
        try:
            start = float(beat.get("start", 0))
            end = float(beat.get("end", start + 1))
        except (TypeError, ValueError):
            continue
        label = str(beat.get("label") or "beat").strip()
        text = str(beat.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"- {start:g}-{end:g}s [{label}]: {text}")
    return "\n".join(lines) or f"- 0-{duration}s: one continuous take"


def _format_overlays(overlays) -> str:
    if not overlays:
        return "- (no on-screen text planned)"
    lines = []
    for item in overlays[:8]:
        if isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            try:
                span = f"{float(item.get('start', 0)):g}-{float(item.get('end', 0)):g}s"
            except (TypeError, ValueError):
                span = "timed"
            lines.append(f"- {span}: {text}")
        elif isinstance(item, str) and item.strip():
            lines.append(f"- {item.strip()}")
    return "\n".join(lines) or "- (no on-screen text planned)"


def build_single_pass_prompt(
    plan: dict,
    profile: dict,
    template: Optional[dict] = None,
    duration: int = 20,
    segment: str = "full",
    asset_notes: str = "",
    is_extension: bool = False,
) -> str:
    """
    Build the prompt for ONE coherent generation covering the whole video.

    Args:
        plan: the reviewed studio plan (hook_line, script, beats, overlays...).
        profile: the approved App Profile, used only to keep the product name
            and category accurate in any spoken or depicted context.
        template: the hook template, for visual style and pacing direction.
        duration: seconds this generation must cover.
        segment: "full" for the primary generation, or "extension" when this
            job continues a previous one.
        asset_notes: what real assets will be composited afterwards, so the
            model leaves appropriate room.
        is_extension: True when continuing a longer video. The prompt then
            asks the model to continue seamlessly rather than open cold.
    """
    app_name = (profile or {}).get("brand_name") or "the app"
    hook = (plan.get("hook_line") or "").strip()
    script = (plan.get("script") or "").strip()
    cta = (plan.get("cta") or "").strip()
    visual = (plan.get("visual_direction") or "").strip()
    voice = (plan.get("voice_direction") or "").strip()
    sound = (plan.get("sound_direction") or "").strip()
    feature = (plan.get("feature_emphasis") or "").strip()
    tpl = template or {}
    tone = (plan.get("tone") or tpl.get("tone") or "").strip()

    sections = []

    sections.append(
        f"Create ONE continuous {duration}-second vertical (9:16) promotional video "
        f"for the mobile app {app_name}. It must be a single coherent take containing "
        f"both the opening hook and its continuation, with no visible cut to a separate clip, "
        f"no black frames, and no title card."
    )

    if is_extension:
        sections.append(
            "This clip CONTINUES an existing video. Open exactly as the previous clip "
            "ended, matching its subject, framing, lighting, and motion. Do not re-introduce "
            "the app or repeat the hook; move straight into the payoff and the call to action."
        )
    else:
        sections.append(
            f"The first 3 seconds are the hook and must land immediately: {hook or 'open on the strongest visual beat'}."
        )

    if script:
        sections.append(f"Spoken script, performed naturally on camera or as voiceover:\n\"{script}\"")

    sections.append(
        "Beat-by-beat timeline — follow these timings:\n" + _format_beats(plan.get("beat_timeline"), duration)
    )

    sections.append(
        "On-screen text will be added afterwards. Plan clean space for these, and do not "
        "render the text yourself:\n" + _format_overlays(plan.get("overlays"))
    )

    if visual:
        sections.append(f"Visual direction: {visual}")
    if feature:
        sections.append(f"The single feature being demonstrated: {feature}. Show it in use, not described.")
    if tpl.get("visual_style"):
        sections.append(f"Visual style: {tpl['visual_style']}")
    if tpl.get("camera_pacing") or tpl.get("continuation_structure"):
        pacing = " ".join(p for p in (tpl.get("camera_pacing"), tpl.get("continuation_structure")) if p)
        sections.append(f"Camera and pacing: {pacing}")
    if voice:
        sections.append(f"Voice direction: {voice}")
    if tone:
        sections.append(f"Tone: {tone}")
    if sound:
        sections.append(
            f"Sound direction: {sound}. Use only original or licensed audio; "
            f"do not reference or imitate a specific commercial recording."
        )
    if cta:
        sections.append(f"End on the call to action: {cta}")

    sections.append(_UI_RENDERING_WARNING)

    if asset_notes:
        sections.append(f"Real app assets that will be composited over this footage: {asset_notes}")

    person_anchor = person_anchor_notes(plan.get("assets") or [])
    if person_anchor:
        sections.append(person_anchor)

    sections.append(
        "Keep one consistent person, hand, or subject for the entire clip. Vertical framing "
        "throughout. The result must look like a single real take, not an edit."
    )

    return "\n\n".join(sections)


def extract_cost(response: dict) -> tuple:
    """
    Pull a USD cost out of an OpenRouter response.

    Returns (cost_usd_or_None, source_label). OpenRouter has moved this
    between `usage.cost`, `data.usage.cost`, and a top-level `cost`, and not
    every response includes it at all, so every shape is probed and an
    explicit "unavailable" is returned rather than a silent zero — a hard 0.0
    would read as "free" in the analytics.
    """
    if not isinstance(response, dict):
        return None, "unavailable"

    cost_keys = ("cost", "total_cost", "cost_usd")

    def pick(node):
        if not isinstance(node, dict):
            return None
        for key in cost_keys:
            value = node.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
                return float(value)
        return None

    # Each probe is (container, label); the container is where the cost keys
    # are expected to live directly.
    probes = [
        (response.get("usage"), "usage.cost"),
        (
            response.get("data", {}).get("usage") if isinstance(response.get("data"), dict) else None,
            "data.usage.cost",
        ),
        (response, "cost"),
    ]
    for container, label in probes:
        value = pick(container)
        if value is not None:
            return value, label

    return None, "unavailable"


def is_recoverable_error(message: str) -> bool:
    """
    Whether retrying the same request could plausibly succeed.

    Rate limits, timeouts, and 5xx are worth another attempt. A rejected
    prompt, an unsupported parameter, or a content-policy refusal is not —
    retrying burns money and always fails the same way.
    """
    if not message:
        return False
    text = message.lower()
    permanent_markers = (
        "content policy",
        "content_policy",
        "safety",
        "moderation",
        "unsupported",
        "invalid parameter",
        "invalid_parameter",
        "validation",
        "not found (404)",
        "expired",
        "prompt is too long",
    )
    if any(marker in text for marker in permanent_markers):
        return False
    recoverable_markers = (
        "timeout",
        "timed out",
        "429",
        "rate limit",
        "500",
        "502",
        "503",
        "504",
        "temporarily",
        "overloaded",
        "connection",
        "eof occurred",
    )
    return any(marker in text for marker in recoverable_markers)


def person_anchor_notes(assets: list) -> str:
    """
    Return a prompt section locking the on-camera person to the project's
    attached character reference, or "" when none is attached.

    The reference image itself rides along as a model input (see server.py's
    _submit_generation, which passes it as an input_references identity
    guide). This text tells the model what that image IS: the exact person
    who must appear on camera. First matching character_reference asset wins —
    attach only one per project.
    """
    if not assets:
        return ""
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if str(asset.get("kind") or "").strip().lower() != "character_reference":
            continue
        label = str(asset.get("name") or asset.get("label") or "the attached character reference").strip()
        return (
            "The person on camera must be the exact individual in the attached "
            f"character reference image ({label}): same face, same appearance, "
            "same age. Do not invent a different person, and do not describe or "
            "alter them. They star in every scene from opening to call to action."
        )
    return ""


def asset_notes(assets: list) -> str:
    """
    Summarise attached assets for the prompt.
    Only names and kinds are described: the point is to tell the model what
    will be laid over the footage so it composes around it.
    """
    if not assets:
        return ""
    parts = []
    for asset in assets[:8]:
        if not isinstance(asset, dict):
            continue
        kind = str(asset.get("kind") or asset.get("type") or "asset").strip()
        label = str(asset.get("name") or asset.get("label") or "").strip()
        parts.append(f"{kind}{f' ({label})' if label else ''}")
    return ", ".join(parts)
