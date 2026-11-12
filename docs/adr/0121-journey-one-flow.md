# 0121 — The journey is one flow: inline profile approval, one-pass plan + strategy, Demo + CTA finishing step, and a joined finished → posted home

Status: accepted.

## Context

The audit's end-to-end journey aspect sat at 6/10 on four seams where the
founder was made to carry state between surfaces by hand:

- **Approval lived elsewhere.** A draft App Profile could only be approved
  on the App Profile page. The wizard's first step named the unapproved
  profiles and linked away; the founder left the flow, approved, came
  back, and re-found their place — for a gate whose whole content is
  "read these facts and say they are right".
- **Plan and strategy were two waits.** The Review step generated the
  plan, the founder read it, and then the strategy — which is defined as
  a function of that plan — was built by a second call with its own wait
  and its own failure surface, auto-fired from a panel further down the
  same step. Nothing about the second wait bought the founder anything:
  the strategy cannot be reviewed before the plan exists, and it is
  never wanted without one.
- **The flow ended at the render.** Demo + CTA was a separate surface
  that started blank (ADR 0082's standalone shape). The wizard's last
  step handed the founder a download and a link; the editor then made
  them pick the clip they had just made from a list, in a different
  place, as if the render and its finish were unrelated jobs.
- **A finished video had no one home.** On a History card, the export
  sat in the media row, the post copy in one collapsible, and the posted
  link and recorded results behind a second toggle. "What does this
  video still need?" required opening the card and hunting three places.

## Decision

**Approval folds into the flow's start.** The wizard's profile step now
renders each draft profile with the facts its approval will be judged
on — the four rows of `_approval_gaps` (description, core features, a
use, a linked outcome), blanks named as blanks — and an approve button
under them. The approval itself is unchanged: the same
`POST /app-profiles/{id}/approve` endpoint App Profile's own button
calls, the same gaps refusal (which now lands inline, under the profile
that earned it, beside a link to the editor that can fill the gaps), the
same server-side angle generation. Approving picks the profile and
walks on to the choosing step. Only the location moved; an unapproved
profile still cannot be picked, planned from, or rendered from, and the
standalone App Profile page stays the place profiles are researched and
edited.

**Plan + strategy collapse into one pass.** A new endpoint,
`POST /studio/projects/{id}/plan-and-strategy`, runs the two existing
handlers back to back server-side — `generate_plan`, then
`generate_project_strategy`, which re-reads the row and so builds from
the plan the same pass wrote — and answers once with both. Shape,
deliberately: **two internal stages behind one endpoint**, not one
merged prompt. The prompts, gates, quality bars, spoken-line rules,
performance steering and writes of both stages are byte-for-byte the
shipped ones; merging the *calls* is what removes the second wait and
the second failure surface, and merging the *prompts* would have risked
both stages' craft for no founder-visible gain. One error surface,
honestly staged: a plan failure is the error and the strategy stage is
never attempted; a strategy failure is the error, and the plan it was
building from stays written, so a retry (the pass again, or the strategy
panel's own rebuild — which survives unchanged as the repair path for a
stale strategy) starts from the plan rather than from nothing. The
Review step's generate action calls the pass and counts down the
combined wait (the plan's founder-measured 50s plus the strategy's
~30s). Marking ready still happens after, exactly as it did after the
plan alone.

**Demo + CTA is the wizard's finishing step.** The wizard gains a
fourth step, Demo + CTA, after Review & submit. It renders the same
generation editor loader as the standalone route
(`DemoCtaGenerationEditor`), opened on the project's newest finished
render — resolved at page level (a fetch keyed on the project, plus the
render panel's completion reports), so a deep link to `?step=finish`
and a founder who watched the render land get the same answer. The
render panel's "Open in Demo + CTA" now walks to this step instead of
leaving the flow. The step ticks done when a finished render exists for
it to open on: the demo and closing message are the founder's optional
craft on top of a finished clip, so gating the journey's end on an
export would contradict the product's own "use it as is, or open it in
Demo + CTA". Before any render exists, the step names the missing
render and offers the walk back to it. The standalone `/demo-cta`
routes stay fully working for re-edits of older videos and the founder's
own footage; nothing about the editor itself changed. Progress
fractions restate as quarters; the create tour gains a finishing step
and its approval/plan copy names the inline approval and the one pass.

**History's card is the finished → posted home.** Each finished History
card now carries one journey line in its always-visible summary —
export ready · post copy written or not · posted or not · results
recorded (with the latest snapshot's facts) or none — with a stage
derived from the same row fields the scattered controls write:
`finished`, `posted` (link saved), `measured` (snapshot recorded). It
is a reading of the record, not a second record: no new data model, no
new writes. Each unfinished item is a button that walks to the control
that owns it (the post-copy panel or generate prompt; the results
section's link input, via the row's existing `openResults`). The
controls themselves did not move.

## What did not change

- `_submit_generation` is still the sole render path and the only paid
  step; plan + strategy remain free text calls.
- Posting stays manual, exactly as designed — no TikTok API, no
  publishing endpoint. The no-posting test and the landing's "publish
  them yourself" copy are untouched.
- The claim-safety system stays removed (ADR 0119).
- The two stage endpoints stay: the strategy panel's rebuild and the
  draft-recovery paths call them as before.
- ADR 0082's standalone Demo + CTA shape stays: the standalone editor
  still starts blank for the founder's own footage. What changed is
  that the wizard no longer sends its own finished renders there as a
  separate errand.
