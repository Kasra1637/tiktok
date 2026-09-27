"""
Internal analytics.

Pure functions over rows already fetched from the database, so every metric is
unit-testable without a database and the arithmetic cannot drift between the
API and the UI.

Honesty rules encoded here:
- Cost is only ever summed from generations where a provider actually
  reported one. Runs where cost_source is 'unavailable' are counted
  separately rather than silently treated as free.
- TikTok performance is operator-entered. It is never labelled verified and
  never presented as platform data.
"""
from collections import Counter
from datetime import datetime, timezone
from typing import Iterable, Optional

# Videos are only counted once they are usable. A queued or in-flight
# generation is work in progress, not an output.
TERMINAL_STATES = ("completed", "failed", "archived")


def _elapsed_seconds(start: str, end: str) -> Optional[float]:
    """
    Seconds between two ISO timestamps, or None if either is unusable.

    Timestamps are stored as ISO strings, so they must be parsed before
    subtracting; strings would either raise or compare lexicographically.
    """
    if not start or not end:
        return None
    try:
        a = datetime.fromisoformat(str(start))
        b = datetime.fromisoformat(str(end))
    except (TypeError, ValueError):
        return None
    if a.tzinfo is None:
        a = a.replace(tzinfo=timezone.utc)
    if b.tzinfo is None:
        b = b.replace(tzinfo=timezone.utc)
    delta = (b - a).total_seconds()
    return delta if delta >= 0 else None


def _cost(generations: Iterable[dict]) -> dict:
    """
    Split spend into what is known and what is unpriced.

    Returning a single sum would be dishonest: a run whose provider response
    carried no cost would pull the average down as if it were free.
    """
    total = 0.0
    priced = 0
    unpriced = 0
    for g in generations or []:
        value = g.get("cost_usd")
        if isinstance(value, (int, float)):
            total += float(value)
            priced += 1
        else:
            unpriced += 1
    return {
        "total_usd": round(total, 4),
        "priced_runs": priced,
        "unpriced_runs": unpriced,
        "complete": unpriced == 0,
    }


def generation_metrics(generations: Iterable[dict]) -> dict:
    """
    Core counts and rates for a set of generations.

    The success rate counts only finished attempts, because a generation still
    in flight would otherwise drag the rate down and look like a failure.
    """
    rows = list(generations or [])
    total = len(rows)

    by_status = Counter(r.get("status") or "unknown" for r in rows)
    completed = by_status.get("completed", 0)
    failed = by_status.get("failed", 0)
    in_flight = by_status.get("submitted", 0) + by_status.get("generating", 0)
    finished = completed + failed

    durations = [
        elapsed
        for elapsed in (
            _elapsed_seconds(r.get("started_at"), r.get("completed_at"))
            for r in rows
        )
        if elapsed is not None
    ]

    return {
        "videos_created": total,
        "completed": completed,
        "failed": failed,
        "in_flight": in_flight,
        "archived": by_status.get("archived", 0),
        "success_rate": round(completed / finished, 4) if finished else None,
        "failure_rate": round(failed / finished, 4) if finished else None,
        "avg_generation_seconds": round(sum(durations) / len(durations), 1) if durations else None,
        **_cost(rows),
    }


def by_dimension(
    generations: Iterable[dict], field: str, label_map: Optional[dict] = None
) -> list:
    """
    Group a countable dimension (model, template, app) with its own totals.

    label_map translates a bucket key into something a human recognises, e.g.
    a profile id into an app name. It is applied here rather than patched on
    afterwards, because the grouping step is where the key is known.

    Ordering is by volume so the most-used items surface first, which is what
    the "most-used content angle / audience / template" questions need.
    """
    buckets: dict = {}
    for row in generations or []:
        key = row.get(field)
        if key is None or key == "":
            key = "(none)"
        bucket = buckets.setdefault(key, [])
        bucket.append(row)

    out = []
    for key, rows in buckets.items():
        label = (label_map or {}).get(key, key)
        entry = {
            "key": key,
            "label": label,
            "count": len(rows),
        }
        entry.update(generation_metrics(rows))
        out.append(entry)
    out.sort(key=lambda e: (-e["count"], str(e["label"])))
    return out


def regeneration_metrics(generations: Iterable[dict]) -> dict:
    """
    How much work is being redone.

    A generation with attempt > 1 is a retry of a failed segment; a row with a
    parent is a deliberate variation. Both count as rework, and the spec asks
    for them separately.
    """
    rows = list(generations or [])
    retries = [r for r in rows if (r.get("attempt") or 1) > 1]
    variations = [r for r in rows if r.get("parent_generation_id")]
    children = Counter(r.get("parent_generation_id") for r in variations)
    return {
        "regenerated": len(retries),
        "variations": len(variations),
        "parents_with_variations": len([k for k, n in children.items() if n]),
        "max_variations_of_one_video": max(children.values()) if children else 0,
        "failed_then_recovered": len([
            r for r in retries if r.get("status") == "completed"
        ]),
    }


def manual_performance_summary(entries: Iterable[dict]) -> dict:
    """
    Summarise operator-entered performance.

    Always reports source='manual' and verified=False. This app never connects
    to a platform, so nothing here can honestly be called verified.
    """
    rows = list(entries or [])
    def total(field):
        values = [r.get(field) for r in rows if isinstance(r.get(field), (int, float))]
        return sum(values)

    successful = [r for r in rows if r.get("outcome") == "successful"]
    unsuccessful = [r for r in rows if r.get("outcome") == "unsuccessful"]
    return {
        "source": "manual",
        "verified": False,
        "entries": len(rows),
        "views": total("views"),
        "likes": total("likes"),
        "comments": total("comments"),
        "shares": total("shares"),
        "saves": total("saves"),
        "marked_successful": len(successful),
        "marked_unsuccessful": len(unsuccessful),
        "avg_views": round(total("views") / len(rows), 1) if rows else None,
    }


def template_usage(templates: Iterable[dict], generations: Iterable[dict]) -> list:
    """
    Template selection, annotated with outcome and cost.

    Sorting by success rate would rank a template used twice at 100% above one
    used fifty times at 80%, which is misleading, so volume leads.
    """
    by_id = {t.get("id"): t for t in (templates or [])}
    buckets: dict = {}
    for row in generations or []:
        tid = row.get("template_id") or "(none)"
        buckets.setdefault(tid, []).append(row)

    out = []
    for tid, rows in buckets.items():
        template = by_id.get(tid) or {}
        entry = {
            "template_id": tid,
            "name": template.get("name") or "(deleted template)",
            "category": template.get("category") or "other",
            "origin": template.get("origin") or "unknown",
            "used": len(rows),
        }
        entry.update(generation_metrics(rows))
        out.append(entry)
    out.sort(key=lambda e: (-e["used"], e["name"]))
    return out


def feedback_summary(events: Iterable[dict]) -> dict:
    """
    What happened, and why.

    Two independent breakdowns, kept apart on purpose:

    - by_event / top_signals count factual triggers. Every regenerate is
      recorded, so this says how often rework happens.
    - top_reasons counts only the explicit judgments a founder supplied. Since
      those are optional, this is usually smaller, and that is honest: it is
      the subset of rework someone bothered to explain.

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


def build_report(
    generations: Iterable[dict],
    templates: Iterable[dict] = (),
    performance: Iterable[dict] = (),
    feedback: Iterable[dict] = (),
    profiles: Iterable[dict] = (),
    project_lookup: Optional[dict] = None,
) -> dict:
    """
    The full internal analytics payload.
    """
    generations = list(generations or [])
    project_lookup = project_lookup or {}
    profile_names = {p.get("id"): p.get("brand_name") for p in (profiles or [])}

    # Angle and audience live on the project, so they are joined in here.
    enriched = []
    for row in generations:
        item = dict(row)
        project = project_lookup.get(item.get("studio_project_id")) or {}
        item["objective"] = project.get("objective") or item.get("objective")
        item["audience"] = project.get("audience")
        angle_id = project.get("content_angle_id")
        item["content_angle_id"] = angle_id
        item["app_name"] = profile_names.get(item.get("brand_profile_id"))
        enriched.append(item)

    return {
        "totals": generation_metrics(enriched),
        "by_model": by_dimension(enriched, "model"),
        "by_app": by_dimension(enriched, "brand_profile_id", label_map=profile_names),
        "by_template": template_usage(templates, enriched),
        "by_objective": by_dimension(enriched, "objective"),
        "by_audience": by_dimension(enriched, "audience"),
        "by_angle": by_dimension(enriched, "content_angle_id"),
        "rework": regeneration_metrics(enriched),
        "performance": manual_performance_summary(performance),
        "feedback": feedback_summary(feedback),
    }
