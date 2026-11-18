# ADR 0188: Each craft trait is paid once, and the cue lists know the in-between places

Status: accepted

Kasra's order, Nov 17 2026, after a full methodology review
of the Craft check (backend/creative_quality.py): the eight
categories and their weights are right, but the calculation
pays some traits two or three times, its word lists miss
ordinary places from real scripts, and the Story arc tooltip
reads as if it contradicts itself. Fix the calculation; the
categories, the weights (20/15/10/10/15/10/10/10), the
deterministic cue method and the trust cap do not change,
and the scorer does NOT learn from outcomes — he rejected
that explicitly: "I don't want it to learn. That's not what
it's supposed to do."

## Decision

- **First person has one home: Audience truth.** It was paid
  in Hook stopping power (+2), Audience truth (+2, −1 when
  absent) and Demo handoff (+2 when the last line held "I"),
  so one trait moved three scores. The Hook and Handoff
  payments are removed; Audience truth — the customer-voice
  category — keeps its payment and its penalty. The Hook's
  advice line no longer names first person as something this
  category pays for.
- **The open ending has one home: Demo handoff.** It was
  paid in Story arc (+2 for a gap ending with no closure)
  and in Demo handoff (+4 gap, +2 named question, −3
  closure), so a pair's ending moved two scores. The Story
  arc payment is removed; Story arc keeps the problem, the
  insight, the mid-script shift (resolution cues still read
  before the last sentence only, so the two dimensions never
  pay for opposite endings), the echo/scene/action signals
  and its penalties. Demo handoff's arithmetic is unchanged
  apart from the first-person removal above.
- **The cue lists learn the in-between places.** The
  concrete/place/action/time/sensory lists stopped at rooms
  and furniture, so the founder's real rendered lines — the
  quad steps after class, the announcement on the platform —
  scored as if their scenes were abstract (the platform
  script's Concreteness read 6; it reads 9 now). The lists
  gain a curated set of everyday lived-environment words:
  steps, stairs, hallway, platform, station, counter, queue,
  doorway, parking lot, sidewalk, bench, bus stop, waiting
  room, driveway, elevator; the sound of a place
  (announcement, noise, buzzing, ringing); the small verbs of
  waiting and getting there (climb, wait, carry, hold); and
  the day's named anchors (commute, school run, workout,
  break time) as time cues. Whole-phrase matching already
  prevents substring false hits. App/screen words are NOT
  added — "screen" stays an app-behavior cue, because the
  story must stay out of the app's screens.
- **The Story arc advice now says what the scorer does.**
  The old next step ("Make the script answer the hook's
  problem in its first clause, live in first person, and end
  on the strongest concrete line…") read as contradicting
  the findings list beside it. The scorer penalizes NOT
  answering the hook in the first clause (−1), pays a shift
  landed before the last line (+3), and pays the open ending
  in Demo handoff. The new line says exactly that: answer
  the hook in the first clause, land the shift before the
  last line, leave the last line open for the demo. Copy
  only; no scoring change in this item. The frontend's
  standing per-dimension explanations are updated to match
  (Hook no longer claims first person earns there; Story
  arc names the handoff as the open ending's home; Demo
  handoff no longer claims first person earns there).
- **The tooltip duplication was in the text layer, not the
  layout.** Radix's TooltipContent renders its children
  twice: once visible, and once in a visually hidden
  accessible copy that the trigger's aria-describedby points
  at. With no aria-label, the hidden copy repeats the whole
  findings-and-advice block word for word, so the founder's
  pasted tooltip text read everything twice. The craft
  tooltip now passes a one-line aria-label ("Story arc /
  payoff: 9 of 15"), which replaces the hidden copy; the
  findings and advice exist exactly once. A render-smoke
  assertion counts occurrences of an evidence line and a
  next step in the tooltip's text and requires one each.

## Consequences

Scores move only where a double payment or a blind spot was
doing the moving. The review's worked examples: the generic
sample pair 62 → 58 (its first person no longer pays in two
extra categories); the strong rewrite pair 84 → 82 (the
open ending now pays once, in the handoff, where the clamp
already held it at its max); a closed ending's Story arc now
ties its open twin (11 = 11) while the whole difference
lands in Demo handoff (10 vs 2). Stored reports are frozen
at submit (ADR 0117) and keep the arithmetic they were
scored with; the Review card recomputes on read, so current
projects show the new numbers immediately.

The tests land with it (backend/test_creative_quality.py):
the first-person pair now asserts the voice moves Audience
truth alone and ties in Hook; a new test pins the open
ending's single home (equal Story arc, different handoff);
a new test pins the widened lists against the founder's two
real rendered scripts. One downstream calibration moved
with the arithmetic: the plan loop's craft retry fires
below a total of 80 (CRAFT_RETRY_BELOW), and the plan-loop
tests' "good" pair was calibrated to total exactly 80 under
the old payments. It earns the same 80 now — the script
gained an insight beat and lost an abstract noun — with the
hook, the named place and the open ending unchanged
(backend/test_hook_voice.py).
