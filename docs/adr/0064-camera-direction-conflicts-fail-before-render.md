# 0064 — Refuse conflicting fixed-camera directions before rendering

- **Status:** accepted; refines [0063](0063-two-camera-setups.md)
- **Date:** 2026-10-31
- **Anchors:** `backend/generation_planning.py` (`require_camera_setup_directions`, `build_segment_prompt`); `backend/server.py` (`_submit_generation`); `frontend/src/pages/CreateVideo.jsx` (`review-visual-direction`); `backend/test_generation_api.py` (`TestCameraSetup`).

## Context

A strategy stamped for fixed camera can still contain “Handheld selfie, close
framing” in `scene.visual_style` or a recording phone held at arm’s length in
`performance.movement`. Both reached the video model as locked instructions
alongside the stationary shot, at both 6,800- and 4,090-character budgets.
The review screen also displayed those notes without explaining which control
owned framing. Strategy-writing instructions alone do not protect a paid render.

## Decision

- Camera setup remains the owner of framing and camera movement. Validate the
  unbudgeted fixed-camera strategy before prompt assembly, including scene,
  performance, opening/segment direction and camera-gesture fields.
- Explicit conflicting directions cause an HTTP 409 before a generation record
  or provider call. Name the conflicting field and direct the founder to edit
  it or rebuild the strategy on Hook + Story, then review again.
- Do not silently strip or replace mixed free-text directions: they can contain
  reviewed setting, lighting, wardrobe and gestures. Saved strategy and scene
  notes remain unchanged. Spoken scripts are not camera instructions and are
  not scanned; natural head gestures and the final second-phone reveal remain
  valid. Negative camera constraints are allowed.
- Label the existing visual-direction input “Setting, lighting & wardrobe” and
  explain its relationship to Camera setup. Switching setups preserves its
  contents; the existing save/rebuild/review gates still apply.
- No new model, model call, render stage, settings or processing change.
  Handheld behavior and existing provider prompt ceilings remain unchanged.

## Consequences and alternatives

- Known contradictory strategies fail visibly instead of spending a render.
  A conflicting older strategy needs correction/rebuild before it can render.
- The guard recognizes explicit camera language; it is not a semantic verifier
  for arbitrary prose, nor a guarantee that generated footage follows a prompt.
- Dropping entire visual-style/movement fields was rejected because that also
  discards valid reviewed details. An LLM rewrite at submission was rejected
  because it adds work and can change the approved direction without review.
- Regression checks cover both prompt budgets, pre-provider refusal, retained
  scene/voice/gesture/script content, and review save/reload. Actual generated
  framing still requires separately approved paid-render evaluation.
