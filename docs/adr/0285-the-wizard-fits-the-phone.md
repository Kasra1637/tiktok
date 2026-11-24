# ADR 0285: The wizard fits the phone

Status: accepted

## Context

On Nov 23 2026 Kasra opened Create Video on his phone and sent a
screenshot: in mobile view the page read unoptimized — the four-step
rail crowded wider than the content under it, and the stacked canvas
(ADR 0099) made the page very lengthy. His order: optimize the rail
for mobile view, fix the layout on this page for mobile view only,
and take any other mobile optimization on the page that presents
itself. Desktop layout is settled (ADR 0141) and is not to move.

## Decision

Every change is a below-breakpoint variant or a max-width media
query, so the desktop wizard is byte-identical:

- The rail sheds what a phone cannot carry. Below `sm` each segment
  is badge and label only: its cumulative percentage steps aside
  (the live score at the rail's end still states progress) and its
  state/pick line steps aside (the section header's chip below says
  the same words). Both stay in the segment's aria-label at every
  width. Segment padding and the rail's gaps tighten below `sm`,
  and the rail row and nav gain `min-w-0`, so no part of the row can
  force the page wider than the screen.
- The stacked canvas tightens below `lg`: its section gap goes
  from 12px to 8px (`space-y-2 lg:space-y-3`), shortening the long
  stacked page without touching the paged desktop layout.
- The step card's gutter tightens on phones: `.surface-step` —
  a class only the wizard's sections carry — goes from 20px to
  16px below 768px in index.css, the compact scale's gutter. Every
  content column inside a step widens by 8px and each card shortens;
  from 768px up the settled 20px stands. The token change is
  recorded in design_guidelines.md in this same commit.

Navigation, states, labels, percentages and the sticky bar are
unchanged; ADR 0283's underline and pulse ride along untouched.
A smoke check pins the segments' phone classes, the canvas gap and
the stylesheet rule.

## Consequences

The phone rail is one line per segment and can no longer outgrow
the screen; the stacked page is shorter and its content wider.
Nothing at tablet or desktop widths changes, and no other page's
cards move — the gutter change rides a wizard-only class.
