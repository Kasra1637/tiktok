# 0135 — Hook power taught from the founder's scored pairs, and the feature-noun ban becomes a gate

- **Status:** accepted
- **Date:** 2026-11-14
- **Anchors:** `backend/ai_service.py` (`_spoken_line_rules_block`,
  `generate_creative_plan`, `generate_video_strategy`,
  `rewrite_hook_line`, `rewrite_spoken_line`, `_hook_bake_off`),
  `backend/ai_spoken.py` (`_feature_noun_hit`, `_FEATURE_NOUNS`,
  `_generated_spoken_issues`), `backend/test_hook_voice.py`,
  `backend/test_hook_bakeoff.py`, `backend/test_ai_json_calls.py`
  (strategy prompt ceiling). Extends ADR 0123/0128 (spoken-line gates)
  and ADR 0130 (the bake-off's hard filter).

## Context

The founder walked six live garden/masking hooks with their craft
Hook stopping power scores — 7/20, 12/20, 13/20 among them — and set
the bar: hooks must reach at least 15/20 going forward. The hooks the
app produced were competent sentences that stopped nobody. He named
five leaks, each visible in his own examples:

1. **The hook gives away the resolution** — "talk it out", "isn't
   your words", "start to sound like me": the payoff is spent in the
   opening line, so the demo that follows has nothing to answer.
2. **Meta talk about labels and wording** instead of the lived
   feeling — the hook discusses the label instead of feeling it.
3. **Report voice** — third-person, label-voice narration instead of
   the person living the moment; two statements jammed into one line.
4. **Abstract verdict words** ("borrowed") instead of concrete felt
   detail.
5. **App feature words spoken aloud** — "reflections" reached him
   inside a hook. The craft block had banned the app's feature nouns
   since the rule was first written, but the ban was prompt-side
   only: no deterministic check existed, and the noun shipped.

His strongest shape, in his own words: "After masking all day words
in the quiet garden aren't mine" — moment + place + first person +
resolution withheld.

Two enforcement shapes were put to him for the 15/20 bar. The HARD
shape: no hook under 15 ships, and a plan can refuse loudly instead
of shipping one. The SOFT shape: strengthen the generation
instructions so 15 becomes typical, with no shipping floor. **On
2026-11-14 he chose SOFT, and the hard floor was rejected.** A
below-15 hook can still ship; the ADR 0130 bake-off's best-candidate
logic is unchanged — a candidate ships only when it scores strictly
above the draft, exactly as before.

## Decision

**The hook rules are taught, from his scored pairs, in the shared
block.** `_spoken_line_rules_block()` gains a HOOK POWER bullet,
riding in every prompt that writes a hook — the plan, the strategy
(when it writes its own words), both rewrites, and the bake-off,
which receives the same block. Five rules:

1. **Name the moment** — a time or a place, exact (the existing
   hook-specific reinforcement; the general NAME THE MOMENT bullet
   already stood).
2. **First person, lived feeling** — the speaker's own words (my
   words, my voice, mine); never label-voice or meta talk about
   wording/labels, never third-person report voice.
3. **Withhold the resolution** — name the problem and stop; the
   demo that follows is the answer.
4. **One statement** — one thought only, never two jammed together.
5. **Concrete felt detail over abstract verdict words.**

The bullet teaches with his fixtures verbatim, scores attached:
"Label isn't me after masking, I talk it out in quiet garden" (7/20 —
label-voice, resolution given away); "Generic label after masking in
quiet garden isn't your words" (12/20 — label-voice, third person,
resolution given away); "after masking all day quiet garden words
feel borrowed" (13/20 — "borrowed" is a verdict word); and the strong
shape quoted in Context. The strategy prompt's measured ceiling
moves with the block: 40,816 → 42,153 chars (+1,337, exactly the
block's growth), ceiling 41,500 → 42,800 with the usual headroom,
recorded in the ceiling test's ledger.

**The feature-noun ban becomes a deterministic gate.**
`_feature_noun_hit` joins `ai_spoken.py` in the style of the
grammar and UI-control gates: whole-token matching on normalized
text against `_FEATURE_NOUNS`, a list kept to the one noun the
prompts themselves name as the app's feature word — **"reflections"**.
The list grows by witnessing another leak, never by guessing at
vocabulary. Ordinary speech cannot flag: the singular act ("a quiet
reflection on the porch") and the plain verb ("the lake reflects the
last light") are different tokens, and the everyday words the craft
block offers instead ("what I wrote", "my notes", "the words on the
screen") contain none of the list.

Wired into `_generated_spoken_issues` per spoken line, which wires
both required paths at once: the plan pass's editorial loop treats
it as a correctable hard issue (a draft hook or script speaking the
noun is rewritten, and refuses after the bounded attempts like any
hard defect), and the bake-off's hard filter removes any candidate
carrying it before scoring — a feature-word candidate cannot win,
however high it would score. The craft scorer reads the same issue
list (ADR 0115), so the noun also costs score wherever it appears.

## Consequences

- Hook generation is steered, not floored: nothing in this record
  stops a below-15 hook from shipping. If the bar keeps being
  missed, the rejected hard shape is the recorded next option and
  needs a fresh founder decision.
- The gate's list is deliberately one word. Profiles whose apps name
  their features differently are still covered by the craft block's
  general ban (any app's own feature names, in the prompt) and by
  the profile's own facts; only the witnessed noun is deterministic.
