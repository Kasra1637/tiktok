# 0094 — Render & result: actions stay open, explanations collapse

- **Status:** accepted
- **Date:** 2026-11-04
- **Anchors:** `frontend/src/components/HookContinuityPanel.jsx` (`CollapsedGroup`,
  `summaryLine`, `StrategyBlock`'s `hideTitle`, the four disclosure testids),
  `frontend/scripts/check-render-smoke.cjs` (checks "the strategy panel keeps
  the actionable parts open and collapses the explanations" and "the scene
  block points at the Location editor for its place")
- **Shapes:** the information hierarchy of the Review & submit render half.
  GenerationPanel (Location editor, rating, render controls) is unchanged.

## Context

The strategy review had grown into a wall of prose above the two sections the
founder actually acts on: hook concept, the strategy summary, three outcome
rows, and a full scene spec-sheet of up to thirteen rows — all open by default,
all before the spoken lines and the render button. The scene rows still matter
(they lock the render), but reading every one of them before every render is
not an action; it is a chore. Hiding them entirely would repeat the older
mistake of making governing fields invisible.

## Decision

- **Keep open** — the parts people act on: the Location editor, the two
  sections with their spoken lines and "What they do", the Good / Not good
  rating, and the render controls including the Rebuild button when it is
  needed.
- **Collapse by default** — three explanation groups (Hook concept, Why this
  works for this app, What the viewer ends up with) and one "Scene details"
  group holding camera angle, framing, wardrobe, props, colour palette,
  lighting and movement. All use the shared `Disclosure`; nothing is deleted.
- **One-line digest on every closed group** — the first sentence of the prose
  for the explanations, and a values digest for the scene:
  "Footbridge at dusk, handheld selfie, olive jacket" (place, camera setup,
  wardrobe or lighting). `summaryLine` case-normalises and cuts at a word
  boundary, never mid-thought.
- A group with no values renders nothing at all, so an older strategy that
  predates the outcome fields does not show an empty "What the viewer ends up
  with" group.
- The scene helper text still names the real editor ("Render your Hook + Story
  below") from ADR 0092; it moves inside the group rather than sitting above
  the fold.

## Alternatives rejected

- **Remove the explanation blocks.** They govern the prompt and the founder
  still needs them to catch a wrong strategy (ADR 0092 made them consistent;
  hiding them would undo that review step).
- **Collapse the two sections too.** Those are the words and actions the
  founder approves before paying; hiding them would be the chore this change
  removes, not the cure.
- **A "show details" button per row.** Thirteen toggles are worse than one
  group with one digest.

## Consequences

- The default read of the page is: Location, two sections, rating, render —
  with four closed groups carrying their own one-line clues.
- The smoke suite pins the closed state, the non-empty digests and that the
  two sections are never inside a closed group, so a future "make everything
  visible again" change fails the gate.
- `StrategyBlock` gains `hideTitle`: inside a disclosure the group title is
  the disclosure's summary, so the rows are not labelled twice.
