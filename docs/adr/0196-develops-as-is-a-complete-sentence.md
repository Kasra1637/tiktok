# ADR 0196: "Develops as" is a complete sentence

Status: accepted

Kasra's Nov 17 2026 Audience & template screenshot: a template
card's "Develops as" read "develops the interruption by
contrasting the slow typing habit with speaking through racing
thoughts at the orchard gate, and it educates the viewer..." —
lowercase, subject stripped, starting mid-sentence. A Nov 14
card read "keeps the person at the bus stop in the same held
position while...". The lines read as broken English because
they were assembled to be fragments.

## What the trace found

The generation prompt asks for full sentences — the model writes
"The video develops the interruption by..." — and the assembly
layer then broke them on purpose, in
`backend/angle_scene.py` (`_development_beat`, and the plan path
of `opening_development`):

- the first letter was lowercased (unless the sentence opened
  with "I");
- the terminal period was stripped (`.rstrip(".")`);
- leading subjects were regex-stripped: `^then\s+` and
  `^(?:the |this )?(?:middle|video|piece|rest)\s+`.

The design intent was that the card label "Develops as" would
carry the sentence and the value would read as its clause. In
practice the founder reads the value as a sentence in its own
right, so the strip produced exactly the screenshot's fragments.
The subject was not lost at generation time; it was deleted in
post-processing.

## Decision

`opening_development` now returns a complete sentence on both
paths, via `_as_sentence` in `backend/angle_scene.py`:

- The subject is kept. A subject that names the writing instead
  of the video ("The middle names the cost of guessing") is
  given the video as its subject ("The video names the cost of
  guessing") rather than being stripped — on the template path
  only; the plan path prints the founder's approved words
  unrewritten, as before (ADR 0108).
- The first letter is a capital; a lowercase model sentence is
  capitalized, never stripped.
- The terminal period is restored; "!" and "?" endings stand.
- The genuine cleanups are unchanged: the place/time conflict
  drop, the screen-clause strip, the handoff-echo strip, the
  phone-phrase strip, and the pronoun-stub drop (a middle that
  was nothing but the echo still yields no development line).

## Consequences

Regression pins live in `backend/test_development_sentence.py`,
built on the two screenshot shapes verbatim (orchard gate,
bus stop), the meta-subject rewrite, a "Then" opening, a
lowercase model sentence, the echo-only drop, and the plan
path's period. The clause-era pins in
`backend/test_template_relevance.py` were updated to the
sentence shapes they now produce.
