# 0255 — Generated scripts land in their band, and render prompts fit the model

Status: accepted

## Context

Kasra's live failure (Nov 21 2026, Create Video, HeyGen Video):
pressing Generate produced the pre-spend refusal — "This script
and photo assemble a 4099-character prompt, 9 over the 4090
HeyGen Video accepts. MiniMax H3 Max accepts 6800. Cut about 9
characters from the script, or switch to MiniMax H3 Max on the
Generate step — nothing has been charged." His script was 172
characters against the 155 ceiling he had been given for his
video's shape. Nothing was charged — the guard worked — but the
script should never have arrived over its band, and the assembled
prompt should never have landed over the model limit. His rules
for the fix: a generated script never exceeds its ceiling on any
path; for the standard shape, delivered scripts land between 140
and 155 characters, nothing more, nothing less; and the render
prompt must never exceed the model's limit, with the app's own
direction wording absorbing any squeeze — never the script.

Investigation found one hole in each half, plus a number that
does not exist.

**The 155.** No app surface computes 155. Every spoken ceiling
is `spoken_budget(middle_seconds)` — 15 characters per second of
the middle — so a 15-second video's ceiling is 150, 165, 180 or
195 depending on the hook's seconds, and the script target is
`min(150, ceiling)`. Kasra's 172 was in fact UNDER the code's
ceiling for his row's shape (the prompt guard, not the
spoken-fit gate, refused him, so his words had passed at a
ceiling of 180 or more). The 155 he was quoted came from the
conversation around the app, not from the app. His band is
therefore adopted below in the form the machinery can honor on
every governed shape — and for the standard shape it reproduces
his numbers exactly.

**The generation hole.** The plan path enforced its ceiling
(the editorial loop charges an over-ceiling draft), but no
producer enforced a floor, and one producer enforced nothing at
all:

- `generate_video_strategy` stated the ceilings in its prompt
  and accepted the reply as written — its own comment read "No
  wording gate: the strategy is accepted as written." Plan-less,
  its section scripts are the words a render speaks, so an
  over-ceiling middle shipped exactly as generated.
- The whole-script remake was bounded above (its ceiling) and
  never below.
- Nothing anywhere treated an under-length script as a defect,
  though a 90-character script leaves a ten-second middle half
  empty.

**The render hole.** Three faults compounded in
`build_segment_prompt`'s fit, all pinned by a reproduced build —
a fully populated FIXED-camera strategy at the silent-reduced
HeyGen budget (4,090 − 459 for the ADR 0246 silence direction =
3,631), which returned 3,684 characters:

1. The final walk restarted from the wrong scale. After the
   correction loop bottomed out at MIN_SCALE (0.10), the walk
   sized its first step from the current prompt's length as
   though it were unscaled (≈0.83 in the traced case), then
   decayed ×0.7 for only 8 steps — reaching ~0.069, above the
   ~0.03 where that prompt fits — and returned the over-budget
   assembly.
2. The fit's floors were measured on the HANDHELD assembly
   (full 4017, condensed 2475). A fixed camera's own fixed text
   measures 3988 full and 2588 condensed, so every fixed fit
   under-counted its fixed text by 113 (condensed).
3. Even a correct walk stopped at FINAL_SCALE 0.02, but the
   traced assembly's mass — fixed text, absolutes, the sacred
   words, and dozens of scaled fields at their eight-character
   minimums — only settles under that budget below ~0.01
   (measured asymptote 3,616 against the 3,631 budget).

The fallback builder, `build_single_pass_prompt`, had no final
walk at all: a prose-saturated plan at a 3,100 budget returned
3,180. It is unreachable in the shipped flow (the submit path
refuses strategy-less projects first), but its stated contract —
corrected from the measured length until the prompt fits — was
false exactly where a budget was tightest.

## Decision

**The delivery band.** `spoken_targets` now carries the script's
band alongside its target and ceiling: for a middle of ten
seconds or more, `(target − 10, min(ceiling, target + 5))`; for
shorter middles, none — their target is their ceiling, so a
window around it would be most of the line, and a complete
shorter thought there stays a choice. At the standard shape's
150 target the band is exactly Kasra's 140 to 155 (a 15-second
video with a 4-second hook: ceiling 165, band 140–155; with a
5-second hook: 140–150 — never over his 155, never under 140).

**Generation honors the band and every ceiling.**

- The plan's editorial loop charges an out-of-band script like
  an over-ceiling one (`script_band_issue`, stated in both the
  plan prompt and the correction prompt): rewritten on the same
  bounded attempts, refused on the same terms, never shipped.
  The charge is suppressed when the ceiling charge already
  fires — the harder limit names the fix. The craft correction
  may not swap an accepted in-band draft for an out-of-band one.
- The strategy generator fails loudly on over-ceiling words
  when no approved plan binds over them: the hook line and both
  section scripts are checked against the budgets its own
  prompt states, and an over-length reply raises, naming the
  line, its length and its ceiling. No correction re-call — a
  second strategy call costs a full generation, and the
  established pattern for this function is that defects fail
  loudly and the founder retries.
- The whole-script remake takes the band's floor as
  `min_chars`: an under-floor reply joins the existing
  repair-able failures — one bounded correction naming the
  floor, then `RewriteRefusal`. The rewrite endpoint passes the
  floor for the script role from the project's own shape.

**The render fit keeps its promise.**

- The final walk never steps UP: its first step is clamped to
  the scale the correction loop ended at, and it keeps stepping
  until the prompt fits or FINAL_SCALE is reached (the fixed
  eight-step cap is gone; a 24-step bound remains for the
  pathological case).
- The floors are camera-aware: `FIXED_FULL_PROMPT_FLOOR = 3988`
  and `FIXED_CONDENSED_PROMPT_FLOOR = 2588`, measured on the
  fixed assembly the same way the handheld pair was, pinned by
  the same kind of test, and selected by the strategy's camera
  in the scale, the correction loop and the walk.
- FINAL_SCALE is 0.005, low enough for the traced mass to fit
  and still far above a one-character field (`_clip`'s own
  minimum is eight).
- `build_single_pass_prompt` takes the same final walk.
- The guarantee's limit is unchanged in kind: if a prompt's
  unscalable mass alone exceeds a ceiling even at FINAL_SCALE,
  the builder returns its tightest assembly and the submit
  guard remains the backstop.

**The refusal stops blaming the script.** `prompt_ceiling_refusal`
no longer takes `spoken_chars` and never advises a cut. It keeps
the measured headline and the roomier-model sentence, names the
real cause — the app's direction around the words is already
squeezed to its tightest — and points at the levers that exist:
switch to the roomier model, or shorten the scene and direction
on the Hook + Story step and build the strategy again. "Nothing
has been charged" stays. The four pinned refusal tests were
rewritten to the new wording, and one new pin reproduces
Kasra's exact 4099/4090 refusal shape.

## Consequences

- A generated script now arrives inside its band or not at
  all, on every producer: plan, plan-less strategy, remake.
  Under-length joins over-length as a generation defect, which
  is the change Kasra's "nothing more nothing less" asked for.
- The traced fixed-camera silent build fits its 3,631 budget
  with the script and hook byte-identical in the prompt; the
  squeeze falls where ADR 0201 put it — on the app's direction
  wording. The script's sacred protection and the opening
  action's protection class are unchanged.
- Existing test fixtures whose mock scripts sat under the band
  at governed shapes were padded into band across
  test_ai_json_calls.py, test_studio_api.py, test_cover_text.py,
  test_craft_gap_prompts.py, test_behavior_direction.py,
  test_hook_bakeoff.py, test_plan_banned_everywhere.py,
  test_plan_angle_bounds.py, test_hook_voice.py and
  tests/test_spoken_pov.py — mock data only; no assertion's
  intent changed, and the craft-calibrated pairs in
  test_hook_voice.py were re-measured so their totals keep the
  relationships their tests pin. The API-boundary ceiling test
  in test_generation_api.py pins the new refusal wording at the
  submit path, as the unit pins do at the function.
- Untouched, deliberately: the Craft check scorer (Kasra's
  standing rule — generator-side only); the deterministic
  trims in ai_spoken (their refuse-instead-of-cut question is
  a separate pending decision); hand-edited scripts, which
  remain the founder's own words — the render fit still
  protects their renders by tightening direction wording;
  model limits, prices and the model list.
