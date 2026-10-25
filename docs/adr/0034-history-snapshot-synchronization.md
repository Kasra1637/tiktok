# 0034 — History owns confirmed record snapshots

- **Status:** accepted
- **Date:** 2026-10-25
- **Partially supersedes:** 0021 (frontend post-kit ownership only)
- **Anchors:** `frontend/src/pages/GenerationHistory.jsx` (`updateRow`, `load`, `setFilter`); `frontend/src/components/PostKitSection.jsx` (`onUpdated`); `frontend/src/components/ComponentThumbs.jsx` (`pendingRef`)

## Context

A regenerated kit was persisted but only the mounted section knew about it.
Closing and reopening a History drawer restored the list's older copy; Details
could also diverge from the drawer. Local filter state duplicated the URL, and
an older request could overwrite a newer filter's results. Rating saves could
race or complete after the rated item changed.

## Decision

- History's list owns confirmed generation snapshots. PostKitSection still owns
  display and regeneration, but optionally reports confirmed copy to the list.
  Drawer and Details consume the same kit; other surfaces need no callback.
- URL search parameters own History filters. Edits preserve the clip anchor;
  same-page navigation and back/forward read that same source.
- Only the current History request may settle rows, errors or loading. Rating
  saves serialize per control and ignore completions for replaced items.

## Consequences

No API contracts, workflow, controls, winner rules or learning weights change.
There is one optional post-kit callback instead of a global cache/event bus or
reloading the list (which would close drawers and interrupt playback). Focused
DOM regressions cover stale successes/failures, same-page navigation, kit
handoffs and rating settlement; API tests reject deceptive TikTok hosts.
