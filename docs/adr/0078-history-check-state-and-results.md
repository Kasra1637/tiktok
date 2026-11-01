# 0078 — History names automatic-check state and exposes results directly

Status: accepted

Partially supersedes 0062: errors no longer stop invisibly; bounds and manual checks remain.

## Context

History stopped polling without saying why, could overlap a slow request, and discarded successful updates whenever another row's request rejected. Compact cards required finding the secondary drawer before recording results.

## Decision

Track attempts and active/paused/error state per awaiting row. Each row has at most one request in flight, at most twenty attempts per continuous awaiting membership, and its own failure state. A 429 remains retryable within that bound. Merge fulfilled results independently of rejected siblings. Clear timers on cleanup and ignore results after cancellation. A stopped browser check never marks the provider job failed.

Show row-level status and keep Check again; the existing single attention banner remains. Compact playable cards get Record results, opening/focusing the existing posted-link or views input. Keep winner semantics, results state ownership, and sorting unchanged.

## Alternatives and consequences

Infinite polling wastes requests for orphaned jobs. A page-wide failure state incorrectly describes successful rows. Calling every low-view clip a loser would invent a performance verdict. Poll states are browser feedback, not saved provider statuses or a guarantee of successful durable saving.

Anchors: `frontend/src/pages/historyPolling.js`; `frontend/src/pages/historyPolling.test.js`; `frontend/src/pages/GenerationHistory.jsx:openResults`; render check `History polling feedback and compact results access are actionable`.
