# 0263 — The hero headline rises again: 48px on mobile, 60px on desktop

Status: accepted (supersedes ADR 0215's sizes; its token
mechanism, pin and "only the size moved" rule carry over)

## Context

ADR 0215 dropped the landing h1 from Tailwind's steps — 48px at
base widths, 60px from `sm` up — to 42px on mobile and 50px on
desktop, on Kasra's Nov 19 2026 dictation, to calm the hero.

Over the following days the page grew around that calmer
headline. The sections below it carry `text-3xl`/`text-4xl`
headings (30/36px; the marketing display scale, pinned by the
display-scale smoke check), and the hero's second column now
holds the phone story figure at 360–400px. Against both, a 42px
mobile h1 barely outranks a section heading above a phone
figure — the hero reads first among equals rather than as the
page's opening statement.

## Decision

1. **The hero h1's tokens rise to 48px / 60px.** `hero: '48px'`
   and `hero-wide: '60px'` in `frontend/tailwind.config.js`,
   worn as `text-hero` / `sm:text-hero-wide`. This is Tailwind's
   own 3xl→6xl display step restored, carried through the same
   named tokens ADR 0215 introduced — arbitrary text sizes stay
   banned in marketing source, so the theme keeps the exception
   in one named place.

2. **Nothing else moves.** Same dictated words (ADRs 0157/0261),
   the one animated brand gradient, the display font, semibold
   weight, `leading-[1.05]` and tight tracking. The sub-headline,
   the hero figure, spacing and every other section keep their
   settled proportions.

3. **The pins move with it.** The standing hero headline check
   still asserts `text-hero` + `sm:text-hero-wide` and now
   rejects `text-5xl`/`sm:text-6xl` as the *unused* spelling —
   the tokens remain the only legal route to these sizes.
   `design_guidelines.md`'s named exception restates 48/60.

## Alternatives rejected

- **Leaving 42/50 and enlarging something else instead.** The
  phone figure and the trust line are already at their settled
  proportions; the gap is the headline's rank, not the figure's
  size.
- **Going past 60px on desktop.** The headline column is roughly
  half of the 1152px grid (~530px). At 60px the line wraps in
  four confident lines; beyond ~64px it climbs to five or six
  and the last line strands.
- **Spelling the pixels inline.** The display-scale check bans
  arbitrary text sizes in marketing source; the tokens exist for
  exactly this.

## Consequences

The hero wins the eye again at both widths while keeping ADR
0215's mechanism: one named theme exception, one smoke pin, and
a size change still requires a record rather than a quiet class
swap. Copy, gradient, story animation and placement
(ADRs 0157, 0176–0178) stand untouched.
