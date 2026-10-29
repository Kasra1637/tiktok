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
# thumb_up / thumb_down are founder verdicts on ONE component (goal, template,
# plan, script, or video), named in the `step` column. Each component's
# verdicts feed only the stage that produces it.
EVENTS = (
    "template_rejected",
    "script_edited",
    "video_regenerated",
    "video_downloaded",
    "plan_opened",
    "thumb_up",
    "thumb_down",
    # Implicit behavior beside the explicit thumbs. Thumbs stay the founder's
    # verdict; these add the dense evidence underneath:
    #
    # - adopted: the founder moved forward with exactly this item (picked it
    #   AND advanced: the goal/angle/template behind a generated plan, the
    #   plan and script behind a submitted render). Strongest positive.
    # - abandoned: the founder produced or picked this item and then moved
    #   past it without proceeding (regenerated over an unrendered plan,
    #   switched away from a template/angle that never rendered). Hard
    #   negative.
    # - generated: the item was shown as a candidate but never picked
    #   (an angle/goal/template on screen while another was chosen). Soft
    #   negative, and the weakest: being passed over once is not rejection.
    #
    # Like thumbs, behavior rows name their component in `step`, carry no
    # signal and no reason, and are never inferred into judgments. Adoption
    # and abandonment attribute exactly like thumbs (goal rows carry
    # `objective=..;kind=..` in detail); a shown-but-not-picked row carries
    # whatever identifies the item (template_id, or detail for angles/goals).
    "adopted",
    "abandoned",
    "generated",
)

COMPONENTS = ("goal", "template", "plan", "script", "video")

COMPONENT_LABELS = {
    "goal": "content goal",
    "template": "hook template",
    "plan": "script plan",
    "script": "spoken script",
    "video": "generated video",
}

# Rows recorded before component voting named the wizard step instead.
_LEGACY_STEPS = {
    "audience_goal": "goal",
    "template_photo": "template",
    "review": "plan",
    "hook_story": "script",
}


def normalize_component(step: str) -> str:
    """The component a thumbs verdict belongs to, or '' when unrecognised."""
    s = (step or "").strip().lower().replace("-", "_").replace(" ", "_")
    s = _LEGACY_STEPS.get(s, s)
    return s if s in COMPONENTS else ""

# Factual triggers, captured automatically. Each maps to the event it explains.
SIGNALS = {
    "template_changed": "template_rejected",
    "script_edited_heavy": "script_edited",
    "script_edited_light": "script_edited",
    "regenerated": "video_regenerated",
    "downloaded": "video_downloaded",
    "open_plan": "plan_opened",
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
    "video_downloaded": (
        "ready_to_post",
    ),
}

# Human-readable labels for the UI. Labels for retired video-level reasons
# stay so older stored rows still print readably in the breakdown.
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


# Goal verdicts attribute to the angle kind and objective that were picked.
# Rows are pre-joined server-side (feedback -> project -> angle kind +
# objective). Kinds and objectives are fixed vocabularies, so the counts
# survive an angle regeneration that replaces every angle row id.
def _goal_detail(detail: str) -> dict:
    """Parse 'objective=..;kind=..' written on a goal thumb at vote time."""
    parsed = {}
    for part in (detail or "").split(";"):
        key, _, value = part.partition("=")
        if key.strip() in ("objective", "kind") and value.strip():
            parsed[key.strip()] = value.strip()
    return parsed


def summarize_angle_feedback(rows) -> dict:
    """
    Goal thumbs grouped by the angle kind and objective they judged.

    `rows` are pre-joined dicts carrying `kind`, `objective`, `event`, `step`.
    Only thumbs on the goal component count; verdicts on a template, plan or
    script say nothing about the goal and are ignored.
    """
    kinds: dict = {}
    objectives: dict = {}
    total = 0
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if normalize_component(row.get("step") or "") != "goal":
            continue
        event = row.get("event") or ""
        if event == "thumb_up":
            verdict = "wins"
        elif event == "thumb_down":
            verdict = "flops"
        elif event == "adopted":
            verdict = "adoptions"
        elif event == "abandoned":
            verdict = "abandonments"
        else:
            continue
        # What was on screen when the founder voted beats the project's
        # current values, which change if they switch goal afterwards.
        voted = _goal_detail(row.get("detail") or "")
        kind = (voted.get("kind") or row.get("kind") or "").strip()
        objective = (voted.get("objective") or row.get("objective") or "").strip()
        if not kind and not objective:
            continue
        total += 1
        if kind:
            bucket = kinds.setdefault(
                kind, {"wins": 0, "flops": 0, "adoptions": 0, "abandonments": 0})
            bucket[verdict] += 1
        if objective:
            bucket = objectives.setdefault(
                objective, {"wins": 0, "flops": 0, "adoptions": 0, "abandonments": 0})
            bucket[verdict] += 1

    def _ranked(buckets):
        return [
            {"name": name, "wins": counts["wins"], "flops": counts["flops"],
             "adoptions": counts["adoptions"],
             "abandonments": counts["abandonments"]}
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
        parts = []
        for entry in entries:
            text = f"{entry['name']} ({entry['wins']} win(s), {entry['flops']} flop(s)"
            if entry.get("adoptions") or entry.get("abandonments"):
                text += (f", moved forward with {entry.get('adoptions', 0)}, "
                         f"dropped after picking {entry.get('abandonments', 0)}")
            parts.append(text + ")")
        return "; ".join(parts)

    lines = [
        "PAST VERDICTS from the founder's thumbs on previously picked goals "
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
        "components": list(COMPONENTS),
        "heavy_edit": {
            "ratio": HEAVY_EDIT_RATIO,
            "min_chars": HEAVY_EDIT_MIN_CHARS,
        },
    }


def summarize_component_feedback(events) -> dict:
    """
    Thumbs and behavior per component. Each bucket counts only rows naming
    that component, so a verdict on one component can never move another's
    counts. `total` stays the thumbs total so existing readers keep their
    meaning; behavior rides in its own counters.
    """
    per = {
        c: {"up": 0, "down": 0, "adopted": 0, "abandoned": 0, "shown": 0}
        for c in COMPONENTS
    }
    for row in events or []:
        if not isinstance(row, dict):
            continue
        event = row.get("event") or ""
        if event not in ("thumb_up", "thumb_down", "adopted", "abandoned",
                          "generated"):
            continue
        component = normalize_component(row.get("step") or "")
        if not component:
            continue
        if event == "thumb_up":
            per[component]["up"] += 1
        elif event == "thumb_down":
            per[component]["down"] += 1
        elif event == "adopted":
            per[component]["adopted"] += 1
        elif event == "abandoned":
            per[component]["abandoned"] += 1
        else:
            per[component]["shown"] += 1
    return {
        c: {"up": n["up"], "down": n["down"], "total": n["up"] + n["down"],
            "adopted": n["adopted"], "abandoned": n["abandoned"],
            "shown": n["shown"]}
        for c, n in per.items()
    }


def build_component_feedback_section(summary: dict, component: str) -> str:
    """Prompt context for ONE component's verdicts; '' for an unknown one."""
    component = normalize_component(component)
    if not component:
        return ""
    label = COMPONENT_LABELS[component]
    counts = (summary or {}).get(component) or {}
    up = int(counts.get("up") or 0)
    down = int(counts.get("down") or 0)
    if not up and not down:
        return (
            f"FOUNDER VERDICTS on the {label}: none recorded for this app yet. "
            "Work from the verified facts."
        )
    if down > up:
        steer = (
            f"Most past {label}s were rejected: take a noticeably different, "
            "sharper approach from the customer's point of view."
        )
    elif up > down:
        steer = (
            f"Past {label}s mostly landed: keep the same customer-first "
            "quality bar and do not drift toward generic copy."
        )
    else:
        steer = "Verdicts are mixed: weak evidence, do not over-correct."
    behavior = _describe_behavior(counts)
    return (
        f"FOUNDER VERDICTS on the {label} for this app: {up} thumbs up, "
        f"{down} thumbs down. {steer} These verdicts are about the {label} only."
        f"{behavior}"
    )


def _describe_behavior(counts: dict) -> str:
    """One behavior sentence for a prompt section, or '' when there is none."""
    adopted = int((counts or {}).get("adopted") or 0)
    abandoned = int((counts or {}).get("abandoned") or 0)
    shown = int((counts or {}).get("shown") or 0)
    if not adopted and not abandoned and not shown:
        return ""
    return (
        f" Behavior: moved forward with {adopted}, dropped after picking "
        f"{abandoned}, shown but not picked {shown}."
    )


# Transparent feedback weights. These are deliberately small and capped: past
# behavior should inform a recommendation, not permanently bury a template
# because a founder rejected it twice while exploring the library.
FEEDBACK_WEIGHTS = {
    "explicit_template_rejection": -2.0,
    "automatic_template_change": -1.0,
    "template_thumb_down": -1.5,
    "template_thumb_up": 1.0,
}
# Implicit behavior beside the explicit verdicts. Adoption is the strongest
# signal in the loop — the founder picked this item AND moved forward with
# it — so it outranks a thumb up. Abandonment (picked or produced, then
# dropped without proceeding) is a hard negative on par with an explicit
# rejection. A shown-but-not-picked impression is only a soft negative:
# being passed over once is not rejection, but a template that is always
# shown and never chosen is telling the founder something.
BEHAVIOR_WEIGHTS = {
    "adopted": 3.0,
    "abandoned": -2.0,
    "generated": -0.25,
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
        "heavy_script_edits": 0,
        "adoptions": 0,
        "abandonments": 0,
        "impressions": 0,
        "top_reasons": [],
        "selected_template": {
            "template_id": template_id or "",
            "rejections": 0,
            "top_reasons": [],
        },
    }
    reason_counts = {}
    selected_reason_counts = {}
    for row in events or []:
        if not isinstance(row, dict):
            continue
        event = row.get("event") or ""
        # Component thumbs travel only through their own stage, never this
        # shared aggregate. Behavior events DO travel here: an adoption is
        # exactly "this founder moves forward with this kind of thing".
        if event not in EVENTS or event in ("thumb_up", "thumb_down"):
            continue
        reason = row.get("reason") or ""
        row_template_id = str(row.get("template_id") or "")
        is_selected = bool(template_id) and row_template_id == template_id
        summary["total"] += 1
        if event == "template_rejected":
            summary["template_rejections"] += 1
        elif event == "video_regenerated":
            summary["generation_rejections"] += 1
        elif row.get("signal") == "script_edited_heavy":
            summary["heavy_script_edits"] += 1
        elif event == "adopted":
            summary["adoptions"] += 1
        elif event == "abandoned":
            summary["abandonments"] += 1
        elif event == "generated":
            summary["impressions"] += 1
        if reason:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            if is_selected:
                selected_reason_counts[reason] = selected_reason_counts.get(reason, 0) + 1
        if is_selected and event == "template_rejected":
            summary["selected_template"]["rejections"] += 1
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
        "thumb_ups": 0,
        "thumb_downs": 0,
        "adoptions": 0,
        "abandonments": 0,
        "impressions": 0,
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
        elif event in ("thumb_up", "thumb_down"):
            # Only a verdict on the template itself moves its score.
            if normalize_component(row.get("step") or "") != "template":
                continue
            if event == "thumb_up":
                facts["thumb_ups"] += 1
                approval_delta += FEEDBACK_WEIGHTS["template_thumb_up"]
            else:
                facts["thumb_downs"] += 1
                rejection_delta += FEEDBACK_WEIGHTS["template_thumb_down"]
        elif event in ("adopted", "abandoned", "generated"):
            # Only behavior on the template itself moves its score.
            if normalize_component(row.get("step") or "") != "template":
                continue
            if event == "adopted":
                facts["adoptions"] += 1
                approval_delta += BEHAVIOR_WEIGHTS["adopted"]
            elif event == "abandoned":
                facts["abandonments"] += 1
                rejection_delta += BEHAVIOR_WEIGHTS["abandoned"]
            else:
                facts["impressions"] += 1
                rejection_delta += BEHAVIOR_WEIGHTS["generated"]
        else:
            continue
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
        f"Video regenerations: {summary.get('generation_rejections', 0)}.",
        f"Heavy script edits: {summary.get('heavy_script_edits', 0)}.",
    ]
    # Behavior lines are conditional: a zero count carries no information, and
    # every prompt line spends ceiling the strategy budget test guards.
    if summary.get("adoptions"):
        lines.append(f"Moved forward with (adoptions): {summary.get('adoptions')}.")
    if summary.get("abandonments"):
        lines.append(
            f"Dropped after picking (abandonments): {summary.get('abandonments')}.")
    if summary.get("impressions"):
        lines.append(f"Shown but not picked: {summary.get('impressions')}.")
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
            f"{selected.get('rejections', 0)} rejections."
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
