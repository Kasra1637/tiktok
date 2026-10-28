# Camera ownership split — verification

## Scope

- Strategy schema, normalization and strategy-generation prompt:
  [ai_service.py](../backend/ai_service.py).
- Verbatim selfie starting shot, full/condensed orbit-and-gesture instruction,
  preserved final-phone handoff: [generation_planning.py](../backend/generation_planning.py).
- One exact centered processing zoom: [overlays.py](../backend/overlays.py).
- 70%-of-hook timing and fresh-download-only application:
  [server.py](../backend/server.py).
- Regression checks: [test_ai_json_calls.py](../backend/test_ai_json_calls.py),
  [test_generation.py](../backend/test_generation.py),
  [test_overlays.py](../backend/test_overlays.py),
  [test_recovery_sources.py](../backend/test_recovery_sources.py).
- Decision: [ADR 0053](../docs/adr/0053-generated-orbit-centered-zoom.md),
  superseding ADR 0008. No frontend implementation, provider selection, identity
  routing, script budgets, dependencies, or unrelated workspace edits changed.
  No commit, push, deployment, cloud upload or paid render was performed.

## Ownership confirmed

The AI prompt asks for one small left/right orbit to three-quarter at unchanged
camera-to-face distance, then hold, and one short story-specific actor gesture
**when the story begins**. It explicitly prohibits generated push-in, pullback
and zoom. There is no numeric generated-motion timestamp or spoken-word sync.
The requested starting shot is verbatim in both full and shortened render prompts.
Metre-based camera/framing fields no longer override it.

`camera_beat` contains only direction and gesture; legacy `at`/arc are discarded.
Both directions and a short gesture survive saturated prompts for every eligible
provider, including HeyGen's sacred-script path. Provider ceilings remain 6,800
(H3/H3 Max) and 4,090 (HeyGen). Existing ceiling and opening-performance regression
assertions remain intact; camera additions are paid for by equivalent condensed
wording, not a raised ceiling or weakened test.

Processing performs one inverse-coordinate centered resampling, not a lateral
crop, arc or face-following pan. Total magnification is exactly 1.10 by default,
with a permitted 1.08–1.12 setting. There is no lateral scale allowance. For a 3s
hook it starts at 2.1s, completes at 2.7s, then holds. Other hook lengths use
`0.7 * hook_seconds`; saved strategy timestamps cannot override this. The
existing fresh-download gate prevents a second zoom on a saved canonical clip.

## Real-pixel regression

An added static-grid regression failed against the interrupted implementation:
FFmpeg's dynamic scale + crop kept the crop at its initial origin, producing a
top-left zoom despite nominal center expressions. At frame 66 a line expected
at x=118.40 appeared at x=122.50. The production processing entry point now uses
one fractional inverse-coordinate mapping about the frame center. The same
regression passes, measuring both axes before start, through smoothstep, at the
1.10 endpoint and at the final frame. A 120px grid becomes 132px, not 150px.
The output remains 1080x1920 with unchanged duration. This test runs real FFmpeg,
not only command-string assertions.

## Three existing real clips (copies only)

All were copied before processing. Each copy ran through actual
`rescale_to_canvas_sync` then `apply_camera_move_sync`; source files were not
rewritten. Hook length was explicitly set to 3s for this processing experiment,
not inferred from audio or claimed to be these older clips' creative timing.

| Clip | Content | Source size | Canvas duration before/after | Result |
|---|---|---|---|---|
| `7d4cb61e4680a859` | Creator selfie | 720x1280 | 13.908s / 13.908s | Encode succeeded, no warnings; source framing not head-safe |
| `a369ade95b3c15ee` | Two actors in kitchen | 1080x1920 | 8.682s / 8.682s | Encode succeeded, no warnings; observed male actor head/chin preserved at sampled start/end/final frames |
| `5ce9592c-8cf5-4719-b2f4-3cb0840faf2f` | Hand-held phone composite with test-pattern screen | 1920x1080 | 6.050s / 6.050s | Encode succeeded, no warnings; phone body visible in sampled final frame |

Every output is 1080x1920. Optional audio remains present. Compare corresponding
source/output frames to separate processing geometry from motion already in the
clip. Affine registration on nine sampled times per clip (before start, ramp,
endpoint, hold and final frame) measured:

| Clip | Maximum scale error vs smoothstep target | Maximum estimated center drift |
|---|---:|---:|
| Selfie | 0.0000636x | 0.086px |
| Kitchen | 0.0000636x | 0.087px |
| Hand/phone composite | 0.0000704x | 0.086px |

At 2.7s and the last frame, measured horizontal/vertical scales are approximately
1.1000. These small residuals are registration/resampling noise, not lateral
travel. The 29.91fps phone clip starts at the first available frame after 2.1s
(2.106s) and reaches the held zoom at approximately 2.708s, as expected for
frame quantization.

Local binary proof artifacts (ignored runtime output, not source changes):
[comparison contact sheet](../backend/storage/generated/camera-review/real-clip-comparison.jpg),
[metadata](../backend/storage/generated/camera-review/real-clip-results.json),
[pixel measurements](../backend/storage/generated/camera-review/all-frame-metrics.json).

## Framing and orbit limits — not a full visual acceptance pass

- The older selfie source already crowds/cuts the hair/top of head at some
  sampled times. Centered zoom can crop it further. **The never-crop-head
  requirement is not proven on that source**, and no adaptive recentering or
  reduced-zoom workaround was added.
- The kitchen footage has no final phone pickup, and the selfie never brings a
  phone into view. Neither can prove the desired actor-to-CTA phone handoff.
- The third clip is a hand/phone composite with a synthetic screen, not a newly
  generated actor performance. It demonstrates phone-body preservation on that
  existing framing, not generated final-phone compliance.
- No available actor clip was generated with the new orbit instruction. No
  new paid provider render was submitted, so **new generated orbit reliability
  is unverified**, not passed or judged reliable from older footage.
- New generation instructions keep full head/chin/phone in the central 88%,
  inside the 89.29% area retained at the maximum 1.12x setting. This is a prompt
  requirement, not an automatic guarantee of model adherence. Fresh actor
  renders still need head/chin and final-phone acceptance review.
- These limits were reported before adding any camera workaround. None was
  introduced.

## Checks actually run

- `python -m pytest backend/test_overlays.py -q`: **28 passed**, including real
  FFmpeg grid and duration/pixel processing tests.
- Combined prompt/finalization/storage regression run: **338 passed, 1 failed**.
  Failure was the shortened opening wording no longer carrying an existing
  literal requirement. Restored the required wording (not the assertion) and
  remeasured the prompt floor.
- Final affected prompt rerun:
  `python -m pytest backend/test_generation.py -q -k 'OpeningPatternInterrupt or PerProviderPromptBudget or FinalPhoneFraming'`:
  **36 passed**. This includes the repaired failure, measured floors, every
  provider ceiling, both orbit directions and final-phone retention.
- `node frontend/scripts/check-imports.cjs`: **133 files, no import problems**.
- `node frontend/scripts/check-frontend-logic.cjs`: **passed**.
- `node frontend/scripts/check-render-smoke.cjs`: **333 passed**.
- `git diff --check`: passed after removing a trailing blank-line issue.

The complete backend suite and fresh remote video generations were not run.
Existing dependency deprecation warnings remain; no test assertions were weakened.
