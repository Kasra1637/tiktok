# 0040 — History record tucks post copy and plan context behind disclosures

- **Status:** accepted
- **Date:** 2026-10-26
- **Partially supersedes:** 0039 (attached cards, no expand step)
- **Anchors:** `frontend/src/pages/GenerationHistory.jsx` (`history-post-copy-*` and `history-context` disclosures); smoke check "History tucks post copy and plan context behind disclosures"

## Context

0039 killed the expand step: every card mounts its full record, no
interaction cost to reach any action. But the full record is long — frozen
caption block, hashtags, cover text, audience, demo brief — and it all sits
above the votes and the onward actions, so reviewing a render means
scrolling past reference material to reach the parts that decide something.
The fact row already carries identity and results; the record repeats them.

## Decision

- Post copy and plan context start collapsed in native `<details>`,
  summaries naming their contents ("Post copy", "Plan context"). Facts,
  votes, TikTok row, and actions stay fully visible.
- Native disclosures, not a custom accordion: the part-ratings disclosure
  already set the shape (`rounded-xl` hairline border, `text-xs` muted
  summary), so all three share it with no JS open state to manage.
- The frozen-kit contract does not move: same `post-kit` section, same copy
  and regenerate buttons, one click deeper.

## Alternatives rejected

- **Keep the record fully expanded.** Preserves 0039 literally, but the
  votes and actions stay buried under reference text on every card.
- **Bring back a card-level expand step.** Reintroduces the tab/drag/Esc
  machinery 0039 removed to fix the exact complaint the screenshots showed.
- **Custom accordion component.** A second disclosure pattern beside the
  native one the part ratings already use, with state to keep in sync for
  no added behavior.

## Consequences

- Regenerate and the copy buttons cost one click. The collapsed-tile leak
  pin now asserts the retired caption layout stays out, not that the kit
  is absent from the card.
- 0039's "no expand state anywhere" now reads "no card-level expand state":
  disclosure open state lives inside the record, per section, non-exclusive.
