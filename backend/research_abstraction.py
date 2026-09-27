"""
Trend Research: turning public TikTok observation into reusable template drafts.

The output of this module is an ABSTRACT creative structure, never a
transcription of somebody's video. That distinction is the whole point of the
repositioning, so it is enforced in three places:

1. The prompt forbids carrying over identity, gestures, voice, music, or
   choreography, and asks for mechanics in the abstract.
2. The parser drops any field that looks like a source identity, and refuses
   to keep a source URL on the draft.
3. Drafts are created with review_status='draft' and are NOT usable until an
   operator publishes them, so a raw observation can never reach generation
   unreviewed.

A source video is never required for, or stored for reuse by, any customer
generation.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Vocabulary for abstracted hooks. Kept aligned with template_library's
# controlled categories so a draft can be published without reclassification.
MECHANIC_CATEGORIES = (
    "pattern-interrupt", "pain-point-question", "contrarian", "curiosity-gap",
    "before-after", "reveal", "demo", "tutorial", "story", "pov",
    "listicle", "social-proof", "other",
)

# Phrases that indicate a draft is still describing a specific video rather
# than a reusable structure. Checked against every generated string field.
IDENTITY_MARKERS = (
    "@", "creator handle", "this creator", "the same person", "voice of",
    "their face", "her face", "his face", "clone the voice", "same voice",
    "copyrighted song", "that song", "the beat from",
)

# Fields a draft may contain. Anything else from the model is discarded.
DRAFT_FIELDS = (
    "name", "category", "hook_mechanic", "opening_structure",
    "continuation_structure", "cta_pattern", "pacing_note",
    "why_it_repeats", "suits",
)


def _clean(value, limit: int = 400) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = ", ".join(str(v) for v in value)
    text = " ".join(str(value).split())
    return text[:limit].strip()


def looks_like_identity_copy(text: str) -> bool:
    """
    Whether text describes a specific creator rather than a mechanism.

    Used to reject a draft outright. Being conservative here is deliberate: a
    template that imitates a person is exactly what the product excludes, and a
    false positive just means the draft is rewritten.
    """
    blob = (text or "").lower()
    return any(marker in blob for marker in IDENTITY_MARKERS)


def normalize_mechanic(category: Optional[str]) -> str:
    c = (category or "").strip().lower().replace("_", "-").replace(" ", "-")
    return c if c in MECHANIC_CATEGORIES else "other"


def build_abstract_prompt(observations: list, app_context: str = "") -> str:
    """
    Prompt asking for reusable mechanics from a set of public observations.

    observations: [{"title","view_count","like_count","duration","hook_summary",
                    "text_overlays"}] — public metadata only.
    """
    import json as _json

    lines = []
    for i, obs in enumerate(observations[:15], start=1):
        lines.append(
            f"{i}. views={obs.get('view_count', 0)} "
            f"likes={obs.get('like_count', 0)} "
            f"duration={obs.get('duration', 0)}s\n"
            f"   opening text on screen: {_clean(obs.get('text_overlays'), 200)}\n"
            f"   observed structure: {_clean(obs.get('hook_summary'), 300)}"
        )
    block = "\n".join(lines) or "(no observations available)"

    return (
        "You study short-form video openings to extract REUSABLE CREATIVE MECHANICS.\n\n"
        f"PUBLIC OBSERVATIONS:\n{block}\n\n"
        f"{('APP CONTEXT: ' + app_context) if app_context else ''}\n\n"
        "Propose template DRAFTS describing the recurring MECHANISM behind openings like "
        "these. Return ONLY a JSON array, where each element is:\n"
        "{\n"
        '  "name": "short template name, e.g. Pain-point question",\n'
        '  "category": "one of: ' + ", ".join(MECHANIC_CATEGORIES) + '",\n'
        '  "hook_mechanic": "the abstract trigger, e.g. asking the viewer\'s problem out loud",\n'
        '  "opening_structure": "how an opening using this mechanic is built, generically",\n'
        '  "continuation_structure": "how it pays off, generically",\n'
        '  "cta_pattern": "how it closes, generically",\n'
        '  "pacing_note": "how fast it moves and where it cuts",\n'
        '  "why_it_repeats": "the structural reason this mechanic recurs",\n'
        '  "suits": ["app categories this would work for"]\n'
        "}\n"
        "HARD RULES:\n"
        "- Describe the MECHANISM only. Do NOT name, reference, or describe any creator, "
        "their handle, appearance, voice, personality, or likeness.\n"
        "- Do NOT reproduce specific gestures, choreography, or body performance.\n"
        "- Do NOT reference, name, or request any specific song, sound, or copyrighted audio.\n"
        "- Do NOT copy captions or scripts verbatim; describe the pattern, not the words.\n"
        "- Every draft must be usable by ANY creator for ANY app with no source video.\n"
        "- If the observations do not support a clear recurring mechanic, return fewer "
        "drafts rather than inventing one.\n"
        "Return ONLY valid JSON."
    )


def parse_drafts(response) -> tuple:
    """
    Turn the model response into safe drafts.

    Returns (drafts, rejected). Rejected entries are reported with a reason so
    an operator can see that the guard fired rather than wondering why a
    draft vanished.
    """
    if isinstance(response, dict):
        response = response.get("drafts") or response.get("templates") or []
    if not isinstance(response, list):
        return [], [{"reason": "model response was not a list"}]

    drafts, rejected = [], []
    for item in response[:12]:
        if not isinstance(item, dict):
            rejected.append({"reason": "entry was not an object"})
            continue

        cleaned = {f: _clean(item.get(f)) for f in DRAFT_FIELDS}
        suits = item.get("suits")
        cleaned["suits"] = (
            [s for s in (_clean(v, 60) for v in suits) if s][:8]
            if isinstance(suits, list) else []
        )

        # The identity guard runs over the whole draft, not one field, because
        # a creator reference can appear anywhere.
        blob = " ".join(str(v) for v in cleaned.values())
        if looks_like_identity_copy(blob):
            rejected.append({
                "name": cleaned.get("name") or "(unnamed)",
                "reason": "described a specific creator or copyrighted audio, not a mechanic",
            })
            continue

        if not cleaned["name"] or not cleaned["hook_mechanic"] or not cleaned["opening_structure"]:
            rejected.append({
                "name": cleaned.get("name") or "(unnamed)",
                "reason": "missing a name, mechanic, or opening structure",
            })
            continue

        cleaned["category"] = normalize_mechanic(cleaned.get("category"))
        # No source URL is ever carried onto a draft. The structure is the only
        # thing a draft keeps.
        cleaned["evidence_note"] = (
            "Drafted from public trend research, abstracted to a reusable mechanic. "
            "No source video, creator, or audio is retained or required."
        )
        cleaned["origin"] = "research_draft"
        cleaned["review_status"] = "draft"
        cleaned["archived"] = 0
        drafts.append(cleaned)

    return drafts, rejected


def summarize_observations(videos: list) -> list:
    """
    Reduce raw public video rows to the fields the prompt needs.

    Keeps only public engagement metadata and text, so nothing personal or
    copyrighted is carried into the model call.
    """
    out = []
    for v in (videos or [])[:15]:
        out.append({
            "title": _clean(v.get("title"), 120),
            "view_count": v.get("view_count") or 0,
            "like_count": v.get("like_count") or 0,
            "comment_count": v.get("comment_count") or 0,
            "duration": v.get("duration") or 0,
            "hook_summary": _clean(v.get("description") or v.get("title"), 300),
            "text_overlays": _clean(v.get("hashtags"), 200),
        })
    return out
