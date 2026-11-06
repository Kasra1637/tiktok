# 0087 — Template tailoring waits for the founder's Generate click

- **Status:** accepted (the free ranked read on the goal pick superseded by 0098)
- **Date:** 2026-11-01
- **Anchors:** `frontend/src/hooks/useWizardTemplates.js` (auto-run effect removed; `runTailoring` exported), `frontend/src/pages/CreateVideo.jsx` (goals-section CTA, `data-testid="templates-generate"`); smoke checks "template generation waits for the founder's click, not the goal pick", "wizard requests tailored templates for the chosen objective"
- **Shapes:** the visible side of 0080 (the hook owns tailored state; when the server is asked is a page decision from now on)

## Context

Picking a video goal fired `ensureObjectiveTemplates` immediately through an
effect keyed on `profileId:objective`. Tailoring is a billed generation: the
server reads every template against the goal, and each and every switch to a
new goal fired it again. Browsing goals on the Audience step — the normal way
to compare "Name the problem" against "Make it simple" — spent a generation
per goal, and one accidental tap on a neighbouring card cost the same. The
founder's only consent had been to the pick, not the spend.

## Decision

- The goal pick re-keys only the ranking, which is free. It queues no
  tailored-template request.
- The goals section offers a Generate CTA once a goal is picked and no
  tailored set is showing. Its click calls `runTailoring` (ensure semantics):
  the server creates the missing set for this goal and profile, or returns the
  cached one it already has.
- The header Regenerate keeps `regenerate: true` — it is the deliberate
  "pay for a fresh set" control, and stays exactly where 0087 leaves it.
- A goal that already has a tailored set shows it again free when the founder
  navigates back to it; nothing re-bills for returning.

## Alternatives rejected

- **A confirm dialog on every goal pick.** It interrupts the free re-ranking
  the step exists for, and trains dismissal exactly like the accidental spends
  it tries to prevent.
- **Debouncing the auto-run.** The spend still happens, just after a pause;
  it also delays hunting behind the bail that cancels it.

## Consequences

- No template card appears until the founder clicks one button after picking
  the goal — one extra action on the path to rendering.
- A resumed draft with a picked template still shows that template's card
  from the library; its tailored ranking is built only if the founder clicks
  Generate (pick and card survive independently of the click, as before).
- The smoke suite pins both halves: generation fires only on the click, and
  the tailoring narration itself (hidden list, count-up, cascade) still works
  once clicked.
