"""
Planning for a single-pass video generation.

Three jobs live here, all pure functions so they can be tested without a
network or a model:

- build_single_pass_prompt(): turns a reviewed creative plan into ONE prompt
  that covers the hook AND its continuation, so the video is a single
  coherent take rather than two unrelated clips.
- extract_cost(): reads cost out of whatever shape OpenRouter returns.
- is_recoverable_error(): decides whether a failure is worth retrying.

The prompt contract matters for the product rule that the model renders
everything it shows: the environment, setting, lighting and props are
invented from the verified app facts in the prompt, because nothing is
composited over the footage except deterministic captions and the end
card. The one thing the model must never invent is the person — they come
from the founder's character reference photograph, which rides along as a
model input. Anything the viewer could read as a factual claim about the
app (prices, ratings, interface text) must come from verified facts or
stay out of frame.
"""
from contextvars import ContextVar
from typing import Optional

# Hard ceiling on the assembled render prompt, in characters.
#
# Proven live: a 7,724-char prompt to minimax/hailuo-3-max was refused with
# "content[0].text too long: 7724 > 7000 characters". The /videos payload
# sends our prompt as the text verbatim, so the prompt itself must stay under
# the provider's 7,000. The 200-char margin covers any measuring difference on
# their side (e.g. astral-plane characters counted as two units); it is not
# round-number comfort, and the test below pins the measured worst case so any
# growth forces a conscious trim rather than a surprise 400.
#
# Enforced structurally, not by truncating the finished string: every variable
# read below goes through _clip, so the worst case is bounded no matter what
# a strategy, plan, template or profile carries — including rows written
# before this ceiling existed. Cutting the finished tail instead would
# amputate the identity close at the end, which is the worst part of the
# prompt to lose.
RENDER_PROMPT_LIMIT = 6800

# How much of the field budgets above to actually grant this render.
#
# The budgets above are sized for the provider whose ceiling RENDER_PROMPT_LIMIT
# was measured against. A second provider with a lower ceiling cannot be given
# the same prompt: it 400s, and the founder pays for the attempt. Rather than
# truncate the finished string — which would amputate the identity close at the
# very end, the worst part of the prompt to lose — every _clip is scaled, so the
# bound holds structurally at any ceiling.
#
# A ContextVar rather than a parameter threaded through all four helper
# functions: the scale is set once at the top of build_segment_prompt and must
# reach every _clip inside them. Task-local, so two concurrent renders on
# different models cannot see each other's budget.
_PROMPT_SCALE: ContextVar = ContextVar("hookforge_prompt_scale", default=1.0)


def _clip(text, limit: int) -> str:
    """Clip one variable prompt value to a fixed budget, stripped."""
    s = str(text or "").strip()
    effective = max(1, int(limit * _PROMPT_SCALE.get()))
    if len(s) <= effective:
        return s
    return s[:effective].rstrip()

# Words the model must not attempt to draw. Listed so the instruction can be
# explicit rather than relying on the model inferring "don't fake the facts".
# Note what is NOT here: the environment, setting, lighting and props ARE
# invented by the model from the verified app facts — nothing is composited
# over the footage except captions now, so the scene has to be rendered, not
# reserved.
_UI_RENDERING_WARNING = (
    "Do NOT draw or render: app interface elements, app screenshots, button "
    "labels, prices, ratings, review counts, download counts, logos, or any "
    "small on-screen text. Nothing is composited over this footage except "
    "captions, so invent the environment, setting, lighting "
    "and props concretely from the verified app facts — but anything the "
    "viewer could read as a factual claim about the app must come from those "
    "facts, never from invention. Leave clean, uncluttered space for the captions."
)

# The App Profile's must_not_show list, turned into a prompt section.
#
# This field's UI label used to promise "Must never be contradicted by promos"
# and nothing checked it: it was passed to the plan and strategy prompts as
# loose context and never reached a video prompt at all, so a model that
# contradicted it had no way of knowing. Emitting it here is the whole point of
# the rename — a founder who writes "never show a hospital corridor" now gets
# that instruction attached to the render that could break it.
def must_not_show_section(profile: dict) -> str:
    """
    The app-specific things that must never appear in frame.

    Returns "" when the profile records none, so the prompt is unchanged for
    the majority of profiles rather than carrying an empty rule.
    """
    raw = (profile or {}).get("must_not_show")
    if isinstance(raw, str):
        items = [part.strip() for part in raw.split("\n") if part.strip()]
    elif isinstance(raw, (list, tuple)):
        items = [str(part).strip() for part in raw if str(part).strip()]
    else:
        return ""
    if not items:
        return ""
    listed = "; ".join(_clip(part, 30) for part in items[:8])
    return (
        "MUST NOT APPEAR — recorded on this app's profile as things a promo must never "
        f"contradict or show: {listed}. Do not depict any of them, do not imply them, and "
        "do not use them as background, prop, or setting detail."
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
        # Two sections, because two sections is the whole video. The middle
        # carries everything after the hook and ends at the moment the viewer
        # reaches for the app. There is no demonstration beat and no closing
        # beat: the founder's own recording supplies both, and a plan that
        # reserved seconds for them would render footage that runs out
        # mid-thought.
        return (
            f"- 0-{hook}s: hook — the only part of this {duration}s video with {hook}s "
            f"to stop the scroll\n"
            f"- {hook}-{duration}s: middle — develops the hook through the situation and "
            f"ends on them reaching for the app. Do NOT film the app working, and do not "
            f"ask for anything: the demo and the call to action are attached afterwards."
        )
    lines = []
    for beat in beats[:10]:
        try:
            start = float(beat.get("start", 0))
            end = float(beat.get("end", start + 1))
        except (TypeError, ValueError):
            continue
        label = str(beat.get("label") or "beat").strip()
        text = _clip(beat.get("text"), 100)
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
            text = _clip(item.get("text"), 60)
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
        is_extension: True when continuing a longer video. The prompt then
            asks the model to continue seamlessly rather than open cold.
    """
    app_name = (profile or {}).get("brand_name") or "the app"
    hook = _clip(plan.get("hook_line"), 150)
    script = _clip(plan.get("script"), 400)
    visual = _clip(plan.get("visual_direction"), 120)
    voice = _clip(plan.get("voice_direction"), 120)
    sound = _clip(plan.get("sound_direction"), 120)
    tpl = template or {}
    tone = _clip(plan.get("tone") or tpl.get("tone"), 120)

    # The template's own opening length, clamped. This is directorial — how much
    # of the opening the hook has to land in — and NOT a render length: the whole
    # piece is this one render.
    hook_seconds = max(
        2, min(4, int(tpl.get("hook_seconds") or plan.get("hook_seconds") or 3))
    )

    sections = []

    sections.append(
        f"Create ONE continuous {duration}-second vertical (9:16) promotional video "
        f"for the mobile app {app_name}. It must be a single coherent take containing "
        f"both the opening hook and its continuation, with no visible cut to a separate clip, "
        f"no black frames, and no title card."
    )

    if is_extension:
        # Unreachable in the shipped flow: a video is one render, so nothing
        # extends anything. Kept so an old project saved with extend_intent set
        # cannot produce a prompt that instructs a model to continue a chain that
        # no longer exists.
        sections.append(
            "This clip CONTINUES an existing video. Open exactly as the previous clip "
            "ended, matching its subject, framing, lighting, and motion. Do not re-introduce "
            "the app or repeat the hook; move straight into developing the situation."
        )
    else:
        # Match the template's own opening length rather than asserting a
        # constant, so this line agrees with the beat layout below and with the
        # mechanism the founder selected.
        sections.append(
            f"The first {hook_seconds} seconds are the hook and must land immediately: "
            f"{hook or 'open on the strongest visual beat'}."
        )
        sections.append(
            f"The rest of the {duration} seconds are the middle: they develop the hook through "
            f"the situation, the friction, or the reaction, and they end on the moment the "
            f"presenter reaches for their phone. This is the last thing in the video — the "
            f"founder records their own product demo and adds their own call to action after "
            f"it, so do not film the app being used, do not show a screen, and do not ask the "
            f"viewer to do anything."
        )

    if script:
        sections.append(f"Spoken script, performed naturally on camera or as voiceover:\n\"{script}\"")

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
    if tpl.get("visual_style"):
        sections.append(f"Visual style: {_clip(tpl['visual_style'], 100)}")
    if tpl.get("camera_pacing") or tpl.get("middle_structure"):
        pacing = " ".join(
            p for p in (_clip(tpl.get("camera_pacing"), 100), _clip(tpl.get("middle_structure"), 100)) if p
        )
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
    # No call to action is appended, deliberately. The plan no longer carries a
    # `cta` field and the strategy no longer carries `cta_strategy`; the founder
    # adds their own in their editor. Reading a stale value here would put a
    # closing instruction into a video that is supposed to stop at the moment
    # the viewer reaches for the app.

    sections.append(_UI_RENDERING_WARNING)

    forbidden = must_not_show_section(profile)
    if forbidden:
        sections.append(forbidden)

    # The attached face is covered by the person anchor below, and nothing
    # else can be attached — so there is no composited-assets section. Any
    # retired uploads still sitting on an old project are refused before any
    # prompt is built, and never reach here.
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
        "sensitive",
        "sensitive_content",
        "privacy",
        "contentdetect",
        "content_detect",
        "contentfilter",
        "content_filter",
        "policy_violation",
        "policyviolation",
        "inputimage",
        "input_image",
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
    _submit_generation, which carries it as an input_references identity guide
    on Hailuo 3 and as the opening frame on Hailuo 3 Max). This text tells the
    model what that image IS: the exact person who must appear on camera. First matching character_reference asset wins —
    attach only one per project.

    Two things this deliberately does NOT say, both learned the hard way:

    - It used to require the clothing to match the photograph too. Clothing is
      now the one thing a scene may change (the strategy picks a wardrobe, see
      character_scene_lock), so requiring it here contradicted the rest of the
      prompt.
    - It used to say "animated rather than re-imagined". That is very likely
      what grew the invented hair: video models express motion in hair by
      making it longer and flowing, so asking for the person to be *animated*
      invites the model's most confident hair behaviour. Nothing in the prompt
      forbade adding hair — only matching it — which left the addition
      unspecified and therefore free. Hence the explicit no-additions clause.
    """
    if not assets:
        return ""
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if str(asset.get("kind") or "").strip().lower() != "character_reference":
            continue
        label = _clip(asset.get("name") or asset.get("label") or "the attached character reference", 60)
        return (
            "The person on camera is the person in the attached character reference "
            f"image ({label}). Copy that person exactly: same face, skin, age and build, "
            "and the same hair — same hairline, colour, length, texture and parting. "
            "Their appearance is fixed by that photograph: do not add, lengthen, restyle "
            "or recolour their hair, and do not add or remove anything absent from the "
            "image (hats, glasses, jewellery, makeup). Move and speak naturally, but do "
            "not change who they are. The image is the only authority on who they are — "
            "where this prompt or any written description states otherwise, ignore the "
            "text and follow the image. Do not invent a different person and do not blend "
            "them with anyone else. Their clothing is the one exception: the scene above "
            "sets it, and it need not match the photograph."
        )
    return ""


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
        # Wardrobe is the one presentational field that reaches the lock. It is
        # chosen by the strategy to suit the setting and holds for both
        # sections, which is why it belongs to the scene rather than to the
        # person: everything about the person is the photograph's job.
        ("wardrobe", "wardrobe"),
        ("props", "props"),
    ),
    "performance": (
        ("movement", "movement"),
        ("voice_delivery", "voice delivery"),
    ),
}


def character_scene_lock(strategy: dict) -> str:
    """
    Render the strategy's scene and performance as an explicit do-not-change
    block.

    A video model has no memory of the previous segment. Anything not restated
    is an invitation to reinvent it, and the attributes it reinvents most
    reliably are the scene, the wardrobe and the camera — so every attribute
    the strategy fixed is written out again, by name, as a locked value.

    The person's appearance is deliberately NOT restated. The on-camera person is
    copied from the founder's uploaded character reference image, and this
    function used to write a model's guess at that face, hair, age and wardrobe
    alongside the photograph, under a heading telling the provider both were
    locked. Strategies generated before that was removed still carry such a
    block, so "character" is skipped here by name rather than trusted.

    Wardrobe is the deliberate exception, and it sits in the scene rather than
    the person for a reason: the strategy chooses clothes to suit the setting,
    and a scene that claims someone has to keep them in the same outfit for
    both sections. Locking it here is what makes "do not re-wardrobe" in the
    trailer below enforceable — the clothing is stated once, by the thing that
    decided it, instead of being left to the photograph and the model to
    reconcile.
    """
    strategy = strategy or {}
    lines = []
    for section, fields in _SECTION_LABELS.items():
        if section == "character":
            continue
        values = strategy.get(section)
        if not isinstance(values, dict):
            continue
        described = [
            f"{label}: {_clip(values.get(key), 100)}"
            for key, label in fields
            if str(values.get(key) or "").strip()
        ]
        if described:
            lines.append("\n".join(f"  {item}" for item in described))

    if not lines:
        return ""
    lock = (
        "THE SCENE AND THE DELIVERY ARE LOCKED. Reproduce these exactly — same place, "
        "same light, same camera, same wardrobe and props, same way of moving and speaking:\n"
        + "\n".join(lines)
        + "\n\nThese are not suggestions. Do not restyle, re-light, re-wardrobe or relocate "
        "this scene, and do not swap in a different location, prop or outfit, even if the "
        "later part of the story would seem to call for it."
    )
    # The block as a whole is capped, not just its values: scene fields come
    # first so a pathological strategy loses the performance tail, never the
    # location and light the render needs most. Sized to clear a realistic
    # full lock (~1,050 with every field populated) — anything lower
    # amputates pinned fields even for ordinary strategies.
    return _clip(lock, 1100)


def strategy_brief(strategy: dict) -> str:
    """
    Render the app-specific strategy into prompt text.

    What is NOT here matters as much as what is. There is no cta line: a call to
    action is added by the founder in their own editor, and instructing the
    render to end on one would put a closing beat into footage that is supposed
    to stop at the moment the viewer reaches for the app. There is no
    "the one feature shown" line either, for the same reason the plan carries a
    demo_brief rather than a feature_emphasis: a feature instruction that
    reaches the render is a product demo being generated, and this workflow does
    not generate one. The differentiation and desired-outcome lines stay — they
    are how the middle frames the situation, not what it demonstrates.

    The problem, outcome and differentiation are restated rather than assumed to
    have been absorbed, so a single render cannot drift into a generic
    advertisement. The feature is named as subject matter only: what this app is
    about is what the middle is set in, not an instruction to film it working.
    """
    strategy = strategy or {}
    parts = []
    summary = _clip(strategy.get("strategy_summary"), 250)
    if summary:
        parts.append(f"Strategy for this video: {summary}")

    problem = _clip(strategy.get("audience_problem"), 200)
    if problem:
        parts.append(f"The problem this viewer actually has: {problem}")

    triggers = [_clip(t, 80) for t in (strategy.get("emotional_triggers") or []) if str(t).strip()]
    if triggers:
        parts.append(f"Emotions to land: {'; '.join(triggers[:4])}")

    pillars = [_clip(p, 100) for p in (strategy.get("messaging_pillars") or []) if str(p).strip()]
    if pillars:
        parts.append("Messaging that must be delivered: " + "; ".join(pillars[:4]))

    feature = _clip(strategy.get("primary_feature"), 200)
    if feature:
        # Subject matter, not an instruction. The old wording ("The one feature
        # shown: {feature}. Show it in use, not described.") was a direct
        # product-demo order reaching the render prompt on every generation.
        parts.append(
            f"What this app is about (the situation the middle is set in, never filmed "
            f"working): {feature}"
        )

    outcome = _clip(strategy.get("desired_outcome"), 200)
    if outcome:
        parts.append(f"Outcome the viewer should expect: {outcome}")

    diff = _clip(strategy.get("differentiation_beat"), 200)
    if diff:
        parts.append(f"How this app is different: {diff}")

    if not parts:
        return ""
    brief = "THIS APP-SPECIFIC STRATEGY — it governs this whole video:\n" + "\n".join(
        f"  {p}" for p in parts
    )
    # The brief as a whole is capped: its head (summary, problem, triggers)
    # carries the context the render needs, so a pathological strategy loses
    # the tail, never the head. Sized to clear a realistic full brief — lower
    # cuts feature and outcome lines out of ordinary strategies.
    return _clip(brief, 700)


def build_segment_prompt(
    strategy: dict,
    profile: dict,
    template: Optional[dict] = None,
    duration: int = 4,
    assets: Optional[list] = None,
    plan: Optional[dict] = None,
    prompt_budget: Optional[int] = None,
) -> str:
    """
    Build the prompt for the whole generated piece: a hook and a middle.

    Thin wrapper that establishes the per-provider character ceiling and then
    hands off to the assembler. Split out so the scale is set and cleared around
    the whole assembly rather than inside it — the budget has to reach every
    _clip call, including the ones in the four helpers this calls, and those have
    no reason to know which provider is rendering.

    Args:
        strategy: the normalized app-specific strategy (see
            ai_service.normalize_strategy). Required: without it there is no
            app specificity to preserve.
        profile: the approved App Profile, for the accurate product name.
        template: the hook template, for mechanism and pacing language.
        duration: seconds the whole piece must cover.
        assets: the project's attached assets (character_reference etc).
        plan: the reviewed creative plan, read only for `hook_seconds` so the
            two sections are split at the boundary the plan and the strategy
            both agreed on. Nothing else is taken from it: the strategy already
            carries the approved words.
        prompt_budget: this render's character ceiling. Defaults to
            RENDER_PROMPT_LIMIT, which is the measured figure for Hailuo. A
            provider with a lower ceiling passes its own; every field budget is
            scaled down to fit rather than the tail being cut off.
    """
    scale = 1.0
    if prompt_budget:
        try:
            scale = float(prompt_budget) / float(RENDER_PROMPT_LIMIT)
        except (TypeError, ValueError, ZeroDivisionError):
            scale = 1.0
        # A zero, negative or non-numeric budget is a caller bug, not a tight
        # budget. Falling back to the measured default keeps the prompt whole;
        # clamping it would silently shrink every Hailuo render to a tenth of
        # its detail because someone passed -1.
        if scale <= 0:
            scale = 1.0
        # Floor it well above zero: a provider ceiling far below what the fixed
        # instructions alone occupy would clip every field to a stub, which reads
        # as corruption rather than as a budget.
        scale = max(0.10, min(1.0, scale))
    token = _PROMPT_SCALE.set(scale)
    try:
        return _assemble_prompt(strategy, profile, template, duration, assets, plan)
    finally:
        _PROMPT_SCALE.reset(token)


def _assemble_prompt(
    strategy: dict,
    profile: dict,
    template: Optional[dict] = None,
    duration: int = 4,
    assets: Optional[list] = None,
    plan: Optional[dict] = None,
) -> str:
    """
    Assemble the render prompt. See build_segment_prompt for the arguments.

    The name of the public wrapper is historical. A video used to be assembled
    from separately rendered segments, one per beat, and the builder chose the
    prompt for whichever one was being made. Now the hook and the middle are a
    single render, so this builds the whole thing. There is no `segment_index`,
    `continuity`, `is_hook` or `previous_summary` argument: all four described a
    seam between two clips, and there is no seam.

    What holds the two sections together is the scene lock plus the app-specific
    brief, both of which apply to the whole piece.
    """
    strategy = strategy or {}
    tpl = template or {}
    plan = plan or {}
    app_name = (profile or {}).get("brand_name") or "the app"
    seconds = max(1, int(duration or 0))

    sections = []

    # The whole piece is one render with two sections, so both are always
    # described: index 0 is the hook and index 1 is the middle. Which is which
    # comes from the section's role, not its position, so a strategy whose
    # middle is missing still renders the hook and says plainly that it has no
    # middle to film rather than stretching the hook over the whole runtime.
    sections.append(
        f"Create ONE continuous {seconds}-second vertical (9:16) promotional video for the "
        f"mobile app {app_name}, containing exactly TWO sections: a HOOK in the opening "
        f"seconds, then a MIDDLE that develops it. It must read as a single take — no visible "
        f"cut to a separate clip, no black frames, no title card."
    )
    # Stated up front rather than left to the beat list, because this is the
    # single most important constraint on the render and the model has a strong
    # prior towards resolving a promo on camera.
    sections.append(
        "This video ends before the product is shown. The founder records their own demo and "
        "attaches it after this footage, and adds their own call to action. So: do NOT film the "
        "app being used, do NOT show a screen or interface, do NOT describe the app working "
        "while something unrelated happens on camera, and do NOT ask the viewer to download, "
        "install or try anything. End on the moment the presenter reaches for their phone."
    )

    hook_line = _clip(strategy.get("hook_line"), 200)
    hook_concept = _clip(strategy.get("hook_concept"), 75)
    hook_action = _clip(strategy.get("hook_action"), 75)
    hook_dialogue = _clip(strategy.get("hook_dialogue"), 75)
    promise = _clip(strategy.get("hook_promise"), 40)
    if hook_concept:
        sections.append(f"What the opening must DO: {hook_concept}")
    if hook_line:
        sections.append(f"The spoken hook line, delivered on camera: \"{hook_line}\"")
    if hook_action:
        sections.append(f"What the person physically does in the opening: {hook_action}")
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

    # The seam block that used to live here is gone. It described carrying a
    # previous clip's frame, its established facts and its do-not-repeat list
    # into a continuation — all of which presupposed a second render. One
    # render has no previous clip, so the only thing that has to hold the two
    # sections together is the scene lock above.

    # Both sections, in order, so the model has the whole piece in front of it
    # rather than one beat at a time. Roles are read rather than assumed, so a
    # strategy that names them out of order still films the hook first.
    sections_by_role = {
        str(s.get("role") or "").strip().lower(): s
        for s in (strategy.get("segments") or []) if isinstance(s, dict)
    }
    # The section boundary. The plan's own hook length wins, because the founder
    # approved a plan whose two beats start and end at that second, and the
    # strategy's schema echoes the template's. Clamped to 2-4s because that is
    # the window a hook has to land in.
    hook_seconds = max(
        2, min(4, int(plan.get("hook_seconds") or tpl.get("hook_seconds") or 3))
    )
    middle_seconds = max(1, seconds - hook_seconds)

    # The purpose is a full clause, because these headings are read as
    # instructions: "its job is to stops the scroll" is a visible grammar fault
    # in a prompt someone may have to debug, and the model reads it as a
    # malformed instruction rather than a shorter one.
    for role, label, budget, purpose in (
        ("hook", "HOOK", hook_seconds, "stop the scroll"),
        ("middle", "MIDDLE", middle_seconds, "develop the hook and end at the reach"),
    ):
        section = sections_by_role.get(role) or {}
        goal = _clip(section.get("goal"), 85)
        script = _clip(section.get("script"), 160)
        action = _clip(section.get("action"), 85)
        block = [f"{label} — {budget}s, and its job is to {purpose}:"]
        if goal:
            block.append(f"  what it must achieve: {goal}")
        if action:
            block.append(f"  what happens on camera: {action}")
        if script:
            block.append(f"  spoken, performed naturally: \"{script}\"")
        if not (goal or action or script):
            # A strategy missing a section is a real gap — a model that returned
            # one beat. Say what the section is for rather than borrowing the
            # other one's content, which is how the hook used to be restated.
            block.append(
                f"  the strategy did not plan this section in detail. Write it so it "
                f"{purpose}, in this same scene, and keep it distinct from the other "
                f"section."
            )
        sections.append("\n".join(block))

    if tpl.get("opening_structure"):
        sections.append(f"Hook mechanism to honour: {_clip(tpl['opening_structure'], 80)}")
    if tpl.get("middle_structure"):
        sections.append(f"Middle structure to honour: {_clip(tpl['middle_structure'], 80)}")
    if tpl.get("visual_style"):
        sections.append(f"Visual style: {_clip(tpl['visual_style'], 80)}")
    if tpl.get("camera_pacing"):
        sections.append(f"Camera and pacing: {_clip(tpl['camera_pacing'], 80)}")

    sections.append(
        "On-screen text will be added afterwards. Plan clean space for it, and do not "
        "render any text yourself."
    )
    sections.append(_UI_RENDERING_WARNING)

    forbidden = must_not_show_section(profile)
    if forbidden:
        sections.append(forbidden)

    # The attached face is covered by the person anchor below, and nothing
    # else can be attached — so there is no composited-assets section here
    # either. Retired uploads are refused before any prompt is built.
    person_anchor = person_anchor_notes(assets or [])
    if person_anchor:
        sections.append(person_anchor)

    sections.append(
        f"Vertical 9:16 throughout. One continuous {seconds}-second take with no cut, no "
        f"black frame, and no title card. The person on camera is the same individual in "
        f"every frame, with their face and hair exactly as in the reference photograph, in "
        f"the one outfit this scene specifies, in the same place, under the same light."
    )

    return "\n\n".join(section for section in sections if section)
