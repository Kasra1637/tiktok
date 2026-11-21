# 0249 — Outcomes are stored whole, hooks must be complete in meaning, and the Hook + CTA card has one hook button

Status: accepted (the unified button supersedes the two-action arrangement ADR 0244/0247 left in the Hook card; the completeness bar and the dangling-question charge extend 0231's gate family without changing its verdicts elsewhere)

## Context

Four findings from Kasra on Nov 21 2026, all from the live Hook + CTA
page:

1. The Focus dropdown (ADR 0247) offered broken options: beside
   whole outcomes ("Emotional clarity without hunting for labels
   yourself", "See your own rhythms") sat "triggers", "and growth
   over time", "on your terms", "from your own words" — lowercase
   sentence pieces. His words: each selection should stay one line,
   start cleanly, and be "more punchy and easy to understand … so
   they can easily select one of the good focus area they want."
   Diagnosis: nothing in the app splits outcomes at display time —
   the profile research itself stored comma-chopped fragments of its
   own outcome sentences as separate outcomes, in both
   `desired_outcomes` and `outcome_statements[].outcome`, and every
   acceptance layer stored them verbatim.
2. A generated hook was complete in punctuation and broken in
   meaning: focus "You can spot your own rhythms instead of feeling
   surprised by your mood", shape Question, 4 seconds, returned "I'm
   trying to spot my rhythms, why so surprised?" — the focus's key
   noun (mood) dropped to fit the budget, leaving a question that
   asks about nothing. His order: "Make sure the hooks sound
   complete and not broken or mid-sentence, or spelling and grammar
   incorrect."
3. The Hook card carried two hook-writing actions — "Regenerate the
   hook" and, under the editor, "Suggest a clearer hook" — and Kasra
   asked why there were two. His first order removed the suggestion;
   he then tested both live and REVERSED himself: the generation
   gave him "I'm trying to spot my rhythms, I get surprised." while
   the suggestion gave him "I'm trying to notice my mood, and I keep
   missing it every day." — the complete line. His final design:
   remove the blue Regenerate button; ONE button does everything.
4. The hook generation's busy state counted down from the shared
   busy-eta (it borrowed the plan's 50s estimate). His order:
   "remove the countdown also for regenerate or generate the hook."

He also floated a regenerate option for the Focus list and withdrew
it in the same breath ("I'm just kidding") — not built, recorded
here so the absence is a decision, not an oversight.

## Decision

**Outcomes are stored whole (the research acceptance bar).** The
profile-research instruction now requires every outcome — flat and
statement alike — to be ONE complete phrase that stands alone,
punchy and plain, and forbids chopping a sentence into entries at
its commas. Behind the instruction, a deterministic bar
(`_outcome_stands_alone` in `backend/ai_service.py`) runs where the
research payload is validated: the flat list is filtered in
`analyze_app_profile` and statement outcomes in
`_normalize_outcome_statements`. An entry stands alone when it has
at least two words (a lone word names a topic, not an outcome),
does not open with a conjunction or a preposition (the words a
chopped continuation opens with), and does not end on a comma or a
conjunction (a head piece chopped mid-list). Case is deliberately
NOT judged: a lowercase verb phrase ("fall asleep without replaying
the day") stands alone and stays — the bar refuses continuations
and stray words, not case. Existing stored profiles keep their data
(no migration, no rewrite of stored rows) and founder hand-edits are
untouched; the bar governs new research runs, and a profile carrying
fragments heals on its next research run. The Focus pick itself is
unchanged: focus, tone and shape stay independent and combinable
exactly as ADR 0247 built them.

**A hook must be complete in meaning, not only in punctuation.**
Three layers, in the repo's existing style:

- The shared spoken-line craft block's FINISHED SENTENCES bullet
  now states the meaning rule for both lines on every surface that
  carries the block — a question carries its object, never a bare
  tail spliced on with a comma, and a line's key noun is never the
  word dropped to make a length fit. The hook rewrite path
  (`rewrite_hook_line`, which serves the clearer-hook suggestion on
  both pages) includes that block, so the suggestion flow answers
  to the same expectation by instruction; no new refusal was added
  there, and Create Video's rewrite contract is otherwise untouched.
- `generate_hook_line`'s own HOOK RULES repeat the rule for this
  surface: never drop the focus's key noun to squeeze under the
  budget — write a smaller thought that keeps it whole.
- A narrow deterministic charge joins the generation loop beside
  the budgets and the ADR 0231 gate adapters:
  `_dangling_question_issue` fires only for a question-picked line
  ending in "?" whose question segment (the words after the last
  comma or sentence break) opens with a question word, runs to at
  most three words, and carries no auxiliary verb — no subject, no
  object, nothing the question is about. A whole question carries
  its object and passes. The charge names the dangling tail in the
  loop's one bounded correction; a reply that keeps dangling is
  refused with the standing RuntimeError rather than shipped.

**One hook button on the Hook + CTA card.** The accent "Regenerate
the hook" button and its helper line are removed. In their place,
at the same spot under the picks, one control follows the card's
state: with no hook line it is "Generate the hook" (the accent
button, driving `generate_hook_line` exactly as before — same
handler, same flush of pending picks, same error alert); with a
line on file it is "Suggest a clearer hook" — the existing
`LineRewriteAction` flow verbatim (the suggestion offered beside
the founder's words, written only on "Use this line"), receiving
the live line and the draft edit as its accept. Both backend
endpoints stand; nothing was deleted. The page mounts
`HookLineEditor` with its new `suggestClearerHook={false}` prop so
the editor does not grow a second copy of the suggestion — the
prop defaults to true and Create Video's Review keeps its own
"Suggest a clearer hook" exactly as ADR 0205 arranged. The picks'
stale note now names the surviving remedy ("suggest a clearer hook
to write it with them").

**No countdown on this button.** The unified control's busy state
is plain — spinner sweep and "Writing the hook" — because the
generate mode no longer passes `etaSeconds` (it had borrowed
`BUSY_ETA_SECONDS.plan`). The removal is scoped to this one button
in `HookCta.jsx`; the plan (50s), angle (40s) and every other
countdown in the shared Button machinery are untouched, and the
Create Video surfaces that share the plan estimate keep theirs.

## Alternatives considered

- **Repair fragments at read time** (joining pieces back into
  sentences in `profile_outcome_lines`): rejected — the pieces are
  ambiguous (a fragment may belong to either neighbour), and a
  read-time guess would invent outcome text the research never
  stated. The bar at acceptance keeps stored data honest instead.
- **A capital-letter rule** for outcomes: rejected — legitimate
  lowercase verb-phrase outcomes exist in the corpus and fixtures;
  case is not what makes a fragment a fragment.
- **Keeping both buttons and labelling them better**: rejected by
  Kasra's live test — the generation path produced the thinner line
  twice, and two actions for one job was the original complaint.
- **A deterministic dangling check inside the shared spoken gate**
  (so the rewrite would refuse too): rejected — the gate serves the
  plan and Create Video surfaces whose contracts ADR 0231 settled;
  the charge is wired only where a question is the picked shape,
  and the rewrite path gets the doctrine by instruction instead.
