# 0239 — The saved story is trimmed to its exact beat length

Status: accepted (settles the boundary surfaced by 0238; amends 0238)

## Context

ADR 0238 made story frames beats of 3, 4 or 5 seconds and
budgeted their spoken lines to fit, but it surfaced — without
settling — a gap between the app's number and the provider's:
both catalog models declare a **5-second floor**
(`min_duration: 5` in `VIDEO_MODELS` for HeyGen Video and for
MiniMax H3 Max), and `generate_video`'s payload clamps the
requested duration up to that floor. So a 3- or 4-second story
was requested at its own seconds, rendered and billed at 5,
and — until this change — **stored at 5**: the file the founder
posts was longer than the beat they picked, padded with exactly
the quiet tail the line was never written to fill.

Kasra's ruling (Nov 20 2026): stories must BE three to five
seconds in the posted file. Of the three ways to close the gap
— render at the floor and trim the saved file, accept
5-second files for everything, or hunt for a model with a
lower floor — he chose the trim: render five, trim the saved
story to its exact beat. The line is already written to the
beat's word budget (0238), so the cut takes only the tail past
the line.

## Decision

1. **The submit records the beat as the row's trim.** In
   `_submit_generation` — still the only render path — an
   exact-duration submit (the stories router is the only caller
   that passes `exact_duration`, ADR 0228) whose seconds sit
   below the model's `min_duration` now records
   `trim_to_seconds = ` its own seconds. At or above the floor
   nothing is recorded: a 5-second story already IS its beat
   and is stored untrimmed. The submit still **requests** the
   frame's own seconds exactly as 0228/0238 settled — what the
   app asks for and what the row records never move; only the
   delivered file was longer than both, because the provider
   payload clamps up to the floor and the provider renders and
   bills 5.
2. **The persist cuts the saved file's tail, in place.** The
   existing in-place length trim in `_persist_generation_clip`
   — the trim kept for pre-single-pass hook rows — now also
   serves the story beat: it runs before storage and before
   the row records a length, on the canonical path, so the
   stored file is the beat and anything that bridges from the
   file's final frame bridges from the frame the viewer sees.
   The cut is tail-only by construction (the trim keeps the
   head of the clip); the spoken line, budgeted to the beat,
   sits in the kept head.
3. **A successful beat cut writes no trim note.** The legacy
   trim writes "Cut down to Xs." into the row's
   `storage_error` slot — the slot the render panel reads as
   its durable-copy alert. For a hook row that note is honest:
   the delivered length deviates from what was rendered. For a
   story the cut IS the requested outcome, so the same note
   would raise a "Durable copy missing" alert on every short
   story ever saved. The persist therefore reads the project's
   `kind` once for its processing block and, for a story-kind
   row, suppresses the note on a successful cut — the head
   cut's reasoning (ADR 0181) applied to the tail. Legacy hook
   rows keep their note, byte for byte.
4. **A failed beat cut names the story and accounts for the
   floor.** If the cut fails, the full render is kept rather
   than lost, and the error names the story, not the hook:
   "Could not cut the story down to Xs, so it is delivered at
   its full rendered length." The row's delivered length then
   records what the founder actually gets — the model's
   `min_duration`, less the head cut when one applied — rather
   than the requested beat; `_apply_persist_outcome` already
   writes `duration = delivered_seconds`, so the row, History
   and playback stay truthful about the longer file. A
   successful cut records the beat outright, as the legacy
   trim did.
5. **Hook videos and the head trim are untouched.** A hook
   submit runs with `exact_duration` off and records no trim,
   so no hook video is ever tail-cut by this change (pinned in
   `test_generation_api.py`). The ADR 0181 HeyGen head cut is
   unchanged and composes with the beat cut on a HeyGen story:
   head first, then the tail down to the beat, landing on
   exactly the story's seconds (pinned against real clips in
   `test_story_tail_trim.py`).

## Consequences

A posted story file is now the length its frame declares —
3, 4 or 5 seconds — while the provider still renders and
bills its 5-second floor for the two shorter beats; the cost
of a short story is unchanged, only the delivered file is
honest. The end-to-end pins: the submit records the trim per
beat (3 → 3, 4 → 4, 5 → none) in `test_stories_api.py`, and
the persist is proven against real clips — cut to 3, cut to 4,
5 stored untrimmed, hook rows uncut, HeyGen head + tail
composing, and the failed cut delivering the full render with
the story named and the floor recorded — in
`test_story_tail_trim.py` and `test_stories_api.py`.
