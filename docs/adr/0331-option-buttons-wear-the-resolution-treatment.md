# 0331 — Every small option button wears the resolution treatment

## Status

Accepted, Nov 25 2026. Supersedes the button-design half of ADR
0330's live-review addendum (the centered pop-up and the three-wide
direction window stand).

## Context

ADR 0330's live-review round left two button families standing:
the render panels' resolution row (the shared Button in a
thumb-pair row — brand and thumb-selected on the pick) and the
rounded pills the Voice pick wore, which the direction fields and
the HookPicksControl pills (tone, shape, hook length) shared or
matched. Kasra compared them live and ruled: do not wait on
button selection, button style, or hover effect — every one of
these small option buttons matches the resolution buttons, the
480p / 768p row being his named example.

## Decision

One treatment for every small option set named here — hook
length, tone, shape, location, wardrobe, and the voice pick:
the shared Button (size sm) in a `.thumb-pair` row, variant
brand with `thumb-selected` on the picked option, secondary
otherwise, `tap-chip` on every button. Selection state, hover
motion (the Button base's 300ms ease and 1px lift), and spacing
(the shared `.thumb-pair` gap) are therefore identical wherever
a founder makes a small choice. The pill design retires from
these controls; the camera setup already wore this treatment
and is unchanged.

## Consequences

PickPills, DirectionSelect, and VoiceModeControl all render the
one treatment, so a fix or restyle to the resolution row's design
now carries to every small option set by construction. The
direction fields keep ADR 0330's corrected behavior — three
options shown, a saved pick outside them on the last seat, "New
options" bringing the next set — under the new skin. Kasra's
spread gate still holds for the non-button follow-ups from the
Nov 25 audits (the History pop-up and the four remaining
dropdown conversions); button style was expressly taken out of
that wait by this ruling.
