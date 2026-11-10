# 0112 — Split the OpenRouter adapter by flow, keeping the transport with the seam

Status: accepted

## Context

`backend/ai_service.py` carried ~6,150 lines: the OpenRouter transport
(`_post_chat`, `_chat_json`, temperature/refusal handling), the video
submit/poll flow, the chat-driven generation flows (app profile, angles,
goals, brand templates, creative plan/strategy, hook rewrite, post kit,
direction options) — and a large mass of pure normalization those flows
consume (spoken-word budgets and trimming, story-shape checks, strategy
normalization, HTML/page-text extraction, image data URIs). Reading or
testing any one pure function required importing the whole adapter,
including `httpx` and the model catalog.

ADR 0111 named this remainder explicitly ("`ai_service.py` remain[s]
large"); this record narrows that consequence.

## Decision

Move each pure cluster into its own flow module and keep
`ai_service.py` as the re-exporting facade for the OpenRouter adapter:

- `ai_spoken.py` — spoken-word budgets, trimming, partition/binding and
  story checks (pure; stdlib + `claim_safety`/`final_beat` only).
- `ai_strategy.py` — strategy normalization (raw plan JSON → bounded
  two-section plan).
- `ai_text.py` — HTML → text (+ title/meta/JSON-LD) for app research.
- `ai_media.py` — image → data-URI encoding for vision calls.

The transport and every chat-driven generation flow stay in
`ai_service.py`. The suite monkeypatches `ai_service._chat_json` (54
uses), `ai_service._TEMPERATURE_SUPPORT`, `ai_service.OPENROUTER_API_KEY`
and `ai_service.ANGLE_MODEL` — that namespace is the patch seam. Moving
a flow would require facade indirection for each of those reads; the
pure clusters need none, so they move first. The move is move-only:
every moved name is re-exported from `ai_service` under its old name,
so each existing caller and test keeps its binding.

The same separation, applied to the wizard page, extracts the
angle-steps lifecycle (angles + verdict evidence, both click-to-view
gates, live billed goals, regenerate handlers) from `CreateVideo.jsx`
into `frontend/src/hooks/useWizardAngleStep.js`, following the
established `useWizardTemplates` / `useWizardDirections` pattern: the
page keeps the draft, picks, step and plan, and clears through the
hook's returned setters.

## Alternatives rejected

- Moving the chat flows too: correct but requires every LLM/config
  read to route through a facade (as the routers do with `_cfg`) —
  worth doing later with a dedicated test pass, not bundled into a
  move-only extraction.
- Leaving the pure clusters in the adapter: keeps importing `httpx` and
  the video catalog to unit-test a string trimmer.

## Consequences and evidence anchors

- `ai_service.py` drops from ~6150 to ~4740 lines; the pure clusters are
  independently importable and covered by the pure-policy contracts in
  `backend/test_architecture.py` (no `httpx`/`auth`/`fastapi`/
  `aiosqlite`, no `server`, no `ai_service`).
- Re-export identity (`ai_service.X is ai_spoken.X` etc.) is enforced in
  `backend/test_architecture.py`.
- `CreateVideo.jsx` keeps the wizard draft/picks/plan; the angle steps'
  lifecycle has one owner (`useWizardAngleStep`), next to the existing
  template and direction hooks.
- The LLM flows still live with the transport: a future extraction of
  those should go through the facade-seam design named above.

Anchors: `backend/ai_service.py`, `backend/ai_spoken.py`,
`backend/ai_strategy.py`, `backend/ai_text.py`, `backend/ai_media.py`,
`frontend/src/hooks/useWizardAngleStep.js`,
`backend/test_architecture.py:test_ai_service_reexports_pure_clusters_for_existing_callers`.
