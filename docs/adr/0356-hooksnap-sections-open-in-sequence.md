# ADR 0356: HookSnap's sections open in sequence, each at its headline until the work above it is done

## Status

Accepted, Nov 25 2026 — Kasra's order on a voice call: every
section on the HookSnap page collapses by default, showing only
its headline, with no new icon and no new chrome on the
headline; a section auto-expands only when the work that fills
it is done — and not from the get-go: a section opens only
after the previous section's requirement is done, successfully,
the expansion running in sequence down the page. Once expanded,
a section displays everything it displays today.

Update, Nov 25 2026 (later the same night): the gate for The
hook named below — the settled direction read — is superseded
by ADR 0357, Kasra's correction at his live review: The hook
reveals only when place and wardrobe stand selected. Every
other gate in this record stands as written.

## Context

After ADR 0355 the page stands in work order — Choose an app,
Place and wardrobe, The hook, Presenter photo, Render the hook,
Demo + CTA, Post kit — but all seven sections rendered in full
from the first moment: `SectionCard` had no collapse support,
`HookCta.jsx` carried no expanded state, and the presenter
photo section (the shared `PresenterPhotoControl`, its own
panel) rendered whole too. The founder faced the whole canvas
at once, including sections whose work could not exist yet —
a render panel with nothing to render, a finish step with no
finished hook, a post kit with nothing to post.

## Decision

Each section stands at its headline alone until its turn
comes, driven purely by state the page already holds — no new
user-facing toggle, button, icon or control of any kind, and
no content, copy, control, subtitle or testid inside any
section removed or changed. `SectionCard` gains an optional
`collapsed` flag (the body stands in a hidden wrapper under
the unchanged heading row) and `PresenterPhotoControl` the
same flag (its `GroupLabel` headline stands; everything under
it hides); callers that never pass the flag — the Create
wizard above all — render byte-for-byte as before.

The per-section completion mapping, from the page's existing
state:

- **Choose an app** has no previous requirement: it stands
  open when the page is ready for work. It is complete when
  the picked app's draft project exists.
- **Place and wardrobe** opens on that draft (the card already
  renders only then). It is complete when the direction read
  for the picked app has settled — landed or failed.
  `useWizardDirections` now reports that settle
  (`directionSettled`): the place and wardrobe picks are
  optional refinements the page defaults — the hook generates
  from them empty, and a saved row's picks are matched in by
  the read itself — so the settled read, not a pick, is this
  section's work done. A failed read settles too, so the
  cascade can never deadlock on an error the page already
  survives today, and a hook already on file proves the step
  was passed either way.
- **The hook** opens when the direction has settled. It is
  complete when a hook line exists (`hook_line`, read through
  the page's edits, so the just-written line counts).
- **Presenter photo** opens when the hook exists. It is
  complete when a `character_reference` asset is attached to
  the project row.
- **Render the hook** opens when the photo is attached. It is
  complete when the page's generation stands `completed`.
- **Demo + CTA** opens when the render has finished. Its own
  work — the combined export — is founder-side: no page state
  records it and nothing downstream requires it.
- **Post kit** opens when the hook exists, alongside the
  presenter photo. Its first work, the caption preview, is
  written from the hook line alone (ADR 0353) and exists to be
  read before the render finishes; its frozen kit is the
  render's own artifact, the same kit History carries, and
  nothing in the section waits on the Demo + CTA export.
  Gating it on the finish step would hide the preview until
  after the very render it precedes — so its gate is the
  hook, the last thing its own work needs.

A section whose content already exists stands open on that
alone (a photo attached opens the render; a finished render
opens Demo + CTA and the post kit), so returning to a worked
project resolves the whole cascade open in sequence from
state, instantly, with nothing to redo.

## Alternatives considered

Requiring a place and a wardrobe pick before The hook opens:
rejected. Today's page treats the picks as optional — the
hook generates from the app's defaults with both empty — so
that gate would change what the sections do, not when they
show, and would strand the page's own first-run flow (and its
checks) behind two picks Kasra never made mandatory.

Gating the Post kit on Demo + CTA's completion: rejected for
the reason named above — it makes ADR 0353's caption preview
unreachable in the only window it exists for, and invents a
dependency the page does not have; the kit is written by the
render, not by the finish step.

A user-facing collapse toggle on each headline: rejected by
the order itself — no new icon, no new chrome; the headline
stays exactly the one the section has today.

## Consequences

The page now reads as a sequence: pick the app, the direction
settles, write the hook, attach the photo, render, finish,
post — each step's section opening as the previous step's
work lands, and a finished project opening whole. The
render-smoke suite gains three ADR 0356 checks (red before
green): a fresh draft stands with the later four sections at
their headlines and their bodies intact under the collapse; a
walk down the page opens exactly the next section at each
finished step; a completed project opens with every section
expanded and its full content standing. No existing check was
changed: the collapse decides when a body shows, never what
it shows, so every interaction the suite already drove inside
the sections drives the same content.
