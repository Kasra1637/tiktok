# ADR 0367: Create's steps one and two carry no standing copy, and the What will render preview is removed whole

## Status

Accepted, Nov 26 2026 — Kasra's spread order in the main
chat, with two orders folded into the same round on his
voice call: the whole "What will render" preview goes, and
the helper line under the Generate tailored templates
button goes.

## Decision

**Step 1.** "Only approved App Profiles can make a video
in this studio." is removed. The unapproved-profiles
panel's lead line takes the shared eyebrow face — on BOTH
pages' twin panels (Create Step 1 and HookSnap's Choose
an app card), converted in the one round so the twins
cannot drift. The instruction line naming the remedy and
every state row in the panels stay.

**Step 2.** `ANGLES_CTA_COPY` and `GOALS_CTA_COPY` are
removed with their render blocks — the gate buttons name
their own actions, and the lines only restated them. The
goal header keeps only its state sentence (how many
suggestions stand for the picked angle, or that they are
ready when clicked); its descriptive second sentence
("The angle shapes this video — the goal shapes the
campaign it serves.") is removed. No pairs stand in Step
2: Angle and Goal are dependent, not comparable. Every
instruction and state line the audit named stays — the
gap-naming lines, the fixed-camera staging note, the
refreshed-age line, the regeneration notices.

**The "What will render" preview is removed whole**
(Kasra's folding order, superseding this round's first
treatment of it, which would have converted its title and
removed only its subtitle). ADR 0363's record counted the
preview among the direction section's remaining state
elements; this order removes the block outright —
heading, the "Scene: …" and "Voice: …" readouts, and the
subtitle ("Saved here first; the plan and render read
these words.") alike. The removal is display only, proven
from the code: the block rendered readouts of the draft's
saved direction values with no handler, effect or write
of its own, so the save, the plan and the render behave
exactly as before — and the direction checks' save and
reload assertions stand green over the same tree. This
finishes the direction section ADR 0362 began: title, two
pairs, their headings, buttons, separators, and the
conditional state elements (the plan default, the saved-
place warnings, the refresh error) are all that stand.

**The tailoring helper line is removed on Kasra's
explicit order, despite its classification.** The line
under the Generate tailored templates button ("Tailoring
runs only when you click it — switching goals never
starts it.") was classed instruction/keep by the audit
and by this round's original brief. Kasra ordered this
specific line out by name; his direct order wins, and the
override is recorded here rather than silently absorbed.
Display only: tailoring still runs solely from that
button's click, and switching goals still never starts
it — the behavior the line described is unchanged, and
the click-to-generate checks that pin it stand green.

## Checks

Changed, named here per the house rule:

- The angle-gate check's CTA-copy assertion is flipped to
  absence (the same flip the ADR 0362 round made for its
  removed lines).
- "Review without a goal asks for it instead of spinning
  forever": its `goals-cta-copy` presence assertion
  becomes an absence pin — the Review goal gate was the
  copy's last home. Its subjects (no plan without a goal,
  the picker, the Generate click starting the plan) are
  unchanged.
- "goal options wait until the founder picks an audience
  angle": the step's explanation now rests on the goal
  header's "(required)" label alone; the CTA-copy half of
  its assertion is flipped to absence. The waits-for-angle
  marker contract is unchanged.
- "every gate leads with its ask above its hint, spaced
  the same": the angle gate records its spacing WITHOUT a
  hint under its button — it has none now. The other
  gates' hint requirements and the shared-spacing subject
  are unchanged.
- "Review and dense panels put the primary action above
  its guidance copy": the angle gate's ordering assertion
  becomes an absence pin for the removed copy; the other
  panels' ordering assertions are unchanged.
- "delivery comes from the video, never from a direction
  control": its live-preview readout assertion ("Voice:
  Calm.") is replaced by an absence pin for the removed
  preview. Its subject — no delivery control exists
  anywhere; delivery comes from the video — is unchanged,
  and the scene-label assertions beside it stand.

## Alternatives considered

Keeping the preview with only its subtitle removed (the
round's first treatment): Kasra's screenshot settled it —
the block itself was the clutter he named, not its
subtitle. Keeping the tailoring line for its honesty
value: it described a real behavior, but Kasra weighed
that and ordered it out by name; the behavior survives
the line.
