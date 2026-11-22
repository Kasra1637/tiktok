# 0261 — The proof pill leaves the hero

Status: accepted (supersedes ADR 0260 in part: its hero proof pill
and its headline wording; the rest of 0260 stands)

## Context

ADR 0260, shipped earlier the same day (Nov 21 2026), placed a
backend-driven proof pill directly above the hero `<h1>` on the
landing page: the strong EyebrowPill carrying three live counts
from `GET /api/landing-proof` — curated hook structures, approved
app profiles, plans drafted.

Kasra reviewed it live and rejected it outright: the three-count
copy read long and confusing to him. Every shorter replacement
offered in the same conversation was also rejected. His ruling was
removal, not another rewrite — and in the same breath he dictated
the headline's next wording: "Just say apps URL. Everything else
same."

## Decision

1. **The pill is removed.** `HeroProofPill`, its live-fetch wiring,
   the Landing-only proof state (`LANDING_PROOF_BASELINE`,
   `proofCount`) and its render seat above the `<h1>` are gone from
   `frontend/src/pages/Landing.jsx`; the hero opens with the
   headline alone, as it did before ADR 0260. The `getLandingProof`
   helper leaves `frontend/src/lib/api.js` with it (an in-file
   removal — no file is deleted), and the imports only the pill
   used (`api`, `useState`/`useEffect`, `Zap`) leave with it. The
   closing CTA's own EyebrowPill ("Ready when you are") is a
   different seat and is not touched; `EyebrowPill`'s optional
   `testId` prop from ADR 0260 stays.

2. **The headline.** The hero `<h1>` reads exactly "Turn your apps
   URL into a tailored video in minutes." — Kasra's words, "apps"
   with no apostrophe. The ADR 0215 size tokens
   (`text-hero` / `sm:text-hero-wide`), the gradient treatment, the
   placement and the sub-headline are unchanged; the smoke pin
   moves to the new line.

3. **The endpoint stays.** `GET /api/landing-proof`
   (`backend/routers/health.py`) and its tests
   (`backend/test_landing_proof.py`) remain in place, unused by
   the page. It is tested, harmless, and the only way back if
   Kasra ever asks for proof on the page again; removing it was
   not part of the ruling, and its test file would have been this
   commit's one file deletion.

4. **The pins move.** The render-smoke headline check carries the
   new line. The two ADR 0260 pill checks — the pill's presence
   with the live counts, and the frontend baseline↔catalog parity
   — are replaced by one absence pin: no `landing-proof-pill`
   anywhere on the rendered page, and the `<h1>` is the first
   element standing in its hero column. The smoke stub's
   `getLandingProof` entry leaves with the helper it mirrored.

## Alternatives rejected

- **Another pill copy.** Kasra rejected every draft offered —
  shorter, four-word, outcome-led, value-led. The seat itself was
  the problem, not only the wording; a fifth rewrite would have
  ignored the ruling.
- **Deleting the endpoint and its tests in the same commit.** The
  ruling named the pill above the headline. The endpoint costs
  nothing standing unused, its counts stay honest, and deleting
  its test file was outside the zero-deletion bound Kasra set for
  this change.
- **Keeping the frontend helper "just in case".** A client method
  for a caller that no longer exists is drift; it leaves with the
  pill and can return with any future caller.

## Consequences

The landing hero makes no numeric claims again; the page's only
eyebrow pill is the closing CTA's. ADR 0260 stands for its
headline history (now reworded), the Features mockups, the
frame-type tags and the BrandSetup badges; its pill and the
endpoint's page contract are this record's to describe. The smoke
gate pins the new headline and the pill's absence; the backend
gate still pins the endpoint that outlived its caller.
