"""
Structured feedback.

Two columns with deliberately different jobs:

- `signal` is a FACTUAL trigger, captured automatically the moment something
  happens. It is knowable without asking the founder anything, because it is
  just a record of what the software did.
- `reason` is a JUDGMENT about why, supplied explicitly. Optional.

Keeping them apart is the important design decision. A trigger such as
"regenerated" says nothing about *why*, and inferring a reason from it would
poison the "common regeneration reasons" aggregate with counterfactuals —
nothing knows the founder was unhappy with the hook specifically rather than
the length, the audience, or the day they had.

`reason` values are a fixed vocabulary rather than free text, because free
text cannot be aggregated, and this data is only useful if "hook too weak" and
"CTA unclear" are distinguishable. `detail` is accepted as an optional note
but is never counted.
"""

# What happened.
EVENTS = (
    "template_rejected",
    "script_edited",
    "video_regenerated",
    "generation_rejected",
    "video_approved",
    "video_downloaded",
    "marked_successful",
    "marked_unsuccessful",
)

# Factual triggers, captured automatically. Each maps to the event it explains.
SIGNALS = {
    "template_changed": "template_rejected",
    "script_edited_heavy": "script_edited",
    "script_edited_light": "script_edited",
    "regenerated": "video_regenerated",
    "rejected": "generation_rejected",
    "approved": "video_approved",
    "downloaded": "video_downloaded",
}

# A heavy script edit is judged by a character-count diff. The threshold is
# arbitrary but fixed, and the signal records which side of it the edit fell
# on, so the number is auditable rather than buried in a constant.
HEAVY_EDIT_RATIO = 0.25
HEAVY_EDIT_MIN_CHARS = 40


def classify_script_edit(before: str, after: str) -> str:
    """
    Return script_edited_heavy or script_edited_light for a change.

    "Heavy" means either at least HEAVY_EDIT_RATIO of the script's length
    changed, or at least HEAVY_EDIT_MIN_CHARS characters changed. Length is
    measured on the longer of the two texts so a rewrite from short to long
    counts as substantial.
    """
    before = before or ""
    after = after or ""
    if before == after:
        return ""
    changed = abs(len(after) - len(before))
    longest = max(len(before), len(after), 1)
    if changed >= HEAVY_EDIT_MIN_CHARS or (changed / longest) >= HEAVY_EDIT_RATIO:
        return "script_edited_heavy"
    return "script_edited_light"

REASONS = {
    "template_rejected": (
        "hook_too_weak",
        "template_inappropriate",
        "audience_mismatch",
        "too_promotional",
        "visual_style_wrong",
    ),
    "script_edited": (
        "script_too_long",
        "hook_too_weak",
        "cta_unclear",
        "too_promotional",
        "app_feature_inaccurate",
        "pacing_too_slow",
    ),
    "video_regenerated": (
        "hook_too_weak",
        "pacing_too_slow",
        "ui_distorted",
        "character_inconsistent",
        "audio_unsuitable",
        "app_feature_inaccurate",
        "visual_style_wrong",
    ),
    "generation_rejected": (
        "hook_too_weak",
        "ui_distorted",
        "character_inconsistent",
        "app_feature_inaccurate",
        "visual_style_wrong",
        "audio_unsuitable",
    ),
    "video_approved": (
        "worked_well",
        "hook_strong",
        "clear_cia",
    ),
    "video_downloaded": (
        "ready_to_post",
    ),
    "marked_successful": (
        "good_performance",
    ),
    "marked_unsuccessful": (
        "poor_performance",
        "hook_too_weak",
    ),
}

# Human-readable labels for the UI. Keeping them here means the wording lives
# beside the codes it describes.
REASON_LABELS = {
    "hook_too_weak": "Hook too weak",
    "template_inappropriate": "Template inappropriate",
    "audience_mismatch": "Wrong audience",
    "too_promotional": "Too promotional",
    "app_feature_inaccurate": "App feature inaccurate",
    "ui_distorted": "UI distorted",
    "character_inconsistent": "Character inconsistent",
    "pacing_too_slow": "Pacing too slow",
    "cta_unclear": "CTA unclear",
    "script_too_long": "Script too long",
    "visual_style_wrong": "Visual style wrong",
    "audio_unsuitable": "Audio unsuitable",
    "model_error": "Model error",
    "worked_well": "Worked well",
    "hook_strong": "Hook was strong",
    "clear_cia": "Clear CTA",
    "ready_to_post": "Ready to post",
    "good_performance": "Good performance",
    "poor_performance": "Poor performance",
}


def normalize_event(event: str) -> str:
    e = (event or "").strip().lower().replace("-", "_").replace(" ", "_")
    return e if e in EVENTS else ""


def normalize_signal(signal: str) -> str:
    """Validate an automatic trigger. Returns '' when unrecognised."""
    s = (signal or "").strip().lower().replace("-", "_").replace(" ", "_")
    return s if s in SIGNALS else ""


def signal_event(signal: str) -> str:
    """The event a given trigger belongs to, or '' when unrecognised."""
    return SIGNALS.get(normalize_signal(signal), "")


def normalize_reason(event: str, reason: str) -> str:
    """
    Validate an optional reason against its event.

    A reason is only counted when it belongs to the moment it was captured, so
    'hook_too_weak' is valid for a rejected template but not for a rejected
    generation. An unrecognised pair returns an empty string, which is legal:
    an automatically captured signal may legitimately carry no reason at all,
    because nothing knows the founder's judgment.
    """
    e = normalize_event(event)
    if not e:
        return ""
    r = (reason or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not r:
        return ""
    allowed = REASONS.get(e, ())
    return r if r in allowed else ""


def allowed_reasons(event: str) -> list:
    e = normalize_event(event)
    return [
        {"key": reason, "label": REASON_LABELS.get(reason, reason)}
        for reason in REASONS.get(e, ())
    ]


def catalog() -> dict:
    """Events, their permitted reasons, and the automatic triggers."""
    return {
        "events": [
            {
                "key": event,
                "reasons": allowed_reasons(event),
            }
            for event in EVENTS
        ],
        "signals": [
            {"key": signal, "event": event}
            for signal, event in SIGNALS.items()
        ],
        "heavy_edit": {
            "ratio": HEAVY_EDIT_RATIO,
            "min_chars": HEAVY_EDIT_MIN_CHARS,
        },
    }
