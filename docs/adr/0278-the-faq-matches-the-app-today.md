# ADR 0278: The landing FAQ matches the app today

Status: accepted

## Context

On Nov 23 2026 Kasra asked whether the landing page's FAQ
("A few things worth knowing") still aligns with the app's
current functionality, workflow, and audience. The audit found
four of the five answers accurate — including the honest ones:
posting and tracking stay manual, results are pasted back by
hand and do not prove conversions, the photo guides a presenter
rather than cloning the founder, and posted patterns start
steering generation at three posted clips (ADR 0117's
MIN_POSTED_CLIPS_FOR_PERFORMANCE_STEERING). Two gaps and one
wrong note stood out. The script answer said "before you pay
for a render," but the app has no payment or pricing in it —
Kasra ruled the pay wording out entirely. And the questions a
new visitor most likely asks had missing answers: what they
need to start, what the Hook + CTA page is — the short flow
(ADR 0244) the FAQ never mentioned — and how a photo becomes
a video built to stop the scroll, the presenter already
moving from the first frame with the hook landing in the
first two seconds. Kasra ordered all of it added, in plain,
conversational words, and corrected the shape himself: the
presenter is a real person from the uploaded photo, not a
cartoon, and the video is ready in a few minutes.

## Decision

The QUESTIONS set in Landing.jsx grows from five to eight, in
visitor order. First stands the new "What do I need to get
started?" — the product's link and one clear photo of the
presenter, the link studied and the video built around the
photo, no filming and no blank page. After the script question
stands the new "What is Hook + CTA?" — the short route: a
four-to-five-second hook rendered on its own, finished on the
same page with the real demo and closing message, with a post
kit (caption, cover text, and five hashtags picked by volume,
ADR 0139) alongside. After the face-and-voice question stands
"How does my photo become a video that stops the scroll?" —
the photo becomes the presenter, a real person already moving
from the first frame, the hook landing in the first two
seconds, the story keeping the scene alive, the real demo and
closing message finishing the job, the whole video built for
TikTok and ready in a few minutes. The script answer keeps
its meaning and loses the pay clause: the review now happens
"before anything renders, never after." The other four
answers stand word for word — their disclosure patterns in
the render-smoke suite are untouched, and the suite's
question-count pin moves from five to eight in this commit,
recording that the count moves only with the set.

## Consequences

The FAQ now opens with what a founder needs in hand, names the
short flow beside the full one, says plainly how the photo
becomes a scroll-stopping TikTok video, and promises no
payment step the product does not have. Nothing else on the
landing moves.
