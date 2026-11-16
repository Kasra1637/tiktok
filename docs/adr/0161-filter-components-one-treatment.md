# ADR 0161: Every filter control wears one treatment

Status: accepted

Presentation only: no filter's options, values, defaults, or results
change anywhere in the app. Every `data-testid`, aria attribute, and
label is untouched.

## Context

Kasra, on Nov 15 2026, screenshotted the History filter bar and
ordered a polish of every filter bar and filter component in the
app: more modern and polished, better usability, easier to
understand, more elegant — true to the app's design system and
philosophy — with the same updates carried through the hover, the
toggled/active, and the dropdown-open/selected states.

The inventory behind the order: the History filter bar (search
input, copy select, view toggle, More-filters disclosure, app
picker, status select, sort select), the Analytics app picker, and
the Asset Library search input all already wore the shared pill
skin (`PILL_SELECT_CLASS`) — but two hand-rolled controls in the
History bar (the view toggle, the disclosure) wore lookalike
classes instead, and the skin itself stated only two of the states
Kasra named. Rest and hover existed; a filter holding a non-default
value looked exactly like a filter at its default, so which filters
were on could only be learned by opening each one; the view
toggle's on state was a quiet grey step from its off state; and the
pill selects and search inputs carried no keyboard focus ring at
all, though the app's chips have had the shared one all along.

## Decision

**One treatment, stated once, in `index.css` as `.filter-control`.**
The shared pill skin carries the class (and the shared `focus-ring`)
from `PILL_SELECT_CLASS`, so every control wearing the skin — every
filter select and search input, on every page — inherits the states
together; the two hand-rolled History controls wear the class
directly. The states:

- **Rest** — the existing pill: hairline border, recessed tint,
  bevel rim. Unchanged; the treatment is a refinement of this look,
  not a new visual language.
- **Hover** — the pill-studio lift and lit rim, already shared.
- **Focus-visible** — the shared indigo halo (`.focus-ring`), now
  on the filter controls for the first time.
- **Open** — a disclosure standing open (`aria-expanded="true"`)
  wears the indigo border. A native select's open moment is its
  focus, which the halo already states; the native menu itself
  stays native (the settled rule that raw selects keep their
  platform behaviour and arrow stands). Where a platform lets the
  page dress the menu — Chromium's list on Windows, Firefox — the
  options wear the app's dark card and the chosen option the brand
  fill; everywhere else the menu is ignored by the rule and stays
  exactly as native as it was.
- **Active** — a filter holding a non-default value wears the
  selection treatment (`data-active="true"`): indigo border
  (`--indigo-45`), indigo tint (`--indigo-15`), the lit top rim —
  the same statement the verdict thumbs make when chosen. Indigo
  means "selected" in this app, so an active filter reads as ON at
  a glance, without opening it. Each control names its own default:
  a search holding text, the copy filter on its non-default side, a
  chosen status, a non-default sort, the app picker narrowed to one
  app. A pressed toggle (`aria-pressed="true"`) wears the same
  treatment, so the view toggle's on/off is unmistakable; its
  hand-rolled grey active classes are gone. The More-filters
  disclosure wears the active state whenever a filter behind it is
  on — the same condition its "(active)" suffix already names.

**The picker's two forms stay distinct.** `AppPicker` in its filter
form (an "every app" option exists) marks a chosen app active. As a
page's app switcher (Brand Setup, Asset Library) it names the
current context — always chosen, never filtering — and never wears
the active state.

**Out of scope, deliberately.** The wizard's and editor's selects
(camera setup, direction, model, resolution, video fit) are form
fields wearing `CONTROL_CLASS`, not filters; nothing about them
changes. The shared `Chip` is a selection chip for picks, not a
filter, and keeps its own treatment.

## Pins

The render smoke suite gains "every filter control wears the one
treatment and an active filter reads active": the shared skin
carries the class and the ring, the stylesheet states the active
look in the selection indigo and the pressed state beside it, and a
History mount with filters preset by URL shows each control's
`data-active` exactly where its value leaves the default — and
nowhere else.

## Consequences

- Any future filter control that wears `PILL_SELECT_CLASS` — or
  the class directly — inherits rest, hover, focus, open, and
  active states without re-deciding them; a new filter states its
  default and marks `data-active` when its value leaves it.
- Which filters are on is a property of the bar's face, not of its
  menus: a scanning founder sees the search lit, the status lit,
  the sort quiet, and knows the shape of the list below.
