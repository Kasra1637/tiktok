# ADR 0377: The spoken gate charges a named place

## Status

Accepted, Nov 26 2026 — Kasra's order after a live
script named its place mid-line. The change lands
in `backend/ai_spoken.py`, in the defect gate
`_generated_spoken_issues`.

## Context

ADR 0294 settled that the spoken words never name
the place — the viewer already sees where the
speaker is. The rule lived in the generation
prompts alone, and it still shipped: Kasra's live
script read "After lunch on my harbour walk I point
to it and I'm calmer." The gate could not see the
leak. Its older place checks are an article slip
(fires only when the article is MISSING from a
place phrase) and the story-arithmetic scene checks
(which read the script's first and last sentences,
never as a defect) — and "harbour" stood outside
the scene vocabulary entirely. A rule with no gate
behind it is a hope, and the hope failed on a
possessive locative phrase in the middle of a
script.

## Decision

The gate now charges the construction itself: a
locative preposition phrase built on a place noun —
"on my harbour walk", "at the kitchen table", "in
the garden" — in the hook or the script:

- The noun carries the charge, so the doctrine's
  allowed riders cannot trip it. Light time
  grounding names moments, not places ("after
  lunch", "on Wednesday", "Saturday morning"), and
  body sensations name the body, not a place ("in
  my chest", "to my stomach") — weekday, mealtime
  and body words stand outside the vocabulary.
- The vocabulary extends the scene cluster's place
  words in its own style — single concrete location
  nouns, grown by witnessed leaks ("harbour" is the
  witnessed one) — and a phrase may carry one
  compound tail ("harbour walk", "kitchen table",
  "bus stop"), because a place compound names the
  place as plainly as its head noun alone.
- The charge names the phrase it caught and tells
  the rewrite what to do instead: drop the place
  and let the feeling carry the line.

## Checks

New in `backend/tests/test_spoken_pov.py`:

- "test_script_naming_a_place_on_a_locative_phrase
  _is_a_hard_issue" pins Kasra's witnessed line —
  the charge fires and names "harbour walk".
- "test_script_at_the_kitchen_table_is_a_hard_issue"
  pins the compound-tail form.
- "test_hook_naming_a_place_is_a_hard_issue" pins
  the charge on the hook, not only the script.
- "test_time_grounding_and_body_sensations_name_no
  _place" pins the allowed riders: a generation
  carrying after-lunch, Wednesday, Saturday-morning
  and in-my-chest lines earns no issue at all.

Changed, named per the house rule — every one a
fixture whose spoken line named a place, losing the
place phrase and nothing else:

- In the same file, the persistent-quotes fixture's
  opening words "At the desk, I say…" become
  "Leaning in, I say…" — the quote test was silently
  depending on the gate not seeing "at the desk".
  The quote behavior it pins is unchanged.
- `test_ai_json_calls.py`: the recorded production
  line behind the continuity test drops "in the
  car" (kept: the dangling "walk in", the point the
  test exists for), with the reason recorded inline.
- `test_creative_quality.py` and
  `test_hook_voice.py`: the shared sample scripts
  open "Before breakfast stretching" instead of "In
  the garden stretching", and the strong script
  drops its garden opening the same way.
- `test_hook_voice.py`'s plan-loop pair is
  recalibrated, with the arithmetic recorded inline:
  its porch step came out (a good draft can no
  longer carry a named place), and the hook's
  recurrence cue earns back what the place words
  paid, so the pair stays over the same craft bar.
- `test_spoken_line_rewrite.py`: the screenshot
  series' clearer replies drop "at my desk" — a
  clearer line carrying a named place could never
  be accepted again — and the fragment-correction
  pair drops it the same way, the fragment staying
  a fragment. The stored script keeps its place:
  it is the flawed input the clicks exist to fix.
- `test_hook_bakeoff.py`: the draft hook and the
  best clean candidate both carried "at my desk";
  both are re-cut without the place, with the
  recalibration recorded at the fixture. The gated
  stars (the bare "bus stop" and "office") are
  untouched — they were always the gate's, and
  every pick the suite asserts still lands.

## Alternatives considered

Charging any locative preposition phrase at all:
rejected — it would fire on the allowed riders and
teach the model to drop its time grounding and its
body sensations, both of which the doctrine wants.
Extending only the scene vocabulary: rejected —
the scene checks do story arithmetic, not defects;
a place named mid-script would still pass them.
