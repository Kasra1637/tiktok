# 0010 — No warm fills on buttons: coral and red move out of the surface

- **Status:** accepted
- **Date:** 2026-10-16
- **Anchors:** `frontend/src/components/ui/button.jsx:22` (destructive),
  `:38` (brand), `frontend/src/index.css:895` (`.btn-bevel-brand`),
  `frontend/src/components/Chip.jsx:34` (pressed tone)

## Context

The palette reserved `--brand-coral` (`#FE2C55`) for "this performs the action",
so a filled coral button was the loudest surface on every screen it appeared
on: Landing hero and final CTA, wizard commits, thumbs verdicts, the Demo + CTA
studio, History's onward action. The same red family also filled
`variant="destructive"`, which put the one button in the app whose action cannot
be undone in the same visual weight class as a primary.

Two things had drifted underneath that rule. Most commits had already been
unified onto the indigo accent (`8c5e3435`, "unify all buttons on the Save
profile accent variant"), so coral was no longer the primary CTA language —
it survived as an inconsistent handful of call sites. And on a near-black
studio palette, a saturated red fill is the single brightest object in the
viewport, which is the opposite of what a commit button has to be when the
content being committed (a video) is what the eye should land on.

## Decision

Buttons do not paint coral or red.

- `variant="brand"` is the **dark selected** surface: the slate fill family
  shared with `secondary`, plus the indigo hairline that already marks selection
  everywhere else. Its call sites mean "this one is chosen" — an active thumb
  verdict, the onward Demo + CTA — which a second CTA colour never expressed.
- `.btn-bevel-brand` keeps its name (call sites and the check suite reference
  it) and paints the dark studio gradient instead of the coral one. No brand
  glow on it.
- `variant="destructive"` is a **dark** surface with the red kept where it
  carries meaning: the label, the icon and the hover border/fill tint.
- `Chip`'s `tone="coral"` option is deleted — the pressed pill is the indigo
  accent, and no call site ever asked for coral.
- `accent` / `default` (indigo, `.btn-bevel-accent`, `--glow-indigo`) is the
  button that acts. Indigo is now the only colour a filled button wears.

Coral is untouched as a brand colour: badges (`--coral-12` / `--coral-25`),
the landing capability accents, decorative overlays and `--brand-coral` itself
all stay, because those are not buttons.

## Alternatives rejected

- **Coral becomes indigo everywhere.** It reads as a rename rather than a
  decision: the "selected" call sites would then wear the same fill as the
  acting button, and `brand` and `accent` would be one variant with two names.
- **Keep coral, soften it to a dark red.** Still a warm fill, still the
  brightest object on the screen, and it makes every future "make it pop" pass
  reach for the same lever.
- **Dark fill everywhere, including `accent`.** The app would lose the one
  signal that says which button a screen commits to; a page of identical slate
  buttons is exactly the ambiguity the original palette split was protecting
  against.

## Consequences

- A red-filled `Button` can no longer be rendered by any variant, and the smoke
  suite asserts it: every variant's class string (and `.btn-bevel-brand` and
  `Chip`) is checked for coral and for an unprefixed `bg-destructive`.
- Destructive actions are quieter at rest. The affordance moves to the label,
  the icon and the hover tint, which is enough for the delete controls the app
  actually ships (all of which were already dark buttons with a red hover), but
  it is a real loss of at-a-glance weight.
- `--glow-coral`, `.glow-coral` and the `--coral-*` tints remain defined and are
  used only by non-button surfaces. If a badge is later removed the token can
  follow; nothing in the check suite requires them.
- `--destructive` keeps its value and its non-button uses: alert borders and
  fills, badges, error text and the toast's destructive variant are unchanged.
