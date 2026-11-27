# ADR 0376: Step headers are standing headings — navigation lives in the rail and the sticky bar alone

## Status

Accepted, Nov 26 2026 — Kasra's order: remove the
in-section step-navigation buttons from the Create
flow, so moving between steps and taking a step's
action happens from the sticky components alone.
The change lands in `frontend/src/pages/CreateVideo.jsx`.

## Context

Create carried two navigation models at once. The
rail segments (ADR 0298) and the sticky bottom bar
(which carries each step's primary action, ADR
0133) walk the wizard honoring the sequential seal:
a step is locked until every previous step is done,
and a locked rail segment is disabled (ADR 0328).
But each step's section header was also a button
calling `setStep` — and it honored no seal, so a
click on a locked step's header opened it anyway.
Two models, two different rules for the same walk,
and the looser one standing at the head of every
section. ADR 0229 had already removed the panels'
own jump buttons for the same reason; the headers
were the surviving second door.

## Decision

The four section headers are standing headings now,
not controls:

- The header element is a plain block carrying the
  step's digit (or padlock), its label and its state
  chip, under the same `wizard-section-toggle-<key>`
  testid. It has no click handler, no `aria-expanded`,
  and opens nothing.
- Moving between App Profile, Audience & template,
  Review & submit and Demo + CTA belongs to the rail
  segments and the sticky bar alone. The bar's Back
  stays free, as before; its Continue stays the hard
  gate, as before.
- Companion fix, same record: the project deep-link
  load overrode an explicit `?step=` — an unplanned
  draft's link naming Review was dragged to the
  Audience step by the load's auto-landing. The
  profiles load already respected a named step; the
  project load now does the same. A link naming a
  step lands on that step, and the step's own guards
  say what is missing — the behavior the step
  state's own comment has always promised. Links
  naming no step land exactly as before.

## Checks

New: "the step headers are standing headings, not
navigation" pins the removal — clicking a header
moves nothing, the header still names its step and
its lock, and the locked step's rail segment stands
disabled.

The harness's `openStep` now walks by the rail
segment, the way a founder does, and fails loudly
when a fixture asks for a sealed step. Eighteen
standing checks reached Review through the old
header door; each is changed as named, with its
assertions at full strength:

- Ten land on Review by the step link at mount —
  "Review's angle gate names the angle in its own
  words", "Review without a goal asks for it instead
  of spinning forever", "a failed plan offers retry
  instead of spinning forever", "a review missing
  only the photo names only the photo", "live goals
  generate only on the Review gate click", "live
  goal failure keeps the gate and names the retry",
  "Review with a goal but no angle waits for a real
  angle before planning" (its walk back and return
  still ride the rail), "Review names a missing
  profile in words and offers no jump", "Review
  names only the gap actually missing, never two
  firsts", and "Review & submit's angle gap asks
  once, in words, in both states".
- "the revealed angle list keeps its pick across
  steps": the excursion now leaves to App Profile
  and returns. Review is sealed until the whole
  Audience step completes, and completing it would
  bury the pick assertion under a full-flow setup;
  what is pinned — the pick's survival across step
  changes — is unchanged.
- "the plan is written before a character photo is
  attached": the fixture arrives on Review by its
  deep link carrying every plan input except the
  photo. With no photo the Audience step never
  reads done, so no walk can reach Review; what is
  pinned — the photo does not gate the plan
  (ADR 0122) — is unchanged.
- "Review & submit names the missing angle instead
  of generating or jumping": lands by the step
  link, and the walk home rides the sticky bar's
  Back, the one direction that stays free — the
  Audience segment is sealed until a profile is
  picked, and this fixture picks none.
- "no template id is silently reported as done on
  the progress bar": the Review leg remounts on the
  draft's project link with the step named; the
  resumed server row carries the angle and goal,
  and its template names no row — the gap under
  test.
- "the regen notice names rebuilding at Review and
  carries no jump of its own" and "the regen notice
  dismisses and stays dismissed across steps": the
  walk to Review now finishes the Audience step the
  way a founder does — the fresh angle's goal, then
  the template gate — which is what stands the
  Review segment open.
- "every gate leads with its ask above its hint,
  spaced the same" and "Review and dense panels put
  the primary action above its guidance copy": the
  still-missing panel is recorded from a fresh mount
  on Review's step link, the same panel the walk
  used to reach; their remaining fixtures take the
  link at mount.

## Alternatives considered

Keeping the headers clickable for unlocked steps
only: rejected — a heading that is sometimes a door
keeps the second navigation model alive and invites
the next bypass. Removing the sequential seal so
every step stands open: rejected — the seal is the
wizard's guidance (ADR 0328), and the founder's
complaint was the duplicate doors, not the seal.
