# 0061 — Provider 429 is throttling: poll waits quietly, submit names the retry

- **Status:** accepted
- **Date:** 2026-10-30
- **Anchors:** `backend/generation_planning.py` (`is_rate_limit_error`); `backend/server.py` (poll 429 branch, submit 429 detail); `frontend/src/components/GenerationPanel.jsx` (429 skips the outage budget); `frontend/src/pages/historyRepair.js` (429 message); smoke check "a rate-limited poll neither stops the loop nor raises the banner"

## Context

A 429 during generation used to read as a broken render. The poll handler
wrote rate-limit noise into `generations.error` and 502ed, so the panel
spent its five-poll outage budget on a healthy-but-busy provider and then
raised "Could not check generation status: Client error '429 ...'" — while
the row carried 429 text as if the render itself had failed. After heavy
throttling the founder stared at processing, then at a scary banner, with
nothing actionable.

## Decision

- **Poll:** a rate-limited status check touches nothing and answers 429
  with a calm detail ("still going — this page keeps checking"). The row
  keeps no error, and the panel does not count the poll against its outage
  budget — it just keeps waiting.
- **Submit:** a 429 means the render never started and nothing was charged,
  so the detail names the wait and the retry ("Wait a moment, then Render
  it again") instead of quoting the raw provider refusal. The row is still
  recorded failed + retryable, so "Render it again" works.
- **History recheck:** a 429 there says the provider is rate limiting and
  nothing is lost, instead of the raw request message.
- `is_rate_limit_error` is deliberately narrower than
  `is_recoverable_error`: only 429/rate-limit/too-many-requests means
  "asked too often". A 500 stays a 502 with row context.

## Alternatives rejected

- **Retry the poll server-side with backoff.** Holding the request open
  burns a worker per throttled poll; the client already polls, so the
  quiet client loop is the cheaper waiter.
- **Count 429 toward the outage budget.** Five throttled polls in a row is
  normal under load, not an outage — escalating it pages the founder over
  nothing.

## Consequences

- Throttled renders complete silently in the background instead of
  erroring; the founder only sees a banner for real outages.
- Backend tests pin the 429 poll response, the untouched row, and the
  submit wording; the smoke suite pins the budget-free client loop.
