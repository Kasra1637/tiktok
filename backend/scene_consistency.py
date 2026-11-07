"""Scene fields that must agree with each other before a render (ADR 0092).

The Render & result panel is read before money is spent, and everything it
shows is sent to the video model. Four invariants used to be the model's
problem and the founder's surprise:

- Location names the place only; lighting and time of day live in Lighting.
- Props lists every object the hook/middle actions and the shot timeline show.
- Movement covers every action those lines show.
- Scene fields never carry internal wording ("Use STARTING SHOT").

`reconcile_scene` enforces them on a strategy: it patches what can be patched
deterministically and reports what cannot (a list that will not fit) so the
render guard can refuse with the field named instead of sending a
contradiction to the provider. Detection is lexical and conservative, like
angle_scene's: a text with no lighting or time word never changes, a body part
is never an object, and a place or time word is never an object either.

Pure policy: no HTTP, AI, auth or persistence imports.
"""
import copy
import re

import angle_scene
import final_beat

# The same per-field cap ai_service._normalize_strategy_section applies. A
# patch that would need more room than this is reported, not silently cut.
FIELD_LIMIT = 300

# Movement covers every action from hook_action (cap 700), both section
# actions and the timeline action clauses. The old 300-char cap guaranteed
# ordinary strategies would overflow it, so the render guard refused them.
# 600 chars holds a normal set with headroom; beyond it Movement is compacted
# best-effort and reported as an advisory warning (ADR 0104), never a block.
MOVEMENT_LIMIT = 600

# Words that mean "this clause is about light or time of day, not the place".
# Multi-word phrases come first so "golden hour" wins over "hour".
_LIGHT_WORDS = (
    "golden hour", "lamp glow", "candlelight", "candle light",
    "sunlight", "sunshine", "daylight", "sunlit", "backlit", "lighting",
    "lights", "light", "lit", "sunny", "lamp", "candle", "glow",
    "shadows", "shadow", "neon", "fluorescent",
)
_LIGHT_RE = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in _LIGHT_WORDS) + r")\b", re.I)

# Adjectives that belong with the light/time phrase they qualify ("soft
# morning light" is one phrase, not a place with an adjective).
_QUALIFIERS = frozenset((
    "soft", "warm", "cool", "bright", "dim", "low", "harsh", "natural",
    "even", "diffused", "gentle", "crisp", "flat", "golden", "sunny",
    "early", "late", "ambient", "overcast", "deep", "faint", "pale",
))

# Prepositions a light/time phrase hangs off ("at 7am", "in the morning").
_LINKERS = frozenset((
    "at", "in", "on", "during", "by", "around", "before", "after",
    "under", "with", "near", "until", "past",
))

# Words left dangling once a phrase is removed; stripped from the tail of the
# remaining place text so "Kitchen at 7am" ends as "Kitchen", not "Kitchen at".
_DANGLING = _LINKERS | frozenset((
    "of", "to", "for", "and", "or", "the", "a", "an", "but", "then",
    "while", "when", "as", "into", "onto", "from", "over",
))

# Objects are read from determiner phrases ("a mug", "the phone"). Capturing
# up to three words lets "the ceramic mug" through; the connector trim below
# cuts it back before validation.
_OBJECT_RE = re.compile(
    r"\b(?:a|an|the|my|his|her|their|your|its)\s+"
    r"([a-z][a-z'\u2019-]*(?:\s+[a-z][a-z'\u2019-]*){0,2})",
    re.I,
)

_OBJECT_TRAILERS = frozenset((
    "and", "or", "then", "while", "when", "with", "without", "into", "onto",
    "in", "on", "at", "to", "from", "of", "for", "as", "before", "after",
    "up", "down", "out", "back", "again", "over", "under", "about", "around",
    "through", "across", "toward", "towards", "past", "along", "by", "but",
    "so", "that", "this", "these", "those", "it", "its", "there", "here",
    "is", "are", "was", "were", "while",
))

# A body part is never a prop; the person comes from the photograph. A
# glance/look/stare is the eyes doing something, never a carried object.
_BODY_WORDS = frozenset((
    "face", "head", "hair", "eye", "eyes", "gaze", "glance", "glances",
    "stare", "blink", "brow", "brows",
    "eyebrow", "eyebrows", "jaw", "chin", "hand", "hands", "arm", "arms",
    "shoulder", "shoulders", "chest", "torso", "body", "posture", "leg",
    "legs", "knee", "knees", "finger", "fingers", "thumb", "thumbs",
    "skin", "smile", "expression", "mouth", "lips", "breath", "voice",
))

# Fixed things that belong to the place, not to the person. A props list that
# names one is repeating Location and telling the model to put scenery in the
# character's hands. Signage lives in a second set: a sign can be carried, so
# it is scenery only when the Location already names it.
_FIXED_SCENERY_WORDS = frozenset((
    # Furniture
    "table", "counter", "countertop", "desk", "chair", "stool", "bench",
    "couch", "sofa", "armchair", "bed", "bookcase", "bookshelf", "shelf",
    "shelves", "cabinet", "cupboard", "dresser", "nightstand", "wardrobe",
    "closet", "sideboard", "drawer", "drawers",
    # Rooms, buildings and structures
    "wall", "floor", "ceiling", "window", "door", "doorway", "staircase",
    "stairway", "stairs", "stair", "step", "steps", "stoop", "hallway", "room",
    "kitchen", "bedroom", "bathroom", "office", "building", "house", "home",
    "apartment", "shop", "store", "storefront", "street", "road", "sidewalk",
    "pavement", "fence", "gate", "bridge", "station", "platform", "park",
    "tree", "plant", "roof", "porch", "balcony", "driveway", "garage",
    "corridor", "lobby",
    # Fixtures, decor and screens
    "lamp", "rug", "carpet", "curtain", "mirror", "painting", "frame", "sink",
    "stove", "oven", "fridge", "refrigerator", "microwave", "toilet",
    "bathtub", "shower", "clock", "vase", "television", "tv", "monitor",
    "screen",
    # Outdoor ground: bare "yard"/"lawn" never match angle_scene's backyard
    # pattern, so without these the location strip would read the yard as a
    # carried object.
    "ground", "grass", "sky", "yard", "lawn", "patio", "deck", "field",
    "meadow", "woods", "forest",
))
_SIGNAGE_WORDS = frozenset((
    "sign", "billboard", "poster", "banner", "logo", "placard",
))

# A prop entry sometimes trails into the place it rests in ("a mug on the
# counter"). The object is the part before that place phrase; the place is
# Location's job, never a prop's.
_PROP_PLACE_TAIL_RE = re.compile(
    r"\s+(?:on|at|in|under|behind|beside|next\s+to|near|by|against|inside|"
    r"outside|above|below|over|around|across|across\s+from|in\s+front\s+of)\s+"
    r"(?:the|a|an|my|your|her|his|their|its)\s+.+$",
    re.I,
)

# Abstract nouns the determiner pattern would otherwise catch ("the moment",
# "the problem"). None of these is an object on camera.
_ABSTRACT_WORDS = frozenset((
    "moment", "moments", "day", "days", "time", "times", "thing", "things",
    "way", "ways", "feeling", "feelings", "story", "video", "app", "screen",
    "camera", "lens", "frame", "shot", "take", "line", "word", "words",
    "point", "reason", "idea", "look", "mind", "thought", "energy", "pace",
    "scene", "viewer", "founder", "brand", "audience", "experience",
    "journey", "habit", "routine", "problem", "solution", "chance",
    "change", "life", "world", "minute", "second", "hour", "morning",
    "evening", "afternoon", "night", "question", "answer", "list",
    "pattern", "cycle", "chore", "task", "feeling", "dread", "guilt",
    "relief", "calm", "focus", "flow", "start", "finish", "push", "pull",
))

# Placeholder wording that is an instruction to the model, never a scene value.
_PLACEHOLDER_RE = re.compile(r"starting shot|final-phone|use starting", re.I)

# Movement completeness: an action text is "covered" when most of its content
# words already appear in the movement line.
_ACTIONS_STOP_WORDS = frozenset((
    "then", "with", "that", "this", "they", "them", "their", "when",
    "from", "into", "onto", "over", "under", "about", "around", "through",
    "while", "also", "very", "just", "some", "again", "back", "down",
    "face", "faces", "hands", "hand", "head", "eyes", "gaze", "slowly",
    "gently", "little", "small", "quick", "quickly", "slight", "slightly",
))
_COVERAGE = 0.5

# Beats are "what happens and what is said", so only the clauses that read as
# an action belong in movement. A small verb list keeps narration out.
_ACTION_VERBS = (
    "stands", "standing", "sits", "sitting", "walks", "walking", "steps",
    "turns", "turning", "reaches", "reaching", "grabs", "grabbing", "picks",
    "picking", "puts", "putting", "places", "placing", "lifts", "lifting",
    "sets", "setting", "drops", "dropping", "opens", "opening", "closes",
    "closing", "taps", "tapping", "scrolls", "scrolling", "looks",
    "looking", "glances", "glancing", "smiles", "smiling", "sighs",
    "sighing", "nods", "nodding", "shakes", "shaking", "types", "typing",
    "writes", "writing", "reads", "reading", "moves", "moving", "leans",
    "leaning", "crosses", "crossing", "raises", "raising", "lowers",
    "lowering", "holds", "holding", "pulls", "pulling", "pushes",
    "pushing", "slides", "sliding", "swipes", "swiping", "points",
    "pointing", "presses", "pressing", "rubs", "rubbing", "stretches",
    "stretching", "waves", "waving", "walks", "tosses", "tossing",
    "catches", "catching", "carries", "carrying", "brings", "bringing",
    "takes", "taking", "switches", "switching", "clicks", "clicking",
    "unlocks", "unlocking", "folds", "folding", "tears", "tearing",
    "throws", "throwing", "zips", "zipping", "ties", "tying", "untangles",
    "kneels", "kneeling", "stops", "stopping", "pauses", "pausing",
)
_ACTION_VERB_RE = re.compile(
    r"\b(?:" + "|".join(_ACTION_VERBS) + r")\b", re.I
)


def time_spans(text: str) -> list:
    """(start, end) spans of time-of-day words in `text`, merged and ordered."""
    raw = str(text or "")
    found = []
    for pattern in angle_scene.time_patterns():
        found.extend(m.span() for m in re.finditer(pattern, raw, flags=re.IGNORECASE))
    found.sort()
    merged = []
    for start, end in found:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _expand(text: str, span: list) -> list:
    """Grow a span over the adjectives and the preposition it hangs off."""
    start, end = span
    while True:
        match = re.search(r"([\w'\u2019-]+)\s*$", text[:start])
        if not match or match.group(1).strip(".,;:").lower() not in _QUALIFIERS:
            break
        start = match.start()
    match = re.search(r"([\w'\u2019-]+)\s+$", text[:start])
    if match and match.group(1).lower() in _LINKERS:
        start = match.start()
    return [start, end]


def _strip_dangling(text: str) -> str:
    """Drop connectors and punctuation left at the tail by a removed phrase."""
    text = " ".join(str(text or "").split())
    while True:
        new = re.sub(r"[\s,;:.\u2013\u2014-]+$", "", text).strip()
        new = re.sub(
            r"\b(" + "|".join(re.escape(w) for w in _DANGLING) + r")$",
            "", new, flags=re.I,
        ).strip()
        if new == text:
            return text
        text = new


def _join_unique(parts) -> str:
    return ", ".join(_unique_list(parts))


def _unique_list(parts) -> list:
    seen, out = set(), []
    for part in parts:
        text = " ".join(str(part or "").split()).strip(" ,;.")
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def split_location(text):
    """`text` as (place only, lighting-and-time text that was removed).

    "Kitchen at 7am" -> ("Kitchen", "7am"); a text that names no lighting or
    time of day comes back untouched with "" moved. When every word is a
    light/time phrase there is no place left to name, so the split declines
    and the original text is kept rather than emptied.
    """
    raw = " ".join(str(text or "").split())
    if not raw:
        return raw, ""
    spans = [_expand(raw, span) for span in time_spans(raw)]
    spans.extend(_expand(raw, span) for span in
                 ((m.start(), m.end()) for m in _LIGHT_RE.finditer(raw)))
    if not spans:
        return raw, ""
    spans.sort()
    merged = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append([start, end])
    kept, moved = [], []
    cursor = 0
    for start, end in merged:
        kept.append(raw[cursor:start])
        piece = raw[start:end].strip(" ,;:-")
        piece = re.sub(
            r"^(?:" + "|".join(re.escape(w) for w in _LINKERS) + r")\s+",
            "", piece, flags=re.I,
        )
        if piece:
            moved.append(piece)
        cursor = end
    kept.append(raw[cursor:])
    place = _strip_dangling(" ".join(" ".join(kept).split()))
    if not re.search(r"[A-Za-z]", place or ""):
        return raw, ""
    return place, _join_unique(moved)


def clean_placeholders(scene) -> list:
    """Blank internal placeholder wording in scene fields; return the labels."""
    changed = []
    if isinstance(scene, dict):
        for key, label in (("camera_angle", "Camera angle"), ("framing", "Framing")):
            if _PLACEHOLDER_RE.search(str(scene.get(key) or "")):
                scene[key] = ""
                changed.append(label)
    return changed


# The filming device, when Camera angle or Visual style names it. A phone in
# either field reads as a phone in the scene, and a handheld selfie cannot film
# one (ADR 0097) — the video model draws what the direction calls it.
_FILMING_DEVICE_RE = re.compile(
    r"(?P<det>\b(?:the|a|an|my|your|her|his|their|its)\s+)?"
    r"(?P<device>smart\s*phones?|cell\s*phones?|mobile\s*phones?|iphones?|"
    r"phone\s*cameras?|camera\s*phones?|phones?)\b",
    re.I,
)


def camera_wording(text) -> str:
    """Camera angle / visual style with the filming device called the camera.

    "Handheld phone footage" becomes "handheld camera footage"; a determiner or
    possessive becomes "the camera" ("shot on her phone" -> "shot on the
    camera"), so the direction never puts a phone in the character's hand.
    Spoken lines live in other fields and are never passed here.
    """
    def _replace(match):
        device = match.group("device")
        plural = bool(re.search(r"s$", device, re.I))
        if match.group("det"):
            replacement = "the cameras" if plural else "the camera"
            if match.group("det")[:1].isupper():
                replacement = replacement[:1].upper() + replacement[1:]
            return replacement
        replacement = "cameras" if plural else "camera"
        if device[:1].isupper():
            replacement = replacement[:1].upper() + replacement[1:]
        return replacement

    return _FILMING_DEVICE_RE.sub(_replace, str(text or ""))


# ---------------------------------------------------------------------------
# One camera setup, one set of camera words (ADR 0108).
#
# The setup dropdown is the source of truth: a handheld strategy cannot say
# "fixed camera", "locked shot" or "steady framing", and a fixed strategy
# cannot say "handheld" or "arm's length". The render prompt and the panel
# both read these fields, so a contradiction here is a video that films
# something other than the setup the founder picked.
# ---------------------------------------------------------------------------
_LOCATION_CLAUSE_SPLIT_RE = re.compile(
    r"\s*,\s*|\s+(?:and|with)\s+(?=(?:a|an|the|my|his|her|their|your|its)\b)",
    re.I,
)

# Words that describe who is in the place, not an object they carry. Defined
# below the body/abstract vocabularies it builds on.
def _location_non_objects():
    return _BODY_WORDS | _ABSTRACT_WORDS | frozenset((
        "person", "people", "character", "characters", "viewer", "viewers",
        "someone", "anyone", "everyone",
    ))


def _location_clause_names_object(clause) -> bool:
    """True when a Location clause names a carried/used object, not the place.

    A clause that only names scenery ("a closed front door behind the step")
    is a place clause and is kept. A clause that names a carried object is
    removed even when it also names the place it rests on ("a mug on the
    counter") — the object is the deciding phrase, not every word in the
    clause — because Location must name the place only.
    """
    text = " ".join(str(clause or "").split()).strip(" ,;.")
    if not text:
        return False
    if _FILMING_DEVICE_RE.search(text):
        return True
    for match in _OBJECT_RE.finditer(text):
        phrase = _is_object(match.group(1))
        if not phrase:
            continue
        # The determiner capture overshoots ("a dark yard stretching"), so the
        # noun that decides place-vs-object is not always the last word. Any
        # scenery word anywhere in the phrase makes it a place phrase.
        words = {w.casefold().strip(" .,;:'\u2019") for w in phrase.split() if w.strip()}
        if words & (_FIXED_SCENERY_WORDS | _SIGNAGE_WORDS):
            continue
        core = phrase.split()[-1].casefold()
        if core in _location_non_objects():
            continue
        return True
    return False


def strip_location_objects(text):
    """Location as (place only, removed clauses): never an object on camera.

    "A porch step ... and the phone lying face-down beside the person" keeps
    the porch, the yard and the door and drops the phone. A clause that names
    scenery stays; a clause that names a carried object goes, in every camera
    setup (a fixed camera may keep the phone in the action and Props, never in
    the place). A text with no removable clause comes back untouched.
    """
    raw = " ".join(str(text or "").split())
    if not raw:
        return raw, []
    parts = [part.strip() for part in _LOCATION_CLAUSE_SPLIT_RE.split(raw) if part.strip()]
    if len(parts) <= 1:
        return raw, []
    kept, removed = [], []
    for part in parts:
        if _location_clause_names_object(part):
            removed.append(part)
        else:
            kept.append(part)
    if not removed:
        return raw, []
    place = ", ".join(kept).strip(" ,;.")
    if not re.search(r"[A-Za-z]", place):
        return raw, []
    return place, removed


def _match_case(original: str, replacement: str) -> str:
    if str(original or "")[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _apply_rewrites(text, rewrites) -> str:
    out = str(text or "")
    for pattern, replacement in rewrites:
        if callable(replacement):
            out = pattern.sub(replacement, out)
        else:
            out = pattern.sub(
                lambda match, repl=replacement: _match_case(match.group(0), repl),
                out,
            )
    return out


def _handheld_shot(match) -> str:
    size = (match.group(1) or "").strip()
    replacement = f"handheld {size + ' ' if size else ''}selfie shot"
    return _match_case(match.group(0), replacement)


_HANDHELD_CAMERA_REWRITES = (
    (re.compile(r"\bfixed(?:[- ]positioned)?\s+camera\b", re.I), "handheld selfie camera"),
    (re.compile(r"\blocked(?:[- ]off)?\s+camera\b", re.I), "handheld selfie camera"),
    (re.compile(r"\bstatic\s+camera\b", re.I), "handheld selfie camera"),
    (re.compile(r"\bcamera\s+(?:is\s+)?(?:fixed|locked|static)\b", re.I), "camera is handheld"),
    (re.compile(
        r"\b(?:locked|static|fixed)(?:[- ]off)?\s+"
        r"(?:(medium|wide|close(?:-up)?|full|tight|loose)\s+)?shot\b",
        re.I,
    ), _handheld_shot),
    (re.compile(r"\bsteady\s+framing\b", re.I), "handheld framing"),
    (re.compile(r"\bsteady\s+(?:camera|shots?)\b", re.I), "handheld camera"),
    (re.compile(r"\btripod\b", re.I), "handheld selfie"),
)

_FIXED_CAMERA_REWRITES = (
    (re.compile(r"\bhandheld\s+selfie\s+camera\b", re.I), "fixed camera"),
    (re.compile(r"\bhandheld\s+selfie\b", re.I), "fixed camera"),
    (re.compile(r"\bhandheld\s+camera\b", re.I), "fixed camera"),
    (re.compile(r"\bhandheld\b", re.I), "fixed camera"),
    (re.compile(r"\bselfie\s+camera\b", re.I), "fixed camera"),
    (re.compile(r"\bselfie\b", re.I), "fixed camera"),
    # "At arm's length" names a handheld camera distance. Rewriting the bare
    # noun to "fixed camera" after "handheld selfie" would leave "fixed
    # camera at fixed camera"; the prepositional phrase becomes a fixed
    # position instead.
    (re.compile(r"\bat\s+arm(?:['\u2019]s)?[- ]length\b", re.I), "from a fixed position"),
    (re.compile(r"\barm(?:['\u2019]s)?[- ]length\b", re.I), "a fixed position"),
    (re.compile(r"\bthe person holds the camera\b", re.I), "the camera is fixed in place"),
    (re.compile(r"\bholds the camera\b", re.I), "the camera is fixed in place"),
)

# A handheld camera cannot physically push in, pull back or zoom: the phone
# is in the character's hand. The move becomes the person's lean, which is
# what the selfie prompt can actually film.
_HANDHELD_MOVEMENT_REWRITES = (
    (re.compile(r"\bthe camera (?:slowly |gently )?pushes? in\b", re.I), "they lean in toward the lens"),
    (re.compile(r"\bthe camera (?:slowly |gently )?pulls? (?:back|out)\b", re.I), "they ease back from the lens"),
    (re.compile(r"\bthe camera (?:slowly |gently )?zooms? in\b", re.I), "they lean closer to the lens"),
    (re.compile(r"\bthe camera (?:slowly |gently )?zooms? out\b", re.I), "they ease back from the lens"),
    (re.compile(r"\bthe camera (?:slowly |gently )?(?:pans?|tilts?|orbits?|tracks?)\b[^.;,]*", re.I), "the selfie frame follows their movement"),
)


def camera_setup_wording(strategy) -> list:
    """Rewrite camera wording to the setup the strategy declares; return labels.

    The setup is the source of truth, so this is deterministic rather than a
    refusal: a handheld strategy's "fixed camera" becomes "handheld selfie
    camera", and a fixed strategy's "handheld" becomes "fixed camera". Spoken
    words are never touched.
    """
    result = strategy if isinstance(strategy, dict) else {}
    if not result:
        return []
    fixed = str(result.get("camera_setup") or "handheld").strip().lower() == "fixed"
    rewrites = _FIXED_CAMERA_REWRITES if fixed else _HANDHELD_CAMERA_REWRITES
    changed = []
    scene = result.get("scene") if isinstance(result.get("scene"), dict) else None
    if scene is not None:
        for key, label in (
            ("camera_angle", "Camera angle"),
            ("framing", "Framing"),
            ("visual_style", "Visual style"),
            ("character_positioning", "Character positioning"),
        ):
            before = str(scene.get(key) or "")
            after = _apply_rewrites(before, rewrites)
            if after != before:
                scene[key] = after
                changed.append(label)
    performance = result.get("performance") if isinstance(result.get("performance"), dict) else None
    if performance is not None:
        before = str(performance.get("movement") or "")
        # Movement for a fixed setup is left for the render's fixed-camera
        # refusal (require_camera_setup_directions): rewriting an actor's
        # "holds the recording phone at arm's length" by word substitution
        # would hide the conflict and leave nonsense ("at fixed camera").
        # Handheld movement is rewritten, including the push-in translation,
        # because no handheld check exists to catch it later.
        if not fixed:
            after = _apply_rewrites(before, rewrites)
            after = _apply_rewrites(after, _HANDHELD_MOVEMENT_REWRITES)
        else:
            after = before
        if after != before:
            performance["movement"] = after
            changed.append("Movement")
    return changed


# ---------------------------------------------------------------------------
# Carry the plan's camera movement into Framing and Movement.
#
# The plan's visual direction is the render's default look, and a movement
# named there ("a slow push in during the middle") used to live only in the
# plan text: Framing showed the locked opening shot and Movement never named
# the move at all. The same move now appears in both fields. Handheld
# translates it to a lean, because the selfie camera cannot push in.
# ---------------------------------------------------------------------------
_CAMERA_MOVE_PATTERNS = (
    ("push_in", re.compile(
        r"\b(?:slow(?:ly)?\s+)?push(?:es|ing|ed)?[ -]?in\b"
        r"|\bcamera\s+(?:slowly\s+)?pushes?\s+in\b", re.I)),
    ("pull_back", re.compile(
        r"\b(?:slow(?:ly)?\s+)?pull(?:s|ing|ed)?[ -]?(?:back|out)\b"
        r"|\bcamera\s+(?:slowly\s+)?pulls?\s+(?:back|out)\b", re.I)),
    ("zoom_in", re.compile(
        r"\b(?:slow(?:ly)?\s+)?zoom(?:s|ing|ed)?[ -]?in\b"
        r"|\bcamera\s+(?:slowly\s+)?zooms?\s+in\b", re.I)),
    ("zoom_out", re.compile(
        r"\b(?:slow(?:ly)?\s+)?zoom(?:s|ing|ed)?[ -]?out\b"
        r"|\bcamera\s+(?:slowly\s+)?zooms?\s+out\b", re.I)),
    ("pan", re.compile(r"\b(?:camera\s+)?pan(?:s|ning|ned)?\b", re.I)),
    ("tilt", re.compile(r"\b(?:camera\s+)?tilt(?:s|ing|ed)?\b", re.I)),
    ("orbit", re.compile(r"\borbit(?:s|ing|ed)?\b", re.I)),
    ("track", re.compile(r"\btrack(?:s|ing|ed)?\b", re.I)),
)

_FIXED_FRAMING_MOVES = {
    "push_in": ("a push-in during the middle", "a slow push-in during the middle"),
    "pull_back": ("a pull-back during the middle", "a slow pull-back during the middle"),
    "zoom_in": ("a zoom-in during the middle", "a slow zoom-in during the middle"),
    "zoom_out": ("a zoom-out during the middle", "a slow zoom-out during the middle"),
    "pan": ("a pan during the middle", "a slow pan during the middle"),
    "tilt": ("a tilt during the middle", "a slow tilt during the middle"),
    "orbit": ("an orbit during the middle", "a slow orbit during the middle"),
    "track": ("a tracking move during the middle", "a slow tracking move during the middle"),
}

_FIXED_MOVEMENT_MOVES = {
    "push_in": ("the camera pushes in during the middle", "the camera slowly pushes in during the middle"),
    "pull_back": ("the camera pulls back during the middle", "the camera slowly pulls back during the middle"),
    "zoom_in": ("the camera zooms in during the middle", "the camera slowly zooms in during the middle"),
    "zoom_out": ("the camera zooms out during the middle", "the camera slowly zooms out during the middle"),
    "pan": ("the camera pans during the middle", "the camera slowly pans during the middle"),
    "tilt": ("the camera tilts during the middle", "the camera slowly tilts during the middle"),
    "orbit": ("the camera orbits during the middle", "the camera slowly orbits during the middle"),
    "track": ("the camera tracks during the middle", "the camera slowly tracks during the middle"),
}

_HANDHELD_FRAMING_MOVES = {
    "push_in": ("the selfie frame tightens as they lean in", "the selfie frame slowly tightens as they lean in"),
    "pull_back": ("the selfie frame eases back as they lean away", "the selfie frame slowly eases back as they lean away"),
    "zoom_in": ("the selfie frame tightens as they lean closer", "the selfie frame slowly tightens as they lean closer"),
    "zoom_out": ("the selfie frame eases back as they lean away", "the selfie frame slowly eases back as they lean away"),
    "pan": ("the selfie frame follows their movement", "the selfie frame slowly follows their movement"),
    "tilt": ("the selfie frame follows their movement", "the selfie frame slowly follows their movement"),
    "orbit": ("the selfie frame follows their movement", "the selfie frame slowly follows their movement"),
    "track": ("the selfie frame follows their movement", "the selfie frame slowly follows their movement"),
}

_HANDHELD_MOVEMENT_MOVES = {
    "push_in": ("they lean in toward the lens", "they slowly lean in toward the lens"),
    "pull_back": ("they lean away from the lens", "they slowly lean away from the lens"),
    "zoom_in": ("they lean closer to the lens", "they slowly lean closer to the lens"),
    "zoom_out": ("they lean away from the lens", "they slowly lean away from the lens"),
    "pan": ("they turn their body through the space", "they slowly turn their body through the space"),
    "tilt": ("they move their gaze through the space", "they slowly move their gaze through the space"),
    "orbit": ("they turn slowly toward the lens", "they turn slowly toward the lens"),
    "track": ("they move with the frame", "they slowly move with the frame"),
}

_MOVE_HINTS = {
    "push_in": ("push in", "push-in", "lean in", "lean closer"),
    "pull_back": ("pull back", "pull-back", "lean away"),
    "zoom_in": ("zoom in", "zoom-in", "lean closer"),
    "zoom_out": ("zoom out", "zoom-out", "lean away"),
    "pan": ("pan", "follows their movement", "turn their body"),
    "tilt": ("tilt", "follows their movement", "move their gaze"),
    "orbit": ("orbit", "turn slowly toward"),
    "track": ("track", "move with the frame", "follows their movement"),
}


def plan_camera_movements(plan) -> list:
    """Camera moves named by the plan's default look or shot timeline.

    The project row calls the timeline `beat_timeline`; `generate_video_strategy`
    hands the strategy builder an `approved_plan` whose same list is called
    `beats`. Both spellings name the same shots.
    """
    plan = plan if isinstance(plan, dict) else {}
    texts = [
        str(plan.get("visual_direction") or ""),
        str(plan.get("camera_pacing") or ""),
    ]
    beats = plan.get("beat_timeline") or plan.get("beats") or []
    for beat in beats:
        if isinstance(beat, dict):
            texts.append(str(beat.get("text") or beat.get("beat") or ""))
    found = []
    for kind, pattern in _CAMERA_MOVE_PATTERNS:
        hits = [text for text in texts if text and pattern.search(text)]
        if not hits:
            continue
        found.append({
            "kind": kind,
            "slow": any(re.search(r"\bslow(?:ly)?\b", text, re.I) for text in hits),
        })
    return found


def _append_movement(existing, addition, limit) -> tuple:
    text = " ".join(str(existing or "").split()).strip(" .;")
    if not text:
        return addition[:1].upper() + addition[1:] + ".", True
    if addition.casefold() in text.casefold():
        return text, False
    joined = append_clause(text, addition)
    if len(joined) > limit:
        joined = _truncate_to_limit(joined, limit)
    return joined, True


def carry_camera_movement(strategy, plan) -> list:
    """Put the plan's camera move into Framing and Movement; return labels."""
    result = strategy if isinstance(strategy, dict) else {}
    movements = plan_camera_movements(plan)
    if not result or not movements:
        return []
    fixed = str(result.get("camera_setup") or "handheld").strip().lower() == "fixed"
    scene = result.get("scene") if isinstance(result.get("scene"), dict) else None
    performance = result.get("performance") if isinstance(result.get("performance"), dict) else None
    changed = []
    for move in movements:
        kind = move["kind"]
        slow = bool(move["slow"])
        if fixed:
            framing_text = _FIXED_FRAMING_MOVES[kind][1 if slow else 0]
            movement_text = _FIXED_MOVEMENT_MOVES[kind][1 if slow else 0]
        else:
            framing_text = _HANDHELD_FRAMING_MOVES[kind][1 if slow else 0]
            movement_text = _HANDHELD_MOVEMENT_MOVES[kind][1 if slow else 0]
        hints = _MOVE_HINTS[kind]
        if scene is not None:
            framing = str(scene.get("framing") or "")
            if not any(hint in framing.casefold() for hint in hints):
                scene["framing"], did = _append_movement(framing, framing_text, FIELD_LIMIT)
                if did:
                    changed.append("Framing")
        if performance is not None:
            movement = str(performance.get("movement") or "")
            if not any(hint in movement.casefold() for hint in hints):
                performance["movement"], did = _append_movement(
                    movement, movement_text, MOVEMENT_LIMIT
                )
                if did:
                    changed.append("Movement")
    return list(dict.fromkeys(changed))


def _action_texts(strategy: dict) -> list:
    texts = [str(strategy.get("hook_action") or "").strip()]
    for section in strategy.get("segments") or []:
        if isinstance(section, dict):
            texts.append(str(section.get("action") or "").strip())
    return [text for text in texts if text]


def _beat_action_texts(plan) -> list:
    """Action clauses out of the shot timeline, skipping what is only said."""
    out = []
    for beat in (plan or {}).get("beat_timeline") or []:
        if not isinstance(beat, dict):
            continue
        text = str(beat.get("text") or beat.get("beat") or "").strip()
        if not text:
            continue
        clauses = [c.strip() for c in re.split(r"[,;.]|\band\b", text, flags=re.I) if c.strip()]
        for clause in clauses:
            if _ACTION_VERB_RE.search(clause):
                out.append(clause)
    return out


# A conjunction ends the object: "the counter and looks" is the counter, not
# an object called "counter and looks". A pronoun at the end is the next
# clause's subject, not the noun ("the first second they" is a second, not
# an object called "first second they") — the cut keeps only the noun phrase.
_OBJECT_STOPS = frozenset((
    "and", "or", "then", "but", "so", "that", "this", "these", "those",
    "it", "is", "are", "was", "were", "while", "when",
    "they", "them", "he", "him", "she", "her", "we", "us", "you", "i", "me",
    "my", "his", "their", "its", "the", "a", "an",
))

# An adverb or determiner at the end is the verb's manner ("the line slowly",
# "glance toward the"), never the object noun itself.
_OBJECT_END_WORDS = frozenset((
    "the", "a", "an", "they", "them", "he", "him", "she", "her", "we", "us",
    "you", "i", "me", "my", "his", "their", "its",
))


def _trim_object(phrase: str) -> str:
    words = str(phrase or "").split()
    for index, word in enumerate(words):
        if word.strip(" .,;:'\u2019").lower() in _OBJECT_STOPS:
            words = words[:index]
            break
    while words and words[-1].strip(" .,;:'\u2019").lower() in _OBJECT_TRAILERS:
        words.pop()
    return " ".join(words)


def _is_object(phrase: str) -> str:
    """The phrase when it is an object on camera, else ""."""
    phrase = _trim_object(phrase)
    if not phrase:
        return ""
    words = [w.strip(" .,;:'\u2019").lower() for w in phrase.split()]
    if not words:
        return ""
    core = words[-1]
    if len(core) < 3 or core in _BODY_WORDS or core in _ABSTRACT_WORDS:
        return ""
    if any(word in _BODY_WORDS for word in words):
        return ""
    # An abstract noun anywhere in the phrase marks the whole phrase as
    # abstract ("the last line lands", "the day in rough"): the determiner
    # capture picks up the verb or adverb that follows the abstract noun,
    # so the head noun check above cannot see it.
    if any(word in _ABSTRACT_WORDS for word in words):
        return ""
    # An adverb, pronoun or determiner at the end ("the line slowly",
    # "glance toward the") means the noun came earlier and the capture ran
    # past it; the phrase names no object.
    if core in _OBJECT_END_WORDS or core.endswith("ly"):
        return ""
    if _LIGHT_RE.search(phrase):
        return ""
    scene = angle_scene.scene_of(phrase)
    if scene["place"] or scene["time"]:
        return ""
    return phrase


def _mentioned_objects(texts, location: str = "") -> list:
    found = []
    for text in texts:
        for match in _OBJECT_RE.finditer(str(text or "")):
            phrase = _is_object(match.group(1))
            # An object the action only places ON something is the place, not
            # a prop: "sets the mug on the counter" puts the mug in Props and
            # leaves the counter to Location.
            if phrase and not _is_scenery_entry(phrase, location):
                found.append(phrase)
    return found


def _field_mentions(field_text, phrase: str) -> bool:
    blob = " ".join(str(field_text or "").casefold().split())
    if not blob:
        return False
    core = phrase.split()[-1].casefold()
    return bool(re.search(r"\b" + re.escape(core) + r"s?\b", blob))


def _prop_item(entry) -> str:
    """The carried/worn/used object in one props entry, without its place tail."""
    text = " ".join(str(entry or "").split()).strip(" ,;.")
    text = _PROP_PLACE_TAIL_RE.sub("", text)
    return text.strip(" ,;.")


def _prop_head(entry) -> str:
    words = re.findall(r"[A-Za-z][A-Za-z'\u2019-]*", str(entry or ""))
    return words[-1].casefold() if words else ""


def _scenery_word(word: str, words) -> bool:
    word = str(word or "").casefold().strip(" \t\r\n.,;:'\u2019\"")
    if not word:
        return False
    if word in words:
        return True
    # Plural forms: "counters", "benches", "shelves" (the irregular is listed).
    for suffix in ("es", "s"):
        if word.endswith(suffix) and word[:-len(suffix)] in words:
            return True
    return False


def _is_scenery_entry(entry, location: str = "") -> bool:
    """True when a props entry names the place, not an object the person uses.

    Furniture, rooms, buildings, fixtures and decor are always scenery. A sign,
    poster or billboard could be carried, so it is scenery only when the
    Location already names it — the duplication this removes.
    """
    item = _prop_item(entry)
    head = _prop_head(item)
    if not head:
        return False
    if _scenery_word(head, _FIXED_SCENERY_WORDS):
        return True
    return _scenery_word(head, _SIGNAGE_WORDS) and _field_mentions(location, item)


def prune_scenery_props(props, location: str = ""):
    """Props as (text, changed): objects only, never the place they rest in.

    A generated props list that names a counter, window or building is telling
    the model to draw scenery as a hand-held object, and it repeats what
    Location already says. Every entry is reduced to the object before any
    place phrase ("a mug on the counter" -> "a mug"), and scenery entries are
    dropped. A list that becomes empty comes back as "" so the row disappears.
    """
    raw = " ".join(str(props or "").split()).strip()
    if not raw:
        return raw, False
    parts = [part.strip() for part in re.split(r"\s*[,;]\s*", raw) if part.strip()]
    if not parts:
        return raw, False
    if len(parts) == 1 and parts[0].casefold() in ("none", "no props", "n/a", "-"):
        return raw, False
    kept, changed = [], False
    for part in parts:
        item = _prop_item(part)
        if not item or _is_scenery_entry(item, location):
            changed = True
            continue
        if item != part:
            changed = True
        kept.append(item)
    if not changed:
        return raw, False
    return ", ".join(kept), True


def append_clause(existing, addition) -> str:
    """Append a clause to a text field, capitalised, without double punctuation."""
    base = " ".join(str(existing or "").split()).strip(" .;")
    text = f"{base + '; ' if base else ''}{addition}".strip(" .;")
    return (text[:1].upper() + text[1:]) if text else text


def _append_list(existing, additions):
    """Join `additions` into a list field; returns (text, overflowed)."""
    base = " ".join(str(existing or "").split()).strip(" .;")
    if base.casefold() in ("", "none", "no props", "n/a", "-"):
        base = ""
    joined = ", ".join(additions)
    text = append_clause(base, joined)
    if len(text) > FIELD_LIMIT:
        return text, True
    return text, False


def _content_tokens(text):
    return {
        word for word in re.findall(r"[a-z']{4,}", " ".join(str(text or "").casefold().split()))
        if word not in _ACTIONS_STOP_WORDS
    }


def _missing_actions(texts, movement) -> list:
    movement_tokens = _content_tokens(movement)
    missing = []
    for text in texts:
        tokens = _content_tokens(text)
        if not tokens:
            continue
        covered = len(tokens & movement_tokens) / len(tokens)
        if covered < _COVERAGE:
            missing.append(" ".join(str(text).split()))
    return missing


def _compact_clause(text, must_cover, limit=FIELD_LIMIT) -> tuple:
    """Shorten a text field to `limit` without losing `must_cover` content.

    The field is a "; "-joined list of clauses. Clauses whose content words
    are already covered by the clauses that stay are redundant and are
    dropped, longest-first, until the field fits. Returns ("", True) when no
    shortening can preserve every required action, so the caller can decide:
    Props refuses rather than cut, Movement truncates with a warning.
    """
    raw = " ".join(str(text or "").split()).strip(" .;")
    if not raw or len(raw) <= limit:
        return raw, False
    clauses = [clause.strip() for clause in raw.split(";") if clause.strip()]
    if not clauses:
        return "", True

    required = set()
    for item in must_cover or []:
        required |= _content_tokens(item)

    def preserves(candidate) -> bool:
        covered = set()
        for clause in candidate:
            covered |= _content_tokens(clause)
        return not required or required <= covered

    candidate = list(clauses)
    while len("; ".join(candidate)) > limit and len(candidate) > 1:
        best = None
        for index in range(len(candidate)):
            rest = candidate[:index] + candidate[index + 1:]
            if preserves(rest):
                saved = len(candidate[index]) + 2
                if best is None or saved > best[0]:
                    best = (saved, index)
        if best is None:
            break
        candidate.pop(best[1])
    compacted = "; ".join(candidate)
    if len(compacted) > limit:
        return "", True
    compacted = compacted.strip(" .;")
    return (compacted[:1].upper() + compacted[1:] if compacted else compacted), (compacted != raw)


def _truncate_to_limit(text: str, limit: int) -> str:
    """Best-effort fit: cut at the last clause boundary at or under limit."""
    raw = " ".join(str(text or "").split()).strip(" .;")
    if len(raw) <= limit:
        return raw[:1].upper() + raw[1:] if raw else raw
    head = raw[:limit]
    cut = head.rfind("; ")
    if cut > 0:
        trimmed = head[:cut].strip(" .;")
        if trimmed:
            return trimmed[:1].upper() + trimmed[1:]
    trimmed = head.rsplit(" ", 1)[0].strip(" .;")
    return (trimmed[:1].upper() + trimmed[1:]) if trimmed else head.strip(" .;")


def reconcile_scene(strategy, plan=None) -> dict:
    """Patch a strategy's scene fields into agreement; report what will not fit.

    Returns {"strategy", "changed", "blocked", "warnings"}. `changed` lists the
    labels of the fields the patch rewrote; `blocked` lists {field, reason} for
    a field that still cannot hold its requirement (only Props can block now),
    which the render guard turns into a refusal; `warnings` lists advisory
    fields (Movement over MOVEMENT_LIMIT) that were compacted best-effort so
    the render can proceed. The input strategy is never mutated.
    """
    result = copy.deepcopy(strategy) if isinstance(strategy, dict) else {}
    changed, blocked, warnings = [], [], []
    if not result:
        return {"strategy": result, "changed": changed, "blocked": blocked,
                "warnings": warnings}

    # The setup the founder picked is the source of truth (ADR 0108): the plan
    # carries it when the caller saved one, and the strategy's own field is
    # the fallback. Syncing first keeps every rewrite below honest about
    # which phone/camera words are allowed.
    if isinstance(plan, dict):
        planned_setup = str(plan.get("camera_setup") or "").strip().lower()
        if planned_setup in ("handheld", "fixed"):
            result["camera_setup"] = planned_setup

    # A handheld selfie names no phone anywhere (ADR 0093): Phone clauses are
    # removed from the strategy's own action/concept/movement fields before
    # any completion pass below can copy them back into Props or Movement.
    # Running the same strip the render guard runs keeps the panel and the
    # prompt agreeing on read as well as on render. A fixed camera keeps the
    # phone in the action and Props.
    if final_beat.is_selfie(result):
        strip_audit = final_beat.strip_fields(result)
        result = strip_audit["strategy"]
        changed.extend(strip_audit["changed"])

    scene = result.get("scene") if isinstance(result.get("scene"), dict) else None
    if scene is not None:
        changed.extend(clean_placeholders(scene))

        # Camera angle and Visual style describe how the camera films, never
        # what the person holds: a filming phone is always "the camera" there.
        for key, label in (("camera_angle", "Camera angle"),
                           ("visual_style", "Visual style")):
            before = str(scene.get(key) or "")
            after = camera_wording(before)
            if after != before:
                scene[key] = after
                changed.append(label)

        # Location names the place only, in every camera setup: a phone may
        # stay in the action and Props for a fixed camera, never in the place
        # (ADR 0108). Object clauses are dropped before the lighting split
        # below, so lighting text is never read as an object either.
        place_only, objects_removed = strip_location_objects(scene.get("location"))
        if objects_removed:
            scene["location"] = place_only
            for key in ("environment", "background", "setting"):
                if key in scene and scene[key] != place_only:
                    scene[key] = place_only
            changed.append("Location")

        # Location names the place; the lighting and time it still carries move
        # into Lighting. The legacy split copies (environment/background/
        # setting) follow it, or their longer text wins the time of day back
        # through merge_legacy_location on the next read.
        place, moved = split_location(scene.get("location"))
        if moved:
            scene["location"] = place
            for key in ("environment", "background", "setting"):
                if key in scene and scene[key] != place:
                    scene[key] = place
            scene["lighting"] = append_clause(scene.get("lighting"), moved)
            changed.append("Location")
            changed.append("Lighting")

        # One setup, one set of camera words: a handheld strategy cannot say
        # "fixed camera"/"locked shot"/"steady framing", and a fixed strategy
        # cannot say "handheld"/"arm's length". The setup is rewritten, never
        # refused, because the plan/strategy already disagreed and a rewrite
        # is the deterministic repair (ADR 0108). Movement is included so a
        # handheld "the camera pushes in" becomes the lean it can film.
        changed.extend(camera_setup_wording(result))

        # A camera move the plan's default look names ("a slow push in during
        # the middle") lives in Framing and Movement as well as in the plan
        # text, translated to a lean for handheld (ADR 0108).
        changed.extend(carry_camera_movement(result, plan))

        # Props are objects the person carries, wears or uses — never the
        # furniture, buildings or signs Location already names.
        props_text, props_pruned = prune_scenery_props(
            scene.get("props"), scene.get("location")
        )
        if props_pruned:
            scene["props"] = props_text
            changed.append("Props")

        texts = _action_texts(result) + _beat_action_texts(plan)
        if final_beat.is_selfie(result):
            # In a selfie video the recording phone cannot appear: beat texts
            # and props that name one would otherwise be copied into the
            # props/movement lists this pass completes (ADR 0093).
            texts = [
                kept for kept, _removed in
                (final_beat.split_phone_clauses(text) for text in texts)
                if kept
            ]
            props_kept, props_removed = final_beat.strip_props(scene.get("props"))
            if props_removed:
                scene["props"] = props_kept
                changed.append("Props")

        missing_objects = []
        for phrase in _mentioned_objects(texts, scene.get("location")):
            if not _field_mentions(scene.get("props"), phrase):
                missing_objects.append(phrase)
        if missing_objects:
            props_text, over = _append_list(
                scene.get("props"), _unique_list(missing_objects)
            )
            if over:
                blocked.append({
                    "field": "Props",
                    "reason": "cannot list every object the actions and timeline show within its size limit",
                })
            else:
                scene["props"] = props_text
                changed.append("Props")

    performance = result.get("performance") if isinstance(result.get("performance"), dict) else None
    if performance is not None:
        movement_texts = _action_texts(result) + _beat_action_texts(plan)
        if final_beat.is_selfie(result):
            # Beat texts and props that name one would otherwise be copied
            # into the lists this pass completes (ADR 0093).
            movement_texts = [
                kept for kept, _removed in
                (final_beat.split_phone_clauses(text) for text in movement_texts)
                if kept
            ]
        missing = _missing_actions(
            movement_texts, performance.get("movement"),
        )
        if missing:
            movement = append_clause(
                performance.get("movement"), "; ".join(dict.fromkeys(missing))
            )
            if len(movement) > MOVEMENT_LIMIT:
                # Compact instead of refusing an ordinary render: the fields
                # the founder actually reads (Location, Lighting, Props, the
                # actions and the prompt) stay intact, and Movement is
                # shortened to the actions it can still cover. Movement is a
                # summary lock — the source actions are still sent verbatim —
                # so beyond MOVEMENT_LIMIT it is truncated best-effort with a
                # warning, never a block (ADR 0104).
                compacted, compacted_changed = _compact_clause(
                    movement, movement_texts, MOVEMENT_LIMIT
                )
                if not compacted or len(compacted) > MOVEMENT_LIMIT:
                    compacted = _truncate_to_limit(movement, MOVEMENT_LIMIT)
                    warnings.append({
                        "field": "Movement",
                        "reason": "movement exceeds its size limit and was shortened to fit",
                    })
                performance["movement"] = compacted
                changed.append("Movement")
                if compacted_changed:
                    changed.append("Movement")
            else:
                performance["movement"] = movement
                changed.append("Movement")

    # De-duplicate labels in first-seen order.
    changed = list(dict.fromkeys(changed))
    return {"strategy": result, "changed": changed, "blocked": blocked,
            "warnings": warnings}
