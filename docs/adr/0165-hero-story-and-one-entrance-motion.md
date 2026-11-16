# ADR 0165: The hero tells the story in one motion, and every entrance is the one rise-and-settle

Status: accepted

Follows ADR 0154 (the hero loop has no pause control) and ADR 0158
(the hero figure is hidden below the desktop breakpoint); both
outcomes carry over — this record changes what plays in the figure
and unifies entrance motion app-wide.

## Context

Two orders from Kasra on Nov 15 2026, in one call.

First, the hero. The landing hero's figure carried HeroFlow: the
five How it works step illustrations cycling in the portrait frame,
four seconds a step, with badge + title captions and a dots row.
He asked for the animation that shows the product instead — "link
in, video out": a store link drops into a phone and the finished
video builds itself inside it. The five steps were the pipeline
described; he wanted the promise shown.

Second, motion everywhere else. The app's entrances were a
patchwork of four timings doing one job: the primary content reveal
at 150ms (`page-content-enter`, 4px), the route entrance at 120ms
(`route-entry`, 4px), the card entrance at 150ms (`card-enter`,
8px), the wizard canvas disclosure at 150ms the other way
(`wizard-section-enter`, −4px), and the landing reveal at 0.5s
(`fade-up`, 12px). He approved one unified entrance — "rise and
settle" — for page load, section load, in-view reveals and cards,
and ruled that the skeleton's replacement should arrive with it
too: the skeleton structure and its while-loading shimmer stay,
only the resolve changes.

## Decision

**The hero figure carries the story animation.** A store-link chip
drops in above a phone frame as if pasted; inside the phone's
screen a finished video assembles in stages on one 12s CSS clock —
the hook line types on (two lines, staggered), the demo block fills
in, the end card slides up, the play badge lands and the story
progress bar fills — then the finished frame holds and the loop
restarts. It is pure CSS (the `hs-*` keyframes in index.css): no JS
timer, no video bytes, no new image assets, and no control of any
kind — ADR 0154's no-pause-control outcome is preserved by there
being nothing to control. The base styles are the finished
assembled frame and every stage animation is gated on
`prefers-reduced-motion: no-preference`, so reduced motion stands
on the finished video, static. HeroFlow, its dots, its captions and
its CSS are retired. ADR 0158's placement rule carries over
unchanged: the figure (`.hero-shot`) stays hidden below 1024px and
renders on desktop. The headline, sub-headline, CTAs and checkmark
lines are untouched, and the How it works section below — its own
five STEP_ART illustrations — does not change.

**Every entrance is the one rise-and-settle.** One keyframe,
`rise-settle`: from opacity 0 and `translate3d(0, 7px, 0)` to rest,
300ms, `cubic-bezier(0.16, 1, 0.3, 1)` — the app's signature ease.
Every entrance class keeps its name and now resolves to it:
`page-content-enter`, `route-entry`, `card-enter`,
`wizard-section-enter` (its direction joins the shared rise), and
`animate-fade-up`. The five legacy keyframes are deleted. The
skeleton resolve rides the same motion without new machinery:
resolved content already mounts under `page-content-enter` when a
page's loading state ends (Analytics, History, BrandSetup's manual
card, Asset Library's list), so it now arrives with the
rise-and-settle instead of its own 150ms. List staggers stay as
they are — the same keyframe with a capped inline delay (≤70ms
steps, capped at 8 items in the studio lists). Deliberately NOT
entrances, and untouched: the generate-glow invite pulse, the
headline gradient loop, the busy and shimmer sweeps, the marquee,
the aurora floats, the tour fade — ambient and attention loops,
not arrivals. Reduced motion stills the unified treatment exactly
as it stilled the patchwork: the gated classes never animate
without the no-preference match, `animate-fade-up` stays in the
reduced-motion block, and PageTransition keeps its JS belt.

## Consequences

- One motion vocabulary to reason about: a reader who finds any
  entrance class finds the same 300ms rise; the smoke suite pins
  the contract (the unified keyframe, every class resolving to it,
  the legacy keyframes absent, the skeleton resolve riding
  `page-content-enter`).
- Route changes now take the same 300ms as everything else instead
  of a brisker 120ms — the cost of one motion, accepted by the
  decision; the ease curve front-loads the movement, and reduced
  motion still shows the page instantly.
- The hero no longer teaches the five steps; the How it works
  strip directly below carries them, as it always did in full.
