# 0260 — The landing hero carries live proof

Status: accepted (headline wording supersedes ADR 0256's hero line;
the ScriptMockup treatment follows ADR 0258)

## Context

Kasra's spec (Nov 21 2026) asked for five landing-and-editor pieces in
one delivery: a new hero headline, a backend-driven proof pill above
it, three Features mockup upgrades, frame-type tags in Demo + CTA, and
live block-count badges on BrandSetup's two block fields.

Two points in the spec met a tree that had moved since it was written,
and both are recorded here rather than silently followed or silently
dropped:

- The ScriptMockup was asked to wear ".spoken-line-frame boxes". ADR
  0258, shipped the same day, retired that frame everywhere: generated
  text now wears the `.generated-highlight` wash. A mockup's job is to
  show the product as it is, so the mock wears the highlight.
- The frame-type tags were asked for "in the Device picker". There is
  no device picker: the editor's frame is fixed by a recorded design
  decision (`DemoCtaEditor.jsx`: "The picker is gone by design — one
  frame, no choice"), and the spec's own constraint was tags only, with
  frame behavior, geometry and values unchanged. Resurrecting a picker
  would change behavior; the tags therefore live in the catalog and on
  the editor's frame line (point 4 below).

## Decision

1. **Headline.** The hero `<h1>` in `frontend/src/pages/Landing.jsx`
   reads exactly "Turn your URL into a tailored video in minutes." —
   superseding ADR 0256's "app or website link" wording. The ADR 0215
   size tokens (`text-hero` / `sm:text-hero-wide`), the gradient
   treatment, and the sub-headline are unchanged; the smoke pin moves
   to the new line.

2. **The proof pill.** Directly above the `<h1>` stands the same
   `<EyebrowPill strong>` the closing CTA uses for "Ready when you
   are" (12px semibold uppercase, `.eyebrow .eyebrow-accent`,
   rounded-full, indigo border and fill, Zap icon; `EyebrowPill` gains
   an optional `testId` prop, forwarded as `data-testid`). Its copy is
   composed from the endpoint's fields, in this order:

   "{hook_structures} curated hook structures · {profiles_approved}
   approved app profiles · {plans_drafted} plans drafted"

   (rendered uppercase by the eyebrow treatment). It is backed by a
   new public endpoint, `GET /api/landing-proof`
   (`backend/routers/health.py`, no auth — the page is public and the
   counts are aggregate, identifying no founder; per-account inventory
   stays on `/api/health`). Every number is a real count at request
   time, from exactly one source each:

   - `plans_drafted` — `COUNT(*)` over `studio_projects` (a row exists
     only once a plan has been drafted against an approved profile).
   - `profiles_approved` — `COUNT(*)` over `brand_profiles` where
     `status = 'approved'`, the state the approval endpoint writes.
   - `hook_structures` — `len(template_library.CURATED_TEMPLATES)`,
     read from the catalog in-process (10 at this writing).

   The response also carries `baseline` and `live`. The baseline is
   deterministic and true at any time — 0 for both database counts
   (a count's floor) and the catalog size for the structures — and the
   page renders the pill from the same baseline on first paint, then
   swaps the live counts in when the fetch lands, so the pill never
   invents a number and its seat never moves. If a database read
   fails, the endpoint falls the whole report back to the baseline
   with `live: false` rather than quoting one real number beside one
   floor. The frontend baseline's structure count is pinned against
   the backend catalog by a render-smoke check, so the two cannot
   drift apart silently. Backend tests pin the shape, the seeded-row
   counts, and the baseline's determinism.

3. **Features mockups** (`frontend/src/pages/FeaturesMockups.jsx`).
   ScriptMockup: the hook and the story's two beats wear
   `.generated-highlight`, labelled Hook / Beat 1 / Beat 2, with the
   craft-check row kept. RenderMockup: a filled presenter (brand-
   gradient figure in a lit scene, play badge) under two dashed
   safe-zone guides — TikTok (right rail and bottom reserved) and
   Instagram — drawn as mockup annotations; the white "Your spoken
   hook" banner burned into the old frame is gone. DemoMockup: a
   browser-window frame (window bar, URL field, page lines) over a
   three-step sequence timeline — Hook + Story / Your demo / End
   card — replacing the palette dots.

4. **Frame-type tags.** Every entry in `DEVICES`
   (`frontend/src/demoCta/constants.js`) gains a `kind`: `"phone"` for
   the eight handsets, `"browser"` for the Browser / Web Card;
   `DEVICE_KIND_LABELS` names them "Phone" and "Web / Browser", and
   `deviceKindTag(device)` resolves an entry to its label. In
   `DemoCtaEditor.jsx` the Base clip & look group gains a frame line
   naming the active frame with its tag (`demo-cta-frame-tag`). Tags
   and naming only — no frame value, geometry or behavior changes,
   and any future picker inherits the tags from the catalog.

5. **BrandSetup block badges.** On the label rows of
   "Feature-to-outcome statements" (4 lines per block) and "Why they
   would not try or download" (3 lines per block), a live badge
   (`BlockCountBadge` in `frontend/src/pages/BrandSetup.jsx`, riding
   the shared `Field` wrapper's new `badge` slot) shows the complete-
   block count and, when a block is missing a line, a coral warning
   naming how far the last partial block got ("unfinished block — 2
   of 4 lines, won't save"). The count is computed by the very parsers
   the save path runs (`textToOutcomes` / `textToObjections`), and
   both parsers plus the badge read blocks through one shared
   `splitTextBlocks`, so the badge cannot drift from what save will
   keep. Visibility only: nothing about what gets saved changes.

## Alternatives rejected

- **Baking the counts into the page at build time, or a marketing
  round number.** A static figure goes stale and reads as live; a
  rounded claim is an unverified one. The endpoint counts at request
  time or falls back to a floor it names as a floor.
- **Per-account proof numbers.** The pill is public evidence about
  the studio; a visitor has no account, and one founder's inventory
  is `/api/health`'s job, behind auth.
- **Restoring `.spoken-line-frame` for the ScriptMockup.** It would
  advertise a UI the app retired the same day (ADR 0258).
- **Bringing back a device picker to hold the tags.** A picker is a
  behavior change wearing a tag's clothing, against both the fixed-
  frame decision and the spec's own "tags only" bound.
- **A second, badge-only block parser.** Two parsers for one format
  drift; the badge shares the save path's split and calls its
  parsers outright.

## Consequences

The landing page makes three numeric claims, all of them countable
and counted; the smoke gate pins the headline, the pill's seat,
treatment and live swap, the baseline-to-catalog parity, the three
mockups' new contracts, the editor's frame tag, and both badges'
count-and-warn behavior. The frontend-logic gate pins the device
kinds and tag labels.
