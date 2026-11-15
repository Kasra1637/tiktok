# ADR 0155: The landing headline — turn your App Store link into a tailored TikTok

Status: accepted

Supersedes the hero copy set by the Nov 15 2026 landing bundle
("Yours in minutes, and only yours." with its chosen sub-headline);
that pair stays as history in the commit that shipped it.

## Context

Kasra, in the main chat on Nov 15 2026, reversed the headline he
had chosen earlier the same night: "Yours in minutes, and only
yours." did not say what is yours. He proposed a new base in his
own words — turn an App Store link into a tailored TikTok video —
asked for it more polished, scored the two polished options, and
picked the higher-scored one with "Use that".

An intermediate headline, "One link, one photo, one tailored
TikTok.", had been selected minutes earlier and was then held by
the founder ("No, I'm not ready yet") before any implementation;
it was never shipped and is superseded by this decision.

## Decision

The hero headline is exactly:

"Turn your App Store link into a tailored TikTok, in minutes."

It says exactly what the app does and what the user gets: an App
Store link goes in, a tailored TikTok comes out, in minutes. The
two-span treatment is unchanged — `text-shine` carries "Turn your
App Store link into a tailored TikTok," and `text-gradient-brand`
carries "in minutes.", the gradient holding the payoff phrase as
it held "and only yours." before. Type scale and layout are
untouched.

The sub-headline takes one light alignment, nothing more. The new
headline ends in "in minutes", so the sub-headline's identical
phrase would repeat it two lines apart; that phrase alone is
removed. The word "tailored" stays in the sub-headline
deliberately — there it says a different thing: the video is made
for your app alone. The sub-headline now reads exactly:

"No filming, no editing, no blank page. Your app's facts become a
hook, a script, and a finished video, tailored to your app alone,
and learning from every video you judge."

The smoke suite's hero check pins both lines to this copy and
asserts the held headline stays off the page.
