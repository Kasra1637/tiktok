# HookForge — internal app-promo video studio

An internal tool for mobile app founders to create short-form promotional
videos from curated, reusable hook templates.

This is **not** a viral-video copying tool. It reproduces reusable hook
*mechanics* — never a creator's identity, performance, gestures, frames, voice,
or copyrighted content. The primary workflow requires **no source video at
all**.

**Nothing is ever published automatically.** Videos are generated, reviewed,
downloaded, and posted by hand. The app has no code path that posts,
schedules, engages, or holds platform credentials.

---

## Quick start

### Prerequisites

| Tool | Why | Notes |
|---|---|---|
| Python 3.12 | Backend | `pip install -r requirements.txt` |
| Node 20+ | Frontend | Uses `yarn` 1.22 |
| **ffmpeg** | Frame extraction **and overlay compositing** | Must be on `PATH` |
| A font file | Caption/end-card text | Auto-detected; override with `OVERLAY_FONT` |

Without ffmpeg, overlays are skipped and the un-composited video is kept.
Without a font, text layers are skipped rather than rendered wrong.

### Backend

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env      # then fill in the keys below
python -m uvicorn server:app --reload
```

API on `http://localhost:8000`. `init_db()` runs on startup and is
idempotent: it creates tables, adds missing columns, and seeds the curated
template library without duplicating it.

### Frontend

```bash
cd frontend
yarn install
echo "REACT_APP_BACKEND_URL=http://localhost:8000" > .env
yarn start
```

App on `http://localhost:3000`.

### Environment

All optional except `OPENROUTER_API_KEY` if you want AI features. Copy
`backend/.env.example` and set what you need:

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | **Required** for research, angles, scripts, video |
| `APIFY_API_TOKEN` | Trend Research. Without it, research fails with a clear 503 |
| `CLERK_JWKS_URL` | Optional. Unset means auth is disabled (all access is `anonymous`) |
| `PUBLIC_BASE_URL` | Public HTTPS origin; required for V2V references |
| `R2_*` | Durable video storage. Unset means videos don't survive a redeploy |
| `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN` | Cloud SQLite. Unset uses local SQLite |
| `MODAL_FRAME_EXTRACTOR_URL` | Offloads frame extraction off the API host |
| `VIDEO_MODEL_DEFAULT` | Swap video provider without a code change |
| `VIDEO_MODEL_ALLOWLIST` | Restrict which providers may be used at all |
| `OVERLAY_FONT` | Font file for captions |

---

## The workflow

```
App URL  →  website + store research  →  AI App Profile  →  review & approve
        →  ICP segments + content angles  →  template recommended or chosen
        →  real assets attached  →  script + shot plan  →  claim check
        →  ONE complete video generated  →  real app visuals composited
        →  review, vary, download  →  founder posts by hand
```

Three gates protect the spend, in order:

1. **Profile approval** — nothing is generated from an unreviewed profile.
2. **Claim check** — the plan is independently re-checked on *every edit*, and
   generation is blocked while a prohibited claim is present.
3. **Ready state** — a project must be explicitly marked ready before a paid
   generation is submitted.

### Why a variation never costs money by itself

A variation produces a **draft project**. Producing the video is a separate,
explicit action. Variations are never batch-generated.

### Why interfaces are never fabricated

The model produces a person, a scene, and movement. Screenshots, screen
recordings, logos, on-screen text, and the CTA are composited afterwards with
ffmpeg from **real assets**, so app interfaces, pricing, and text are
pixel-exact and cannot drift.

---

## Architecture

### Backend modules

| Module | Responsibility |
|---|---|
| `server.py` | Routes, DB, orchestration |
| `ai_service.py` | OpenRouter: research, angles, plans, video, polling |
| `template_library.py` | Curated structures, vocabularies, duration clamping |
| `claim_safety.py` | **Deterministic** claim checking (never model self-report) |
| `video_providers.py` | Provider capability layer; env-configurable model |
| `generation_planning.py` | Single-pass prompt, cost extraction, error triage |
| `overlays.py` | ffmpeg filter-graph construction and rendering |
| `variations.py` | The nine controlled variation axes |
| `analytics.py` | Pure metric computation |
| `feedback.py` | Structured feedback vocabulary |
| `research_abstraction.py` | Trend data → abstract template drafts |
| `pipeline.py` | yt-dlp / ffmpeg / Modal media pipeline |
| `storage_service.py` | Cloudflare R2 |
| `apify_tiktok.py` | Public TikTok data (Clockworks actor) |
| `viral_detection.py` | Engagement ranking |

### Data model

`brand_profiles` (App Profiles, extended from the old `brand_profiles`) ·
`content_angles` · `hook_templates` (extended) · `template_favorites` ·
`studio_projects` · `generations` · `assets` · `overlay_compositions` ·
`performance_entries` · `feedback_events` · `research_runs`

`studio_projects` is deliberately separate from `generations`: the founder
iterates on a script for free, and only a marked-ready project spends money.

---

## Testing

```bash
cd backend
python -m pytest -q
```

**474 passing, 3 failing.** The three failures are in
`test_face_swap_prompt.py` and are **pre-existing**: they assert a prompt
contract string removed in an earlier commit and fail identically at `fcc8a35`
(the last commit before this work). They belong to the demoted legacy
exact-match flow and were left untouched rather than rewritten to pass.

Overlay tests render real MP4s with ffmpeg and assert on output, because the
worst bugs in that path (an orphaned filter chain, a 600-second output) exited
0 and produced plausible-looking files.

---

## Known limitations

### Video model capabilities

| Model | Single pass | Notes |
|---|---|---|
| `minimax-h3` *(default)* | 5–15s | 2K, native audio. **Cannot** combine `frame_images` with `input_references`. 20s and 30s need a second generation. |
| `seedance-2.5` | 4–30s | 720p, native audio, up to 50 multimodal references, first-frame guidance. The longest single pass available. |
| `runway/aleph-2` | — | **Editor, not a generator.** Refused by this workflow: it edits an existing clip and cannot generate from a prompt. Legacy flow only. |

Other constraints:

- **720p vs 2K.** Seedance outputs 720p, MiniMax 2K. A 20s video on the
  default model means a 15s generation plus a 5s extension, which can show a
  visible join. Set `VIDEO_MODEL_DEFAULT=seedance-2.5` for 20s/30s in one pass.
- **Vertical is assumed.** Every model here is driven at 9:16.
- **Cost reporting is best-effort.** Spend counts only runs whose provider
  response carried a cost. Unpriced runs are reported separately, never as
  free.
- **No live end-to-end verification.** Duration logic, cost capture, retry,
  provenance, and overlay compositing are verified — the last against real
  rendered MP4s. Whether a given model returns a usable clip to composite onto
  has **not** been confirmed against a live generation; that needs a key with
  credit.

### Other limitations

- **Turso untested on Windows.** `libsql_experimental` is a Rust extension
  without Windows wheels, so tests exercise the local SQLite path. The cloud
  branch is unverified.
- **Overlay quality depends on the base clip.** Overlays are composited at
  fixed 1080×1920 with a 0–3s hook assumption baked into templates.
- **Text overlays are only as good as the plan.** They come from the reviewed
  plan, never invented at composition time — which is correct for claim safety
  but means a poor plan yields a poor caption.
- **Trend Research needs `APIFY_API_TOKEN`.** Without it, scans fail loudly
  rather than returning an empty result that would read as "nothing found".

---

## What changed from the previous version

### Preserved

- OpenRouter client, polling, retry-on-transient, and job normalization
- Apify integration and public TikTok data parsing
- yt-dlp / ffmpeg / Modal frame-extraction pipeline
- Cloudflare R2 storage and the `video_assets` registry
- SQLite with the Turso fallback, plus the migration pattern
- Clerk auth (unchanged, per your instruction) and the anonymous fallback
- SQLite/Turso DB helpers, MediaFile storage, and the deploy setup
- The legacy exact-match flow, demoted but fully working

### Modified

- `brand_profiles` → **App Profiles** with store URLs, pricing, features,
  ICP, claim tiers, and review/approve/refresh
- `hook_templates` → **Hook Template Library** with structure fields,
  versioning, favorites, archive, and publication
- Video generation → **one job per video** with provenance and cost tracking
- Nav → Create / Insight / Setup / Legacy

### Added

App Profiles, content angles, the 18-template curated library, the
recommendation engine, the creation studio, deterministic claim safety, the
provider capability layer, the per-App-Profile asset library, deterministic
overlay compositing, generation history, nine controlled variation axes,
manual performance logging, trend research, analytics, structured feedback,
operations, dashboard, and settings.

### Removed / demoted

Nothing was deleted. The exact-match recreation flow is **demoted** to a
Legacy nav group and kept working:

| Route | Was | Now |
|---|---|---|
| `/discover` | primary entry | Legacy |
| `/face-swap` | primary creation | Legacy |
| `/bookmarks` | Hook Templates | Legacy (renamed Saved Hooks) |
| `/history` | exact-match history | **Generation History** (old one at `/legacy-history`) |

No code path can publish, post, schedule, engage, or capture platform
credentials — asserted by tests, not just documented.

### Deliberately not added

Public registration, customer authentication, Stripe/billing, public
marketing or pricing pages, multi-platform publishing, and bulk variant
generation.

---

## Confirmation

**The primary workflow no longer depends on frame-by-frame viral-video
reproduction.**

A video is produced from an approved App Profile, a content angle, and an
abstract hook template. A test asserts that no curated template references a
creator handle, requires a reference video, or is described as proven
(`test_template_library.py::TestAbstractStructureGuarantee`); another asserts
that no seed describes itself as proven, viral, or guaranteed. Templates are
labelled "curated" or "based on recurring high-performing hook mechanics"
until this app's own history supports more.

The exact-match code still exists for Trend Research and legacy comparison,
but nothing in the primary path requires it, and the Aleph editor model is
refused because it can only work from a source clip.
