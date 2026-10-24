# Opening-message verification

Date: 2026-10-24

## Change

Opening text now requests exactly 20 app-grounded, distinct messages through the existing OpenRouter service. The first successful response updates the editor's controlled text; subsequent clicks consume unseen suggestions without another request. No message/copy counter is displayed. CTA selection and existing single-source export behavior remain unchanged.

History attachment supplies its app context; restoring a pinned source restores that app. The server resolves only the caller's approved profile, or the existing active app for a standalone editor. Missing credentials, rejected responses and provider errors preserve the current text and show a remedy. Pending clicks are deduplicated, old-app responses are discarded, and edits made while waiting are preserved.

Structure: [ADR 0026](../docs/adr/0026-fresh-opening-message-batches.md).

## Final gates

- Full backend: **1146 passed**, 182 existing deprecation warnings.
- Frontend unit: **100 passed**, 17 suites.
- Mounted render smoke: **248 passed**, including 20 distinct controlled-input updates and counter absence.
- Named imports: **148 files**, no problems.
- Frontend logic and onboarding target audit: passed.
- Production build: succeeded with existing hook-dependency warnings in DemoCtaEditor and CreateVideo.
- Diff whitespace check: passed.

Removed legacy hookVariants tests referenced retired Next/Add/Remove APIs; their opening behavior is replaced by useOpeningMessages tests, while CTA surprise coverage remains.

## Browser exercise and limitation

Ran the actual CRA editor at `http://127.0.0.1:3002/demo-cta` with FastAPI at port 8002.

- Real click reached the actual endpoint, preserved the old opening on failure, cleared loading, and allowed another click.
- The local backend has no OpenRouter key. After the explicit configuration guard, the actual UI displays the missing `OPENROUTER_API_KEY` remedy (503); it does not pretend to generate text.
- Separately, an explicitly mocked 20-message API response was consumed through 20 real browser clicks. The textarea displayed all twenty in order, the counter count was zero, and the error count was zero. This proves UI wiring, **not live model generation**.
- The CLI's initial cross-origin mock lacked CORS headers and failed with Network Error. A browser-only same-origin XHR adapter allowed testing the fixture; it and all network routes were removed afterward. No product CORS policy was changed.
- Browser error log was empty. No screenshot or visual review was performed.

Live provider generation remains unverified until the server has a configured OpenRouter key and is restarted. The first request of a batch has model/network latency; only queued suggestions are instant. No keys or runtime logs are included in this report.
