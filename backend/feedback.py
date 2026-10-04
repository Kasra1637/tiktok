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
"the ending felt abrupt" are distinguishable. `detail` is accepted as an
optional note but is never counted.

The vocabulary describes the generated piece only. "CTA unclear" was here for
as long as the plan carried a call to action; it is gone because a generated
piece has no closing beat — the middle stops at the moment the viewer would
reach for the app, and the close is the founder's own footage. Asking why a
generated video's CTA was unclear asked about something that was never in it.
"""
from collections import Counter

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
#
# "clear_cia" keeps its original misspelling on purpose: it is a code already
# stored against real approval events, and renaming the key would orphan that
# history and print the raw code in the breakdown. Only the label
# changed — it used to read "Clear CTA", which described a closing beat this
# product does not generate. "Ended cleanly" is what the founder is actually
# reporting on: the generated middle stopping where the demo takes over.
REASON_LABELS = {
    "hook_too_weak": "Hook too weak",
    "template_inappropriate": "Template inappropriate",
    "audience_mismatch": "Wrong audience",
    "too_promotional": "Too promotional",
    "app_feature_inaccurate": "App feature inaccurate",
    "ui_distorted": "UI distorted",
    "character_inconsistent": "Character inconsistent",
    "pacing_too_slow": "Pacing too slow",
    "script_too_long": "Script too long",
    "visual_style_wrong": "Visual style wrong",
    "audio_unsuitable": "Audio unsuitable",
    "model_error": "Model error",
    "worked_well": "Worked well",
    "hook_strong": "Hook was strong",
    "clear_cia": "Ended cleanly",
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


# Transparent feedback weights. These are deliberately small and capped: past
# behavior should inform a recommendation, not permanently bury a template
# because a founder rejected it twice while exploring the library.
FEEDBACK_WEIGHTS = {
    "explicit_template_rejection": -2.0,
    "automatic_template_change": -1.0,
    "generation_rejection": -1.0,
    "marked_unsuccessful": -1.5,
    "video_approved": 1.0,
    "marked_successful": 2.0,
}
FEEDBACK_CAPS = {
    "rejection": -6.0,
    "approval": 4.0,
}


def summarize(events) -> dict:
    """
    What happened, and why.

    Two independent breakdowns, kept apart on purpose:

    - by_event / top_signals count factual triggers. Every regenerate is
      recorded, so this says how often rework happens.
    - top_reasons counts only the explicit judgments a founder supplied. Since
      those are optional, this is usually smaller, and that is honest: it is the
      subset of rework someone bothered to explain.

    Reading them together is the point. A high regenerate count with a
    near-empty top_reasons means rework is frequent but unexplained, which is a
    different problem from a specific, repeatable complaint.

    Free-text detail is deliberately excluded from both: it is not a fixed code
    and cannot change a recommendation.
    """
    rows = list(events or [])
    by_event = Counter(r.get("event") or "unknown" for r in rows)
    by_signal = Counter(r.get("signal") for r in rows if r.get("signal"))
    by_reason = Counter(r.get("reason") for r in rows if r.get("reason"))
    return {
        "total": len(rows),
        "by_event": dict(by_event.most_common()),
        "top_signals": [{"signal": s, "count": n} for s, n in by_signal.most_common(10)],
        "top_reasons": [{"reason": r, "count": n} for r, n in by_reason.most_common(10)],
        # How many events carry an explanation, so a thin top_reasons is
        # readable as "unexplained" rather than mistaken for "no problem".
        "explained": sum(by_reason.values()),
    }


def summarize_profile_feedback(events, template_id: str = "") -> dict:
    """
    Aggregate one App Profile's feedback into recommendation- and prompt-ready
    facts.

    Only fixed event/signal/reason codes are counted. Free-text detail is
    ignored here for the same reason it is ignored in summarize(): it cannot be
    applied consistently, and passing founder notes into a prompt would leak
    unstructured judgments into generated copy.
    """
    summary = {
        "total": 0,
        "template_rejections": 0,
        "generation_rejections": 0,
        "approvals": 0,
        "successful_marks": 0,
        "unsuccessful_marks": 0,
        "heavy_script_edits": 0,
        "top_reasons": [],
        "selected_template": {
            "template_id": template_id or "",
            "rejections": 0,
            "approvals": 0,
            "successful_marks": 0,
            "unsuccessful_marks": 0,
            "top_reasons": [],
        },
    }
    reason_counts = {}
    selected_reason_counts = {}
    for row in events or []:
        if not isinstance(row, dict):
            continue
        event = row.get("event") or ""
        reason = row.get("reason") or ""
        row_template_id = str(row.get("template_id") or "")
        is_selected = bool(template_id) and row_template_id == template_id
        summary["total"] += 1
        if event == "template_rejected":
            summary["template_rejections"] += 1
        elif event in ("generation_rejected", "video_regenerated"):
            # A regenerate is weaker evidence than an explicit rejection, but
            # it is still rework attached to whatever was just rendered.
            summary["generation_rejections"] += 1
        elif event == "video_approved":
            summary["approvals"] += 1
        elif event == "marked_successful":
            summary["successful_marks"] += 1
        elif event == "marked_unsuccessful":
            summary["unsuccessful_marks"] += 1
        elif row.get("signal") == "script_edited_heavy":
            summary["heavy_script_edits"] += 1
        if reason:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            if is_selected:
                selected_reason_counts[reason] = selected_reason_counts.get(reason, 0) + 1
        if is_selected:
            if event == "template_rejected":
                summary["selected_template"]["rejections"] += 1
            elif event in ("video_approved", "marked_successful"):
                summary["selected_template"]["approvals"] += 1
                if event == "marked_successful":
                    summary["selected_template"]["successful_marks"] += 1
            elif event in ("generation_rejected", "marked_unsuccessful"):
                summary["selected_template"]["unsuccessful_marks"] += 1
    summary["top_reasons"] = [
        {"reason": reason, "count": count}
        for reason, count in sorted(
            reason_counts.items(), key=lambda item: (-item[1], item[0])
        )[:5]
    ]
    summary["selected_template"]["top_reasons"] = [
        {"reason": reason, "count": count}
        for reason, count in sorted(
            selected_reason_counts.items(), key=lambda item: (-item[1], item[0])
        )[:5]
    ]
    return summary


def template_feedback_adjustment(events, template_id: str) -> dict:
    """
    Convert feedback into a bounded recommendation adjustment.

    The adjustment is returned alongside its factual basis so the UI can show
    exactly why a score moved. Automatic triggers count less than explicit
    judgments, and nothing here invents a reason the founder did not state.
    """
    facts = {
        "template_id": template_id or "",
        "explicit_rejections": 0,
        "automatic_changes": 0,
        "approvals": 0,
        "successful_marks": 0,
        "unsuccessful_marks": 0,
        "top_reasons": [],
    }
    rejection_delta = 0.0
    approval_delta = 0.0
    # Only rows naming this template affect its score. Profile-level totals
    # belong in prompts, not in one template's score.
    for row in events or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("template_id") or "") != (template_id or ""):
            continue
        event = row.get("event") or ""
        reason = row.get("reason") or ""
        signal = row.get("signal") or ""
        if event == "template_rejected" and reason:
            facts["explicit_rejections"] += 1
            rejection_delta += FEEDBACK_WEIGHTS["explicit_template_rejection"]
        elif event == "template_rejected":
            facts["automatic_changes"] += 1
            rejection_delta += FEEDBACK_WEIGHTS["automatic_template_change"]
        elif event in ("generation_rejected", "marked_unsuccessful"):
            facts["unsuccessful_marks"] += 1 if event == "marked_unsuccessful" else 0
            rejection_delta += FEEDBACK_WEIGHTS[
                "marked_unsuccessful" if event == "marked_unsuccessful" else "generation_rejection"
            ]
        elif event == "video_approved":
            facts["approvals"] += 1
            approval_delta += FEEDBACK_WEIGHTS["video_approved"]
        elif event == "marked_successful":
            facts["successful_marks"] += 1
            approval_delta += FEEDBACK_WEIGHTS["marked_successful"]
        if reason:
            for entry in facts["top_reasons"]:
                if entry["reason"] == reason:
                    entry["count"] += 1
                    break
            else:
                facts["top_reasons"].append({"reason": reason, "count": 1})
    facts["top_reasons"].sort(key=lambda entry: (-entry["count"], entry["reason"]))
    facts["top_reasons"] = facts["top_reasons"][:3]
    delta = max(FEEDBACK_CAPS["rejection"], min(0.0, rejection_delta))
    delta += max(0.0, min(FEEDBACK_CAPS["approval"], approval_delta))
    facts["delta"] = round(delta, 2)
    return facts


def summarize_proved_hooks(rows) -> dict:
    """
    What this app's own finished videos actually did, from manual performance.

    This is the only signal in the system that improves with use. Everything
    else on the App Profile is scraped once and then goes stale: the model
    guesses which hook language sounds right, and nothing corrects it. Here the
    founder's own numbers say which templates and which openings carried a video.

    `rows` are the result of joining performance_entries to generations, which
    is where template_id lives -- an entry is a performance number against a
    render, and the render is what knows which template it used.

    Deliberately aggregate and anonymous. No video text, caption or source URL is
    read, only per-template counts, so nothing about a specific published video
    reaches a prompt. `source` is respected rather than trusted: an entry not
    marked manual is excluded, because a future automated import must not be
    able to quietly feed itself into generation.

    Returns an empty "no signal" shape rather than an invented best performer
    when there is not enough data to say anything -- one view is not evidence,
    and a confident-sounding wrong claim here would be worse than silence.
    """
    per_template = {}
    total = 0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("source") or "manual") != "manual":
            continue
        try:
            views = int(row.get("views") or 0)
        except (TypeError, ValueError):
            views = 0
        if views <= 0:
            # A like or a save with no view count cannot be ranked against
            # anything, and treating it as one would invent a rate.
            continue
        key = str(row.get("template_id") or "").strip() or "(untemplated)"
        bucket = per_template.setdefault(
            key,
            {"template_id": key, "views": 0, "likes": 0, "shares": 0, "saves": 0, "videos": 0},
        )
        for field in ("views", "likes", "comments", "shares", "saves"):
            try:
                bucket[field] = bucket.get(field, 0) + int(row.get(field) or 0)
            except (TypeError, ValueError):
                pass
        bucket["videos"] += 1
        total += 1

    if total == 0:
        return {"has_signal": False, "videos": 0, "top": [], "bottom": []}

    ranked = sorted(
        per_template.values(),
        key=lambda b: (-b["views"], b["template_id"]),
    )

    def _rate(bucket, field):
        return round(bucket.get(field, 0) / bucket["views"], 4) if bucket["views"] else 0.0

    def _shape(bucket):
        return {
            "template_id": bucket["template_id"],
            "videos": bucket["videos"],
            "views": bucket["views"],
            "save_rate": _rate(bucket, "saves"),
            "share_rate": _rate(bucket, "shares"),
        }

    return {
        "has_signal": True,
        "videos": total,
        "top": [_shape(b) for b in ranked[:3]],
        "bottom": [_shape(b) for b in reversed(ranked[-2:])] if len(ranked) > 1 else [],
    }


def build_proved_hooks_section(summary: dict) -> str:
    """
    Render the aggregate as prompt context, or say plainly that there is none.

    Silence is the honest output for a new app. A prompt that says "the founder
    found nothing yet" tells the model to rely on the app's own facts, which is
    the correct instruction -- whereas an invented best performer would be
    indistinguishable from a real one by the time it reaches generation.
    """
    summary = summary or {}
    if not summary.get("has_signal"):
        return (
            "PAST PERFORMANCE: none recorded for this app yet. There is no evidence "
            "about which openings work, so rely on the verified facts and do not "
            "assume any approach is proven."
        )

    def _describe(item):
        return (
            f"{item['template_id']} ({item['videos']} video(s), {item['views']} views, "
            f"save rate {item['save_rate']}, share rate {item['share_rate']})"
        )

    lines = [
        f"PAST PERFORMANCE for this app across {summary['videos']} recorded video(s), "
        "from the founder's own numbers:",
    ]
    top = summary.get("top") or []
    if top:
        lines.append("Carried the most views: " + "; ".join(_describe(i) for i in top) + ".")
    bottom = summary.get("bottom") or []
    if bottom:
        lines.append(
            "Underperformed: " + "; ".join(_describe(i) for i in bottom)
            + ". Do not reuse these openings; the numbers are the founder's, not an estimate."
        )
    lines.append(
        "This is view-count evidence only, not a claim that one template is better. "
        "Use it to avoid repeating what already flopped, not as proof."
    )
    return "\n".join(lines)


def build_profile_feedback_section(summary: dict) -> str:
    """
    Render feedback as prompt context without leaking free text.

    The model receives counts and fixed reason codes only. It is explicitly
    told that automatic triggers do not explain themselves, so it can avoid
    repeating a stated problem without inventing a causal story.
    """
    summary = summary or {}
    lines = [
        f"Recorded feedback events: {summary.get('total', 0)}.",
        f"Template rejections: {summary.get('template_rejections', 0)}.",
        f"Generation rejections or regenerations: {summary.get('generation_rejections', 0)}.",
        f"Approvals: {summary.get('approvals', 0)}.",
        f"Videos marked successful: {summary.get('successful_marks', 0)}.",
        f"Videos marked unsuccessful: {summary.get('unsuccessful_marks', 0)}.",
        f"Heavy script edits: {summary.get('heavy_script_edits', 0)}.",
    ]
    top_reasons = summary.get("top_reasons") or []
    if top_reasons:
        stated = ", ".join(
            f"{item.get('reason', '').replace('_', ' ')} ({item.get('count', 0)})"
            for item in top_reasons
        )
        lines.append(f"Founder-stated recurring issues: {stated}.")
    else:
        lines.append("No founder-stated reason has been supplied yet.")
    selected = summary.get("selected_template") or {}
    if selected.get("template_id"):
        lines.append(
            "Selected template history: "
            f"{selected.get('rejections', 0)} rejections, "
            f"{selected.get('approvals', 0)} approvals, "
            f"{selected.get('successful_marks', 0)} successful marks, "
            f"{selected.get('unsuccessful_marks', 0)} unsuccessful marks."
        )
        selected_reasons = selected.get("top_reasons") or []
        if selected_reasons:
            stated = ", ".join(
                f"{item.get('reason', '').replace('_', ' ')} ({item.get('count', 0)})"
                for item in selected_reasons
            )
            lines.append(f"Founder-stated issues for this template: {stated}.")
    lines.append(
        "Automatic triggers record that rework happened; only the stated "
        "reasons above explain why. Avoid repeating a stated issue, but do not "
        "invent additional causes."
    )
    return "\n".join(lines)
