# ADR 0306: A finished login lands on the Dashboard — always

Status: accepted

## Context

The founder ruled, in all caps, on Nov 23 2026: when a user
logs in, they should land on the Dashboard — always. The app's
inner home route already points at the Dashboard (the app
shell's "/" redirects to "/dashboard"), but the sign-in and
sign-up pages mounted Clerk's components with no redirect of
their own, so where a finished login actually landed was left
to Clerk's defaults and any return path in play — a user
bounced from a deep link could be returned to that page
instead of the Dashboard.

## Decision

Both auth pages force the landing: ClerkSignIn and ClerkSignUp
each carry forceRedirectUrl="/dashboard" and
fallbackRedirectUrl="/dashboard". The forced URL wins over any
stored return path, so a completed sign-in or sign-up ends on
the Dashboard whatever page or deep link started it. A smoke
check pins both props on both pages.

## Consequences

Login has exactly one destination, matching the Dashboard's
role as the routing home. A founder following a shared deep
link while signed out lands on the Dashboard after login and
navigates from there — the trade the ruling explicitly chose
with its "always".
