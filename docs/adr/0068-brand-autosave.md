# 0068 — App Profile form autosaves through the server path

Status: accepted

## Context

The App Profile form holds 20+ fields behind a single manual Save, the
same shape of risk that motivated the Review autosave (ADR 0067): an
unpressed button reads as lost work. Research, refresh and profile
switches all land through `applyProfile`, and editing never changes
approval status server-side, so an autosave can ride the exact manual
path without changing what a save means.

## Decision

Autosave profile edits ~1s after the last change through the same
`updateAppProfile` / `createBrand` call as the manual button (silent: no
form lockdown, status line narrates). The manual Save stays for an
immediate, explicit save. No autosave runs during research, refresh,
approval or a manual save; a nameless form never autosaves (the server
row cannot be created without a name — the manual Save still validates
with a toast). A save that lands mid-flight never clobbers newer
keystrokes, and a changed profile mid-flight drops the stale result.

Alternatives rejected: browser-local draft storage (the render gate
reads the server row, so a local copy would diverge from what Create
Video uses); locking inputs during autosave (interrupts the typing it
follows).

## Consequences

- An edit is saved whether or not the founder presses Save.
- Autosave failures surface in the status line, never as toasts — a
  refused save still names itself, without interrupting typing.
- Anchor: `frontend/src/pages/BrandSetup.jsx:saveProfileRef`.
