# ADR 0334: Softer picks, full labels, New options beside the title, and the Focus pop-up

## Status

Accepted, Nov 25 2026 — Kasra's rulings at the live review of
the ADR 0331–0333 round, on a voice call.

## Context

ADR 0331 unified every small option button on the resolution
treatment, and on screen the family read heavy: a whole row of
picks at the full secondary weight, dark against the page. The
Location and Wardrobe buttons also trimmed their labels with an
ellipsis, which read as a broken, half-shown word, and their
"New options" link sat at the far end of the title row instead
of beside the title. The Focus pick still stood as a dropdown
stretching the full width of its section for one line of text —
the width complaint Kasra had already raised about the wizard's
sections — and its options are whole sentences, read before
choosing, which no row of buttons can carry.

## Decision

Four changes, one round:

1. **Unpicked options stand light.** An `.option-btn` rule in
   index.css takes the unpicked member of the option family —
   hook length, tone, shape, voice, camera setup, location,
   wardrobe, and the resolution rows on both render panels —
   off the secondary fill: a transparent ground over a hairline
   border, muted text, no bevel shadow, and a gentle indigo
   wash on hover. The pick keeps the full brand and
   thumb-selected treatment, so the choice still stands out at
   a glance. The shared Button and its variants are untouched;
   the History verdict pair, which lent the design, keeps its
   own weight.
2. **Direction labels never wear dots.** The ADR 0332 trim
   still caps a Location or Wardrobe button's text at 25
   characters, but it now ends at the last whole word inside
   the cap with no ellipsis. The full option still applies
   underneath and still shows on the button's title.
3. **"New options" stands beside the title.** The direction
   fields' title row clusters the label and its refresh link
   at the left, in the Focus row's arrangement, instead of
   pushing the link to the row's far end.
4. **Focus picks in a centered pop-up.** The Focus dropdown is
   gone. In its place: a trigger in the field's own skin that
   hugs its text — the current choice and the pop-out icon, the
   angle cards' signal (ADR 0330) — opening a centered overlay
   that lists "Let the app choose" and every outcome line in
   full; a tap picks and closes, as do the backdrop, the close
   button, and Escape. The pop-up is a picker here, not a read
   sheet: Focus is the one control whose options are
   sentence-length, and the pop-up stays a read-or-read-to-pick
   treatment — the short picks (voice, location, wardrobe,
   hook length, tone, shape) stay visible buttons in place and
   do not move into pop-ups.

## Consequences

The pick rows read light and gentle on the eyes, in Kasra's
words, with the chosen option still unmistakable. No direction
button can show a cut-off label again. The Focus field takes
only the width its current choice needs, and the wide reading
happens in the pop-up, where the width is welcome. The Focus
trigger is no longer an AppSelect, so the wizard-step dropdown
sweeps no longer count it among the listboxes.
