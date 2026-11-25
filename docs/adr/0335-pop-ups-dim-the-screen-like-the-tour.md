# ADR 0335: Pop-ups dim the screen like the tour

## Status

Accepted, Nov 25 2026 — Kasra's order in the main chat.

## Context

The centered pop-ups (the angle sheet, ADR 0330 as corrected;
the Focus pick, ADR 0334) each dimmed the screen with their own
black at 60%, and the shared dialog behind every confirm dialog
used a heavier 70% black with a blur. Three dimming treatments
for one job, and none of them the one Kasra pointed at: the
"Show me around" tour, whose backdrop and spotlight ring darken
everything but the focus with a flat 55% black.

## Decision

One scrim for every pop-up: a `.pop-scrim` rule in index.css
carrying the tour's own dim — `rgba(0, 0, 0, 0.55)`, flat, no
blur. The angle pop-up's backdrop, the Focus pop-up's backdrop,
and the shared dialog overlay all wear it, so while any pop-up
stands, the rest of the screen looks exactly as it does while
Show me around is running, and the pop-up alone holds the eye.

The tour itself is untouched — it already wears this dim; the
pop-ups were brought to it, not the other way round. The mobile
sidebar drawer's scrim and the sign-in modal's backdrop are not
pop-ups and keep their own treatments.

## Consequences

Any future pop-up wears `.pop-scrim` on its backdrop; a new
dimming value is a change to this record, not a local choice.
The render-smoke suite pins the scrim on the angle and Focus
pop-ups and on the shared dialog overlay's source.
