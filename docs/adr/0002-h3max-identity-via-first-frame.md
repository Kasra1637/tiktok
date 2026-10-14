# 0002 — H3 Max identity rides as the opening frame, not `input_references`

- **Status:** accepted
- **Date:** 2026-10-14 (decision predates this record; backfilled)
- **Anchors:** `backend/video_providers.py` (`minimax-h3-max`: `max_reference_images: 0`,
  `identity_via_first_frame: True`); `backend/server.py` (`_submit_generation`
  identity branch); `backend/ai_service.py` (`VIDEO_MODELS["minimax-h3-max"]` comment)

## Context

OpenRouter lists `input_references` for MiniMax Hailuo 3 Max, but the serving
provider refuses it outright — proven live with a 400. Sending the founder's
photo in that field spends a failed submit on every render. The generic
OpenRouter videos mechanism is therefore not trustworthy per-model: "listed"
and "accepted" are different claims.

## Decision

- H3 Max carries identity as the opening `first_frame` (`identity_via_first_frame`),
  which OpenRouter documents as supported for this model. `max_reference_images`
  is 0 — recorded as input-reference capacity specifically, so capability checks
  never read it as permission to send any.
- The submit path picks the field from the capability; photo resolution stays in
  one place (`_studio_identity_references`). New models with the same unknown
  (HeyGen, Grok at entry) default to `input_references` and fail loudly on
  refusal rather than silently pinning the opening on the photograph (see ADR 0001).

## Consequences

- **Gain:** Max renders are submittable; the photo-placement rule is data, not
  branching, so adding a model is an environment-shaped change.
- **Cost:** first-frame routing pins the opening to the uploaded photo's own
  room/light — the HeyGen lesson. Acceptable for Max (documented, proven);
  never applied silently to a model where it would corrupt the opening.

## Alternatives considered

- **Send both frame and references, let the provider sort it out:** rejected —
  providers 400 on combined `frame_images` + `input_references`; exactly one
  visual anchor survives, and the seam/identity frame wins.
- **Refuse identity models that reject `input_references`:** rejected — loses a
  working renderer over a field choice; the frame route renders fine.
