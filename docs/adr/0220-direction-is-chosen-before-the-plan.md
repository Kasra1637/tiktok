# 0220 — Direction is chosen before the plan

Status: accepted

## Context

Kasra's ruling on Nov 19 2026: move the Visual & audio direction
section (camera setup, location, wardrobe, and the direction text it
composes) out of Review & submit and into the Audience & template
step, below the angle and goal picks — "so that when users set their
shit up they don't have to regenerate plan again for this reason,"
and "by the time the plan is generated it already includes that."

The section sat in Review, after plan generation, and that seat cost
twice. First, the plan was written before the founder had chosen a
camera setup or a place, so it could stage the wrong setup; setting
direction afterwards moved the saved direction off the strategy's
snapshot, and the raw-value drift gate (ADRs 0142/0146) marked the
strategy stale and forced a rebuild — the change-direction-later
trap. Second, ADR 0219 made the fixed camera indoors only inside the
generation prompts, while the location dropdown went on offering
outdoor places for a fixed setup, leaving the rule to be enforced
by prose against a pick the UI itself had offered.

## Decision

1. **The section renders on the Audience & template step**, below
   the angle selector and the goal panel and above the template
   picks. It is the same section — the same disclosure, controls,
   testids and behavior — relocated, not redesigned. It stays
   optional and stays out of the step's substep row: it is
   refinement, not a finishing pick or a gate. Nothing of it remains
   in Review & submit; the one pointer to it (the strategy panel's
   scene block) now names the Audience & template step.

2. **No save-path change was needed, and none was made.** Direction
   edits ride the same draft and the same ~1s autosave as every
   wizard edit, and plan generation reads the saved project row —
   `location`, the reconciled `visual_direction`, and `camera_setup`
   all reach `generate_creative_plan` from the row (verified in
   `routers/studio.py`, both the plan endpoint and the
   plan-and-strategy pass). A plan generated after the picks is
   written already respecting them, because the prompt reads what
   this step saved.

3. **The location list respects the camera setup, at the options
   source.** The direction-options endpoint and the per-field
   refresh take the picked camera setup. For a fixed camera the
   location list is filtered through `template_library`'s
   `location_setting` (ADR 0219) to classifier-indoor locations
   only — outdoor and unclassifiable are both withheld, because
   unknown is never permission. Handheld, and a request that states
   no setup, get the full list. The frontend keys the options
   lifecycle on the setup (`useWizardDirections`), so flipping the
   setup re-reads the list under the new one, for the static list
   and for refreshed options alike.

4. **A saved place that becomes ineligible is named, not rewritten.**
   The codebase's pattern for a saved value that stops being
   eligible (the gone template is the sibling case) is that the
   value stands, the pick reads empty, and a notice names what
   happened and what to do. The section follows it: when the setup
   is fixed, the lists are loaded, a place is saved, and no offered
   indoor location matches it, the pick reads empty and the section
   shows a notice (`direction-location-ineligible`) saying the saved
   place is not an indoor location and to pick one. The saved value
   is not silently rewritten; ADR 0219's plan rule guards
   generation in the meantime. The matching derivation also no
   longer clobbers an unsaved pick that is still offered when the
   lists re-read — a pick the new list drops still falls out, which
   is what makes the ineligible case read empty.

5. **Three wording lines changed, because the move falsified them.**
   The camera line no longer says "save, then rebuild the strategy
   before rendering" — it says the plan and the render follow the
   setup saved here. The location-and-wardrobe help no longer says
   the picks "apply together when you rebuild the strategy" — they
   apply together in the plan written from them. The live preview's
   subtitle no longer says the values are "set from this video's
   plan" — they are saved here first, and the plan and render read
   them. Every other label, option, help line and the preview
   itself is verbatim.

6. **The staleness rules are untouched.** Direction still feeds
   the raw `direction_saved` diff on both sides, so editing it
   after a strategy exists still marks that strategy stale and
   names the rebuild, exactly as ADRs 0142/0146 rule. What changed
   is the normal path: direction is set before any plan or strategy
   exists, so the trap no longer springs on a first setup.

## Consequences

- A founder picks camera setup and location before generation, and
  the plan comes out already respecting them; the first-setup
  rebuild trap is gone.
- A fixed camera and an outdoor location can no longer be picked
  together. A project saved earlier with that pairing reads as an
  empty location pick with a notice under the fixed setup, and
  flipping back to handheld restores the pick.
- Tests: the backend suite pins the fixed-filtered static list,
  the unfiltered handheld list, and the refresh filtering including
  the unknown exclusion; the render smoke pins the section's step
  (present on Audience & template, absent from Review), the
  save-and-reload round trip and the autosave from the new step,
  the camera-keyed list swap, and the ineligible-place notice.
