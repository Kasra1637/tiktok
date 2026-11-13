# 0122 — Generation waits for the click everywhere in the create flow

Status: accepted.

## Context

Kasra's rule (2026-11-12): "if user decide to go back through the vid
creation sections and steps no content should be auto-generated unless the
user click to generate on any section."

ADR 0107 already pinned this for live goals — the goal picker never fires a
billed generation on navigation — but the same pattern had grown back in
three places in the create flow, each costing the founder a model call (and
in one case a billed one) for doing nothing but moving through the steps:

- **The plan auto-fired on entering Review.** `CreateVideo.jsx` ran
  `handleGeneratePlan` — the one plan + strategy pass — the moment the
  wizard arrived at step 3 with a profile, a template, an angle and a goal.
- **The strategy auto-built on mount.** `HookContinuityPanel.jsx` fired its
  own `generateStrategy` call when the panel mounted with a ready project,
  an angle and no strategy yet.
- **The angle list backfilled on read.** The backend's `list_content_angles`
  ran `_auto_generate_content_angles` — a billed call — on a plain GET
  whenever an approved profile held zero angles. The wizard GETs that list
  on mount, on profile pick and on deep-link load, so the backfill fired
  on navigation too.

In all three cases the founder's intent was only to look: re-reading a step
they had already planned, going back to change one choice, or resuming a
draft.

## Decision

Generation waits for the click everywhere in the create flow. This
generalizes ADR 0107 (and the tailoring discipline of ADR 0087/0098) to the
whole flow:

- **Navigation is display-only.** Going back or forward through steps and
  sections renders exactly what is already stored or cached, and fires
  nothing. Project load, draft resume and deep links fire nothing either.
- **An empty section shows its Generate button.** The click is the
  generation, exactly like the empty angle set already behaved. Review's
  plan panel got the same shape: a `plan-generate-button` that fires the
  one plan + strategy pass, with the same countdown the retry carries.
- **Stale is shown, not regenerated.** Changing an upstream selection may
  still mark downstream content stale (existing staleness semantics stay),
  but stale content is never auto-regenerated: the section shows its stale
  state and its own Generate/Regenerate control, and only the click
  regenerates.
- **Every section keeps a working explicit generate control** with its
  existing testid, busy state and countdown. No section becomes
  display-only forever.

The three auto-fires were gated, not re-routed:

1. The Review plan effect became a slim adoption-only effect: when the
   server row holds a goal this session lost, the wizard adopts it so the
   gates and the Generate click read one consistent choice.
2. The strategy panel's auto-build effect was removed; its empty state now
   says the strategy is built on the founder's click and points at the
   button above.
3. The angle listing is a pure read now; it returns the empty set for a
   profile with no angles, and the angle step's Generate button is the way
   a set gets written.

## The approve case — deliberately kept

One generation was **not** gated, and this is the one judgment call in the
decision: **approving an App Profile still generates its first angle set
server-side** (`POST /brands/{id}/approve` calls
`_auto_generate_content_angles`).

The reasoning is that approval is an action, not navigation. The founder
clicked Approve — an explicit, deliberate decision on that profile — and the
angle set is the profile's first usable content, generated at the moment the
profile becomes usable. Gating it would leave every newly approved profile
with an empty angle step and force a second deliberate click for content
the founder had just implicitly asked for by approving. The alternative —
removing generation from approve and rewriting the approval tests and the
end-to-end journey — was considered and rejected for exactly that reason:
the click that approves the profile is the click that generates its angles.

## Scope boundary

Server-side completion pipelines that are not navigation-triggered are not
section navigation, and were left running:

- The post-kit first write and poster scheduling at render completion
  (`_apply_persist_outcome` → `_schedule_post_kit`, reached via the
  generation poll and the stranded-render sweep).
- The stranded-render sweep and the jobs queue themselves.
- The plan pass's internal bounded craft retry (ADR 0115/0116) — part of
  the clicked pass, not a trigger of its own.

## Consequences

- Moving through the create flow costs no model calls at all until the
  founder clicks a Generate control — the plan, the strategy and the angles
  included.
- The smoke suite pins the rule in both directions: entering Review with a
  ready draft fires zero plan passes, the Generate click fires exactly one,
  and re-entering fires nothing; mounting the strategy panel with no
  strategy fires nothing, and its button fires exactly one; the angle
  listing returns empty and fires no generation. Pins that encoded the old
  auto-fire behaviour were rewritten to the click in the same change.
- The Review step's "still missing" guidance now reads "Set the choices
  above, then generate your free plan here." — picking the goal readies the
  Generate button, it does not start the plan.
- The founder sees one more click on a first pass through Review than
  before. That is the cost of the rule, and it is the point: the first pass
  used to spend a model call the founder had not asked for.
