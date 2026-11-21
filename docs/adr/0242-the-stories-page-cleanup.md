# 0242 — The Stories page cleanup: honest labels, one length, named places, story kits in History

Status: accepted; partially superseded by 0243 (History's story-kit regenerate offer is removed with the stories router; the kit display stays, read-only)

## Context

Kasra reviewed his own screenshot of the shipped Stories page
(Nov 20 2026) and ordered a cleanup, then added two items in
follow-ups. Eight items, all on surfaces ADRs 0235–0239 built:

1. The render panel's model label read "one render, up to 15s" —
   a hook-video truth on a frame of 3–5 seconds (ADR 0238).
2. The frame's length stood three times on one screen: the type
   card ("Frame length 4s"), the frame-length pick, and a helper
   under the pick restating the default.
3. The direction refresh failure rendered the backend's raw
   parenthetical — "(Direction options: model returned no content
   (finish_reason=length))" — beside the dropdown.
4. The drafts list showed type, frame length and date only, so
   two drafts of one type read as the same draft twice.
5. The fixed-camera direction notice said "the saved place"
   without naming which place it meant.
6. The script's "Remake the script" control sat ABOVE the script
   box, beside an explainer line, while the hook's "Suggest a
   clearer hook" sits under the hook box with no explainer.
7. In Generation History, a story render's card offered the
   "Generate post copy" button, whose endpoint refuses stories
   with HTTP 409 "This is a story render — regenerate its story
   kit instead." — a dead end, because History offered no story
   kit.
8. Kasra's ruling: "When a user clicks the Regenerate button on
   a Story Kit inside the Stories page, screen text should also
   regenerate, not just the captions."

## Decisions

- **Item 1 — the label was two literals, not one shared string.**
  The "one render, up to Ns" wording lives as a separate literal
  in `GenerationPanel.jsx` and in `StoryRenderPanel.jsx`. The
  story panel's now reads "one render at the frame's own length";
  the wizard's is untouched — the ceiling is true for a ~15s
  presenter segment. No model names change.
- **Item 2 — the pick is the one place the length is set and
  stated.** The helper under the pick is removed outright: its
  whole content was the length (the type's default and what the
  pick means), so nothing non-length was lost. The type cards
  keep their default-length note — before a type is chosen there
  is no draft and no pick, and the card is what explains the
  choice; once a draft exists the pick states the length. The
  length now appears in at most the card and the pick, never
  with the helper restating it as well.
- **Item 3 — the founder-facing detail is the plain sentence.**
  `POST /app-profiles/{id}/direction-options/refresh` now answers
  "AI direction options failed. Please try again." with no
  parenthetical. The raw error is not lost: `_log_model_call`
  records every failed call with its error in the server-side
  model-call ledger before the endpoint converts it (verified in
  `backend/db.py`), so the diagnosis stays where debugging reads
  it. The endpoint serves the Create flow too; the plainer error
  is correct in both, and the frontend renders the detail
  verbatim, so no frontend change was needed.
- **Item 4 — a draft is named by its hook line.** The drafts list
  rows already carried `hook_line` (the project list serializes
  the whole row via `_public_project`), so this is frontend
  only: a planned draft's row shows its opening spoken line, a
  draft with no plan yet shows "No plan yet" in its place. Type,
  length and date stay as they were.
- **Item 5 — the notice names the place, in both surfaces.** The
  sentence now reads "Your saved place, '…', is not an indoor
  location, so it is not offered for a fixed camera. …" with the
  saved location's own value inside the quotes. The notice JSX
  is a per-page literal (the direction behavior is shared via
  `useWizardDirections`; the sentence is not), so `Stories.jsx`
  and `CreateVideo.jsx` each name the place the same way.
- **Item 6 — the remake stands under its box, unexplained.** The
  explainer line ("Or remake the script in one go. …") lived in
  the shared `ScriptRewrite` component and is removed from it,
  which cleans the Create flow's Review page identically — the
  hook's assist carries no explainer and is understood, and the
  suggestion itself arrives with accept/dismiss, so the safety
  the line narrated is visible at the moment it matters. The
  placement was Stories-local: Review already stood the
  component under its script box, so only `Stories.jsx` moved —
  the control now sits directly under the script box, matching
  the hook pattern. The "The story is heard as much as read…"
  line under the Stories script box is untouched (Kasra ruled
  it stays), and the accept/dismiss flow is unchanged.
- **Item 7 — History offers the story kit, in the post copy
  slot's place.** No new endpoint was needed: the
  generation-scoped story-kit regenerate
  (`POST /generations/{id}/story-kit/regenerate`, ADR 0228)
  already existed — History simply never called it. What was
  missing was the row's knowledge: the history list now selects
  `g.story_kit` and `p.kind AS project_kind` and parses the kit
  beside the post kit, so a card can tell a story render from a
  video render. A story card renders `StoryKitPanel` in a solid,
  always-expanded section where the post copy section would
  stand (pairing with Plan context under the same ADR 0153
  rule), or the dashed generate offer — "Generate story kit" —
  when no kit exists yet; the journey line's kit item names the
  story kit and walks to it. The Post copy button and
  `PostKitSection` never render for a story render, and
  `hasCopyContext` counts a story kit as copy, so the
  with/without split and deep-link resolution treat a kitted
  story as the copy-carrying render it is. The 409 guard in
  `post_kit.py` stays as the safety net underneath.
- **Item 8 — kit regeneration refreshes the screen text.** The
  regenerate endpoint now runs `suggest_story_screen_text`
  first — the same call the editor's own Suggest button offers,
  under the same 80-char / 14-word caps and sound-off doctrine —
  and builds the kit from a project view carrying the new text,
  so the kit's screen text, its caption (written against the
  screen text) and its sticker plan are all built from the text
  the founder will actually post. Both model calls complete
  before any write; only then are the generation's kit and the
  project's `screen_text` saved, so a failure on either side
  answers 502 and changes nothing (ADR 0180's atomicity sense).
  The answer carries `screen_text` beside `story_kit`;
  `StoryKitPanel` hands it to `onUpdated`, and the Stories page
  adopts it into the screen-text editor through the normal draft
  edit. The standalone Suggest flow (advisory, accept-to-apply)
  is untouched, the completion-time kit writer still writes the
  first kit from the accepted text — only regeneration
  refreshes — and History's regenerate (item 7) shares this
  endpoint, so it inherits the behavior: the project still
  updates server-side even though History has no editor to show
  it in.

## Pins

- Backend: the refresh endpoint's plain 502 detail
  (`TestDirectionRefresh`); the regeneration's screen-text
  refresh and both failure directions' atomicity, plus the
  history list's kind/kit shape (`TestStoryKit`,
  `TestHistoryNamesTheStoryKind` in `test_stories_api.py`).
- Smoke: the model label (source-pinned per panel), the length
  stated by its pick alone, drafts told apart by hook line, the
  named place on both direction surfaces, the remake under its
  box with the explainer gone and the heard-as-read line kept,
  and the two History story-kit checks (kit shown, kit offered).
- Jest: `ScriptRewrite` renders no explainer; a story-kit row
  resolves to the with-copy side of History's split.
