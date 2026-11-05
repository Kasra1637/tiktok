"""The last beat of a selfie render: a physical ending, never a phone (ADR 0093).

In a selfie-style video the camera IS the phone in the character's hand, so
nothing at the end — or anywhere on camera — can be a phone being raised,
held or shown: the recording device cannot appear as a prop. Fixed-camera
renders (phone on a stand, both hands free) keep the phone handoff.

For selfie, the ending is ONE short physical beat in the same final moment:
physical only, no extra words or time, with a split-second hold before the
cut. A curated list is rotated per render so consecutive renders do not
repeat, preferring beats whose mood matches the strategy's emotional
triggers. Detection of phone mentions is lexical and conservative: a phone
that is only reached for is the story's handoff moment, not a device on
camera, so it is left alone.

Pure policy: no HTTP, AI, auth or persistence imports.
"""
import copy
import re

SELFIE = "handheld"
FIXED = "fixed"

# Each beat: physical, camera-facing, and it ends on a hold. `moods` prefers a
# beat that fits the hook's mood when the strategy names emotions.
ENDINGS = (
    {"text": "Eyes drop off to the side for a beat, then snap back to the lens with a small nod.",
     "moods": ("recognition", "relief", "realization")},
    {"text": "A slow head tilt with a half smile, eyes holding the lens.",
     "moods": ("amusement", "warmth", "playfulness")},
    {"text": "Shoulders drop with a long exhale, then a small nod to the lens.",
     "moods": ("relief", "calm")},
    {"text": "Eyebrows lift once, then settle into a knowing look straight down the lens.",
     "moods": ("recognition", "surprise", "curiosity")},
    {"text": "A sharp little laugh through the nose, then a slow blink and a nod.",
     "moods": ("amusement", "recognition")},
    {"text": "Lips press together, one firm nod, and the eyes soften on the lens.",
     "moods": ("determination", "resolve", "confidence")},
    {"text": "A long blink, then the eyes come back up to the lens with a small, satisfied nod.",
     "moods": ("relief", "satisfaction")},
    {"text": "A glance down for a heartbeat, an almost-smiling head shake, then the eyes return to the lens.",
     "moods": ("amusement", "recognition")},
    {"text": "One slow exhale through the nose, shoulders easing, eyes steady on the lens.",
     "moods": ("calm", "relief")},
    {"text": "A quick eyebrow raise and a corner-of-the-mouth smile, held on the lens.",
     "moods": ("playfulness", "confidence", "curiosity")},
    {"text": "They still for a beat, then give one slow nod, eyes locked on the lens.",
     "moods": ("resolve", "gravity", "determination")},
    {"text": "Head tilts, the eyes narrow playfully, then widen with a small nod at the lens.",
     "moods": ("curiosity", "playfulness", "surprise")},
)

DEFAULT_ENDING = ENDINGS[0]["text"]

# A phone being held, raised, shown, lifted or pointed at — the recording
# device cannot appear in a selfie frame. Reaching for a phone is the story's
# handoff moment, not a device on camera, so it is deliberately not matched.
_PHONE_ENDING_RE = re.compile(
    r"(?:rais\w+|hold\w*|show\w*|lift\w*|point\w*|bring\w*|push\w*|pick\w*"
    r"|tak\w*|pull\w*|get\w*|grab\w*)\s+(?:\w+\s+){0,2}?"
    r"(?:the|her|his|their|my|your|a)\s+phone"
    r"|(?:the|her|his|their|my|your|a)\s+phone\s+"
    r"(?:into|up|toward|towards|out|appears?|shows?|comes?)"
    r"|screen\s+(?:facing|to)\s+(?:the\s+)?(?:camera|lens|her|him|them)"
    r"|\bphone\s+(?:into view|up to|to the)",
    re.I,
)


def is_selfie(strategy) -> bool:
    """True when the camera is held by the character (handheld selfie)."""
    return str((strategy or {}).get("camera_setup") or SELFIE) != FIXED


def examples(count: int = 3) -> str:
    """A few ending beats, for the generation prompts' examples."""
    return "; ".join(entry["text"].rstrip(".") for entry in ENDINGS[:count])


def pick(strategy, exclude=(), index: int = 0) -> str:
    """One ending for this render: mood-matched, not among `exclude`.

    `index` is the render's ordinal for the project, so consecutive renders
    walk the list instead of repeating; `exclude` removes endings already used
    (including the strategy's own, if it carries one).
    """
    used = {" ".join(str(text or "").split()).strip(" .").casefold()
            for text in exclude if str(text or "").strip()}
    pool = [entry for entry in ENDINGS
            if " ".join(entry["text"].split()).strip(" .").casefold() not in used]
    if not pool:
        pool = list(ENDINGS)
    triggers = " ".join(
        str(item) for item in ((strategy or {}).get("emotional_triggers") or [])
    ).casefold()
    if triggers:
        preferred = [entry for entry in pool
                     if any(mood in triggers for mood in entry["moods"])]
        if preferred:
            pool = preferred
    return pool[index % len(pool)]["text"]


def split_phone_clauses(text):
    """`text` as (kept, removed): clauses that hold or show a phone are removed.

    A text made entirely of phone clauses comes back as ("", removed) so the
    caller can replace it whole.
    """
    raw = " ".join(str(text or "").split())
    if not raw or not _PHONE_ENDING_RE.search(raw):
        return raw, ""
    clauses = [c.strip() for c in re.split(
        r"(?<=[.!?])\s+|,\s+|;\s+|\s+and\s+(?=[a-z])", raw, flags=re.I,
    ) if c.strip()]
    kept = [c for c in clauses if not _PHONE_ENDING_RE.search(c)]
    removed = [c for c in clauses if _PHONE_ENDING_RE.search(c)]
    if not kept:
        return "", ", ".join(removed)
    return ", ".join(kept), ", ".join(removed)


def strip_props(props):
    """Props without the phone; returns (text, changed)."""
    parts = [p.strip() for p in re.split(r"\s*[,;]\s*", str(props or "")) if p.strip()]
    if not parts:
        return str(props or ""), False
    kept = [p for p in parts if not re.search(r"\bphones?\b", p, re.I)]
    if len(kept) == len(parts):
        return ", ".join(parts), False
    return ", ".join(kept), True


def strip_fields(strategy):
    """Remove every phone held or shown from a selfie strategy's own fields.

    Returns {"strategy", "changed"}: a copy with the phone clauses dropped
    from the hook action, section actions, movement, props and the camera
    fields. The chosen ending is applied afterwards by the caller.
    """
    result = copy.deepcopy(strategy) if isinstance(strategy, dict) else {}
    changed = []
    if not result:
        return {"strategy": result, "changed": changed}

    for key, label in (
        ("hook_action", "Opening action"),
        ("hook_dialogue", "Hook dialogue"),
    ):
        kept, removed = split_phone_clauses(result.get(key))
        if removed:
            result[key] = kept
            changed.append(label)

    for section in result.get("segments") or []:
        if not isinstance(section, dict):
            continue
        kept, removed = split_phone_clauses(section.get("action"))
        if removed:
            section["action"] = kept
            role = str(section.get("role") or "hook").strip().capitalize()
            changed.append(f"{role} — what they do")

    performance = result.get("performance") if isinstance(result.get("performance"), dict) else None
    if performance is not None:
        kept, removed = split_phone_clauses(performance.get("movement"))
        if removed:
            performance["movement"] = kept
            changed.append("Movement")

    scene = result.get("scene") if isinstance(result.get("scene"), dict) else None
    if scene is not None:
        for key, label in (("framing", "Framing"), ("camera_angle", "Camera angle")):
            value = str(scene.get(key) or "")
            if _PHONE_ENDING_RE.search(value):
                kept, _removed = split_phone_clauses(value)
                scene[key] = kept
                changed.append(label)
        props, removed = strip_props(scene.get("props"))
        if removed:
            scene["props"] = props
            changed.append("Props")
    return {"strategy": result, "changed": changed}


def apply_ending(strategy, ending: str):
    """Write the chosen ending into the middle action and the movement.

    The ending is the last clause of the middle section's action and of the
    movement line — the same final moment the phone handoff used to occupy,
    physical only, held for a split second before the cut.
    """
    result = copy.deepcopy(strategy) if isinstance(strategy, dict) else {}
    changed = []
    ending = " ".join(str(ending or "").split()).rstrip(".")
    if not result or not ending:
        return {"strategy": result, "changed": changed}

    def _has_ending(text):
        return ending.casefold() in " ".join(str(text or "").split()).casefold()

    def _append(text):
        base = " ".join(str(text or "").split()).strip(" .;")
        if not base:
            return ending[:1].upper() + ending[1:] + "."
        if _has_ending(base):
            return base if base.endswith(".") else base + "."
        text = f"{base}; {ending}."
        return text[:1].upper() + text[1:]

    sections = result.get("segments") or []
    middle = None
    for section in sections:
        if isinstance(section, dict) and str(section.get("role") or "").lower() == "middle":
            middle = section
            break
    if middle is None and len(sections) > 1 and isinstance(sections[1], dict):
        middle = sections[1]
    if middle is not None and not _has_ending(middle.get("action")):
        middle["action"] = _append(middle.get("action"))
        changed.append("Middle — what they do")

    performance = result.get("performance") if isinstance(result.get("performance"), dict) else None
    if performance is not None and not _has_ending(performance.get("movement")):
        performance["movement"] = _append(performance.get("movement"))
        changed.append("Movement")

    result["final_beat"] = ending + "."
    return {"strategy": result, "changed": changed}
