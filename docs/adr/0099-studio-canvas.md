# 0099 — The studio canvas: every step on one page, the active one expanded

- **Status:** accepted
- **Date:** 2026-11-06
- **Anchors:** `frontend/src/pages/CreateVideo.jsx` (navigable
  `studio-progress-rail` with the `studio-progress-segment-*` buttons and the
  `studio-progress-pct` readout, one
  `wizard-section-*` section per step, next-action `wizard-footer-hint` in the
  `wizard-arrows` bar), `frontend/src/index.css` (`wizard-section-enter`);
  smoke checks "the canvas stacks all three sections and expands the active
  one", "the progress bar is the nav, stated in thirds", "the progress rail
  rides the canvas with a live percentage",
  "the action bar names the next action beside its arrows", "the ready review
  names no blocker and offers the render" and "the angle hint follows the
  substep the founder is on"
- **Shapes:** extends 0095 (arrows, arrow-only bodies, sticky placement and
  the task line stay) and keeps 0098 whole (disclosure queues no request);
  supersedes only 0095's hint-free bar and its single-card focus view

## Context

The wizard was three screens shown one at a time: a card swapped in with a
slide, the pills as the only map of where the founder was, and the rest of
the workflow invisible until they walked to it. The step machine, the gates
and the request rules all work well; what read as dated was the framing — a
single card that hid everything else, so the page answered "what is here?"
but never "where am I in the whole thing?". Modern studio canvases keep the
workflow on one page and disclose it: the shape is visible, the active part
is open, finished parts fold down to a line.

## Decision

- **One canvas, three sections.** All three steps render as `.surface-step`
  section cards in order. The step in view is expanded; every other step is
  collapsed to a header row — number, glyph, label, and a state chip that
  carries its pick when it is done.
- **A header is a control, not a label.** Opening a collapsed section calls
  the same `setStep` its segment calls. One state machine, one gate set, one
  set of arrows: progressive disclosure adds no second navigation model and
  queues no request of any kind (0098 stays whole — sections render from
  state the page already holds).
- **The progress bar is the nav.** The pills were a second nav carrying the
  same labels, so they were removed and the bar owns step navigation: three
  segments, each stating its step's cumulative third (33 / 67 / 100%) and the
  state in words or the pick once done, with the live score at the end. All
  of it derives from the same step states, so the readouts can never
  disagree. The bar scrolls with the canvas — a pinned bar over the plan form
  read as a floating second layer — and it is transparent chrome, never a
  panel.
- **The action bar carries one state-derived line.** 0095 dropped the footer
  hint because a standing sentence could not name what was missing. The bar
  gets a line back only as derived copy that names the live gate — including
  "templates wait for your click" on the angle step — and it never restates
  the task line under the title. It follows the substep the founder is on,
  and on a blocked review it names only the blocker that is actually true
  (a photo already attached is never asked for again). The arrow-only pair and
  the sticky placement are unchanged; the last-step exit was removed later, so
  the arrow Back covers every step.
- **A ready review gets its forward action back.** The last step has no
  Continue arrow, so when the review is done (plan, photo, no edits) the bar
  carries a primary "Go to render" button that opens the Render & result
  half and scrolls to it. Navigation only: the render itself stays
  GenerationPanel's, the single render path unchanged.
- **Walking the canvas lands where it went.** A step change scrolls the
  opened section into view (`scroll-mt-24` keeps it clear of the shell's top
  strip), after the paint; mount never scrolls. An unfinished step's Continue
  wears the same dashed "not done" cue the pills use instead of locking —
  moving stays free.
- **Disclosure motion is brief and optional.** An opened section body rises
  `150ms` (`wizard-section-enter`, 4px) only under
  `prefers-reduced-motion: no-preference`; reduced motion is instant. The
  retired `wizard-slide-*` step transition leaves `index.css`.

## Alternatives rejected

- **Everything expanded, no collapse.** Three bodies mounted at once turn the
  page into a wall and put every step's effects on screen together; the
  collapse is what makes the canvas scannable.
- **A multi-open accordion.** `step` is the single source of truth for the
  gates, the arrows and the plan effects; two open bodies would give the page
  two "current" screens.
- **Scroll-jacking or next-only buttons.** The pills still free-jump and the
  arrows still walk one step; nothing about movement changes.

## Consequences

- The workflow's shape is visible before any walking: a founder reads where
  they are and what is left without leaving the current section.
- The smoke suite pins the canvas (three sections, exactly one active, header
  click moves the step), the bar as the nav (three segments stating their
  thirds, clicking one moves the step, no pills back), the live percentage,
  and the action bar's state-derived line beside arrow-only controls.
- Checks that scoped text to "the active step card" now select
  `.surface[data-active="true"]`, so collapsed headers cannot leak another
  step's content into the assertion.
- No backend, request or gate change: same steps, same order, same rules.
