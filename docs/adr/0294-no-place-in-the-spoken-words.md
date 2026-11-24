# ADR 0294: No place in the spoken words

Status: accepted

## Context

Kasra re-raised a rule he had given before and was angry to see
still broken (Nov 23 2026): the spoken words name the place the
presenter is in — his example was a generated script opening "At
the kitchen table after lunch on Wednesdays…" — and naming it
brings no value, because the viewer on TikTok already sees the
place. He confirmed the scope in his own words: the location
comes out of the script and the hook line; the feeling stays in
the hook, right at the start. "Don't touch anything else. Just
that."

The hook already complied — the shared rules and the Hook + CTA
prompt both ban the place anywhere in the hook line (ADR 0182).
The script did not: ADR 0201's EXTENSION rule required the
script's first sentence to name the place with its article,
deliberately parking in the script the place the hook could not
say. The whole-script remake (ADR 0205) repeated the requirement
in its own prompt. The cover text had the same habit: the shared
cover block and both schema lines put "the moment and place up
front" — and the cover Kasra was shown read complete, confusing
and unclear to him; he ordered it fixed along with the rest: the
ache first, in plain words, one short line, the picture carrying
the rest.

## Decision

Generator-side wording only, in `backend/ai_service.py`:

- The EXTENSION rule in the shared spoken-line block no longer
  names the place. The script's first sentence lands inside the
  moment through what she does and feels — one concrete action,
  one body detail ("I press my palm to my stomach") — and never
  the place: the viewer sees it already, so no "at the kitchen
  table", no "at the bus stop". This supersedes ADR 0201's
  place-naming sentence; the rest of ADR 0201 (answers the hook in
  the first clause, no looking-back preamble, two beats max, the
  open ending) stands unchanged.
- The script remake's prompt and docstring say the same: the
  remake opens by answering the hook from what she is doing and
  feeling in it, never the place.
- The cover rules lead with the ache: the shared cover block now
  reads "The ache up front, in plain words, with one concrete
  felt detail — never the place", and the plan and post-kit
  schema lines match. The cover's size (3 to 5 words, 35
  characters), first-person voice, and withheld resolution are
  unchanged (ADR 0206).

Nothing else moves. The Location field still names the place for
staging, direction, templates and the scene-consistency guard —
only the spoken words and the cover stop saying it. The Craft
scorer is untouched (Kasra's standing rule): generated pairs no
longer earn its place-named Concreteness credit, by his order —
the words' job is the viewer's stop, not the score's.

## Consequences

- One doctrine test re-pinned: the script-opening pin in
  `backend/test_craft_gap_prompts.py` now pins the no-place rule
  and the action/body-detail opening; the plan and strategy
  prompt pins still hold ("at the bus stop" remains in the block,
  now as a place-opening to avoid).
- The strategy prompt stays under its 48,600-character ceiling —
  the new EXTENSION wording was compressed until the budget test
  passed with the change in.
- Scripts and covers generated before this change keep their
  place-naming; the rule governs new generations and remakes.
