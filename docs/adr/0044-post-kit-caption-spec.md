# 0044 — Post-kit captions are short, user-voiced, and tailored

- **Status:** accepted
- **Date:** 2026-10-26
- **Anchors:** `backend/ai_service.py` (`generate_post_kit`); `backend/test_post_kit_api.py` (`TestPostKitCaptionGuards`)

## Context

The frozen post copy on History read like the founder wrote it: captions up
to 50 words, marketing-shaped ("this timer starts your session in one
tap"), with no enforced relationship to the app's profile, the plan, or the
clip. Long, promotional captions sit beside a render instead of sounding
like someone who used the app.

## Decision

- Captions must be 50 to 80 characters total, ending with a question. Anything
  outside the window fails loudly instead of shipping.
- The caption is written AS an everyday user of the app — first person or
  plain observation — never promotional, never founder or marketer voice.
- The prompt is grounded wider: profile description, category, audience,
  voice, differentiators, features, and use moments, plus the plan's
  objective, audience, and demo brief alongside the hook, script, and CTA.
- Hashtags and cover text are unchanged; only the caption carries the new
  voice and length contract.

## Alternatives rejected

- **Keep 50 words.** A 50-word caption is a paragraph under a 10-second
  clip; the short window forces one user-shaped thought plus a question.
- **Trim overlong captions silently.** Clamping a 100-character caption to
  80 would cut the question or mid-word; a loud failure keeps bad copy out
  of the frozen record.

## Consequences

- Old frozen kits stay untouched; only newly generated and regenerated
  captions follow the rule.
- The prompt's plan columns (`objective`, `audience`, `demo_brief`) are read
  from `studio_projects` at kit time, so future plan fields join by
  extending that read.
