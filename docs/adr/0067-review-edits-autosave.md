# 0067 — Review edits autosave through the server path

Status: accepted

## Context

Review-step edits waited on an explicit Save press, so an unpressed
button read as lost work. The Demo + CTA editor already saves shortly
after every change — but into browser-local draft storage, which is the
wrong destination for claim-checked plan text.

## Decision

Autosave Review edits ~1s after the last change through the exact same
`updateStudioProject` + claim-check + ready re-mark path as the manual
button (silent: no step lockdown, status line narrates). The manual Save
button stays for an immediate, explicit save. No autosave runs during a
plan flight or a manual save.

Alternatives rejected: browser-local draft autosave (would diverge from
the claim-checked server truth the render gate reads); disabling inputs
during autosave (interrupts the typing it follows); longer debounce
(loses work on fast navigate-aways).

## Consequences

- An edit is saved whether or not the founder presses Save; the
  "Save your edits before rendering" hint now covers only the ~1s window.
- Autosave failures surface in the same error banner as manual saves —
  a refused claim still names itself.
- Anchor: `frontend/src/pages/CreateVideo.jsx:saveEditsRef`.
