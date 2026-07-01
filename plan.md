# plan.md — TikTok Hook Analyzer + Customization (No Auth / No Landing)

## 1) Objectives
- Provide a niche-based browsing feed of **curated trending TikTok videos** (no TikTok API) + **manual TikTok URL** analysis.
- Implement a **real hook-analysis pipeline** for the first 2–3 seconds: frames → vision LLM → **structured JSON** insights.
- Provide a **customization workflow** that outputs:
  - (a) a **Generation Spec JSON** for future video-gen integration, and
  - (b) a **still-image preview** generated now (Gemini image model) using uploaded person photo + key hook frame.
- Ensure reliable caching/storage of downloads, frames, analyses, and customizations.

## 2) Implementation Steps

### Phase 1 — Core POC (must pass before app build)
**Goal:** Prove the end-to-end core pipeline works with real calls.

1. **Websearch best practices**
   - Confirm current best approach for: TikTok download via `yt-dlp`, frame extraction via `ffmpeg`, and safe caching patterns.

2. **Build `/app/backend/test_core.py`** (single script)
   - Input: (a) one known public TikTok URL, (b) one local fallback video path, (c) one test portrait image.
   - Step A: Download TikTok video via `yt-dlp` into `/app/backend/storage/videos/{hash}.mp4` (skip if cached).
   - Step B: Extract frames for first 2–3s via `ffmpeg` (e.g., 8 frames) into `/storage/frames/{video_hash}/`.
   - Step C: Send frames (base64) to a **vision-capable LLM** using `emergentintegrations` + `EMERGENT_LLM_KEY`; return **strict JSON**:
     - `facial_expressions`, `micro_expressions`, `body_language_gestures`, `pacing_cuts`, `text_overlays_timing`, `audio_cues_inferred`, `hook_summary`, `effectiveness_score`, `key_hook_frame_timestamp`, `replicable_mechanics[]`.
   - Step D: Generate still-image preview using **Gemini image editing** (gemini image model) with:
     - reference key frame + uploaded person photo + customization prompt (env/background/clothing) → output image base64.
   - Save outputs locally and print paths + JSON summary (no base64 logging).

3. **POC hardening**
   - Handle failures: invalid URL, download blocked, ffmpeg missing, model errors.
   - Implement fallback: if TikTok download fails, run analysis on a bundled sample mp4.

**Exit criteria:** Script reliably produces (1) extracted frames, (2) valid structured hook JSON, (3) generated preview image.

---

### Phase 2 — V1 App Development (build around proven core)

#### Backend (FastAPI + MongoDB)
1. Data model + seed
   - Seed 10 niches with 3–4 curated videos each (URL + title/creator/stats + thumbnail url if available).

2. Storage + caching
   - Local storage folders: `storage/videos`, `storage/frames`, `storage/uploads`, `storage/generated`.
   - Cache by `sha256(url)`; store metadata in Mongo.

3. API endpoints
   - `GET /api/niches` → list niches.
   - `GET /api/niches/{niche}/videos` → curated feed.
   - `POST /api/videos/ingest` {`tiktok_url`} → download (yt-dlp), create video doc.
   - `POST /api/videos/{id}/analyze-hook` → extract frames (if needed) + vision LLM JSON; store analysis.
   - `GET /api/videos/{id}` and `GET /api/videos/{id}/analysis`.
   - `POST /api/videos/{id}/customize` (multipart: person image + preset fields + free text) →
     - build/store **Generation Spec JSON**
     - call Gemini image model to generate preview; store and return.
   - `GET /api/customizations` + `GET /api/customizations/{id}`.
   - Serve images via `GET /media/...` (static file serving).

#### Frontend (React)
1. App shell (no landing/auth)
   - Default route: **Niche Feed**.

2. Niche feed + URL paste
   - Niche selector (top).
   - Cards for curated videos + “Analyze Hook”.
   - URL input bar: paste TikTok URL → ingest → navigate to analysis.

3. Analysis page
   - Video preview (embedded if possible) + extracted frames strip.
   - Hook analysis sections rendered from JSON (cards for each dimension) + overall score + hook summary.
   - CTA: “Customize this Hook”.

4. Customization page
   - Upload portrait.
   - Presets: environment/background/clothing + optional free-text.
   - Show reference key frame + generate button.
   - Results: side-by-side original key frame vs generated preview + collapsible Generation Spec JSON.

5. History page
   - List analyses + customizations; open detail.

6. UX states (must-have)
   - Progress UI for: download, frame extraction, LLM analysis, image generation.
   - Clear error UI with retry.

**Phase 2 user stories (minimum)**
1. As a user, I can pick a niche and browse curated trending videos.
2. As a user, I can paste a TikTok URL and ingest it for analysis.
3. As a user, I can analyze the first 2–3 seconds and see extracted frames.
4. As a user, I can read a structured hook breakdown and understand what to replicate.
5. As a user, I can upload my photo, customize styling, and generate a still preview + spec.

**End of Phase 2:** run `testing_agent_v3` for one full E2E pass.

---

### Phase 3 — Iteration + Quality Improvements
1. Improve analysis quality
   - Better frame selection (include motion changes), add optional transcript extraction if feasible.
   - Add “Hook mechanics checklist” derived from `replicable_mechanics`.

2. Better customization controls
   - More presets, lock toggles (lock pose/expression vs allow variation).
   - Re-generate with tweaks without re-upload.

3. Reliability + cost controls
   - Deduplicate LLM calls, store analysis hash, rate-limit endpoints.

**Phase 3 user stories (minimum)**
1. As a user, I can re-run generation with new styling without re-analyzing the video.
2. As a user, I can lock specific hook mechanics (gesture/expression) while changing background.
3. As a user, I can compare multiple generated previews for the same hook.
4. As a user, I can quickly reuse a prior uploaded portrait for new hooks.
5. As a user, I can see which exact frame/time was used as the “key hook frame”.

**End of Phase 3:** run `testing_agent_v3` again.

## 3) Next Actions
1. Save the image integration testing rules to `/app/image_testing.md`.
2. Implement and run `test_core.py` until the core pipeline passes reliably.
3. Once POC passes, scaffold backend routes + Mongo schemas + storage, then build React UI in one cohesive pass.
4. Seed curated niche dataset and verify feed → analyze → customize → history flows.

## 4) Success Criteria
- POC script consistently succeeds: download/frames/analysis JSON/preview image.
- V1 app supports: niche feed + URL paste ingestion + hook analysis page + customization preview + history.
- Stored artifacts persist and are re-used (no re-downloading or re-analyzing unnecessarily).
- Clear progress + error handling for each long-running step.
- No auth/landing present; app opens directly into core workflow.
