"""The last beat of a selfie render: a physical ending, never a phone (ADR 0093).

In a selfie-style video the camera IS the phone in the character's hand, so
nothing at the end — or anywhere on camera — can be a phone being raised,
held or shown, and the character can never reach toward, hold, raise or show
a phone or camera at any point. One hand holds the camera, so no action may
need a second free hand. Fixed-camera renders (phone on a stand, both
hands free) keep the phone handoff.

For selfie, the ending is ONE short physical beat in the same final moment:
physical only, no extra words or time, with a split-second hold before the
cut. A curated list is rotated per render so consecutive renders do not
repeat, preferring beats whose mood matches the strategy's emotional
triggers. Detection of forbidden clauses is lexical and conservative: a
negated mention (``no phone on camera``, ``never raises the phone``) is a
rule, not an action, so it is left alone. Spoken words are never rewritten
here — this module strips direction/action wording only.

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

# A phone or camera being held, raised, shown, lifted, pointed at or reached
# for — the recording device cannot appear in a selfie frame, and a hand
# cannot reach toward the lens/phone/camera either. Reaching toward the lens
# is also matched: in a selfie that gesture is the old handoff reframed.
_PHONE_ENDING_RE = re.compile(
    r"(?:rais\w+|hold\w*|show\w*|lift\w*|point\w*|bring\w*|push\w*|pick\w*"
    r"|tak\w*|pull\w*|get\w*|grab\w*|extend\w*|stretch\w*|wave\w*)"
    r"\s+(?:\w+\s+){0,2}?(?:the|her|his|their|my|your|a)\s+(?:phone|camera)\b(?!\s+call)"
    r"|(?:the|her|his|their|my|your|a)\s+(?:phone|camera)\s+"
    r"(?:into|up|toward|towards|out|appears?|shows?|comes?)"
    r"|screen\s+(?:facing|to)\s+(?:the\s+)?(?:camera|lens|her|him|them)"
    r"|\bphone\s+(?:into view|up to|to the)"
    r"|\b(?:phone|camera)\s+in\s+(?:her|his|their|my|your|the)\s+hands?\b"
    r"|\breach\w*\s+(?:out\s+)?for\s+"
    r"(?:the\s+|her\s+|his\s+|their\s+|my\s+|your\s+|a\s+)?"
    r"(?:phone|camera)\b"
    r"|\breach\w*\s+(?:\w+\s+){0,4}?towards?\s+(?:the\s+)?(?:phone|camera|lens)\b"
    r"|\breach\w*\s+(?:a\s+|her\s+|his\s+|their\s+|my\s+|your\s+|the\s+)?"
    r"(?:hands?|arms?)\s+(?:towards?|to|at)\s+(?:the\s+)?(?:lens|camera|phone)\b"
    r"|\b(?:hands?|arms?)\s+(?:reach\w+|extend\w*|stretch\w*|push\w*|go\w*|move\w*)"
    r"\s+(?:\w+\s+){0,3}?(?:towards?|to|at)\s+(?:the\s+)?(?:lens|camera|phone)\b",
    re.I,
)

# A phone or camera named as an OBJECT of the action. In a selfie the camera
# IS the phone in the character's hand, so a second phone in the frame is the
# recording device appearing as a prop (ADR 0093) — the shot would contradict
# its own premise. "A phone call" is not a phone on camera, so it is spared.
_PHONE_OBJECT_RE = re.compile(
    r"\b(?:the|her|his|their|my|your|a|an)\s+(?:phone|camera)\b(?!\s+call)",
    re.I,
)

# One hand holds the camera in a selfie, so an action that needs a second
# free hand cannot be filmed. ``both hands in frame`` is visibility, not an
# action, so the pattern needs a using/with/in before the second hand.
_SECOND_HAND_RE = re.compile(
    r"\b(?:with|using|uses|use|in)\s+(?:\w+\s+){0,2}?(?:both|two|other|second|free)\s+hands?\b"
    r"|\bclaps?\b|\bclapping\b",
    re.I,
)

_NEGATION_RE = re.compile(r"\b(?:no|never|not|without)\b", re.I)

# An app surface on camera is impossible in a selfie for the same reason a
# phone is: the camera IS the phone, so there is no second device showing a
# chart, and one hand holds the camera while the other may grip the rail —
# a thumb has no job left to scroll with. Clauses that look at, scroll, swipe
# or tap a chart/graph/screen/report/dashboard — or thumb-tap/scroll on the
# phone's behalf ("thumb taps once to scroll", "scrolls my week") — are
# therefore forbidden in action/direction wording for selfie, never in
# spoken words (never rewritten here). "Stop the scroll" (the viewer
# scrolling past) is not a clause this matches on its own: "scroll" there
# has no surface noun and no thumb, and is only caught when paired with a
# chart/screen/app/phone/week noun, which that idiom never carries.
# Detection works by keywords, so paraphrases that never repeat those
# keywords ("looks at the screen", "a thumb on the display") are covered by
# looking verb + surface noun pairs, never by one fixed wording.
_SCREEN_SURFACE_RE = re.compile(
    r"\b(?:charts?|graphs?|dashboards?|reports?|screens?|displays?|timelines?|"
    r"calendars?|histories|summaries|logs?|entries|trackers?)\b",
    re.I,
)
_SCREEN_LOOK_RE = re.compile(
    r"\b(?:looks?|looking|glances?|glancing|stares?|staring|peers?|peering|"
    r"checks?|checking|reads?|reading|views?|viewing|opens?|opening|"
    r"pulls?|shows?|taps?)\b[^.;,]{0,24}?\b(?:screen|display|chart|graph|"
    r"dashboard|report|phone|app|timeline|calendar|history|summary|log|"
    r"entry|tracker|feed|app screen|display panel)\b"
    r"|\b(?:eyes?|gaze)\s+(?:drop|drops|dropped|fall|falls|fell|land|lands|"
    r"locked|fixed|on|down)\b[^.;,]{0,16}?\b(?:screen|display|chart|phone|app)\b"
    r"|\b(?:thumb|finger)\s+(?:on|over|against)\s+(?:the\s+)?"
    r"(?:screen|display|chart|graph|app|phone|trackpad)\b"
    r"|\bthumb\s+(?:taps?|presses|hits|slides|swipes|scrolls)\b",
    re.I,
)
_SCREEN_OTHER_RE = re.compile(
    r"\b(?:taps?|tapping|presses|pressing|hits|hitting|flicks|flicking|"
    r"drags|dragging)\b[^.;,]{0,24}?\b(?:screen|display|app|phone|chart|graph|"
    r"button|icon|tab|menu)\b"
    r"|\b(?:thumb|finger)s?\s+(?:slides?|sliding|flicks?|flicking|drags?|"
    r"dragging|presses|pressing|hits|hitting)\b"
    r"|\b(?:thumb|finger)s?\s+(?:taps?|tapping|scrolls?|scrolled|scrolling|"
    r"swipes?|swiping)\b",
    re.I,
)
_SCREEN_INTERACTION_RE = re.compile(
    r"\b(?:charts?|graphs?|dashboards?|reports?|screens?|displays?|timelines?|"
    r"calendars?|histories|entries|logs?|trackers?)\b"
    r"|\b(?:scrolls|scrolled|scrolling|swipes|swiped|swiping)\b"
    r"(?:\s+(?:it|this|that|the|my|your|their|screen|display|chart|graph|"
    r"app|phone|week|timeline|calendar|history|summary|log|entry|tracker))?"
    r"|\b(?:thumb|finger)s?\s+(?:taps?|tapping|scrolls?|scrolled|scrolling|"
    r"swipes?|swiping)\b"
    r"|\b(?:taps?|tapping|presses|pressing|hits|hitting)\b[^.;,]{0,24}?"
    r"\b(?:screen|display|app|phone|chart|graph|button|icon|tab|menu)\b",
    re.I,
)

# A bare "phone" is still the recording device on camera: "Phone stays
# face-down on the step" names it without a determiner, which the object
# pattern above cannot see. The selfie strip reads this separately so camera
# direction ("handheld camera", "the camera pushes in") is never mistaken for
# a phone in the frame.
_PHONE_WORD_RE = re.compile(
    r"\b(?:phones?|smartphones?|cell\s*phones?|mobile\s*phones?|iphones?)\b",
    re.I,
)
_PHONE_CALL_RE = re.compile(r"\bphone\s+call\b", re.I)


def _clause_mentions_phone(clause) -> bool:
    """True when a clause names a phone as an object, even without "the"."""
    text = str(clause or "")
    if _PHONE_CALL_RE.search(text):
        return False
    for match in _PHONE_WORD_RE.finditer(text):
        prefix = text[max(0, match.start() - 70):match.start()]
        if _NEGATION_RE.search(prefix):
            continue
        return True
    return False


def _clause_has_screen_action(clause) -> bool:
    """True when a clause looks at or works a chart/graph/screen surface.

    Negated mentions ("no chart on camera") are rules, not actions, so a
    match whose prefix carries a negation is spared, mirroring the phone
    and second-hand checks above.
    """
    text = str(clause or "")
    for pattern in (_SCREEN_INTERACTION_RE, _SCREEN_LOOK_RE, _SCREEN_OTHER_RE):
        for match in pattern.finditer(text):
            prefix = text[max(0, match.start() - 70):match.start()]
            if _NEGATION_RE.search(prefix):
                continue
            return True
    return False


def _clause_mentions_phone_or_screen(clause) -> bool:
    """True when a camera-field clause names a phone or a screen surface."""
    text = str(clause or "")
    if _clause_mentions_phone(text):
        return True
    if _clause_has_screen_action(text):
        return True
    for match in _SCREEN_SURFACE_RE.finditer(text):
        prefix = text[max(0, match.start() - 70):match.start()]
        if _NEGATION_RE.search(prefix):
            continue
        return True
    return False


def _split_clauses(text) -> list:
    return [c.strip() for c in re.split(
        r"(?<=[.!?])\s+|,\s+|;\s+|\s+while\s+|\s+and\s+(?=[a-z])",
        str(text or ""), flags=re.I,
    ) if c.strip()]


def _join_clauses(kept) -> str:
    """Join action clauses back into one line, without a stray capital."""
    if not kept:
        return ""
    parts = [str(clause).strip(" ,;.") for clause in kept if str(clause).strip(" ,;.")]
    if not parts:
        return ""
    text = ", ".join(parts)
    # A removed clause leaves "step, Then their gaze" behind. Lower a leading
    # capital that starts a continuation, but never a standalone "I".
    text = re.sub(r",\s+([A-Z])(?=[a-z])", lambda m: ", " + m.group(1).lower(), text)
    text = " ".join(text.split()).strip(" ,;.")
    return (text[:1].upper() + text[1:]) if text else text


def _clause_has_forbidden(clause) -> bool:
    """True when a clause directs a selfie-forbidden action.

    A negated mention (``never raises the phone``) is a rule rather than an
    action, so a match whose prefix carries a negation is not forbidden.
    """
    text = str(clause or "")
    for pattern in (_PHONE_ENDING_RE, _PHONE_OBJECT_RE, _SECOND_HAND_RE, _SCREEN_INTERACTION_RE, _SCREEN_LOOK_RE, _SCREEN_OTHER_RE):
        for match in pattern.finditer(text):
            prefix = text[max(0, match.start() - 70):match.start()]
            if _NEGATION_RE.search(prefix):
                continue
            return True
    return False


def is_selfie(strategy) -> bool:
    """True when the camera is held by the character (handheld selfie)."""
    return str((strategy or {}).get("camera_setup") or SELFIE).strip().lower() != FIXED


def examples(count: int = 3, exclude=()) -> str:
    """A few ending beats, for the generation prompts' examples.

    Examples only: the render guard picks the actual ending per render via
    `pick`, excluding what this project already used, so consecutive renders
    never repeat the same beat. Passing `exclude` keeps these prompt
    examples from anchoring the model on the endings that are about to be
    added — they illustrate the class, not the instance.
    """
    used = {" ".join(str(text or "").split()).strip(" .").casefold()
            for text in exclude if str(text or "").strip()}
    pool = [entry for entry in ENDINGS
            if " ".join(entry["text"].split()).strip(" .").casefold() not in used]
    if not pool:
        pool = list(ENDINGS)
    return "; ".join(entry["text"].rstrip(".") for entry in pool[:count])


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
    """`text` as (kept, removed): clauses that reach for, hold, raise or show
    a phone or camera, name a phone as an object, look at or work a
    chart/graph/screen surface, reach toward the lens/phone/camera, or need
    a second free hand are removed for selfie.

    A text made entirely of forbidden clauses comes back as ("", removed) so
    the caller can replace it whole.
    """
    raw = " ".join(str(text or "").split())
    if not raw or not (_clause_has_forbidden(raw) or _clause_mentions_phone(raw)):
        return raw, ""
    clauses = _split_clauses(raw)
    kept = [c for c in clauses if not (_clause_has_forbidden(c) or _clause_mentions_phone(c))]
    removed = [c for c in clauses if _clause_has_forbidden(c) or _clause_mentions_phone(c)]
    if not kept:
        return "", ", ".join(removed)
    return _join_clauses(kept), ", ".join(removed)


def split_phone_mentions(text):
    """`text` as (kept, removed): only clauses naming a phone or a screen
    surface as an object.

    Camera direction ("handheld camera", "the camera pushes in") is not a
    phone or a screen in frame, so framing and camera-angle fields use this
    narrower rule.
    """
    raw = " ".join(str(text or "").split())
    if not raw or not _clause_mentions_phone_or_screen(raw):
        return raw, ""
    clauses = _split_clauses(raw)
    kept = [c for c in clauses if not _clause_mentions_phone_or_screen(c)]
    removed = [c for c in clauses if _clause_mentions_phone_or_screen(c)]
    if not kept:
        return "", ", ".join(removed)
    return _join_clauses(kept), ", ".join(removed)


def split_screen_clauses(text):
    """`text` as (kept, removed): only clauses working a chart/screen surface.

    Used where no camera_setup is available (a stored angle promise or a
    template middle that the generated clip can never film in any setup,
    because no generated clip shows app content). Spoken lines are never
    passed here.
    """
    raw = " ".join(str(text or "").split())
    if not raw or not _clause_has_screen_action(raw):
        return raw, ""
    clauses = _split_clauses(raw)
    kept = [c for c in clauses if not _clause_has_screen_action(c)]
    removed = [c for c in clauses if _clause_has_screen_action(c)]
    if not kept:
        return "", ", ".join(removed)
    return _join_clauses(kept), ", ".join(removed)


def strip_props(props):
    """Props without the phone, camera, a screen surface, or a selfie-forbidden
    reach/hand action; (text, changed).

    The noun filter alone caught "phone, tripod" but missed "reaches toward
    the camera" — a prop entry that needs the forbidden action, not the
    device. The action clause now goes through split_phone_clauses, so any
    entry the guard would refuse is removed here first and the field survives
    instead of becoming a wall.
    """
    parts = [p.strip() for p in re.split(r"\s*[,;]\s*", str(props or "")) if p.strip()]
    if not parts:
        return str(props or ""), False
    kept = []
    for part in parts:
        kept_text, removed = split_phone_clauses(part)
        if removed:
            continue
        if re.search(
            r"\b(?:phones?|cameras?|charts?|graphs?|dashboards?|reports?|screens?)\b",
            part, re.I):
            continue
        kept.append(kept_text or part)
    if len(kept) == len(parts):
        return ", ".join(parts), False
    return ", ".join(kept), True


def strip_fields(strategy):
    """Remove every selfie-forbidden clause from a selfie strategy's own fields.

    Returns {"strategy", "changed"}: a copy with the reaching/phone/camera/
    second-hand clauses dropped from the hook action, section actions,
    movement, props and the camera fields. The chosen ending is applied
    afterwards by the caller.
    """
    result = copy.deepcopy(strategy) if isinstance(strategy, dict) else {}
    changed = []
    if not result:
        return {"strategy": result, "changed": changed}

    for key, label in (
        ("hook_action", "Opening action"),
        ("hook_concept", "Hook concept"),
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
        movement = str(performance.get("movement") or "")
        kept, removed = split_phone_clauses(movement)
        kept = _fix_hand_contradictions(kept)
        if removed:
            performance["movement"] = kept
            changed.append("Movement")

    scene = result.get("scene") if isinstance(result.get("scene"), dict) else None
    if scene is not None:
        for key, label in (("framing", "Framing"), ("camera_angle", "Camera angle"),
                           ("character_positioning", "Character positioning")):
            # Camera direction IS the camera: "Shot on the camera" is the
            # filming device, never a phone in frame, so only phone mentions
            # (and a second-person holder) are stripped here. The broader
            # reach/hold/raise rule governs the action fields, where "the
            # camera" names a second device in the frame.
            value = str(scene.get(key) or "")
            kept, phone_removed = split_phone_mentions(value)
            if phone_removed:
                value = kept
            fixed = _fix_selfie_camera_agreement(value, scene_direct=True)
            if fixed != str(scene.get(key) or ""):
                scene[key] = fixed
                changed.append(label)
        props, removed = strip_props(scene.get("props"))
        if removed:
            scene["props"] = props
            changed.append("Props")
    return {"strategy": result, "changed": changed}


def forbidden_hits(strategy):
    """Labels of fields that still carry a selfie-forbidden clause.

    The render guard runs this after stripping: any hit is a clause the
    strip could not remove without losing the field, so it blocks rather
    than rendering it. Spoken words are deliberately not checked — the hook
    dialogue may be the founder's own line, and a script is never rewritten
    or refused for this.
    """
    result = strategy if isinstance(strategy, dict) else {}
    hits = []
    if split_phone_clauses(result.get("hook_action"))[1]:
        hits.append("Opening action")
    if split_phone_clauses(result.get("hook_concept"))[1]:
        hits.append("Hook concept")
    for section in result.get("segments") or []:
        if not isinstance(section, dict):
            continue
        if split_phone_clauses(section.get("action"))[1]:
            role = str(section.get("role") or "hook").strip().capitalize()
            hits.append(f"{role} — what they do")
    performance = result.get("performance") if isinstance(result.get("performance"), dict) else None
    if performance is not None and split_phone_clauses(performance.get("movement"))[1]:
        hits.append("Movement")
    scene = result.get("scene") if isinstance(result.get("scene"), dict) else None
    if scene is not None:
        for key, label in (("framing", "Framing"), ("camera_angle", "Camera angle"),
                           ("character_positioning", "Character positioning")):
            # Narrow rule only, matching strip_fields: camera direction names
            # the filming device and is never a phone in frame.
            if split_phone_mentions(scene.get(key))[1]:
                hits.append(label)
        if strip_props(scene.get("props"))[1]:
            # strip_props reports changed=True whenever it removed a phone
            # noun, but a hit here means the stripped remainder still carries
            # a forbidden clause the strip could not remove without losing
            # the rest of the field — a wall, not a guard.
            hits.append("Props")
    return hits


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


def _fix_hand_contradictions(movement: str) -> str:
    """One hand cannot hold two jobs at once.
    If movement says one hand rests on the chest and that same hand stays
    at the side, the side clause is dropped; the chest rest wins.
    """
    text = " ".join(str(movement or "").split())
    if not text:
        return text
    left_on_chest = bool(re.search(
        r"\b(?:left|her left|his left)\s+hand\s+(?:rests?|resting|on|placed|lies|pressed|flat)\s+on\s+(?:the\s+)?chest", text, re.I))
    if left_on_chest and re.search(
            r"\b(?:left|her left|his left)\s+hand\s+(?:stays?|hangs?|at|by)\s+(?:her|his|the|their|my|your)?\s*side", text, re.I):
        text = re.sub(
            r",?\s*(?:and\s+)?(?:her|his|their|my|your|the)?\s*(?:left)\s+hand\s+(?:stays?|hangs?|at|by)\s+(?:at\s+)?"
            r"(?:her|his|their|my|your|the)?\s*side\b", "", text, flags=re.I).strip(" ,;.")
    right_on_chest = bool(re.search(
        r"\b(?:right|her right|his right)\s+hand\s+(?:rests?|resting|on|placed|lies|pressed|flat)\s+on\s+(?:the\s+)?chest", text, re.I))
    if right_on_chest and re.search(
            r"\b(?:right|her right|his right)\s+hand\s+(?:stays?|hangs?|at|by)\s+(?:her|his|the|their|my|your)?\s*side", text, re.I):
        text = re.sub(
            r",?\s*(?:and\s+)?(?:her|his|their|my|your|the)?\s*(?:right)\s+hand\s+(?:stays?|hangs?|at|by)\s+(?:at\s+)?"
            r"(?:her|his|their|my|your|the)?\s*side\b", "", text, flags=re.I).strip(" ,;.")
    return " ".join(text.split())


_SECOND_PERSON_RE = re.compile(
    r"(?:camera\s+(?:held|operated|manned)\s+by\s+(?:someone|another\s+person|cameraperson|cameraman|the\s+(?:viewer|operator|photographer))"
    r"|(?:someone|another\s+person|a\s+stranger|the\s+(?:viewer|operator|photographer))\s+(?:holds?|operates?|films?|records?)\s+(?:the\s+)?camera"
    r"|(?:walking|moving)\s+(?:beside|next\s+to)\s+(?:her|him|them|the\s+person)[^.;,]*"
    r"\s+(?:holds?|films?|records?|operates?)[^.;,]*camera"
    r"|(?:someone|another\s+person)\s+walks\s+beside)", re.I)


def _fix_selfie_camera_agreement(text: str, scene_direct: bool = False) -> str:
    """Rewrite camera direction for a selfie setup.
    If camera_setup is handheld (non-fixed), camera fields must describe the
    character filming herself — never a second person or outside viewer
    holding the camera. Template wording that implies an outside camera is
    rewritten to a selfie description.
    """
    raw = " ".join(str(text or "").split())
    if not raw:
        return raw
    if _SECOND_PERSON_RE.search(raw):
        replacement = "handheld selfie, filmed at arm's length by the character"
        fixed = _SECOND_PERSON_RE.sub(replacement, raw)
        return " ".join(fixed.split()).strip(" .;")
    if not scene_direct and re.search(r"\b(?:walking\s+beside|next\s+to\s+(?:her|him|them)|outside\s+viewer|someone\s+else)", raw, re.I):
        fixed = re.sub(
            r"\b(?:walking\s+beside|next\s+to\s+(?:her|him|them)|outside\s+viewer|someone\s+else)\b",
            "filmed at arm's length by the character", raw, flags=re.I)
        return " ".join(fixed.split())
    return raw
