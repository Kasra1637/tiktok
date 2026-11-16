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

## Addendum (Nov 15 2026): the stages carry real content — and the story is the process

Kasra reviewed the shipped hero from a screenshot and rejected
its content while accepting its motion: the phone animated
correctly, but its stages were abstract placeholder bars — the
hook was two empty line spans, the demo a head bar and two rows,
the end card a line and an empty pill — so nothing in the frame
read, in motion or in the finished frame a still (or reduced
motion) stands on. His words: there should be "some example of a
video preview or something. Or like a image or something of a
image of a person or some illustration. That shows what
happens."

A first fix gave the finished-video stages real words and an
illustrated presenter. Kasra then replaced that direction with
the final brief, and it supersedes the intermediate word sets
entirely: the phone mockup must illustrate the process,
stylized — not the exact app UI, and not just a finished
video's content. In a few seconds, in four acts on the same
12s clock and under the same contracts (pure CSS, no JS timer,
no controls, hidden below 1024px):

1. The store-domain input: the link chip that already exists
   ("yourapp.com/store") drops in and lands in an input field
   at the top of the phone screen, so a visitor sees they
   paste their store link.
2. Their unique app profile sets up: the app icon, the name
   "yourapp", and three short profile rows — "Store page",
   "Screenshots", "Facts" — each checked off in turn.
3. One click: a "Generate the video" control appears and is
   visibly clicked (a press and a tap ripple).
4. The video: the finished video frame plays in the phone —
   the presenter illustration (an inline SVG in the STEP_ART
   line family: head, shoulders, holding a phone), the hook
   in real words, the play badge, and the progress bar
   filling — closing on a brief end-card beat: "Your app.
   Your story." over a "Get the app" pill.

The hook inside the finished video is "A year building this
app." / "Nobody knew why it mattered." — the app-maker
framing. A journaling-flavored alternative ("After a long
day, the words just aren't mine") was built as a competing
pin during the fix and is rejected on the record: Kasra
stated this app is not for journaling, and the alternative
stays out of the page, the pins and this record's decision.

The base state changes with the story: acts 1–3 are process
UI and rest hidden, and the finished VIDEO frame — presenter,
hook words, play badge, progress, end card, all assembled —
is the base state, so reduced motion and any still screenshot
read as a finished video. The in-phone words were checked
against the landing's pinned and banned copy before landing
— they promise nothing — and the smoke suite pins the flow
version's content (the field's link text, the profile's icon,
name and checked rows, the labelled generate control with its
ripple, the video's presenter, hook words and end card, and
the retired demo stage absent from the DOM, the page source
and the stylesheet), not only the stages' presence.
