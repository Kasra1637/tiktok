# 0215 — The hero headline is smaller: 42px on mobile, 50px on desktop

Status: accepted

## Context

On Nov 19 2026 Kasra looked at the landing hero live and asked
what size its headline was. The answer from the source: the h1
in `frontend/src/pages/Landing.jsx` wore Tailwind's steps —
`text-5xl` (48px) at base widths and `sm:text-6xl` (60px) from
the sm breakpoint up. His ruling came in two parts on the same
call: the desktop size drops from 60 to 50, and the mobile size
drops from 48 to 42.

Neither target is a Tailwind step — the scale jumps 48 → 60
with nothing at 42 or 50 — and the arbitrary-value spelling
(`text-[42px]`) is not available here: the render smoke's
display-scale check bans arbitrary text sizes in marketing
source outright, so the ladder cannot be left by writing the
pixels inline. The sizes therefore ride as named theme tokens,
the same way the brand colors and radii already do.

The headline itself is settled copy and treatment: Kasra's
dictated line (ADR 0157) in the one animated brand gradient.
Only its size was ever in question here.

## Decision

1. **The hero h1 wears `text-hero` and `sm:text-hero-wide`**,
   backed by two `fontSize` tokens in
   `frontend/tailwind.config.js` — `hero: 42px` and
   `hero-wide: 50px`. Mobile reads 42px, desktop 50px,
   exactly as dictated; the compiled CSS carries
   `.text-hero { font-size: 42px }` and the sm variant at
   50px.
2. **Nothing else about the headline moves.** Same words,
   same gradient treatment, same display font, weight
   (semibold), leading (1.05) and tracking (tight). No other
   headline or component is touched.
3. **The render smoke pins the sizes.** The standing hero
   headline check now asserts the h1 carries `text-hero`
   and `sm:text-hero-wide` and neither retired step class,
   so the sizes cannot silently revert to 48/60.

## Alternatives rejected

- **Spell the pixels as arbitrary values
  (`text-[42px]` / `sm:text-[50px]`).** The display-scale
  check bans arbitrary text sizes in marketing source; the
  exception belongs in one named place in the theme, not in
  a hole cut through the enforcement.
- **Use the nearest Tailwind steps instead (text-4xl /
  text-5xl).** 36/48 is not what was dictated; the numbers
  were named exactly, so they are carried exactly.
- **Scale the whole hero down with it.** Kasra named the
  headline's size only; the sub-headline, spacing and hero
  figure keep their settled proportions.

## Consequences

The hero opens calmer at both widths — the dictated line
takes less vertical room on a phone and less dominance on
desktop — while every other settled hero decision (ADR 0157
copy, ADR 0176–0178 story animation and placement) stands
untouched. The display ladder keeps one named exception,
visible in the theme and in this record. A future size
change is a new dictation and a new record, not a quiet
class swap: the smoke pin fails on the old classes, as it
did before this change landed.
