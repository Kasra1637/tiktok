# 0096 — Templates: exactly three selections, no more and no less

- **Status:** accepted
- **Date:** 2026-11-04
- **Anchors:** `backend/ai_service.py` (`BRAND_TEMPLATE_COUNT`), `backend/server.py`
  (`recommend_templates`), `frontend/src/hooks/useWizardTemplates.js`,
  `frontend/src/pages/CreateVideo.jsx` (`#substep-template`);
  tests `backend/test_template_library.py`, `backend/test_template_library_api.py`;
  smoke check "the template picker shows exactly three cards"
- **Shapes:** the Step 2 template list — the same step as the angles and goals
  picker. This refines the picker's size only; tailoring, scoring and
  relevance stay as ADR 0089 and ADR 0087 left them.

## Context

The tailored set was six structures per (profile, objective, angle), asked
for whole with a top-up call, and the recommendations endpoint returned up to
eight scored rows. The picker is one scannable band on the angle/goal step,
and the list read as a scroll rather than a choice.

## Decision

- **Exactly three template cards, always.** The tailored set is three
  structures (`BRAND_TEMPLATE_COUNT = 3`), asked for whole with the same
  top-up for a short reply.
- **The top three, never more.** `recommend_templates` clamps any
  client-supplied limit to at most three: the scored top three from the
  longest list available, backfilling a retired active row with the rest.
  A client can only ask for fewer.
- **The display contract matches.** The options hook requests three, the
  visible list is sliced at three in both the ranked and tailored branches,
  and the grid renders at most three cards with no "show more" control.

## Alternatives rejected

- **Three curated, six tailored.** Two counts on one step is the same
  confusion as the old Tone/Voice pair (ADR 0091): the founder cannot tell
  which list is real.
- **A "show more" control.** The step's job is a choice, not a library browse;
  extra cards push the photo off the screen.
- **Pad a short tailored set with curated shapes.** A short set about THIS
  problem stays honest; ADR 0089 already rules out off-topic padding, and
  the top-up call exists precisely so a short reply is refilled with on-topic
  structures instead.

## Consequences

- The picker is one row of three cards on desktop and three stacked on a
  phone — the angle, goal and photo stay in one scroll length.
- A model that keeps under-delivering still stops after one top-up and
  returns what exists; the endpoint's backfill then fills the row to three
  from the next-best matches.
- The tailored-generation prompt asks for three, so a billed call generates
  the same structures the founder sees.
