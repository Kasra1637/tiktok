# ADR 0176: The video is born on the steps page

Status: accepted

Refines ADR 0168 (the two-page hero) and ADR 0175 (the typing
restored, the video stage a composed frame); supersedes the
third-stage shape those records and ADR 0172 gave the loop's
finish — the full-screen video stage and its end card. Kasra's
ruling, Nov 16 2026, from his screenshot of page two: "make
this last step. Don't show anything after this. There is no
other step after this."

## Context

Page two of the hero phone carried the four creation steps in
a card at the top and the Generate button at the bottom, with
a long empty center between them — the same dead space Kasra
had already ruled against on page one. The finished video
played afterwards as a third stage that took the whole screen,
closing on the end card ("Your app. Your story." over a "Get
the app" CTA). Shown that page, Kasra pointed at the empty
center: the video the button generates should be generated
there, in that space — and that step should be the last one.
The hybrid offered in reply (born in the slot, then expanding
to fill the screen for the payoff) was explicitly refused:
no expansion, no third stage, nothing after the video.

## Decision

- **Page two is the final page.** The video stage moves into
  page two's DOM between the steps card and the Generate
  button and flexes to fill that center slot. After Generate's
  click (press + ripple, unchanged), the stage materializes
  there — fade and scale in on a new `hs-stage` track — and
  plays: the ADR 0175 composition carried over whole (the
  stage surface with its indigo wash, the filled presenter in
  her scene as the subject, the hook lines as the caption
  block, the play badge seated on the presenter — riding lower
  in the slot's shorter frame — and the progress bar, now
  riding the stage's own top edge, filling across the video's
  run). The steps stay checked above it; the Generate button
  stays in place below it and settles to a quieter presence
  (opacity 0.8 on its track) once its video exists — still
  visible, still wearing the accent treatment.
- **The third stage and the end card are removed, not
  supplemented.** The `.hero-story-video` full-screen wrapper,
  the `.hero-story-endcard` card with its icon tile, closing
  line and CTA, and their `hs-video` / `hs-endcard` tracks are
  deleted from the page, the stylesheet and the pins. The loop
  holds on the assembled page two — steps, playing video,
  button — and fades only at its last beat for the restart.
- **The clock stays 13s.** Page one keeps its ADR 0175 windows
  entire (typing 4%→18%, Research waking at 24%, clicked at
  27%, page one out at 36%). Page two enters at 40%; the steps
  check off 50%→62% and Generate is clicked at 69%, as before;
  the video materializes 71%→79% in the slot, the hook lines
  reveal across 78%→89%, the play badge pops at 84% and yields
  at 94% now that the video is playing (it no longer yields to
  an end card), the progress fills 80%→97%, and the assembled
  page holds to 97% before the restart fade.
- **Reduced motion rests on the assembled page two.** The
  base styles now describe that page standing: page two's base
  is visible, with its steps, stage and button in their
  composed states (the check dash lives only in keyframes, so
  every check stands drawn), and page one stays hidden at
  base.

## Consequences

The story the phone tells is now two pages and a birth: type,
research, steps, generate — and the thing itself appears where
the button was pressed, in the space the visitor was already
looking at. The end card's closing line leaves the hero with
the card; the landing's own final CTA section below still
carries the page's close. The contracts around the change
stand: ADR 0173's mirror (Research's Sparkles and secondary
surface, Generate's Play and accent bevel, the rail's filled
check badges), the presenter figure and her scene, `.hero-shot`
hidden below 1024px (ADR 0158), one CSS clock and no JS timer,
and the headline, sub-headline, CTAs, checkmark lines and
How-it-works strip untouched. The pins follow the ruling: the
stage is asserted inside page two in DOM order between the
steps and the button with the button last on the page, the
retired wrapper and end card are asserted absent from the DOM,
the source and the stylesheet, the one-clock list trades
`hs-video`/`hs-endcard` for `hs-stage`, and the reduced-motion
check rests on the assembled page by name.

## Addendum — the closing line returns inside the stage (Nov 16 2026)

When this decision was reported, the founder was told the end
card would go with the third stage, and was offered the
choice: if he wanted "Your app. Your story." to survive
inside the video slot itself, it would be folded in before
the push. He answered "Okay. Do it."

- **The line returns as the video's own end beat.** A closing
  layer inside `.hero-story-stage` carries the line over the
  presenter scene: held back while the video plays, it fades
  and rises in on a new `hs-closing` track across the progress
  bar's last stretch (hidden to 89%, resolved at 95%, held
  through the restart fade), so the video ends the way real
  videos end — on its own end card — and still nothing
  follows it: no stage, no page, no beat after the video.
- **"Get the app" returns with it**, wearing the small accent
  Button treatment (ADR 0173) the retired end card's CTA wore
  — at slot scale the line and the small pill sit honestly in
  the stage's frame. The retired card's icon tile does not
  return: at slot scale it read as card furniture, not a
  video's close.
- **Reduced motion rests on the close.** The closing layer's
  base state is resolved, so the assembled page two that
  reduced motion stands on carries the finished video's end
  card standing in the slot — the resting contract ADR 0175
  kept, when the base frame was the finished video with its
  end card standing under it.
- The presenter is never shrunk to make room: she stands at
  subject size through the whole playing beat, and the
  closing layer gives way over her picture only as the run
  completes, as an end card does.
