# 0073 — Angles carry the viewer's outcome, not just the feature

Status: accepted

## Context

Angle cards showed FEATURE SHOWN with no outcome line, and the videos
that followed were feature demos. The cause was structural: the angle
schema asked for `app_feature` ("the feature this angle demonstrates")
with no outcome slot, and the per-angle instructions never said to pick
the change in the viewer's life — even though the profile's
`outcome_statements` (feature → life-change links) were already in
context. The strategy stage used outcomes properly; the angle stage
never asked. Separately, the health-adjacent guardrail was flattening
apps' own stated positioning (e.g. built for ADHD) into generic
productivity language.

## Decision

- New `viewer_outcome` field on every angle, drawn from
  `outcome_statements` via the chosen feature's `from_feature` link,
  flat `desired_outcomes` second, never invented. Stored in a new
  `content_angles.viewer_outcome` column (additive migration; old rows
  read as NULL and render no outcome line), editable on manual angles.
- The angle card shows an Outcome line between the feature and the
  emotion. The strategy receives it three ways: the OUTCOME rule in the
  angle+goal block (the payoff beat lands exactly this), `angle_outcome`
  in both the plan and strategy briefs — conditional keys, so empty
  outcomes spend no prompt budget and the strategy ceiling still holds.
- Guardrail calibration: the research prompt now records the app's own
  stated audience as a verified fact; the angle prompt uses that
  positioning in functional terms. The restriction stays on inferring
  conditions about viewers beyond what the sources state.

Alternatives rejected: deriving the outcome only at strategy time (the
card is where the founder judges the angle — an outcome that appears
only downstream cannot guide the pick); a fixed outcome vocabulary (the
profile's own statements are the verified set; a second vocabulary
would need its own review tier); raising the strategy prompt ceiling
(the conditional keys hold it — net-zero again).

## Consequences

- An angle is now a promise plus its proof path: feature shown, change
  delivered, emotion aimed at. Feature-demo angles are visible as such
  on the card.
- Old angles render exactly as before; new and regenerated angles carry
  outcomes. Manual angles can set one by hand.
- Anchor: `backend/ai_service.py:generate_content_angles`
  (`scene_setting_guidance`-style block is `viewer_outcome` in the
  schema); `backend/server.py:_serialize_angle_row`;
  `frontend/src/lib/angleSubtitle.js:DETAIL_FIELDS`.
