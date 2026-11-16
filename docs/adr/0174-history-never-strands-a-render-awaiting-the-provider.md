# ADR 0174: History never strands a render awaiting the provider

Status: accepted

Extends ADR 0171 (the panel never stops watching a live render) to
History.

## Context

Kasra, Nov 16 2026, over a screenshot of a History card standing on
a black empty stage: the card read "Still marked as generating —
The last saved state is still generating. Check again to ask the
provider for an update." His rule, verbatim: "this should never
happen."

What the code proved: History's awaiting poll carried the same two
give-ups the panel carried before ADR 0171. `historyPolling.js`
retired a row after 20 attempts (~3 minutes at its 10s interval) as
"paused", and stopped it on the first non-throttling failure as
"error"; the interval then cleared and the row was never checked
again. The page rendered the retirement as a dead end — the paused
banner ("Automatic checks paused after 20 attempts… Use Check
again, or return later"), the stopped line, and the stage notice
above — leaving the manual Check again button as the only way out.
`historyRepair.js`'s own comment named the stranded case: renders
that finished at the provider while the app was down, so nothing
ever polled them and they kept the status forever. A founder who
did not think to press the button met a finished render presented
as permanently stuck.

## Decision

- History polling for a row awaiting the provider never permanently
  stops while the row is still submitted/generating. The 20-attempt
  pause and the stop-on-error are deleted; there is no "paused" or
  "error" poll state. Polling for a row ends only when the row
  settles — the video lands, or a terminal status arrives.
- Failures stretch the row's own wait instead of spending a budget,
  with the panel's backoff shape (ADR 0171): throttling grows the
  wait per consecutive 429 (10s base × (1 + throttles), capped at
  60s), a sustained run of other failures (3+) settles the wait at
  twice the base, and a success resets both counters and the
  cadence. One row's failures never touch another row's checks.
- From the third consecutive failure of either kind the row says so
  in the panel's words — "Still rendering — status checks are being
  slowed down right now… It has not stopped: the finished video
  will appear here." At the base cadence the row states the live
  truth: automatic checks are active and the finished video will
  appear on its own when it lands.
- The dead-end presentation is deleted: the "Still marked as
  generating / Check again to ask the provider for an update" stage
  notice, the paused banner, and the stopped line are gone. The
  stage notice for an awaiting row now names the state honestly —
  still generating, still being checked — and the attention
  banner's guidance for awaiting rows says History keeps checking
  on its own instead of directing the founder to the button.
- Check again remains on the card as a shortcut only: it asks the
  provider immediately, and its result note says History keeps
  checking on its own too. No copy presents it as required, and it
  is never the only way out.

## Consequences

A render that finishes at the provider — including one that
finished while the app was down — appears on its History card on
its own whenever History is open, however long the provider took
and however rough the connection was on the way. The cost is the
same bounded, backed-off poll the panel already pays: never a
tight loop, the minimum interval unchanged, every failure path
stretching it. Pins: a smoke check asserts the give-up machinery
and the dead-end copy are absent from `historyPolling.js` and
`GenerationHistory.jsx`; jest covers the backoff shape directly,
throttling stretching the wait and marking the row slowed, a
failing row watched indefinitely while a settled row is never
re-polled, polling still firing past the old 20-attempt limit with
a late finish landing, and a generic error backing off instead of
stopping the loop.
