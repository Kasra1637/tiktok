# 0233 — Fixed camera restates the angles indoors and fits the action to the room

Status: accepted (extends 0219 and 0224)

## Context

Kasra's ruling on Nov 20 2026, confirmed repeatedly on a voice call.
Angles are generated BEFORE the camera setup is picked — the direction
section sits below the angle picks (ADR 0220) — so an angle can be
written around an outdoor moment ("feelings at a coastline", "in a
courtyard", "courthouse" becoming a living room in his examples). When
the founder then switches to Fixed, everything that follows must be
indoor, with everything else the same — and nobody is forced to re-pick
angles: Kasra considered a scroll-up-and-repick prompt and rejected it,
settling on automatic restatement plus a note instead.

ADR 0219 already made the fixed camera indoor-only in the plan prompt
(`fixed_location_rule`), the strategy prompt ("THE SCENE IS INDOORS")
and the render prompt (`FIXED_STARTING_SHOT`), and ADR 0224 restated
the template cards' staging line. Two gaps remained. First, the angle
cards themselves — the first thing the founder reads on the step — still
showed the angle exactly as written outdoors, the same class of
contradiction 0224 fixed one section down. Second, 0219's rule governed
the PLACE only: nothing anywhere told the plan, the strategy or the
render that the staged ACTION must also fit the room, so an angle whose
moment is walking a coastline, swimming, running or flying could be
staged indoors in name while its action stayed impossible there.

## Decision

1. **The angle display restates indoors, display-side only.** The angle
   list read takes `camera_setup` as a query parameter and the
   generate/regenerate requests carry it as an optional field, threaded
   the way ADR 0224 threaded the recommendations path:
   endpoint → `_serialize_profile_angles` → `_serialize_angle_row`, a
   keyword argument whose default is the old behavior. For a fixed
   camera, `angle_scene.indoor_restatement` overlays the serialized
   fields (label, audience, problem, promise, feature, emotion,
   outcome, claims) with their restated text. The STORED angle is never
   rewritten; the content fit is still scored from the angle as written;
   flipping back to Handheld — or any caller that passes no setup, like
   the profile page and the manual create/PATCH responses — reads the
   angle exactly as written. The template-recommendations response's
   `angle` key takes the same threading, since that endpoint already
   holds the setup and restates its cards (0224); the tailor endpoint's
   serialization deliberately stays as written, because there the angle
   is a judgement input and fit is judged against the angle as written
   (0224's principle).

2. **The restatement is a bounded phrase table, not a prose rewriter.**
   `angle_scene.restate_text_indoors` swaps known outdoor place phrases
   for their indoor counterparts: framed phrases swap together with
   their preposition ("at the courthouse" → "in the living room",
   "at the coastline" → "by the large window", "in the courtyard" →
   "in the atrium"), and bare nouns swap where the surrounding words
   already fit ("the courthouse queue" → "the living room queue"),
   preserving first-letter case. The overlay applies only when the
   setup is fixed AND the angle's scene — the moment's place per
   `video_scene`, the same scene the template cards read — is outdoors.
   The boundary is stated plainly: a place the table does not know
   (a café, which this module's own detection reads both ways across
   the codebase, is deliberately left alone) passes through unchanged,
   and compound nouns are guarded only where cheap ("park bench",
   "garden gate" keep their noun). The note in Decision 3 still tells
   the founder the staging is indoors in that case. The scene detector
   also gains three outdoor words it was missing — coastline, coast,
   courthouse — which closes the same detection gap for the template
   cards' staging flip (0224), not just for this display.

3. **A note tells the founder.** When the setup is fixed, the angle
   section shows a small note in the app's voice — "With the fixed
   camera, these angles are staged indoors — an outdoor place shows as
   its indoor version." — beside the list's own controls. The wizard
   passes the draft's saved setup into the angle step the way it
   already feeds the template cards, and the angle hook re-reads the
   list when the effective setup changes (a pure read, ADR 0122; row
   ids are stable, so the pick survives; flipping back restores the
   written text exactly).

4. **The chain was verified stage by stage.** Template cards: sound
   under 0224, confirmed and left alone. Plan, strategy, render: the
   place rule was already enforced at all three under 0219 and its
   pins stand. The activity gap was real at all three — no stage said
   the action must fit the room — and is closed by Decision 5.

5. **The staged action must fit the room (0219 extended from place to
   activity).** The plan prompt's fixed rule, the strategy prompt's
   indoor block, and the render prompt each gain the same rule in
   their own register: every staged action must be one that can happen
   in that room — no swimming, running or flying indoors; an
   outdoor-only activity is staged as its indoor-plausible equivalent
   keeping the feeling (a coastline walk becomes pacing by a large
   window or through an atrium); in a bedroom, only bedroom-plausible
   actions. The spoken words never change — hook and script stay
   exactly as approved; only staging and direction adapt. The plan and
   strategy prompts carry the full instruction, since they write the
   staging and the actions; the render prompt carries the compact
   backstop inside `FIXED_STARTING_SHOT` ("…and every action is one
   that fits that room", +46 characters — the saturated fixed prompt
   at HeyGen's 4,090 ceiling re-measures at 4,055 and still fits).
   Enforcement is generator-side only, exactly as 0219 is enforced;
   the craft scorer is untouched, and a handheld prompt carries none
   of it — handheld behavior is unchanged.

## Consequences

- A fixed camera's angle cards, template cards, plan, strategy and
  render now all tell one indoor story, and the founder learns it
  from a note on the angle section rather than by contradiction.
- The stored angles, the fit judgement and every spoken word are
  untouched; the restatement exists only in a fixed camera's display
  and evaporates when the setup flips back.
- Tests: `test_angle_scene.py` pins the restatement (fixed + outdoor
  restates place phrases only, everything else byte-identical by
  omission; handheld, indoor and unknown-place angles untouched; case
  preserved); `test_template_library_api.py` pins the list endpoint
  restating under `camera_setup="fixed"` with the stored row proven
  unchanged by re-reading without it; `test_ai_json_calls.py` pins the
  activity-fit wording in the fixed plan and strategy prompts and its
  absence handheld; `test_generation.py` pins it in the fixed render
  prompt, saturated at every ceiling and absent handheld; the jest
  suite pins the API client carrying the setup, and the smoke suite
  pins the note appearing under Fixed and vanishing under Handheld.
  Every new check failed before the change.
