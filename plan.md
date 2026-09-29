# plan.md — TikTok Hook Analyzer + Customization (No Auth / No Landing)

> **Status note (added later, history preserved below).** This document is the
> plan for the original V1 app — MongoDB, Gemini, no auth — and is kept as a
> record of what was asked for then. The app was since remade around App
> Profiles, hook templates, and the creation studio; the current spec is
> `README.md`. Of this plan's Phase 3, the cost controls (deduplicate LLM
> calls, rate limiting, background queue) are still open; everything else was
> either built in the remake or superseded by it.

## 1) Objectives
- Provide a niche-based browsing feed of **curated trending TikTok videos** (no TikTok API) + **manual TikTok URL** analysis.
- Implement a **real hook-analysis pipeline** for the first 2–3 seconds: frames → vision LLM → **structured JSON** insights.
- Provide a **customization workflow** that outputs:
  - (a) a **Generation Spec JSON** for future video-gen integration, and
  - (b) a **still-image preview** generated now (Gemini Nano Banana image model) using uploaded person photo + key hook frame.
- Ensure reliable caching/storage of downloads, frames, analyses, and customizations.

**Current status:** Objectives are fully achieved in V1 and verified end-to-end with real data.

---

## 2) Implementation Steps

### Phase 1 — Core POC (must pass before app build)
**Goal:** Prove the end-to-end core pipeline works with real calls.

✅ **Status: COMPLETE**

**Delivered artifact:** `/app/backend/test_core.py`
- Step A: Download public TikTok video via `yt-dlp`.
- Step B: Extract frames from first 2–3 seconds via `ffmpeg`.
- Step C: Vision LLM hook analysis (Gemini vision model + `AI_API_KEY`) returning strict structured JSON.
- Step D: Still-image face-swap/customized preview (Gemini Nano Banana: `gemini-3.1-flash-image-preview`) using reference hook frame + uploaded portrait.

**Exit criteria achieved:** Script reliably produces (1) extracted frames, (2) valid structured hook JSON, (3) generated preview image.

---

### Phase 2 — V1 App Development (build around proven core)

✅ **Status: COMPLETE**

#### Backend (FastAPI + MongoDB)
1. **Curated niche configuration (real creators)**
   - Implemented `niches_config.py`: **10 niches × 3 verified public creator handles** per niche.
   - Curated feed is built by **live fetching** latest videos for each creator via yt-dlp (no TikTok API).

2. **Storage + caching**
   - Local storage folders:
     - `storage/videos` (yt-dlp downloaded mp4)
     - `storage/frames` (ffmpeg extracted hook frames)
     - `storage/uploads` (normalized user portraits)
     - `storage/generated` (AI-generated preview images)
   - Cached by `sha256(url)`-derived hash.
   - Niche feed caching:
     - `GET /api/niches/{niche}/videos` uses **6-hour TTL** cache in Mongo with optional refresh.

3. **Media pipeline implementation**
   - Implemented `pipeline.py`:
     - Async subprocess wrappers for `ffmpeg` and yt-dlp.
     - Uses `python -m yt_dlp` (not `yt-dlp` binary) to fix PATH issues under supervisor.

4. **AI services**
   - Implemented `ai_service.py`:
     - Hook analysis via Gemini vision model returning required structured JSON fields.
     - Still-image generation via Gemini Nano Banana image model.

5. **API endpoints (implemented)**
   - `GET /api/niches` → list niches.
   - `GET /api/niches/{niche}/videos` → curated feed (live via yt-dlp + cached).
   - `POST /api/videos/ingest` → ingest a TikTok URL (metadata).
   - `GET /api/videos/{id}` → video doc.
   - `POST /api/videos/{id}/analyze-hook` → download + extract frames + AI hook analysis.
   - `GET /api/videos/{id}/analysis` → latest analysis.
   - `POST /api/videos/{id}/customize` (multipart) → validate portrait + generate preview + persist Generation Spec.
   - `GET /api/customizations` + `GET /api/customizations/{id}`.
   - `GET /api/history` → videos + counts + customizations.
   - Static media serving: `/api/media/...`.

#### Frontend (React)
1. **App shell (no landing/auth)**
   - Root route `/` renders **Niche Feed**.
   - Global AppShell includes:
     - Paste TikTok URL bar (ingest → route to analysis)
     - History navigation

2. **Niche feed + URL paste**
   - Niche selector chips (10 niches).
   - Trending feed grid using live curated data.
   - “Analyze Hook” CTA per card.

3. **Analysis page**
   - Loads video metadata + runs analysis.
   - Filmstrip showing extracted frames (first ~3 seconds) with timestamps.
   - Hook breakdown cards:
     - Facial expressions
     - Body language & gestures
     - Pacing & cuts
     - Text overlays timing
     - Audio cues (inferred)
     - Hook summary
     - Replicable mechanics checklist
   - Effectiveness score badge.
   - CTA: “Customize this Hook”.

4. **Customization page**
   - Photo upload (file input / dropzone) + validation.
   - Preset chips + text inputs for:
     - environment
     - background/lighting
     - clothing
   - Optional custom instructions.
   - Generates:
     - Still preview image (AI)
     - Collapsible Generation Spec JSON (copy-to-clipboard)
   - Side-by-side comparison: original hook frame vs generated preview.

5. **History page**
   - Lists prior analyses + customization thumbnails.
   - Dialog detail view: comparison + Generation Spec JSON.

6. **UX states**
   - Multi-stage progress UI for:
     - download
     - frame extraction
     - AI analysis
     - AI generation
   - Error states with retry.
   - `data-testid` attributes added for key UI elements.

**End of Phase 2 verification:** ✅ Completed.

---

### Phase 3 — Iteration + Quality Improvements
⏳ **Status: NOT STARTED (future work if requested)**

1. **Improve analysis quality**
   - Smarter frame selection (motion-aware).
   - Optional transcript/caption extraction if feasible.
   - Expand “Replicable mechanics” into a more structured hook checklist.

2. **Better customization controls**
   - Re-generate with tweaks without re-analyzing.
   - “Lock” toggles for specific hook mechanics (gesture/expression/pose).
   - Compare multiple previews side-by-side.
   - Reuse prior uploaded portraits across multiple hooks.

3. **Reliability + cost controls**
   - Deduplicate LLM calls via analysis hashing.
   - Rate limiting for heavy endpoints.
   - Background job queue (optional) for long operations.

4. **Deferred integrations (explicitly out of scope for V1)**
   - Official TikTok API integration.
   - Full AI video-generation integration.
   - Current handoff artifact: **Generation Spec JSON**.

---

## 3) Next Actions
✅ **V1 delivered**. Recommended next steps only if/when requested:
1. Add Phase 3 features (lock mechanics, re-generate, compare outputs, portrait reuse).
2. Add reliability/cost controls (rate limiting, dedup hashes, optional queue).
3. Plan integrations:
   - TikTok API (official discovery/trending)
   - AI video-generation API (use Generation Spec as prompt/spec contract)

---

## 4) Success Criteria
✅ **Met in V1**
- POC script consistently succeeds: download/frames/analysis JSON/preview image.
- V1 app supports: niche feed + URL paste ingestion + hook analysis page + customization preview + history.
- Stored artifacts persist and are reused (caching for videos, frames, niche feed).
- Clear progress + error handling for each long-running step.
- No auth/landing present; app opens directly into core workflow.

✅ **Testing evidence**
- `testing_agent_v3` iteration report: **97.6% overall pass** (40/41).
  - Frontend: **100%** (30/30)
  - Backend: **90.9%** (10/11; one non-issue noting generation quality depends on uploading a real face photo)
