# 0222 — The pipeline bodies share one length

Status: accepted

## Context

On Nov 19 2026 Kasra read the landing page's pipeline section —
the three stacked blocks under "You direct. HookForge produces."
(`PIPELINE_BLOCKS` in `frontend/src/pages/Landing.jsx`) — and ruled
that the first two blocks' body text must match the third: their
lengths should be the length of "Nothing ships without your yes."

Measured, the three bodies were not one set: "The opening, written
to hold" ran 244 chars, "Your footage, centre stage" ran 296, and
"Nothing ships without your yes" ran 231. The longer bodies made
the section read unevenly — the same complaint that put the six
feature cards at a uniform 160 chars under ADR 0156.

## Decision

1. **The third block sets the length, and stands unchanged.** Its
   body stays byte-identical at 231 chars; it is the anchor, not a
   third text to rewrite.
2. **The first two bodies are trimmed to exactly 231 chars each,**
   in Kasra's approved wording, meanings unchanged. The opening
   block keeps its beats — one AI-generated clip, the hook built to
   stop the scroll, the story that earns the click, the demo and
   closing message never generated footage, recorded by the founder
   from the separate brief — in fewer words. The footage block
   keeps its beats — a base clip styled from the founder's own
   recording or a Hook + Story, a second clip added, Real Video
   laying a recording in a phone over the base, each clip's look,
   framing, zoom, hook text and end card set, one TikTok MP4
   exported — likewise compressed, never re-scoped.
3. **The render smoke pins the shared length.** A new check,
   "Landing pipeline bodies share one length," pins the three
   titles and asserts each body is exactly 231 chars, in the same
   style as the ADR 0156 feature-card pin beside it, so a future
   copy edit cannot silently drift the three apart again. The pin
   was written first and watched failing on the old copy (244
   chars under the opening title) before the trim landed. The
   older boundary-disclosure check beside it, which quotes the
   pipeline bodies to prove the generated/real footage boundary
   is stated, now quotes the trimmed wording — the boundary it
   guards ("never generated footage", the demo recorded by the
   founder) is the same statement in the new words.

## Consequences

The pipeline section now reads as one set of three equal-weight
blocks, the way the feature grid above it already does. No layout,
title, kicker or icon changes; no other landing copy moves. A
future edit to any pipeline body must hold 231 chars or change
all three together under a new ruling — the smoke check fails
otherwise, by design.
