# 0019 — One TikTok caption per post kit, regenerable on demand

- **Status:** accepted
- **Date:** 2026-10-26
- **Anchors:** `backend/ai_service.py` (`generate_post_kit`);
  `backend/server.py` (`regenerate_post_kit`);
  `frontend/src/components/PostKitSection.jsx`;
  `backend/test_post_kit_api.py`

## Context

The frozen post kit shipped three captions per render, forcing the founder
to choose between near-duplicate options at publish time. One render needs
one caption: hook idea in the viewer's words, the app stated plainly, a
short question at the end.

## Decision

- **Return a single `caption`** (under 50 words, clamped to 300 chars)
  instead of a three-entry `captions` array. Hashtags tighten to 4–7 with
  `#AppName` first; `cover_text` and every guard (length clamps, banned
  claims, guarantee language) stay.
- **Old kits still display**: the section falls back to the first of three
  stored captions. The backend passes frozen rows through untouched.
- **Regenerate is explicit**: a button on the section calls
  `POST /generations/{id}/post-kit/regenerate` only on click and replaces
  the saved row. Failure answers loudly and leaves the current copy with
  the error. The Demo + CTA export card shows the inherited copy without
  the button — the kit belongs to the render.

## Consequences

- **Gain:** one paste-ready caption per video; a stale or off-tone kit can
  be rewritten without re-rendering.
- **Cost:** founders with a saved three-caption kit see only the first one
  until they regenerate — no data loss, but a visible narrowing.

## Alternatives considered

- **Keeping three captions.** Rejected: the choice added work at publish
  time for near-duplicate options.
- **Auto-regenerating on every read.** Rejected: the kit is frozen output;
  silent rewrites would break the History audit trail.
