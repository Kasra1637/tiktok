# ADR 0173: The hero mockup mirrors the app's real UI

Status: accepted

Refines ADR 0168/0172 (the two-page hero). Kasra's order, recorded
in the founder's notes, Nov 16 2026: "The buttons and every font,
text, layout and UI element inside the phone mockup must match
the app's real UI exactly — button labels are the app's own CTA
texts — so the animation looks unified with the app."

## Context

The audit found the phone had drifted from the studio it
advertises — in two places it had the real app's iconography
exactly swapped:

- **Research wore a Search icon and an indigo pill.** BrandSetup's
  real "Research app for video" is the `secondary` Button
  (`frontend/src/pages/BrandSetup.jsx`): a Sparkles icon, the
  slate `--secondary` surface at 70%, a hairline border, the
  neutral bevel's top rim, rounded-xl.
- **Generate wore a Sparkles icon and a horizontal-gradient
  pill.** The render panel's real "Generate the video"
  (`frontend/src/components/GenerationPanel.jsx`) is the `accent`
  Button: a Play icon — Play is Generate's signature (ADR 0144) —
  over `.btn-bevel-accent`'s vertical 180deg gradient
  (`--brand-indigo` → `--brand-indigo-dark`), a white/15 border,
  the bevel's top rim and the indigo glow, rounded-xl.
- **A done step wore a bare indigo check glyph.** The wizard
  progress rail's done segment carries a white Check inside a
  filled brand-indigo circle badge (h-5 w-5), its label
  text-xs semibold in foreground/85; the mockup's rows had the
  size and colour but weight 500 and no badge.
- **The end card's "Get the app" pill** wore the same horizontal
  gradient in a 999px pill at 12.5px — no button in the app is
  shaped or painted that way; the small accent Button (size sm)
  is its closest real analogue.

The words were already the app's own — "Research app for video",
"Generate the video", and the four step names match
`STEPS` in CreateVideo exactly — so no label changed. The fonts
already matched too: phone body text inherits the app's Figtree
stack and the display lines carry the Space Grotesk display
stack. The button text stays 13px against the real 14px: at the
real size the research label overflows the phone's measure —
the mockup is a scale model, and its type scale stays
proportional (the step rows, whose text is already the rail's
real text-xs, carry the badge at the rail's real size).

## Decision

- **The mockup mirrors the real UI.** `.hero-story-research`
  wears the secondary Button's treatment (slate surface,
  hairline border, neutral rim, rounded-xl, Sparkles);
  `.hero-story-generate` wears the accent Button's treatment
  (vertical bevel gradient, white/15 border, top rim over the
  indigo glow, rounded-xl, Play); both take the real buttons'
  gap-2. A done step's check sits in `.hero-story-step-badge`,
  the rail's filled indigo badge with a white check, and the
  rows take the rail label's semibold weight. The end card's
  CTA wears the small accent treatment (rounded-lg, text-xs,
  px-4 py-1.5, the bevel's gradient, rim and border), and its
  icon tile takes the bevel's vertical gradient and rim.
- **Standing rule:** when a real treatment the mockup mirrors
  changes — a CTA's surface, icon, radius or the rail's done
  marker — the mockup follows in the same change. The mirror is
  pinned, not remembered: a smoke check ("the hero mockup
  mirrors the app's real controls") asserts the icons the two
  controls render, the badge around each step's check, and the
  shared treatment tokens in index.css (the bevel's gradient
  string, rounded-xl, the secondary surface, the rim), so a
  drift back to pills and horizontal gradients fails the gate.
- **Unchanged:** the animation's structure, beats and 13s
  timing (ADR 0172), the words, the reduced-motion resting
  frame (the same assembled end state, restyled), `.hero-shot`
  below 1024px, and everything outside the phone. The video's
  play badge is not app chrome — it is the finished video's own
  overlay — and keeps its circular form; its solid indigo and
  white glyph already sit in the accent family.

## Consequences

The landing visitor now rehearses the studio's actual controls:
the same Sparkles that researches in the app, the same Play that
generates, the same badge that marks a step done. The cost is a
standing coupling — a future CTA redesign is not done until the
hero agrees — which is the founder's stated intent: one product,
one face, inside the phone and out.
