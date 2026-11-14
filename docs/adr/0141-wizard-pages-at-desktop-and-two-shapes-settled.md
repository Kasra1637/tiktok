# ADR 0141: The wizard stands one step at a time at desktop widths; Review's column and Analytics' calm are settled

Status: accepted

## Context

The desktop UI/UX audit of Nov 14 2026 (ADR 0140) reserved three questions
it could not answer mechanically, because each is a feel, not a defect:

- **Review's desktop shape.** Should Read-the-plan become two columns at
  wide screens — script editor left, Craft check and verdict evidence as
  a right rail — or is the single calm column the product's chosen feel?
- **The wizard's stacked canvas.** ADR 0099 stands every step on one page
  as a section, the active one expanded, the rest collapsed to headers.
  On desktop that is honest but long. Making the steps true pages at
  desktop widths touches deep-linking, draft resume and the tour anchors,
  so it is a product decision, not a polish item.
- **Analytics density.** Finding 6 of the audit gridded Analytics'
  summary/verdict band two-across at lg (shipped in ADR 0140). Whether
  the page should go further — a dense dashboard — or stay a calm ledger
  was left open.

On Nov 14 2026 Kasra asked for Flash's recommendation on all three and
approved it in full: Review stays one column, the wizard becomes true
pages at desktop widths, Analytics stays calm. This record is the
decision, so no future audit re-opens the two that changed nothing.

## Decision

- **Review stays one column, at every width.** No build. The single calm
  column — read the plan top to bottom, then render — is the product's
  chosen feel, not an unfinished two-column layout. The right-rail
  alternative is rejected: the Craft check is read as part of the plan's
  story, not as a sidebar competing with it.
- **The wizard is paged at desktop widths, stacked below them.** At
  Tailwind's lg breakpoint (1024px) and up, only the step in view renders
  its section: it stands as its own page, and navigation — a progress
  segment, the sticky bar's arrows, the bar action — swaps the page
  instead of expanding a section in one long scroll. Below lg, ADR
  0099's canvas stands exactly as it was: every step a section, the
  active one expanded, the rest collapsed to a header and a state chip.
  0099 is therefore superseded at desktop widths only.
  The split is presentation, never state. One step machine, one `?step=`
  mirror, one gate set serve both shapes: `step` stays the source of
  truth, so a deep link or a resumed draft lands on the correct step and
  the shape follows it. The width is read by `useDesktopWidth`
  (`frontend/src/lib/desktopWidth.jsx`, `(min-width: 1024px)`, guarded
  like `useReducedMotionPreference` — no matchMedia reads as
  not-desktop, so the canvas is the fallback), and the canvas map in
  `frontend/src/pages/CreateVideo.jsx` renders no section for a step
  that is not in view while paged; the container carries
  `data-layout="pages" | "canvas"` so the shape in effect is observable.
  Every hard contract holds, and each is pinned:
  - Click-to-generate (ADR 0122) does not regress: paging queues no
    request of any kind (0098's disclosure rule extends to pages), and
    the kept exceptions — profile approval generating its first angle
    set, automatic completion pipelines — are untouched. A smoke check
    walks a full circuit of the pages and asserts no generation call
    fires.
  - The sticky bar still carries the one unblocking action per
    step/state (ADR 0133), the Review button rule and the render
    panel's one-primary-action rule (ADR 0134) are untouched, and the
    Review step's ListenButton (ADR 0140) stays in the Review page's
    header.
  - Tour anchors resolve: the create tour targets the progress-rail
    segments (rendered at every width) and optional in-body targets
    that were always state-dependent; the tour-target audit still
    prints ALL TOUR TARGETS EXIST, and no tour definition changed.
- **Analytics stays calm.** No build. The Finding 6 shape — summary and
  verdict band two-across at lg, the clip ledger and weekly chart at
  full width — is the final shape. The page is a ledger the founder
  reads, not a dashboard to scan, and the remaining single column is
  intent, not an oversight.

## Consequences

- ADR 0099 is partially superseded: its canvas governs below 1024px,
  this record governs at and above it. Its status line and index row
  say so; the file otherwise stands.
- The paged shape has regression pins: a render-smoke check stands the
  wizard at desktop width and walks it page to page (only the active
  section in the DOM, its body rendered, the Back arrow returning a
  page), a second check asserts the circuit spends no generation call,
  and jest pins the hook itself (missing matchMedia, the lg query,
  a live breakpoint crossing). The long-standing stacked-canvas smoke
  check keeps pinning the below-lg shape unchanged, under the harness's
  default matchMedia.
- `design_guidelines.md` states all three settled shapes in its Layout
  section, so the next audit scores against the decisions instead of
  re-asking them.
