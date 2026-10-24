# 0026 — Opening text uses app-grounded batches of twenty

Status: accepted

## Context

Surprise me rotated persisted presets by index, so duplicate messages could leave the displayed opening unchanged. The user requested twenty app-specific outputs and no copy counter, limited to opening text.

## Decision

- The editor owns the displayed opening. `useOpeningMessages` owns an ephemeral queue of twenty unseen suggestions and request status; overlay taste owns styling and the unchanged CTA presets, not opening copy.
- One explicit click generates twenty distinct messages through the existing OpenRouter text service. The first appears when the response arrives; subsequent clicks consume the queue immediately without another API request. Exhausting it requests a fresh batch and excludes the previous batch.
- A routed render supplies its app. Attaching History switches opening context to that row's app; restoring the original source restores its context. Standalone uploads use the existing active-app policy. The server resolves only caller-owned approved profiles.
- Duplicate, empty, oversized, banned-claim and guarantee outputs fail visibly rather than falling back to unrelated saved messages. Pending clicks are deduplicated; stale app responses and edits made during generation cannot be overwritten.
- No counter or additional generation button is exposed. CTA behavior is unchanged.

Anchors: `frontend/src/demoCta/useOpeningMessages.js:6`, `frontend/src/demoCta/DemoCtaEditor.jsx:531`, `backend/ai_service.py:2182`, `backend/server.py` (`generate_opening_messages`).

## Alternatives rejected

Twenty fixed presets cannot supply app-specific fresh copy. One provider request per click adds unnecessary latency. Reusing the styling preference store carries old app copy into another app and admits duplicate slots.

## Consequences

The first suggestion in each batch requires network/model latency, narrated by the button; the remaining suggestions appear immediately. Suggestions do not persist on reload. Missing provider configuration is a visible setup error, never a silent unchanged message.
