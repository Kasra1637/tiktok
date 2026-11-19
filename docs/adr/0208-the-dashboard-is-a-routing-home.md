# 0208 — The Dashboard is a routing home

Status: accepted

## Context

On Nov 18 2026 the founder ordered a Dashboard: the first link in the
sidebar, above App Profile, and the page a signed-in user lands on by
default — little content, visually enticing, SaaS best practice, its
job to direct the user quickly to the next appropriate section or
workflow.

A Dashboard existed before and was deliberately removed (the removal
rationale lived in a comment in `frontend/src/App.js`): it restated
what Generation History already shows — totals and failed generations
with a Retry button — and then linked out to pages already in the
sidebar. A page whose content is another page's numbers, plus links
the frame already carries, earns nothing. That failure mode is the
constraint this decision is written against.

## Decision

1. **The Dashboard returns as a routing home, not a report.**
   `frontend/src/pages/Dashboard.jsx` carries exactly three things:
   one state-aware next-action hero, a visual grid of the six existing
   destinations, and — only when generations exist — up to three
   newest renders as picture tiles linking to History. No totals, no
   stats, no restated History or Analytics numbers, no retry actions.
2. **The hero names the single next right thing**, decided by a pure
   helper (`frontend/src/lib/dashboardNextAction.js`) in the working
   order: no app profiles → set up App Profile (`/brand`); a recent
   draft (the sidebar's own `lib/recentDraft` source) → continue it;
   a generation in flight → watch it in History; the newest finished
   render → finish it in Demo + CTA on that render; otherwise →
   Create a video. While data loads the hero wears the skeleton
   language; if either read fails the hero falls back to Create a
   video and the rest of the page still renders — a navigation hub
   never dead-ends, and it never invents data.
3. **The grid speaks the sidebar's vocabulary.** Each card is a
   single link wearing the sidebar's own icon for that destination
   and its existing hint line, copied from `Sidebar.jsx` NAV_ITEMS —
   no new copy, no new visual language. The page is built only from
   the existing design system (PageFrame / PageHeader, `.surface` /
   `.surface-compact`, IconTile, StatusBadge, the accent Button, the
   one rise-and-settle entrance); no new token, color or gradient.
4. **It is the authenticated default landing.** App.js gains the
   `/dashboard` route (lazy, like the other app pages) and the
   authenticated `/` redirect moves from `/create` to `/dashboard`;
   the stale "The Dashboard is gone" comment is replaced by the new
   rationale. The public signed-out `/` (Landing) is unaffected. The
   sign-in / sign-up completion fallbacks in `AuthControls.jsx`
   (SignInTrigger / SignUpTrigger) move from `/create` to
   `/dashboard`; no other `/create` link changes.
5. **The sidebar leads with it.** NAV_ITEMS gains Dashboard first —
   `/dashboard`, LayoutDashboard, `dashboard-nav-link`, hint "Start
   here — pick your next step" — above App Profile, and the ordering
   comment records why: the hero itself sends a profile-less user to
   App Profile first, so the profile no longer has to lead to protect
   that step. The mobile drawer renders the same NAV_ITEMS and
   follows automatically.

## Consequences

This supersedes the old dashboard's removal rationale recorded in
App.js: the objection was to a stats restatement, and this page is
not one. `/create` stops being the landing without stopping being
the workflow — the hero's fallback and the grid both route there,
and every existing `/create` deep link (draft links included) is
untouched. Checks: the sidebar smoke check now pins Dashboard first
in a seven-item order; new Dashboard smoke checks pin the route, the
`/` redirect, both auth fallbacks, the hero's precedence at page
level, the grid's six routes, the recent strip's tiles and the
failure fallback; the pure precedence helper carries a Jest suite
over its five cases and their outranking.

## Addendum — Nov 18 2026: the recent strip shows five

The founder raised the recent renders strip from up to three tiles
to the last five renders. The strip's flex-wrap row is unchanged —
five tiles wrap the same way three did — and the smoke pin now
expects the newest five from six fixture rows, the sixth left off.
