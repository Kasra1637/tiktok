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
# thumb_up / thumb_down are explicit founder verdicts from the thumbs-only AI
# loop (Audience & goal, Template & photo, Review, Hook + Story). They carry
# no signal or reason: the `step` column says where the verdict was given and
# `detail` optionally names the item version (e.g. plan v3). Existing
# aggregates ignore them; summarize_thumbs() reads them per step.
EVENTS = (
    "template_rejected",
    "script_edited",
    "video_regenerated",
    "generation_rejected",
    "video_approved",
    "video_downloaded",
    "marked_successful",
    "marked_unsuccessful",
    "thumb_up",
    "thumb_down",
)

# CreateVideo steps that accept a thumbs verdict. Stored lowercase in the
# `step` column so counts group cleanly regardless of UI labels.
THUMB_STEPS = (
    "audience_goal",
    "template_photo",
    "review",
    "hook_story",
)


def normalize_step(step: str) -> str:
    """Validate a thumbs step. Returns '' when unrecognised."""
    s = (step or "").strip().lower().replace("-", "_").replace(" ", "_")
    return s if s in THUMB_STEPS else ""

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


# History verdicts that attribute to the angle and objective behind a video.
#
# The rows these aggregate are pre-joined server-side (feedback event ->
# generation -> project -> angle kind + objective), because neither the event
# nor the generation names an angle on its own. Kinds and objectives are
# fixed vocabularies, so the counts survive an angle regeneration that
# replaces every angle row id — per-id attribution would be wiped by the
# very refresh it is meant to improve.
ANGLE_POSITIVE_EVENTS = ("marked_successful", "video_approved")
ANGLE_NEGATIVE_EVENTS = ("marked_unsuccessful", "generation_rejected")


def summarize_angle_feedback(rows) -> dict:
    """
    History verdicts grouped by the angle kind and objective behind each video.

    `rows` are pre-joined dicts carrying `kind`, `objective`, and `event`.
    Only the verdict events above are counted; anything else (a download, a
    thumb on another step) is ignored rather than lumped into a bucket.
    A row naming no kind and no objective says nothing attributable and is
    skipped for the same reason.
    """
    kinds: dict = {}
    objectives: dict = {}
    total = 0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        event = row.get("event") or ""
        if event in ANGLE_POSITIVE_EVENTS:
            verdict = "wins"
        elif event in ANGLE_NEGATIVE_EVENTS:
            verdict = "flops"
        else:
            continue
        kind = (row.get("kind") or "").strip()
        objective = (row.get("objective") or "").strip()
        if not kind and not objective:
            continue
        total += 1
        if kind:
            bucket = kinds.setdefault(kind, {"wins": 0, "flops": 0})
            bucket[verdict] += 1
        if objective:
            bucket = objectives.setdefault(objective, {"wins": 0, "flops": 0})
            bucket[verdict] += 1

    def _ranked(buckets):
        return [
            {"name": name, "wins": counts["wins"], "flops": counts["flops"]}
            for name, counts in sorted(
                buckets.items(),
                key=lambda item: (-item[1]["wins"] - item[1]["flops"], item[0]),
            )
        ][:5]

    return {"total": total, "kinds": _ranked(kinds), "objectives": _ranked(objectives)}


def build_angle_feedback_section(summary: dict) -> str:
    """
    Render angle verdicts as prompt context, or say plainly that there are none.

    Only counts travel: no video text, no founder notes. A thin record is
    labelled weak evidence so one verdict cannot permanently steer generation.
    """
    summary = summary or {}
    kinds = summary.get("kinds") or []
    objectives = summary.get("objectives") or []
    if not kinds and not objectives:
        return (
            "PAST VERDICTS: none recorded for this app yet. There is no evidence "
            "about which angles work, so propose from the verified facts and do "
            "not assume any approach is proven."
        )

    def _describe(entries):
        return "; ".join(
            f"{entry['name']} ({entry['wins']} win(s), {entry['flops']} flop(s))"
            for entry in entries
        )

    lines = [
        "PAST VERDICTS from the founder's own History verdicts "
        f"({summary.get('total', 0)} attributed verdict(s)). Weak evidence, not proof: "
        "lean toward what won and away from what flopped, but do not exclude "
        "a kind or objective on one verdict alone.",
    ]
    if kinds:
        lines.append("Angle kinds: " + _describe(kinds) + ".")
    if objectives:
        lines.append("Objectives: " + _describe(objectives) + ".")
    return "\n".join(lines)


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
        "thumb_steps": list(THUMB_STEPS),
        "heavy_edit": {
            "ratio": HEAVY_EDIT_RATIO,
            "min_chars": HEAVY_EDIT_MIN_CHARS,
        },
    }


def summarize_thumbs(events) -> dict:
    """
    Per-step thumbs verdicts for the AI refinement loop.

    Only thumb_up / thumb_down rows are counted, grouped by their step. Rows
    naming an unknown step are ignored rather than lumped into a bucket,
    so a typo cannot inflate another step's down count.
    """
    per_step = {step: {"up": 0, "down": 0} for step in THUMB_STEPS}
    for row in events or []:
        if not isinstance(row, dict):
            continue
        event = row.get("event") or ""
        if event not in ("thumb_up", "thumb_down"):
            continue
        step = normalize_step(row.get("step") or "")
        if not step:
            continue
        per_step[step]["up" if event == "thumb_up" else "down"] += 1
    return {
        step: {
            "up": counts["up"],
            "down": counts["down"],
            "total": counts["up"] + counts["down"],
        }
        for step, counts in per_step.items()
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
