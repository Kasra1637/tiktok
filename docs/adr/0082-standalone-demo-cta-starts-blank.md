# 0082 — Standalone Demo + CTA starts blank instead of resuming a draft

- **Status:** accepted
- **Date:** 2026-11-01
- **Anchors:** `frontend/src/demoCta/DemoCtaEditor.jsx` (draft-restore effect gated on `generation?.id || sourceUrl`); smoke check “the standalone Demo + CTA starts blank even with a stored draft”
- **Supersedes:** 0058 (partially — “drafts keep the value they stored” no longer applies to the standalone entry)

## Context

Overlays were fixed to start off (0058) and the preview to park on load, so a
freshly added clip opens as footage alone. But the standalone route
(`/demo-cta`) reapplied the previous session's stored draft on every visit:
the old footage reappeared in the preview with its overlay switches, so the
founder was greeted by a video they did not upload and text they did not turn
on. The draft restore could not tell “my work in progress” from a stale
session, and on a page whose job is “upload a clip” the stale read always
wins the surprise.

## Decision

- The standalone entry (`!generation?.id && !sourceUrl`) never applies a
  stored draft: the preview opens on its empty frame, every overlay stays
  off, and the page waits for an upload.
- The stored standalone draft is left alone, never deleted. The first edit of
  the new session overwrites it through the normal edit-session save, so no
  explicit clearing step can strand the founder.
- A pinned workspace (`/demo-cta/:id`) keeps restoring its draft: that draft
  belongs to the render on screen, and resume is the point of opening it.
- Draft-recovery failure still blocks editing with a retry, now exercised
  through the pinned path, which is the only path that reads.

## Alternatives rejected

- **A “Resume last session” button.** Explicit resume is honest, but it is
  a new affordance for work the founder did not ask to keep. Blank-by-default
  with silent overwrite on first edit needs no new UI and cannot be clicked
  past by accident.
- **Deleting the stale draft on entry.** Deletion is irreversible; skipping
  the apply keeps the bytes until the founder's next edit replaces them.

## Consequences

- Returning to `/demo-cta` never shows another session's footage or copy.
  Uploading and editing works exactly as before, including undo/redo within
  the visit.
- Reloading a pinned render still restores its footage, overlay switches and
  copy, and undo/redo still spans the reload there.
- 0058's “drafts keep the value they stored” now holds only for pinned
  workspaces; the smoke suite pins the standalone blank start and the pinned
  resume separately, so either regressing fails the gate.
