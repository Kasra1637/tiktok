# ADR 0380: The six feature-card lines fit a 130–135 band

## Status

Accepted, Nov 26 2026 — Kasra's order: shorten the
six feature-card descriptions on the landing to
130–135 characters each. His first prepared set was
set aside at his word ("Or no"); the lines below
are his reworked set, approved the same evening.
The change lands in `frontend/src/pages/Landing.jsx`
and supersedes ADR 0156's exact-160 length rule for
these six descriptions.

## Context

ADR 0156 pinned every card description at exactly
160 characters so no card ended with ragged empty
space. At 160 the lines read long beside the cards'
titles, and Kasra ordered them shorter — a band,
not a single length, so each line can end on its
own strongest words. The six titles he picked stand
unchanged.

## Decision

The six descriptions now read, with their lengths:

- Facts you approve (135): "Drop your site or store
  link in once. HookForge pulls the real facts from
  it, so every video stays true to your product and
  your brand."
- One clear outcome (133): "One buyer, one goal,
  one clip. Nothing generic, nothing people scroll
  past — each second is shaped to hold a real
  viewer's attention."
- Your voice, one script (133): "Your hook and
  script arrive in your voice, graded on craft
  before any render. Weak lines flagged — no grade
  ever blocks your renders." Kasra's reworked
  ending ("no score can block you") says the same
  thing in fewer words, but the claims check pins
  the disclosure's exact standing phrase — "no
  grade ever blocks your renders" — so the ending
  carries that phrase and the line's first sentence
  stands exactly as he wrote it.
- Never filmed (132): "Your photo and script become
  a finished presenter video in minutes. No camera,
  no studio, no reshoots — change a line, render
  again."
- Demo, finished (133): "Your screen recording
  lands in a clean phone or browser frame — smooth
  zoom, captions, and a strong closing CTA,
  exported as one MP4."
- Results that teach (131): "Post, then log the
  views, retention, saves, and shares. Three clips
  in, HookForge sees what holds people and steers
  your next ones."

The "Your voice, one script" line also drops the
old "before you spend a cent" — the landing carries
no pay wording anywhere, and the reworked line
keeps it that way.

## Checks

The standing check is renamed "Landing feature
cards are the six Kasra picked, descriptions in
the 130 to 135 band": the six titles are pinned as
before, and each description must now measure
inside 130–135 instead of exactly 160. The band is
tight enough that the cards still read as one set.

## Alternatives considered

One exact length for all six, as before: rejected
by the order itself — Kasra asked for the band so
each line ends where its words land, not where a
count forces it. Keeping 160 and trimming only the
weakest lines: rejected — the order was all six.
