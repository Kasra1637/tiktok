# 0020 — Regenerate reaches the export card; caption must ask; completed-only

- **Status:** accepted
- **Date:** 2026-10-26
- **Anchors:** `frontend/src/demoCta/DemoCtaEditor.jsx` (export card kit);
  `backend/ai_service.py` (`generate_post_kit` question guard);
  `backend/server.py` (`regenerate_post_kit` status gate)
- **Supersedes:** 0019 (partially — the export card had no button, the
  question was prompt-only, any status could regenerate)

## Context

0019 left three holes: the export card — the publish-prep surface — showed
post copy with no way to fix it, the caption's closing question lived only
in the prompt, and the regenerate endpoint accepted renders that never
finished.

## Decision

- **The export card passes its saved row id** (`generationId={saved.id}`).
  The export row inherits the parent's project, so the endpoint resolves
  and rewrites that export's own copy — parent and child can diverge, which
  is correct since each History entry owns its kit.
- **A caption must end with `?`.** Prompt-only structure already failed
  once in spirit; the one enforceable slice is now a loud validation error,
  keeping the fail-loud convention for grounded copy.
- **Only finished renders regenerate** (`completed`, plus `archived`
  which is a finished render in hiding). Anything else answers 409 and
  the stored kit is untouched.

## Consequences

- **Gain:** no dead ends — every surface showing post copy can rewrite it.
- **Cost:** an archived render's kit can still be rewritten; archiving was
  never a freeze, only a filter.

## Alternatives considered

- **Regenerating the parent from the export card.** Rejected: the card
  displays the child's copy, so rewriting the parent would leave the
  displayed text stale until refetch.
- **Completed-only, excluding archived.** Rejected: archived rows are
  finished renders whose kits remain visible in History.
