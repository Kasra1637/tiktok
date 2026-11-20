# 0240 — The tutorial entry returns to the Dashboard, and Stories gets its tour

Status: accepted (extends 0118; the Dashboard half settles a gap 0208 left)

## Context

Kasra's report (Nov 20 2026): "Onboarding tutorial is also not
showing in the sidebar of the dashboard. Make sure that reappears,
and also add the spotlight tutorial guide for the Stories too."

The sidebar's tutorial entry is `SidebarFooter`'s "Show me
around" button. It is not a fixed fixture: it renders only when
the onboarding provider resolves a tour for the current page —
`hasTourForPage` is `!!getTourIdForPath(pathname)`. The entry
itself was never removed from the sidebar. What happened is
upstream of it:

- ADR 0208 (commit `c1ec8d1`, Nov 19 2026) made `/dashboard`
  the authenticated default landing — `/` redirects there and
  both auth-completion fallbacks follow.
- No `dashboard` tour was ever added to `TOURS`, and
  `/dashboard` was never mapped in `getTourIdForPath`. The
  evidence is the history: `git log -S`/`-G` over
  `lib/onboarding/tours.js` finds no "dashboard" in any
  revision, and `pages/Dashboard.jsx` has never carried a tour
  affordance in either of its incarnations.
- Before 0208 the landing was Create Video, which has a tour,
  so the entry showed on arrival. After 0208 the founder lands
  on the one main page that resolves no tour, so the button
  renders nothing there — the entry silently vanished exactly
  where a signed-in founder arrives, while still appearing on
  every other tour page.

Stories (ADRs 0235/0236) shipped with no tour at all: no
`stories` entry in `TOURS`, no `/stories` mapping, and no
eligibility registration — the only main creation surface
without one.

## Decision

1. **A `dashboard` tour restores the entry.** Three steps on
   the page's own anchors — the next-action hero
   (`dashboard-next-action`, already present), the destinations
   grid and the recent strip (anchors added to `Dashboard.jsx`
   in this commit: `dashboard-destinations`,
   `dashboard-recents`, the strip's step optional since
   the strip needs renders behind it) — and `/dashboard` maps
   to it in `getTourIdForPath`. The sidebar entry reappears in
   its same footer place, with its same "Show me around"
   label, doing its same job: replaying the current page's
   tour.
2. **The Dashboard tour is replay-only.** It is not added to
   `CORE_AUTO_OPEN_TOURS` and the page registers no
   eligibility. ADR 0118's auto-open set is the journey's
   working and fork pages, each with a first-run state of its
   own; the Dashboard is the arrival screen itself, and the
   retired home-page tour (recorded in `tours.js`) is the
   standing lesson against an overlay over the arrival
   screen. The Dashboard hero already names the next action,
   which is the one thing an auto-opened tour would say.
3. **A `stories` tour walks the settled flow.** Nine steps in
   the page's stacking order: pick the app, pick one of the
   four types, direction (camera, place, wardrobe — fixed
   means indoors), generate the plan, the editors (the spoken
   line aloud; the screen text as the hand-added sticker,
   capped at 80 characters / 14 words), the story Craft
   check, the preview with both platforms' safe zones, the
   render at the frame's own 3–5 second length, and the
   story kit. The two picker steps are required — a first-run
   page already shows them; every step past the type pick is
   optional, because its section waits on a draft or a plan
   the founder has not made yet. All anchors already existed
   except one, added in this commit (`story-editors` on the
   editors block).
4. **Stories joins the core auto-open set** in the provider,
   on ADR 0118's fork-page rule — it is the other creation
   surface, a page a founder can arrive at before
   understanding it. The page registers conservative
   first-run eligibility in the ADR 0077 pattern: loaded
   without error, an approved app picked, no draft open or
   created yet, and the picked app's draft list settled
   empty. A `draftsSettled` flag separates "no drafts" from
   "not known yet" — an unsettled read also reports an empty
   list, and the flag is the loading guard the other tour
   pages register behind. Seen and dismissal semantics are
   unchanged.

## Alternatives rejected

- **An always-rendered sidebar button** that starts some
  other page's tour, or a generic tour, on pages without
  one. The entry's settled behavior is "replay this page's
  tour"; a button on the Dashboard that opened Create
  Video's steps would spotlight targets that do not exist
  here and misname what it does.
- **Mapping `/dashboard` to an existing tour.** Same failure
  as above, with the added dishonesty of the mapping
  claiming the Dashboard is another page.
- **Auto-opening the Dashboard tour on first landing.**
  Rejected for the arrival-screen reason in decision 2;
  "Show me around" covers the deliberate revisit, as it
  does for the per-record App Profile detail tour.

Anchors: `frontend/src/lib/onboarding/tours.js` (`dashboard`
and `stories` tours, `getTourIdForPath`);
`frontend/src/components/onboarding/OnboardingProvider.jsx`
(`CORE_AUTO_OPEN_TOURS`);
`frontend/src/pages/Stories.jsx` (`useTourEligibility`,
`draftsSettled`); `frontend/src/pages/Dashboard.jsx` (the two
added anchors); render checks in
`frontend/scripts/check-render-smoke.cjs` (the fork-page
onboarding check's page set, "the sidebar offers Show me
around on the Dashboard…", "the Stories tour walks the
settled flow…", "the Stories page registers its first-run
tour eligibility").
