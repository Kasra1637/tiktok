# 0001 — Provider 400s fail loudly with the provider's quoted words

- **Status:** accepted (Grok eligibility superseded by [0006](0006-retire-grok-video-model.md); loud-400 rule still active)
- **Date:** 2026-10-14
- **Anchors:** commit `6a0b320`; `backend/ai_service.py` (`generate_video` submit path,
  `_extract_provider_message`); `backend/server.py` (`_submit_generation` error path)

## Context

A Grok Imagine Video 1.5 Lite render (15s, 480p, 9:16, photo as reference image)
was refused with HTTP 400 before starting. The founder saw only
"Video generation failed to submit: ... The full p…" — the message was truncated
to 200 chars by the server, and the actual provider wording lived only in the
server log, which the founder never sees. Undiagnosable failures invite blind
retries and re-uploads of files that already reached the provider.

## Decision

- The submit error quotes the provider's own excerpt (`Provider said: …`,
  extracted from the nested error JSON) alongside the request summary
  (model, duration, resolution, aspect, photo route) and states nothing was charged.
- Submit detail widened 200 → 800 chars; `generations.error` widened
  1000 → 2000 chars. The full body stays in the server log.
- Grok stays selectable. A 400 marks the generation non-retryable
  (`is_recoverable_error`), so the UI says to change script or model — never
  "try again" on the identical request.
- No silent fallback to another model. Founder decision.

## Consequences

- **Gain:** the next 400 arrives with the provider's reason attached, so the
  fix (reference field vs resolution vs duration) is answerable without log access.
- **Cost:** longer error strings in the UI and DB; the excerpt parser must never
  raise on unparseable bodies (it doesn't — it degrades to collapsed raw text).

## Alternatives considered

- **Silent auto-retry on the default model:** rejected — spends a billed render
  on a different model than the founder chose, making results non-reproducible.
  Offered as an explicit one-click choice instead, via the surfaced error.
- **Quarantine Grok from the studio dropdown:** rejected for now — kept as a
  one-line kill-switch (`STUDIO_ELIGIBLE`) if 400s prove systematic rather
  than parameter-specific.
