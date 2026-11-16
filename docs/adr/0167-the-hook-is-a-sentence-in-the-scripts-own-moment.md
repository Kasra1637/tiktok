# 0167 — The hook is a complete sentence standing in the script's own moment, and the fix is the generator's, not the scorer's

- **Status:** accepted
- **Date:** 2026-11-15
- **Anchors:** `backend/ai_service.py` (`_spoken_line_rules_block`,
  `generate_creative_plan`, `_hook_bake_off`, `rewrite_hook_line`),
  `backend/test_hook_voice.py`, `backend/test_hook_bakeoff.py`,
  `backend/test_ai_json_calls.py` (strategy prompt ceiling). Extends
  ADR 0123 (Kasra's three spoken-line rules), ADR 0135 (hook power)
  and ADR 0145 (first-person alignment). `backend/creative_quality.py`
  is deliberately NOT an anchor: it does not change.

## Context

A generated pair made the gap visible. The script stood somewhere
concrete — "At the school gate on Monday I talk out loud, shoulders
shaking, and the racing stops feeling stuck in me. That blank ache
lifts before the bell." Its hook stood nowhere and was not a
sentence: "Losing thoughts in my head, moment instead of blank
page." — a participle fragment whose middle is scrambled, talking
about wording and pages instead of the lived feeling, naming no
moment at all.

The craft check scored that hook 18/20 Hook stopping power
(Clarity 10/10, Trust 10/10, Concreteness 9/10, Audience truth
11/15, Story arc 10/15, Spoken naturalness 7/10). Kasra put the
contradiction plainly — either the analytics is incorrect or the
rating is — and then made the decision this record holds: **the
Craft check algorithm and its scores do not change. The fix goes
into the hook generator.** A scorer can reward energy it can count;
only the generator can be taught the shape of the line. His
hand-written model of the fixed hook, from the same project:
"I can't write in my journal Monday morning at the school gate." —
one complete sentence, the script's own moment up front, plain
spoken words, the ending open.

The old doctrine allowed the failure in three places. NAME THE
MOMENT (ADR 0123) asked for *a* time or place, so a hook could name
a moment its script never visits — or, as here, none. Nothing in
the rules demanded a complete sentence that parses on the first
read; ONE STATEMENT banned two thoughts jammed together, not a
fragment with its words out of order. And HOOK POWER's meta ban
named labels and wording, but not pages or the act of naming —
the exact shape of "moment instead of blank page".

## Decision

The shared spoken-line block (`_spoken_line_rules_block`) is
sharpened in three places, and every surface that writes a hook
mirrors the tightening in its own words:

1. **HOOK SENTENCE (new bullet).** The hook is one complete
   sentence that parses on the first read — subject and verb in
   their natural spoken order, the thought arriving in the order
   it is understood. No scrambled middle the listener must rebuild,
   and no fragment standing in for a sentence: an opener that never
   gives the line a person doing something is a fragment, not a
   sentence.
2. **NAME THE MOMENT, tightened.** The hook stands in the
   SCRIPT'S OWN MOMENT and opens with it — the same time or place
   the script stands in, in the hook's first words; never a
   different scene invented for the hook, never the moment saved
   for halfway through the line. A hook written without its script
   (the clearer-hook rewrite) keeps the moment its story gives it,
   still first. The mirrors: the plan's `hook_line` field opens
   with the moment the script stands in; HOOK PUNCH opens inside
   that moment; the bake-off's candidates each open with the
   story's own moment and its correction keeps that moment first;
   the rewrite names the story's moment and opens with it.
3. **HOOK POWER's meta ban, extended.** Meta talk about labels,
   wording, pages or the act of naming a feeling is banned in one
   breath: the hook lives the feeling; it never discusses the
   words for it. The boundary with NAME THE ACTION stands — the
   journal as the speaker's real action ("I don't want to write in
   my journal today") is still the good example; the journal or
   the page as a *topic of commentary* is the failure.

The rules already hook-scoped stay as they are: WITHHOLD THE
RESOLUTION (the hook's ending stays open so the demo is the
answer — the Story arc doctrine), first person as the voice
(ADR 0145), and the ~60-character aim with the set-length hard
rule for suggestions (ADR 0130). The script's rules do not change.

Because the block rides in the strategy prompt, the strategy
prompt ceiling moves by the measured growth, per the ADR 0135
precedent: fully-populated prompt 42,221 → 43,102 (+881, exactly
the block's rendered growth 6,062 → 6,943); ceiling 42,800 →
43,750, keeping ~650 of headroom.

## Consequences

- The generator is steered on every hook it writes — plan draft,
  bake-off candidates and their correction, the clearer-hook
  rewrite, and a strategy writing without an approved plan — from
  each project's own material. Nothing is hard-coded from the
  school-gate example: his sentences appear only in the test
  corpus, per its existing conventions, never in a production
  prompt.
- The scorer's word stands. A future hook can still score 18/20
  and read scrambled to a person; that disagreement is now a
  known, accepted property of an advisory score, recorded here
  rather than relitigated per generation. If Kasra ever reverses
  the order, the scorer is where the change would go.
- No gate was added. The deterministic checks in `ai_spoken.py`
  are unchanged, so every existing bake-off and plan fixture keeps
  its measured behavior; fixtures that bend the new rules are the
  deliberate negative fixtures (the gated stars, the weak hook)
  whose rule-breaking is their test purpose. One fixture is named
  plainly: the certified-outcome test's draft, "Starting is where
  the setup friction wins.", names no moment — it stands as a
  gate fixture whose pinned totals are scorer measurements, and
  the scorer is untouched by the founder's order.
- Prompt cost: +881 rendered characters in every prompt carrying
  the shared block. The strategy ceiling raise is the named price,
  as it was for ADR 0135.
