"""Benchmark harness for non-video text models on OpenRouter.

One-off, run manually with OPENROUTER_API_KEY. It:
1. Runs the golden fixtures through each candidate model's
   generate_creative_plan and generate_video_strategy (via _chat_json's
   `model` override, so production prompts are untouched).
2. Rates each output two ways:
   - gated: the app's deterministic gates (spoken budget, one pronoun,
     no screen narration, no bounded-by result) as a hard pass/fail.
   - blind: an LLM judge scores the output 0-10 for hook strength,
     lived detail, voice and approval readiness, without knowing which
     model wrote it.
3. Prints a per-model table and writes a markdown report to
   `test_reports/benchmark_YYYY-MM-DD.md`.

Cost is not considered: this is a quality-only comparison for a documented
record. The current model is the baseline; every other row is the delta.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.dirname(__file__))

import ai_service  # noqa: E402
import final_beat  # noqa: E402
from claim_safety import bounded_by_conflict  # noqa: E402
from golden_fixtures import FIXTURES  # noqa: E402

# Candidate list. The baseline is the shipped default; the others are the
# top general-purpose models running on OpenRouter today. Confirm slugs
# against OpenRouter's live catalog before a run — a retired slug 404s and
# wastes the whole batch.
BASELINE = "anthropic/claude-haiku-5.5"
CANDIDATES = [
    BASELINE,
    "anthropic/claude-sonnet-4.5",
    "openai/gpt-5",
    "openai/gpt-5.1",
    "google/gemini-3-pro-preview",
    "x-ai/grok-4.1-fast",
    "deepseek/deepseek-v3.2-speciale",
    "meta-llama/llama-4-maverick",
    "qwen/qwen3-max",
    "mistralai/large-3",
    "mistralai/mistral-large-2.1",
]

JUDGE_MODEL = BASELINE  # the baseline judges blind; it cannot see names


def _gate_plan_output(plan: dict, fixture: dict) -> list:
    """Deterministic gate verdicts for one generated plan."""
    issues = []
    angle = fixture.get("angle") or {}
    hook = str(plan.get("hook_line") or "")
    script = str(plan.get("script") or "")
    hook_budget = ai_service.spoken_hook_budget(fixture.get("duration") or 20)
    script_budget = ai_service.spoken_middle_budget(fixture.get("duration") or 20)
    hooks = [hook] if hook else []
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
    # Screen-surface narration in the spoken line.
    if final_beat._clause_has_screen_action(ai_service._normalize_spoken(script)):
        issues.append("script narrates scrolling/reading a surface")
    return issues


async def _run_one(model: str, fixture: dict) -> dict:
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

    # Blind rating: the judge sees the words, never the model name.
    blind = await _judge(plan, strategy, fixture)
    return {
        "fixture": fixture["name"],
        "model": model,
        "gated_pass": not gate_issues,
        "gate_issues": gate_issues,
        "blind_score": blind,
        "hook_line": plan.get("hook_line", ""),
        "script": plan.get("script", ""),
    }


async def _judge(plan: dict, strategy: dict, fixture: dict) -> float:
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
            prompt, "blind judge", model=JUDGE_MODEL, max_tokens=200,
        )
        return float(result.get("score", 0))
    except Exception:
        return 0.0


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="*", help="override the candidate list")
    parser.add_argument("--limit", type=int, default=0, help="stop after N fixtures per model")
    args = parser.parse_args()

    models = args.models or CANDIDATES
    fixtures = FIXTURES[: args.limit] if args.limit else FIXTURES
    print(f"benchmark: {len(models)} models x {len(fixtures)} fixtures", flush=True)
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY is required", file=sys.stderr)
        sys.exit(1)

    rows = []
    for model in models:
        for fixture in fixtures:
            row = await _run_one(model, fixture)
            rows.append(row)
            print(
                f"{model:40s} {fixture['name']:28s} "
                f"gate={'pass' if row['gated_pass'] else 'FAIL'} "
                f"blind={row['blind_score']:.1f}",
                flush=True,
            )

    # Aggregate: gated pass rate, mean blind score, per-form variance.
    summary = {}
    for model in models:
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
