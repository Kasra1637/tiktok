# ADR 0194: The centre word a "Why it fits" line cites is a content word

Status: accepted

Kasra's Nov 17 2026 Audience & template screenshot: the template
titled "Reducing Stress with AI" carried the WHY IT FITS line
"Puts 'with' at the centre of the piece — your main feature
arrives as the reason they stayed, not as a bullet." A rationale
that cites a function word as the heart of the piece is nonsense
on its face, and it teaches the founder to distrust every other
rationale on the card.

## What the trace found

The feature factor in `score_template_for_angle`
(`backend/template_recommendations.py`) tokenized the angle's
main feature by length alone — any word longer than three
letters — so "Voice-first journaling **with** AI transcription"
yielded the token `with`. It then matched those tokens against
the template's slot values **and its name**, and "Reducing
Stress **with** AI" contains `with` in its own title. Two
compounding defects:

- no stop-word filtering, so glue words were matchable evidence;
- the candidate tokens lived in a `set`, so which matching token
  got cited depended on hash iteration order — the same inputs
  could cite different words on different runs.

## Decision

- Feature tokens are the phrase's content words only: a stop-word
  list is excluded, tokens are ordered most-specific-first with
  phrase order breaking ties, so the citation is deterministic.
- When a content word matches, the rationale cites it as before.
- When no content word matches but the template names the whole
  feature phrase verbatim (a feature with no citable word of its
  own, e.g. one named "AI"), the factor still earns and the
  rationale runs centre-less: "Your main feature runs through
  the piece — it arrives as the reason they stayed, not as a
  bullet."
- A stop-word-only overlap earns nothing and cites nothing: the
  previous behaviour paid the factor for the word "with".

## Consequences

Regression pins live in `backend/test_template_fit.py`
(`TestCentreWord`): the screenshot shape exactly, a content-word
citation while the title still contains "with", determinism
across repeated scoring, and the centre-less fallback. The
factor's weight is unchanged here; the scale rebalance is
ADR 0195.
