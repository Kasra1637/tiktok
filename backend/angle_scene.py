"""Where and when the video happens, owned by the selected angle (ADR 0084).

The angle's hook_promise is the opening moment, so its place (indoors or
outdoors) and time of day bind every later step: direction dropdowns, the
founder's saved look, template examples and the render prompt. Detection is
lexical and conservative: a text with no place or time words never conflicts.
Pure policy: no HTTP, AI, auth or persistence imports.
"""
import re
from typing import Optional

import character_policy

_OUTDOOR = (
    r"\boutside\b", r"\boutdoors?\b", r"\bsteps? out\b", r"\bstepping out\b",
    r"\bstreet\b", r"\bsidewalk\b", r"\bpavement\b", r"\bpark\b", r"\bparking lot\b",
    r"\btrail\b", r"\bpath\b", r"\bgarden\b", r"\bbalcony\b", r"\bbeach\b",
    r"\bmarket\b", r"\brooftop\b", r"\bbus stop\b", r"\bcrosswalk\b", r"\bcourtyard\b",
    r"\bplaza\b", r"\bopen air\b", r"\bwalk(?:s|ing)? (?:home|along|down|through|past|to)\b",
    r"\bcommut(?:e|es|ing)\b", r"\bstation\b", r"\bplatform\b", r"\bporch\b",
    r"\bstoop\b", r"\bcaf[e\u00e9]\b", r"\bhilltop\b", r"\bbridge\b", r"\bcampus\b",
    r"\bdriveway\b", r"\bbackyard\b", r"\bwaterfront\b", r"\bon a run\b",
    r"\bback steps?\b", r"\bfront steps?\b",
    r"\bout of the (?:office|building|house|car|gym|station)\b",
)
_INDOOR = (
    r"\bliving room\b", r"\bbedroom\b", r"\bin bed\b", r"\bbed\b", r"\blamp\b",
    r"\bcouch\b", r"\bsofa\b", r"\bkitchen\b", r"\bdesk\b", r"\bindoors?\b",
    r"\bhome office\b", r"\barmchair\b", r"\bwindow\b", r"\bbathroom\b",
    r"\bhallway\b", r"\bat home\b", r"\bcandle\b", r"\bbookshelf\b",
    r"\b(?:in|inside) (?:the|her|his|their|a|my) car\b", r"\bparked car\b",
    r"\boffice\b", r"\bcubicle\b", r"\bgym\b", r"\bapartment\b",
    r"\bdorm\b", r"\bclassroom\b", r"\blibrary\b", r"\bshower\b",
)
_TIMES = {
    "night": (r"\bnight\b", r"\bnighttime\b", r"\bmidnight\b", r"\bbedtime\b",
              r"\bafter dark\b", r"\beleven\b", r"\b(?:10|11|12) ?pm\b"),
    "morning": (r"\bmorning\b", r"\bsunrise\b", r"\bdawn\b", r"\bbreakfast\b",
                r"\b[5-9] ?am\b"),
    "evening": (r"\bevening\b", r"\bsunset\b", r"\bdusk\b", r"\bafter work\b",
                r"\bend of the (?:work ?)?day\b", r"\bcommute home\b"),
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
    """The angle's opening moment as a plain sentence fragment, capitalised.

    Identity-neutral like every other video-facing line: the founder's uploaded
    photo decides who is on screen, so the promise says "the person" and never
    names a gender or a role (ADR 0089).
    """
    text = re.sub(r"\s+", " ", str((angle or {}).get("hook_promise") or "")).strip().rstrip(".")
    text = character_policy.neutralize(text).strip()
    return _capitalise(text)


def angle_scene(angle: Optional[dict]) -> dict:
    """Moment, place and time of day the selected angle fixes for the video."""
    moment = angle_moment(angle)
    return {"moment": moment, **scene_of(moment)}


def scene_is_unclear(angle: Optional[dict]) -> bool:
    """True when the angle has an opening moment that names no place at all."""
    scene = angle_scene(angle)
    return bool(scene["moment"]) and not scene["place"]


def video_scene(angle: Optional[dict]) -> dict:
    """The angle's opening moment with its place and time of day made explicit.

    The promise owns where and when (ADR 0084). When the promise names neither,
    the Problem's own moment supplies what it leaves out: the two describe the
    same moment by construction, and a card that cannot say where the video
    happens tells the founder less than one that can. Neither field is ever
    invented — both come from text the founder's angle already carries.
    """
    scene = angle_scene(angle)
    if scene["place"] and scene["time"]:
        return scene
    from_problem = scene_of(str((angle or {}).get("user_problem") or ""))
    return {
        **scene,
        "place": scene["place"] or from_problem["place"],
        "time": scene["time"] or from_problem["time"],
    }


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


def _capitalise(text: str) -> str:
    text = str(text or "")
    return text[:1].upper() + text[1:] if text else ""


# Card lines, not paragraphs: the shape is the opening alone and the
# development is one beat, because a founder comparing six cards reads one line
# of each.
_SHAPE_LIMIT = 220
_BEAT_LIMIT = 150


def _first_sentence(text: str) -> str:
    """The first sentence of `text`, or the whole of it when it has no full stop."""
    blob = re.sub(r"\s+", " ", str(text or "")).strip()
    if not blob:
        return ""
    match = re.match(r"(.+?[.!?])(?:\s|$)", blob)
    return (match.group(1) if match else blob).strip()


def _clip(text: str, limit: int) -> str:
    """`text` cut at a word boundary, with an ellipsis when anything was cut."""
    text = str(text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,;:-\u2014")
    return cut + "\u2026"


def _development_beat(template: dict, scene: dict) -> str:
    """The template's first middle beat, ready to follow the opening, or "".

    Dropped when it moves the video somewhere the angle does not go: a middle
    that relocates the story is a second opening wearing a middle's clothes.
    """
    template = template or {}
    middle = _first_sentence(
        template.get("middle_structure") or template.get("continuation_structure")
    )
    if not middle or conflict_reason(middle, scene):
        return ""
    beat = character_policy.neutralize(middle).rstrip(".")
    # The prompt asks the middle to stop at the moment the viewer would reach
    # for the app, and models echo that instruction back as the last clause.
    # It is an instruction to the writer, not a second beat, so it goes.
    beat = re.split(
        r"[,;]?\s*(?:and |then )?(?:stops|stopping|ends|ending) at the moment\b",
        beat,
    )[0].rstrip(" ,;:-\u2014")
    if not beat:
        return ""
    if beat[:1].isupper() and not beat.startswith(("I ", "I'")):
        beat = beat[:1].lower() + beat[1:]
    # The card labels the line itself ("Develops as"), and a middle that opens
    # with "Then" would read as a second opening. A middle written in the
    # prompt's own meta voice ("The middle names the cost") keeps the label
    # rather than the noun, so the line describes the video and not the writing.
    beat = re.sub(r"^then\s+", "", beat, flags=re.IGNORECASE)
    beat = re.sub(r"^(?:the |this )?(?:middle|video|piece|rest)\s+", "", beat, flags=re.IGNORECASE)
    if not beat:
        return ""
    return _clip(beat, _BEAT_LIMIT)


def opening_shape(angle: Optional[dict], template: Optional[dict] = None) -> str:
    """The one opening this card makes, built from the First 3 Seconds Promise.

    "Shape" used to be the template's own first-seconds staging while the card
    printed the angle's promise underneath as "In your video", so a single card
    described two different openings (ADR 0089). The shape is now the promise
    itself — one character doing one thing — and nothing else: a template's own
    opening never speaks here, so nothing on the card can disagree with what the
    render opens on. What the template adds is its development, which the card
    prints as its own line (`opening_development`), never as a second opening.
    """
    promise = angle_moment(angle)
    if not promise:
        # No promise on this angle: the template's own staging is the only
        # opening on record, and it is shown neutralized like everything else.
        return character_policy.neutralize(
            str((template or {}).get("opening_structure") or "")
        ).strip()
    return _clip(promise.rstrip(".") + ".", _SHAPE_LIMIT)


def opening_development(angle: Optional[dict], template: Optional[dict] = None) -> str:
    """How THIS template develops that one opening, or "" when it cannot.

    A middle that relocates the video, or that has nothing to say, leaves the
    card with the opening alone rather than inventing a beat. Returned without
    a leading capital because the card prints it as a clause, not a sentence.
    """
    if not angle_moment(angle):
        return ""
    return _development_beat(template or {}, video_scene(angle))


def opening_staging(angle: Optional[dict]) -> str:
    """Where and when the opening happens, and where the character comes from.

    The card's second line: the shape says what happens, this says where and
    when it happens and that the person on screen is the founder's uploaded
    photo. Never a described face or a named kind of person (ADR 0089).
    """
    scene = video_scene(angle)
    if not scene["moment"]:
        return ""
    where = _where(scene)
    look = "The character's look comes from the photo you upload."
    return f"{_capitalise(where)}. {look}" if where else look


def fit_direction_options(options: dict, angle: Optional[dict]) -> dict:
    """Direction dropdowns with every option that contradicts the angle removed.

    The angle's own moment leads the Location list, so the first choice is the
    place the angle opens in. Lists are topped up with place-safe fallbacks
    so a filtered dropdown is never left with one lonely option.
    """
    scene = angle_scene(angle)
    out = dict(options or {})
    out["angle_moment"] = scene["moment"]
    if not scene["moment"]:
        return out
    fallbacks = {
        "location": [scene["moment"]],
        "lighting": _LIGHTING_FALLBACKS.get((scene["place"], scene["time"]), [])
        + _LIGHTING_FALLBACKS.get((scene["place"], ""), []),
        "voice": _VOICE_FALLBACKS.get(scene["place"], []),
    }
    for field in ("location", "lighting", "wardrobe", "voice", "tone"):
        kept = [o for o in (out.get(field) or []) if not conflict_reason(o, scene)]
        if field == "location":
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
    """How a template reads against the angle's opening.

    `structure` is the plain reason the template's fixed shape contradicts the
    angle (it is ranked lower and labelled); `example_conflicts` means only
    its sample wording does, so the card shows the angle's moment instead.
    `shape` and `staging` are the two lines the card prints: one opening built
    from the promise, and where and when that opening happens; `development` is
    what this template does next, printed as its own line (ADR 0089).
    """
    scene = angle_scene(angle)
    structural = " ".join(
        str((template or {}).get(k) or "") for k in ("opening_structure", "visual_style")
    )
    reason = conflict_reason(structural, scene)
    example = conflict_reason(str((template or {}).get("example_preview") or ""), scene)
    return {
        "moment": scene["moment"],
        "shape": opening_shape(angle, template),
        "staging": opening_staging(angle),
        "development": opening_development(angle, template),
        "structure": (
            f"Doesn't fit this angle: its opening {reason}, but your angle opens {_where(scene)}."
            if reason else ""
        ),
        "example_conflicts": bool(example),
    }
