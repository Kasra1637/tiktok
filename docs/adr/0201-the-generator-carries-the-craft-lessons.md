# ADR 0201: The generator carries the craft lessons

Status: accepted

Kasra's order on Nov 18 2026: read what each Craft check category
says a pair must do to earn its points, then strengthen the
GENERATION prompts so future hook+script pairs close those gaps —
"a system in place that detects what needs to be placed or what
needs to be changed to get the score up" already exists; the
prompts should write to it. This is generator-side only. The
scorer (`backend/creative_quality.py`) does not change: no
weights, no cue lists, no caps, no grade logic. The founder's own
clips of Nov 18 2026 supplied the evidence — a 72/100 pair whose
hook "states a situation" and whose script opened in retrospect,
and a pair that lost 6 Trust points to two unfinished sentences
and was capped to F for them (the cap itself is ADR 0202).

## The gap map

Each category of `creative_quality.py` was read in full, and every
payment was checked against the actual prompt text (the shared
spoken-line block, the plan prompt, the strategy prompt, the
rewrite prompts). Only verified gaps were closed:

- **Hook stopping power (+3 problem cue, +2 concrete anchor).**
  The block said "name the problem", and ADR 0182 reframed the
  hook as a goal-first trying-line — which, bare, states a
  situation and earns neither payment. Both founder pairs scored
  "No clear cost or problem cue". The block now states THE COST
  RIDES ALONG: the trying-line names what keeps going wrong while
  she tries, resolution still withheld. The time grounding was a
  permission ("may ride along"); it is now an instruction — one
  anchor (day, time of day, named routine moment), never the
  place (ADR 0182 untouched).
- **Concreteness (+2 place).** The place was instructed for the
  visual `scene.location` and in the strategy's middle rules, but
  no shared instruction put it in the SPOKEN script — and the
  hook may never name it, so a pair could name no place anywhere
  (both founder pairs did exactly that). EXTENSION now states the
  script's first sentence names the place she is in, with its
  article — which also answers Trust's bare-place charge ("at bus
  stop", ADR 0128) before it can fire.
- **Story arc (first-clause answer, scene opening).** "Answers
  its question in the first clause" was already instructed
  everywhere, yet both founder pairs missed the payment: each
  script opened with a preamble (retrospect — "Looking back over
  my recent days" — or a lately-summary) and answered late. The
  failure shape is now named and banned in EXTENSION, and the
  scene lands inside that same first sentence rather than before
  the answer.
- **Spoken naturalness (−2 per sentence past 18 words, −2
  fronted modifier).** No prompt anywhere stated a word limit;
  both founder pairs lost points to 19- and 23-word sentences.
  CONVERSATIONAL now carries BREATH: no sentence past 18 words,
  split the thought instead — and sentences lead with the person,
  never with a scene phrase trailing into a comma (the fronted
  modifier's shape). Contractions are named in the block for the
  first time (the plan and strategy already asked for them).
- **Trust & compliance (−3 per unfinished sentence).** The plan
  prompt stated COMPLETE SENTENCES plainly; the shared block
  stated completeness for the hook only, and the strategy prompt
  and both rewrite prompts — which write lines with no plan to
  bind to — carried no finished-sentence rule at all. The block
  now carries FINISHED SENTENCES for both lines: capital start,
  own full stop, nothing trailing on a joining word, no fragment
  in the script, no semicolon in the hook — and the distinction
  the doctrine needs: the open ending is a complete sentence
  whose thought stays open, never an unfinished sentence.
- **Concreteness / Story arc (−2 vague stand-in payoff).** The
  plan's schema named the banned shapes ('a word', 'that vague
  sense'); the shared block only said "strongest concrete line".
  The ending rule now names the stand-ins in the block itself.
- **Clarity and Demo handoff** scored 10/10 on the founder's
  panel: deliberately untouched — no churn where the prompts
  already earn full marks. **Audience truth** likewise: first
  person, concrete language and the promotion/founder bans were
  already instructed.

Deliberately NOT instructed, recorded so a future reader does
not "fix" them: the +1 for direct "you/your" address (Audience
truth) — the doctrine is that the hook is her lived line in first
person, not an address; the +1 trigger-word payment (Hook) —
instructing a trigger word followed by a concrete cue is
cue-list gaming, and the concreteness rules above cover the
territory honestly; the scorer's internal tension between
"notice/tend to" as written cues (Naturalness) and insight cues
(Story arc) — a scorer question, and scorer changes are the
founder's call alone. The capped category maxima the Nov 18
audit found (Hook 17/20, Audience 13/15) are likewise untouched:
that decision is still open.

## Where the rules live

All six additions live in `_spoken_line_rules_block`
(`backend/ai_service.py`), the one block the plan, the strategy,
both rewrites and the hook bake-off all consume — so no flow can
drift back to writing without them. No flow prompt needed its own
copy; the plan keeps its COMPLETE SENTENCES rule, now backed by
the block rather than standing alone. The block grows
7,739 → 9,308 chars (+1,569); the fully-populated strategy
prompt measures 46,244 → 47,813, and its ceiling moves by the
established measured pattern to 48,600 (~790 headroom). One
temperature (ADR 0199), the app-profile flow and all render code
are untouched, as is `ai_spoken`'s detection logic.

## Pins

`backend/test_craft_gap_prompts.py` pins each new instruction in
the block and in the assembled plan and strategy prompts (red
before green: all eight failed on the old block). The strategy
ceiling test's comment chain records the measurement.
