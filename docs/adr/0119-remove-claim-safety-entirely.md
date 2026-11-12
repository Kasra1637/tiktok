# 0119 — Remove the claim-safety system entirely

- **Status:** accepted
- **Date:** 2026-11-12
- **Anchors:** `backend/claim_safety.py` (deleted) and
  `frontend/src/components/SafetyPanel.jsx` (deleted);
  `backend/routers/studio.py` (no report computed, stored or returned;
  `_public_project` drops the stored verdict fields);
  `backend/ai_service.py` (post kit and opening messages never refuse
  wording); `backend/ai_spoken.py` (`FIRST_PERSON_PATTERNS` lives here
  now — spoken craft, not a verdict); `backend/models.py` (profile claim
  lists leave the request models and row parsing);
  `frontend/src/pages/BrandSetup.jsx` and
  `frontend/src/pages/AppProfileDetail.jsx` (no claim-list UI);
  `frontend/src/pages/Landing.jsx` (the anchor feature card is the craft
  grade, at the same pinned lengths).
- **Shapes:** supersedes ADR 0081 (claim reports advisory) outright, and
  partially supersedes ADR 0108: its bounded-by submit refusal is removed,
  while 0108's setup/Location/shape ownership is untouched.

## Context

ADR 0081 removed claim *blocking*: the safety report became advisory, no
wording flag refused a render, and tests asserted never-blocks. The system
around the report stayed — `claim_safety.build_safety_report` was still
computed on plan, strategy, edit and ready; stored on every project;
rendered in Review as the SafetyPanel; fed by three founder-maintained
claim lists (approved / needs review / banned) on the App Profile; and two
wording refusals survived outside the report: a render refused when the
final line broke the angle's bounded-by limits (ADR 0108), and the post
kit and opening messages refused copy containing a banned phrase or an
unverifiable guarantee.

The founder's decision (2026-11-12, stated repeatedly): he sees no value
in the system, it gets in the way, and the app should not be responsible
for users' flagged videos. An advisory checker the founder does not want
is not a compromise position — it is the same surface, the same lists to
maintain, and the same implication that the app vouches for wording,
minus only the refusal.

## Decision

Remove the claim-safety system entirely — code, features and content:

- `backend/claim_safety.py` is deleted, with its test file. The safety
  report is no longer computed, stored or returned anywhere; project
  responses drop `safety_report`/`safety_summary` at serialization.
- `SafetyPanel` is deleted, and with it the Review "Checks" wording
  surface and the vague-hook note in `HookLineEditor` (its data came from
  the report; the hook-rewrite endpoint stays, unsurfaced for now).
- The founder claim lists leave the product: the BrandSetup "Claim
  guardrails" group, the AppProfileDetail claim panel, the profile
  request fields, the research schema, and every prompt block that quoted
  them. `claims_used` goes with them — its only consumer was the report.
- The ADR 0108 bounded-by submit refusal is removed. The angle's
  `claims_to_respect` data field, its schema and the "BOUNDED BY" prompt
  lines stay: they are the founder's own steering for the generator, not
  a checker — nothing scans a finished line against them any more.
- Post kits and opening messages are generated without a wording refusal;
  the post kit's shape guards (hashtag classification per ADR 0100,
  caption length, the closing question) are unchanged.
- The spoken-craft first-person patterns (`FIRST_PERSON_PATTERNS`) move
  to `ai_spoken.py`: a draft claiming a personal history with the app is
  still rewritten by the generator, because that is a craft rule about
  invented testimonials, not a verdict on the founder's words.
- The database columns stay (no migration, per the no-schema-change
  rule); nothing writes or reads them.

Not claim safety, and untouched: the creative-quality craft score and
its retry, the spoken-line craft rules, the scene / opening-move /
final-beat render guards, prompt ceilings, idempotency, and the
performance snapshots and steering.

## Consequences

- No surface in the app collects, checks or comments on claim wording;
  what a founder's script says is the founder's responsibility, including
  after publishing — which is the point of the decision.
- Landing and tour copy no longer describe claim checking; the landing
  anchor card now describes the craft grade at the same pinned lengths.
- ADR 0081's never-blocks tests are replaced by acceptance tests: strong
  wording is returned, marked ready and rendered like any other wording.

Rejected alternative: keep the advisory system as ADR 0081 left it. The
founder considered the advisory version the same cost with the same
implied responsibility, and asked for the whole system out.
