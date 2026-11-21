# 0238 — Stories are beats of three to five seconds

Status: superseded by 0243 (the Stories page is removed; the 4/5-second word budgets live on in the Hook + CTA hook, ADR 0244)

## Context

On Nov 20 2026 Kasra ruled the shipped Stories lengths far too
long: 15 seconds — and even 10 — is a short video, not a story.
Stories are not meant to generate long videos. He ordered the
feature matched to what TikTok and Instagram Stories actually
are, in duration and in every other way, and the platform
research run the same day (the Stories mechanics report in the
research notes) established the facts:

- Instagram shows a photo story for **5 seconds** by default —
  the shortest natural story beat on either platform.
- Instagram accepts story video from **3 seconds** (its
  publishing API's band is 3–60 seconds per story).
- TikTok's story timer is selectable from **1–15 seconds**, and
  15 seconds is TikTok's per-segment **maximum** — the old demo
  moment default sat at the platform's ceiling.
- Natural speech runs about **2.5 words per second**, so a frame
  of 3 seconds holds about 6–7 spoken words, 4 seconds about
  8–9, and 5 seconds about 10–12. The old plan wrote against a
  character budget only (ADR 0228's `spoken_budget`), which at
  these lengths lets far more words through than the frame can
  speak.
- TikTok Stories has **no link sticker and no countdown
  sticker** for organic stories; Instagram has both. The kit
  already said this in its per-type checklist lines (0228), but
  the catalog's own one-line purposes still named the link and
  countdown stickers without the platform split.

## Decision

1. **The per-type defaults are beats now** (`backend/story_types.py`,
   mirrored exactly in `frontend/src/lib/storyTypes.js`): hook
   teaser 10 → **4s**, question / poll prompt 5 → **3s**, demo
   moment 15 → **5s**, announcement / countdown 10 → **4s**. The
   4-second frame is the primary target; 5 seconds is the
   ceiling, never the target; 3 seconds is the shortest frame.
2. **The frame-length pick is 3/4/5** (`STORY_FRAME_SECONDS`),
   everywhere the old 5/10/15 set was listed or validated: the
   Stories page pick, the create, plan and generate endpoints,
   and the story branch of the project PATCH. Off-pick lengths
   refuse with the new set named, as before.
3. **The spoken lines carry a word budget scaled to the frame**
   (`STORY_SPOKEN_WORD_BUDGETS` / `spoken_word_budget` in
   `story_types.py`): the hook and script **together** run at
   most **7 words at 3s, 9 at 4s, 12 at 5s** — one spoken line
   for the frame. `generate_story_plan` instructs the budget in
   the prompt beside the character budget, and enforces it with
   the plan's existing honesty pattern: one correction naming
   the counts, then a loud `RuntimeError` — an over-long line is
   never silently stored. A thought that needs more words is a
   second frame. The hook-video spoken-line rules and both craft
   scorers are untouched; the story craft check's four checks
   stand as they are.
4. **The kit's sticker adaptation is stated per platform in the
   catalog too.** The hook teaser's purpose now reads that the
   kit carries the link sticker **for Instagram** — TikTok has
   no link sticker, so there it points at the profile — and the
   announcement's that the countdown sticker is **for
   Instagram**, set to the founder's date, with the date riding
   the text sticker on TikTok. The kit checklist's per-type
   lines say the same in the founder's words: each sticker step
   is named Instagram-only, with the TikTok alternative (the
   profile for a teaser; the date in the text sticker for an
   announcement).

## Consequences

Existing story drafts keep their stored lengths only while the
length is still inside the new pick: a stored 10s or 15s frame
fails the PATCH and endpoint validation loudly rather than
rendering at a length nobody can pick anymore, and the plan
falls back to the type's new default when it re-plans. The
fake-provider end-to-end test now proves a 3-second question /
poll story submits `duration == 3` through the one render path.

One boundary is recorded honestly: **the app's own submit path
accepts 3 seconds end to end, but both catalog models declare a
5-second provider floor** — `VIDEO_MODELS` carries
`min_duration: 5` for HeyGen Video (OpenRouter lists its
supported durations as 5–15) and for MiniMax H3 Max, and
`generate_video`'s payload clamps the requested duration up to
that floor. So a real 3- or 4-second story render is submitted
by the app at its own seconds and reaches the provider at 5.
Nothing here raises the app's number silently to meet the
floor, and nothing lowers the recorded provider floor on
suspicion: whether to render short frames at 5 and trim, pick
a model whose floor is lower, or accept the provider's 5 is
Kasra's call, surfaced — not settled — by this record.
