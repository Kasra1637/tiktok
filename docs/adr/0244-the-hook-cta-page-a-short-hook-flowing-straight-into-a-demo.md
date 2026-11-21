# 0244 — The Hook + CTA page: a short hook flowing straight into a demo

Status: accepted (partially superseded by 0248 — the sidebar link is removed; the page is reached from Create Video's flow switcher and the Dashboard card)

## Context

ADR 0243 removed the Stories page on Kasra's ruling: a short hook +
demo + CTA posted as a regular TikTok/Reel beats standalone stories
for views, total clicks and installs (stories reach ~10% of
followers and are not recommended to non-followers; an Instagram
story link sticker earns roughly 1–3 clicks per 100 viewers over
that tiny pool; TikTok stories have no click path at all; ~80% of
TikTok reach is non-followers via For You). He rated the
hook-into-CTA workflow 9/10 for that outcome and directed the page
be remade "fully suitable for the purpose of hook plus a short hook
four five second video hook attached with a CTA," with the workflow
and feature set optimized for views, clicks and installs.

The name is Flash's working label, offered on the call that ordered
the build; Kasra approved it the same evening — "I love the name
too" (Nov 20 2026). It is the page's name, not a placeholder.

## Decision

1. **The page.** "Hook + CTA", sidebar label "Hook + CTA", route
   `/hook-cta`, placed where Stories sat — directly after Create
   Video in the sidebar and the Dashboard destinations. One stacked
   canvas of section cards in the fork-page shape (ADR 0118), not
   the wizard: App, Moment and direction, The hook, Render, Demo +
   CTA, Post kit, and the drafts list. Its one job: a founder picks
   their app and gets ONE feed-ready video — a 4–5 second presenter
   hook flowing straight into their demo and CTA — plus its post
   kit.

2. **The workflow, six stages.** (1) Pick an approved App Profile —
   the draft is created on the pick, in the background, calling no
   model (ADR 0122). (2) Direction: camera setup, location,
   wardrobe, presenter photo, through the wizard's own machinery
   (`useWizardDirections`, `DirectionSelect`,
   `PresenterPhotoControl`), fixed-camera indoor rules included
   (ADRs 0219/0233). (3) The hook: one click writes ONE hook line
   plus its render direction. (4) Render at the pick's own length.
   (5) Demo + CTA: the founder attaches the demo (screen recording
   or the ADR 0237 image sequence) and the CTA in the Demo + CTA
   composition, and the export — hook segment + demo/CTA segment —
   saves beside the hook in History. (6) Post kit: the standard
   video post kit, shown on the page and carried in History.

3. **The hook (stage 3).** `ai_service.generate_hook_line` writes
   the line under the hook doctrine, stated for a hook that stands
   alone: open with the GOAL drawn from the app's desired outcomes
   and outcome statements (goal-first, ADR 0182's doctrine), first
   person, a trying-line; never name the place; withhold the
   resolution — the demo that follows is the answer. Grounding is
   the profile facts alone (the story plan's facts dict and the
   shared grounding/goal blocks with no angle). No script, no
   screen text, no sticker plan, no craft check — the story framing
   is gone, and no new scorer is built. The line is held to two
   budgets and one gate: the word budget (4s ≤ 9 words, 5s ≤ 12 —
   ADR 0238's numbers, re-homed from the retired story catalog into
   `ai_spoken.SHORT_HOOK_SECONDS` / `short_hook_word_budget`), the
   character budget (`spoken_budget` for the pick), and the
   finished-sentence gate (ADR 0231) — one bounded correction, then
   a refusal in founder words; an over-long or unfinished line is
   never stored silently. The direction carries the opening-action
   bookends (ADRs 0187/0223): the opening move already in motion in
   the first frame with its snap inside the first half second, and
   a closing beat at the same energy, never a fade. Editing reuses
   `HookLineEditor` and the studio hook-suggestion flow unchanged.
   The endpoint assembles the render strategy deterministically:
   the hook segment carries the line (seconds 4 — see item 5), the
   middle segment is direction only (the closing beat, no words),
   the scene locks from the saved direction.

4. **The render (stage 4).** A new thin router,
   `backend/routers/hook_cta.py`, in the retired stories router's
   shape (`_cfg` injection from the composition root), owns create,
   hook and generate. The generate submits through
   `_submit_generation` with `exact_duration=True` at the pick's
   seconds, so ADR 0239's beat trim cuts the saved file back to
   exactly the pick below the providers' 5-second floor. The render
   panel is the retired story panel's pattern re-homed
   (`HookRenderPanel`): same two models, same poll chain (ADR
   0171), its readiness gate is the hook line itself. The Demo + CTA
   finish reuses `DemoCtaGenerationEditor` — the exact component
   Create Video's finishing step renders — on the same composition
   functions (`frontend/src/demoCta/exportTikTok.js`); the Demo +
   CTA page itself is untouched. The post kit needs no new code:
   these are video projects, so completion writes the standard kit
   (ADR 0234's caption, ADR 0139's hashtags) and `PostKitSection`
   renders it.

5. **Data model.** The draft is kind **"video"** — History, post
   kits and analytics treat its renders as video renders, which is
   the point of the page. The distinguishing marker is a new
   nullable column, `surface` (migration step 9), written
   `'hook_cta'` by this page's create and NULL everywhere else.
   Every existing field was considered and rejected, and the
   rejection is the record: `objective` is a closed vocabulary read
   by the hook rewrite's goal block and the post-kit prompts;
   `cta` is read by `generate_post_kit` as the call to action;
   `tone` is read by the wizard's plan prompts; `story_type` would
   lie by its name on a video row forever. A marker that three
   prompt surfaces read is not a marker. The precedent is ADR 0227
   itself: step 7 added `kind` for exactly this shape of need.
   `hook_seconds` is stored at 4, the shared machinery's widest hook
   window: the render counts the hook's words first against that
   window's ceiling (80 chars), and generation already gates the
   line to the frame's tighter `spoken_budget` (60/75 chars), so
   the line always fits the hook section whole and is never
   re-sliced into a script this page does not have. Drafts autosave
   and list like Stories drafts did (per-app list, deep link), rows
   told apart by their hook line (ADR 0242's pattern).

6. **The beat trim's rule is re-homed (the one behavior change
   outside the new page).** ADR 0239 keyed the beat cut on the
   project's kind ('story'). The persist now reads the generation
   row: a trim is a beat cut when the render was requested AT the
   cut length (`requested_duration == trim_to_seconds`), which is
   exactly what an exact-duration submit records. Every observable
   behavior is preserved and pinned in `backend/test_beat_trim.py`
   (the retired `test_story_tail_trim.py`'s coverage, re-homed):
   a hook-cta beat cut writes no note and records the pick; a
   legacy story row — which recorded the same shape — keeps its
   beat behavior untouched; a legacy hook row (trim target against
   a full-length request) keeps its "Cut down to Xs." note; a
   failed beat cut records the floor length and names what was
   being cut, "story" for a legacy story row, "hook" otherwise.
   ADR 0239's mechanism is unchanged; only its key moved.

7. **The tour.** The stories tour is gone (ADR 0243); this page
   gets its own spotlight tour in the same system, on ADR 0118's
   fork-page pattern: id `hook-cta`, a seat in
   `CORE_AUTO_OPEN_TOURS`, first-run eligibility registered by the
   page (loaded, an approved app picked, no draft open, the app's
   draft list settled empty), "Show me around" replay, seven steps
   walking the six stages — the app pick required, every later step
   optional. ALL TOUR TARGETS EXIST holds.

## Consequences

- The app has one short-form surface again, aimed at the outcome
  Kasra chose: the feed video, not the story. Stories stay retired;
  their data stays readable in History (ADR 0243).
- One new backend surface to maintain (a thin router, one model
  call, one migration), against a page built almost entirely from
  parts that already existed: the direction hook, the photo
  control, the hook editor and its suggestion flow, the render
  panel pattern, the finishing editor, the post kit, the exact-
  duration submit and the beat trim.
- The `surface` marker is deliberately boring: it names where a
  draft was created and nothing else. A future page that needs the
  same distinction writes its own value rather than borrowing a
  prompt-read field.
- Kasra's story drafts and renders are untouched by this ADR, as
  they were by ADR 0243.
