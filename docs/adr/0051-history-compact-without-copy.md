# 0051 — Compact History cards without copy or context

- **Status:** accepted
- **Date:** 2026-10-27
- **Partially supersedes:** 0039 (single-column cards and always-visible records for renders without copy or context)
- **Anchors:** `frontend/src/pages/GenerationHistory.jsx` (`history-compact-grid`); `frontend/src/index.css` (`.history-card-compact`)

## Context

Renders with no post copy or plan context leave a disproportionately tall video rail in the attached-card layout. They need a denser view without separating the clip from its record or hiding its actions.

## Decision

Only the without-copy filter uses compact cards: fixed-height, contained previews and a responsive grid with up to two cards per row. The media and record sit side by side only when the card itself has enough room; otherwise they stack. Cards stretch within each grid row, but their content can grow without clipping. On mobile, secondary results and onward actions start collapsed under a labeled disclosure; video, Download, Delete, errors, and available repair actions stay visible. A deep link to an awaiting TikTok field opens the disclosure. Copy/context cards keep the existing layout.

## Alternatives and consequences

A fixed card height could clip longer metadata, repair messages, or controls. A two-column grid at every width would make those controls cramped. The responsive grid preserves the attached record and repair actions, while unusually long content can still make its row taller. On mobile the disclosure adds one interaction to reach feedback, in exchange for a shorter list.
