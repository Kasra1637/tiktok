# ADR 0177: The hero phone stands below the pitch on mobile

Status: accepted

Supersedes ADR 0158's hide rule (that record's status flips
with this commit; its history stands). Kasra's ruling, Nov 16
2026: asked whether the phone should display on mobile or stay
hidden, he took the recommendation — show it, stacked below
the pitch — and said "Do it."

## Context

ADR 0158 hid the hero figure below the 1024px breakpoint
because of what the figure then was: a decorative cycling
picture section — a portrait frame of step illustrations that
cost a full stacked screen of mostly empty dark space and
repeated the How it works strip below it. Hiding it on phones
was right for that figure.

The figure is not that anymore. Across ADRs 0165, 0168, 0175
and 0176 it became the product story itself, told in the
phone: the store link typing in, the Research click, the four
creation steps checking off, the Generate click, and the
finished video born in the page's center and closing on its
own end beat. And HookForge's first users are mobile — the
Nov 14 2026 decision ships on Google Play first — so the hide
rule now withholds the story from the main audience to protect
them from a decoration that no longer exists.

The old rule's spirit was never "hide the phone." It was
"never let the phone push the pitch off the first screen":
the headline, sub-headline, CTAs and checkmark lines land
complete before anything else competes with them. That spirit
can be honored by order instead of absence.

## Decision

- **`.hero-shot` states plain visibility at every width.**
  In `frontend/src/index.css` the class is now a single
  `display: block` rule; ADR 0158's base `display: none` and
  its 1024px media-query restore are deleted. There is no
  breakpoint flip anymore.
- **Placement rides the markup that already exists.** Below
  lg the hero container is a single column, the figure
  (`data-testid="landing-hero-shot"` in
  `frontend/src/pages/Landing.jsx`) already follows the pitch
  block in DOM order, and its own utilities — `mx-auto mt-12
  w-full max-w-[360px]` — center it under the pitch at its
  stacked measure, inside the hero container's existing
  side padding. At lg the grid (`lg:grid-cols-[1.02fr_1fr]`)
  and the figure's `lg:` utilities (`lg:mx-0 lg:mt-0
  lg:max-w-[400px]`) stand it beside the pitch. Desktop
  layout is unchanged, class for class.
- **One figure, one animation, every width.** The figure is
  never duplicated in the DOM and nothing renders it
  conditionally; no JS is involved. The 13s hs-* clock runs
  identically on mobile — page one's typing, page two with
  the video in its center slot, the in-video closing beat —
  and reduced motion rests on the same assembled final page
  as on desktop.

## Alternatives rejected

- **Keep ADR 0158's hide.** Protects the first screen by
  withholding the story from the audience the product is
  being built for first; the cost it avoided (an empty
  decorative frame) is not a cost this figure carries.
- **Show the phone above the pitch on mobile.** The story
  would land before the promise it illustrates, and the
  pitch would leave the first screen — exactly what the
  old rule's spirit forbids.
- **A separate, smaller mobile remake of the animation.**
  A second loop to keep in sync forever, when the phone's
  own width logic already caps it to the column at its
  stacked measure.

## Consequences

On phones the hero reads in one column: headline,
sub-headline, CTAs, checkmark lines — the pitch complete —
then the phone below, playing the same loop a desktop
visitor sees. At 1024px and up nothing changes. The smoke
pin that asserted ADR 0158's hide flips to the new rule: it
asserts the figure carries `.hero-shot`, the stylesheet
shows it by default with no hide and no breakpoint flip,
the figure follows the complete pitch block in DOM order,
its mobile sizing classes stand, and the desktop grid and
placement classes are unchanged. ADR 0158's record stays,
status superseded by this one; the AGENTS.md landing bullet
and this index follow in the same commit.
