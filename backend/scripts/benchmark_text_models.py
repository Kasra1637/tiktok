"""Benchmark harness for non-video text models on OpenRouter.

One-off, run manually with OPENROUTER_API_KEY. It:
1. Discovers the current general-purpose text models from OpenRouter's live
   catalog (GET /api/v1/models — no preset list), filtering out video, image,
   embedding and moderation models, one per family.
2. Runs the golden fixtures through each candidate model's
   generate_creative_plan and generate_video_strategy (via _chat_json's
   `model` override, so production prompts are untouched).
3. Rates each output two ways:
   - gated: the app's deterministic gates (spoken budget, one pronoun,
     no screen narration, no bounded-by result) as a hard pass/fail.
   - blind: an LLM judge scores the output 0-10 for hook strength,
     lived detail, voice and approval readiness, without knowing which
     model wrote it. The judge is NOT in the candidate set.
4. Prints a per-model table and writes a markdown report to
   `test_reports/benchmark_YYYY-MM-DD.md`.

Cost is not considered: this is a quality-only comparison for a documented
record. The current model is the baseline; every other row is the delta.

Corrects two flaws in the earlier harness:
- The preset CANDIDATES list was sample-only and violated the "no preset
  list" rule. It is now discovered live from the catalog.
- JUDGE_MODEL = BASELINE let the baseline judge its own outputs, inflating
  its blind scores. The judge is now a fixed model outside the candidate
  set (or a candidate explicitly excluded from the set before the run).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import datetime
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import ai_service  # noqa: E402
import final_beat  # noqa: E402
from claim_safety import bounded_by_conflict  # noqa: E402
from golden_fixtures import FIXTURES  # noqa: E402

BASELINE = "anthropic/claude-haiku-5.5"

EXCLUDED_KINDS = ("video", "image", "embedding", "moderation")
FAMILY_PREFIXES = (
    "anthropic", "openai", "google", "x-ai", "deepseek", "qwen",
    "mistralai", "meta-llama", "microsoft", "z-ai",
)
FAMILY_ORDER = {f: i for i, f in enumerate(FAMILY_PREFIXES)}


def _family_of(model_id: str) -> str:
    return (model_id or "").split("/", 1)[0].lower() if "/" in (model_id or "") else ""


def discover_candidates(baseline: str = BASELINE, limit: int = 12) -> list:
    """Live discovery from OpenRouter's catalog — no preset list.

    GET /api/v1/models, filter out video/image/embedding/moderation, keep
    currently servable general-purpose text models, one per family.
    """
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is required for live discovery")
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    models = data.get("data") or []

    seen = {}
    for entry in models:
        model_id = (entry.get("id") or "").strip()
        if not model_id:
            continue
        architecture = entry.get("architecture") or {}
        modality = (architecture.get("modality") or "").lower()
        if any(kind in modality for kind in EXCLUDED_KINDS):
            continue
        family = _family_of(model_id)
        if family not in FAMILY_ORDER:
            continue
        current = seen.get(family)
        if current is None or len(model_id) > len(current):
            seen[family] = model_id

    candidates = list(seen.values())
    candidates = [baseline] + [m for m in candidates if m != baseline]
    candidates.sort(
        key=lambda m: (0 if m == baseline else 1, FAMILY_ORDER.get(_family_of(m), 99), m)
    )
    return candidates[:limit]


def pick_judge(candidates: list, preferred: str = "openai/gpt-5") -> str:
    """A fixed judge that is NOT in the candidate set."""
    base = set(candidates) | {BASELINE}
    if preferred not in base:
        return preferred
    for fallback in (
        "openai/gpt-4.1", "google/gemini-2.0-flash-001", "mistralai/large-3",
        "meta-llama/llama-3.3-70b-instruct",
    ):
        if fallback not in base:
            return fallback
    raise RuntimeError("No judge outside the candidate set — pass --judge explicitly")


def _gate_plan_output(plan: dict, fixture: dict) -> list:
    """Deterministic gate verdicts for one generated plan."""
    issues = []
    angle = fixture.get("angle") or {}
    hook = str(plan.get("hook_line") or "")
    script = str(plan.get("script") or "")
    hook_budget = ai_service.spoken_hook_budget(fixture.get("duration") or 20)
    script_budget = ai_service.spoken_middle_budget(fixture.get("duration") or 20)
    issues += ai_service._generated_spoken_issues(
        hook, script, hook_budget, script_budget,
        allows_question=ai_service._plan_requests_question_format(
            fixture.get("template"), None) or ai_service._angle_invites_question(angle),
        claims_to_respect=list(angle.get("claims_to_respect") or []),
    )
    if not hook:
        issues.append("hook_line is empty")
    if ai_service.hook_form_of(hook) == "question" and not ai_service._angle_invites_question(angle):
        issues.append("question hook without a self-ask problem")
    if final_beat._clause_has_screen_action(ai_service._normalize_spoken(script)):
        issues.append("script narrates scrolling/reading a surface")
    return issues


async def _run_one(model: str, fixture: dict, judge_model: str) -> dict:
    """One fixture through one model's plan + strategy, with both ratings."""
    original = ai_service.TEXT_MODEL
    ai_service.TEXT_MODEL = model
    try:
        plan = await ai_service.generate_creative_plan(
            fixture["profile"], fixture["template"],
            angle=fixture.get("angle"), duration_seconds=fixture.get("duration") or 20,
            camera_setup=fixture.get("camera") or "handheld",
        )
        strategy = await ai_service.generate_video_strategy(
            fixture["profile"], fixture["template"],
            angle=fixture.get("angle"), hook_seconds=3,
            total_duration=fixture.get("duration") or 20,
            camera_setup=fixture.get("camera") or "handheld",
        )
    finally:
        ai_service.TEXT_MODEL = original
    gate_issues = _gate_plan_output(plan, fixture)

    blind = await _judge(plan, strategy, fixture, judge_model)
    return {
        "fixture": fixture["name"],
        "model": model,
        "gated_pass": not gate_issues,
        "gate_issues": gate_issues,
        "blind_score": blind,
        "hook_line": plan.get("hook_line", ""),
        "script": plan.get("script", ""),
    }


async def _judge(plan: dict, strategy: dict, fixture: dict, judge_model: str) -> float:
    """LLM-as-judge 0-10 for hook strength, lived detail, voice, approval readiness."""
    prompt = (
        "You are a founder reviewing a TikTok hook script for their app. "
        "Rate this plan 0 (unusable) to 10 (would upload today).\n\n"
        f"HOOK: {plan.get('hook_line')}\n"
        f"SCRIPT: {plan.get('script')}\n"
        f"ANGLE: {fixture.get('angle', {}).get('label')}\n"
        f"PROBLEM: {fixture.get('angle', {}).get('user_problem')}\n\n"
        "Score on: hook strength (stops the scroll), lived detail (one "
        "concrete moment), voice (spoken, not written), and approval "
        "readiness (would you render this unchanged?). "
        "Reply with ONLY a JSON object: {\"score\": <number>, "
        "\"hook\": <0-10>, \"voice\": <0-10>, \"approval\": <0-10>}"
    )
    try:
        result = await ai_service._chat_json(
            "Rate founder scripts on a strict 0-10 scale.",
            prompt, "blind judge", model=judge_model, max_tokens=200,
        )
        return float(result.get("score", 0))
    except Exception:
        return 0.0


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="stop after N fixtures per model")
    parser.add_argument("--judge", help="explicit judge model (must be outside the candidate set)")
    parser.add_argument("--baseline", default=BASELINE)
    args = parser.parse_args()

    fixtures = FIXTURES[: args.limit] if args.limit else FIXTURES
    candidates = discover_candidates(baseline=args.baseline)
    judge = args.judge or pick_judge(candidates)
    if judge in set(candidates) | {BASELINE}:
        print(f"judge {judge} must be outside the candidate set", file=sys.stderr)
        sys.exit(1)

    print(f"baseline: {BASELINE}", flush=True)
    print(f"candidates ({len(candidates)}): {candidates}", flush=True)
    print(f"judge (not a candidate): {judge}", flush=True)
    print(f"fixtures: {len(fixtures)}", flush=True)
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY is required", file=sys.stderr)
        sys.exit(1)

    rows = []
    for model in candidates:
        for fixture in fixtures:
            row = await _run_one(model, fixture, judge)
            rows.append(row)
            print(
                f"{model:40s} {fixture['name']:28s} "
                f"gate={'pass' if row['gated_pass'] else 'FAIL'} "
                f"blind={row['blind_score']:.1f}",
                flush=True,
            )

    summary = {}
    for model in candidates:
        mine = [r for r in rows if r["model"] == model]
        summary[model] = {
            "n": len(mine),
            "gated_pass_rate": sum(1 for r in mine if r["gated_pass"]) / max(len(mine), 1),
            "mean_blind": sum(r["blind_score"] for r in mine) / max(len(mine), 1),
            "baseline": model == BASELINE,
        }
    ranked = sorted(summary.items(), key=lambda kv: (kv[1]["gated_pass_rate"], kv[1]["mean_blind"]), reverse=True)

    today = datetime.date.today().isoformat()
    out = [f"# Text model benchmark — {today}", ""]
    out.append(f"Baseline: {BASELINE}  ·  Judge (not a candidate): {judge}  ·  Candidates: discovered live from OpenRouter (no preset list)")
    out.append("")
    out.append("| model | gated pass | mean blind (0-10) | baseline |")
    out.append("|---|---|---|---|")
    for model, s in ranked:
        out.append(
            f"| {model} | {s['gated_pass_rate']:.0%} ({s['n']}) "
            f"| {s['mean_blind']:.1f} | {'yes' if s['baseline'] else ''} |"
        )
    out.append("")
    out.append("## Failures (gate)")
    for r in rows:
        if not r["gated_pass"]:
            out.append(f"- {r['model']} / {r['fixture']}: {'; '.join(r['gate_issues'])}")

    path = os.path.join("test_reports", f"benchmark_{today}.md")
    os.makedirs("test_reports", exist_ok=True)
    with open(path, "w") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"\nreport: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
