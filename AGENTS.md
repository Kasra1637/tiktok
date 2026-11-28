# AGENTS.md — HookForge (TikTok studio)

Dark-studio web app: FastAPI backend (`backend/`) + CRA frontend (`frontend/src/`).
One render path, single-pass video generation via OpenRouter.

## Commands (run from repo root)

- Backend tests: `python -m pytest backend/ -q` (media cases need ffmpeg/ffprobe
  on PATH; a missing ffmpeg is a setup failure, not a reason to skip).
- Frontend gates: `yarn --cwd frontend run check` (imports, logic, demo-cta draft,
  contrast gate, render smoke, tour targets — not Jest or the build). Focused smoke:
  `SMOKE_ONLY='wizard' node frontend/scripts/check-render-smoke.cjs` — a filter
  that selects zero checks verifies nothing.
- Frontend tests/build: `CI=true yarn --cwd frontend test --watchAll=false` /
  `yarn --cwd frontend build`.
- Match your harness's shell (Git Bash or PowerShell); preserve failure exit
  status when redirecting/piping. In PowerShell chain with `; if ($?) { ... }`.
- Local setup: `README.md`; ownership: `docs/architecture.md`; change/test
  matrix: `CONTRIBUTING.md`; incidents/deploy/rollback: `docs/operations.md`.

## Architecture (ownership map)

- `backend/server.py` — composition root (ADR 0111): includes the domain
  routers, re-exports their helpers, and owns the render lifecycle.
  `_submit_generation` is the ONLY render path; `_studio_identity_references`
  resolves the photo. Keeps the mutable DB config the tests rebind.
- `backend/db.py` + `backend/schema.py` — SQLite/Turso primitives, the
  versioned schema (recorded baseline plus numbered steps, ADR 0120) and the
  jobs-queue claim/lease helpers; `db.py` reads config through a `_server`
  back-reference. Domain
  routers (`routers/brands.py`, `routers/studio.py`, `routers/assets.py`,
  `routers/history.py`, `routers/hook_cta.py`, `routers/post_kit.py`,
  `routers/health.py`, `routers/media.py`) own their endpoints and resolve test-patched `server`
  names at call time via `_cfg`; none may import `server` back (ADR 0111).
- `backend/ai_service.py` — all OpenRouter calls; `VIDEO_MODELS` is the model
  catalog; `generate_video` submits, `describe_provider_refusal` classifies.
  Pure clusters live in `ai_spoken.py` (spoken budgets/trimming/story
  checks), `ai_strategy.py` (strategy normalization), `ai_text.py`
  (HTML→text) and `ai_media.py` (image data URIs) and are re-exported here
  (ADR 0112); the transport + chat flows stay, so the patched
  `_chat_json`/temperature/config names keep resolving on this namespace.
- `backend/angle_policy.py` — pure normalization, source grounding and lexical
  diversity. `backend/template_recommendations.py` — pure fit/shared notes and
  Problem/Promise relevance. `backend/character_policy.py` — pure identity rule:
  the on-screen person is never given a gender, role or pronoun (ADR 0089).
  Same pure contract — no HTTP, AI, auth or persistence imports; `test_architecture.py`
  parametrizes the 5 it imports — for `backend/scene_consistency.py` (ADR 0092 /
  0103 / 0104: `reconcile_scene`; Movement ≥600 is advisory, Props stays a hard
  block), `backend/final_beat.py` (ADR 0093 / 0097: selfie strip; spoken words
  never rewritten), `backend/opening_move.py` (ADR 0090: validate / repair the
  opening move), `backend/angle_scene.py` (ADR 0084), `backend/face_crop.py`
  (YuNet crop + defocus, fallback to the original image), and
  `backend/hook_prompting.py` (extracted prompt builders, re-exported by
  `server.py`). `backend/observability.py` + `backend/routers/health.py` own
  `/api/metrics` — process-local counters, observability only, never a gate.
  Old adapter names are compatibility aliases.
- `backend/video_providers.py` — capability source of truth (limits, identity
  routing, prompt ceilings). Swapping providers is env config, not redesign.
- `backend/generation_planning.py` — prompt assembly + `is_recoverable_error`
  (retry policy). Prompt budget + sacred-script rule live here.
- `frontend/src/components/GenerationPanel.jsx` — the render panel; errors via
  `lib/errorMessage.js`. Its own Generate is the only one that submits: the
  panel registers its ready/flight faces with the page for the wizard's
  sticky bar (restored by ADR 0229, superseding 0218), and the bar's click
  only scrolls to the panel (ADR 0169); the model,
  resolution and render handler live here and nowhere else. Card
  padding/spacing tokens live in `index.css`.
- `frontend/src/demoCta/` — canvas overlay system; `overlays.js` motion is a
  pure function of video time (export matches preview), faces come from
  `OVERLAY_FONTS` (vendored woff2 only). See ADR 0007. The second slot also
  takes an image sequence (ADR 0237): `imageSequence.js` composes its
  frames (each still's picked motion — still by default, ADR 0354 — plus
  crossfade, pure in sequence time) and `imagePlayer.js`
  stands in the append element's place for transport; the export
  synthesizes that segment instead of decoding a track.
- `frontend/src/pages/CreateVideo.jsx` — four-step wizard orchestration:
  App Profile → Audience & template → Review & submit → Demo + CTA (the
  finishing step renders the Demo+CTA editor loader on the project's newest
  finished render; ADR 0121). At desktop widths the wizard stands one step
  at a time, as pages; below, the canvas stacks (ADR 0141). Selection UI lives in
  `components/studio/SelectionPanels.jsx` (the only `AngleSelector`); the Visual
  & audio direction section renders on the Audience & template step, below the
  angle and goal picks (ADR 0220), and its dropdowns and plan-phase narration
  live in `ReviewPanels.jsx`. Project writes stay
  in the page. `pages/wizardDraft.js` owns coupled draft transitions;
  `hooks/useWizardTemplates.js` owns recommendation/tailoring state,
  `hooks/useWizardAngleStep.js` owns the angle-step lifecycle (ADR 0112).
  Other steps navigate to the angle control, not a second selector.
  Review/editor siblings: `components/studio/HookLineEditor.jsx` (spoken-line editor),
  `pages/useWizardDirections.js` (stale-request guard), `pages/PendingSaveCard.jsx` (storage retry),
  `lib/vitals.js` (LCP/INP/CLS, window-exposed, no sink), `lib/recentDraft.js`
  (sidebar draft link), `pages/DemoCtaStudio.jsx` (starts blank ADR 0082).
- `frontend/src/pages/GenerationHistory.jsx` (+ `historyPolling.js`,
  `historyRepair.js`) — confirmed row snapshots, per-row polling that
  never retires a row still awaiting the provider (ADR 0174, extending
  0171's panel rule: failures back off, the row resolves on its own,
  no dead-end state) and durable-save recovery; a stopped browser
  check is not a provider failure.
  The generating skeleton mirrors the finished card. At desktop widths the
  media column is capped (288px) so the clip stands at about half its
  former height and the record takes the freed width; the columns stand
  equal, and the record fills by its natural spacing rhythm, never by
  distributing filler between its blocks (ADR 0149, refining 0143). The
  identity summary rides at the head of the record, not under the clip —
  the media column carries only the stage, Download and Work rows
  (ADR 0150). Post copy and Plan context stand in the record as solid
  sections — always rendered in full, never disclosures (ADR 0151).
  On a full standard card the two sections pair side by side (the
  pair template engages at a 1080px card-container breakpoint) and
  the feedback block rides in the media column under the Work row,
  so a standard card renders no Results & actions disclosure;
  compact cards keep their feedback in the record (ADR 0153). The
  pair is a property of the two slots, not of the kit's presence:
  a finished kit-less render's empty post-copy panel stands in
  the Post copy column beside Plan context (ADR 0184).
  A view toggle switches the list between the full cards and
  compact scan rows (ADR 0159): a scan row carries the hook,
  status and the verdict in the row, mounts the full card when
  opened, and the choice persists via `lib/historyView.js`. In
  Post copy and Plan context the field labels stack above their
  values (`.post-kit-row-stacked`); Plan context carries no listen
  control, and the post kit carries no written-for line.
  `components/PostKitSection.jsx` + `backend/routers/post_kit.py` own post
  kits; routers receive DB functions from `server` and never import it back.
- `backend/feedback.py` — the whole-video verdict bundles and their
  prompt section, plus the posted-performance record math (dated
  snapshots, the craft score frozen at submit) (ADRs 0055/0070/0071,
  0117's record half, 0124).
- Persistence: Turso refuses local SQLite writes on a configured outage
  (ADR 0083). `backend/storage_service.py` + `backend/media_signing.py` own R2
  durability and signed playback — a provider URL is not a durable link, and a
  finished render can still carry `storage_error`.
- Other surfaces: `backend/auth.py` (Clerk; authz stays at HTTP/DB entry
  points), and onboarding tours in `components/onboarding/` +
  `lib/onboarding/tours.js`. The Video Upscaler is removed (ADR 0152); the
  single-segment audio passthrough it shared with the Demo + CTA export
  lives at `frontend/src/demoCta/audio.js` under the export's ownership.
  Schemas: `backend/models.py` owns `STUDIO_EDITABLE_FIELDS` and row
  serialization; `backend/template_library.py` + `backend/recommendation_tags.py`
  own curated vocab / tag matching. Operator tooling — NOT a render path:
  `backend/repair_failed_saves.py`, `backend/recovery_report.py`,
  `backend/live_sample.py`, `backend/mp4_samples.py`, and the Media
  offload (`backend/pipeline.py`, `backend/posters.py`,
  `backend/modal_worker.py`). `_submit_generation` stays the sole submit.
- `frontend/src/pages/Landing.jsx` — the public marketing page. The
  "Everything between idea and posted" grid carries SIX feature cards
  (ADR 0156) — facts, aim, plan, render, demo, results; the templates
  and craft-grade beats fold into the plan card, whose description
  carries all three. Card descriptions sit in a 130–135 char band
  (ADR 0380, superseding ADR 0156's uniform 160), smoke-pinned with
  the six exact titles; titles are short and no
  longer share one length. The hero figure carries the story
  animation (ADRs 0165/0168, refined by 0172/0175/0176/0178) — inside a
  phone frame the process plays across two pages (page one
  types the store link into its field — ADR 0175 restored the
  typing after Kasra saw page one live without it; the field
  is lit with the input-well's focus treatment while the link
  types and "Research my app" rests dimmed until it wakes for its
  click; page two checks off the four video creation steps,
  each check drawing itself in, and carries the only Generate
  the video click; then the finished video is generated in
  page two's own center, between the steps and the button, as
  one framed stage — the filled presenter in her scene as its
  only subject, the play badge seated on her, the progress
  bar filling across its run — the video carries no words at
  all: ADR 0178 deleted its hook lines and its closing line
  outright, as not relevant — and nothing follows it: page two is the last
  page, the loop holds on it assembled, and reduced motion
  rests on it (ADR 0176, which retired the full-screen video
  stage and its separate end card)), pure CSS on one 13s
  clock, the phone carrying depth (weighted shadow, indigo
  glow, glass sheen) and the beats sliding and scaling
  between pages — and the phone's controls mostly mirror the
  app's real UI (ADR 0173): Generate the render panel's accent button,
  a done step the wizard rail's filled check badge, smoke-pinned
  so the mockup follows whenever the real treatments change —
  Research is the one deliberate departure (ADR 0178): the
  mockup's button wears Generate's accent treatment under its
  own shorter "Research my app" label, because the mirrored
  secondary surface read wrong live; the real app's button
  and label are untouched —
  under ADR 0177's placement rule (`.hero-shot`, shown at every
  width — beside the pitch at lg, stacked below the whole pitch
  under it; superseding ADR 0158's hide rule); the How it works
  strip below keeps the five steps. Every
  entrance in the app is the one rise-and-settle (ADR 0165).
- `frontend/src/components/AppPicker.jsx` (`PILL_SELECT_CLASS`) +
  `formControls.js` (`CONTROL_CLASS`) — the shared control skins. Every
  filter control in the app wears the one filter treatment (ADR 0161):
  `.filter-control` in index.css states the rest, hover, focus, open and
  active states, an active filter (a non-default value, a pressed toggle)
  wears the selection indigo via `data-active` / `aria-pressed`, and the
  app picker marks active only in its filter form, never as a page's app
  switcher. Every dropdown in the app is app-drawn
  (`frontend/src/components/AppSelect.jsx`, ADRs 0162/0163): a native
  select's open menu belongs to the browser and ignores the page, so
  the History copy/status/sort dropdowns, the app picker and the
  form-field dropdowns alike (the render panel's model and resolution,
  the camera setup, the direction picks, the Demo + CTA video fit)
  render a button plus the app's own listbox, whose chosen option wears
  the same selection indigo. Form fields are not filters — they keep
  `CONTROL_CLASS` as the button's skin instead of the pill — but they
  draw their menus the same way; no native `<select>` remains.
- Voice: `frontend/src/lib/listen.js` + `ListenDock` (mounted by `AppShell`) —
  browser `speechSynthesis` only (no text leaves the device), text built from
  the data model, never the DOM. See ADR 0088.

## Conventions

- Conventional commits, imperative, with a why-body on non-trivial changes.
- Commit or push only when requested — a push to `main` can deploy production.
- Spacing tokens live in `frontend/src/index.css` (`.surface`, `.inset-panel`);
  never add `p-*` to card JSX. Token changes update `design_guidelines.md`
  same-commit.
- Layout reset (Nov 27 2026, Kasra's order): one title spacing and one equal
  alignment inside containers — group headings carry the same 0.5rem gap below
  them (`.eyebrow` in index.css), section titles take the shared SectionCard
  rhythm, and everything inside a container starts at the container's inset.
  Nothing inside a container is centered; ADR 0381's app-wide centering is
  removed. The `.section-pair` start line and ADR 0364's divider geometry stand.
- Bare sections + direction trio (Nov 27 2026, Kasra's order): HookSnap's
  Choose an app and Render the hook stand bare (`bare` on SectionCard — no
  `.surface` chrome; heading, testid and the ADR 0356 collapse stand
  unchanged), its Place and wardrobe lays Voice, Location and Wardrobe on one
  line in `.section-trio` (the pair mechanism carried to three areas;
  `.section-pair` itself untouched), and the voice pick's long talking-mode
  line is removed whole on both pages (the silent note stays).
- Hook picks as sliders + the Opening pick (Nov 27 2026, Kasra's order): on
  HookSnap only, Tone and Shape render as drag sliders (`picksAsSliders` on
  HookPicksControl; the default pill rendering is unchanged) and a third
  pick, Opening (App's choice / Action / Feeling), joins them in the trio.
  Opening rides the draft as `hook_opening` (migration step 12, closed set
  validated in the update path) into `_hook_steering_block`: "action" opens
  on the verb in motion, "feeling" on the felt sensation, "auto" steers
  nothing — every existing hook rule stands.
- Direction groups as sliders (Nov 27 2026, Kasra's order): HookSnap's trio
  groups wear the same slider (`asSlider` on VoiceModeControl and
  DirectionSelect; Create converted too by the unified spread below) —
  Voice's two choices are the
  stops (the knob rests on the standing mode while no pick stands, ADR
  0361), Location and Wardrobe carry their two standing picks as stops
  (ADR 0365's last-seat rule included), and New options still reveals the
  full set as pills.
- The unified toggle + the saved check (Nov 27 2026, Kasra's order): every
  pick-one-of-a-few control wears the one PickSlider groove — a fixed-width
  track, a dot per stop, the indigo grip-pill knob, a tint fill to the knob,
  and only the current pick's name under it (no stop-names row, no smaller
  duplicate line). It stands on HookSnap (Focus included — the pop-up form
  stands only in the control's unused default rendering), Create's Camera
  setup and direction section, both render panels' resolution (768p still
  the default value), the Demo + CTA editor's five pick groups, and
  History's copy and status filters; the sort stays a dropdown and the
  verdict thumbs stay. A setting's note (the Voice silent note) shows only
  after the user changes that slider this session, never for a standing
  pick. Autosave writes no words anywhere: each completed save fires
  `signalSaved()` and the one green check in the top chrome
  (SaveSavedIndicator) remounts and pulses anew; a failed autosave still
  names itself in the old seats.
- Left defaults + slider explainers (Nov 27 2026, Kasra's order): every toggle
  rests on its left stop by default — a fresh project (both creates) is born
  with the voice on talking, superseding ADR 0248's silent start; a stored
  pick is never rewritten, only the unset state resolves left. Every
  PickSlider carries one brief explainer per stop (`lib/pickExplainers.js`,
  fixed texts 55–65 chars, smoke-pinned), shown only after the user changes
  that slider this session; the silent stop's explainer replaces the long
  silent-voice sentence, and the note that remains on HookSnap is the
  text-to-speech handover alone.
- The pick text's quiet face (Nov 27 2026, Kasra's order): the pick's name
  (`.pick-slider-value`) and its explainer (`.pick-slider-explain`) stand in
  one matched voice everywhere the PickSlider stands — the same 0.875rem
  size, both at regular weight 400 (the name's old bold 600 is gone), the
  name in the foreground tone and the explainer one tone quieter in the
  muted foreground, smoke-pinned in the hook-picks slider check. The
  explainers themselves stay — a toggle like Focus means nothing with no
  word on what it selects.
- Demo + CTA library picker + second-clip sequence (Nov 27 2026, Kasra's
  order): both clip slots' add doors open the Assets library pop-up
  (`demoCta/LibraryPicker.jsx`, the pop-scrim portal shell) listing the
  active screen recordings and screenshots as tappable thumbnails. The
  base takes one video pick (replaces; images shown, never pickable);
  the second slot's media model is now one ordered sequence of entries
  (`demoCta/appendSequence.js`) mixing clips and stills — multi-pick in
  the pop-up, reorder by strip drag or arrows, remove from inside the
  pop-up, and per-sequence settings stay per-sequence so a one-entry
  sequence behaves exactly like the old single second clip (one video
  still plays through the real element; stills keep the ADR 0237
  player; mixed runs play and export through per-item segments painted
  as the second clip). Pre-sequence drafts (appendMedia/appendImages)
  migrate to entries at restore. Files dropped on the second clip's
  area insert at the hovered tile's seat and file to the library like
  any device add; sequence rows are named Item 1, Item 2, … with the
  kind carried by the row's icon, never by the slot's name.
- Demo + CTA editor fit (Nov 27 2026, Kasra's order): the preview column
  fits at working heights with no scrollbar of its own — the frame
  spends the column's full leftover height (no 0.75 factor) from a
  176px floor, and `--demo-cta-chrome` budgets the player's real height
  (trim timeline included) instead of the 144px bar it grew from. The
  column and the scrubber strip share one 8px inset, so the seek knob
  and ticks — centred on their percentage — land whole at 0%/100%
  instead of being halved by the player's `overflow-x-clip`. Trim
  tracks wear the `.trim-timeline` density of `.inset-panel`, and the
  second clip's sequence stands as a wrapping row of item tiles with
  the add tile last.
- Posted link, full-card History, switch glide, HookSnap score (Nov 27
  2026, Kasra's order): the render panel carries the History card's
  verdict + TikTok link section (`components/PostedLinkSection.jsx`)
  directly below the Demo + CTA button — one row of verdict toggles,
  link field and Save link on the same `setVideoVerdict` /
  `setTikTokLink` saves, so a winner reads the same everywhere.
  History is full cards only: the Full/Compact toggle, the compact
  scan rows and their CSS are removed (ADR 0159 superseded;
  `lib/historyView.js` stands orphaned until a deletion round).
  PickSlider switches settle with a 180ms glide on knob and fill,
  gated on not-dragging and on reduced-motion no-preference. HookSnap
  shows Create's Craft card (`components/CraftCheckCard.jsx`, shared)
  beside the hook line; the /hook response scores the hook alone with
  the model evaluator, exactly as the studio single-project GET does.
- History one list + filter row (Nov 27 2026, Kasra's order): the copy
  filter is removed whole — the `copy` URL param is read and written
  nowhere, the two copy sections and their per-side counts are gone,
  and every render the search and server filters leave stands in one
  run of full cards; `hasCopyContext` still drives everything inside
  the cards. The status slider's All statuses stop carries no
  explainer (the line was removed; the other five stand). The top
  filter row holds only the search, the app picker and the sort,
  adjacent in that order; the status slider stays in the secondary
  group, and the More filters button reads active off it alone. The
  unified-toggle note above now covers History's status filter only.
- Significant trade-offs add or supersede a record in `docs/adr/` same-commit
  (see `docs/adr/README.md` for the rules).
- Fail loudly, never silently: no fallback model, no invented lookalike, no
  generic take. A refusal must name the next step. A gate that cannot
  act names what's missing in words instead of dying silently — in the
  wizard, the rail segments and the sticky bar do the navigating (ADR 0229).
- No claim-safety system exists (ADR 0119): wording is never checked,
  reported on, or refused anywhere in the app; the angle's bounded-by lines
  are prompt guidance for the generator only, never a gate on a result.
- The strategy drift gate diffs raw values only (ADRs 0142/0146): the
  frontend helper (`frontend/src/lib/strategyStaleness.js`) mirrors the
  server diff over the payload's `direction_saved` — the saved direction
  before any display transform — and the two sides must never disagree.
  `_public_project`'s location display transforms (scene fill, object-clause
  strip, fragment repair) must never feed a comparison.
- A claimed persist execution is bounded (ADR 0148): every path (detached,
  inline, startup drain) executes through `_execute_claimed_persist_job`,
  which runs under `_PERSIST_EXECUTION_LIMIT_SECONDS` (1800). A bound-expired
  save fails its job through the ordinary bookkeeping and lands on the row
  as a named `storage_error` — completed, retry offered — never an eternal
  `generating`. The detached heartbeat extends the lease only inside the
  bound; it protects a slow save, it cannot keep a hung one alive.
- The wizard's sticky bar is back (ADR 0229, superseding 0218 and
  restoring the bar rules of 0144/0147/0169): the rail segments and
  the bar own step navigation, and each section's own buttons own its
  actions — nothing inside a section jumps the user to another step
  (gap panels name the gap in words instead). The render panel's
  Generate, beside the model and resolution, is the only button that
  submits: the bar wears its face on the render half but its click
  only scrolls (ADR 0169), the Review halves switch by their own
  tabs, and a render in flight is narrated by the panel and the bar's
  registered flight face alike. The strategy and render panels
  register their bar actions with the page; the finish step carries
  no Back arrow (ADR 0217), and the bar stands down there over a
  finished render.
- The craft scorer (`backend/creative_quality.py`) rewards first person and
  penalizes only diary framing; the story arc ends open, the demo completes
  it, and the cover text is scored with the hook (ADR 0145). Since ADR 0312
  the rendered report is the text model evaluating the pair against this
  checklist's own rubric (dimensions, cues, reachable caps); the
  deterministic scorer is the fallback and still serves list/mutation
  payloads and generation's internal comparisons. Generation
  prompts follow the same doctrine — 'I' is the goal, never a ration. The
  plan drafts `cover_text` to the shared cover best-practice rules; Review
  shows it as plain text and regenerates it only as a suggestion the founder
  accepts — never auto-saved, never hand-edited in place — and the post kit
  ships the accepted cover verbatim. Generated text wears one highlight,
  never a box (ADR 0258, superseding the cover frame of ADRs 0186/0191):
  the hook and script fields beside it stand in `.generated-highlight-field`
  (index.css, token `--generated-highlight`) around the unchanged fields,
  so the spoken words read as finished lines, and the same wash
  (`.generated-highlight`) backs every generated output — the post kit's
  caption and cover, Review's cover value, suggestion previews, History's
  demo brief and the legacy kit's texts. The highlight family carries no
  quotation marks and shows nothing on click (ADR 0191's rules, carried
  over), and the demo brief stands in the same wash; History's own hook
  (the card's title) and Plan context's picked facts stay plain text.
  The wash stands only where words are (ADR 0264): the field seats
  render only for a non-blank value (an empty field is a plain field,
  placeholders never earn the wash), the highlight hugs its text
  (fit-content; the hook seat shrink-wraps), and the wash merges in
  half a second after the words land — a background-only fade on the
  same signature ease, declared only inside the reduced-motion
  no-preference gate.
- Settled layout decisions are not open questions (ADR 0141): Review stays
  one column at every width, Analytics stays a calm ledger (its Clip
  results and Renders cards stand at one height, its Clip results read
  as stacked entries whose short fields never wrap (ADR 0209), Renders per week reads as one row per week with a dot per
  render under a plain busiest-week sentence, and the expanded Clip
  results ledger scrolls inside its bound rather than growing the
  pair, ADRs 0159/0160; Clip results stands open and never collapses,
  and the Analytics skeleton fades into the content it gives way to,
  ADR 0166),
  and the wizard is paged at desktop widths, stacked below. Render progress is narrated in
  words with an elapsed clock — never a staged percentage (ADR 0140) —
  and its three stages name the real backend phase (ADR 0170):
  'submitted' is "Sending your approved script", 'generating' is
  "Rendering your hook + story", and 'generating' with the row's
  persist_in_flight flag set is "Saving your finished video"; the
  checklist alone carries them (no header line, no headline stage
  line, the timer beside the bar).
- Feedback learning is one verdict on the whole video (ADR 0124): a single
  thumbs up or down per finished video on its History card, with the whole
  bundle (spoken words, post kit, opening visual, audio identity) frozen
  at verdict time — that bundle is the only signal that steers the plan
  and strategy prompts, fits the goals (ADR 0126), and ranks the templates
  (ADR 0127: the scorer reads verdict bundles only, and the presented set
  prefers structurally distinct templates). The plan's hook must carry the
  certified outcome's key terms, enforced in the editorial loop (ADR 0127).
  Per-element ratings were removed because neither
  the founder nor TikTok can attribute a posted result to one element of
  the video; do not reintroduce them. Posted snapshots and the craft
  score frozen at submit are the record (ADR 0117), never steering.
- Review autosave is a validated server write; the Demo + CTA editing document
  is browser-local — never call browser storage a cloud backup.
- One logical change per commit. A behavior or default change is an explicit
  product decision named in the message, never bundled inside a fix; copy
  sync rides in its own commit so behavior stays reviewable and revertable.
- Red before green: a behavior fix ships with a regression check that fails
  without it. Suites staying green proves nothing changed, not that the new
  behavior works.
- Wizard subtitles carry `data-subtitle`, stay `text-sm` and 55–60 chars,
  enforced by the smoke suite. Loading indicators narrate fresh work and
  unmount on settle *and* error; lists arrive staggered, collapsing to
  instant under reduced motion.
- `memory/` is an empty stub, not a system. `memory/PRD.md` is the historical
  Unified Location spec (ADR 0090), implemented. `test_reports/` holds committed
  review evidence; scratch logs stay untracked.

## Before changing provider behavior

Read `docs/adr/README.md` first. Three hundred and eighty-two decisions (0001–0382; two
share the number 0263, written in parallel on Nov 21–22 2026) now
exist; `docs/adr/README.md` index is the source of truth if this line drifts.
the submit-path canon is 0001–0006 (identity, temperature, single-pass, prompt
ceilings, Grok retirement, no silent fallback), joined by 0053 (generation
orbit), 0061 (429 is throttling), 0063–0064 (camera setups, conflicts refused
pre-render), 0083 (database durability), 0090 (Location is the single source
of truth; the hook opens on a visible move), 0187 (the opening movement
enacts the story, rapid and mid-motion, on this video's own channel —
hand, face, mouth, body or camera — and the close carries the opening's
energy), 0092 (Render & result scene
fields agree — fix or block) and 0097 (a selfie never shows a phone, a reach
toward the lens, or a second free hand); 0099 stacks the wizard as one canvas.
Post kits follow 0100 as amended by 0139: the model proposes a 12–15
hashtag candidate pool, post counts are researched best-effort
(`backend/hashtag_volume.py`, cached 7 days), and exactly five are selected
by size — about three at 10k–50k posts and two at 100k–500k, never
million-plus, never bait; a lookup outage falls back to the pool's first
five on wording alone, so a kit never breaks.
`provider_capabilities.py` compares
the catalog to OpenRouter's live listing at boot as a warning only — never a
gate. Frontend design constraints live in `design_guidelines.md`.
