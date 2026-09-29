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


def _format_beats(beats, duration: int, hook_seconds: int = 3) -> str:
    """
    Render the beat list, or a sensible default when the plan has none.

    `hook_seconds` is the opening segment's length. It was previously hardcoded
    to 3, which contradicted the template's own hook_seconds (2-3s) arriving
    in the same prompt — so a 2s-hook template was told to hold its hook for 3
    seconds. It is now threaded through from the caller.
    """
    hook = max(1, min(int(hook_seconds or 3), max(1, duration - 1)))
    if not beats:
        return (
            f"- 0-{hook}s: hook — {duration}s total video, hook in the first {hook} seconds\n"
            f"- {hook}-{hook + 5}s: problem or transition\n"
            f"- {hook + 5}-{max(hook + 5, duration - 3)}s: app demonstration and payoff\n"
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
        # Match the template's own hook length rather than asserting 3s, so this
        # line agrees with the beat layout below and with the mechanism the
        # founder selected.
        hook_len = int((template or {}).get("hook_seconds") or plan.get("hook_seconds") or 3)
        sections.append(
            f"The first {hook_len} seconds are the hook and must land immediately: "
            f"{hook or 'open on the strongest visual beat'}."
        )

    if script:
        sections.append(f"Spoken script, performed naturally on camera or as voiceover:\n\"{script}\"")

    # The template's declared hook length wins over the 3s default, so the
    # fallback beat layout and the mechanism in the same prompt agree.
    hook_seconds = int(tpl.get("hook_seconds") or plan.get("hook_seconds") or 3)
    sections.append(
        "Beat-by-beat timeline — follow these timings:\n"
        + _format_beats(plan.get("beat_timeline"), duration, hook_seconds)
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


# ---------------------------------------------------------------------------
# App-specific influencer segments
# ---------------------------------------------------------------------------
# Below here is the segmented influencer workflow. build_single_pass_prompt()
# above stays as the one-shot path: it is correct for a single generation and
# is covered by its own tests. These builders differ in kind rather than degree
# — they take a video STRATEGY (app-specific concept, locked persona, locked
# scene, continuity contract) and emit the prompt for ONE segment of it.

_SECTION_LABELS = {
    "character": (
        ("appearance", "overall look"),
        ("facial_features", "face"),
        ("hairstyle", "hair"),
        ("age_range", "apparent age"),
        ("body_appearance", "build and posture"),
        ("wardrobe", "wardrobe"),
        ("styling_details", "styling details"),
        ("facial_expression", "expression"),
    ),
    "scene": (
        ("environment", "location"),
        ("background", "background"),
        ("setting", "time of day and context"),
        ("camera_angle", "camera angle"),
        ("framing", "framing"),
        ("lighting", "lighting"),
        ("color_palette", "colour palette"),
        ("visual_style", "visual style"),
        ("character_positioning", "position in frame"),
        ("props", "props"),
    ),
    "performance": (
        ("movement", "movement"),
        ("voice_delivery", "voice delivery"),
    ),
}


def character_scene_lock(strategy: dict) -> str:
    """
    Render the strategy's persona as an explicit do-not-change block.

    A video model has no memory of the previous segment. Anything not restated
    is an invitation to reinvent it, and the attributes it reinvents most
    reliably are the face, the wardrobe and the background — exactly the three
    that make an extension read as the same video. So every attribute the
    strategy fixed is written out again, by name, as a locked value.
    """
    strategy = strategy or {}
    lines = []
    for section, fields in _SECTION_LABELS.items():
        values = strategy.get(section)
        if not isinstance(values, dict):
            continue
        described = [
            f"{label}: {str(values.get(key)).strip()}"
            for key, label in fields
            if str(values.get(key) or "").strip()
        ]
        if described:
            lines.append("\n".join(f"  {item}" for item in described))

    if not lines:
        return ""
    return (
        "THE PERSON AND THE SCENE ARE LOCKED. Reproduce these exactly — same face, "
        "same hair, same wardrobe, same place, same light, same camera:\n"
        + "\n".join(lines)
        + "\n\nThese are not suggestions. Do not restyle, re-age, re-crop, re-light, "
        "re-wardrobe or relocate this person, and do not swap in a different person, "
        "even if the later part of the story would seem to call for it."
    )


def strategy_brief(strategy: dict) -> str:
    """
    The app-specific messaging the segment must keep communicating.

    Present on the opening segment AND every extension, so the continuation
    cannot drift into a generic advertisement. The app's problem, feature,
    outcome, differentiation and CTA are restated each time rather than
    assumed to have been absorbed by the previous segment.
    """
    strategy = strategy or {}
    parts = []
    summary = str(strategy.get("strategy_summary") or "").strip()
    if summary:
        parts.append(f"Strategy for this video: {summary}")

    problem = str(strategy.get("audience_problem") or "").strip()
    if problem:
        parts.append(f"The problem this viewer actually has: {problem}")

    triggers = [str(t).strip() for t in (strategy.get("emotional_triggers") or []) if str(t).strip()]
    if triggers:
        parts.append(f"Emotions to land: {'; '.join(triggers[:4])}")

    pillars = [str(p).strip() for p in (strategy.get("messaging_pillars") or []) if str(p).strip()]
    if pillars:
        parts.append("Messaging that must be delivered: " + "; ".join(pillars[:4]))

    feature = str(strategy.get("primary_feature") or "").strip()
    if feature:
        parts.append(f"The one feature shown: {feature}")

    outcome = str(strategy.get("desired_outcome") or "").strip()
    if outcome:
        parts.append(f"Outcome the viewer should expect: {outcome}")

    diff = str(strategy.get("differentiation_beat") or "").strip()
    if diff:
        parts.append(f"How this app is different: {diff}")

    cta = str(strategy.get("cta_strategy") or "").strip()
    if cta:
        parts.append(f"Call-to-action strategy: {cta}")

    if not parts:
        return ""
    return "THIS APP-SPECIFIC STRATEGY — it governs every segment of this video:\n" + "\n".join(
        f"  {p}" for p in parts
    )


def _segment_for(strategy: dict, index: int) -> dict:
    """The strategy's own plan for segment `index`, falling back to the last."""
    segments = [s for s in (strategy.get("segments") or []) if isinstance(s, dict)]
    if not segments:
        return {}
    for segment in segments:
        try:
            if int(segment.get("index", -1)) == index:
                return segment
        except (TypeError, ValueError):
            continue
    return segments[-1] if index >= len(segments) else {}


def _contract_list(strategy: dict, field: str, limit: int = 6) -> list:
    contract = strategy.get("continuity_contract")
    if not isinstance(contract, dict):
        return []
    return [str(v).strip() for v in (contract.get(field) or []) if str(v).strip()][:limit]


def build_segment_prompt(
    strategy: dict,
    profile: dict,
    template: Optional[dict] = None,
    segment_index: int = 0,
    duration: int = 4,
    assets: Optional[list] = None,
    continuity: Optional[dict] = None,
    is_hook: bool = False,
    previous_summary: str = "",
) -> str:
    """
    Build the prompt for ONE segment of the app-specific influencer video.

    Segment 0 is the hook: it establishes the person and the scene. Every
    segment after it is a continuation, and the difference is not cosmetic —
    a continuation is told what the previous segment already delivered and what
    it must therefore NOT repeat, and it is told the same locked persona and
    the same app strategy so the story cannot drift generic.

    Args:
        strategy: the normalized app-specific strategy (see
            ai_service.normalize_strategy). Required: without it there is no
            app specificity to preserve.
        profile: the approved App Profile, for the accurate product name.
        template: the hook template, for mechanism and pacing language.
        segment_index: 0 for the hook, 1+ for extensions.
        duration: seconds this segment must cover.
        assets: the project's attached assets (character_reference etc).
        continuity: the video_providers.continuity_plan() record for this
            request. Read, never re-decided — this prompt must not claim more
            continuity than the submission will actually deliver.
        is_hook: True for the opening segment.
        previous_summary: what the previous segment established, in one line.
    """
    strategy = strategy or {}
    tpl = template or {}
    app_name = (profile or {}).get("brand_name") or "the app"
    segment = _segment_for(strategy, segment_index)
    continuity = continuity or {}
    guarantee = str(continuity.get("guarantee") or "")
    degraded = continuity.get("degraded") or []
    seconds = max(1, int(duration or 0))
    is_continuation = not is_hook and int(segment_index or 0) > 0

    sections = []

    if is_continuation:
        # State the seam in the terms the model can act on. When a real frame
        # was attached, say so, because that is the difference between
        # "continue this" and "make something like this".
        if continuity.get("use_frame"):
            sections.append(
                f"You are continuing an existing video. The image supplied as the first frame is the "
                f"EXACT final frame of the clip the viewer has already seen. Start from those pixels: "
                f"the same pose, framing, focus and light, with motion continuing naturally forward. "
                f"Begin mid-action. Do not re-open the scene, do not re-establish the shot, do not "
                f"restart the performance, and do not show any title card, black frame or fade."
            )
        else:
            # No visual anchor. Say that plainly in the prompt as well as in
            # the report, so the model aims at the written lock rather than
            # assuming it can see the previous clip.
            sections.append(
                "You are continuing an existing video, but you have NOT been given the previous "
                "clip or any frame from it. Reproduce the locked person and scene below from the "
                "written description alone, as exactly as possible. Treat the description as "
                "authoritative: do not reinterpret, restyle or re-invent any part of it."
            )
    else:
        sections.append(
            f"Create a {seconds}-second vertical (9:16) promotional video for the mobile app "
            f"{app_name}. This is the OPENING HOOK and it has {seconds} seconds to land."
        )
        hook_line = str(strategy.get("hook_line") or "").strip()
        hook_concept = str(strategy.get("hook_concept") or "").strip()
        hook_action = str(strategy.get("hook_action") or "").strip()
        hook_dialogue = str(strategy.get("hook_dialogue") or "").strip()
        promise = str(strategy.get("hook_promise") or "").strip()
        if hook_concept:
            sections.append(f"What these {seconds} seconds must DO: {hook_concept}")
        if hook_line:
            sections.append(f"The spoken hook line, delivered on camera: \"{hook_line}\"")
        if hook_action:
            sections.append(f"What the person physically does: {hook_action}")
        if hook_dialogue:
            sections.append(f"Dialogue and delivery: {hook_dialogue}")
        if promise:
            sections.append(f"What the hook promises: {promise}")

    lock = character_scene_lock(strategy)
    if lock:
        sections.append(lock)

    brief = strategy_brief(strategy)
    if brief:
        sections.append(brief)

    # What the previous segment already delivered. This is the mechanism that
    # stops an extension from restarting the video: the model is told what the
    # viewer has already seen and heard, so it moves forward instead of
    # re-introducing the app.
    if is_continuation:
        established = _contract_list(strategy, "established")
        must_not_change = _contract_list(strategy, "must_not_change")
        do_not_repeat = _contract_list(strategy, "do_not_repeat")
        parts = []
        if previous_summary:
            parts.append(f"The previous segment ended on: {previous_summary}")
        if established:
            parts.append(
                "The opening segment already established: " + "; ".join(established[:6])
            )
        if must_not_change:
            parts.append(
                "Carry these forward unchanged: " + "; ".join(must_not_change[:6])
            )
        if do_not_repeat:
            parts.append(
                "Do NOT repeat any of this — the viewer has already seen or heard it: "
                + "; ".join(do_not_repeat[:6])
            )
        parts.append(
            "Move the story forward from the seam: deliver this segment's goal, then the "
            "app benefit, then the call to action. Do not re-introduce the app or the "
            "person, do not repeat the hook line, and do not restart the opening framing."
        )
        sections.append("CONTINUITY — what came before:\n" + "\n".join(f"  {p}" for p in parts))

    goal = str(segment.get("goal") or "").strip()
    script = str(segment.get("script") or "").strip()
    action = str(segment.get("action") or "").strip()
    if goal:
        sections.append(f"What these {seconds} seconds must achieve: {goal}")
    if action:
        sections.append(f"What happens in this segment: {action}")
    if script:
        sections.append(f"Spoken script for this segment, performed naturally on camera:\n\"{script}\"")

    if tpl.get("opening_structure") and is_hook:
        sections.append(f"Hook mechanism to honour: {tpl['opening_structure']}")
    if tpl.get("continuation_structure") and is_continuation:
        sections.append(f"Continuation structure to honour: {tpl['continuation_structure']}")
    if tpl.get("visual_style"):
        sections.append(f"Visual style: {tpl['visual_style']}")
    if tpl.get("camera_pacing"):
        sections.append(f"Camera and pacing: {tpl['camera_pacing']}")

    sections.append(
        "On-screen text will be added afterwards. Plan clean space for it, and do not "
        "render any text, interface, price, rating or logo yourself."
    )
    sections.append(_UI_RENDERING_WARNING)

    notes = asset_notes(assets or [])
    if notes:
        sections.append(f"Real app assets composited over this footage: {notes}")

    person_anchor = person_anchor_notes(assets or [])
    if person_anchor:
        sections.append(person_anchor)

    if degraded:
        # Never let the prompt imply a guarantee the request could not make.
        # The founder sees the same list on the generation record.
        reasons = "; ".join(
            str(d.get("reason") or "").strip() for d in degraded if str(d.get("reason") or "").strip()
        )
        if reasons:
            sections.append(
                "This provider could not receive every continuity reference: " + reasons +
                " Honour the written lock above with particular care, and treat the described "
                "person and scene as exacting requirements rather than suggestions."
            )

    sections.append(
        f"Vertical 9:16 throughout. One continuous {seconds}-second take with no cut, no "
        f"black frame, and no title card. The person on camera is the same individual in "
        f"every frame of this segment."
    )
    if is_continuation and guarantee in ("text_only",):
        sections.append(
            "Because this request carries no visual reference from the previous clip, "
            "reproduce the locked description as precisely as possible — the same person "
            "in the same clothes in the same place under the same light."
        )

    return "\n\n".join(section for section in sections if section)
