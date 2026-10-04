"""
Live render verification: one real render per model, end to end.
This is the check no mocked test can perform. The suite proves the gates refuse
correctly; only a real provider response proves the two-section prompt produces
a real hook-then-middle clip, that the character reference survives as the
presenter on BOTH models, and that H3 Max accepts what we send it (768p, no
generate_audio) instead of 400ing after the request is committed.

Runs: exactly two video renders (one per model) plus a few text calls.
Nothing here is mocked. Run it, then WATCH both clips: the script asserts file
validity, but identity likeness, the phone-reach ending, and the absence of a
generated demo/CTA need human eyes.

Usage (PowerShell):
    $env:OPENROUTER_API_KEY = "<key never committed anywhere>"
    python backend/verify_live_renders.py --photo ./my-face.png --out ./live-clips

The key is read from the environment only, never printed, never stored.
"""
import argparse
import asyncio
import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

USER = "live-verify"
POLL_EVERY_SECONDS = 20


def _run(coro):
    return asyncio.run(coro)


def _mp4_report(path: Path) -> dict:
    """Validity checks that need no tools: real MP4 structure, non-trivial size."""
    data = path.read_bytes()
    boxes = set()
    i = 0
    while i + 8 <= len(data) and len(boxes) < 20:
        size = int.from_bytes(data[i:i + 4], "big")
        boxes.add(data[i + 4:i + 8].decode("latin1", "replace"))
        if size < 8:
            break
        i += size
    report = {
        "bytes": len(data),
        "has_ftyp": "ftyp" in boxes,
        "has_moov": data.find(b"moov") != -1,
        "ffprobe": None,
    }
    if shutil.which("ffprobe"):
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_format", "-show_streams", str(path)],
                capture_output=True, text=True, timeout=60,
            )
            info = json.loads(out.stdout or "{}")
            streams = info.get("streams", [])
            video = next((s for s in streams if s.get("codec_type") == "video"), {})
            report["ffprobe"] = {
                "duration": info.get("format", {}).get("duration"),
                "width": video.get("width"),
                "height": video.get("height"),
                "codec": video.get("codec_name"),
            }
        except Exception as e:  # ffprobe is a bonus, not the verdict
            report["ffprobe"] = {"error": str(e)[:120]}
    return report


async def _one_render(api, photo: Path, out_dir: Path, model_key: str,
                      timeout_s: int, poll_every: int) -> dict:
    from models import (
        BrandProfileCreateRequest, ApproveAppProfileRequest,
        CreateStudioProjectRequest, GeneratePlanRequest, StudioGenerationRequest,
        now_iso,
    )
    tag = model_key.replace("-", "_")
    print(f"\n=== {model_key}: profile ===", flush=True)
    profile = await api.create_brand(payload=BrandProfileCreateRequest(
        brand_name=f"Live Verify {model_key}",
        brand_description="Shift logging for healthcare workers.",
        app_category="Productivity",
        core_features=["One-tap shift logging"],
        usage_moments=["Clocking on and off between shifts"],
        claims_approved=["Logs a shift in one tap"],
        claims_banned=["cures burnout"],
    ), user_id=USER)
    await api.approve_app_profile(
        profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=USER)

    templates = await api.list_templates(user_id=USER)
    usable = [t for t in templates["templates"]
              if t.get("is_usable") and "character_reference" in (t.get("required_assets") or [])]
    if not usable:
        raise RuntimeError("no usable face-anchored template in the library")
    template = usable[0]
    print(f"template: {template['name']} (default {template.get('default_duration')}s)", flush=True)

    print(f"=== {model_key}: project + photo ===", flush=True)
    project = await api.create_studio_project(payload=CreateStudioProjectRequest(
        brand_profile_id=profile["id"],
        template_id=template["id"],
        objective="demonstrate_feature",
    ), user_id=USER)

    asset_dir = Path(tempfile.mkdtemp(prefix="live-verify-assets-"))
    face = asset_dir / f"face-{tag}{photo.suffix.lower()}"
    shutil.copy(photo, face)
    asset_id = str(uuid.uuid4())
    now = now_iso()
    await api._execute(
        "INSERT INTO assets (id, brand_profile_id, kind, name, file_path, label,"
        " created_at, updated_at, user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (asset_id, profile["id"], "character_reference", "Founder face",
         str(face), "Founder face", now, now, USER))
    await api._execute(
        "UPDATE studio_projects SET assets = ? WHERE id = ?",
        (json.dumps([{"asset_id": asset_id, "kind": "character_reference",
                      "label": "Founder face", "file_path": str(face)}]),
         project["id"]))

    print(f"=== {model_key}: plan (live text call) ===", flush=True)
    planned = await api.generate_plan(
        project_id=project["id"], payload=GeneratePlanRequest(), user_id=USER)
    print(f"hook: {planned.get('hook_line')}", flush=True)

    print(f"=== {model_key}: ready + strategy (live text call) ===", flush=True)
    await api.mark_project_ready(project_id=project["id"], user_id=USER)
    import server
    strategy = await api.generate_project_strategy(
        project_id=project["id"], payload=server.GenerateStrategyRequest(), user_id=USER)
    assert strategy.get("strategy", {}).get("hook_line"), "strategy came back without a hook line"

    print(f"=== {model_key}: SUBMIT (paid) ===", flush=True)
    gen = await api.submit_project_generation(
        project_id=project["id"],
        payload=StudioGenerationRequest(
            model=model_key, idempotency_key=f"live-verify-{tag}-{uuid.uuid4().hex[:8]}"),
        user_id=USER)
    print(f"generation {gen['id']} submitted at {gen.get('requested_duration')}s", flush=True)

    deadline = time.time() + timeout_s
    while True:
        await asyncio.sleep(poll_every)
        row = await api._fetch_one("SELECT * FROM generations WHERE id = ?", (gen["id"],))
        status = row.get("status")
        if status in ("submitted", "generating"):
            if time.time() > deadline:
                raise TimeoutError(
                    f"{model_key} still '{status}' after {timeout_s}s; "
                    f"generation {gen['id']} left polling in history")
            print(f"  ... {status} ({int(deadline - time.time())}s left)", flush=True)
            await api.poll_generation(gen["id"], USER)
            continue
        if status != "completed":
            raise RuntimeError(
                f"{model_key} ended '{status}': {(row.get('error') or '')[:300]}")
        final = await api.get_generation(gen["id"], USER)
        break

    import pipeline
    local = pipeline.VIDEOS_DIR / f"{gen['id']}.mp4"
    if not local.is_file():
        # Fall back to whatever the row points at.
        raise RuntimeError(
            f"{model_key} completed but no local clip found; "
            f"video_url={final.get('video_url')!r} r2_url={final.get('r2_url')!r} "
            f"storage_error={final.get('storage_error')!r}")
    dest = out_dir / f"live-{tag}.mp4"
    shutil.copy(local, dest)
    report = _mp4_report(dest)
    print(f"=== {model_key}: clip {dest} ({report['bytes'] / 1e6:.1f} MB) ===", flush=True)
    print(json.dumps(report, indent=2), flush=True)
    assert report["bytes"] > 100_000, "clip suspiciously small"
    assert report["has_ftyp"] and report["has_moov"], "not a well-formed MP4"
    return {
        "model": model_key,
        "generation_id": gen["id"],
        "storage_error": final.get("storage_error"),
        "file": str(dest),
        "report": report,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Live two-model render verification.")
    ap.add_argument("--photo", required=True, type=Path,
                    help="front-facing photo of the presenter (png/jpg)")
    ap.add_argument("--out", type=Path, default=Path("live-clips"),
                    help="where to copy the finished clips")
    ap.add_argument("--models", default="minimax-h3,minimax-h3-max",
                    help="comma-separated model keys to verify")
    ap.add_argument("--timeout-min", type=float, default=25,
                    help="max minutes to poll per model")
    ap.add_argument("--poll-every", type=int, default=POLL_EVERY_SECONDS)
    args = ap.parse_args()

    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY is not set. Export it first; it is never printed or stored.",
              file=sys.stderr)
        return 2
    if not args.photo.is_file():
        print(f"photo not found: {args.photo}", file=sys.stderr)
        return 2

    tmpdir = tempfile.mkdtemp(prefix="live-verify-db-")
    os.environ["TURSO_DATABASE_URL"] = ""
    os.environ["CLERK_JWKS_URL"] = ""
    if "server" in sys.modules:
        del sys.modules["server"]
    server = importlib.import_module("server")
    server.DB_PATH = Path(tmpdir) / "live.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _run(server.init_db())

    args.out.mkdir(parents=True, exist_ok=True)
    results = []
    failed = False
    for key in [m.strip() for m in args.models.split(",") if m.strip()]:
        try:
            results.append(_run(_one_render(
                server, args.photo, args.out, key,
                int(args.timeout_min * 60), args.poll_every)))
        except Exception as e:
            failed = True
            print(f"\n!!! {key} FAILED: {e}", flush=True)
    print("\n================ SUMMARY ================", flush=True)
    for r in results:
        print(f"{r['model']}: {r['file']} "
              f"storage_error={r['storage_error']!r}", flush=True)
    if results:
        print("\nHUMAN CHECKLIST -- watch each clip and confirm:", flush=True)
        print(" 1. the presenter matches --photo (same person, same clothes ok to differ);", flush=True)
        print(" 2. exactly two sections: hook, then a middle that STOPS where you would", flush=True)
        print("    reach for your phone -- no generated demo, no generated CTA;", flush=True)
        print(" 3. H3 Max clip is 768p-ish and H3 is 2K-ish (see ffprobe above);", flush=True)
        print(" 4. any storage_error above is understood before relying on the clip.", flush=True)
    sys.modules.pop("server", None)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
