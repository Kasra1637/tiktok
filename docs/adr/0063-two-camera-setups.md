# 0063 — Handheld selfie and fixed camera share one render path

- **Status:** accepted
- **Date:** 2026-10-31
- **Partially supersedes:** [0053](0053-generated-orbit-centered-zoom.md) on universal selfie/orbit/zoom behavior; handheld behavior is unchanged.
- **Anchors:** `backend/models.py` (`camera_setup`); `backend/generation_planning.py` (`starting_shot`, `camera_move_section`); `backend/server.py` (`_submit_generation`, `_persist_generation_clip`); `frontend/src/pages/CreateVideo.jsx` (`camera-setup`); `backend/test_generation_api.py` (`TestCameraSetup`).

## Context

A close handheld selfie is not the only casual UGC setup. A phone placed on a
shelf or tripod lets the presenter show more body language without holding the
recording camera. Adding a prompt sentence alone would conflict with the fixed
selfie/orbit instructions and the centered zoom applied during completion.

## Decision

- One per-draft choice: **Handheld selfie** (default, including existing drafts)
  or **Fixed camera**. Use the existing review/save workflow, not a new settings
  system. Changing the choice invalidates the strategy; rebuild and review it
  before submitting. Hand-editing a strategy cannot stamp it as rebuilt for a
  different setup.
- Handheld keeps its existing chest-up selfie, subtle sway, generated orbit and
  centered processing zoom. No existing footage is reprocessed.
- Fixed uses an eye-level, straight-on stationary phone on a shelf or tripod,
  framing head to mid-thigh with headroom and space for both hands. Keep the
  natural amateur phone look. Expressions, gestures and small weight shifts
  carry the performance; no walking toward the lens, camera movement or zoom.
- Generation planning owns the shot instructions for strategy and rendering.
  Fixed replaces selfie/orbit instructions and template camera pacing, rather
  than adding contradictory instructions. Full and condensed prompts preserve
  the approved speech, identity rules, phone reveal and prompt ceilings.
- Keep the existing face-reference crop/routing. Models requiring that crop as
  a literal first frame cannot promise the wider opening: refuse fixed-camera
  submission before billing, explain beside model selection, and ask the founder
  to choose a compatible model or handheld. Never auto-switch models or add a
  paid image-generation stage.
- Snapshot the setup on each generation at submission. Completion and storage
  recovery read that immutable choice, not the mutable draft; fixed skips the
  automatic processing zoom, not canvas fitting, audio or storage. Existing
  generation records default to handheld. Deliberate later framing edits in
  Demo + CTA remain available.

## Consequences and alternatives

- Wider framing leaves body appearance outside a face reference to model
  synthesis. The UI states that identity guidance is not exact body fidelity.
- Fixed-camera support is narrower than handheld provider support. Sending a
  face crop as the first frame and hoping for a wider shot was rejected, as was
  silently selecting another model or generating an extra opening image.
- No distance, lens, framing or movement sliders: two coherent setups are the
  requested scope. Fixed does not silently become polished or cinematic.
- Automated checks establish saved state, strategy gates, prompts, capability
  refusal and processing. They do not establish generated framing or identity
  quality; matched paid renders need separate user approval.
