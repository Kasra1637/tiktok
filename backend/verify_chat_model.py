"""
Live chat-model verification: real calls, nothing mocked.

The suite proves the request SHAPE the studio sends; only a real provider
response proves that shape is ACCEPTED. Two facts about the Claude Haiku 5.5
swap cannot be settled by a mocked test, and this script settles both:

  1. Structured output. Every research / angles / plan / script call depends on
     OpenRouter strict json_schema (response_format). Anthropic documents
     structured outputs for Haiku 4.5 and 5.5, but OpenRouter routes support per
     endpoint, so this proves the endpoint the studio actually reaches accepts
     the envelope and returns JSON that satisfies a strict schema.

  2. The temperature question. The studio SENDS a temperature to Claude (0.4 by
     default), because Haiku 5.5 runs adaptive thinking by default and whether a
     non-default temperature is accepted alongside that is undocumented. A
     refusal is survivable — _post_chat drops the field and retries the request
     — but that retry costs a wasted round trip on every call, so it is worth
     knowing which world we are in. This probe sends a temperature and reports
     whether the provider takes it, with the exact follow-up for either answer.

Two cheap text calls by default, plus one vision call with --photo. The key is
read from the environment only, never printed, never stored.

Usage (bash):
    export OPENROUTER_API_KEY="<key never committed anywhere>"
    python backend/verify_chat_model.py
    python backend/verify_chat_model.py --photo ./face.png
"""
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

# A tiny strict schema in exactly the shape every shipped schema uses: all
# properties required, additionalProperties false. If this one is refused, no
# larger schema can succeed either.
PROBE_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean", "description": "true when the schema was followed"},
        "word": {"type": "string", "description": "the single word: ready"},
    },
    "required": ["ok", "word"],
    "additionalProperties": False,
}


def _run(coro):
    return asyncio.run(coro)


def _guard(fn, *args) -> dict:
    """Run one probe, turning any raise into a FAIL row rather than a traceback."""
    try:
        return fn(*args)
    except Exception as e:
        return {"check": getattr(fn, "__name__", "probe"), "model": "",
                "passed": False, "detail": repr(e)}


async def _structured_output(ai_service) -> dict:
    """The studio's real path: _chat_json against a strict schema."""
    out = await ai_service._chat_json(
        system_message="You reply with strict JSON and nothing else.",
        prompt='Return exactly {"ok": true, "word": "ready"}.',
        context="Live verify: structured output",
        json_schema=PROBE_SCHEMA,
        max_tokens=2000,
        attempts=1,
    )
    passed = (
        isinstance(out, dict)
        and out.get("ok") is True
        and out.get("word") == "ready"
    )
    return {"check": "structured output (strict json_schema)",
            "model": ai_service.TEXT_MODEL, "passed": passed, "detail": out}


async def _temperature_probe(ai_service, model: str, temperature: float) -> dict:
    """
    Sent raw, because _temperature_param omits the field by design — the whole
    point is to find out what happens when it IS sent.
    """
    import httpx

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with the single word: ready"}],
        "temperature": temperature,
        "max_tokens": 512,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{ai_service.OPENROUTER_BASE}/chat/completions",
            headers=ai_service._headers(),
            json=payload,
        )
    accepted = resp.status_code == 200
    detail = "accepted"
    if not accepted:
        try:
            body = resp.json()
            detail = body.get("error", {}).get("message") or json.dumps(body)
        except Exception:
            detail = (resp.text or "")[:400]
    return {"check": f"temperature accepted (={temperature})", "model": model,
            "passed": accepted, "status": resp.status_code, "detail": detail[:400]}


async def _vision_probe(ai_service, photo: Path) -> dict:
    out = await ai_service.analyze_image_for_hook(photo, "live-verify")
    passed = isinstance(out, dict) and bool(out.get("hook_summary"))
    return {"check": "vision (image in, JSON out)", "model": ai_service.VISION_MODEL,
            "passed": passed, "detail": out}


def main() -> int:
    ap = argparse.ArgumentParser(description="Live chat-model verification.")
    ap.add_argument("--photo", type=Path,
                    help="optional presenter photo to verify the vision path")
    ap.add_argument("--temperature", type=float, default=0.4,
                    help="temperature to probe for acceptance")
    ap.add_argument("--model", default="",
                    help="model slug to probe (default: the configured TEXT_MODEL)")
    args = ap.parse_args()

    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY is not set. Export it first; it is never "
              "printed or stored.", file=sys.stderr)
        return 2

    import ai_service

    model = args.model or ai_service.TEXT_MODEL
    results = [
        _guard(_run, _structured_output(ai_service)),
        _guard(_run, _temperature_probe(ai_service, model, args.temperature)),
    ]
    if args.photo:
        results.append(_guard(_run, _vision_probe(ai_service, args.photo)))

    print("\n================ RESULTS ================", flush=True)
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        print(f"[{mark}] {r['check']}  ({r['model']})", flush=True)
        if not r["passed"] or r["check"].startswith("temperature"):
            print(f"        {json.dumps(r.get('detail'))[:400]}", flush=True)

    temp = next((r for r in results if r["check"].startswith("temperature")), None)
    print("\n---------------- next step ----------------", flush=True)
    if temp and temp["passed"]:
        print("temperature WAS accepted. The retry is no longer needed: remove", flush=True)
        print('"claude" from _TEMPERATURE_FALLBACK_PREFIXES in ai_service.py so', flush=True)
        print("the field is simply sent.", flush=True)
    elif temp:
        print("temperature was REFUSED. _post_chat is handling it — the field is", flush=True)
        print('dropped and the call retried. Keep "claude" in', flush=True)
        print("_TEMPERATURE_FALLBACK_PREFIXES. To avoid the wasted first request,", flush=True)
        print('also add "claude" to _TEMPERATURE_OMITTED_PREFIXES.', flush=True)

    # The temperature verdict is informational either way; only the checks the
    # studio depends on decide the exit code.
    required = [r for r in results if not r["check"].startswith("temperature")]
    return 1 if any(not r["passed"] for r in required) else 0


if __name__ == "__main__":
    raise SystemExit(main())
