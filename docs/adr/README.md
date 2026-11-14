# Architecture Decision Records

One file per significant decision: **context → decision → consequences**, plus
the alternatives we rejected and why. Git records *what* changed; these record
*why*, in one browsable list.

## Rules

- Numbered `NNNN-<slug>.md`, sequential, never renumbered.
- A new decision that overturns an old one gets a new file; the old file stays,
  with `Status` flipped to `superseded by NNNN`. History is append-only.
- A commit that picks between real alternatives adds or supersedes an ADR in
  the same commit.
- Each record cites a verifiable anchor (commit hash or `file:line`). If the
  anchor doesn't resolve, the record is stale — fix or supersede it.

Current navigation: [architecture](../architecture.md),
[operations](../operations.md), [contributing](../../CONTRIBUTING.md).
Records below preserve historical decisions; current routes and state owners
come from the architecture map and code, not an old record's UI description.

## Index

| # | Decision | Status |
|---|----------|--------|
| [0001](0001-grok-submit-failures-are-loud.md) | Provider 400s fail loudly with the provider's quoted words; no silent fallback | accepted (Grok eligibility superseded by 0006) |
| [0002](0002-h3max-identity-via-first-frame.md) | H3 Max identity rides as the opening frame, not `input_references` | accepted |
| [0003](0003-temperature-from-endpoint-declaration.md) | Temperature support is read from the endpoint declaration, not a model list | accepted |
| [0004](0004-single-pass-generation-only.md) | Generation is single-pass only; durations clamp, never chain | accepted |
| [0005](0005-per-provider-prompt-ceilings.md) | Each provider gets its own prompt ceiling; the spoken script is sacred on tight ones | accepted |
| [0006](0006-retire-grok-video-model.md) | Retire Grok Imagine Video 1.5 Lite (`input_references` unsupported) | accepted |
| [0007](0007-overlay-font-motion-options.md) | Caption/CTA overlays get selectable fonts, animations, and size | accepted |
| [0008](0008-hook-boundary-lean-in.md) | The hook-boundary transition is a face-anchored lean-in on a committed beat | superseded by 0053 |
| [0009](0009-history-tiles-expand-on-demand.md) | History tiles open on demand: the clip first, the record behind a tab | partially superseded by 0033 (tile identity & results) and 0035 (full-width band) |
| [0010](0010-no-warm-button-fills.md) | No warm fills on buttons: coral and red move out of the surface | partially superseded by 0011 (Demo + CTA wears accent) |
| [0011](0011-history-onward-wears-accent.md) | History's onward Demo + CTA wears accent, not brand | accepted |
| [0012](0012-timestamped-tiktok-export.md) | Timestamped, frame-by-frame encoding delivers one TikTok MP4 without real-time capture drift | accepted |
| [0013](0013-eye-catching-motion-expansion.md) | Ten new background motions + ten shared overlay entrances; Output group removed | partially superseded by 0014 (picker retires underline, spotlight) and 0018 (picker retires six background motions) |
| [0014](0014-retire-underline-spotlight-entrances.md) | Retire underline + spotlight from the entrance picker; motion kept for old renders | accepted |
| [0015](0015-preview-transport-owns-playhead.md) | Preview transport owns the playhead (no replay on option change); Sora leaves the font catalog | partially superseded by 0017 (scoped overlay replay) |
| [0016](0016-editable-zoom-lock-preview.md) | Paused zoom drafts remain editable; saved hand/phone locks drive preview and export | accepted |
| [0017](0017-scoped-overlay-review.md) | Replay overlay windows; save reusable looks after final CTA review | accepted |
| [0018](0018-retire-six-background-motions.md) | Retire six background motions from the picker; bloom becomes the default | accepted |
| [0019](0019-one-caption-post-kit.md) | One TikTok caption per post kit, regenerable on demand | partially superseded by 0020 (export-card regenerate, question guard, completed-only) |
| [0020](0020-post-kit-regenerate-everywhere.md) | Regenerate reaches the export card; caption must ask; completed-only | accepted |
| [0021](0021-post-kit-ownership.md) | Post-kit state has one owner per layer | partially superseded by 0034 (frontend snapshot synchronization) |
| [0022](0022-looks-live-together-in-end-card-cta.md) | Saved looks live with saving in End Card CTA | accepted |
| [0023](0023-shared-caption-text-styles.md) | One shared text treatment across hook, story and end card | partially superseded by 0024 (text-style catalog trimmed to three) |
| [0024](0024-retire-three-text-styles.md) | Retire outline, clean and sticker from the text-style picker | accepted |
| [0025](0025-real-video-phone-composite.md) | Real Video combines a base clip and looped phone upload through one timestamped painter | superseded by 0027 (appended sequence) |
| [0027](0027-real-video-appended-sequence.md) | Real Video appends the second clip after the base with both soundtracks | accepted |
| [0028](0028-per-clip-presentation.md) | Each sequence clip picks its own floating/hand/real presentation | accepted |
| [0029](0029-second-clip-group-and-look.md) | Second clip gets its own gated group and its own background/motion/scene | accepted |
| [0026](0026-fresh-opening-message-batches.md) | Opening text consumes twenty app-grounded suggestions instead of saved preset indices | accepted |
| [0030](0030-per-clip-audio-mutes.md) | Each sequence clip mutes its own audio in preview and export | accepted |
| [0031](0031-first-run-checklist.md) | First-run checklist carries the founder across pages with their tours | accepted |
| [0032](0032-history-tiktok-link-and-winner.md) | A TikTok link marks a render posted; thumbs up plus link is the winner | accepted |
| [0033](0033-clip-results-comparison.md) | Compare saved clip reach and votes; keep History summaries synchronized | accepted |
| [0034](0034-history-snapshot-synchronization.md) | History owns confirmed snapshots; URL filters and current requests prevent stale handoffs | accepted |
| [0035](0035-history-detail-band.md) | Open History detail is a full-width band; one band at a time | partially superseded by 0036 (band spans a pair row) |
| [0036](0036-history-pair-rows.md) | History pairs two videos per row; band spans beneath its pair | partially superseded by 0037 (band lands after the open pair) |
| [0037](0037-history-pair-aware-band.md) | History band lands after the open pair via a list-owned portal slot | superseded by 0039 (attached cards, no expand) |
| [0039](0039-history-attached-cards.md) | History rows are one attached card, no expand step | partially superseded by 0040 (record disclosures) and 0051 (compact without-copy cards) |
| [0040](0040-history-record-disclosures.md) | History record tucks post copy and plan context behind disclosures | partially superseded by 0052 (mobile results disclosure) |
| [0041](0041-analytics-visual-results.md) | Analytics results go visual: leaderboard, bars, timeline | partially superseded by 0046 (three-row opening, collapsible card, status disclosures) |
| [0042](0042-history-drops-part-ratings.md) | History drops per-part ratings; one vote per render | accepted |
| [0043](0043-history-single-source-identity.md) | History identity lives once, under the clip | accepted |
| [0044](0044-post-kit-caption-spec.md) | Post-kit captions are short, user-voiced, and tailored | accepted |
| [0038](0038-workspace-type-scale-step-up.md) | Workspace type steps up: 16px body/inputs/titles, 30px H1 | accepted |
| [0045](0045-demo-cta-clip-start-point.md) | Demo + CTA clips carry a start point; the head is trimmed, the tail is not | superseded by 0054 |
| [0046](0046-analytics-status-disclosures.md) | Analytics opens on three results; render statuses open their clips | accepted |
| [0047](0047-analytics-loaded-set-and-recorded-dates.md) | Analytics states its loaded set once; views carry recorded dates | accepted |
| [0048](0048-clip-joint-transitions.md) | Five joint transitions between the two clips | partially superseded by 0049 (swipe replaced by flash + fade) |
| [0049](0049-flash-fade-replace-swipe.md) | Flash and fade replace swipe in the joint-transition catalog | superseded by 0050 (hard cut, flash, fade leave; four trends, one row) |
| [0050](0050-four-trend-transition-row.md) | Four motion trends in one transition row; whip is the default | accepted |
| [0051](0051-history-compact-without-copy.md) | Without-copy History cards use a compact responsive grid | accepted |
| [0052](0052-history-mobile-results.md) | History keeps primary filters and copy visible while compacting mobile results | accepted |
| [0053](0053-generated-orbit-centered-zoom.md) | Generation owns the orbit and gesture; processing owns one exact centered zoom | partially superseded by 0063 (fixed camera) |
| [0054](0054-demo-cta-editing-documents.md) | Browser-local editing documents, undo/redo and compact two-sided trimming | accepted |
| [0055](0055-implicit-behavior-signals.md) | Implicit behavior signals (adopted/abandoned/generated) supplement explicit thumbs | accepted |
| [0056](0056-hero-play-control.md) | The autoplaying hero carries its own play/pause control; reduced motion loads on an explicit tap | accepted |
| [0057](0057-preview-frame-play-button.md) | The Demo + CTA preview plays from a branded button on its own frame | accepted |
| [0058](0058-text-overlays-start-off.md) | Hook, story and end-card text overlays all start off until the founder turns one on | partially superseded by 0082 (standalone entry starts blank) |
| [0059](0059-natural-amateur-default-look.md) | The default look is natural amateur phone footage, never polished | accepted (device naming refined by 0103) |
| [0060](0060-kitless-post-copy-offer.md) | Kit-less finished renders offer post-copy generation in History | accepted |
| [0061](0061-rate-limit-is-throttling.md) | Provider 429 is throttling: poll waits quietly, submit names the retry | accepted |
| [0062](0062-history-polls-awaiting-renders.md) | History polls its awaiting renders on its own | partially superseded by 0078 (visible per-row stop state) |
| [0063](0063-two-camera-setups.md) | Handheld selfie stays default; fixed camera is wider, stationary and unzoomed | accepted |
| [0064](0064-camera-direction-conflicts-fail-before-render.md) | Refuse conflicting fixed-camera directions before rendering; preserve reviewed scene notes | accepted |
| [0065](0065-profile-tailored-goal-order.md) | Tailor goal suggestion order to recorded profile evidence, retaining the six-goal set | accepted |
| [0066](0066-profile-matched-direction-dropdowns.md) | Match direction dropdown choices to the approved profile; retain validated saves | accepted |
| [0067](0067-review-edits-autosave.md) | Autosave Review edits through the existing server save and claim-check path | accepted |
| [0068](0068-brand-autosave.md) | Autosave App Profile edits without clobbering newer inputs or changed profiles | accepted |
| [0069](0069-moved-forward-momentum.md) | Proceeding to build shows as momentum beside verdicts, never inside the fit score | accepted |
| [0070](0070-posted-performance-judges.md) | Posted TikTok performance judges; founder verdicts nominate; 90-day half-life on sort | accepted |
| [0071](0071-pair-attribution-and-exploration-guard.md) | Pair (kind × objective) attribution sharpens below each axis; thin evidence invites one untried kind | accepted |
| [0072](0072-active-varied-settings.md) | Strategies stage active, varied settings from the usage moment; bedrooms and cars stop being the default | accepted |
| [0073](0073-angle-carries-viewer-outcome.md) | Angles carry viewer_outcome from outcome_statements; card shows it, strategy lands it | accepted |
| [0074](0074-shared-template-fit-notes.md) | Fit notes shared by every template card are read once above them | accepted (section-copy clause superseded by 0085) |
| [0075](0075-actionable-review-checks.md) | Review findings select editable text; supporting evidence stays collapsed | accepted |
| [0076](0076-angle-diversity-and-source-links.md) | Correct duplicate arguments and carry recorded feature/outcome links | accepted |
| [0077](0077-intent-aware-core-tours.md) | Core tours wait for first-run page readiness; other help stays manual | accepted |
| [0078](0078-history-check-state-and-results.md) | History names polling stops and opens existing results controls directly | accepted |
| [0079](0079-policy-and-studio-module-ownership.md) | Isolate deterministic policies and studio panels; retain project orchestration and compatibility | accepted |
| [0080](0080-wizard-draft-state-transitions.md) | Make coupled wizard draft changes atomic; isolate template-loading state | accepted |
| [0081](0081-remove-claim-render-blocking.md) | No wording flag refuses a render; claim reports stay advisory | superseded by 0119 |
| [0082](0082-standalone-demo-cta-starts-blank.md) | Standalone Demo + CTA starts blank; only pinned workspaces resume drafts | accepted |
| [0083](0083-turso-outage-refuses-local-fallback.md) | A configured Turso outage fails database requests instead of accepting local SQLite writes | accepted |
| [0084](0084-angle-owns-scene.md) | The selected angle owns where, when and what happens; later steps conform with a visible note | accepted |
| [0085](0085-template-step-reads-strongest-shared-note.md) | The template step reads the strongest shared note, not every one; the angle keeps its own bounds | accepted |
| [0086](0086-upscaler-exports-1080p.md) | The upscaler exports 1080p, not 4K; eligibility moves with the target | accepted |
| [0087](0087-template-tailoring-waits-for-a-click.md) | Template tailoring waits for the founder's Generate click; a goal pick never bills | accepted (free ranked read on the pick superseded by 0098) |
| [0088](0088-voice-reads-locally.md) | Voice reads locally through the browser's speechSynthesis; data-driven text, one dock, no text leaves the device | accepted |
| [0089](0089-templates-follow-the-video-fields.md) | Tailored templates are generated from and checked against the Problem, Promise and Audience; one character, one opening; the person has no gender or role | accepted |
| [0090](0090-location-single-source-and-opening-move.md) | Location (the plan's visual direction) is the single source of truth — one save rewrites every place-bearing strategy line, spoken words refuse rather than change; the hook's first beat is a visible move | accepted |
| [0091](0091-voice-direction-is-the-one-delivery-control.md) | Voice direction is the single delivery control on Review; the video-level Tone dropdown is removed, brand "Tone / voice" remains | accepted |
| [0092](0092-render-result-scene-fields-agree.md) | Render & result scene fields must agree: Location is the place only (lighting and time in Lighting), Props and Movement cover the actions and timeline, no internal wording, viewer rows from the viewer's point of view — fix or block | partially superseded by 0103 (props scope: carried objects, not scenery) |
| [0093](0093-selfie-ends-on-a-physical-beat.md) | Selfie renders end on a varied physical beat, never a phone; fixed camera keeps the phone handoff | accepted |
| [0094](0094-render-result-actions-open-explanations-collapsed.md) | Render & result keeps actions open and collapses the strategy explanations and scene spec-sheet into groups with one-line digests | accepted |
| [0095](0095-wizard-sticky-arrow-navigation.md) | Wizard task line under the title; back/continue are arrow-only, centred and sticky | accepted (hint-free bar superseded by 0099) |
| [0096](0096-templates-exactly-three.md) | Templates: exactly three selections, no more and no less | accepted |
| [0097](0097-selfie-never-shows-a-phone-or-a-reach.md) | A handheld selfie never shows a phone, a reach toward the lens, or an action needing a second free hand; the fixed camera keeps the phone handoff | accepted |
| [0098](0098-every-template-request-waits-for-the-click.md) | Every template request — billed tailoring and the ranked read — waits for the Generate click; a goal pick queues nothing | accepted |
| [0099](0099-studio-canvas.md) | The studio canvas: every step on one page, the active one expanded; sticky rail with a live fill, next-action line in the arrow bar; disclosure queues nothing | accepted |
| [0100](0100-hashtag-strategy.md) | The hashtag strategy: a fresh account gets 4 to 6 classified tags (problem anchor, community, one category), never engagement bait | accepted |
| [0101](0101-hook-voice.md) | The hook speaks to the viewer: the hook line uses 'I' at most once; the middle stays the customer's first-person story | partially superseded by 0106 (statement default; middle is two beats) |
| [0102](0102-voice-and-lighting-auto.md) | Voice and lighting are set from each video's own context; no founder control owns delivery; lighting stays a scene field written by the model | accepted |
| [0103](0103-props-are-carried-and-the-camera-is-never-a-phone.md) | Props names only what the person carries, wears or uses — never scenery Location already names; Camera angle and Visual style call the filming device "the camera", never the phone | accepted |
| [0104](0104-movement-cap-600-advisory.md) | Movement's cap rises to 600 characters and overflow becomes an advisory truncation with a warning, not a render block; Props keeps the hard block | accepted |
| [0105](0105-middle-is-the-hook-continued.md) | The middle script continues the hook as one spoken thought — answers its question first, plain spoken language with one lived detail, strongest line last — by prompt rule only, targets unchanged | partially superseded by 0106 (statement default; middle is two beats) |
| [0106](0106-hooks-default-to-a-statement-and-the-middle-is-two-beats.md) | Hooks default to a statement naming the viewer's feeling or situation, not a question, unless the plan explicitly requests a question format; the middle is two beats max (one action, one lingering thought) on the arc problem, insight, shift | accepted |
| [0107](0107-live-goals-for-the-selected-angle-click-gated.md) | Live goals for the selected angle from its full context (audience, problem, promise, outcome, emotion, feature), click-gated, facet list as the fallback | accepted |
| [0108](0108-setup-owns-camera-words-and-the-plan-owns-shape.md) | Setup owns camera words, Location owns the place, plan owns shape: rewrite setup wording, strip phone clauses and Location objects, carry the plan's camera move as a lean for handheld, quote the hook line and middle as Shape/development, refuse a final line breaking its bounded-by | partially superseded by 0119 (bounded-by refusal) |
| [0109](0109-screen-surfaces-and-fragment-location.md) | No screen surfaces in generated clips; Location never opens as a fragment: scroll/chart clauses stripped for selfie, promises strip screen work, Location repaired to its anchor, "now I know" maps to diagnosis bounds in plan generation | accepted |
| [0110](0110-muse-ember-max-chat-model.md) | All chat generation runs on Muse Ember (Max): Claude Haiku 5.5 retired from the shipped defaults; reasoning_effort=max pinned for the shipped slug; temperature follows ADR 0003's endpoint declaration | accepted |
| [0111](0111-composition-root-domain-routers.md) | Decompose the composition root into domain routers (db/schema, brands, studio, assets, history); server keeps include + re-exports; routers resolve test-patched server names at call time via `_cfg`, never importing server | accepted |
| [0112](0112-split-ai-service-by-flow.md) | Split the OpenRouter adapter by flow: pure clusters (spoken, strategy, text, media) move to `ai_*` modules with ai_service re-exporting; transport + chat flows stay (patch seam); CreateVideo angle-step lifecycle extracts to `useWizardAngleStep` | accepted |
| [0113](0113-wider-selfie-framing-and-vertical-reference.md) | Wider selfie framing (mid-chest, never crop forehead/chin) and a vertical 9:16 identity reference; fixed-text cost paid by naming the framing instead of restating the distance | accepted |
| [0114](0114-advisory-craft-score.md) | Advisory 8-dimension craft score for the spoken pair: recomputed on read, never a gate; performance (retention/completion/saves/follows) stays a separate normalized measure | accepted |
| [0115](0115-craft-findings-steer-one-plan-retry.md) | Craft findings steer one bounded plan retry: below 60, one targeted correction call; keep the higher hard-valid draft, never refuse over craft | partially superseded by 0116 (bar 80, hook frozen, quote salvage) |
| [0116](0116-craft-bar-80-hook-frozen-quote-salvage.md) | Craft bar at 80; craft retry rewrites the script only (hook byte-for-byte); live-POV rules (no quotes/narration, suffix hard until salvage); persistent quotes stripped mechanically and shipped quote-free, all other hard issues still refuse | accepted |
| [0117](0117-performance-feedback-loop.md) | Performance feedback loop: manual dated snapshots, frozen craft score, prompt steering (steering superseded by 0124; snapshots and the frozen score stay as the record) | accepted |
| [0118](0118-onboarding-core-tour-expansion.md) | Onboarding core tours expand to the journey's fork pages (Demo + CTA, Analytics, Assets); App Profile detail stays replay-only | accepted |
| [0119](0119-remove-claim-safety-entirely.md) | Remove the claim-safety system entirely: no claim lists, no safety report, no SafetyPanel, no bounded-by or wording refusals; angle bounds stay as prompt guidance only | accepted |
| [0120](0120-versioned-migrations-backup-fail-loud-jobs-queue.md) | Data durability: versioned migrations, operator backup/restore, production fail-loud, and a jobs queue for post-render persistence | accepted |
| [0121](0121-journey-one-flow.md) | The journey is one flow: inline profile approval at the wizard's start, one-pass plan + strategy behind one endpoint, Demo + CTA as the wizard's finishing step, and History's joined finished → posted journey line | accepted |
| [0122](0122-generation-waits-for-the-click.md) | Generation waits for the click everywhere in the create flow: plan, strategy and angle listing fire only from their own Generate controls; approving a profile still generates its first angle set | accepted |
| [0123](0123-script-ending-is-a-hard-check.md) | The script's ending is a hard check: a last sentence in question form joins the editorial loop's observable defects and refuses after the bounded retries; the spoken block also treats hook + script as one text for repeated words and bans the app's own feature nouns from spoken lines | accepted |
| [0124](0124-whole-video-verdict-replaces-per-element-feedback.md) | One whole-video verdict replaces per-element feedback: a single up/down per finished video on a bundle frozen at verdict time is the only steering signal for plan and strategy prompts (silent below 3 verdicts); the Review refine loop and all per-element thumbs come out; snapshots and the frozen craft score stay as the record | accepted |
| [0125](0125-angle-grounding-near-match-and-moment-diversity.md) | Angle grounding gains a guarded near-match tier (unique token containment or Jaccard >= 0.8; ambiguity means no link, exact always wins) and angle diversity gains a same-moment check (both fields' token sets >= 0.6) beside the lexical one; same-moment pairs join the existing single diversity correction | accepted |
| [0126](0126-goals-fit-certified-outcome-distinct-verdict-evidence.md) | Goals fit the certified outcome: the goal prompt carries the angle's verified_feature_outcome when one certifies and aims why_it_fits at it; goal distinctness gains a meaning-level check (combined description + why_it_fits token sets >= 0.6) with the same one-correction-then-loud-failure handling; goal cards show whole-video verdicts tallied per objective from the frozen bundles, a pure read that never triggers generation | accepted |
| [0127](0127-templates-and-plan-join-the-verdict-loop.md) | Templates and the plan join the verdict loop: template ranking reads whole-video verdict bundles only (the per-element record stays as record), the presented set prefers structurally distinct templates with duplicate backfill, template cards and Review show verdict evidence, and the plan's hook must carry the certified outcome's key terms — a deterministic check in the editorial loop that refuses loudly, silent when no outcome certifies | accepted |
| [0128](0128-spoken-line-quality-gates.md) | Spoken-line quality gates (Kasra's 8–9 directive, extending 0123): determiner-less place phrases, control-verb + levels/sliders constructions, and problem-restating endings join the editorial loop's hard issues; the clearer-line rewrite gets a reasoning-sized budget and per-class failure messages; the one-working-button rule extends to the no-strategy state | accepted |
| [0129](0129-reasoning-budgets-cover-thinking-plus-payload.md) | Every reasoning-model call budgets for thinking plus payload: named per-family constants sized at twice the largest budget observed to return empty, after the plan's 8000 start and 16000 retry both came back as empty content (finish_reason=length) on the verdict-grown prompt — PLAN_MAX_TOKENS 32768 at both plan calls, STRATEGY_MAX_TOKENS 24576, REWRITE_MAX_TOKENS 1500 → 6000 after its 3000 retry truncated live too, each pinned by a budget-gate test; the bare-place grammar gate widens to beside/by/near/outside/inside + signpost and the "on bus stop days" compound, exclusions intact | accepted |
| [0130](0130-hook-bake-off-and-set-length-rule.md) | The hook bake-off and the set-length rule: after the editorial loop accepts a draft, three alternative hooks are written for the same story, filtered hard by the same deterministic gates (the certified outcome is a requirement, never a bonus) and ranked by the existing craft scorer — a candidate ships only when it strictly beats the draft, so the floor rises without any plan getting worse; and every generated or regenerated line is sized by its set character length as a hard acceptance rule (the hook rewrite takes its set length; a script line's suggestion must fit its share of the script's ceiling, the own-length credit removed), because over-length spoken lines overlap when rendered over the video | accepted |
| [0131](0131-goals-show-top-three-for-the-angle.md) | The goal picker shows the top 3 goals for the selected angle: the six-goal pool is still generated and meaning-checked, then the endpoint returns only the top 3 ranked by certified-outcome key-term coverage of the goal's own words, then fit_score, then generation order — and the picker caps its featured list at the same three in every state, vocabulary padding gone | accepted |
| [0132](0132-angle-generations-are-unique-per-profile.md) | Angle generations are unique per profile across generations: migration 0004 records every offered angle, each new generation is checked against the whole record with the ADR 0125 wording/same-moment judges (one bounded correction, complete set or loud failure), so no profile is ever offered the same angle twice | accepted |
| [0133](0133-direction-change-suggestions-and-the-unblocking-bar.md) | A rebuild after a Visual & audio direction change first offers a refreshed hook + script in a modal (direction stamped in the strategy record at build; suggestion craft-gated, accept saves through the plan path, keep writes nothing, failure falls back to the saved words with a note), every rebuild surface reads "Rebuild strategy", and the sticky bar carries the one unblocking action on every step — no forward arrow beside it | accepted |
| [0134](0134-one-primary-action-in-the-render-panel.md) | The render panel's one-action rule extends to the un-saved plan: while the plan needs saving, "Generate the video" is not rendered at all and only the "Review and save the plan" remedy shows — the rebuild-owed and no-strategy states already worked this way; the angle/photo navigation remedies keep the disabled button as their gate | accepted |
| [0135](0135-hook-power-instructions-and-the-feature-noun-gate.md) | Hook power taught from the founder's scored pairs and the feature-noun gate: the shared spoken-line block gains a HOOK POWER bullet (first person lived feeling, resolution withheld, one statement, felt detail over verdict words, the moment named) built from his 7/20, 12/20 and 13/20 hooks and his strong shape, under his SOFT choice — 15/20 is the aimed bar, never a shipping floor, the hard refusal shape offered and rejected; and the app-feature-noun ban moves from prompt-side to a deterministic gate ("reflections", whole-token) inside the shared spoken-issues list, so the plan's editorial loop corrects it and the bake-off's hard filter removes any candidate carrying it | accepted |
| [0136](0136-one-location-editor-in-visual-and-audio-direction.md) | The Location is edited in one place only — the direction pick inside Visual & audio direction: the plan view's standalone Location textarea and the render panel's Location editor ("Save location") are removed, since all three editors wrote the same project.location through the same PATCH; the ADR 0090 scene reconcile stays in the shared PATCH handler, so the pick's save (manual or autosave) gets the identical reconcile and version re-stamp, the ADR 0133 snapshot diff still offers refreshed words at rebuild, the Scene Details LOCATION row stays as the read-only locked-scene record, and the response's location_change audit stays in the save contract with its one UI consumer retired | accepted |
| [0137](0137-history-clip-flush-frame-and-work-row.md) | The History clip sits flush and work with this render lives under it: the preview frame spans the media column edge to edge at the Download row's width (no padding, no width or height cap, at most the card hairline — the indigo surround and corner marks are gone, the stage goes flush when a standard card plays), the Work with this render group moves from the record column into the media column directly under the Download row as its own row, and the finished clip's native controls carry controlsList="nodownload noremoteplayback" plus disablePictureInPicture so the browser's three-dots overflow has nothing in it | accepted |
| [0138](0138-poll-detaches-the-durable-save.md) | The completion poll hands the durable save to its BackgroundTasks: poll used to run the whole download/trim/rescale/upload inline before answering, so any save past the client's 120s poll timeout aborted mid-persist, stranded the queue job under an unheartbeated 300s lease, and looped (later polls answered generating against the lease or restarted the save into the same abort) — the live panel sat at 85% until an unattached run (the startup sweep after a cold start) landed the completion; now the poll records and claims the job synchronously (ADR 0120 intact), executes it detached with a 60s lease heartbeat, and answers the row's current state while the panel's next poll serves the completed row | accepted |
| [0139](0139-hashtag-volume-research-then-select.md) | Post-kit hashtags are researched first, then selected: the model proposes a 12-15 niche candidate pool (relevance-ordered), each candidate's TikTok post count is looked up best-effort behind an injectable fetcher seam (default: the Creative Center radar API — 40101 in every build-time check, so the design assumes fragility), counts persist in a 7-day cache (migration 0005), and exactly five are selected by the named mix (3 at 10k-50k posts, 2 at 100k-500k, never a million-plus) with stepwise widening to neighbouring ranges; any research outage falls back to the pool's first five on wording alone, so a finished video never loses its post copy; exactly-five supersedes the old 4-6 range while the shape gate (one token, unique, no bait) is unchanged, and the community slot, rotation and learning layer the founder rejected stay out | accepted |
