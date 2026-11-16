# ADR 0172: The hero's buttons breathe, the link text goes, the end card lands

Status: accepted

Refines ADR 0168 (the two-page hero). Kasra's orders, voice call,
Nov 16 2026: display both buttons about half a second longer,
remove the store-link text, and completely enhance the last step.

## Decision

- **One 13s clock.** The loop lengthens from 12s to 13s and every
  hs-* track shares the new duration, so no stage is squeezed.
  Both buttons gain about half a second of display before their
  clicks: "Research app for video" appears at 2.6s — half a second
  sooner than the typed cut's 3.1s, Kasra's own clarification of
  "half a second longer" — and is clicked at 3.5s (0.9s of display,
  against 0.36s); "Generate the video" displays 0.78s before its
  click, against 0.36s. The loop stays seamless and pure CSS.
- **The link text is removed entirely.** The typed
  "yourapp.com/store" field — field, typed-text span, caret, and
  the hs-field / hs-typing / hs-caret tracks — is deleted from the
  DOM, Landing.jsx and index.css. Page one opens cleanly on the
  Research beat, and the HeroStory aria-label no longer claims a
  link is typed. The headline's own words are untouched.
- **The last step is enhanced into a real closing moment.** The
  finished video now plays out in beats: the presenter rises, the
  two hook lines reveal in turn, the progress bar fills across the
  video's whole stand (not the old late rush), the play badge pops
  at center — then yields, fading as the end card resolves. The
  end card is rebuilt as a centered closing card: a gradient app
  icon tile, "Your app. Your story." at display size, and the
  "Get the app" CTA as a full pill, rising and settling with a
  soft shadow as the loop's final image. The presenter is raised
  so the taller card never covers it.

## Consequences

The contracts around the change stand: .hero-shot stays hidden
below 1024px (ADR 0158), reduced motion rests on the finished —
now enhanced — video frame (the end card's base styles are its
assembled state), there is no JS timer, and the headline,
sub-headline, CTAs, checkmark lines and How-it-works strip are
untouched. Pins updated, not deleted: the process check now
asserts the field's absence everywhere and the end card's icon;
the one-clock check asserts every stage on 13s and none on 12s.
