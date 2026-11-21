# 0227 — Stories are projects with a kind marker

Status: superseded by 0243 (the Stories page is removed; the kind marker survives as legacy data)

## Context

Kasra's order (Nov 19 2026): a new HookForge feature — a separate
sidebar link and page dedicated only to short video Stories for
Instagram and TikTok, not feed posts — built end to end to match the
app's design and branding system exactly, for fast creation of
relevant, high-quality, eye-catching Stories using platform best
practices. He delegated the six open design questions to research
("You have to research that yourself. Use TikTok's best practices."),
and the research settled all six (Nov 19 2026). The governing
documents live outside the repo, beside the work that produced them:
the build plan (`~/workspace/hookforge-stories-plan.md`, its section 6
records the six questions SETTLED) and the research file
(`~/workspace/hookforge-stories-research.md`, the evidence and every
build number). This record is the in-repo anchor for the decisions
the build follows; the plan's phase list is the build order, and this
phase — phase 1, data and types — is the only one this commit lands.

The shape question underneath everything: what IS a story, in data?
A story needs almost everything a hook video already has — an app
profile and its facts, a presenter photo, direction picks, a model, a
render through the one submit path, the polling/storage/repair
lifecycle, and a row in History. What it does not have is the wizard's
plan → strategy ceremony, a post kit, or a verdict. A second table
would fork every shared system to re-join them at History; a marker
on the project row keeps one lifecycle and lets each surface branch
only where stories genuinely differ.

## Decision

1. **A story is a `studio_projects` row with `kind = 'story'`.**
   Migration step 7 (`backend/schema.py`, `_migration_0007_project_kind`)
   adds `studio_projects.kind TEXT NOT NULL DEFAULT 'video'`: every
   existing row becomes a hook video, story rows carry `'story'`. The
   marker is the row's identity — `CreateStudioProjectRequest` accepts
   it (`backend/models.py`, `Literal["video", "story"]`, default
   `'video'`), the create INSERT writes it, and `_public_project`
   (`backend/routers/studio.py`) carries it, defaulting a row from
   before the step to `'video'`. It is deliberately NOT in
   `STUDIO_EDITABLE_FIELDS` and not on the update request: a draft
   edit can never turn a video into a story or back. The Stories
   creation endpoints arrive with the Stories router in phase 2; this
   phase makes the data layer hold and expose the marker.

2. **One render per frame, through the existing generation path.**
   A story frame is one single-pass render of 5–15 seconds (every
   catalog model caps a pass at 15s; TikTok caps a story segment at
   15s), submitted by the same `_submit_generation` that renders every
   hook video — it stays the only render path, and story renders are
   ordinary `generations` rows. A multi-frame story is several
   independent renders on the existing `segment_index` column, posted
   in order by the founder. There is no render chain and no join
   (ADR 0004 stands). v1 is single-frame; sequences are the phase-5
   fast follow, capped at 3 frames (research: completion decays with
   every added frame).

3. **The story kit is the posting layer, shaped now, written in
   phase 2.** At render completion a story render grows a story kit
   beside the post kit's home — never a post kit, and hook-video
   renders never grow a story kit. The kit carries: a caption in the
   story register (ADR 0139's five-hashtag machinery does NOT apply —
   stories are not feed posts); the accepted on-screen text VERBATIM,
   handed over as a native text sticker the founder places at posting
   (never burned into the render — the two platforms' safe zones
   differ too much for one burned position, and native text survives
   upload compression); a per-frame sticker plan naming the sticker,
   its exact wording, and its placement in words, adapted per
   platform (countdown, questions and slider stickers are
   Instagram-only; TikTok's kit carries the date or question in the
   screen text and spoken line instead); and a short posting
   checklist. Screen text is capped at 80 characters / 14 words —
   derived from TikTok's 5–10 words-per-second pacing rule, not a
   published platform limit — so it reads whole inside the shortest
   5-second frame and carries the whole message alone for the muted
   minority, while the spoken line stays a first-class channel
   (stories are majority sound-on on both platforms).

4. **Story rows take no verdict and never enter the feedback
   bundles.** ADR 0124's one-verdict bundle is the signal that steers
   hook-video plans, goal fits (ADR 0126) and template ranking
   (ADR 0127). A story's outcome measures a different format; mixing
   it in would blur exactly what the bundle measures. Stories land in
   History through the existing list with a Story chip and filter
   (phase 5), as record — not as learning signal. Analytics is
   untouched in v1.

5. **The v1 types are four, in a new pure module.**
   `backend/story_types.py` (the `template_library.py` pattern: code-
   owned curated data, no generation, no endpoints) holds the settled
   catalog, each with its id, display name, default frame length, and
   one line on what it is for: **Hook teaser** (10s — points at the
   founder's newest hook video or post, closing on "the full one is
   up", link sticker in the kit), **Question / poll prompt** (5s —
   one question drawn from the angle's tension; the poll sticker is
   the best-evidenced story mechanic either platform documents),
   **Demo moment** (15s — one app moment as a presenter beat, the
   spoken line ending open), **Announcement / countdown** (10s — a
   launch, update, or deadline beat; the countdown sticker carries
   the date after the clip ends). Frame lengths are per-type defaults
   with a 5/10/15 pick on the page — no platform prescribes one fixed
   length. **Testimonial-style is excluded**: there is no claim-safety
   system (ADR 0119) and no source of real user quotes to ground one,
   and an invented testimonial is an invented lookalike. It can be
   added when the founder supplies the quote text themselves.

6. **The remaining settled decisions this build follows.** Sidebar
   placement: Stories directly after Create Video (product default —
   research does not govern another app's navigation). History:
   stories mixed in with a Story chip and filter (product default —
   one record of everything rendered). Canvas 1080×1920; the preview
   draws Instagram's safe zone (top 250 / bottom 340 / sides 65 px)
   and TikTok's in-feed overlay (top 240 / bottom 660 / sides 120,
   right rail 300 below y≈840) — TikTok publishes no Stories-specific
   safe zone, so its official in-feed template is the conservative
   reading. The story plan's spoken rules keep the shared spoken-line
   doctrine with the hook's move inside the first second — stricter
   than the hook video's first-two-seconds rule and than the
   platforms' published guidance, because stories are tapped through
   faster than feed posts. The story craft check, when it lands in
   phase 2, is a fixed deterministic checklist beside the existing
   scorer — never calibrated against outcomes, under the same ruling
   that covers the craft check.

## Alternatives considered

- **A separate stories table and lifecycle.** Rejected: it forks the
  render, polling, storage, and repair paths and then has to re-join
  them at History — two lifecycles to keep honest for a row that
  differs by a handful of fields and one kit.
- **`kind` as an editable draft field.** Rejected: the marker is what
  the row IS. Making it PATCH-able would let a video with a strategy,
  a post kit, and a verdict bundle be relabelled a story after the
  fact, and every branch on the marker would have to defend against a
  history it was never built under.
- **Burning the screen text into the render.** Rejected in research:
  live stickers cannot ride in a render at all, the platforms' safe
  zones disagree, and burned text takes the upload-compression hit
  that native text avoids. The kit carries the words; the founder
  places them.

## Consequences

- Phase 1 lands only the data layer: migration step 7,
  `story_types.py`, and the marker on the request model, the create
  INSERT, and the serializer. No endpoint, prompt, page, or kit
  behavior changes; every existing project reads back `'video'` and
  behaves exactly as before.
- Phases 2–4 build on this marker without another schema decision:
  the story plan flow and `routers/stories.py`, the story brief in
  prompt assembly, the kit writer, then the page. Phase 5 adds
  sequences (capped at 3) and the History chip/filter.
- Tests: `test_schema_migrations.py` pins step 7 — recorded, the
  column's TEXT/NOT NULL/`'video'`-default shape, existing rows
  becoming `'video'`, a `'story'` row staying `'story'` — and the
  fresh/legacy convergence fingerprint now covers the column.
  `test_story_types.py` pins the catalog: the four ids in order, the
  display names, the 10/5/15/10 defaults inside the 5–15 band, a
  one-line purpose each, no testimonial, and unknown ids resolving to
  None rather than a fallback. `TestProjectKind` in
  `test_studio_api.py` pins the model and serializer: create defaults
  to `'video'`, a story row is created and read back distinctly, an
  unknown kind is refused at the model, and the marker is not
  editable. All were watched failing before the change.
