# ADR 0145: First person earns craft points, and the cover text is scored and shown as part of the opening

Status: accepted

## Context

On Nov 14 2026 Kasra read out a live Craft check (Hook 13/20, Audience
truth 11/15, Clarity 10/10, Concreteness 7/10, Story arc 2/15, Spoken
naturalness 9/10, Demo handoff 10/10, Trust 7/10) and asked for the
full scoring methodology behind the eight dimensions to be read and
its weaknesses found, with one goal: more attention-grabbing TikTok
videos and more views. Reading `backend/creative_quality.py` in full
found a deterministic word-list scorer whose terms fought the
founder's own doctrine at four points:

- **Hook and Audience truth taxed the strongest voice.** Zero
  first-person markers earned +2; two or more cost points as a
  "diary". Kasra's strongest hook shape — set as the bar on Nov 13
  2026 — is first person: "After masking all day words in the quiet
  garden aren't mine." The bake-off and retry loop optimize toward
  the scorer, so the scorer was steering generation away from his
  best shape.
- **Story arc fought Demo handoff.** Story arc paid +3 for resolution
  cue words anywhere in the script, including the last line; Demo
  handoff pays for the last line staying open. The same bakery script
  scored Handoff 10/10 and Story 2/15: in a 15-second Hook + Story
  the demo IS the resolution, and Kasra's standing rule is that the
  script ends on the strongest concrete line that opens the
  discovery.
- **The first two seconds were only half scored.** The opening
  visual's words — the cover text — decide the scroll-stop alongside
  the spoken hook, but the scorer never read the cover text at all.
  It also never showed in the Create flow's steps, so the founder
  would have been graded on words he could not see.
- **The cue lists were frozen short of the founder's real world.**
  "Bakery" appeared in no list, so his actual setting earned nothing;
  a warm paper bag in hand — a felt detail — earned nothing either.

## Decision

The eight maxima and the /100 total do not change (the weights are
intentional, Kasra's standing ruling), and the score stays advisory:
it never blocks a render.

- **First person is rewarded, not punished.** Hook stopping power
  reads its cues over the opening whole (spoken hook + cover text)
  and pays +2 for a first-person voice; Audience truth pays +2 when
  the hook speaks as the viewer. What remains penalized is journal
  framing — self-reporting openers ("I've been...", "I keep...") —
  never the person: time-led openers are moment anchors, and the
  founder's hooks lead with the moment.
- **Story arc completes in the demo.** Resolution cues earn their +3
  only before the script's last sentence — a turn earned mid-story is
  craft; a wrapped-up final line is not. A last line that stays open
  (a gap, no closure) earns +2 of its own, so the deliberately open
  ending the format demands is worth more to the arc, not less, and
  Story arc and Demo handoff stop paying for opposite endings.
- **Concreteness knows the founder's places.** "Bakery" and "cafe"
  join the place and concrete cue lists; "paper bag" joins the
  concrete and sensory lists — real place words and felt details the
  lists previously missed.
- **The cover text is a first-class line of the plan.** The plan pass
  drafts it with the hook and script (a new `cover_text` field on the
  project, migration 0006), written to TikTok cover best practice:
  a few words only, readable inside the first two seconds; first
  person, the person's own voice, never a label or title; the moment
  and place up front with one concrete felt detail; it complements
  the opening visual instead of repeating what the image shows; it
  withholds the resolution; and it is never a copy of the spoken
  hook — a second angle on the same moment. Hook stopping power
  scores it with the hook, and its evidence names the cover when the
  cover carried a cue, so the contribution is visible, not silent.
- **Review shows the cover text, scored, and regenerable.** The
  Review step shows the cover text as a preview — as it will sit on
  the video's opening — beside the hook and script, with its scoring
  stated. Its own button regenerates it (generation only from its own
  button, ADR 0122): the fresh suggestion returns with the Hook
  stopping power it would earn, is never auto-saved, and is accepted
  through the normal edit path, exactly like the clearer-line
  suggestions. The post kit keeps the founder's approved cover text
  when one exists; its own generated cover follows the same best
  practice when none does.

## Consequences

- The scorer now steers generation toward the founder's proven shape
  — first person, moment-anchored, concretely felt, ending open —
  instead of away from it. The bake-off's hard filters are unchanged;
  only the advisory rubric moved.
- A founder can see, in Review, every word the opening is scored on:
  the spoken hook, the script, and the cover text, each with its
  score's reasoning.
- Honest limit, stated to Kasra when he approved this: no rubric can
  promise virality. This removes the scorer's self-contradictions and
  its blindness to the cover; it does not calibrate the weights
  against posted outcomes, which remains the open gap the verdict
  record (ADR 0124) exists to close over time.

## Addendum (Nov 14 2026): the generation side is aligned to this scorer

This decision moved the scorer first, and the build flagged that the
generation side still carried the doctrine the scorer had retired:
`rewrite_hook_line`'s prompt told the model to use "'I' at most once —
zero is better", and its acceptance check refused any rewrite speaking
in first person more than once. The same ration sat in the shared
spoken-line block's HOOK FORM bullet, in the plan editorial loop's
correction prompt, and — hardest of all — as a deterministic issue in
`ai_spoken._generated_spoken_issues`, which rewrote any plan hook with
two or more 'I's and hard-filtered such bake-off candidates before
scoring. Kasra approved aligning all of it the same evening.

So, in the follow-up commit: first person is stated as the voice in
every one of those places — "'I' is the goal, not a ration" — and the
count gates are gone. What remains banned is what this ADR always
banned: diary/journal framing (a log of what happened to me today)
and label/meta talk, carried by the prompts and by the scorer's
journal-opener tax, never by counting 'I's. The rewrite's remaining
acceptance checks are unchanged: the echo, the set length (ADR 0130),
and a question the angle does not invite. This addendum supersedes
one line of the Consequences above: the bake-off's hard filters did
change in exactly one respect — they no longer reject a candidate for
speaking in first person.

## Addendum 2 (Nov 15 2026): the bake-off's own prompts complete the alignment

The addendum above swept the places the alignment was known to touch
and missed two it did not: the prompt strings `_hook_bake_off` builds
itself. The candidates call still told the model "'I' at most once",
and the bake-off correction repeated it — both sitting in the same
prompt as the rules block that had just retired the ration, so the
contest ADR 0130 runs to pick the strongest hook was being briefed
against the founder's best shape. A docs sweep in the ADR 0147–0149
bundle found them; Kasra approved finishing the alignment.

Both strings now carry the rewrite's own wording — the speaker's own
first-person voice, "'I' is the voice of the hook, not a ration" —
and nothing else about the bake-off changed: three candidates, the
same hard filters, the same scoring, the same strictly-above-draft
shipping rule (ADR 0130 stands untouched). Prompt-content tests pin
both strings the way the rewrite's prompt is pinned. The same sweep
also found the ration still standing in two schema descriptions —
the plan prompt's `hook_line` field and the strategy prompt's
`hook_line` field; those are recorded here as known leftovers,
deliberately outside this fix, for a separate decision.

## Addendum 3 (Nov 15 2026): the two schema descriptions finish the alignment

Addendum 2 closed by recording the ration's last two hiding places —
the `hook_line` field descriptions in the plan prompt's schema and
the strategy prompt's schema — as known leftovers for a separate
decision. Kasra's direction was to finish the alignment everywhere,
and this is that decision: both descriptions now carry the same
wording as every sibling — the speaker's own first-person voice,
"'I' is the voice of the hook, not a ration" — in place of "at most
one 'I'". Nothing else in either description moved: the plan field
keeps its character budget and the strategy field keeps its word
budget, word for word.

A final sweep of the generation prompts (`ai_service.py`,
`ai_spoken.py`, `hook_prompting.py`, `ai_strategy.py`, `ai_text.py`)
finds no first-person rationing left anywhere; `ai_spoken` states
the opposite as a deliberate rule. Prompt-content tests pin both
schema descriptions the way the bake-off's strings are pinned. With
this, the generation side is fully aligned to this ADR: no prompt,
gate, or schema counts the hook's 'I's — what remains banned is
diary framing and label talk, exactly as the decision above set out.
