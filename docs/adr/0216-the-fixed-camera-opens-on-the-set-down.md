# 0216 — A fixed camera opens on the set-down, on a surface the scene itself offers

Status: superseded by 0219 (the set-down opening is reversed on Kasra's order, and fixed camera is indoors-only)

## Context

Kasra (Nov 19 2026) named the opening that performs across his
Instagram and TikTok feeds: the recording is already running while
the person sets the phone down somewhere — the microphone catches
the handling noise of the placement, the frame shakes a little as
it lands — and only then do they get in front of it and start
talking. HookForge's fixed camera (the non-held, propped-phone
setup) opened instead on an already-stationary frame: the phone
was simply *there*, on "a shelf or tripod", and the presenter was
already in position. The most organic first second the format has
was being skipped.

His edge case, ruled on the same call: some moments have no
surface to set a phone on (mid-street). The camera setup's context
should flow into the environment choice — the scene must be
somewhere a phone can plausibly be set down and stay, and a moment
with no resting surface shifts its setting to the nearest sensible
spot instead of forcing the placement.

## Decision

- **The set-down is the fixed opening.** `FIXED_SET_DOWN_OPENING`
  (backend/generation_planning.py, with its condensed twin) is
  emitted for the fixed setup only, inside the camera block —
  after the starting shot it lands in, before the locked-camera
  hold. It states: the recording is already running as the
  presenter sets the phone down on a surface this scene itself
  offers (a table, counter or shelf indoors; outdoors a bench, the
  steps themselves, a low wall, a café table, a fence rail); the
  phone's own microphone catches the soft thump and scuff of the
  landing and the frame shakes and settles, a natural left-to-right
  wobble, as it comes to rest; that set-down is the first second's
  movement (for this setup it *is* ADR 0187's opening movement —
  the payoff beat in seconds 1–2 is the presenter settled in frame
  as the hook lands); then the presenter gets in front of the
  phone and talks. The thump is the recording phone's own handling
  sound, stated as such — the voice-only rule still bans music and
  added effects.
- **The environment rule rides in the same text.** The surface is
  never invented: the scene must be somewhere a phone can be set
  down and stay, and if the story's spot offers nothing to rest it
  on, the same moment is staged at the nearest spot that does —
  the words never change, only the staging. The strategy prompt
  (backend/ai_service.py) carries the same rule where hook_action
  and the scene are actually written, so a fixed strategy opens
  its hook_action on the set-down and picks (or shifts) its scene
  under the rule, instead of the render prompt fighting a strategy
  written around a different opening.
- **Handheld is untouched.** No set-down text reaches a handheld
  prompt, strategy or render; the selfie phone is already in the
  presenter's hand. Spoken words, hooks and scripts are untouched
  everywhere — this is video-prompt direction only.
- **The starting shot drops the tripod.** `FIXED_STARTING_SHOT`
  no longer rests the phone "on a shelf or tripod": the resting
  place is the set-down's business, and a tripod is a piece of
  equipment no scene here contains. The shot states the frame
  only; its framing (head to mid-thigh, headroom, both hands)
  is unchanged.

## Paying for the text (ADR 0053)

The block is setup-conditional, and the measured floors are built
on the selfie default, so FULL_PROMPT_FLOOR (4014) and
CONDENSED_PROMPT_FLOOR (2464) do not move. The cost lands where it
should: on the fixed prompt itself. Unpaid, the growth put the
saturated fixed build 288 characters over HeyGen's 4,090 ceiling
with the script held sacred (4,378 measured). It was paid out of
fixed-only wording that stated a fact twice:

- the condensed header's fixed ending clause ("End on the moment
  the presenter reaches for their phone") — already stated by the
  MIDDLE heading's "end at the reach" and by the handoff block in
  full; the header keeps the download/install ask-ban, which
  appears nowhere else in the condensed text;
- the fixed camera hold's restatements of the frame ("Keep head
  and both hands in frame") and of the phone's place ("the
  recording phone is not in her hands") — a locked camera cannot
  reframe mid-take, so unlike the selfie hold (ADR 0213) the
  restatement buys nothing; the starting shot and the set-down
  each state their fact once;
- the condensed handoff's doubled orientation ("back to camera,
  screen to her") and doubled margins ("clear margins" beside
  "central 88%") — each now stated once;
- the starting shot's "on a shelf or tripod" (above).

After payment the saturated fixed build measures 4,088 at the
4,090 ceiling, and fits every provider ceiling (pinned by
`test_fixed_camera_survives_a_saturated_strategy_at_every_ceiling`).
No provider ceiling was raised and the spoken script's budget was
not touched. The single-pass fallback builder is unchanged: it
carries no starting shot at all (ADR 0213's precedent), and the
submit path refuses a strategy-less project before it can render.

## Consequences

- Fixed renders now open with the phone being set down — handling
  sound, settling frame — and the presenter stepping in to talk,
  on a surface the video's own scene provides.
- A fixed strategy whose moment has no resting surface is written
  (and rendered) at the nearest sensible spot, with the moment
  and every spoken word intact.
- Tests: the selfie-framing suite gains pins for the whole beat
  and the environment rule in both budget modes, for the set-down's
  absence from handheld prompts at both budgets, and for the
  shift rule reaching a fixed prompt built on a no-surface
  (mid-street) scene while a handheld prompt for the same scene
  carries none of it; the strategy-prompt suite pins the set-down
  rule in a fixed strategy prompt and its absence from a handheld
  one.
