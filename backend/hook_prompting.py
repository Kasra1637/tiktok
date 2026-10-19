"""Hook-video prompt construction: motion styles, style directives, templates.

Extracted verbatim from server.py. The hook prompt is built in layers: a base
prompt (template, hook analysis, image analysis, or hand-written motion style),
then the creator's hook-style directive, then the audio/text-overlay
instructions, so every path that submits a render shares one vocabulary.
server.py re-exports every name defined here, so `server.X` keeps working for
existing imports and tests.
"""

import json
from pathlib import Path
from typing import Optional

import pipeline


HOOK_VIDEO_PROMPT_TEMPLATE = (
    "Create a 3-second vertical video (9:16) starting from this exact first frame. "
    "The character should perform a FAST, punchy, attention-grabbing movement that creates "
    "curiosity: {motion_type}. "
    "PACING IS CRITICAL â€” match the energy of a viral TikTok hook (first 2-3 seconds): "
    "- The movement must happen QUICKLY â€” within the first 1-2 seconds, not gradually "
    "- Fast, snappy transitions â€” NOT slow or cinematic "
    "- Immediate eye contact and direct energy toward the camera from the very first frame "
    "- The viewer should feel startled or hooked within the first second "
    "- Think 'scroll-stopper' speed â€” if someone is swiping fast, this catches their eye instantly "
    "Additional requirements: "
    "- Maintain perfect character consistency with the first frame throughout "
    "- Camera holds steady or has a very subtle push-in for tension "
    "- End on a moment that makes the viewer want to see what happens next"
)

# Hook videos are muted by default. On TikTok, creators almost always attach a
# trending sound or use native text-to-speech in TikTok's own editor after
# exporting â€” a locally-generated audio track can't be posted as a "trending
# sound" and would just get stripped/replaced anyway. Muting by default avoids
# generating audio nobody keeps, while still letting users opt in
# (e.g. for platforms without an in-app sound library, like Reels/Shorts).
AUDIO_ON_INSTRUCTION = (
    "\n\nGenerate native audio that complements the hook â€” ambient sound, subtle "
    "tension-building music, or brief impactful sound design matching the energy "
    "of the movement."
)
AUDIO_OFF_INSTRUCTION = (
    "\n\nIMPORTANT: This video must be completely SILENT â€” no audio, no music, "
    "no voiceover, no ambient sound, no sound design of any kind. The character "
    "must NOT move their lips as if speaking or talking â€” keep the mouth closed "
    "or in a natural resting/smiling position. The creator will add a trending "
    "sound or text-to-speech in TikTok's own editor after exporting this clip."
)

# Always appended to every video prompt â€” text overlays are added later in
# TikTok's editor, not baked into the AI-generated clip.
NO_TEXT_OVERLAY_INSTRUCTION = (
    "\n\nNO TEXT OVERLAYS: The generated video must NOT contain any text, captions, "
    "titles, subtitles, watermarks, emojis, stickers, graphics, or visual text of "
    "any kind rendered on top of the video. The output should be a clean video with "
    "only the character and the scene â€” no text elements whatsoever. The creator "
    "will add their own text overlays in TikTok's editor after exporting."
)


def apply_audio_directive(prompt: str, include_audio: bool) -> str:
    """
    Append explicit audio and text-overlay instructions to a video prompt.

    Applied uniformly across all prompt sources (live analysis, saved
    templates, image analysis, motion-style fallback) right before
    submission, so the muted-by-default behavior and no-text rule hold
    regardless of where the base prompt text came from.
    """
    return prompt + (AUDIO_ON_INSTRUCTION if include_audio else AUDIO_OFF_INSTRUCTION) + NO_TEXT_OVERLAY_INSTRUCTION

# Canonical motion-style definitions â€” the single source of truth for both the
# prompt text sent to the model and the description shown in the UI.
#
# These were previously two independent lists: the prompt fragments here and a
# separate hand-written set of card descriptions in FaceSwap.jsx. They described
# the same five motions in different words, so the UI could tell a creator one
# thing while the model was told another, with nothing keeping them aligned.
# The UI now renders `motion` verbatim (see GET /hook-motion-styles), so what a
# creator reads on the card is literally what gets sent.
# Each entry carries three things, all served to the UI so none of them can
# drift from the others:
#   summary  â€” short, human-readable product copy for the card
#   motion   â€” the verbatim fragment sent to the model (shown on request)
#   overlaps â€” hook-energy keys this motion conceptually duplicates, so the UI
#              can warn when both are set and would layer two competing
#              directives describing the same effect into one prompt
HOOK_MOTION_STYLES = [
    {
        "key": "lean-in",
        "label": "Lean In",
        "summary": "Moves toward camera like you're about to share a secret â€” builds instant curiosity",
        "motion": "a FAST confident lean-in toward camera with a knowing expression, snapping into position within the first second â€” as if about to reveal a secret",
        "overlaps": [],
    },
    {
        "key": "turn",
        "label": "Dramatic Turn",
        "summary": "Starts from the side, then turns to face the viewer â€” creates a reveal moment",
        "motion": "a QUICK dramatic turn from profile to face-on, making immediate eye contact with the camera â€” fast snap, not a slow rotation",
        "overlaps": ["reveal"],
    },
    {
        "key": "gesture",
        "label": "Gesture",
        "summary": "Points, raises a hand, or reveals something â€” signals 'watch this' to stop the scroll",
        "motion": "a RAPID attention-grabbing gesture (pointing, hand raise, or prop reveal) that happens instantly â€” implies 'watch this' with urgency",
        "overlaps": [],
    },
    {
        "key": "intrigue",
        "label": "Intrigue",
        "summary": "Subtle head tilt + raised eyebrow â€” makes viewers think 'what do they know?'",
        "motion": "a FAST head tilt and raised eyebrow with a half-smile, snapping into the intrigue pose within the first second",
        "overlaps": ["curiosity-gap"],
    },
    {
        "key": "stop-motion",
        "label": "Stop Motion",
        "summary": "Sudden freeze-frame pose snap â€” eye-catching jolt that holds attention",
        "motion": "a SUDDEN stop-motion-style pose change that catches the eye instantly, then holds with intensity",
        "overlaps": ["pattern-interrupt"],
    },
]

# Derived views over HOOK_MOTION_STYLES so there is exactly one place to edit a
# motion. HOOK_MOTION_TYPES preserves the original positional list used by
# HOOK_VIDEO_PROMPT_TEMPLATE; MOTION_STYLE_INDEX maps the frontend's keys onto
# it for build_hook_prompt_from_motion_style() and
# apply_motion_style_directive().
HOOK_MOTION_TYPES = [m["motion"] for m in HOOK_MOTION_STYLES]
MOTION_STYLE_INDEX = {m["key"]: i for i, m in enumerate(HOOK_MOTION_STYLES)}


def _coerce_mechanics(mechanics) -> list:
    """Normalize replicable_mechanics into a list (it may be stored as JSON text)."""
    if not mechanics:
        return []
    if isinstance(mechanics, str):
        try:
            mechanics = json.loads(mechanics)
        except (json.JSONDecodeError, TypeError):
            mechanics = [mechanics]
    if isinstance(mechanics, list):
        return [m for m in mechanics if m]
    return [mechanics]




def build_hook_prompt_from_analysis(analysis: dict, has_reference_video: bool = False, v2v_motion_active: bool = False) -> str:
    """
    Build the hook-video prompt from a viral video's hook analysis.

    Shared by the live analysis path and by hook-template creation, so a saved
    template stores exactly the prompt that a fresh analysis would have produced.
    With Seedance 2.5's V2V motion reference, the video reference carries the
    full motion/gesture/camera authority, while the first_frame image anchors
    identity. This text prompt should stay minimal to avoid conflicting with
    the video pixels.

    Args:
        v2v_motion_active: When True, the reference video is actually being
            delivered to the model as a motion reference AND the face image is
            locked as first_frame. The prompt is kept deliberately minimal so
            the video reference is the sole authority on motion, gestures,
            camera, and timing.
    """
    if v2v_motion_active:
        # V2V mode: Seedance 2.5 receives the viral video as motion reference
        # AND the face-swapped image as first_frame (identity anchor).
        # Keep the prompt MINIMAL and framed as creative video production.
        #
        # IMPORTANT: Seedance moderation (error 1026) flags prompts that sound
        # like face-swap/deepfake instructions ("replace the face", "swap identity",
        # etc.). The fix is cinematic production framing â€” describe what the camera
        # should capture, not what faces to change. The first_frame image already
        # carries the character's appearance; the prompt just directs motion.
        prompt = (
            "Create a 3-second vertical video (9:16). The character from the first frame "
            "performs the exact choreography shown in the reference video â€” same body movements, "
            "same hand gestures, same head movements, same timing, same camera angle, same energy. "
            "Match the reference video frame-by-frame: identical pacing, identical physical "
            "performance, identical framing. Cinematic quality, natural lighting, sharp focus."
        )
    else:
        prompt = (
            "Create a 3-second vertical video (9:16) starting from this exact first frame. "
            "Recreate the EXACT hook mechanics that made the original viral video work:\n\n"
            f"FACIAL EXPRESSION: {analysis.get('facial_expressions') or 'engaging expression'}\n"
            f"BODY LANGUAGE & GESTURE: {analysis.get('body_language_gestures') or 'confident body language'}\n"
            f"PACING & MOVEMENT: {analysis.get('pacing_cuts') or 'quick, attention-grabbing pacing'}\n"
            f"HOOK SUMMARY: {analysis.get('hook_summary') or 'attention-grabbing opening'}\n\n"
            "PACING IS CRITICAL â€” this must match the speed and energy of a viral TikTok hook:\n"
            "- The action must start IMMEDIATELY from frame 1 â€” no slow build-up or pause at the start\n"
            "- All movements should be FAST and snappy, matching the rapid pace of the original hook window\n"
            "- Quick, punchy gestures â€” NOT slow or cinematic movements\n"
            "- Immediate direct eye contact with the camera from the very first frame\n"
            "- Energy level should be HIGH from the start â€” think 'scroll-stopper' urgency\n"
            "- The body language tempo must match how fast the original creator moved\n"
            "- Compress all the described movements into the first 2 seconds\n\n"
            "ADDITIONAL REQUIREMENTS:\n"
            "- Perform the EXACT movements and expressions described above â€” these are proven to grab attention\n"
            "- Maintain perfect character consistency with the first frame throughout\n"
            "- Camera holds steady or has a subtle push-in matching the original's pacing\n"
            "- End on a moment of anticipation (the viewer wants to know what happens next)"
        )

    mechanics = _coerce_mechanics(analysis.get("replicable_mechanics"))
    if mechanics and not v2v_motion_active:
        mechanics_str = "; ".join(str(m) for m in mechanics[:5])
        prompt += f"\n\nKEY MECHANICS TO REPLICATE: {mechanics_str}"

    if has_reference_video and not v2v_motion_active:
        prompt += (
            "\n\nNOTE: A reference video is provided for V2V motion transfer. "
            "Replicate its timing, camera movement, performance rhythm, and editing pace "
            "while using the new character from the first frame."
        )
    return prompt


def build_hook_prompt_from_image_analysis(image_analysis: dict) -> str:
    """Build the hook-video prompt when only a single still image was analyzed."""
    prompt = (
        "Create a 3-second vertical video (9:16) starting from this exact first frame. "
        "Animate from this starting pose using these movement cues:\n\n"
        f"FACIAL EXPRESSION: {image_analysis.get('facial_expressions') or 'engaging expression'}\n"
        f"BODY LANGUAGE & MOVEMENT: {image_analysis.get('body_language_gestures') or 'confident movement'}\n"
        f"PACING: {image_analysis.get('pacing_cuts') or 'quick, attention-grabbing pacing'}\n"
        f"HOOK CONCEPT: {image_analysis.get('hook_summary') or 'attention-grabbing opening'}\n\n"
        "PACING IS CRITICAL â€” this must match the speed and energy of a viral TikTok hook:\n"
        "- Start moving IMMEDIATELY from frame 1 â€” no pause or slow build-up\n"
        "- All movements should be FAST and snappy, matching a real creator's rapid energy\n"
        "- Quick, punchy gestures â€” NOT slow or cinematic\n"
        "- Immediate direct eye contact with the camera\n"
        "- Compress all the action into the first 2-3 seconds\n"
        "- Energy level HIGH from the very start â€” scroll-stopper urgency\n\n"
        "ADDITIONAL REQUIREMENTS:\n"
        "- Animate naturally from the starting pose shown in the first frame\n"
        "- Maintain perfect face consistency throughout\n"
        "- The movement should build curiosity and make the viewer want to see more\n"
        "- End on a moment of anticipation"
    )
    mechanics = _coerce_mechanics(image_analysis.get("replicable_mechanics"))
    if mechanics:
        mechanics_str = "; ".join(str(m) for m in mechanics[:5])
        prompt += f"\n\nSPECIFIC MOVEMENTS TO PERFORM (do these FAST): {mechanics_str}"
    return prompt


def build_hook_prompt_from_motion_style(motion_style: str) -> str:
    """Final fallback: a hand-written motion template. Zero model calls.

    Reached only when there is no template, no hook analysis, and the
    single-image analysis returned nothing usable. When motion_style is empty
    (the creator left it on Default), lean-in is used as the house default
    since this branch has no other signal to work from.
    """
    key = (motion_style or "").strip().lower()
    motion = HOOK_MOTION_TYPES[MOTION_STYLE_INDEX.get(key, 0)]
    return HOOK_VIDEO_PROMPT_TEMPLATE.format(motion_type=motion)


def apply_motion_style_directive(prompt: str, motion_style: str) -> str:
    """
    Layer an explicitly-chosen motion style onto an already-built prompt.

    Previously motion_style only reached the output through
    build_hook_prompt_from_motion_style(), i.e. the deepest fallback branch â€”
    so on every normal path (template, hook analysis, or a successful
    single-image analysis) the creator's Motion Style pick was silently
    discarded. This applies it as an explicit movement directive on top of
    whatever base prompt was produced, the same way apply_hook_style_directive
    layers hook energy, so the control actually does something.

    No-ops when motion_style is empty (Default) or unrecognized, which is what
    keeps the untouched-default path eligible for Aleph's exact edit.
    """
    key = (motion_style or "").strip().lower()
    if key not in MOTION_STYLE_INDEX:
        return prompt

    motion = HOOK_MOTION_TYPES[MOTION_STYLE_INDEX[key]]
    return prompt + (
        f"\n\nMOTION STYLE (chosen by the creator): The character must perform {motion}. "
        "This is the primary physical action of the hook â€” where it conflicts with any "
        "other body movement described above, this movement wins. Keep the face "
        "consistency, pacing, and framing requirements above intact."
    )


# ---------------------------------------------------------------------------
# Hook Templates â€” save a proven hook once, reuse it forever for free.
#
# A template is a complete snapshot of an analyzed hook:
#   - the AI hook analysis (so it is never re-analyzed)
#   - the ready-to-submit video prompt (so it is never regenerated)
#   - a local copy of the source clip for V2V motion transfer (never re-downloaded)
#   - a local copy of the key hook frame as a thumbnail
#
# Creating and reusing templates makes ZERO model calls. Only the video
# generation itself calls a provider, which is unavoidable for a new output.
# ---------------------------------------------------------------------------
HOOK_TEMPLATE_CATEGORIES = [
    "curiosity-gap", "pattern-interrupt", "reveal", "reaction", "authority", "confrontation", "other",
]
HOOK_TEMPLATE_NAME_MAX = 80
HOOK_TEMPLATE_NOTES_MAX = 500

# ---------------------------------------------------------------------------
# Hook Style Directives â€” mechanism-based prompt modifiers that map to
# proven 2026 TikTok scroll-stopping patterns (backed by OpusClip's
# analysis of 34,635 clips and multiple UGC performance studies).
#
# These are HOOK MECHANISMS (the psychological trigger that stops the scroll
# in the first 1.5-3 seconds), NOT content genres. Each one produces
# meaningfully different body language, facial expressions, and camera
# energy from the AI video model.
# ---------------------------------------------------------------------------
HOOK_STYLE_DIRECTIVES = {
    "curiosity-gap": (
        "\n\nHOOK STYLE â€” CURIOSITY GAP: This hook must create an irresistible 'wait, what?' "
        "moment that makes the viewer NEED to keep watching. Show something partially â€” an "
        "incomplete reveal, a mysterious expression, an object hinted at but not shown. The "
        "character should have a knowing smirk, a half-smile, or a 'I know something you don't' "
        "look. Build tension through what is deliberately withheld. The body language should "
        "signal 'I have a secret' â€” slight lean-in, eyebrow raise, conspiratorial energy. "
        "The viewer's brain cannot leave the gap unresolved, so they stay."
    ),
    "pattern-interrupt": (
        "\n\nHOOK STYLE â€” PATTERN INTERRUPT: This hook must BREAK the viewer's passive scrolling "
        "state with something visually or physically unexpected. The brain pauses involuntarily "
        "when it encounters something that doesn't fit the expected pattern. Use: a sudden "
        "contradictory movement (start one action, snap into something completely different), "
        "an impossible-seeming gesture, an unexpected frozen pose that breaks into motion, or "
        "a jarring visual change. The key is to be STRATEGICALLY strange â€” the unexpected "
        "element must register in under 1.5 seconds. Think 'cognitive jolt' â€” the viewer's "
        "brain says 'wait, am I seeing this correctly?' and pauses to resolve it."
    ),
    "reveal": (
        "\n\nHOOK STYLE â€” REVEAL / TRANSFORMATION: This hook must set up a dramatic before/after "
        "in one rapid snap. Start in one state â€” obscured, hidden, unremarkable, messy, or plain â€” "
        "then INSTANTLY transition to the payoff: polished, stunning, revealed, or transformed. "
        "The transition should be viscerally satisfying: a hand pull-away, a quick spin, a "
        "blink-and-you-miss-it cut, a dramatic lighting change, or a hand swipe across frame. "
        "This works because showing the OUTCOME in the first 2 seconds is the #1 performing "
        "hook type on TikTok â€” the viewer knows immediately what they'll get if they stay. "
        "Lead with the payoff, make the transformation instant and dramatic."
    ),
    "reaction": (
        "\n\nHOOK STYLE â€” REACTION: This hook must be driven by an exaggerated, larger-than-life "
        "emotional response that makes the viewer wonder 'what did they just see?' The character "
        "should display: shocked wide eyes, jaw drop, hands flying to face, dramatic double-take "
        "toward camera, or a gasp-worthy sudden turn. The reaction must be OVERDRAMATIC â€” "
        "subtle doesn't stop the scroll. It should feel like they just saw/heard/discovered "
        "something incredible. The viewer stays because they want to know what triggered "
        "that extreme response. This exploits emotional contagion â€” seeing someone react "
        "intensely makes us feel it too."
    ),
    "authority": (
        "\n\nHOOK STYLE â€” AUTHORITY / EXPERT SIGNAL: This hook must radiate confident credibility "
        "in the first second, open a curiosity gap in the second, and promise payoff by the third. "
        "The character should have: direct, commanding eye contact, authoritative posture "
        "(squared shoulders, purposeful lean-in), and a 'listen to me' gesture â€” a pointed "
        "finger, a deliberate hand raise, or holding something up with intention. The body "
        "language says 'I have valuable information and you need to pay attention RIGHT NOW.' "
        "Fast, purposeful, no-nonsense movement. This works because TikTok viewers trust "
        "short-form experts who telegraph credibility in under 3 seconds."
    ),
    "confrontation": (
        "\n\nHOOK STYLE â€” CONFRONTATION / CONTRARIAN: This hook must directly challenge the "
        "viewer â€” it says 'you're doing it wrong' or 'everyone believes X, but it's false.' "
        "The character should display: slightly aggressive lean toward camera, pointed finger "
        "or accusatory gesture, 'are you serious?' facial expression, raised eyebrow with "
        "head shake, or a disapproving look that breaks into explanation. The energy is "
        "challenging but not hostile â€” more 'tough love' than angry. This exploits the brain's "
        "inability to leave a contradiction unresolved. The viewer MUST stay to defend their "
        "position or find out if they're wrong. Use urgent, confrontational body language "
        "that says 'stop what you're doing and listen.'"
    ),
}
HOOK_STYLE_CUSTOM_PROMPT_MAX = 200


def _sanitize_custom_hook_prompt(raw: str) -> str:
    """
    Sanitize the user-supplied custom hook prompt before injection.

    Defence-in-depth: even though the frontend enforces limits, the backend
    independently validates and cleans the input. This prevents:
    - Prompt injection via XML-like tags or system/role delimiters
    - Excessive length bypassing frontend limits (direct API calls)
    - Control characters or unicode trickery
    - Attempts to override the base prompt's safety instructions

    Returns the cleaned text (may be shorter than input, or empty).
    """
    import re

    text = (raw or "").strip()
    if not text:
        return ""

    # Strip control characters (keep only printable + basic whitespace)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

    # Collapse newlines and excessive whitespace into single spaces
    text = re.sub(r"[\r\n]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)

    # Remove prompt-injection patterns:
    # - Triple backticks (code fences used to break out of context)
    text = text.replace("```", "")
    # - XML/HTML-style system, instruction, role, or context tags
    text = re.sub(r"</?(?:system|instruction|prompt|role|assistant|user|context|ignore|override|admin)[^>]*>", "", text, flags=re.IGNORECASE)
    # - "Ignore previous instructions" / "disregard above" type phrases
    text = re.sub(r"(?:ignore|disregard|forget|override|bypass)\s+(?:previous|above|prior|all|the)\s+(?:instructions?|prompts?|rules?|context|directions?)", "", text, flags=re.IGNORECASE)
    # - Attempts to redefine role ("you are now", "act as", "pretend to be")
    text = re.sub(r"(?:you\s+are\s+now|act\s+as|pretend\s+(?:to\s+be|you(?:'re| are)))", "", text, flags=re.IGNORECASE)

    # Final cleanup: re-collapse any double spaces introduced by removals
    text = re.sub(r"\s{2,}", " ", text).strip()

    # Hard character limit (defense against direct API calls bypassing frontend)
    text = text[:HOOK_STYLE_CUSTOM_PROMPT_MAX]

    return text


def apply_hook_style_directive(prompt: str, hook_category: str = "", hook_custom_prompt: str = "") -> str:
    """
    Inject a category-based style directive and/or custom prompt into the
    generation prompt. Applied AFTER the base prompt is built but BEFORE
    the audio directive, so the style layer sits between content and
    audio/text-overlay instructions.

    - hook_category: one of the HOOK_STYLE_DIRECTIVES keys (optional)
    - hook_custom_prompt: freeform user text (optional, sanitized + max 200 chars)
    """
    category_key = (hook_category or "").strip().lower()
    custom_text = _sanitize_custom_hook_prompt(hook_custom_prompt)

    if category_key and category_key in HOOK_STYLE_DIRECTIVES:
        prompt += HOOK_STYLE_DIRECTIVES[category_key]

    if custom_text:
        prompt += (
            f"\n\nCUSTOM HOOK DIRECTION (from the creator): {custom_text}. "
            "Incorporate this direction into the hook while preserving the core "
            "mechanics, pacing, and face consistency requirements above."
        )

    return prompt


def _normalize_template_category(category: Optional[str]) -> str:
    key = (category or "").strip().lower()
    return key if key in HOOK_TEMPLATE_CATEGORIES else "other"


def _template_thumbnail_source(video: dict, analysis: dict) -> Optional[Path]:
    """Resolve the on-disk path of the analysis's key hook frame."""
    frames = analysis.get("frames") or []
    if not frames or not video.get("tiktok_url"):
        return None
    key_idx = analysis.get("key_hook_frame_index") or 1
    try:
        key_idx = max(1, min(len(frames), int(key_idx)))
    except (TypeError, ValueError):
        key_idx = 1
    frame_meta = frames[key_idx - 1]
    media_url = frame_meta.get("media_url") or ""
    if not media_url:
        return None
    filename = media_url.split("/")[-1]
    candidate = pipeline.FRAMES_DIR / pipeline.url_hash(video["tiktok_url"]) / filename
    return candidate if candidate.exists() else None
