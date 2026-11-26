# ADR 0368: Review's headings wear the one face, and its descriptive lines are gone

## Status

Accepted, Nov 26 2026 — Kasra's spread order in the main
chat. Headings and lines only: ADR 0141 stands — Review
stays one column at every width, and no pair is built
here.

## Decision

These bold labels become GroupLabel with their own icons:
the script field's own label (PenLine), the HookLineEditor's
"Hook line" label (AudioLines — the shared editor, so the
face lands on HookSnap too, from the one seat; ADR 0366
records the HookSnap side), CoverTextEditor's "Cover text"
title (Type), the demo-brief label "What the demo should
show" (Clapperboard), CraftCheckCard's "Craft check"
title (ShieldCheck), and the piece-length heading "Length
of the generated piece" (Ruler). "This plan is empty"
takes the eyebrow face lite — no icon.

Removed, as pure description: "The spoken story after the
hook — demo and CTA stay yours."; "The words on screen in
the first two seconds of your clip." (the cover subtitle);
"A note about your own recording — never reaches the
render."; "The opening line spoken in your generated Hook
+ Story clip." (the HookLineEditor subtitle, removed in
ADR 0366's seat); "Writes hook, script, shots, and demo
note. Editable below."; "Builds your hook, script, shots,
and demo note from your profile, your angle, and your
goal."; "The outcome this template is built for, in their
terms."

Kept, untouched, by name: "A framing to aim at, not a
result this video can promise." — the honesty guardrail
under the template outcome. It is an instruction about
what the outcome line means, never description, and it
keeps its own line exactly as it stood. Every state line,
count, staleness note and instruction on the step stays.

## Checks

Changed, named here per the house rule:

- "the cover text shows in review as plain text under its
  subtitle with no score beside it": renamed ("…under its
  title…") and re-anchored — the check now asserts the
  section carries NO subtitle, its title wears the eyebrow
  with its icon, and the cover words sit directly under
  the title. Its subjects (plain text, no field, no score
  note, no preview frame) are unchanged.
- The ready-state plan-panel check asserted the panel
  INCLUDES "Builds your hook, script, shots, and demo note
  from your profile, your angle, and your goal." — flipped
  to absence, beside its standing pins against the older
  landing-place lines.
- "the studio never offers a call to action or a product
  demo": its closing assertion — that the demo brief field
  "says it is a note to the founder, not the model" via
  the removed line — becomes an absence pin for that line.
  The boundary it guarded is structural (the brief is
  never passed to the render) and the check's field and
  value assertions stand unchanged.

New in this round: the Review check pinning all six
converted labels, the removed lines' absence, and the
guardrail's presence; and the empty-plan check pinning
the lite eyebrow heading.

## Alternatives considered

Converting the section-level "Script" GroupLabel (FileText)
instead of the field's own label: both stand, and the
audit named the field's label — the section heading was
already in the one face. Leaving the guardrail folded
into a subtitle for compactness: it was cut once that
way; it keeps its own line.
