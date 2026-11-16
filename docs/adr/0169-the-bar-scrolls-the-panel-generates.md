# ADR 0169: The bar scrolls, the panel generates

Status: accepted

Supersedes ADR 0144's and ADR 0147's ready-state bar rule only: the
bar no longer runs the render. ADR 0147's scoping (Generate's face
only on the Render & result half, the plan half's navigation-only
shortcut, the flight presentation, the forward arrow reserved for
the finished render) and every unblocker state stand unchanged.

## Context

ADR 0144 put the real "Generate the video" on the wizard's sticky
bar in the ready state, and ADR 0147 scoped it to the Render &
result half: the bar borrowed the render panel's registered
Generate — same words, Play icon and invitation — and its click ran
the render in the panel, with the project's current model and
resolution.

Kasra reversed that on Nov 16 2026, stated twice on one call. The
render is the step's one paid action, and the bar's click fired it
from a distance: a founder could commit the render without ever
standing in front of the model and resolution choices it would run
with, because those choices live in the panel, not on the bar. His
rule, in his words: "the only button that generates the video
should be the one right on the resolution." The bar's job is to
take the founder to the render, not to be the render.

## Decision

In the ready state on the Render & result half, the bar keeps the
registered Generate's face — its words, Play icon, the
`.generate-invite` glow and its testid — but its click is
navigation only: it scrolls to the render section (the same
`scrollToSubmit()` destination the "Go to render" shortcut uses,
minus the tab switch, the render half already being in view). It
never calls the submit handler, directly or through the registered
action.

Everything else is untouched:

- The panel's registration does not change. GenerationPanel still
  registers the ready Generate — its own button's handler — and,
  during a render, the busy presentation marked `flight`. The page
  simply no longer wires the ready registration's click to the bar;
  the flight registration is still carried whole, so the bar
  narrates a render in flight exactly as before.
- The panel's own "Generate the video", beside the model and
  resolution pickers, is the only control that submits a render.
- The finished state still retires the bar to the forward arrow
  alone; the plan half still gets the navigation-only "Go to
  render"; the save-remedy, rebuild and build-strategy unblockers
  keep their precedence, and Generate's face still never appears
  while a rebuild is owed or no strategy exists.
- ADR 0122 is strengthened, not weakened: the bar's click on both
  halves of Review is now navigation, and generation still happens
  only from the panel's own button.

From the same call, a companion rename: the render section's title
"Render your Hook + Story" becomes "Generate your video" — the
panel's job named plainly, matching the button that does it. It
rides in its own copy commit, per the repo's copy convention; the
"Render and result" tab name does not change.

## Consequences

- One submit path for the one paid action, and it stands beside
  the choices it submits with. A founder who taps the glowing bar
  lands on those choices instead of past them.
- The bar remains a wayfinding device on both halves of Review:
  "Go to render" from the plan half, Generate's face as the scroll
  invitation from the render half, the busy presentation during a
  flight, the arrow once a render has finished.
- The smoke pin that asserted the bar runs the render flips: the
  bar's click now asserts no generation request fires, and the
  panel's own Generate, clicked in the same state, asserts the
  render runs. The flight, finished, plan-half and unblocker pins
  are unchanged and stay green.
