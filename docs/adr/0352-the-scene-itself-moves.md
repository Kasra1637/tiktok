# ADR 0352: The scene itself moves behind the presenter

## Status

Accepted, Nov 25 2026 — Kasra's pick from the HookSnap
enhancement review: keep the five-second lock, with a
subtle motion cue in the background (rated 8/10 on the
call, against 9 for the caption preview in ADR 0353 and
7 for a hashtag suggestion he declined).

## Context

ADR 0250 requires a HookSnap render's location to render
as a real scene behind the presenter — surfaces, objects
and light present and readable, never a plain backdrop.
Nothing anywhere asks that scene to MOVE. A render can
satisfy every standing rule and still hold a frozen,
still-photo room behind a moving presenter, and on a
five-second hook the eye reads that stillness instantly:
the one surface whose whole job is the first seconds
ships the flattest possible background.

## Decision

A hook-surface-only passage joins the real-scene rule at
its append site in `_assemble_prompt`
(`backend/generation_planning.py`): THE SCENE STAYS
ALIVE — the place behind the presenter moves subtly for
the whole take (light shifting across a surface, a
curtain stirring, distant movement passing), quiet and
secondary, never competing with the presenter, who
stays the motion of the shot; a frozen, still-photo
room is a failed render. A condensed twin follows the
standing pattern, so the rule survives tight provider
ceilings in shorter words rather than dropping.

The passage's characters are accounted where the fit
math can see them: `_prompt_floors` gains a hook-surface
term counting all three hook-only passages — the
physical opening and the real scene (ADR 0250) beside
the new motion cue, in the form the budget selects.
The measured floor constants are taken on a surfaceless
assembly and never counted the two older passages; the
fit correction divides the variable text by the room
the floor leaves, so uncounted fixed text silently
spent that room and left HeyGen's 4,090 ceiling
guarantee (ADR 0327) resting on the retry loop. Create
renders are untouched: no surface marker, no passages,
no floor change — their prompts are byte-for-byte what
they were.

## Consequences

HookSnap renders squeeze their variable fields
marginally harder at tight ceilings — the honest price
of the fixed text they actually carry — and still fit:
pinned by tests that the passage and its condensed
twin appear on hook-surface prompts only, that a
saturated hook prompt at 4,090 stays inside it, and
that the floor difference between a hook surface and
none is exactly the three passages' lengths.
