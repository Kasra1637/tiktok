# ADR 0351: A HookSnap video is always five seconds

## Status

Accepted, Nov 25 2026 — Kasra's direct order on a voice
call: remove the hook length selection, the video always
generates at five seconds by default, the two buttons
showing four or five seconds are not displayed on the
front end anymore, and the hook card's subtitle states it.

## Context

ADR 0329 stood the Hook length on HookSnap as two pick
pills, 4 seconds and 5 seconds, under the hook card's
subtitle. In use the choice earned nothing: the hook is
one line, the five-second frame is the surface's settled
shape, and a pick the founder must make before anything
generates is friction on the fastest page in the app.

## Decision

The pick is removed end to end. On the page, the Hook
length control and its buttons are gone, and the hook
card's subtitle reads "One line from your app and your
direction, five seconds." — the fixed length stated where
the pick used to be explained. On the server, the three
HookSnap length resolutions in `routers/hook_cta.py` —
project create, hook generation, render submit — pin the
length to five seconds: a frame outside the old 4/5 pair
is still refused, a legacy 4 is accepted and lands at
five, and a row still storing 4 generates and renders at
five. The shared studio PATCH keeps its standing
validation untouched — the stored value no longer drives
anything on this surface, because every generation path
here resolves five for itself. The strategy's hook window
(`hook_seconds`, the word-budget window) is unchanged.

## Consequences

Existing HookSnap projects need no migration: their next
generation or render lands at five seconds on its own.
ADR 0329's side-by-side pill treatment stands for the
controls that remain (resolution, crop); only the length
pick is retired. Pinned by backend tests (a legacy 4s ask
creates, generates and renders at five) and by smoke
checks (no length control renders, the subtitle states
the five seconds, the render submits at five).
