"""The opening must move: the hook's first beat is a visible physical action.

ADR 0090 made this a prompt rule: inside the first 1-2 seconds the viewer
watches a movement, gesture or position change, and words never open the
video alone. That rule had no automated check — a strategy whose hook action
was a static pose ("stands still", "smiles") or pure speech ("she says...")
passed every gate and rendered a talking head.

This module is the check. It reads the first beat from where it actually
lives — the strategy's `hook_action` (and the hook segment's action) — and
reports it when the opening has no visible move:

- a clear physical movement (steps, turns, stands, sits, reaches, lifts,
  places, grabs, walks, gestures, tilts, nods, shrugs),
- a gesture strong enough to be seen (points, waves, counts, taps),
- nothing that fails: speaking alone, standing still, looking at the lens,
  smiling, or being introduced by the camera.

A missed opening is invalid at generation time and refused at render time,
rather than shipped as a dead opening. The validator is lexical and
conservative like the other scene policy modules: it looks for action verbs
and rejects the known static-talk patterns, so it cannot passively approve
an opening with nothing happening in it.

Pure policy: no HTTP, AI, auth or persistence imports.
"""
import copy
import re

# A genuine visible movement, gesture or position change. Each alternative
# is a verb that a video can show, not a state a person can be in. Kept
# deliberately close to the ADR 0090 enumeration (step, turn, stand, sit,
# reach, lift, place, grab) plus the other moves a hook legitimately uses.
_MOVE_RE = re.compile(
    r"\b(?:walk\w*|step\w*|strid\w*|march\w*|jog\w*|run\w*|turn\w*|pivot\w*|"
    r"spin\w*|twirl\w*|stand\w*|sit\w*|rise\w*|lie\w*(?:\s+down)?|kneel\w*|"
    r"crouch\w*|squat\w*|hop\w*|jump\w*|leap\w*|lean\w*|lunge\w*|"
    r"reach\w*|stretch\w*|grab\w*|grasp\w*|seiz\w*|pick\w*|lift\w*|"
    r"raise\w*|lower\w*|hold\w*|carry\w*|place\w*|put\w*|set\w*|"
    r"push\w*|pull\w*|drag\w*|slide\w*|press\w*|tap\w*|"
    r"point\w*|wave\w*|gesture\w*|nod\w*|shake\w*|tilt\w*|shrug\w*|"
    r"bend\w*|straighten\w*|sway\w*|toss\w*|throw\w*|catch\w*|"
    r"shake\w*|pound\w*|punch\w*|kick\w*|stomp\w*|"
    r"counts?\s+on\s+(?:her\s+|his\s+|their\s+)?fingers?|"
    r"touches?\s+(?:her\s+|his\s+|their\s+)?(?:face|cheek|hair|forehead|"
    r"shoulder|chest|heart|stomach|arm)|"
    r"brings?\s+(?:a\s+|her\s+|his\s+|their\s+|the\s+)?(?:hand|arm|mug|cup|"
    r"glass|phone|book|notebook|bag|object|item)\b|"
    r"places?\s+(?:a\s+|her\s+|his\s+|their\s+|the\s+)?(?:hand|mug|cup|glass|"
    r"object|item|book|notebook|bag)\b|"
    r"opens?\s+(?:the\s+|her\s+|his\s+|their\s+)?(?:notebook|book|bag|"
    r"door|drawer|bottle|box|cover|lid)\b|"
    r"closes?\s+(?:the\s+|her\s+|his\s+|their\s+)?(?:notebook|book|bag|"
    r"door|drawer|bottle|box|cover|lid)\b)"
    r"\b",
    re.I,
)

# Known non-movements: words that describe who someone is or what they are
# doing in a way a camera cannot see. A beat whose only verbs live here is
# static. These are checked for presence but never count as movement.
_STATIC_RE = re.compile(
    r"\b(?:stands?\s+still|stands?\s+quiet|stands?\s+neutral|"
    r"looks?\s+(?:at|into|towards?|toward)\s+(?:the\s+)?(?:camera|lens)|"
    r"eyes?\s+(?:on|to)\s+the\s+(?:camera|lens)|"
    r"looks?\s+serious|looks?\s+calm|looks?\s+happy|"
    r"smiles?\s+at\s+(?:the\s+)?(?:camera|lens)|"
    r"neutral\s+pose|talking\s+head|"
    r"says?\s+(?:the\s+line|it|the\s+words|something)|"
    r"speaks?\s+(?:directly\s+)?to\s+(?!the\s+(?:camera|lens)))\b",
    re.I,
)

# Speaking verbs: when these are the only verbs in the opening, the beat is
# a monologue, not a move.
_SPEAK_RE = re.compile(
    r"\b(?:says?|speaks?|tells?|whispers?|shouts?|yells?|asks?|answers?|"
    r"talks?|chats?|recites?|announces?)\b",
    re.I,
)


def _opening_texts(strategy) -> list:
    """Where the opening actually lives, in decision order."""
    texts = []
    if isinstance(strategy, dict):
        hook_action = str(strategy.get("hook_action") or "").strip()
        if hook_action:
            texts.append(hook_action)
        for section in strategy.get("segments") or []:
            if isinstance(section, dict) and str(section.get("role") or "").lower() == "hook":
                action = str(section.get("action") or "").strip()
                if action:
                    texts.append(action)
    return texts


def has_visible_move(text: str) -> bool:
    """True when a text names a visible movement, gesture or position change."""
    raw = " ".join(str(text or "").split())
    if not raw:
        return False
    clauses = [c.strip() for c in re.split(r"(?<=[.!?])\s+|,\s+|;\s+", raw) if c.strip()]
    if not clauses:
        return False
    for clause in clauses:
        lowered = clause.lower()
        # Static-talk clauses never count, even when they mention a verb shape
        # ("standing still", "looks at the camera"). Strip them before testing.
        if _STATIC_RE.search(lowered):
            if _MOVE_RE.search(_STATIC_RE.sub("", lowered)):
                return True
            continue
        if _MOVE_RE.search(lowered) and not _SPEAK_RE.fullmatch(lowered.strip(" .")):
            return True
    return False


def validate_opening(strategy) -> dict:
    """Check a strategy's first beat for a visible physical move.

    Returns {"ok", "reason", "texts"}: `ok` False means the opening would
    render static. `reason` names the failure in plain words the founder
    and the prompt repair can act on.
    """
    texts = _opening_texts(strategy)
    if not texts:
        return {"ok": False,
                "reason": "the opening names no physical action at all — "
                          "the first beat must show a visible move, not just words",
                "texts": texts}
    for text in texts:
        if has_visible_move(text):
            return {"ok": True, "reason": "", "texts": texts}
    return {"ok": False,
            "reason": "the opening is static — it names speaking, standing still, "
                      "looking at the camera, or a smile rather than a visible "
                      "movement, gesture or position change. Rewrite the first "
                      "beat so the viewer watches the person move first.",
            "texts": texts}


def repair(strategy) -> dict:
    """Prepend a generic visible movement to a rejected opening, if repairable.

    Returns {"strategy", "changed", "ok"}. The repair is additive only: the
    founder's own opening words stay, the move leads, and no spoken line or
    runtime changes. It is the deterministic fallback when regeneration is
    not available; the prompt rule is still the primary route. "Turns toward
    the camera" uses the camera as a direction cue only — it never reaches,
    holds, raises or shows a phone or camera, so selfie stripping leaves it
    alone.
    """
    result = copy.deepcopy(strategy) if isinstance(strategy, dict) else {}
    verdict = validate_opening(result)
    if verdict["ok"]:
        return {"strategy": result, "changed": [], "ok": True}
    lead = "Steps into frame and turns"
    if isinstance(result.get("hook_action"), str):
        result["hook_action"] = (lead + result["hook_action"]).strip()
    elif result.get("hook_action") is None:
        result["hook_action"] = lead
    for section in result.get("segments") or []:
        if isinstance(section, dict) and str(section.get("role") or "").lower() == "hook":
            if isinstance(section.get("action"), str):
                section["action"] = (lead + section["action"]).strip()
            elif section.get("action") is None:
                section["action"] = lead
            break
    if not any(isinstance(s, dict) and str(s.get("role") or "").lower() == "hook"
               for s in result.get("segments") or []):
        # No hook segment at all: the repaired opening lives on hook_action,
        # which the validator reads — do not invent a segment here.
        pass
    return {"strategy": result, "changed": ["Opening action"], "ok": True}
