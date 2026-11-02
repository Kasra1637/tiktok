"""Where and when the video happens, owned by the selected angle (ADR 0084).

The angle's hook_promise is the opening moment, so its place (indoors or
outdoors) and time of day bind every later step: direction dropdowns, the
founder's saved look, template examples and the render prompt. Detection is
lexical and conservative: a text with no place or time words never conflicts.
Pure policy: no HTTP, AI, auth or persistence imports.
"""
import re
from typing import Optional

_OUTDOOR = (
    r"\boutside\b", r"\boutdoors?\b", r"\bsteps? out\b", r"\bstepping out\b",
    r"\bstreet\b", r"\bsidewalk\b", r"\bpavement\b", r"\bpark\b", r"\bparking lot\b",
    r"\btrail\b", r"\bpath\b", r"\bgarden\b", r"\bbalcony\b", r"\bbeach\b",
    r"\bmarket\b", r"\brooftop\b", r"\bbus stop\b", r"\bcrosswalk\b", r"\bcourtyard\b",
    r"\bplaza\b", r"\bopen air\b", r"\bwalk(?:s|ing)? (?:home|along|down|through|past|to)\b",
)
_INDOOR = (
    r"\bliving room\b", r"\bbedroom\b", r"\bin bed\b", r"\bbed\b", r"\blamp\b",
    r"\bcouch\b", r"\bsofa\b", r"\bkitchen\b", r"\bdesk\b", r"\bindoors?\b",
    r"\bhome office\b", r"\barmchair\b", r"\bwindow\b", r"\bbathroom\b",
    r"\bhallway\b", r"\bat home\b", r"\bcandle\b", r"\bbookshelf\b",
)
_TIMES = {
    "night": (r"\bnight\b", r"\bnighttime\b", r"\bmidnight\b", r"\bbedtime\b",
              r"\bafter dark\b", r"\beleven\b", r"\b(?:10|11|12) ?pm\b"),
    "morning": (r"\bmorning\b", r"\bsunrise\b", r"\bdawn\b", r"\bbreakfast\b",
                r"\b[5-9] ?am\b"),
    "evening": (r"\bevening\b", r"\bsunset\b", r"\bdusk\b"),
    "midday": (r"\bnoon\b", r"\bmidday\b", r"\blunch\b", r"\bafternoon\b"),
}
_TIME_CLASH = {
    "night": {"morning", "midday"},
    "morning": {"night", "evening"},
    "evening": {"morning", "midday"},
    "midday": {"night", "evening"},
}
_TIME_WORDS = {
    "night": "at night", "morning": "in the morning",
    "evening": "in the evening", "midday": "in the middle of the day",
}
_LIGHTING_FALLBACKS = {
    ("outdoor", ""): ["Natural open daylight", "Soft overcast daylight outside"],
    ("outdoor", "night"): ["Streetlight and shop-window glow", "Cool city light after dark"],
    ("outdoor", "morning"): ["Fresh early-morning daylight outside"],
    ("outdoor", "evening"): ["Low warm evening sun outside"],
    ("indoor", ""): ["Soft even light in the room", "Warm practical light in the room"],
    ("indoor", "night"): ["Dim warm light late at night"],
    ("indoor", "morning"): ["Soft morning light in the room"],
}
_VOICE_FALLBACKS = {
    "outdoor": ["Natural talking-while-walking delivery"],
    "indoor": [],
}
_MIN_OPTIONS = 3


def _first_hit(text: str, patterns) -> int:
    hits = [m.start() for p in patterns for m in [re.search(p, text)] if m]
    return min(hits) if hits else -1


def scene_of(text: str) -> dict:
    """The place and time of day a piece of text names, or "" for each it does not."""
    blob = str(text or "").lower()
    outdoor, indoor = _first_hit(blob, _OUTDOOR), _first_hit(blob, _INDOOR)
    if outdoor >= 0 and (indoor < 0 or outdoor <= indoor):
        place = "outdoor"
    elif indoor >= 0:
        place = "indoor"
    else:
        place = ""
    found = [(pos, name) for name, pats in _TIMES.items() for pos in [_first_hit(blob, pats)] if pos >= 0]
    time = min(found)[1] if found else ""
    return {"place": place, "time": time}


def angle_moment(angle: Optional[dict]) -> str:
    """The angle's opening moment as a plain sentence fragment, capitalised."""
    text = re.sub(r"\s+", " ", str((angle or {}).get("hook_promise") or "")).strip().rstrip(".")
    return text[:1].upper() + text[1:] if text else ""


def angle_scene(angle: Optional[dict]) -> dict:
    """Moment, place and time of day the selected angle fixes for the video."""
    moment = angle_moment(angle)
    return {"moment": moment, **scene_of(moment)}


def conflict_reason(text: str, scene: dict) -> str:
    """Why `text` contradicts the angle's scene, in plain words, or "" if it does not."""
    if not scene or not (scene.get("place") or scene.get("time")):
        return ""
    found = scene_of(text)
    if scene.get("place") and found["place"] and found["place"] != scene["place"]:
        return "is set indoors" if found["place"] == "indoor" else "is set outdoors"
    if scene.get("time") and found["time"] in _TIME_CLASH.get(scene["time"], set()):
        return f"is set {_TIME_WORDS[found['time']]}"
    return ""


def _where(scene: dict) -> str:
    bits = []
    if scene.get("place"):
        bits.append("outdoors" if scene["place"] == "outdoor" else "indoors")
    if scene.get("time"):
        bits.append(_TIME_WORDS[scene["time"]])
    return " ".join(bits)


def fit_direction_options(options: dict, angle: Optional[dict]) -> dict:
    """Direction dropdowns with every option that contradicts the angle removed.

    The angle's own moment leads the setting list, so the first choice is the
    place the angle opens in. Lists are topped up with place-safe fallbacks
    so a filtered dropdown is never left with one lonely option.
    """
    scene = angle_scene(angle)
    out = dict(options or {})
    out["angle_moment"] = scene["moment"]
    if not scene["moment"]:
        return out
    fallbacks = {
        "setting": [scene["moment"]],
        "lighting": _LIGHTING_FALLBACKS.get((scene["place"], scene["time"]), [])
        + _LIGHTING_FALLBACKS.get((scene["place"], ""), []),
        "voice": _VOICE_FALLBACKS.get(scene["place"], []),
    }
    for field in ("setting", "lighting", "wardrobe", "voice", "tone"):
        kept = [o for o in (out.get(field) or []) if not conflict_reason(o, scene)]
        if field == "setting":
            kept = [scene["moment"]] + [o for o in kept if o.lower() != scene["moment"].lower()]
        for extra in fallbacks.get(field, []):
            if len(kept) >= _MIN_OPTIONS:
                break
            if extra not in kept and not conflict_reason(extra, scene):
                kept.append(extra)
        out[field] = kept
    return out


def reconcile_look(visual_direction: str, angle: Optional[dict]) -> dict:
    """The founder's look with any part that contradicts the angle replaced.

    The angle wins (ADR 0084): a clause naming another place or time of day is
    dropped, the angle's moment takes its place, and `note` tells the founder
    what changed. A look that already agrees comes back untouched.
    """
    text = str(visual_direction or "").strip()
    scene = angle_scene(angle)
    if not text or not scene["moment"]:
        return {"visual_direction": text, "note": "", "dropped": []}
    parts = [p for p in re.split(r"\s*[,;]\s*", text) if p.strip()]
    dropped = [p for p in parts if conflict_reason(p, scene)]
    if not dropped:
        return {"visual_direction": text, "note": "", "dropped": []}
    kept = [p for p in parts if p not in dropped]
    if not any(p.lower() == scene["moment"].lower() for p in kept):
        kept.insert(0, scene["moment"])
    where = _where(scene)
    note = (
        f"I adjusted your look to match your angle. It said \u201c{'; '.join(dropped)}\u201d, "
        f"but your angle opens {where + ': ' if where else 'on: '}{scene['moment'][:1].lower() + scene['moment'][1:]}."
    )
    return {"visual_direction": ", ".join(kept), "note": note, "dropped": dropped}


def template_angle_fit(template: dict, angle: Optional[dict]) -> dict:
    """Whether a template's own staging can happen where the angle opens.

    `structure` is the plain reason the template's fixed shape contradicts the
    angle (it is ranked lower and labelled); `example_conflicts` means only
    its sample wording does, so the card shows the angle's moment instead.
    """
    scene = angle_scene(angle)
    structural = " ".join(
        str((template or {}).get(k) or "") for k in ("opening_structure", "visual_style")
    )
    reason = conflict_reason(structural, scene)
    example = conflict_reason(str((template or {}).get("example_preview") or ""), scene)
    return {
        "moment": scene["moment"],
        "structure": (
            f"Doesn't fit this angle: its opening {reason}, but your angle opens {_where(scene)}."
            if reason else ""
        ),
        "example_conflicts": bool(example),
    }
