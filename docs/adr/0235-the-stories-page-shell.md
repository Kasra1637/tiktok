# 0235 — The Stories page shell: nav, route, and a saved draft

Status: superseded by 0243 (the Stories page is removed)

## Context

Kasra ordered the Stories feature on Nov 19 2026 and delegated its
six design questions to platform research; the settled plan
(`hookforge-stories-plan.md`, section 3) shapes the frontend as one
stacked canvas, not a wizard. Phases 1–2 landed the backend: a story
is a `studio_projects` row with `kind='story'` (0227), and the
stories router creates it, plans it, renders it and kits it (0228).
Until this phase none of that was reachable: no sidebar link, no
route, no page.

## Decision

1. **Stories is a destination, placed once and mirrored once.** The
   sidebar gains a "Stories" link directly after Create Video
   (`/stories`, `stories-nav-link`, the Layers glyph) — it is the
   other creation surface, the short-form sibling of the hook video.
   The Dashboard adds Stories as its seventh destination card in
   this same commit, after Create Video, wearing the sidebar's own
   icon and hint, per ADR 0208's rule that the two destination lists
   stay in step. The route rides the protected block as a lazy page,
   like every other studio page.
2. **The page is one stacked canvas.** `pages/Stories.jsx` is a
   `PageFrame` + `PageHeader` over `.surface` section cards — no
   steps, no rail, no sticky bar. Section subtitles carry
   `data-subtitle` at `text-sm` in the shared 55–60 character band,
   and `Stories.jsx` joins the files the smoke suite's subtitle
   budget reads, so the shell's subtitles are held to the wizard's
   standard rather than merely written to it.
3. **The shell is the two picks and the saved draft they make.** An
   app picker (the existing `AppPicker`, approved profiles only —
   the server's `_require_profile_for_studio` gate is the same one)
   and `StoryTypePicker`, a card row in the wizard's pickable-card
   treatment presenting the four settled types with their one-line
   purposes and frame lengths. Unapproved profiles are named in a
   panel under the picker, as the wizard names them, with the review
   itself left on App Profile. The app's existing story drafts are
   listed under the picks, newest first, the open one marked; a
   draft opens from the list or from a `?project=` deep link, and a
   link naming a hook-video project is refused in words on the page
   rather than opened as a story. Generation UI — plan, direction,
   editors, preview, render, kit — is the next phase, deliberately
   absent here.
4. **Saving is the wizard's pattern, minus the ready mark.** A draft
   reducer owns the picks; once an app and a type are both chosen
   the draft is created in the background through
   `POST /stories/projects` (a draft calls no model, so ADR 0122's
   click-to-generate rule is untouched — nothing generates on
   navigation or on a pick, and the smoke suite pins that). Later
   pick changes ride the ~1-second debounced, validated PATCH
   behind the "All changes saved" line. No `markProjectReady` call
   follows the save: a story has no ready gate (0228), so the
   wizard's re-mark would be a write describing an approval that
   does not exist in this workflow.
5. **A profile switch starts a fresh draft; the type survives it.**
   The saved row belongs to the profile it was created under, so
   switching apps resets the draft, exactly as the wizard's
   profile-selected transition does. The story type is kept across
   the switch: a type is a format, not a property of one app, and
   nothing else in the shell is profile-scoped yet.
6. **A type change writes the type's default length with it.** The
   shell offers no frame-length pick (the 5/10/15 pick belongs to
   the plan flow), so the length stored on the row is always a type
   default; leaving the old type's default in place after a type
   change would store a length nobody chose — a 15-second demo
   moment still reading 5 seconds. The PATCH therefore carries
   `story_type` and `duration_seconds` together. The length follows
   only while it still IS the old type's default: a length that was
   picked on purpose (a draft created with an explicit
   `frame_seconds`) is left alone.
7. **The type catalog is mirrored, not served.** No endpoint returns
   the catalog — a project payload carries only the picked type's
   id — so `frontend/src/lib/storyTypes.js` mirrors
   `backend/story_types.py` exactly: the four ids, names, default
   seconds and description strings, verified character-for-character
   against the backend module at build time. The backend module
   stays the source of truth; a catalog change lands in both files
   in one commit. A serving endpoint was rejected for this phase:
   four settled constants do not need a new surface, and the create
   and plan endpoints already validate every id the page can send.
8. **One backend gap closed: the PATCH now validates `story_type`.**
   Creation validated the type against the catalog loudly (0228),
   but the draft PATCH wrote it through the generic string branch —
   an unknown id would have been stored silently and refused only
   later, at plan time, with the founder further from the pick that
   caused it. `update_studio_project` now refuses an unknown
   `story_type` with the same 400 and the same wording as the create
   endpoint; an empty value still clears the pick. Two tests in
   `test_stories_api.py` pin the acceptance and the refusal.

## Consequences

- A founder can open Stories from the sidebar or the Dashboard,
  pick an app and a type, and walk away from a saved story draft;
  reopening the page or following a draft link restores the picks.
- The frontend gains `createStoryProject` and `getStoryProjects` on
  the api object; opening and saving deliberately reuse
  `getStudioProject` / `updateStudioProject`, so there is one read
  path, one serializer and one validated write path for both kinds.
- The smoke suite's sidebar and Dashboard pins now expect eight
  links and seven cards; the new Stories checks pin the route, the
  four type cards, the create-on-pick, the type-plus-length
  autosave, the deep-link open, and the video-project refusal.
- The next phase builds on this shell without moving it: the plan
  and screen-text editors, the direction section, the safe-zone
  preview, the render panel and the story kit panel join the canvas
  as further cards, and the frame-length pick takes over the
  length-follows-type rule in decision 6.
