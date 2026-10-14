# 0006 — Retire Grok Imagine Video 1.5 Lite (`input_references` unsupported)

- **Status:** accepted (partially supersedes [0001](0001-grok-submit-failures-are-loud.md) on Grok eligibility; loud-400 handling remains)
- **Date:** 2026-10-14
- **Anchors:** `backend/ai_service.py` (`VIDEO_MODELS`); `backend/video_providers.py`
  (`STUDIO_ELIGIBLE`, `_NOTES`)

## Context

In ADR 0001 we added loud provider-400 reporting after a Grok Imagine Video 1.5
Lite render failed before starting, while keeping Grok selectable until we knew
whether the 400 was parameter-specific or systematic. The surfaced error
answered the question directly:

> `Provider said: input_references is not supported for this model.`

Because every studio render attaches the founder's character reference photo
via `input_references` (and we will not pin the photo as `first_frame` where it
locks the opening to the photo's room and lighting), Grok cannot complete a
studio render. Keeping it in the dropdown only invites guaranteed 400s.

## Decision

- Remove `grok-imagine-video-1.5-lite` from `VIDEO_MODELS`, `_NOTES`, and
  `STUDIO_ELIGIBLE`.
- Existing records or saved model preferences naming `grok-imagine-video-1.5-lite`
  degrade cleanly to `default_model_key()` (`minimax-h3`) via `video_providers.resolve()`
  and `video_providers.capability()`.
- Keep ADR 0001's loud-400 error formatting (`Provider said: …`, 800-char submit
  detail, 2000-char `generations.error`, non-retryable 400 classification) for
  all remaining and future providers.

## Consequences

- **Gain:** no dead option in the studio model selector; capability drift check
  and test suite cover only models that can actually render studio projects.
- **Cost:** one fewer comparison model in the dropdown until xAI/OpenRouter
  supports `input_references` on Grok video.

## Alternatives considered

- **Route Grok identity via `first_frame` (like H3 Max):** rejected — pins the
  opening second to the uploaded photo's room and lighting, which is the exact
  failure mode we moved away from on HeyGen.
- **Keep Grok in the dropdown and let it 400:** rejected — the refusal is
  unconditional for reference-image renders, not a parameter combination the
  founder can work around.
