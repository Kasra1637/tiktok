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

# A body part is never a prop; the person comes from the photograph.
_BODY_WORDS = frozenset((
    "face", "head", "hair", "eye", "eyes", "gaze", "brow", "brows",
    "eyebrow", "eyebrows", "jaw", "chin", "hand", "hands", "arm", "arms",
    "shoulder", "shoulders", "chest", "torso", "body", "posture", "leg",
    "legs", "knee", "knees", "finger", "fingers", "thumb", "thumbs",
    "skin", "smile", "expression", "mouth", "lips", "breath", "voice",
))

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


def _trim_object(phrase: str) -> str:
    words = str(phrase or "").split()
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
    if _LIGHT_RE.search(phrase):
        return ""
    scene = angle_scene.scene_of(phrase)
    if scene["place"] or scene["time"]:
        return ""
    return phrase


def _mentioned_objects(texts) -> list:
    found = []
    for text in texts:
        for match in _OBJECT_RE.finditer(str(text or "")):
            phrase = _is_object(match.group(1))
            if phrase:
                found.append(phrase)
    return found


def _field_mentions(field_text, phrase: str) -> bool:
    blob = " ".join(str(field_text or "").casefold().split())
    if not blob:
        return False
    core = phrase.split()[-1].casefold()
    return bool(re.search(r"\b" + re.escape(core) + r"s?\b", blob))


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


def reconcile_scene(strategy, plan=None) -> dict:
    """Patch a strategy's scene fields into agreement; report what will not fit.

    Returns {"strategy", "changed", "blocked"}. `changed` lists the labels of
    the fields the patch rewrote; `blocked` lists {field, reason} for a field
    that still cannot hold its requirement (a props or movement list over its
    size cap), which the render guard turns into a refusal. The input strategy
    is never mutated.
    """
    result = copy.deepcopy(strategy) if isinstance(strategy, dict) else {}
    changed, blocked = [], []
    if not result:
        return {"strategy": result, "changed": changed, "blocked": blocked}

    scene = result.get("scene") if isinstance(result.get("scene"), dict) else None
    if scene is not None:
        changed.extend(clean_placeholders(scene))

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
        for phrase in _mentioned_objects(texts):
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
        movement = performance.get("movement")
        missing = _missing_actions(
            _action_texts(result) + _beat_action_texts(plan), movement
        )
        if missing:
            movement_text, over = _append_list(
                movement, ["; ".join(dict.fromkeys(missing))]
            )
            if over:
                blocked.append({
                    "field": "Movement",
                    "reason": "cannot cover every action the sections and timeline show within its size limit",
                })
            else:
                performance["movement"] = movement_text
                changed.append("Movement")

    # De-duplicate labels in first-seen order.
    changed = list(dict.fromkeys(changed))
    return {"strategy": result, "changed": changed, "blocked": blocked}
