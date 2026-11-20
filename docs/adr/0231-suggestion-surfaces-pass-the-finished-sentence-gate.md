# 0231 — Suggestion surfaces pass the finished-sentence gate

Status: accepted

## Context

On Nov 20 2026 Kasra reported generated cover text, hooks and
scripts coming out incomplete — fragments like "Sunflower gate,
I can't write" and a suggestion cut at exactly the 35-character
cover ceiling mid-sentence — with occasional spelling slips.

The diagnosis, verified in code before any fix was written:

- It is NOT transport truncation. `_chat_json` detects a
  `finish_reason=length`, doubles the budget and raises
  `TruncatedResponse`; the budgets are large (plan 32768,
  rewrites and cover 6000).
- The finished-sentence gate — `_generated_spoken_issues` in
  `backend/ai_spoken.py`, which rejects an unfinished sentence,
  a sentence ending on a dangling function word, an unfinished
  comparison, a continuation opening and the wording families —
  was enforced ONLY in the plan editorial loop and the hook
  bake-off. The suggestion surfaces `rewrite_hook_line`,
  `rewrite_spoken_line`, `rewrite_whole_script` and
  `generate_cover_text` in `backend/ai_service.py` validated
  length, echo and question shape only. A model line squeezed
  against a character ceiling keeps its start and drops its
  tail, and the fragment passed every check those surfaces ran.
- Spelling: no code corrupts characters — cleanup is whitespace
  collapse, quote stripping and whole-word neutralize only.
  Misspellings are raw model output passing unchecked; no
  deterministic check in this fix claims to catch them.

Out of scope, deliberately: the deterministic trims in
`ai_spoken.py` (`trim_to_sentence`, `_trim_hook_line`,
`trim_spoken_body`) still cut rather than refuse — making them
refuse is a separate decision, flagged to Kasra and not bundled
here. The craft scorer is untouched.

## Decision

1. **Every suggestion surface runs the gate.** Two adapters in
   `ai_service.py` shape the pair-check for one line.
   `_spoken_gate_issues` puts a hook line in the hook slot with
   an empty script (dropping the "script is empty" bookkeeping),
   and a script line — a middle sentence or a whole-script
   remake — in the script slot beside the founder's saved hook,
   dropping the hook slot's own issues: the saved hook is not
   the suggestion's defect. The budget is the surface's own set
   length when it has one, else the line's length, so the gate
   never invents a ceiling. `rewrite_hook_line` passes its own
   question allowance (the founder's hook asks, or the angle
   invites one) through to the gate; its question branch is
   restructured so the gate runs after the existing question
   handling, not instead of it.
2. **The cover is judged as a cover.** `_cover_gate_issues`
   runs the same gate with the unfinished-sentence charge
   waived: a cover is a fragment by design — a few words, no
   period — so requiring a terminator would refuse every
   legitimate cover. What is not waived is a thought cut in
   half: a cover may not end on a dangling function word or an
   unfinished comparison, begin as a continuation, join with a
   semicolon, ask a question, or carry the wording families.
   Issues are renamed to the cover's own name ("cover text …").
   The honest boundary, stated plainly: a cut that lands on a
   grammatically complete clause — "Thursday sunflower gate,
   I'm racing" — is beyond word arithmetic and stays the
   prompt's business; the gate refuses the observable cut only.
3. **Failure follows each surface's existing pattern.** The
   gate runs after the surface's length/echo/question checks,
   right before return. A failing reply gets one correction
   retry with the issues named, then the surface's loud refusal
   (`RewriteRefusal`) — hook and middle: "The rewrite kept
   coming back unfinished…"; whole script: "The remake kept
   coming back unfinished…"; cover: "The cover text kept coming
   back cut off mid-thought…". A fragment is never silently
   passed or stored.
4. **One existing pin moves.** `test_angle_scene.py`'s canned
   hook reply ("I don't want to write in my journal today")
   carried no period; under the gate that reply is a fragment,
   so the fixture and its assertion gain the period — an
   intentional pin update for the new behavior, recorded here.

## Consequences

The four surfaces now refuse the exact defect Kasra reported —
a line that kept its start and dropped its tail — with the same
one-correction-then-refusal honesty contract they already had
for echoes, questions and overruns. Regression tests pin each
surface: a tail-dropped fragment is corrected on retry or
refused, never returned as-is, and the well-formed fixtures the
suite already carried pass the gate unchanged (verified by probe
before the code was written). What this does not promise: a
grammatically complete but semantically cut line, and spelling,
remain the model's and the prompt's business — the gate is word
arithmetic, not a grammar parser, exactly as its docstring has
always said.
