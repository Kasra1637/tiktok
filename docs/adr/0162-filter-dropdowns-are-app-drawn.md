# ADR 0162: Filter dropdowns are drawn by the app

Status: accepted

Supersedes ADR 0161's native-menu approach only. The
`.filter-control` treatment itself — the states, the selection
indigo, the picker's two forms — stands exactly as 0161 decided.

## Context

Kasra opened the shipped filter dropdowns on Nov 15 2026 and saw
no enhancement: the closed pills wore the polish, but the open
menu looked exactly as it always had. He was right, and the cause
was structural. Every filter dropdown was a native `<select>` —
the History copy, status and sort selects, and `AppPicker`
everywhere it renders — and a native select's open menu is drawn
by the browser/OS, which ignores the page's styling. The
`.filter-control option` rules ADR 0161 shipped only ever reached
the platforms that let a page dress the menu (Chromium's list on
Windows, Firefox); on the founder's browser the menu stayed the
OS's own. ADR 0161's caveat named this honestly, and the founder's
verdict closed the question: a treatment he cannot see when the
dropdown opens is not done. The open and selected states were the
states he had explicitly ordered — hover, toggled/active, and
dropdown-open/selected — so the dropdown itself had to become the
app's own drawing.

## Decision

**The filter dropdowns are one shared app-drawn control,
`FilterSelect` (`frontend/src/components/FilterSelect.jsx`).** A
button wearing the existing `.filter-control` skin opens a
listbox panel the page draws itself:

- **Closed** — the same pill as before: same skin, same
  `data-active` rules (each control still names its own default),
  same labels, same `data-testid`s. While open the button wears
  the open statement ADR 0161 already defined, the
  `aria-expanded="true"` indigo border.
- **Open** — the menu is a panel in the app's card surface
  language: popover surface, hairline border, the nested 12px
  radius, the large shadow. The chosen option reads selected in
  the same statement an active filter makes — the selection
  indigo, as a tint down the row with a check at its head — and
  the highlighted option (keyboard or pointer) is a plain step up
  from the panel, so a chosen row still reads stronger than a
  highlighted one.
- **Converted** — the History copy filter, status select and sort
  select, and `AppPicker` in every usage (the History and
  Analytics filters, and the page-switcher forms in Brand Setup
  and the Asset Library), because the picker is one component and
  converts as one. The view toggle is not a dropdown and is
  untouched — its `aria-pressed` statement already renders as
  ordered. The Asset Library search is an input, not a dropdown,
  and is untouched. The wizard's and editor's form-field selects
  keep `CONTROL_CLASS` and stay native, as ADR 0161 scoped them.
- **Behaviour parity is the contract.** Same options, same
  values, same order, same `onChange` effects, same URL-param
  behaviour on History. The keyboard contract is the native one,
  kept deliberately: arrows, Home and End move the highlight,
  Enter and Space choose, Escape closes without choosing, Tab
  closes and moves on, first letters jump, a press outside
  closes. Focus stays on the button throughout
  (`aria-activedescendant` names the highlighted option), so
  closing a menu lands the founder back on the control he opened.
  Choosing a value reports it through `onChange` exactly as the
  native change event did. Header pickers open their menus aligned
  to the button's right edge, so a menu at the page's edge never
  spills past it.

## Pins

The render smoke suite gains "filter dropdowns open an
app-drawn menu and choosing applies the filter": the status
control is the dropdown button (`aria-haspopup="listbox"`),
clicking it opens a `role="listbox"` menu whose options are
`role="option"`s with the current value `aria-selected`, choosing
another value navigates the status param and closes the menu,
and ArrowDown/Escape drive the sort menu by keyboard. The checks
that drove the native selects now choose through the custom menu
(`chooseOption`), and the one check that read a select's `.value`
reads the button's `data-value`. The ADR 0161 treatment pin is
unchanged and still passes — the closed face did not move.

## Consequences

- A filter's condition is now visible in both of the places the
  founder looks: on the bar's face (0161) and inside the open
  menu (this record). No future filter dropdown reaches for a
  native `<select>`; a new one is a `FilterSelect` with its
  options as data and inherits rest, hover, focus, open and
  selected without re-deciding them.
- The dead `.filter-control option` rules are deleted from
  `index.css`; the general `select option` rules remain for the
  form fields that are still native.
- The cost is the one native selects never charged: the menu's
  keyboard, focus and dismissal behaviour is the app's own code
  to keep. The pins above are its contract.
