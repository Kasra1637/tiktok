"""
Modal serverless worker: downloads TikTok videos and extracts hook frames.

WHY THIS EXISTS
----------------
Render's free web service is capped at 512MB RAM, shared with Python,
Uvicorn, and the DB connection. Downloading a TikTok video (yt-dlp) and
decoding it into still frames (ffmpeg) can spike well beyond what's left in
that budget, causing Render to OOM-kill and restart the whole instance.

This file moves ONLY that memory-heavy step into its own Modal container,
which can be given a proper RAM allocation (2GB here) and is billed by the
second it actually runs — everything else about the app (the web API, the
database, image/video generation, auth) stays on Render exactly as it is.

Render's backend calls this over plain HTTPS and gets back the frames (and
the source video) as base64, then writes them to its own local disk exactly
like it used to — no other code in the app needs to change.

DEPLOYING THIS FILE (do this once, and again whenever you edit it)
--------------------------------------------------------------------
1. pip install modal
2. modal setup                       # first time only — opens a browser to
                                      # log in / link your Modal account
3. Choose a shared secret value (any random string) — this is what proves a
   request to this endpoint actually came from your Render backend, e.g.:
       openssl rand -hex 24
   Set it as MODAL_SHARED_SECRET when deploying so it's baked into this app's
   environment. You have two options:
     a) `modal secret create hookforge-shared-secret MODAL_SHARED_SECRET=<value>`
        then reference it in the app below (already wired via
        `secrets=[modal.Secret.from_name("hookforge-shared-secret")]`), OR
     b) simplest: just hardcode-compare against an env var you export
        locally before deploying: `MODAL_SHARED_SECRET=<value> modal deploy backend/modal_worker.py`
        (Modal bakes literal env vars referenced this way into the deploy).
4. modal deploy backend/modal_worker.py
5. Modal prints a URL like:
       https://<your-workspace>--hookforge-frame-extractor-extract.modal.run
   Set that as MODAL_FRAME_EXTRACTOR_URL in Render's environment variables,
   and set MODAL_SHARED_SECRET there too (same value as step 3).
6. Redeploy the Render service. Frame extraction now runs on Modal; if
   MODAL_FRAME_EXTRACTOR_URL isn't set, the app transparently falls back to
   running yt-dlp/ffmpeg locally (the original behavior), so this is safe to
   leave unconfigured in local dev.
"""
import base64
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import modal

app = modal.App("hookforge-frame-extractor")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install("yt-dlp", "httpx", "fastapi[standard]")
)

# Simple shared-secret check — see deployment step 3 above. Falls back to an
# empty string (no auth) only if you never set one, which is not recommended
# for a public endpoint.
SHARED_SECRET = os.environ.get("MODAL_SHARED_SECRET", "")


def _run(cmd: list, timeout: int = 100):
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return proc.returncode, proc.stdout.decode(errors="ignore"), proc.stderr.decode(errors="ignore")


@app.function(image=image, timeout=180, memory=2048, secrets=[modal.Secret.from_name("hookforge-shared-secret")])
@modal.fastapi_endpoint(method="POST")
def extract(payload: dict):
    """
    Request body:
        {
            "tiktok_url": str,               # required
            "direct_video_url": str,         # optional, tried first if present
            "num_frames": int,               # default 8
            "duration": float,               # default 3.0 (seconds)
            "secret": str                    # must match MODAL_SHARED_SECRET
        }

    Response body:
        {
            "frames": [{"filename": "frame_001.jpg", "data_b64": "..."}, ...],
            "video_b64": "..."               # the full downloaded video
        }
    """
    from fastapi import HTTPException

    if SHARED_SECRET and payload.get("secret") != SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Invalid shared secret.")

    tiktok_url = (payload.get("tiktok_url") or "").strip()
    direct_video_url = (payload.get("direct_video_url") or "").strip()
    num_frames = int(payload.get("num_frames") or 8)
    duration = float(payload.get("duration") or 3.0)
    if not tiktok_url:
        raise HTTPException(status_code=400, detail="tiktok_url is required.")

    with tempfile.TemporaryDirectory() as tmp:
        video_path = Path(tmp) / "video.mp4"
        downloaded = False

        # Try the direct CDN URL first (faster, no yt-dlp needed) — same
        # approach as the original Render-side download_video().
        if direct_video_url:
            try:
                import httpx
                with httpx.Client(timeout=60, follow_redirects=True) as client:
                    with client.stream("GET", direct_video_url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Referer": "https://www.tiktok.com/",
                    }) as resp:
                        if resp.status_code == 200:
                            with open(video_path, "wb") as f:
                                for chunk in resp.iter_bytes(chunk_size=262144):
                                    f.write(chunk)
                            if video_path.exists() and video_path.stat().st_size > 1000:
                                downloaded = True
            except Exception:
                downloaded = False

        if not downloaded:
            cmd = [sys.executable, "-m", "yt_dlp", "-f", "b[ext=mp4]/best",
                   "--no-warnings", "-o", str(video_path), tiktok_url]
            rc, _out, err = _run(cmd, timeout=120)
            if rc != 0 or not video_path.exists():
                raise HTTPException(status_code=502, detail=f"Video download failed: {err[-400:]}")

        frame_dir = Path(tmp) / "frames"
        frame_dir.mkdir()
        fps = num_frames / duration
        cmd = [
            "ffmpeg", "-y", "-i", str(video_path),
            "-t", str(duration),
            "-vf", f"fps={fps},scale=480:-1",
            "-q:v", "3",
            str(frame_dir / "frame_%03d.jpg"),
        ]
        rc, _out, err = _run(cmd, timeout=60)
        frame_files = sorted(frame_dir.glob("frame_*.jpg"))
        valid_frames = [p for p in frame_files if p.stat().st_size > 1024]
        if rc != 0 or not valid_frames:
            raise HTTPException(status_code=500, detail=f"Frame extraction failed: {err[-400:]}")

        frames_out = [
            {"filename": p.name, "data_b64": base64.b64encode(p.read_bytes()).decode("ascii")}
            for p in valid_frames[:num_frames]
        ]
        video_b64 = base64.b64encode(video_path.read_bytes()).decode("ascii")

    return {"frames": frames_out, "video_b64": video_b64}
