# 0253 — History shows every video in one layout

Status: accepted (the legacy story renders' read-only display, ADR 0243, is explicitly untouched)

## Context

Kasra's ruling (Nov 21 2026): videos made with the Hook + CTA page
lay out differently inside History from videos made through the
Create Video steps, and must match the Create Video card layout.
His named offender: "a long vertical posting checklist that
completely disfigures the layout" of the hook videos' cards, "along
with some other element."

The comparison was made section by section, in code. What it found
is recorded here exactly, including where Kasra's named offender
does not live:

**The card is already one component.** Every render — wizard, hook,
legacy story — renders through the same `GenerationRow`, the same
`.history-row-grid` (media column capped at 288px at desktop
widths, the clip at about half height), and the same record
sections. Post copy and Plan context pair side by side by a
data-driven rule (ADR 0153): the pair engages when both slots
render and the row carries context. Hook rows carry audience and
location, so their sections pair exactly as a wizard row's do.
There is no second hook layout to remove.

**The posting checklist is not on hook cards.** The only element
named a checklist anywhere in History is the legacy story kit's
(`LegacyStoryKit`, `data-testid="story-kit-checklist"`), rendered
when a row carries a `story_kit`. Hook renders never carry one —
verified across the codebase: a hook's post kit is the standard
video kit (caption, hashtags, cover text), and "checklist" exists
only in story kits. So the long vertical list Kasra saw cannot have
come from a hook card's post kit in this code: the card that
stretches that way in the same list is a legacy story render's —
the read-only record ADR 0243 deliberately preserves — or an older
build's card. Either way it is not the hook cards' furniture, and
this change does not touch the legacy display: it is the record of
a retired feature, explicitly out of scope.

**The provable divergence is the draft link.** A hook card's "Work
with this render" block offered "Remix this plan" (or, on a winner,
"Another take like this") linking to `/create?project=<hook id>` —
into the wizard, which has no surface guard and would adopt the
hook draft as a wizard project, under plan wording a hook does not
have. A regular card's link is correct; the hook card's was wrong
in destination and in words.

**The root enabler: History could not see the surface.** The list
payload carried the project's kind (both are "video") but not its
surface, so no part of the card could have treated a hook render
differently even where it should.

**Data-absent furniture, named and not fabricated.** Three regular
-card elements are absent on hook cards because the hook flow never
writes their data: the preview's goal chip (`objective` is NULL —
hooks brief no objective), the "template vX" provenance chip
(`template_id` is NULL — hooks use no template), and Plan context's
"Your demo brief" row (`demo_brief` is NULL — a hook's demo is
attached in its finish step, not briefed). These are missing facts,
not layout differences; inventing values to fill the slots would
lie on the card, so they stay absent and are named here as the
complete list of remaining visual differences.

## Decision

- **The history list names the surface.** The query selects
  `p.surface AS project_surface` beside `project_kind`, and the
  serializer passes it through (`"hook_cta"`, else `""`) — pinned
  in the backend suite for a hook render and a wizard render alike.
- **A hook card's draft link goes home.** For a row whose
  `project_surface` is `"hook_cta"`, the link points to
  `/hook-cta?project=<id>` (the page reads that deep link), reads
  "Reopen this hook", and its title names Hook + CTA; a winner
  keeps the shared "Another take like this" wording, pointed at
  Hook + CTA. Regular cards' link, wording, and titles are
  byte-for-byte unchanged.
- **A smoke pin stands both cards side by side**: a regular
  completed row and a hook-shaped completed row (surface carried,
  no objective/demo brief/template, post kit present, audience and
  location present) assert the same section set and arrangement —
  Post copy section, Plan context section, the paired class, the
  journey line, no story-kit section, no checklist anywhere — and
  the two draft links' destinations and wording.

## Consequences

- Nothing about the legacy story display changes: its kit, its
  checklist, and its read-only standing are ADR 0243's, untouched
  and still pinned by its own checks.
- A noted sibling, deliberately NOT fixed here: Analytics'
  next-take link (`lib/nextTake.js`) builds the same `/create`
  destination for any row with a live draft, hook rows included,
  and the analytics payload does not carry the surface either.
  Kasra's ruling named History; giving Analytics the same
  correction is a separate, smaller decision that can now ride the
  same `project_surface` pattern.
- With the surface visible, any future per-surface card behavior
  has a named input instead of another inference from kind or kit
  presence.
