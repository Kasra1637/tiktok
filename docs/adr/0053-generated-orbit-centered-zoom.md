# 0053 — Generation owns the orbit and gesture; processing owns one centered zoom

- **Status:** accepted
- **Date:** 2026-10-27
- **Supersedes:** [0008](0008-hook-boundary-lean-in.md)
- **Anchors:** [strategy schema and normalization](../../backend/ai_service.py#L557),
  [starting-shot and render camera instructions](../../backend/generation_planning.py#L348),
  [zoom geometry](../../backend/overlays.py#L192),
  [finalize call](../../backend/server.py#L7399),
  [pixel regression](../../backend/test_overlays.py#L203)

## Context

A flat lateral crop cannot produce a new camera perspective. The earlier 9%
canvas-relative arc also made a 0.07 zoom setting become 1.25x total scale.
Asking generation to push in as well assigned the same movement to two owners.
Generated motion cannot be pinned reliably to an exact spoken word.

## Decision

- Use the requested selfie starting-shot text verbatim, replacing metre-based
  camera/framing fields. Preserve scene, light, wardrobe, identity, script,
  single-pass generation and final-phone handoff constraints.
- Generation makes one subtle left/right orbit to three-quarter, keeping the
  same camera-to-face distance, then holds. It performs one short story-specific
  actor gesture at the same moment, **when the story begins**, never at a promised
  timestamp. Generated push-in, pullback and zoom are explicitly prohibited.
- `camera_beat` contains only `direction` and `gesture`. Legacy timestamps and
  arc fields are discarded. Missing legacy direction defaults to right; an
  invalid explicit direction names regeneration as the next step.
- Processing starts one centered zoom at `0.7 * hook_seconds`, eases via
  smoothstep for 0.6 seconds, then holds to the end. The default total is exactly
  1.10x; allowed totals are 1.08x–1.12x. No lateral allowance, crop-based arc,
  face-following pan or face repositioning remains. Finalize still processes
  fresh provider bytes only, never a previously saved canonical clip.
- Use one inverse-coordinate FFmpeg resampling (`geq`) about the fixed frame
  center, retaining fractional coordinates. A real-pixel grid regression found
  that dynamically resizing before `crop` retained the initial crop origin on
  the installed FFmpeg: nominally centered expressions actually zoomed from the
  top-left. The regression measures both axes, ramp and hold rather than merely
  checking command text.
- Keep full head, chin and entire phone inside the central 88% of generated
  footage, safe for the maximum 1.12x crop (which retains 89.29%). The phone back
  remains visible at chest height in the final seconds through the last frame.
- Camera text and the gesture cannot be budget-scaled away. Equivalent condensed
  handoff/identity/opening wording buys room on tight providers without changing
  their constraints. The condensed threshold becomes 5,000 because the enlarged
  full camera floor cannot fit saturated 4,600-character prompts. Provider
  ceilings and sacred-script policy are unchanged.

## Consequences

- Processing can prove one exact centered zoom, not successful generated orbit
  adherence. Existing footage cannot validate instructions it never received.
- A fixed crop cannot preserve a head or phone already at/outside its edges.
  Source framing remains a generation requirement; no hidden adaptive zoom,
  lateral workaround, fallback model or extra generation path is introduced.
- Pixel resampling costs processing time; the existing encode gate, output
  canvas, optional audio, timeout and soft-failure preservation stay unchanged.
- See [verification evidence](../../test_reports/camera-owner-split.md) for real
  clip measurements and explicit orbit/head/phone limitations.

## Alternatives rejected

- Keep a lateral crop to fake the orbit: still cannot create perspective and
  silently spends extra magnification.
- Ask generation for zoom too: doubles ownership and cannot guarantee magnitude.
- Promise exact generated spoken-word sync: unsupported by this generation path.
- Auto-reframe unsafe source footage: violates fixed centered geometry and the
  requested instruction to report reliability/framing problems before changes.
