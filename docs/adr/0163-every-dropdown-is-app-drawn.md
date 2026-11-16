# ADR 0163: Every dropdown is drawn by the app

Status: accepted

Extends ADR 0162 and supersedes its form-field scoping only.
The filter decision — one shared app-drawn control, the
`.filter-control` treatment on its closed face — stands exactly
as 0162 decided. What changes is the reach: 0162 converted the
filter dropdowns and left the wizard's and editor's form-field
selects native, as ADR 0161 had scoped them. That scoping is
what this record overturns.

## Context

Kasra widened the order on the same Nov 15 2026 voice call,
minutes after the ADR 0162 build started: asked what else was
missing, he heard that the create flow's dropdowns (camera
setup, direction, model, resolution, video fit), the render
panel's two and the Demo + CTA editor's one were still the
browser's own menus, left out on purpose as form fields rather
than filters — and answered "Okay. It's all." Every dropdown in
the app gets the same treatment, whichever family it belongs to.
The structural fact from 0162 applies to them unchanged: a
native select's open menu is drawn by the browser/OS and ignores
the page, so on the founder's browser those menus would have
stayed plain no matter what skin the closed field wore.

The remaining native selects, by grep: `DirectionSelect` in
`components/studio/ReviewPanels.jsx` (the Review Location and
Wardrobe picks), the model and resolution selects in
`components/GenerationPanel.jsx`, the camera setup select in
`pages/CreateVideo.jsx`, and the base clip's Video fit select in
`demoCta/DemoCtaEditor.jsx`. The Asset Library held none beyond
the already-converted `AppPicker` — its one `<select>` mention
is a historical comment about a removed one-option control.

## Decision

**One dropdown component for the whole app: `FilterSelect`,
generalized and renamed `AppSelect`
(`frontend/src/components/AppSelect.jsx`).** No second component
is forked; the form fields differ from the filters only in the
skin the caller passes and two needs the filter control never
had:

- **Skins stay the caller's.** Filter dropdowns keep
  `PILL_SELECT_CLASS` and every ADR 0161 `data-active` rule;
  form fields pass `CONTROL_CLASS`, so the closed control keeps
  its form-field look — 44px height, rounded-xl, the input well —
  and only the menu becomes the app's. The menu itself is one
  language everywhere: the same panel, the same selection indigo
  on the chosen row, the same highlight step.
- **A disabled state.** Form fields disable while work is in
  flight (the render panel while a render runs, the Review picks
  while the step is busy, a direction pick before its options
  load); the button now takes `disabled` and cannot open, as a
  disabled native select cannot.
- **A block form.** A field fills its row; the wrapper stands
  block (`.app-select-block`) so the button's full width is the
  row's width, as the native select's was. In a flex row the
  wrapper takes the row's flex share instead (the Video fit
  control beside its Reset button).

**Converted** — the render panel's Model and Resolution, the
Review camera setup, `DirectionSelect` (Location and Wardrobe),
and the Demo + CTA Video fit. For the Video fit only the control
converts: what Cover / Contain / Fill do is unchanged, and the
control stays inside Fine-tune framing — per-clip fit is a
separate queued build, not this one. `DirectionSelect`'s prompt
row stays a row of the menu (value `""`), as the native prompt
option was a row of its list: it can be re-picked to clear the
field.

**Behaviour parity is the contract, as in 0162.** Same options,
same values, same order, same defaults, same `onChange` effects,
same `id`s (each page's `<label htmlFor>` still resolves — the
button carries the id, and a button is a labelable element),
same `aria-label`s, same `data-testid`s. Choosing reports the
picked value through `onChange` exactly as the 0162 control
does — including a re-pick of the value already held, which a
native change event would not have fired for: the History
filters treat a pick as a navigation (the copy filter's re-pick
of the side already showing still moves the URL param, pinned
by "History shows one copy section at a time"), so the
generalized control keeps 0162's reporting semantics untouched
rather than trading a pinned behaviour for a theoretical one.

**The last native-menu dressing leaves `index.css`.** The
`select` / `select option` block that painted the OS-owned list
dark on the page's behalf has no element left to act on and is
deleted; the app's menus need no dressing rules because they are
the app's own markup.

## Pins

The render smoke suite gains two checks, red before green:
"no native select remains: the render panel and Review
dropdowns are the app's own listbox" (neither surface renders a
`<select>`; the model, resolution, camera and direction controls
are `aria-haspopup="listbox"` buttons) and "no native select
remains: the Demo + CTA video fit is the app's own listbox"
(the editor renders no `<select>`, and the fit menu offers
exactly cover / contain / fill). The checks that drove the form
selects now choose through the menu (`chooseOption`) and read
the button's `data-value`; the direction check reads the offered
options from the open menu in place of the native option list;
the wizard length sweep also opens every app-drawn dropdown on
each step and reads its options, so a length control cannot
hide inside the custom menu; and the harness's native
`selectOption` helper is deleted with the last select it could
drive. The ADR 0161 and 0162 pins are unchanged and still pass.

## Consequences

- No native `<select>` remains anywhere in the app. A future
  dropdown is an `AppSelect` with its options as data and its
  caller's skin; it inherits the keyboard contract, the menu
  language and the selected statement without re-deciding them.
- The cost named in 0162 — the menu's keyboard, focus and
  dismissal behaviour is the app's own code to keep — now
  covers every dropdown in the app, not only the filters'. The
  pins above are that contract.
- `CONTROL_CLASS` now names the skin of a dropdown button in
  form fields (and of no raw select, there being none);
  `formControls.js` says so.
