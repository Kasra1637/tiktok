# ADR 0182: The hook opens with the goal, not the place

Status: accepted

Supersedes the place half of ADR 0167's NAME THE MOMENT.
Kasra's ruling, Nov 17 2026: in every video the character
starts by announcing where she is ("Saturday afternoon at
the mural…"), but the viewer can already SEE the place —
naming it wastes the hook's strongest slot. What she
should say instead is what she is trying to do in that
moment: the GOAL. He compared the sources — goal,
template, angle, plan, pain point — and chose the goal:
warmer than the pain point, already gathered per video,
and dynamic, working for any app profile. His approved
shape for the mural video: "I'm trying to keep count,
Saturday afternoon and I keep losing count." The day and
time may stay; the PLACE announcement is what goes.

## Decision

- **The shared rule is replaced.** In
  `_spoken_line_rules_block()`, NAME THE MOMENT becomes
  OPEN WITH THE GOAL, NOT THE PLACE: the hook opens with
  what the speaker is trying to do in the story's moment —
  the intention the video's selected GOAL names, turned
  into her own plain first-person trying-line — and never
  names or announces the place anywhere in the line,
  because the viewer can already see it. Never the goal's
  label or the app's words for it, and never a vague
  stand-in for the attempt ("I'm trying to feel better" is
  the named failure). A time grounding may ride along, and
  the hook still belongs to the script's own moment — she
  is in it, living it, not describing it from outside.
- **Every mirrored surface follows.** The plan schema's
  hook_line description, HOOK PUNCH, the bake-off
  candidate prompt ("Each opens with what she is trying
  to do…") and its correction ("the goal opening kept"),
  and `rewrite_hook_line` ("opens with the goal… a place
  the current line announces comes out"). HOOK POWER's
  doubling line now doubles the goal rule, and its model
  shape is Kasra's mural line; the scored pairs it teaches
  from stand verbatim, as evidence for the flaws they
  name. The ANGLE + GOAL block's PLACE + TIME line keeps
  the scene rule whole — the script and every visual line
  stay in the moment — and gains the hook's clause: the
  hook happens there too, but does not announce the place.
- **The goal was already there; the bake-off's now is
  too.** The plan, the strategy and both rewrites already
  carry the selected goal through `_angle_goal_block`
  (the objective in its OBJECTIVE_OUTCOMES words, plus
  the why-it-fits rationale), so the rule points at text
  the prompt already holds. The bake-off's story context
  was the one surface without it: it now carries THE GOAL
  FOR THIS VIDEO, from the same OBJECTIVE_OUTCOMES
  source, out of data the plan generation already holds.
  No new data flow was invented for any surface.
- **What stands from ADR 0167 and around it.** The
  complete-sentence rule, natural spoken order, the
  anti-meta ban, the open ending, first-person lived
  feeling, the resolution withheld — all unchanged. The
  script's scene grounding is untouched: the place is
  SHOWN, just not said. Cover text is untouched (it is
  on-screen text, not spoken; its moment-and-place rule
  stands). The Craft check scorer (creative_quality.py)
  is untouched, per the founder's standing order — the
  generator carries the doctrine, as it did for 0167.

## Consequences

The pins flipped honestly rather than being deleted:
the rules-block tests now pin the goal opening and the
place ban (and NAME THE MOMENT's absence); the rewrite
tests pin "opens with the goal" where they pinned "names
the exact moment"; the bake-off tests pin the candidate
and correction wording and the goal's presence in the
story context; the hook-power test keeps the scored
pairs and pins the new model shape; and a new test pins
the goal text itself — objective plus outcome meaning —
reaching the plan, strategy and rewrite prompts beside
the rule.

The cost is measured, in the ceiling test's own chain:
the shared block grows 6,943 → 7,739 chars (+796) and the
fully-populated strategy prompt 43,102 → 44,040 (+938,
the block plus the ANGLE + GOAL place line), so the
strategy ceiling moves 43,750 → 44,750, keeping ~710 of
headroom.
