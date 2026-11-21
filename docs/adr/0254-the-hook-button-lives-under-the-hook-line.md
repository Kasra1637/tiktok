# 0254 — The hook button lives under the hook line it refines

Status: accepted

## Context

Kasra's ruling (Nov 21 2026, from his live screenshot of the
Hook + CTA page): the "Suggest a clearer hook" button rendered
ABOVE the hook line output. His words: the button "should
obviously always placed inside the hook line area", and before
the first generation — when no hook line appears yet — "you
gotta make sure the hook line appears above the suggest a clear
hook".

The inversion was structural. ADR 0249 made the Hook card's two
hook actions one stateful button, but left it standing in the
card's upper block, beside the steering picks it is steered by.
The spoken line area (`data-testid="hook-editors"`: the "The
spoken line" group label, its subtitle, and the `HookLineEditor`)
rendered only once a line existed, as a separate block BELOW
that button. So in the written state the refinement action stood
above the text it refines, and in the empty state the spoken
line area — the button's proper home — was not on the page at
all.

This is the same placement principle ADR 0242 settled for the
script: the suggest/remake control sits directly under its box
("just like the hook line['s] suggest the clear hook button", as
Kasra put it then), and it already holds in Create Video's
Review. The Hook + CTA card was the one surface where the
control and its text stood in the wrong order. Ordinary UX
practice agrees: a refinement action belongs under the text it
refines, read after it, not before it.

## Decision

- **The spoken line area is ONE area in both states**, inside
  the Hook card, in this order: the "The spoken line"
  GroupLabel, its subtitle, the `HookLineEditor`, and directly
  beneath the editor the card's one stateful hook button block
  (ADR 0249's control, unchanged), with the generate error
  alert under the button, where it always stood relative to it.
- **The area renders before a line exists.** The empty-state
  judgment: `HookLineEditor` renders gracefully with an empty
  value — a labelled field in the cover frame, with no checks
  or warnings of its own (the "checked as you edit" wording is
  the area's subtitle guidance, not a warning state) — so the
  editor stands above the button in its Generate state too.
  The area keeps one shape across states, the hook line (or
  its empty field) is always above the button, and the control
  never changes home between the first visit and every later
  one.
- **Nothing else moves.** The steering picks (ADR 0247) stay
  above the spoken line area — they steer the generation the
  button drives. ADR 0249's semantics are untouched: one
  button, no countdown, Generate writes from the picks,
  Suggest offers a line that is written only on accept, the
  editor still mounts with `suggestClearerHook={false}` so the
  suggestion stands exactly once. Create Video's Review and
  every other page are untouched.
- **The order is pinned, not just the presence.** Two smoke
  checks assert document order via `compareDocumentPosition`:
  in the written state the editor's field precedes the Suggest
  button and both live inside the spoken line area; in the
  empty state the area stands, its empty field precedes the
  Generate button inside it. Both failed before this change
  ("does not stand inside the spoken line area" / "does not
  stand before a hook line exists") and pass after it.

## Consequences

- The button's position is now a property of the area, not of
  the hook's existence: a founder's eye learns one home for the
  control, and the state change (Generate → Suggest) happens
  in place under the line.
- The hook-cta tour's "Sharpen the line" step targets
  `hook-editors`, which now exists in both states; the step was
  and stays optional, and the `hook-generate` step's target
  still exists in the empty state, now inside the area.
- The generate error alert moved with the button block, so a
  failed first generation is reported at the foot of the spoken
  line area instead of above an area that did not exist yet —
  the same reading order as the control that produced it.
