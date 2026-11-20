# ADR 0147: The Review bar scopes Generate to the render half, and the arrow to the finished render

Status: partially superseded by 0218 (the Review bar's scoping — the wizard
bar is removed; the Review halves, their tabs and the panel's own states
stand in-section)

Refines ADR 0144.

Superseded in part by ADR 0169: the ready-state bar action on the
render half no longer runs the render — the bar keeps Generate's
face, but its click only scrolls to the render section, and the
panel's own button is the only one that submits. The scoping, the
flight presentation and the arrow rule recorded here stand.

## Context

Two sticky-bar defects Kasra named on Nov 14 2026, the second from his
own screenshot of the bar:

- ADR 0144 put the real "Generate the video" on the wizard bar in the
  ready state — on both halves of Review. But Review is two jobs on
  two tabs: "Read the plan" is where the founder reads, and "Render &
  result" is where the render lives. A paid-action invitation glowing
  on the reading half invites the one click the step exists for
  before the plan has been read, and it is not the render's home.
- The same screenshot showed the bar carrying "Generate the video"
  AND the round forward-arrow button side by side. The arrow is the
  way onward to Demo + CTA — a step whose editor opens on the
  project's newest finished render — so beside a Generate that has
  not been pressed yet it offered a way past the step's one job, to a
  finish line with nothing finished. And once a render did start, the
  bar went on offering the CTA it could no longer honor: the panel
  registered nothing while busy, so the bar fell back to the
  navigation shortcut and kept a live-looking action next to a render
  already running.

## Decision

The Review-step bar is a small state machine. The unblocking states
keep their precedence above everything here (ADR 0133: unsaved plan
edits → the save remedy; rebuild owed → "Rebuild strategy"; no
strategy → "Build the strategy"; no plan → the plan-flight mirror /
"Generate your plan" / "Try again"). Within the settled states:

- **In flight, the bar narrates the render and offers nothing.** Once
  a render has started — the panel's submit is busy, or a generation
  row stands submitted/generating — the panel registers its busy
  presentation with the page (the same "Generating video" words its
  own button carries, disabled and busy, no play icon, no invitation,
  no click) and the bar carries exactly that. Generate is gone, the
  shortcut is gone, and the forward arrow stands down: there is
  nothing to press and nowhere to go until the render lands.
- **Finished, the bar retires to the forward arrow alone.** When a
  finished render exists for the project (the page's completed-
  generation lookup — the same signal the finish step reads) and no
  render is in flight, the bar carries no action of its own. The
  round forward arrow renders — on Review, only in this state — as
  the way onward to Demo + CTA. The panel keeps its own Generate for
  a founder who wants another render; the bar's job is done.
- **Ready, the bar follows the half in view.** With no finished
  render and none in flight, ADR 0144 stands on the "Render & result"
  half: the bar carries the panel's registered Generate — same words,
  play icon and invitation — and its click runs the render. On the
  "Read the plan" half the bar is the navigation-only "Go to render"
  shortcut ADR 0144 demoted to a fallback, restored here as that
  half's way forward: plain styling (the clapperboard, never the play
  icon, never the invitation, so Generate's invitation stays unique
  to the real render action), and its click only switches the half in
  view. It never generates (ADR 0122: navigation generates nothing).
  The shortcut also remains the fallback on the render half for a
  state where the panel cannot register, exactly as ADR 0144 left it.
- **The forward arrow on Review renders only in the finished state.**
  Every earlier Review state — plan-half ready, render-half ready,
  in flight, and every unblocking state — shows no arrow. Other steps
  keep the standing rule (the arrow shows beside a non-blocking bar
  action or none); the finish step's own bar is untouched, and so is
  the in-page render panel, including its busy presentation.

## Consequences

- One promise per surface, per half: on the reading half the bar
  offers a way to the render; on the render half it offers the render
  itself; during the render it offers patience; after it, the way
  onward. Generate's invitation appears only where pressing it
  generates, and only before the render it names has run.
- The arrow can no longer walk a founder past an unrendered plan to
  a finishing step that has nothing to finish — it appears exactly
  when there is somewhere to go, which is what its prominence was
  always supposed to mean.
- Regression-pinned in the render smoke suite: the ready review on
  the plan half shows the shortcut (no play icon, no invitation, no
  arrow) and clicking it switches the half and submits nothing; on
  the render half the bar's Generate matches the panel's words and
  invitation, still with no arrow, and clicking it runs the render; a
  generating row puts the bar into the disabled "Generating video"
  presentation with neither Generate, shortcut nor arrow; a finished
  review leaves the bar to the enabled forward arrow alone.
