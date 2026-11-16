# ADR 0171: The panel never stops watching a live render

Status: accepted

## Context

Kasra waited five-plus minutes on the in-flight panel (voice call,
Nov 16 2026; his screenshot showed a 'submitted' row at 0:19 elapsed)
and no video appeared in the section. His order: debug it and fix it
so the panel cannot abandon a live render.

What the code proves: the poll chain carried two hard budgets —
MAX_POLL_429s = 20 consecutive rate-limited polls and
MAX_POLL_FAILURES = 5 consecutive generic failures — after which
pollTimedOut stopped polling permanently and the panel told the
founder the clip "will appear in History once the provider finishes".
At the 6s interval, sustained throttling retires the panel at about
two minutes, well inside a normal long render; five transient
failures do the same faster. The render itself is unaffected: the
backend resolves it detached and the sweep drains it (ADRs
0138/0148), so the clip lands in History while the panel sits frozen
on its in-flight stage.

What the code cannot prove about that specific wait: there are no
production logs in the build environment. The possibilities are
(a) sustained 429s retired the panel at ~2 minutes, (b) five
consecutive generic failures did the same, or (c) the provider was
simply still rendering at five minutes — provider renders can run
long. Under (a) and (b) this change is the fix; under (c) it is
still required, because the panel must stay alive to show the video
the moment it lands. No certainty beyond that is claimed.

## Decision

- Both hard budgets are deleted. While a generation row is in
  flight, polling never permanently stops: rate limiting throttles
  the status CHECK, not the render.
- Failures stretch the interval instead of spending a budget: 429s
  grow the delay per consecutive throttle (6s → 12s → 18s …, capped
  at 60s — the growth the panel already had); a sustained run of
  generic failures (3+) settles the cadence to 12s. The first
  success resets both counters and the cadence, and the
  visibility-return immediate poll is unchanged.
- From the third consecutive failure of either kind, the panel says
  so honestly instead of silently slowing: a stall notice ("Still
  rendering — status checks are being slowed down… It has not
  stopped: the finished video will appear here.") with a "Check
  again now" button that polls immediately. A success clears it.
  No terminal poll state remains reachable while a row is in flight;
  polling still stops on a terminal row status, as before.

## Consequences

A long or throttled render now resolves in the panel where the
founder is watching, whenever it lands, instead of only in History.
The cost is a bounded, backed-off poll for the render's lifetime —
never a tight loop: the minimum interval is unchanged and every
failure path stretches it. Pins: the permanent-stop machinery is
asserted absent from the source; six consecutive failures (past the
old budget) keep the loop firing with the stall notice up, and a
success clears it; a throttled stretch restores the normal cadence
on success; the pre-existing transient-failure and 429 pins stand.
