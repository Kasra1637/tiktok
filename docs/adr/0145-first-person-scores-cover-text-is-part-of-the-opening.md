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
