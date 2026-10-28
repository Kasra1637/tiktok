# 0008 — The hook-boundary transition is a face-anchored lean-in, not a zoom-punch

- **Status:** superseded by [0053](0053-generated-orbit-centered-zoom.md)
- **Date:** 2026-10-16
- **Anchors:** `backend/overlays.py` (`TRANSITION_ARC`, `TRANSITION_MAGNIFICATION`,
  `crop_target`, `detect_face_center`, `move_direction_for`,
  `camera_beat_seconds`); `backend/generation_planning.py` (`_CAMERA_MOVE`,
  `camera_move_section`, `character_scene_lock`); `backend/ai_service.py`
  (`STRATEGY_CAMERA_BEAT_JSON_SCHEMA`); `backend/server.py`
  (`_persist_generation_clip`, strategy write-back)

## Context

Every finished render baked one deterministic camera move at the hook boundary,
and it read as a zoom. The lateral reframe was a fraction of the slack the zoom
itself created (`TRANSITION_SHIFT = 0.35`), and the canvas fit leaves the frame
exactly 1080×1920 — so at the boundary there is no spare width at all and every
pixel of lateral travel had to be borrowed from the zoom. On a 1080 frame that
came to **27 pixels, 2.5% of width**: invisible on a phone. Founders asking for
"the camera moves to her right and then her left, and she is still looking
into the lens" were describing something the pipeline could not produce at any
magnitude, because the setting it was using made the move 27px wide.

Two limits shaped the answer.

**A flat reframe cannot change a viewing angle.** The canvas is fully covered;
there are no pixels outside it, so no crop, scale or pan can produce parallax,
a new perspective, or a viewpoint that was never rendered. A true "the camera
is now to their right" is only obtainable from the model. What a crop *can* do is
grow around their face rather than around the middle of the picture, which is what
a lean-in actually looks like from inside.

**There is no speech beat to sync to.** `beat_timeline` is exactly two intervals,
forced by `_enforce_two_sections`, and there is no usable audio to detect one in:
`minimax-h3-max` sends no `generate_audio`, HeyGen's defaults off, and music is
banned in both prompts. The hook/middle boundary was the only interior boundary
in the system.

## Decision

- **The move is a lean-in pivoted on their detected face.** One frame is extracted
  at `beat - 0.15s` and passed through the YuNet detector already vendored for
  the identity reference (`face_crop.py:98`), so magnification grows *around
  them*, and their face comes to rest just above the horizontal centre
  (`TRANSITION_FACE_REST_Y = 0.45`) with their head breaking the top edge. No face
  found falls back to the frame centre — the anchor improves the move, it is
  never a precondition for it.
- **The arc is canvas-relative, and magnification is derived from it.**
  `TRANSITION_ARC = 0.09` of frame *width*, with
  `TRANSITION_MAGNIFICATION = 1 + 2*ARC + ZOOM` (1.25 at the pinned 7% zoom).
  Lateral travel in a crop is paid for in magnification: sliding the window by
  `ARC` needs half the width-slack on the chosen side, which is `(M-1)/2`, so
  `M = 1 + 2*ARC + ZOOM` is the arithmetic that keeps both visible instead of
  letting one silently eat the other. The zoom drops 17% → 7% to pay for it.
- **Eased, not slid.** 0.6s on a smoothstep instead of 0.25s linear. A move at
  constant rate that stops dead reads as post-processing; zero velocity at both
  ends is the cheapest statement that this is a gesture.
- **The beat is committed to in advance, by both consumers.**
  `overlays.camera_beat_seconds` resolves it once — 70% of `hook_seconds`,
  clamped into the hook — and `generation_planning.camera_move_section` and the
  finalize pass both read it back. It is stamped into `strategy.camera_beat` by
  the strategy endpoint, so no migration: `strategy` is already a JSON column.
  Not the hook/middle boundary itself, because a lean that fires on the same
  instant the spoken line lands is one event that reads as a cut.
- **The model performs the gesture; ffmpeg does the framing.** The render prompt
  (`_CAMERA_MOVE`, with a condensed twin for HeyGen) asks for the lean and the
  head beat on that second. Asking for more travel would only double the move,
  since each half covers what the other cannot do.
- **Direction varies per generation**, derived from the generation id so a
  re-run frames identically and a founder's feed does not lean identically every
  time. Unnamed in the prompt on purpose: the model must not fight a side it
  cannot know.
- **`"same camera"` is gone from the scene lock.** It directly contradicted
  this pass. The lock's job — the room, the light, the wardrobe — is untouched
  by a move that stays in the same scene; what replaces it is the more specific
  rule that this one move is the only change of angle.

## Consequences

- **Gain:** a transition that is actually 9% of frame width and visibly an
  angle change, anchored on their face so the lean reads as a person moving rather
  than a frame closing up; the framing holds for the rest of the piece.
- **Cost:** fixed prompt text on every render (`FULL_PROMPT_FLOOR` 3176 → 3581,
  `CONDENSED_PROMPT_FLOOR` 1952 → 2102), bought out of descriptive room on the
  tightest ceiling — HeyGen's saturated headroom falls from ~200 to ~110
  characters. One extra ffmpeg frame-extract plus a ~10ms detection per render,
  inside the existing `_FFMPEG_SLOT`. The move is still soft-fail: an unmoved
  clip is a watchable video.
- **A latent bug this surfaced:** `build_segment_prompt`'s last-resort squeeze
  was gated on having room after the fixed floor, which is backwards — a budget
  at or under the floor is precisely when squeezing the variables is the only
  lever. The gate meant a builder handed back a *full-size* over-budget prompt
  and let the submit guard refuse a render that could have been terse.

## Alternatives considered

- **Keep the zoom, make the arc bigger.** Rejected: the arc is bounded by
  `(M-1)/2`. A visible 9% lateral needs ~1.25 total magnification either way;
  keeping 17% zoom on top reaches ~1.35 and crops 35% of frame height out of a
  medium close-up. The zoom was traded down instead.
- **Ask the model for the whole orbit and drop the ffmpeg pass.** Rejected: the
  model cannot be trusted with timing (`backend/overlays.py:29-37`), the arc would
  not land on the beat, and nothing would guarantee a move at all. It also cannot
  be the only move — a gesture and a reframe are different jobs, and only the
  second of them can be pinned to a frame.
- **Real sub-beat timing from the plan.** Rejected as too large for the gain:
  it means relaxing `_enforce_two_sections`, changing the review UI, and
  refitting the smoke fixtures — to reach a precision the model would still not
  honour. Revisit if audio ever becomes reliably present.
- **Detect the beat from the clip's own audio.** Rejected: unreachably
  unavailable. Two of three providers return no audio, the third defaults off,
  and detection would have to run in the finalize path before a single-shot
  destructive pass.
- **One fixed direction.** Rejected: every video in a founder's feed leaning the
  same way is what made the arc read as a template rather than as a shot.