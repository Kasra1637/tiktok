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

# How many observations a mechanic needs before its performance is treated as a
# finding. Below this, build_evidence reports no signal regardless of the numbers
# -- one video is not a pattern, and a system that says otherwise teaches a
# founder to trust a coincidence.
MIN_SAMPLE = 5

# Fields a draft may contain. Anything else from the model is discarded.
#
# `middle_structure` replaced `continuation_structure` + `cta_pattern`. A draft
# used to describe a three-beat arc that paid off and closed on a call to
# action, and both halves were read into the render prompts — which is how a
# research draft could reintroduce a product demo into a workflow that does not
# generate one. One field now, describing the middle and stopping at the reach.
DRAFT_FIELDS = (
    "name", "category", "hook_mechanic", "opening_structure",
    "middle_structure", "pacing_note",
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
        '  "middle_structure": "how the middle develops that opening, generically, up to the '
        'moment the viewer would reach for the app",\n'
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
        "- A generated video is a HOOK and a MIDDLE, and nothing else. The middle develops "
        "the opening and stops at the moment the viewer would reach for the app: the product "
        "demo is recorded by the founder and attached afterwards, and they add their own call "
        "to action. So a draft must NOT describe a demonstration, a payoff that shows the app "
        "working, or a closing beat. middle_structure is where the story goes, not where it "
        "resolves.\n"
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


def _band(value, thresholds, labels):
    """
    Map a number onto a coarse label.

    Bands rather than exact numbers, deliberately. A precise view count attached
    to an abstracted mechanic is a fingerprint: it points back at one specific
    video and, through it, one specific creator. What the model actually needs
    is the order of magnitude, and a band carries that without carrying the
    source.
    """
    for threshold, label in zip(thresholds, labels):
        if value >= threshold:
            return label
    return labels[-1]


def build_evidence(videos: list) -> dict:
    """
    Aggregate performance evidence for a mechanic, with no source attached.

    This is the only trend signal that reaches generation, and it reaches it
    anonymously. No video id, URL, creator handle, caption, title or retention
    curve is read, stored, or prompted -- only bands derived from public
    engagement counts, plus how many observations the bands came from.

    `sample_size` is the load-bearing field. A mechanic abstracted from one
    video is not evidence of anything, and a system that reports a single
    observation with the same confidence as thirty is how a founder ends up
    treating a coincidence as a proven format. Below MIN_SAMPLE the whole
    evidence block reports no_signal, because "we saw this once" is not a finding.
    """
    rows = [v for v in (videos or []) if isinstance(v, dict)]
    if len(rows) < MIN_SAMPLE:
        return {
            "has_signal": False,
            "sample_size": len(rows),
            "median_view_band": "unknown",
            "median_engagement_band": "unknown",
            "recency_band": "unknown",
        }

    def _views(v):
        return max(int(v.get("view_count") or 0), 0)

    def _engagement_rate(v):
        views = _views(v)
        if not views:
            return 0.0
        engaged = (
            int(v.get("like_count") or 0) + int(v.get("comment_count") or 0)
            + int(v.get("share_count") or 0) + int(v.get("bookmark_count") or 0)
        )
        return engaged / views

    # Median, not mean: one 40M outlier would otherwise define the whole band
    # and make an ordinary mechanic look exceptional.
    ordered = sorted(_views(v) for v in rows)
    median_views = ordered[len(ordered) // 2]
    rates = sorted(_engagement_rate(v) for v in rows)
    median_engagement = rates[len(rates) // 2]

    ages = sorted(_age_hours(v) for v in rows)
    median_age = ages[len(ages) // 2]

    return {
        "has_signal": True,
        "sample_size": len(rows),
        "median_view_band": _band(
            median_views,
            (1_000_000, 100_000, 10_000, 1_000),
            ("1M+", "100K-1M", "10K-100K", "1K-10K", "under 1K"),
        ),
        "median_engagement_band": _band(
            median_engagement,
            (0.10, 0.05, 0.02),
            ("high (10%+ of views)", "typical (5-10%)", "moderate (2-5%)", "low (under 2%)"),
        ),
        "recency_band": _band(
            # Reversed: newer is better, so the thresholds count down.
            -median_age,
            (-48, -24 * 7, -24 * 30),
            ("under 48h", "under a week", "under a month", "older than a month"),
        ),
    }


def _age_hours(video: dict) -> float:
    """Best-effort age of an observation in hours. Unknown sorts as old."""
    for field in ("age_hours", "hours_old"):
        raw = video.get(field)
        try:
            if raw is not None:
                return max(float(raw), 0.0)
        except (TypeError, ValueError):
            pass
    created = video.get("created_at") or video.get("published_at")
    if isinstance(created, str) and created:
        try:
            from datetime import datetime, timezone
            stamp = datetime.fromisoformat(created.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            return max(
                (datetime.now(timezone.utc) - stamp).total_seconds() / 3600.0, 0.0
            )
        except (ValueError, TypeError):
            pass
    return 24.0 * 60.0


def build_evidence_sentence(evidence: dict) -> str:
    """
    Render the aggregate as one sentence for a prompt.

    Never claims a mechanic is proven. The wording is "openings of this shape
    have carried", which is an observation about a sample, not a guarantee about
    the founder's video.
    """
    if not evidence or not evidence.get("has_signal"):
        return ""
    sample = evidence.get("sample_size") or 0
    return (
        f"Across {sample} public openings of this shape in the last scan, the median one had "
        f"{evidence.get('median_view_band')} views and {evidence.get('median_engagement_band')} "
        f"engagement ({evidence.get('recency_band')}). This is what similar shapes have "
        f"carried, not a promise about any single video."
    )


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
