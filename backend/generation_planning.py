"""
Planning for a single-pass video generation.

Three jobs live here, all pure functions so they can be tested without a
network or a model:

- build_single_pass_prompt(): turns a reviewed creative plan into ONE prompt
  that covers the hook AND its continuation, so the video is a single
  coherent take rather than two unrelated clips.
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

# How far into a clip's budget the first acceptable clean ending must be
# before _clean_boundary gives up and takes the raw cut. Lower values end
# cleaner but discard more; this is where the two trade off evenly.
MIN_BOUNDARY = 0.45

# How many times build_segment_prompt will reassemble a prompt that came out
# over its ceiling.
#
# Each pass corrects the scale by the measured overshoot, so it converges
# geometrically and the number of passes needed is a function of how far
# over the first assembly landed, not of which provider it was for. Three was
# enough while the saturated worst case fitted inside the ceiling at scale
# 1.0; adding the opening pattern-interrupt directive and the larger hook
# budgets pushed that worst case about 240 characters past, which three
# passes did not absorb. Six absorbs a far larger saturated strategy than
# this code can currently build, and the passes are pure string work, so
# the headroom is close to free. Still the tail of the mechanism, not the
# mechanism: almost every prompt fits on the first try.
MAX_FIT_ATTEMPTS = 6

# Whether protected values are still holding their full budgets. Set per attempt
# by build_segment_prompt, which withdraws it if the first assembly came out
# over the ceiling.
#
# Protection has to be best-effort rather than absolute. Holding the script,
# the brief and the locked scene at full length is worth ~1,000 characters, and
# a saturated strategy can spend more than that on those three alone — so a
# provider with a 4,096 ceiling would be handed a 4,879 prompt and refused by the
# guard. Insisting on protection is how the model becomes unusable for exactly
# the founders who gave it the most to work with. One attempt tries the good
# version; if it does not fit, the next rebuilds without protection.
_PROMPT_PROTECT: ContextVar = ContextVar("hookforge_prompt_protect", default=True)

# The floor _budget_scale already clamps to. Repeated here because the retry
# loop has to recognise when it has run out of room to squeeze.
MIN_SCALE = 0.10

# Whether to use the condensed fixed instructions, set the same way as the
# scale and for the same reason: it has to reach the assembler without threading
# a parameter through every helper.
_PROMPT_CONDENSED: ContextVar = ContextVar("hookforge_prompt_condensed", default=False)

# Any ceiling under this renders with the condensed instructions.
#
# Scaling the variable budget alone is not enough to fit a tight ceiling,
# because the FIXED instructions do not scale: measured against no app data at
# all they are 2,047 characters, over half of a typical prompt. A provider
# capping prompts near 4,000 therefore cannot fit a normal prompt however hard
# the variables are squeezed — the floor alone eats half the budget.
#
# So the redundancy in the fixed text comes out instead. It is genuine
# redundancy: the "ends before the product is shown" block and the UI warning
# both forbid the interface, and the opening sentence restates the section
# structure that the per-section headings state again with their real jobs.
# Merging them costs nothing in meaning and roughly halves the floor, which is
# what buys the app-specific brief enough room to still be worth sending.
CONDENSE_BELOW = 4500

# Measured sizes of the fixed instruction text, with no app data at all. The
# difference between the two IS what condensing buys.
#
# These are load-bearing arithmetic, not documentation: the per-provider scale
# below divides by the variable space these imply, so if either drifts the
# prompts stop fitting their ceilings again. A test rebuilds both and pins them,
# which is why they are named rather than inlined.
#
# Both rose when the opening pattern-interrupt directive was added, and again
# when it grew the grounding clause that keeps the opening's beats inside this
# video's own story (its full and condensed forms are the fixed text measured
# here). That is the trade this change makes on purpose: an interrupting
# opening is the product, and it is bought out of descriptive room on the
# providers with the tightest ceilings.
FULL_PROMPT_FLOOR = 3052
CONDENSED_PROMPT_FLOOR = 1800

# What the variables are given at the default ceiling, derived rather than
# measured: the default ceiling is a TOTAL, and the floor is part of it.
#
# This overestimates the variable text the code can actually assemble, which is
# the safe direction. Saturated fields top out around 3,830 characters, not
# 4,753, so a tight budget clips marginally harder than it strictly needs to.
# Erring toward a shorter prompt that fits beats an exact split that does not.
NATURAL_VARIABLE_SPACE = RENDER_PROMPT_LIMIT - FULL_PROMPT_FLOOR


def _budget_scale(prompt_budget, condensed: bool) -> float:
    """
    What fraction of each field budget this render may use.

    The ceiling is a TOTAL character budget, so the fixed instructions have to
    come out of it before the variables get anything. Scaling by
    budget/RENDER_PROMPT_LIMIT ignores that and silently over-allocates by the
    floor, which is how a 4,096 ceiling still produced a 4,175-character prompt.

    Subtracting the floor first is the whole fix: what remains is the space the
    variables actually have, and dividing that by their natural size gives the
    fraction. The guard in the submit path remains the backstop for the residue.
    """
    floor = CONDENSED_PROMPT_FLOOR if condensed else FULL_PROMPT_FLOOR
    available = float(prompt_budget) - float(floor)
    scale = available / float(NATURAL_VARIABLE_SPACE)
    # A ceiling at or below the floor leaves the variables nothing. Squeeze to
    # the floor of the scale rather than to zero: a prompt of one-character
    # stubs reads as corruption, and the submit guard will refuse it anyway.
    return max(MIN_SCALE, min(1.0, scale))


def _clean_boundary(head: str) -> str:
    """
    Trim a hard-cut fragment back to the last place it can end cleanly.

    Hard character cutting is what a video model should never be handed: it
    produced lines like "looks up from the phone, tired, into the le" and
    "What this app is abou", which a model either ignores or reads as a
    complete instruction. A fragment is still information; a broken word is
    just noise that costs characters.

    A line end is preferred, then a sentence end, then a word end, then the raw
    cut as a last resort. Line first matters because the two largest protected
    blocks — the locked scene and the strategy brief — are newline-delimited,
    where cutting mid-line loses a whole field's label and value. Boundaries
    earlier than MIN_BOUNDARY of the budget are refused: keeping one short
    opening sentence and discarding the rest of the field is usually a worse
    trade than an imperfect ending.
    """
    floor = len(head) * MIN_BOUNDARY
    line = head.rfind("\n")
    if line >= floor:
        return head[:line].rstrip()
    end = -1
    for i, ch in enumerate(head):
        if ch not in ".!?;":
            continue
        after = i + 1
        if after < len(head) and head[after] in "\"'":
            after += 1
        if after >= len(head) or head[after] == " ":
            end = after
    if end >= floor:
        return head[:end].rstrip()
    space = head.rfind(" ")
    if space >= floor:
        return head[:space].rstrip()
    return head.rstrip()


def _clip(text, limit: int, protect: bool = False) -> str:
    """
    Clip one variable prompt value to a fixed budget, stripped.

    `protect` marks a value the render cannot do without — the spoken script,
    the on-camera action, the app's strategy. Under a tight ceiling the
    protected values keep their full budget and the descriptive ones absorb
    the squeeze instead. Losing the tail of a product brief is survivable;
    losing half of what the founder is going to say is not.

    Only engaged when condensing. At a normal ceiling the scale is 1.0 and
    every value is already whole, so this changes nothing for Hailuo.
    """
    s = str(text or "").strip()
    scale = _PROMPT_SCALE.get()
    if protect and _PROMPT_CONDENSED.get() and scale < 1.0 and _PROMPT_PROTECT.get():
        effective = int(limit)
    else:
        effective = max(1, int(limit * scale))
    if len(s) <= effective:
        return s
    head = s[:effective].rstrip()
    if _PROMPT_CONDENSED.get():
        return _clean_boundary(head)
    return head

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

# Condensed forms of the fixed instructions, for providers whose prompt ceiling
# is too low to carry the full set. See CONDENSE_BELOW for why.
#
# Nothing is dropped, only stated once. The two prohibitions are merged because
# they were the same prohibition said twice; the opening sentence is folded into
# the section headings that already carry the real jobs. What survives is every
# constraint, and what it buys is the room the app-specific brief needs to still
# be worth sending — which is the entire point of the product.
_CONDENSED_HANDOFF = (
    "The video ends before the product appears: the founder films their own "
    "demo and adds their own close afterwards. Do NOT film or render the app "
    "in use, any interface, screenshot, button, price, rating, review or "
    "download count, logo, or on-screen text. Invent the setting, light and "
    "props from the verified app facts; any factual claim must come from those "
    "facts, never from invention."
)

_CONDENSED_IDENTITY_CLOSE = (
    "Vertical 9:16 throughout, one continuous take with no cut, no black frame "
    "and no title card. The person on camera is the same individual in every "
    "frame, face and hair exactly as the reference photograph, in the one "
    "outfit this scene specifies, in the same place, under the same light."
)

# How the opening plays, as a standing instruction on every studio render.
#
# The strategy supplies the specific beats; this is the requirement they have to
# satisfy, stated where the model is deciding what happens in the first frame.
# It is fixed text, so it is part of the measured floor below and gets a
# condensed twin for providers whose ceiling cannot carry the full set.
#
# What it forbids matters as much as what it asks for: the common failure this
# replaces was an opening that drifts in, settles into a neutral pose and then
# starts talking, which is exactly what a scrolling thumb ignores.
_OPENING_INTERRUPT = (
    "HOW THE OPENING MUST PLAY, frame by frame: the first frame is already in motion \u2014"
    " no neutral pose before anything happens, no fade, drift or slow push-in "
    "standing in for action, no greeting to camera. Inside the first half-second "
    "they do ONE unmistakable thing a scrolling thumb has to pause for: a sharp "
    "look straight into the lens, brows lifting and eyes widening, a hand snapping "
    "up into frame, an object grabbed, moved or put down, a posture or shoulder "
    "break. Two or three such beats, each bigger or stranger than the one before, "
    "so the opening escalates instead of settling. The face, gaze, hands and "
    "posture carry it; the words come second. Read the beats below as the physical "
    "score for those seconds and play them in order.\n"
    "Every one of those beats comes out of THIS video\u2019s own situation \u2014 its props, "
    "its place, its problem, what the middle goes on to do \u2014 so the interrupt reads "
    "as the first move of this story and not a random gesture, and it leaves a "
    "question the rest of the video answers."
)

# The same rule for a provider whose ceiling is too low for the full set. Every
# constraint above survives; only the examples of how to satisfy them go.
_CONDENSED_OPENING = (
    "Opening is a pattern interrupt: the first frame is already moving \u2014 no neutral "
    "pose, no fade, no greeting. One unmistakable beat inside the first half-second, "
    "then two or three escalating ones, carried by the face, gaze, hands and "
    "posture rather than by the words. Play the beats below as the physical score "
    "for those seconds.\n"
    "Those beats come out of this video\u2019s own situation, so the interrupt reads "
    "as the first move of the story and leaves a question the rest answers."
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
    listed = "; ".join(_clip(part, 30, protect=True) for part in items[:8])
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
            f"{label}: {_clip(values.get(key), 100, protect=True)}"
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
    return _clip(lock, 1100, protect=True)


def _brief_field(value, limit: int) -> str:
    """Normalize one opening-brief value without touching prompt-budget state."""
    return " ".join(str(value or "").split())[:limit].rstrip()


def build_heygen_opening_keyframe_brief(
    strategy=None,
    plan=None,
    template=None,
    duration: int = 12,
) -> str:
    """Describe the generated opening still for a HeyGen composite keyframe.

    This brief intentionally carries the approved environment, wardrobe, camera,
    props, and opening action, but never the uploaded photograph's pixels. The
    founder's face is integrated in a separate face-swap call. That separation
    is the fix: a provider receiving the composite as first_frame starts in
    the generated scene instead of starting from the uploaded background.
    """
    strategy = strategy if isinstance(strategy, dict) else {}
    plan = plan if isinstance(plan, dict) else {}
    template = template if isinstance(template, dict) else {}
    scene = strategy.get("scene") if isinstance(strategy.get("scene"), dict) else {}
    performance = (
        strategy.get("performance")
        if isinstance(strategy.get("performance"), dict)
        else {}
    )

    setting = "; ".join(
        part
        for part in (
            _brief_field(scene.get("environment"), 120),
            _brief_field(scene.get("background"), 120),
            _brief_field(scene.get("setting"), 120),
            _brief_field(scene.get("lighting"), 120),
            _brief_field(scene.get("camera_angle"), 120),
            _brief_field(scene.get("framing"), 120),
            _brief_field(scene.get("wardrobe"), 120),
            _brief_field(scene.get("props"), 120),
            _brief_field(scene.get("color_palette"), 80),
            _brief_field(scene.get("visual_style"), 120),
        )
        if part
    )
    action = (
        _brief_field(strategy.get("hook_action"), 280)
        or _brief_field(strategy.get("hook_concept"), 160)
        or _brief_field(plan.get("visual_direction"), 160)
        or _brief_field(template.get("opening_structure"), 120)
        or "The presenter is caught mid-action in the opening beat."
    )
    movement = _brief_field(performance.get("movement"), 160)

    sections = [
        f"Create the opening still for a {int(duration or 12)}-second vertical "
        "promotional video: one presenter is already mid-action in the approved "
        "generated environment.",
    ]
    if setting:
        sections.append(f"Approved setting: {setting}.")
    sections.append(f"Opening action: {action}")
    if movement:
        sections.append(f"Physical performance: {movement}.")
    sections.extend(
        [
            "Show a complete person in the approved wardrobe, posed for the "
            "opening action. The exact face will be integrated separately; do "
            "not invent a final identity here.",
            "Do not render an app interface, screenshot, text, logo, caption, "
            "or watermark.",
            "Do not copy any uploaded photograph's room, background, clothing, "
            "pose, lighting, or camera treatment. Generate this setting from "
            "the approved fields above.",
        ]
    )
    return "\n\n".join(sections)


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
    return _clip(brief, 700, protect=True)


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
            scaled down to fit rather than the tail being cut off. A ceiling low
            enough to leave the fixed instructions most of the budget (see
            CONDENSE_BELOW) also switches the fixed text to its condensed form,
            so a tight provider gets a shorter prompt rather than a truncated
            one. Both mean the same constraints, so the model sees the same
            rules from every provider — only the wording is tighter.

            Under a tight ceiling the spoken script, the on-camera action and
            the app's strategy and locked scene keep their full budgets and the
            descriptive text absorbs the squeeze, because a prompt missing half
            of what the founder is going to say is not a shorter prompt, it is
            a different video. Clipping also ends on a sentence or word
            boundary rather than mid-word. If the result is still over budget
            it is rebuilt with a smaller scale, so a very full strategy thins
            out instead of being refused.
    """
    scale = 1.0
    condensed = False
    budget = 0.0
    # The default is the measured ceiling, as the docstring says it is.
    # It used to be no ceiling at all: a caller that passed nothing got a
    # prompt assembled at full size, which only stayed under 6,800 while
    # every field budget fitted inside it. The opening detail raised the
    # saturated worst case past the limit, and the overflow surfaced as a
    # provider refusal rather than as a prompt that was too long — the
    # same strategy still renders fine on every normal input. Enforcing the
    # default is what the parameter always claimed to do.
    if prompt_budget is None:
        prompt_budget = RENDER_PROMPT_LIMIT
    if prompt_budget:
        try:
            budget = float(prompt_budget)
        except (TypeError, ValueError):
            budget = 0.0
        # A zero, negative or non-numeric budget is a caller bug, not a tight
        # budget. Falling back to the measured default keeps the prompt whole;
        # clamping it would silently shrink every Hailuo render to a tenth of
        # its detail because someone passed -1.
        if budget > 0:
            condensed = budget < CONDENSE_BELOW
            scale = _budget_scale(budget, condensed)

    # Normalised, not just ignored: the retry loop below tests the budget for
    # truthiness, and a negative one is truthy while no prompt can ever be <= it,
    # so it would squeeze the render to nothing. A caller bug gets the
    # measured default — which is what the docstring promises, and what an
    # omitted prompt_budget now gets too — rather than an unlimited prompt.
    if budget <= 0:
        budget = float(RENDER_PROMPT_LIMIT)

    # Protected values hold their full budget, so the scale is no longer a
    # reliable predictor of the assembled length and can undershoot on a very
    # full strategy. Measure what was actually built and squeeze again rather
    # than hand the guard an over-budget prompt: the guard's answer is to refuse
    # the render, which makes the model unusable for exactly the detailed
    # founders who gave it the most to work with.
    prompt = ""
    for attempt in range(MAX_FIT_ATTEMPTS):
        token = _PROMPT_SCALE.set(scale)
        token2 = _PROMPT_CONDENSED.set(condensed)
        token3 = _PROMPT_PROTECT.set(attempt == 0)
        try:
            prompt = _assemble_prompt(strategy, profile, template, duration, assets, plan)
        finally:
            _PROMPT_PROTECT.reset(token3)
            _PROMPT_CONDENSED.reset(token2)
            _PROMPT_SCALE.reset(token)
        if not budget or len(prompt) <= budget:
            return prompt
        # Still over: correct the scale by the measured overshoot and reassemble.
        # Protection is already withdrawn from here, so this is the plain scaled
        # build. Falls back to a real reduction if the scale has bottomed out.
        #
        # The correction divides the VARIABLE text by the variable room, not the
        # whole prompt by the whole ceiling. The fixed instructions are most of
        # what is left on a tight provider and they do not scale at all, so
        # scaling by budget/length asks for far less squeeze than the variables
        # can actually give: the loop then crawls toward the ceiling and runs out
        # of attempts still over it. The floors are measured from exactly this
        # fixed text with no variables at all, so subtracting one lands the next
        # pass inside.
        if scale <= MIN_SCALE:
            break
        fixed = CONDENSED_PROMPT_FLOOR if condensed else FULL_PROMPT_FLOOR
        variable = max(1, len(prompt) - fixed)
        room = budget - fixed
        if room <= 0:
            break
        scale = max(MIN_SCALE, scale * room / variable * 0.99)
    return prompt


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

    condensed = _PROMPT_CONDENSED.get()
    # The whole piece is one render with two sections, so both are always
    # described: index 0 is the hook and index 1 is the middle. Which is which
    # comes from the section's role, not its position, so a strategy whose
    # middle is missing still renders the hook and says plainly that it has no
    # middle to film rather than stretching the hook over the whole runtime.
    #
    # Condensed, the section structure is not restated here: the two headings
    # below carry the real durations and jobs, so this sentence would be saying
    # it a third time in shorter words.
    if not condensed:
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
    else:
        sections.append(
            f"Create ONE continuous {seconds}-second vertical (9:16) promotional video for the "
            f"mobile app {app_name}, in two sections. End on the moment the presenter reaches "
            f"for their phone, and do not ask the viewer to download or install anything."
        )
        sections.append(_CONDENSED_HANDOFF)

    # The requirement the beats below have to satisfy. Placed ahead of them, so
    # the model reads it as the standard for what follows rather than as another
    # fact about the video.
    sections.append(_CONDENSED_OPENING if condensed else _OPENING_INTERRUPT)

    hook_line = _clip(strategy.get("hook_line"), 200, protect=True)
    hook_concept = _clip(strategy.get("hook_concept"), 120, protect=True)
    hook_action = _clip(strategy.get("hook_action"), 280, protect=True)
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
    # Per-role budgets for goal and action, because the two sections are not
    # the same job: the opening's action is the physical score for the seconds
    # that have to stop the scroll, so it is given room the middle does not need.
    for role, label, budget, purpose, goal_budget, action_budget in (
        ("hook", "HOOK", hook_seconds, "stop the scroll", 110, 220),
        ("middle", "MIDDLE", middle_seconds, "develop the hook and end at the reach", 85, 120),
    ):
        section = sections_by_role.get(role) or {}
        goal = _clip(section.get("goal"), goal_budget, protect=True)
        script = _clip(section.get("script"), 160, protect=True)
        action = _clip(section.get("action"), action_budget, protect=True)
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
            if condensed:
                block.append(
                    f"  unplanned here: write it to {purpose}, same scene, distinct "
                    f"from the other section."
                )
            else:
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
    # The condensed handoff block above already carries this prohibition, merged
    # so the same rule is not stated twice on a budget that cannot afford it.
    if not condensed:
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

    if condensed:
        # The seconds are already stated in the opening sentence and in both
        # section headings, so the close states them once and carries only the
        # identity lock, which appears nowhere else.
        sections.append(_CONDENSED_IDENTITY_CLOSE)
    else:
        sections.append(
            f"Vertical 9:16 throughout. One continuous {seconds}-second take with no cut, no "
            f"black frame, and no title card. The person on camera is the same individual in "
            f"every frame, with their face and hair exactly as in the reference photograph, in "
            f"the one outfit this scene specifies, in the same place, under the same light."
        )

    return "\n\n".join(section for section in sections if section)
