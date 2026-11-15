# ADR 0157: The hero headline — one animated gradient, Kasra's dictated line

Status: accepted

Supersedes ADR 0155's headline copy and the two-span headline
treatment it kept (white shine over the first span, the brand
gradient only over "in minutes.").

## Context

Kasra, on a voice call on Nov 15 2026, looked at the live hero and
pointed at the split: the top portion of the headline read white
while the rest did not share the treatment. His calls, in order:
the whole headline should have the same design and feel, not just
the top portion; whatever is on the top — the shine, the shadow —
should happen to the rest; the brand gradient that "in minutes."
carries should run across the whole headline; and that gradient
should animate, in a looping formation.

On the wording, he ruled that "a tailored TikTok" does not parse —
you have to say TikTok video or something else — and then chose
something else: drop the word TikTok entirely and dictate the
replacement line himself, casing included. Every word's first
letter is lowercase, except the T of "Turn" and the S of "Store".

He also asked for the sub-headline about 20 percent shorter, with
the same definition and meaning kept intact.

## Decision

The headline reads, exactly as dictated:

"Turn your app Store link into a tailored videos, in minutes."

One span carries one treatment, `.text-gradient-headline`: the
brand gradient (indigo → pale indigo → red → pale indigo →
indigo) clipped to the text across the whole line, over a soft
indigo drop shadow that now sits under every word alike — the
shadow detail was left to Flash's judgment on the call. The
gradient animates in a seamless loop: the stop list ends where it
begins, the background is sized 200%, and the position runs one
full tile per 9-second cycle. The animation applies only under
`prefers-reduced-motion: no-preference`; reduced motion leaves
the gradient static. The white-shine class (`.text-shine`) is
retired with the split it existed for.

The sub-headline tightens from 171 to 143 characters with all
four meaning beats kept — no filming, no editing, no blank page;
facts become a hook, script, and finished video; for your app
alone; learning from every video you judge:

"No filming, no editing, no blank page. Facts become a hook, script, and finished video for your app alone, learning from every video you judge."

The tightening lands at about a sixth rather than the full fifth
Kasra asked for: the last stretch to 20 percent would have cost
a meaning beat (the "finished" in finished video, or the "alone"
in for your app alone), and his meaning constraint governed.

## Consequences

The smoke hero check pins the dictated headline (casing
included), the single animated-gradient treatment on the H1 —
neither retired span class may reappear inside it — and the
tightened sub-headline. The retired two-span treatment and the
ADR 0155 line stay off the hero.

## Addendum (Nov 15 2026)

Minutes after the headline shipped, Kasra reversed one casing
call from the dictation: the S of "Store" drops to lowercase.
The headline now reads "Turn your app store link into a tailored
videos, in minutes." — the T of "Turn" is the only capital left
in the line. The words, the single animated gradient, and the
sub-headline are unchanged; the smoke hero check pins the new
casing.
