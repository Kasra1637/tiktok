# 0236 — The full Stories flow: direction, editors, preview, render, kit

Status: superseded by 0243 (the Stories page is removed)

## Context

Kasra ordered the Stories feature on Nov 19 2026 and delegated its
six design questions to platform research; the settled plan
(`hookforge-stories-plan.md`, sections 4 and 6) shapes the frontend
as one stacked canvas, not a wizard. Phases 1–3 landed the backend
(a story is a `studio_projects` row with `kind='story'`, 0227; the
stories router creates, plans, renders and kits it, 0228) and the
page shell (0235): the picks, the saved draft, nothing below them.
This phase builds the rest of the flow on that page — direction,
plan and editors, the craft check, the safe-zone preview, the
render, and the story kit — reusing the wizard's own components
wherever the wizard already solved the problem, so a story feels
like the same studio, not a second one.

## Decision

1. **The direction section is the wizard's, reused whole.** The
   card below the picks holds the camera setup pick (the wizard's
   own AppSelect options and framing notes), `DirectionSelect` for
   location and wardrobe, and `PresenterPhotoControl` for the
   presenter's photo — driven by `useWizardDirections` exactly as
   Create Video drives it, with `angle: null` (a story has no
   content angle). ADR 0220's behavior comes with the hook, not
   re-implemented: the option lists are keyed on the camera setup,
   so a fixed camera is offered indoor locations only, and a saved
   location the fixed camera cannot use is named in the section
   (`story-direction-location-ineligible`) while the pick reads
   empty — never silently rewritten, and flipping back to handheld
   restores it. The reducer grows the wizard draft's `edit-field`
   action to carry the hook's dispatches, so direction picks ride
   the page's existing autosave like every other edit. The photo
   comes from the chosen app profile, as in the wizard: attaching
   one writes the profile's `character_reference` asset the render
   gate reads.
2. **The plan is one click, and the frame-length pick is here.**
   "Generate plan" calls phase 2's plan endpoint — click only
   (ADR 0122); opening a draft spends no model call, and the smoke
   suite pins that. Pending edits are flushed through the autosave
   first, so the plan is written from the saved direction, type and
   length; the returned row is adopted whole. The 5/10/15
   frame-length pick lives in this card and takes over ADR 0235
   decision 6's rule: the reducer's type change now merges into
   pending edits instead of recomputing them, and the length
   follows the type only while the effective length still IS the
   old type's default — a length picked here is the founder's.
   Announcement stories get a minimal optional countdown date,
   passed to the plan call. The plan doc's optional content-angle
   seed stays out: it is not part of this flow's scope, and the
   endpoint already honors a stored angle if one is ever set.
3. **The editors are the wizard's editor patterns.** The hook line
   rides `HookLineEditor` (with its clearer-hook rewrite), the
   script the spoken-line frame family — the `.post-kit-cover
   spoken-line-frame` around a textarea, with `ScriptRewrite`'s
   "Remake the script" beside it — both writing through the draft
   edits and the autosave, exactly as typed text does in the
   wizard. The screen text gets its own editor on
   CoverTextEditor's suggest-and-accept pattern (ADR 0145): a
   suggestion is shown, never applied, and accepting writes it
   through the same edit. Its field enforces the settled cap —
   80 characters, 14 words — by refusing the over-cap keystroke
   and naming the cap, so an over-cap text can never reach the
   autosave, the plan, or the kit. The screen text is a native
   text STICKER in the kit, never burned into the video; the
   sticker plan the plan returned is listed read-only beside the
   editors, labeled as placed at posting.
4. **One backend gap closed: the screen-text suggestion.** Phase 2
   shipped no way to suggest screen text, and the wizard's cover
   suggestion endpoint writes cover text under cover rules
   (35 characters) — wrong law for an 80/14 sticker text. The
   stories router gains `POST /stories/projects/{id}/screen-text-suggestion`,
   advisory and writing nothing, backed by
   `suggest_story_screen_text` in `ai_service.py` on
   `generate_cover_text`'s honesty contract: grounded in the
   profile facts, the angle block and the type's brief under the
   story text rules block; one bounded correction naming the
   failed rules, then a `RewriteRefusal` the endpoint surfaces as
   a 422. It refuses an empty answer, an over-cap answer, a
   fragment under the craft check's own three-word floor for
   standing alone, an echo of the current text, and a copy of the
   spoken hook. A hook-video project gets the router's "not a
   story" 400, a missing project a 404. Backend-tested like the
   phase-3 gap closure (0235), and recorded here for the same
   reason.
5. **The story craft check is displayed, never re-scored.** Phase
   2's `story_quality` already rides the project payload;
   `StoryCraftCheck.jsx` prints it in the app's craft-check style —
   the four fixed checks (first-second hook, screen text stands
   alone muted, one idea per frame, sticker plan present), their
   evidence, the passing count, and each failing check's next
   step. Display only: no scorer is touched, and the check stays
   advisory — it gates nothing, as 0228 settled.
6. **The preview is a CSS phone frame with both platforms' safe
   zones.** `StoryPreview.jsx` is DOM/CSS only, no canvas: the
   finished clip when one exists (its poster before that, a quiet
   placeholder before either), the screen text placed as the
   sticker it will be — upper third, below the handle zone — and
   the settled safe zones drawn as quiet dashed guides behind a
   platform toggle: Instagram top 250 / bottom 340 / sides 65 px,
   TikTok top 240 / bottom 660 / sides 120 with its right rail
   (300 px below y≈840), scaled from the 1080×1920 canvas. The two
   platforms' furniture differs too much for one burned-in
   position, which is the same fact that makes the text a sticker.
7. **The render panel is modeled on GenerationPanel, not reused.**
   The plan is explicit that its readiness gate is coupled to
   wizard strategy state a story does not have, so
   `StoryRenderPanel.jsx` is its own component on the same
   patterns: the model and resolution picks with their per-project
   persistence, the single-pass ceiling named before the click,
   one idempotency key per render intent, the indeterminate bar
   with the stage checklist and elapsed clock — never a percentage
   (ADR 0140) — under story stage labels, the poll chain that
   never retires a live render (failures stretch the interval and
   narrate from the third, ADR 0171), the durable URL for playback
   and download, the storage-error alert with its retry, and the
   branded second-render confirmation (ADR 0212). Its gates are a
   story's own, each named in words on the panel: a plan (hook
   line and script — the server 409s without one), the presenter
   photo, and no unsaved edits, since the render reads the saved
   plan. The submit goes through phase 2's generate endpoint with
   the frame's own seconds, so a 5-second question frame renders
   and bills at 5, never at the hook-video clamp's 8 (0228). The
   page holds the generation row as its own state — the panel
   writes it, the preview and kit panel read it — and because the
   kit is written by a background task at completion, a completed
   row without one is re-read a few times before the panel settles.
8. **The story kit panel is the post kit's sibling, never the
   post kit.** `StoryKitPanel.jsx` mirrors `PostKitSection`'s
   shape — local kit state synced from the row, per-row copy
   buttons and Copy all through `useCopyButton`, regeneration
   through the kit's own endpoint with the current kit kept on a
   failure — and renders the story kit only: caption, the accepted
   screen text verbatim under a "native text sticker" label, the
   sticker plan with each entry's platform, wording and
   placement, and the posting checklist. A null kit renders
   nothing. The two kits stay as separate as phase 2 made them
   server-side: a story render never grows a post kit and a hook
   video never grows a story kit, and this UI offers neither panel
   the other's endpoint.

## Alternatives considered

- **Reuse `GenerationPanel` behind a flag.** Rejected by the plan
  and on inspection: its gate reads wizard strategy state
  (`strategyStale`, the render-half angle machinery) that has no
  story meaning; a flag would thread story exceptions through the
  hook-video path every future change must re-check. A sibling on
  the same patterns keeps both gates honest.
- **Suggest screen text through the cover endpoint.** Rejected:
  the cover's 35-character law would refuse legitimate sticker
  text and bless text that breaks the 80/14 cap's intent; the
  suggestion has to be judged by the story's own rules.
- **Burn the screen text into the render.** Rejected by the
  research (0235's plan, section 6): the platforms' safe zones
  conflict, and a native sticker stays movable at posting. The
  preview exists precisely to show placement without burning.
- **Let the screen-text field save over-cap text and flag it.**
  Rejected: the cap is a settled format rule, and a flag would
  still let the autosave carry text the kit would then print
  verbatim. Refusing the keystroke keeps every downstream reader
  honest by construction.

## Consequences

- Stories v1 is complete end to end: pick an app and a type, set
  the direction, generate the plan, edit the words, preview the
  frame against both platforms' zones, render at the frame's own
  length, and post from the kit — all on one stacked canvas in the
  app's own design system.
- Phase 5 stays a fast follow, NOT in this commit: multi-frame
  sequences (capped at 3) and the History Story chip and filter.
  Nothing here pre-builds them; the kit and preview speak of one
  frame because v1 renders one frame.
- The wizard is untouched: every reuse is by import, and the one
  shared-hook behavior change is none — `useWizardDirections` is
  consumed as it stands, its dispatches landing in the story
  reducer's new `edit-field` action.
