# 0243 — The Stories page is removed; its data and its short-render machinery stay

Status: accepted (supersedes 0227, 0228, 0235, 0236, 0238; partially
supersedes 0240 — the Stories tour — and 0242 — the History story-kit
regenerate offer; the trim decision of 0239 stands and is re-homed by
0244)

## Context

Kasra's ruling (Nov 20 2026, after platform research reported in the
same session): a short hook flowing straight into a demo and a CTA,
posted as a regular TikTok or Reel, beats standalone stories for the
outcome HookForge exists for — views, total clicks, and installs.
Stories reach roughly a tenth of a creator's followers and are not
recommended to non-followers; an Instagram story link sticker earns
on the order of one to three clicks per hundred viewers out of that
small pool; TikTok stories have no click path at all; and roughly
80% of TikTok reach is non-followers arriving through For You, which
only feed posts get. Rated for that growth outcome, the
hook-into-CTA workflow scored 9/10 and the Stories page 6/10 (8/10
judged purely as a story tool). Kasra's words: remove everything
about the Stories page and remake the page for the hook-plus-CTA
purpose. He repeated the direction after hearing the rating, and
chose the full removal over a cheaper replace-in-place after hearing
the deletion count read back: fourteen story-only files, each
needing its own push approval.

The Stories feature was five phases of settled work (ADRs 0227,
0228, 0235, 0236, 0238, 0239, 0240, 0242): a `kind='story'` project
marker, a story plan/kit/screen-text generation layer, a four-type
catalog, a craft check of its own, a page with its own render panel
and kit panel, a spotlight tour, and History's story-kit display.
Some of it is the page and dies with it. Some of it is Kasra's data
and the app's short-render machinery, and must not.

## Decision

1. **The story-only files are deleted** (fourteen): backend —
   `backend/routers/stories.py`, `backend/story_types.py`,
   `backend/test_stories_api.py`, `backend/test_story_text.py`,
   `backend/test_story_types.py`, `backend/test_story_tail_trim.py`;
   frontend — `frontend/src/pages/Stories.jsx`,
   `frontend/src/components/studio/StoryTypePicker.jsx`,
   `StoryScreenTextEditor.jsx`, `StoryCraftCheck.jsx`,
   `StoryPreview.jsx`, `StoryRenderPanel.jsx`, `StoryKitPanel.jsx`,
   and `frontend/src/lib/storyTypes.js`. The tail-trim test file is
   deleted with the set; its coverage is re-homed under the new
   page's semantics in 0244's commit, not lost.

2. **The story surface is removed from the shared files**: the
   `/stories` route and its lazy page import (`App.js`), the sidebar
   Stories link and the Dashboard Stories destination, the stories
   tour, its `/stories` route mapping and its seat in the core
   auto-open set, the Dashboard tour's "cut a story" wording, the six
   story functions in `lib/api.js`, and the story smoke section
   (replaced by absence checks: route gone, link gone, tour gone).

3. **The story generation layer is removed from the backend**:
   `generate_story_plan`, `generate_story_kit` and
   `suggest_story_screen_text` leave `ai_service.py` with their
   schemas, budgets and rules blocks; `assess_story_quality` and
   `STORY_HOOK_MAX_CHARS` leave `creative_quality.py`;
   `CreateStoryProjectRequest`, `GenerateStoryPlanRequest`,
   `SuggestStoryScreenTextRequest` and `GenerateStoryRequest` leave
   `models.py`, and the story fields leave `STUDIO_EDITABLE_FIELDS`
   and `UpdateStudioProjectRequest`; the studio router loses its
   story PATCH branches (story duration pick, story-type validation,
   frame count) and the `story_quality` computation in
   `_public_project`; `server.py` loses the stories router include,
   its configuration, and the completion hook's story-kit scheduling.

4. **The data is preserved, untouched.** No migration deletes or
   rewrites a row: existing story projects keep `kind='story'` and
   their story columns, and existing story renders keep their saved
   `story_kit`. The schema columns stay (SQLite cannot cheaply drop
   them, and they are the record). `kind` keeps `"story"` in its
   vocabulary as a legacy value no surface creates anymore.

5. **History keeps displaying a legacy story render and its kit,
   read-only.** The history list still carries `project_kind` and the
   parsed story kit beside the render, and the card still renders the
   kit in the post-copy slot's place — now through a small read-only
   rendering inside `GenerationHistory.jsx` (the deleted
   `StoryKitPanel`'s display shape, without its controls), because
   the kit is the founder's record of that clip's posting layer. The
   one action that dies is regeneration: the kit can no longer be
   rewritten, and a kit-less legacy story render now says plainly
   that there is no story kit instead of offering to generate one.
   The journey line still names the kit ("Story kit written" / "Story
   kit not written yet"), and `hasCopyContext` still counts a saved
   story kit as copy.

6. **The minimal kit read path is kept, and named.** History's
   display depends on exactly one helper from the deleted router:
   `_parse_story_kit`, the stored-kit parser. It moves to
   `backend/routers/history.py` — its last reader's home — and
   `server` re-exports it for the generation serializer, the same
   arrangement `_parse_post_kit` already has. Nothing else of the
   stories router survives: no endpoint, no writer, no scheduler.
   The post-kit writer's own kind check keeps the two kits mutually
   exclusive for any legacy story render that completes after the
   removal: it grows no post kit, and no story kit is written either.

7. **The short-render machinery is preserved, not removed with the
   page**: `_submit_generation`'s `exact_duration` path and the
   persist's tail trim (0239) stay in `server.py`, still keyed on the
   story rows they were built for in this commit. The new Hook + CTA
   page (0244) is their next caller; its commit re-homes the trim's
   beat rule under the new page's semantics and re-homes the deleted
   tail-trim coverage with it.

## Consequences

- ADRs 0227, 0228, 0235, 0236 and 0238 are superseded: the feature
  they decided no longer exists. ADR 0239's trim decision stands —
  the machinery survives under new semantics (0244). ADR 0240 is
  partially superseded (its Stories tour is gone; the Dashboard tour
  half stands), and ADR 0242 partially (its History story-kit
  regenerate offer is gone; the kit display and the rest of the
  cleanup stand).
- A founder with story drafts keeps them as data: the projects and
  renders remain in the database and the renders remain watchable in
  History with their kits. No page opens a story draft anymore, and
  the wizard refuses nothing — story rows simply have no surface.
- The removal is proven by absence checks, not by silence:
  `backend/test_story_removal.py` pins that no `/stories` or
  story-kit route is mounted and the story generation functions are
  gone, beside preservation checks that a seeded legacy story render
  still answers from History with its kit parsed and its kind named,
  and that the post-kit regenerate still refuses a story render.
