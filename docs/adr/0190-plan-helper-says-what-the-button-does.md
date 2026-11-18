# 0190 — The plan helper says what the button does

Status: accepted

## Context

The ready-state plan panel's helper line read "The free plan brings
your hook, script, shots, and demo note here, ready to edit." — a
line Flash compacted a day earlier when the founder delegated the
choice. On the Nov 17 2026 evening call the founder corrected the
choice: the line mainly names what lands in the panel, not what the
button does. His order: remove the text under the "Generate your
plan" button and rewrite it so it explains quickly what the button
does.

## Decision

The line under `plan-generate-button` now reads, in the founder's
exact words:

"Builds your hook, script, shots, and demo note from your profile,
your angle, and your goal."

Nothing else in the panel changes: not the button label, not its
countdown, not the missing-choices subtitle, and the in-flight panel
still carries no line.

One finding shaped the edit: the sentence is a single literal in the
plan-generate panel — it is not a shared constant and there is no
second copy. The plan panel lives inside the merged Review & submit
step (the plan and the render merged there), which is why the same
line was also described as the Review helper when it shipped; the
founder's order and the protection of "the Review one" name the same
single surface. The one smoke pin that named the old string pinned
this panel, and it is updated to pin the new line in the panel and
the old line's absence from the page.

The line is a panel helper (`text-base`, no `data-subtitle`), not a
wizard subtitle, so the subtitles' 55–60 character rule does not
apply to it; the founder's exact wording stands at 92 characters.

## Consequences

The smoke check is renamed to match the rule it now pins ("The plan
helper says what the Generate button does"). Any future helper under
a generate button should say what the button does, not what lands
after it.

Numbering note: 0188 went to the parallel craft-trait delivery and
0189 to the History filter-bar split, so this copy change follows as
0190 to keep the sequence consecutive.
