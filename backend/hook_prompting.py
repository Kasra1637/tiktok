"""Hook-video prompt vocab: motion styles, style directives, templates.

Retained for existing records and the disabled creation routes'
`DISABLED_LEGACY_CREATION_ROUTES` vocabulary (`/hook-motion-styles`,
hook-template categories). The prompt builders that consumed this vocab
(`build_hook_prompt_*`, `apply_*_directive`, `HOOK_VIDEO_PROMPT_TEMPLATE`)
were removed — no live caller remains; the vocab constants below are the
sole survivors and are mirrored in `frontend/src/lib/hookTemplateCategories.js`.
"""

import json
from pathlib import Path
from typing import Optional

import pipeline



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




