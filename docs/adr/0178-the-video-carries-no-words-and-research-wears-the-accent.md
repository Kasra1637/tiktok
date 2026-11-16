# ADR 0178: The video carries no words, and Research wears the accent

Status: accepted

Refines ADR 0176 (the video born on the steps page) and
ADR 0175 (the composed stage); supersedes ADR 0176's addendum
(the closing line inside the stage) and ADR 0173's mirror for
the Research control only. Kasra's rulings, Nov 16 2026, from
seeing the shipped hero live: the hook text inside the video
is "not relevant", and the light Research button read wrong.

## Context

Kasra reviewed the live hero after ADR 0176 and its addendum
shipped. Two objections, both from the screenshots in front of
him:

1. **The video still carried words he had not asked it to
   keep.** The slot's stage composed the presenter under the
   hook lines ("A year building this app." / "Nobody knew why
   it mattered.") as her caption block, and as the run
   completed the closing line "Your app. Your story." resolved
   over the scene with a "Get the app" beneath it — the end
   beat ADR 0176's addendum had folded in on his earlier yes.
   Shown the finished thing, he ruled the hook text not
   relevant and ordered all three texts out completely, with
   no replacement: the video is the presenter, not a caption.
2. **Page one's Research button rendered white.** ADR 0173
   had mirrored BrandSetup's real button faithfully — the
   secondary Button's slate surface — but on the live page,
   inside the dark phone, that surface read light and wrong
   next to Generate's indigo accent. Kasra ordered the
   mockup's Research restyled to match Generate, so the two
   animation buttons look unified, and asked for its label to
   be punchy: short and strong.

## Decision

- **The slot is presenter-only.** The hook block
  (`.hero-story-hook`, its two lines, the `hs-hook-long` /
  `hs-hook-short` reveal tracks), the closing layer
  (`.hero-story-closing`, its line and CTA, the `hs-closing`
  track) and every rule behind them are deleted from the page
  and the stylesheet — not replaced, not supplemented. This
  supersedes ADR 0176's addendum: the closing line's survival
  inside the stage ends, and the line stands nowhere in the
  mockup. The closing window collapses into the slot's hold:
  the progress bar still completes at 97%, the play badge now
  stays seated on the presenter through the hold instead of
  yielding at 94% to a layer that no longer exists, and the
  loop's last image — presenter, badge, full progress — is
  the frame reduced motion rests on. With the caption block
  gone the presenter centers in the stage and the badge rides
  at the frame's center.
- **The mockup's Research wears Generate's accent
  treatment.** `.hero-story-research` now carries the
  `.btn-bevel-accent` tokens the mockup's Generate already
  wears — the vertical indigo gradient, white/15 border, the
  inset top rim over the indigo glow, rounded-xl, white
  text — so the two animation buttons are one family. The
  Sparkles icon stays (Play belongs to Generate), and ADR
  0175's behavior is unchanged: visible dimmed while the link
  types, waking to full presence for its click. This is a
  deliberate departure from ADR 0173's mirror for this one
  control; Generate still mirrors the real accent button and
  the steps still wear the rail's filled badge. The real
  BrandSetup button is untouched.
- **The mockup's label is "Research my app".** Short, strong,
  same meaning as the real button's words. It appears only in
  the mockup and in the figure's aria-label; the real app's
  "Research app for video" label is untouched.

## Consequences

The phone's story is now wordless at its payoff: type,
research, steps, generate — and the thing itself, a person in
a frame, playing where the button was pressed. ADR 0173's
mirror doctrine carries one named exception, recorded here so
the next treatment change does not "fix" Research back to the
secondary surface Kasra rejected: when the real accent
treatment changes, both mockup buttons follow it; the real
secondary Button no longer steers the mockup's Research. The
pins follow the rulings: the process check asserts the three
texts' absence from the page source and the stylesheet, the
slot's presenter-only DOM and the retired tracks' absence;
the mirror check pins Research's accent tokens and label and
the secondary surface's absence from its rule; the one-clock
list retires `hs-hook-long`, `hs-hook-short` and `hs-closing`;
and the reduced-motion check rests on the assembled page
without the closing layer. The contracts around the change
stand: one 13s CSS clock and no JS timer, the typed field and
its focus light, the four steps under their exact names,
`.hero-shot` shown at every width (ADR 0177), and the
headline, sub-headline, CTAs, checkmark lines and
How-it-works strip untouched.
