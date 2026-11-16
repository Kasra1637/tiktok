# 0168 — The hero types the link on page one, then steps through the video on page two

- **Status:** accepted
- **Date:** 2026-11-16
- **Anchors:** `frontend/src/pages/Landing.jsx` (`HeroStory`),
  `frontend/src/index.css` (the `hs-*` keyframes),
  `frontend/scripts/check-render-smoke.cjs` (the hero story pins).
  The step names are `STEPS` in `frontend/src/pages/CreateVideo.jsx`;
  the research label is the submit in `frontend/src/pages/BrandSetup.jsx`.
  Refines ADR 0165 and its addendum (the hero illustrates the
  process); ADR 0154 (no pause control) and ADR 0158 (hidden below
  1024px) carry over unchanged.

## Context

Kasra reviewed the shipped process hero (cb1ed13) on a voice call
and replaced its shape. Three objections, in his order:

1. **The link arrived as if pasted.** A chip dropped in above the
   phone and the field inside was simply full. Nobody pastes their
   way into the product in the story he wants told: a customer
   *types* their store link domain into the app. The entry had to
   read as typing.
2. **The profile card's rows were invented names.** "Store page",
   "Screenshots" and "Facts" are not names the app uses, and he
   called them ugly. The replacement offered on the call —
   "Website", "App Store", "Google Play" — was rejected too: the
   card itself was the wrong beat, not just its labels.
3. **"Generate the video" stood on the wrong page.** It sat under
   the profile on the same single page, so the animation skipped
   the journey a user actually takes to reach it: the app's own
   video creation steps.

## Decision

**The phone mockup now plays two pages on the same 12s CSS clock.**

**Page one is the link, typed.** The input field starts empty
behind a blinking caret, and the link types in character by
character — a stepped width track (`hs-typing`, `steps(17)`) clips
a span that always carries the full text in the DOM, so the pins
and screen readers read the whole link while the eye sees it
typed. The link is the general placeholder already in the figure,
"yourapp.com/store": a hypothetical example, not a real app name.
The drop-in chip above the phone is gone — page one is typing,
not pasting. Under the field, a "Research app for video" control
— the app's exact label for the research submit in BrandSetup —
rises and is visibly clicked (press + ripple): the click that
gets the visitor their profile info. There is no profile card
and no "Generate the video" anywhere on this page.

**Page two is the video journey.** After the research click the
phone turns to a new page carrying the app's video creation
steps under their exact `CreateVideo` names — "App Profile",
"Audience & template", "Review & submit", "Demo + CTA" — each
checking off in turn. "Generate the video" appears only on this
page — its only place in the whole animation — and is clicked
there (press + ripple). The finished video then plays exactly
as before: presenter illustration, the hook "A year building
this app." / "Nobody knew why it mattered.", play badge,
progress bar, and the end card "Your app. Your story." over
"Get the app".

**Every ADR 0165 contract carries over.** Pure CSS on one 12s
clock (the `hs-*` keyframes), no JS timer, no control of any
kind, the figure hidden below 1024px, the headline, sub-headline,
CTAs and the How it works section untouched. The base styles
are still the finished video frame — the two process pages rest
hidden — so reduced motion stands on the finished video, static.

## Alternatives rejected

- **Rename the profile rows to the research sources** ("Website",
  "App Store", "Google Play"): offered on the call as the app's
  exact source names, and refused — the fix Kasra chose removes
  the card, it does not relabel it.
- **Keep the drop-in chip and only animate the field's text:**
  the chip dropping in *is* the paste gesture he objected to;
  half the brief would have survived intact.
- **Show "Generate the video" on both pages** so the promise
  lands earlier: refused on the call — it shows only where the
  steps lead to it.

## Consequences

- The smoke suite pins the two-page flow (the typed field and
  its caret, the stepped typing track, the research click under
  its exact label, the four step names, Generate present exactly
  once and inside page two, the retired chip and profile card
  absent from the DOM, the page source and the stylesheet), not
  only the stages' presence.
- The loop's middle is denser: typing, a click, four steps and
  a second click now share the seconds the profile card used to
  hold, so the finished video's beat starts later on the same
  clock (76% instead of 67%). The 12s total does not change.
