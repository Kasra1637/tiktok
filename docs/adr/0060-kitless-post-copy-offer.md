# 0060 — Kit-less finished renders offer post-copy generation in History

- **Status:** accepted
- **Date:** 2026-10-30
- **Anchors:** `frontend/src/pages/GenerationHistory.jsx` (`history-generate-post-copy-*`); smoke checks "a finished render without post copy offers to generate it", "a failed post-copy generation names the next step"

## Context

Post copy is written once, at completion, on a best-effort path: a kit
failure leaves `post_kit` NULL rather than failing the render. History
renders the Post copy section only around an existing kit, and the only
regenerate control lived inside that section — so a finished render whose
kit was never written showed nothing and offered nothing. The founder's
last video hit exactly this: a completed render with no post copy and no
way to get one.

## Decision

- A completed or archived render with no `post_kit` shows a "Generate post
  copy" box in its History record, calling the existing regenerate
  endpoint and opening the Post copy panel on the fresh kit.
- A refusal names the next step (e.g. render material gone → draft gone)
  instead of dying silently; the stored row is untouched on failure.
- Kit-less rows are found under the without-copy filter, which is where a
  render missing its copy already lives.

## Alternatives rejected

- **Auto-generate on History view.** A side-effectful GET that spends model
  money without a click is the wrong default; generation stays explicit.
- **Backfill at completion time with retries.** The completion hook stays
  best-effort — a render must never fail because its caption did.

## Consequences

- No finished render is permanently copy-less: one click writes the kit.
- The smoke suite pins both the offer and the failure message, so a future
  removal of the box fails the gate.
