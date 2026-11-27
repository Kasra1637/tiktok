# ADR 0382: Regenerates stand as icon + text links

## Status

Accepted, Nov 26 2026 — Kasra's order, confirmed
twice the same evening: every regenerate button
throughout the app loses its pill and stands as an
icon plus text link only, the way HookSnap's "New
options" link already sits beside the Location and
Wardrobe headings. His framing: a regenerate is a
third-tier control, not even a secondary button;
Generate, Render and Continue keep their buttons
because those are the actions that spend and move.
Each converted link sits beside its section
heading, on the heading line — not on its own row.

## Context

The app's re-roll controls wore the shared Button's
secondary pill: Regenerate angles, Shuffle,
Regenerate plan, the templates Regenerate, the
post kit's Regenerate, HookSnap's Generate a new
hook, Create's Buffet and the two rewrite assists.
Beside them, the third-tier face already existed:
DirectionSelect's "New options" refresh and
HookSnap's Focus refresh are plain buttons wearing
one inline class string — `shrink-0 text-sm
text-muted-foreground underline
disabled:opacity-50` — muted, underlined, no
surface. The family read as two designs for one
rank of control.

## Decision

Every standing regenerate/refresh control that
wore a Button converts to a plain `<button>`
wearing the "New options" treatment, extended
with `inline-flex items-center gap-1.5` where the
control carries an icon, so icon and label sit on
one line. Icon, label text, testid, handler and
disabled behaviour are unchanged; the busy
wording stays on the link ("Regenerating
angles", "Regenerating plan", "Regenerating
copy", "Shuffling goals", "Writing the hook")
and the link disables while it runs. Converted,
by name:

- Regenerate angles (`SelectionPanels.jsx`,
  AngleSelector) — moved up beside the "Audience
  angle (required)" heading; it stands only while
  a list stands, the same condition that picks
  the list face. ADR 0372's freshness-and-hint
  line keeps its words and its seat at the head
  of the list, now under the heading row.
- Shuffle (`SelectionPanels.jsx`,
  AngleGoalPicker) — already beside the "Video
  goal" heading; converted in place, title kept.
- The post kit's Regenerate (`PostKitSection.jsx`)
  — already on the "Caption, hashtags, cover"
  heading line, beside Copy all; converted in
  place. The Demo + CTA editor's post kit reuses
  this component, so it converts with it.
- The templates Regenerate (`CreateVideo.jsx`) —
  moved up beside the "Recommended templates" /
  "Tailored template for this app" heading.
- Regenerate plan (`CreateVideo.jsx`) — the plan
  stack has no heading line of its own, so its
  first line is its heading line: the link stands
  there beside the plan-version status, where the
  pill stood. The empty-plan invite glow
  (ADR 0290) rides the link while an empty plan
  waits — `.generate-invite` is a standalone
  animation class, so the pulse survives the
  conversion untouched.
- Generate a new hook (`HookCta.jsx`) — only the
  re-roll face (a hook already on file) converts;
  the first-generation face, Generate the hook,
  keeps its accent button. It converts in place
  at the foot of the spoken-line area: ADR 0254 /
  0313 fix this control's home under the editor
  it acts on, and that standing order is more
  specific than the heading-line rule, so the
  link keeps the seat and changes only its face.
- Create's Buffet (`HookPicksControl.jsx`, the
  Create-surface face) — already beside the
  Focus label; converted in place, so it now
  matches its HookSnap "New options" twin.
- The rewrite assists' triggers
  (`LineRewriteAction.jsx`: Remake the script,
  Suggest a clearer hook) — re-roll controls
  standing under their fields; converted in
  place. Their suggestions' Accept / Dismiss
  buttons are untouched: they decide on a
  suggestion, they do not re-roll.

The shared Button's busy countdown does not ride
the links: the countdown stays with the true
generation buttons (the angle gate keeps its own),
and a link's busy face is its wording plus the
disabled state — the "New options" precedent,
which also spends a model call and never counted
down. Each link also carries `aria-busy` while it
runs — the link form of the Button's busy marker,
since the sweep itself is a filled-surface effect
with no surface to cross on a text link.

Not converted, by name and why:

- First-time generation buttons keep their form:
  the angle gate's Generate angles / Show your
  angles, the goal gate's Generate goals,
  HookSnap's Generate the hook, the strategy
  Build / Rebuild (the step's one unblocking
  action), and every Render / Generate-video
  action, including their sticky-bar faces.
- Dialog confirm buttons keep their form:
  AngleRegenConfirmDialog's Regenerate angles
  and StrategyRebuildConfirmDialog's Rebuild
  strategy are the decisions inside their
  dialogs, not standing section controls. The
  standing control that opens the angle dialog
  is the new link.
- Dropdown menu items keep their form:
  AppProfileDetail's "Refresh research & angles"
  (the regenerate-everything handler) and
  "Refresh from sources", and BrandSetup's
  "Refresh from sources", already wear the
  menu's text-row face — there is no pill to
  remove, and their trigger is a menu opener,
  not a regenerate.
- Render retries keep their form: Retry render,
  Render it again, and History's retry / recheck
  / storage actions are failure recovery — the
  primary action of their moment, not a re-roll
  of content.
- GenerationPanel's remedy buttons keep their
  form: in a blocked panel the remedy is the one
  primary unblocking action standing.
- The Demo + CTA editor's "Surprise me" chips
  keep their form: chips are the editor's own
  option language, not Buttons.

## Checks

One check added, two re-pinned; no check weakened
and no behaviour assertion changed — testids,
labels, handlers and visibility conditions are
identical, so the family's flow checks (post kit
regeneration, Shuffle, Buffet staging, the hook
generate states, the rewrite suggestion flow) pass
as they stood.

- Added: "regenerates stand as icon + text links
  beside their headings (ADR 0382)" — two DOM legs
  (Regenerate angles beside the Audience angle
  heading on Create's Audience step; Regenerate
  plan on the plan stack's first line beside the
  version status) asserting no `btn-studio`
  surface, the underlined treatment and the icon
  present, plus a source leg asserting that in
  each converted control's home file the opening
  tag nearest before its testid is a plain
  `<button>`, never the shared `<Button>`.
- Re-pinned: "the angle refresh line stands above
  Regenerate in its new words (ADR 0372)" becomes
  "the angle refresh line stands under the
  heading row in its new words (ADR 0372,
  placement ADR 0382)". ADR 0372's arrangement —
  the line above the control — is superseded by
  this round's heading-line placement: the
  control moved beside the heading, so the line
  now stands under the heading row. The line's
  words, stamp, separator and one-line shape are
  asserted exactly as before, and the
  fixed-camera note's position (below, in the
  list) is asserted at the same strength.
- The empty-plan `generate-invite` pins pass
  unchanged: the class rides the link.
- Re-pinned: "goal shuffle counts up in flight,
  then cascades cards in" — its in-flight busy
  assertion pinned the pill's mechanism
  (`data-busy="true"`, the attribute the sweep
  keys off). Shuffle is a link now, so the
  assertion pins the link's busy face instead:
  `aria-busy="true"` and the control disabled.
  Every other assertion stands at full strength —
  the label naming the work, no second narrator
  line beside the control or after it, and the
  staggered card cascade on arrival.

## Alternatives considered

- A shared LinkButton component: rejected. The
  house style already inlines the "New options"
  class string at both of its seats; a new
  component is a bigger change than the order,
  and the two forms would drift during migration.
- Keeping the busy countdown on the links:
  rejected. The third-tier precedent never
  counted down, the busy wording names the wait,
  and a countdown is the generation buttons'
  narration (ADR 0140's render-progress rule is
  untouched).
- Converting the dialog confirms and the menu
  items too, for completeness: rejected. Neither
  wears a pill today; converting them would
  change decision and menu faces Kasra did not
  name, past the order's own line.
