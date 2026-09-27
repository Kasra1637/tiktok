"""
Structured feedback.

Feedback is only useful if it can be counted, so every reason here is a fixed
code from the product spec rather than free text. Detail is accepted as an
optional note but never aggregated.

The taxonomy is grouped by the moment it is captured, because "why did you
reject this template" and "why did you reject this script" are different
questions and mixing them produces numbers that mean nothing.
"""

# What happened.
EVENTS = (
    "template_rejected",
    "script_edited",
    "video_regenerated",
    "generation_failed",
    "video_approved",
    "video_downloaded",
    "marked_successful",
    "marked_unsuccessful",
)

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
    ),    "generation_failed": (
        "ui_distorted",
        "character_inconsistent",
        "audio_unsuitable",
        "model_error",
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


def normalize_reason(event: str, reason: str) -> str:
    """
    Validate a reason against its event.

    A reason is only counted when it belongs to the moment it was captured, so
    'hook_too_weak' is valid for a rejected template but not for a failed
    generation. An unrecognised pair returns an empty string and the caller
    refuses it, rather than storing a code that would never be aggregated.
    """
    e = normalize_event(event)
    if not e:
        return ""
    r = (reason or "").strip().lower().replace("-", "_").replace(" ", "_")
    allowed = REASONS.get(e, ())
    return r if r in allowed else ""


def allowed_reasons(event: str) -> list:
    e = normalize_event(event)
    return [
        {"key": reason, "label": REASON_LABELS.get(reason, reason)}
        for reason in REASONS.get(e, ())
    ]


def catalog() -> dict:
    """Events with their permitted reasons, for building the UI."""
    return {
        "events": [
            {
                "key": event,
                "reasons": allowed_reasons(event),
            }
            for event in EVENTS
        ]
    }
