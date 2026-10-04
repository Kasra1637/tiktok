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
| `MODAL_SHARED_SECRET` | Authenticates the Modal frame-extraction worker |
| `CORS_ORIGINS` | Allowed browser origins, comma-separated. Defaults to `*` |
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

Three gates stand between an unreviewed plan and a render, in order:

1. **Profile approval** — nothing is generated from an unreviewed profile.
2. **Claim check** — the plan is independently re-checked on *every edit*, and
   generation is blocked while a prohibited claim is present.
3. **Ready state** — a project must be explicitly marked ready before a
   generation is submitted.

### Why a variation never renders by itself

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
| `generation_planning.py` | Single-pass prompt, error triage |
| `overlays.py` | ffmpeg filter-graph construction and rendering |
| `variations.py` | The nine controlled variation axes |
| `feedback.py` | Structured feedback vocabulary and its aggregate summary |
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
iterates on a script on text alone, and only a marked-ready project renders.

---

## Testing

```bash
cd backend
python -m pytest -q
```

**639 passing, 0 failing** (`cd backend`, `python -m pytest -q`).

Overlay tests render real MP4s with ffmpeg and assert on output, because the
worst bugs in that path (an orphaned filter chain, a 600-second output) exited
0 and produced plausible-looking files.

---

## Known limitations

### Video model capabilities

| Model | Single pass | Notes |
|---|---|---|
| `minimax-h3` | 5–15s | 2K, native audio. **Cannot** combine `frame_images` with `input_references`. 20s and 30s need a second generation. |
| `seedance-2.5` *(default)* | 4–30s | 720p, native audio, up to 50 multimodal references, first-frame guidance. The longest single pass available. |
| `runway/aleph-2` | — | **Editor, not a generator.** Refused by this workflow: it edits an existing clip and cannot generate from a prompt. Legacy flow only. |

Other constraints:

- **720p vs 2K.** Seedance outputs 720p, MiniMax 2K. A 20s video on the
  default model means a 15s generation plus a 5s extension, which can show a
  visible join. Set `VIDEO_MODEL_DEFAULT=seedance-2.5` for 20s/30s in one pass.
- **Vertical is assumed.** Every model here is driven at 9:16.
- **No cost reporting at all.** The product does not meter what a render costs
  the operator. No generation row, no model-request row and no API response
  carries a cost field, and no screen shows one. Metering this honestly is a
  product of its own, and a half-honest meter is worse than none.
- **No live end-to-end verification.** Duration logic, retry,  provenance, and overlay compositing are verified — the last against real
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
- Video generation → **one job per video** with provenance- Nav → Create / Insight / Research

### Added

App Profiles, content angles, the 18-template curated library, the
recommendation engine, the creation studio, deterministic claim safety, the
provider capability layer, the per-App-Profile asset library, deterministic
overlay compositing, generation history, nine controlled variation axes,
manual performance logging, trend research, and structured feedback.

### Removed since

Nothing was deleted lightly; each of these was a view *of* the work rather
than a place *of* work, and everything each one showed is still served where
the work happens:

| Removed | Where its content lives now |
|---|---|
| Operations (`/operations`) | History (failures + Retry), per-generation endpoints |
| Settings (`/settings`) | Studio footer (never-publishes line), History (entered-by-hand figures), Create Video (not-proven-performers note) |
| Dashboard (`/`) | History (totals + failures + Retry), the sidebar (next steps). `/` redirects to `/create` |
| App Profiles list (`/app-profiles`) | Your app (`/brand`) for research/edit/approve; the profile detail page survives for angles, templates, and per-app drafts. `/app-profiles` redirects to `/brand` |
| Analytics (`/analytics`) | Nowhere — deliberately. It reported the operator's own activity and what it cost them, and this product does not meter that. `/analytics` redirects to `/create` |
### Removed / demoted

Pages that were views *of* the work rather than places *of* work have been
deleted outright (see "Removed since" above). The exact-match recreation flow
is **demoted** to the Research nav group and kept working:

| Route | Was | Now |
|---|---|---|
| `/discover` | primary entry | Research group |
| `/face-swap` | primary creation | Route removed; the backend helpers (`face_crop.py`, AI service face functions) remain for Trend Research and legacy comparison |
| `/bookmarks` | Hook Templates | Research group (Saved Hooks) |
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
