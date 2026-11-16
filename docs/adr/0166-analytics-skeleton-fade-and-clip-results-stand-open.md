# ADR 0166: The Analytics skeleton fades into its content, and Clip results stands open

Status: accepted

Refines ADR 0165 (the skeleton resolve) and extends ADR 0151
(History's sections stand solid, never collapsible) to the
Analytics page's last whole-card collapse.

## Context

Two orders from Kasra on Nov 15 2026, reviewing the live
Analytics page from his screenshots.

First, the loading state. ADR 0165 unified the app's entrances
into the one rise-and-settle and let the skeleton resolve ride
it: resolved content mounts under `page-content-enter`. But the
swap itself still hard-cut — the skeleton unmounted in the same
frame the content mounted, so the placeholder vanished mid-shimmer
and only the content's own rise softened the landing. Kasra
screenshotted the placeholder card and asked whether it was
supposed to be removed. The agreed fix, in his review: the
skeleton structure stays while loading (per ADR 0165), but its
resolve must fade — the placeholder fades out as the real
content rises in, instead of cutting.

Second, the Clip results card carried a Collapse/Expand toggle
in its header: one button hid the card's whole body — the
why-details, the next-take band, the table — behind its header.
It was the last whole-card collapse in the app, against the rule
Kasra set for History's Post copy and Plan context sections
(ADR 0151: solid, always-expanded sections, no chevron, no
collapse). He ordered it removed. The "Show all N / Show less"
control inside the card is a different thing — it only widens
the ledger inside ADR 0160's bounded scroll — and he had already
confirmed it works; it stays.

## Decision

**The Analytics skeleton fades out as the content rises in.**
The skeleton and the content branch render inside one grid
stack (`.skeleton-stack`, `frontend/src/index.css:1151`): both
layers occupy the same grid cell, so while both are mounted the
cell is as tall as the taller layer and the handoff cannot shift
the layout. When the page's loading state ends, the page keeps
the skeleton mounted for one fade in a leaving state
(`frontend/src/pages/Analytics.jsx:90`): it gains
`.skeleton-leaving`, which runs the `skeleton-fade` keyframe —
opacity 1 to 0 over 250ms on the signature ease
`cubic-bezier(0.16, 1, 0.3, 1)` — while the content mounts in the
same cell under its existing `page-content-enter` rise. The
leaving state lifts after `SKELETON_FADE_MS` (250,
`Analytics.jsx:71`), the one number the JS timeout and the CSS
animation share. While leaving, the skeleton is `aria-hidden`
and `pointer-events: none` — it is a picture of the content's
arrival, not a second surface. The fade is gated on
`prefers-reduced-motion: no-preference` like every entrance,
and the page never enters the leaving state under reduced
motion at all (`useReducedMotionPreference`, the JS belt, as on
PageTransition): there the swap stays instant. The skeleton's
structure and its while-loading shimmer are untouched.

**Clip results stands open.** The header's Collapse/Expand
button, the `open` state, the panel-id wiring and the
conditional around the body are removed
(`Analytics.jsx:385`); the body — counts, summary line,
why-details, next-take band, table, the Show all / Show less
widening, and the ranked-by footnote — renders always, from the
first paint. The card's only remaining disclosure is the
show-all widening Kasra approved. `ChevronDown` stays imported:
the why-details summary still wears it.

## Consequences

- The Analytics resolve is a crossfade with no layout shift and
  no white flash; under reduced motion it is the instant swap it
  always was.
- The fade machinery is Analytics-only for now. Sibling pages
  with the same swap shape (History's list, BrandSetup's manual
  card, Asset Library's list) still resolve by the content's
  rise alone (ADR 0165); the stack classes are shared CSS, so a
  sibling can adopt the same handoff without new machinery when
  the founder asks.
- No card or section on Analytics or History hides its body
  behind a header toggle anymore. The smoke suite pins both
  halves: the toggle's absence with the body rendered on first
  paint, and the fade's keyframe, gate and belt in source.

## Alternatives considered

- **Fade only the content in** (the ADR 0165 resolve as shipped):
  the founder saw the cut and named it; the placeholder itself
  has to move, not just the arrival.
- **An absolutely-positioned skeleton overlay** over the content:
  the same picture, but the grid cell states the overlap in flow
  and cannot drift from the content's own box.
- **A minimum skeleton display time** so the fade always has
  something to play against: rejected — ADR 0165's rule stands;
  the fade runs only when real data lands, never as a timer kept
  for its own sake.
