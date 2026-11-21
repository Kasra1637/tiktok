# 0228 — The story plan, the story craft check, and the story kit

Status: superseded by 0243 (the Stories page is removed)

## Context

Phase 2 of the Stories build (ADR 0227 settled the shape: a story is
a `studio_projects` row with `kind='story'`; the plan and research
live at `~/workspace/hookforge-stories-plan.md` and
`~/workspace/hookforge-stories-research.md`). This phase lands the
generation layer: how a story frame gets its words, how those words
are checked, how its render is submitted, and what posting layer the
finished render carries. The page arrives in phase 3; this phase is
backend only.

A story is not a short hook video. It is tapped through faster, its
on-screen text must carry the whole message for the muted minority
while the spoken line stays first-class for the sound-on majority,
and its interaction layer — live stickers — cannot exist inside a
render at all. The hook video's plan → strategy → post-kit pipeline
answers none of that directly, so this phase builds the story's own
versions of each piece, reusing the shared machinery (profile facts,
angle grounding, spoken-line rules, the one render path, the kit
write-at-completion contract) wherever the formats genuinely agree.

## Decision

1. **The story plan is ONE generation.** `generate_story_plan`
   (`backend/ai_service.py`) writes the whole written layer in a
   single chat call at the app's one text temperature (0.4): the
   spoken hook and script, the on-screen text, the two physical
   beats, the location, and the sticker plan. It is grounded in the
   profile facts and the picked angle exactly as
   `generate_creative_plan` is grounded — and deliberately NOT in
   verdict feedback (ADR 0227: story rows take no verdict and never
   enter the ADR 0124 bundles, in either direction). There is no
   separate strategy generation: the plan endpoint
   (`backend/routers/stories.py`) assembles the render strategy
   deterministically from the plan's own beats and the saved
   direction picks, stores it on the project, and the generate
   endpoint rebinds the project's current words into it before
   submitting — the wizard's edit-then-render discipline, without a
   second model call or a staleness gate. A story has no
   ready-marking step: its readiness is the plan itself (no plan, no
   render) plus the same model, resolution, and single-pass checks
   every submit makes.

2. **The spoken lines keep the shared doctrine, tightened.** The
   plan prompt carries `_spoken_line_rules_block()` unchanged —
   goal-first, plain loose words, finished sentences, no app-feature
   words — with the story's own additions on top: the hook's move
   lands inside the first second (one finished sentence of at most
   45 characters), and the two lines together are budgeted by
   `ai_spoken.spoken_budget(seconds)` for the frame's own length.

3. **The screen text has its own rules block and settled caps.**
   `_story_text_rules_block()` sits beside `_cover_text_rules_block()`
   — same family (first person, the moment up front, the answer
   withheld, never a copy of the spoken hook) with the story's
   inversion: the text must carry the WHOLE message with the sound
   off. The caps are the research-settled build numbers, 80
   characters / 14 words, defined once in `backend/story_types.py`
   (`STORY_TEXT_MAX_CHARS` / `STORY_TEXT_MAX_WORDS`) and re-exported
   by `ai_service` beside the cover text's. A reply over the caps
   gets one bounded correction; a reply still over raises — the cover
   text's honesty contract. The text is a native text sticker the
   founder places at posting, never burned into the render.

4. **The story craft check is a fixed four-check list, beside the
   scorer, never calibrated.** `assess_story_quality`
   (`backend/creative_quality.py`) checks what the format demands:
   the hook inside the first second (one finished sentence of at
   most 50 characters — at the brisk hook pace the app budgets by,
   the longest opening whose move cannot help but land first); the
   screen text standing alone muted (present, inside the caps, a
   real message rather than a fragment); one idea per frame (the
   spoken words inside the frame's own `spoken_budget`, the script
   at most two sentences); and the sticker plan present (an entry
   naming a sticker and its wording). It is advisory, recomputed on
   read like the spoken report, and gates nothing. The existing
   scorer is untouched, and — under Kasra's standing ruling — this
   check is never calibrated or learned against outcomes, exactly
   like the craft check it sits beside.

5. **Story fields live on the project row; the kit on the render.**
   Migration step 8 (`_migration_0008_story_fields`) adds
   `studio_projects.story_type / screen_text / sticker_plan /
   frame_count` and `generations.story_kit`, each only when missing.
   The story fields ride the existing project PATCH (in
   `STUDIO_EDITABLE_FIELDS`, not the text fields — no plan-version or
   staleness side effects), with `sticker_plan` written as JSON and
   `frame_count` as an integer by their own branches, and a story
   row's `duration_seconds` PATCH keeping the settled 5/10/15 values
   exactly rather than passing through the hook-video clamp. Story
   rows carry `hook_seconds = 2`, the shared machinery's floor: the
   first-second rule lives in the prompt and the craft check, and
   the row only needs a value the shared repairs accept.

6. **A story frame renders at its own seconds.** `_submit_generation`
   gains a keyword-only `exact_duration=False` parameter; the stories
   router passes `True`. This is the one deviation from "submit
   unchanged", and it is forced: the submit's duration clamp
   (`template_library.clamp_duration`) floors at 8 seconds — the
   hook-video catalog's deliberate minimum — so a settled 5-second
   question frame would silently render at 8 seconds, a length
   nobody chose, billed at the longer length. With the flag, the
   validated pick (5/10/15, checked at the endpoint) is used as-is;
   the model's own maximum still caps it a few lines later. Every
   other caller leaves the flag off and clamps exactly as before.
   The render prompt gains a STORY FRAME section
   (`story_brief_section` in `backend/generation_planning.py`) only
   when the strategy carries a `story_brief` — the type, the frame's
   seconds, and the placement discipline the native text sticker
   needs (the presenter never gestures over the lower third where
   the founder's sticker will sit). Hook-video prompts are
   byte-identical: the section returns "" when the brief is absent.

7. **The story kit is the post kit's sibling, and the two never
   mix.** At completion, `_apply_persist_outcome` schedules
   `_schedule_story_kit` beside `_schedule_post_kit`, with the same
   write-once, best-effort, deferred contract; each writer checks
   the project's kind, so a completion grows exactly one kit.
   `generate_story_kit` assembles rather than generates: the accepted
   screen text ships VERBATIM, the sticker plan is the plan's own
   (normalized to platform / sticker / wording / placement, with the
   platform asymmetry stated in the plan prompt — countdown,
   questions and slider stickers are Instagram-only, both platforms
   have a poll, and TikTok carries a countdown's date in the screen
   text and spoken line instead), the checklist is the settled
   posting guidance written in code (native-sticker placement, the
   sticker step, one or two stories on a posting day, plus the
   picked type's follow-through line), and only the caption is a
   model call — short, story register, and deliberately NOT ADR
   0139's hashtag machinery: a caption carrying hashtags is corrected
   once, then refused. The regenerate endpoint mirrors the post
   kit's: click-only, loud on failure, and a hook-video render is
   refused with the reason.

## Alternatives considered

- **Reusing the plan → strategy two-step for stories.** Rejected:
  the format is one frame reviewed once; a second generation would
  double the latency and cost of the fastest surface in the app to
  produce a strategy the plan already determines.
- **Clamping story durations like hook videos.** Rejected: the
  clamp's 8-second floor exists for the hook-video catalog; applying
  it to stories silently breaks the settled 5-second frame. The
  `exact_duration` flag keeps the clamp the default for every
  existing caller instead of moving a shared floor.
- **Scoring a story with the existing craft scorer.** Rejected: its
  categories measure a hook-and-middle pair against a demo handoff;
  a story's demands (first-second hook, muted-readable text, one
  idea, a sticker plan) are a different list. A separate fixed check
  keeps both honest.
- **Letting the kit's model write the checklist or re-draft the
  screen text.** Rejected: the text was accepted by the founder and
  ships verbatim, and settled guidance rewritten per render would
  drift. Only the caption — the one field that is genuinely copy —
  is generated.

## Consequences

- `backend/routers/stories.py` owns the story endpoints
  (`POST /stories/projects`, `.../plan`, `.../generate`,
  `POST /generations/{id}/story-kit/regenerate`), configured from
  the composition root at call time like the studio router, so test
  patching of `server.<name>` intercepts story calls too.
- Tests: `test_story_text.py` pins the caps in both homes, the rules
  block's content, the plan's grounding, budget and correction
  contract, the sticker normalization, the announcement asymmetry,
  the kit's verbatim text and hashtag refusal, and each craft check
  passing and failing. `test_stories_api.py` pins create/plan/
  generate/kit end to end against the fake provider — including one
  render submitted at exactly 5 seconds with the STORY FRAME brief
  in its prompt, a story completion growing a story kit and never a
  post kit, and a hook-video completion growing no story kit.
  `test_schema_migrations.py` pins step 8. All were watched failing
  before the change.
- Phase 3 builds the page on these endpoints; phase 5's sequences
  ride the `segment_index` the generate request already carries.
