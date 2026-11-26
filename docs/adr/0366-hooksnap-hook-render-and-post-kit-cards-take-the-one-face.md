# ADR 0366: HookSnap's hook, render and post kit cards take the one face

## Status

Accepted, Nov 26 2026 — Kasra's spread order in the main
chat: the ADR 0360–0363 pattern (pairs for comparable
pick-groups, the one GroupLabel eyebrow face with a unique
icon per group, no standing descriptive lines) carried
through the rest of the HookSnap page.

## Decision

**The hook card.** Tone and Shape stand side by side in a
`.section-pair`; Focus stays full-width above the pair —
a single wide control never splits. Removed: the card
subtitle ("One line from your app and your direction, five
seconds."), the line under Focus, the line under Shape,
and the spoken-line subtitle inside the shared
HookLineEditor ("The opening line spoken in your generated
… clip.") — that editor is shared, so its subtitle leaves
both pages from the one seat; its label takes the eyebrow
face with AudioLines here and on Create's Review alike
(ADR 0368 records the Review side). The Focus pop-up's
header takes the eyebrow face with the Focus icon — the
pop-up's behavior is untouched, face only. "Caption
preview" gains the Captions icon. The picks-stale note,
the focus-stale note and every error stay: they are state,
not description. The Tone/Shape "App's choice" pills stand
exactly as ADR 0247 left them — held out of this round by
Kasra's own list.

**The render card (headings only).** Its subtitle ("One
press renders the finished hook at its picked length.")
is removed. The "Resolution" label in BOTH render panels
— HookSnap's `HookRenderPanel` and Create's
`GenerationPanel`, duplicated markup in two files —
becomes GroupLabel with the Monitor icon in both. The
resolution pairs' own default-lit face is NOT touched:
it awaits Kasra's ruling, held out of this round.

**Demo + CTA and Post kit cards.** Both card subtitles
are removed, and the Post kit card's standing line ("The
post kit is written when the hook finishes rendering…")
with them. PostKitSection's heading gains an icon through
a new `headingIcon` prop: HookSnap passes Share2, its
card's own glyph; History — which shares the component —
and every other caller pass nothing and render exactly as
before. Every state line in both cards stays: the status
line, the caption count, the silent-render text-to-speech
note inside the kit.

## Checks

Changed, named here per the house rule:

- The ADR 0351 source pin asserted HookCta.jsx CONTAINS
  the five-seconds subtitle. It now asserts its absence.
  ADR 0351's rule itself (always five seconds, no length
  pick, the server pins it) is untouched — only the
  subtitle that stated it is gone.
- "a written hook carries no length pick, and the render
  submits at five seconds": its subtitle assertion becomes
  an absence pin for the removed line; its real subjects —
  no length control, the render submits at five seconds —
  are unchanged.

New in this round: the hook-card check (the pair, Focus
above it, the four removed lines, the pop-up header's
face, the caption preview's icon) and the source check
pinning both Resolution labels, the prop-gated heading
icon, and the removed card lines.

## Alternatives considered

Splitting Focus into the pair as a third cell, or pairing
it with Tone: Focus is one wide sentence-picker, and a
half-width seat would cramp the very lines it exists to
let the founder read. It stays full-width, as the audit
specified.
