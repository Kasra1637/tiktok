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
- Keep full head, chin and whole phone inside the central 88% of generated
  footage, safe for the maximum 1.12x crop (which retains 89.29%). In the final
  1-2s she raises the phone into view as she finishes saying she found it, back
  to camera; it stays fully visible and uncropped at chest height, with clear
  margins and never behind hand/arm/face, through the last frame. About a metre
  is a loose starting hint, not exact. No screen or app content is generated.
- Camera text and the gesture cannot be budget-scaled away. Equivalent condensed
  handoff/identity/opening wording buys room on tight providers without changing
  their constraints. The condensed threshold becomes 5,000 because the enlarged
  full camera floor cannot fit saturated 4,600-character prompts. Provider
  ceilings and sacred-script policy are unchanged.
- Accept the prompt-budget cost of that text instead of shrinking it away. The
  verbatim starting shot, orbit/gesture beat and final-phone rule raise the
  measured fixed floor by about 711 characters (3,487 → 4,198 full; 2,102 →
  2,346 condensed). A saturated strategy at the default 6,800 ceiling therefore
  overflows the first assembly, and the refit amputates the tail it reaches last:
  the locked scene's `props`, then `performance`. The lock's head (location,
  background, time, light, palette, style, position), the founder's spoken words
  and every prohibition survive, which is the order of importance this decision
  buys. Camera ownership is product-mandated; props and delivery are descriptive.
- A recorded prohibition is never clipped. `must_not_show` entries hold their
  full field budget on every attempt, provider and mode — a refit that shortens
  "a hospital corridor" to "a hospita" sends noise instead of a rule while the
  founder believes the render was told.

## Consequences

- Processing can prove one exact centered zoom, not successful generated orbit
  adherence. Existing footage cannot validate instructions it never received.
- A fixed crop cannot preserve a head or phone already at/outside its edges.
  Source framing remains a generation requirement; no hidden adaptive zoom,
  lateral workaround, fallback model or extra generation path is introduced.
- Pixel resampling costs processing time; the existing encode gate, output
  canvas, optional audio, timeout and soft-failure preservation stay unchanged.
- The fixed-text budget is now nearly spent. The tightest ceiling (HeyGen 4,090)
  clears the saturated floor by about 280 characters, down from about 509, and
  the pin that guards it is recalibrated to 250 rather than deleted. Any further
  fixed instruction has to be paid for by trimming existing wording: there is no
  slack left to absorb it, and the alternative that remains is a provider 400.
- A saturated prompt loses the lock's tail; an ordinary one does not. The
  endpoint test pins the surviving head at the default ceiling and pins
  props/movement/voice against a lock built with room, so a regression that drops
  them from the builder outright still fails.
- See [verification evidence](../../test_reports/camera-owner-split.md) for real
  clip measurements and explicit orbit/head/phone limitations.

## Alternatives rejected

- Keep a lateral crop to fake the orbit: still cannot create perspective and
  silently spends extra magnification.
- Ask generation for zoom too: doubles ownership and cannot guarantee magnitude.
- Promise exact generated spoken-word sync: unsupported by this generation path.
- Auto-reframe unsafe source footage: violates fixed centered geometry and the
  requested instruction to report reliability/framing problems before changes.
