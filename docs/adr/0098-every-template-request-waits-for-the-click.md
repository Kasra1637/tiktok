# 0098 — Every template request waits for the Generate click

- **Status:** accepted
- **Date:** 2026-11-05
- **Anchors:** `frontend/src/hooks/useWizardTemplates.js` (the auto-run effect is gone; `loadRecommendations` is called only inside `runTailoring`), `frontend/src/pages/CreateVideo.jsx` (full-width branded CTA in the goals section), smoke check "template generation waits for the founder's click, not the goal pick" (now counts the tailored POST and the ranked read separately)
- **Shapes:** extends 0087; display contract from 0096; consent side of 0080

## Context

0087 made the billed tailoring wait for a click but left the goal pick firing
the free ranked read (`GET template-recommendations`) as an effect. The read
makes no model call, so nothing was billed — but from the founder's seat the
step still behaved as if templates came with the goal: a request was made for
every goal touched, and the visible picker waited on data the founder never
asked to have fetched. "Nothing is generated until I ask" cannot be half
true: any request keyed to the pick is spend the founder has to take on
faith, and the next question is why the list still appears without ever
pressing the button the product points at.

## Decision

- Picking a goal queues nothing at all: no tailored-template request and no
  ranked read. The hook holds no effect loading recommendations; switching
  goals, returning to a goal, or re-entering the step costs zero requests.
- The Generate CTA in the goals section is the single gate for every template
  request. Its click runs one flight: the billed tailoring POST, then the
  free ranked read that feeds the cards' order and the ADR 0096 backfill.
- The ranked read also runs when the generation refuses, so the server's
  documented fallback — the curated picks — is what the founder lands on.
- The CTA is claimed as the step's primary action: full-width, branded
  (accent), inside the goal panel, with one supporting line naming when
  generation runs. Regenerate stays beside the revealed list, as 0087 left
  it.

## Alternatives rejected

- **Keep the free read on the pick.** No model call still means one request
  per goal touched and a data fetch the founder never asked for; the promise
  "nothing until you ask" is only honest if nothing fires at all.
- **Reveal the ranked list free and gate only the tailored set.** Two
  different template sources on one screen — one behind the click, one not —
  re-opens the pre-made leak 0096 closed.

## Consequences

- One extra action before the first template card (same as 0087), and no
  request for goal browsing, returning, or step re-entry — the founder's
  spend is bounded by their own clicks.
- The "No templates recommended yet" empty state renders only after a click
  (an empty ranked read after success, or a refusal's curated fallback),
  never as an ambient state of the step.
- Smoke pins both requests behind the click: the "waits" check counts the
  tailored POST and the ranked read separately, and the ready-path checks
  already click the CTA before asserting cards.
