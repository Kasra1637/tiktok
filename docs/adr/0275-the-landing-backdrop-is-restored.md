# ADR 0275: The landing backdrop is restored

Status: accepted

## Context

Kasra reported on Nov 22 2026 that updates made by the other agent —
the landing page's CSS background above all — were not showing on the
live website, even though their commits were on main and deploys run
automatically from main. The audit found no deploy fault. It found
this push's own earlier work:

The other agent's landing stack (71b7caa's full-page studio spotlight
and dotted canvas, f757601's cinema aperture arcs and ambient wash,
612d865's glow removals, ade59c2's orb removal keeping the arcs,
97bc842's calmed top wash, 76a0ed2's 30% brightening of that wash, and
b2bd47b's hero phone motion) lives in `frontend/src/index.css`, with
its markup in `Landing.jsx`. The markup was never touched — the page
still renders its `landing-aperture` div and `hero-wash` class. The
stylesheet was.

The ADR 0263+0264 push (888c3c0) was assembled from a local tree based
on 2fa6a75, from before that landing stack landed. push-files uploads
whole files, so the push's `index.css` — the older stylesheet plus ADR
0264's highlight additions — silently replaced the newer one on main.
Gone in that one file: the whole `.landing-aperture` block, the calmed
and brightened `.hero-wash` values (reverted to the older, stronger
0.08 / 0.06 / 0.05), and the hero-story keyframes (`hs-phone-float`,
the research and generate sheens, the four step-badge pops, the play
halo) with the reduced-motion block that wires them. The push's
verification compared origin against that same stale local tree and
read zero diff, so it could not catch the loss. The same push also
carried three of f251bbb's `AssetLibrary.jsx` copy lines back to their
older wording (two detach tooltip titles, the upload panel
description). Its `CreateVideo.jsx` lint revert was already healed
upstream when 4c7e270 re-applied those fixes. The gates stayed green
through all of it for a subtler reason: 612d865 had updated the
render-smoke checks in lockstep with the glow removal — the checks
stopped requiring the phone's indigo glow and the research control's
glow variable — and the same stale push uploaded the older
`check-render-smoke.cjs` too, so the stale stylesheet and the stale
checks agreed with each other. A name-level audit of the checks
missed it, because no check was renamed or dropped by the push; only
assertions inside them moved. (The six check names that are absent
now were each accounted for separately: five intentionally
superseded by ADRs 0268 and 0272, one removed by ADR 0272 itself.)
The loss only surfaced when the stylesheet was restored and the two
hero checks — still asserting the pre-removal glows — failed against
it.

## Decision

**Restore, exactly, by merge — not by rewrite.** `index.css` is
rebuilt as a three-way merge: base 2fa6a75 (the last state both
streams shared), one side the other agent's final landing stylesheet
at 76a0ed2, the other side the pre-fix main. The merge is verified in
both directions: against 76a0ed2 the result differs only by ADR 0264's
highlight additions (the fit-content hug, the comment it reworded, and
the wash-in entrance), and against the pre-fix main it differs only by
the restorations. f251bbb's three AssetLibrary lines are restored
word-for-word. The smoke file is restored by the same three-way merge
(base 2fa6a75, the other agent's final at 5734318, current main): the
glow assertions and every other check body their stack updated come
back, while ADR 0268's re-pins, ADR 0272's removals, and ADR 0274's
additions all survive. The merge's two conflicts sat in the hero
headline check, in comment and error wording only — the assertions
were identical on both sides — and resolved to the current side,
which carries ADR 0268's record. Nothing else changes: no markup, and
no copy beyond those three lines.

## Consequences

The landing page shows its aperture arcs, calmed wash, and hero phone
motion again on the next automatic deploy, and the Assets page wears
the unified copy it was given. ADR 0264's highlight behavior is
unchanged. The failure mode is now on record: a whole-file push from a
stale base silently reverts another stream's work in any file both
streams touched, and verifying the push against the pushing tree
proves nothing about what was overwritten. After parallel work, a
push's file list must be diffed against the other stream's last state
for those same files before it goes up.
