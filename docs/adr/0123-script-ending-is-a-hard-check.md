# 0123 — The script's ending is a hard check, not only a prompt rule

- **Status:** accepted
- **Date:** 2026-11-12
- **Anchors:** `backend/ai_spoken.py` (`_sentence_is_question`,
  `_generated_spoken_issues`), `backend/ai_service.py`
  (`_spoken_line_rules_block`, `generate_creative_plan`),
  `backend/test_hook_voice.py`. The retry machinery is ADR 0115/0116's;
  the hook's own question check in the same list is the precedent.

## Context

Kasra reviewed a generated Hook + Story whose script ended "What sets it
off?" — a question in the last line, and one that had drifted off the
story (the piece was about a mood label, not a trigger). The shared
spoken block already said "the script never asks one", and the plan's
editorial loop already repaired or refused other observable defects; the
ending was simply not one of the checked defects, so a prompt-only rule
shipped broken. The same review found two wording drifts the block
stated too loosely: a word repeated across the hook and the script
("still felt wrong" / "not wrong" — the existing ban read as
within-a-line) and the app's own feature noun spoken aloud ("now
reflections sound like me").

## Decision

- **The ending is a hard issue.** `_generated_spoken_issues` now flags a
  script whose LAST sentence is in question form. Detection is
  deterministic and narrow: the terminal "?", or subject–auxiliary
  inversion — an auxiliary first ("Can I say it out loud") or a wh-word
  with the auxiliary in the second slot ("What does it mean"). A wh-word
  with no auxiliary there is NOT flagged: "What sets it off is still a
  mystery" is the statement form that names the unknown, which is
  exactly the ending the craft asks for. The flag rides the existing
  bounded editorial loop — three attempts, the correction names the
  failure — and a draft that keeps ending on a question refuses honestly
  rather than shipping. The craft retry revalidates through the same
  function, so a correction cannot reintroduce the ending. The guard is
  scoped to the ending: a question mid-script stays the prompt's
  business.
- **The block says the three rules plainly.** The last line stays on the
  hook's own subject and names what is still unknown in the story's own
  terms, never switching to a new topic in the final line. The hook and
  the script are one text for repeated words — a content word spent in
  one is not spent again in the other — with the payoff echo (the hook's
  single key image or feeling word, brought back once on purpose) as the
  only deliberate repeat. And a spoken line never uses the app's own
  feature names or product nouns: the thing is named in everyday words
  ("what I wrote", "my notes", "the words on the screen").
- **The strategy prompt ceiling moves with the block.** Measured
  34,833 → 35,633 (+800, the shared block's exact growth 3,926 → 4,726);
  the ceiling in `test_ai_json_calls.py` moves 35,250 → 36,250 by that
  file's established measured pattern.

## Alternatives rejected

- **Prompt-only strengthening.** That is what shipped the defect — the
  rule was already in the prompt, worded almost exactly this way.
- **Flag any question anywhere in the script.** Wider than the failure
  and wider than the handoff the ending performs; the middle stays
  governed by the prompt and the advisory craft score, as continuity
  already is.
- **Fuzzy interrogative matching.** It would refuse statement forms that
  name the unknown — the endings the discovery rule exists to produce.
- **A craft-score deduction instead of a refusal.** The score is
  advisory by design (ADR 0114); an observable form defect belongs with
  the other observable defects the loop already repairs or refuses.

## Consequences

- A plan whose model keeps ending the script on a question now fails
  after three attempts with the existing honest refusal instead of
  reaching Review broken. Clean drafts cost no extra call, and the retry
  budget is unchanged.
- The guard runs at generation only; founder edits are not gated by it.
  The advisory craft report's trust dimension reads the same issue list,
  so a question ending also surfaces there as evidence, never as a gate.
