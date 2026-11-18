# ADR 0187: The opening movement enacts the story, on this video's own channel

Status: accepted

Kasra's ruling, Nov 17 2026, from comparing two of his
own renders frame by frame. The mural render he loves
opens with her hands up in front of the camera, counting
the days on her fingers — the gesture IS the story's
action, already moving in the first second, pausing
mid-count — and its end behavior grabs attention just
as hard. The quad-steps render from the new goal-first
generator opened with her hand resting on her chest for
the first seconds: clean first frame (ADR 0181's trim
verified on it), but the hook's body arrived late. His
words for the rule: rapid behavior, relevant to the
story of the video, consistent across all videos, but
unique in each one.

Minutes later he refined the channel, correcting a
paraphrase that had made the mural's finger-count sound
like the template: NOT always a hand gesture — "some
human movement or behavior whether it's her face,
mouth, hand, camera or something — all the time should
be unique to the video", and of the finger-count itself,
"not every time". The mural's gesture is one example of
the shape, not the template.

## Decision

- **One shared block states the rule.**
  `_behavior_direction_rules_block()` in ai_service.py
  (1,728 chars) joins the plan prompt and the strategy
  prompt — the two surfaces that author behavior
  direction. Its four bullets:
  - OPEN MID-MOTION, RAPID: the first frame catches a
    movement already underway and its snap completes
    inside roughly the first second. A resting pose, a
    hand sitting on the chest, or a slow settle as the
    opening is explicitly banned.
  - THE MOVEMENT ENACTS THE STORY: the opening movement
    physically performs the central action of THIS
    video's script — the thing the person is doing in
    the story's own moment — named concretely in the
    action lines, derived from the script's moment. A
    movement that could sit unchanged on any other
    video is a failed opening.
  - THE CHANNEL IS THIS VIDEO'S ALONE: a hand or the
    fingers, the face or an expression shift, the
    mouth, the whole body, or a camera move toward the
    presenter — whichever this story's action calls
    for. The requirement (rapid, story-enacting, inside
    the first second) is the same in every video; the
    movement itself never is. Never a fixed gesture,
    never a gesture library, never the same device by
    default.
  - CLOSE WITH ENERGY: the last second or two carries
    a sharp closing beat with the opening's energy —
    the story's action left visibly unfinished, or
    turned back to the viewer — never a soft fade and
    never a passive smile hold. Where a setup adds the
    final physical beat itself at render time (the
    selfie ending), the middle's last action still ends
    sharp and unfinished rather than settling.
- **The schema lines that author the fields carry it
  too.** The plan's beat_timeline hook beat ("the
  movement first…") and its middle beat (the sharp
  closing beat); the strategy's hook_action line and
  segment-0 action line; and
  `ai_strategy._two_section_schema`'s hook action — all
  now demand the rapid, already-underway, story-enacting
  movement through this story's channel, instead of the
  old generic first-beat verb list standing alone.
- **The render prompt restates it as fixed text.**
  generation_planning assembles the strategy's fields
  verbatim, so the rule lives where the fields are
  authored (above) — and where the assembly phrases
  movement itself, it now says the same thing:
  `_OPENING_INTERRUPT` gains the enacting/channel/
  no-resting-pose sentences and its condensed twin
  keeps every constraint in compressed wording; the
  final-beat templates (the selfie ending and the
  fixed-camera phone handoff, full and condensed) close
  sharp with the opening's energy, never a soft fade
  or a passive smile hold; and the single-pass fallback
  builder, which phrases the opening itself, states the
  rule once in its own section.
- **What is untouched, deliberately.** The Craft check
  scorer (creative_quality.py) — the founder's standing
  rule; a test pins the rule's wording absent from it.
  The spoken-line rules (ADR 0182's goal-first hook and
  the rest of the shared spoken block) — the behavior
  block is a sibling, not an edit inside them. The
  spoken-line rewrites and the hook bake-off write words,
  not behavior, so they do not carry it; the strategy
  refresh path regenerates through the plan prompt, so
  it is covered there. `opening_move`'s validator is
  unchanged: it already refuses an opening with no
  visible move, and the resting-pose ban is generator
  wording at the place the direction is authored.
  Every existing behavior/scene field keeps its meaning;
  the rule strengthens the direction inside them and
  removes nothing. Scope is the ~15s presenter segment
  (hook + story), as always.

## Consequences

New pins (test_behavior_direction.py, red before green):
the shared block's wording; the block verbatim in both
the plan and strategy prompts; the derived-movement
demand in the strategy's hook_action schema and in the
two-section schema; the render prompt's enacting
opening and energetic close in full, condensed, fixed
and single-pass forms; and the scorer's freedom from
the rule's wording.

The cost is measured. The fully-populated strategy
prompt grows 44,040 → 46,244 (+2,204: the 1,728-char
block plus the strengthened schema lines), so the
strategy ceiling moves 44,750 → 47,000 in the ceiling
test's own chain, keeping ~750 of headroom. The render
floors: FULL 4,019 → 4,013 (−6 — in the full directive
the enacting sentence replaced the old gesture examples
and a paragraph-2 clause it made redundant, so the rule
rides at no net cost there), CONDENSED 2,244 → 2,476
(+232 — compressed harder than the full form, because
at HeyGen's 4,090 ceiling with the script held sacred
the uncompressed condensed sentence landed a saturated
prompt 44 chars over, and fixed text is the only text
the squeeze cannot take back), SINGLE_PASS 2,302 →
2,835 (+533).

An early uncompressed draft of the full-form wording
grew the render floor by ~550 and, through the fit
loop's scale arithmetic, pushed realistic prompts to
scales low enough to clip the strategy brief's payoff
lines out of the final prompt; the prompt-dedup and
influencer-specificity suites caught it, and the
shipped wording pays for the rule out of the examples
it replaces, so those suites pass unchanged. One
existing pin flipped honestly: test_location_source.py's
visible-first-move test asserted the schema's old
"first 1-2 seconds" phrasing and now asserts the
ADR 0187 form (already underway in the first frame,
snap complete inside roughly the first second); the
strategy rules bullet keeping "first 1-2 seconds" is
unchanged. The opening-move validator (opening_move.py)
was not changed: it already refuses a plan whose
opening names no visible move — the ban on resting
openings lives in the generator wording, where the
direction is authored.
