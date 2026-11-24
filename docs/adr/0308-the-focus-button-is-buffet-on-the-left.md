# ADR 0308: The Focus button is Buffet, on the left

Status: accepted

## Context

The Focus block's outcome-refresh button (ADR 0288) stood at the
right end of the Focus label row and was labeled Refresh. On
Nov 23 2026 the founder ordered two changes to it: rename it —
"instead of Refresh call it Buffet" — and move it: the button
shows on the left side, and no button stands on the right
portion of the row.

## Decision

The button is labeled Buffet, in its resting and busy states
alike, and stands on the left of the Focus row, beside the
Focus label. Its behavior is untouched: one click writes a
fresh outcome layer onto the profile from its stored facts,
and the pick's list is replaced by the fresh lines. Its
test id (`hook-picks-focus-refresh`) is unchanged, so the
checks that drive it keep their grip.

## Consequences

The Focus row reads label, then Buffet, then the pick — no
control competes at the row's right end. Any future button for
this block joins the left cluster or goes elsewhere in the
card; the right portion of the Focus row stays empty.
