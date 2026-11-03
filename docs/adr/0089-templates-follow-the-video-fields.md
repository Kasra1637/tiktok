# 0089 — Templates are built from the video's own fields, and the person has no gender

Status: accepted

## Context

A finished Create Video page showed one video: its top block said the Problem was
failing to name a feeling on a back step at night, and its First 3 Seconds
Promise was that same person typing a guessed word, deleting it, and saying out
loud that it is not it either. Every card under "Tailored for this app" was about
something else — journaling feeling like homework, the blank page, three generic
reasons a journal stalls, who could pick up your phone. Only one was close, and
even that was about typing fatigue rather than the missing word.

Two independent causes, one symptom:

- The tailor call received the profile, the objective and every angle's prose,
  but never the selected angle's `hook_promise` or its `claims_to_respect`. It
  generated from the app's topic area, which is exactly what it was given.
- A card printed two openings. "Shape" was the template's own first-seconds
  staging ("the founder says journaling does not have to feel like homework")
  and "In your video" was the angle's promise underneath it. One card, two
  different videos.

Both cards also named a kind of person the founder never chose: "a woman on a
back step", "the founder". The render attaches the founder's uploaded photograph
as the identity reference, so a written gender or role contradicts the only
authority on who is on screen.

## Decision

- The selected angle is the video's source of truth. The tailor call now takes
  `angle_id`, and the prompt restates that angle's Problem, First 3 Seconds
  Promise, Audience and Bounded By above the profile. The plan and hook-rewrite
  prompts carry the same Bounded By line, so a bound reaches the words a viewer
  hears and not just the picker. Tailored rows record the `angle_id` they were
  generated from, so a set is never served as another angle's set.
- `backend/template_recommendations.py` gains a deterministic relevance policy:
  `problem_anchors`, `check_template_relevance` and `filter_relevant_templates`.
  A draft that shares none of the Problem's or Promise's topic words is dropped
  before it is stored, the existing one briefed top-up call asks for the
  shortfall, and a set that comes back short stays short. Showing three shapes
  about this problem is honest; padding to six with other problems is the bug.
- `backend/angle_scene.py` composes the card's lines from that one opening:
  `opening_shape` IS the promise (one character doing one thing) and nothing
  else, `opening_staging` says where and when it happens and that the
  character's look comes from the uploaded photo, and `opening_development`
  prints what this template does next on its own "Develops as" line — never
  folded into the shape, so one card can never describe two openings. The
  template's own opening structure is not printed on the card at all; a draft
  about another problem is dropped at generation instead.
- `backend/character_policy.py` is a new pure module: `neutralize` rewrites
  person nouns and third-person pronouns to "the person" / "their", and
  `identity_terms` proves a payload is clean. It is applied to every
  video-facing field on the way in — angle fields, template names/shapes/slots,
  plan hook/script/visuals/beats, strategy text, hook rewrites and opening
  overlays — and again when the render prompt is assembled, so projects saved
  before this decision are covered without a migration.

## Alternatives rejected

- **Asking the model to self-check relevance.** The failure mode was the model
  writing about the app's topic instead of the founder's moment; asking it to
  grade its own output is the same judgment that drifted.
- **Embedding similarity.** It needs a second billed call and a threshold nobody
  can read. Word overlap against the Problem and Promise is a floor that can
  only catch "about something else", which is the defect, and it is auditable.
- **Trusting the prompt to stay neutral.** Gender and role labels are the
  model's default; a rewrite at the boundary is the only guarantee, and it is
  what makes the rule true for rows written before it.
- **Filtering curated library rows the same way.** A curated template is a shape
  the plan fills with this angle's problem, not content about another one, and
  dropping every curated row would leave the picker empty when a tailored
  generation fails. They stay listed, unpenalized on relevance; only tailored
  rows carry the verdict, and only tailored rows are dropped.

## Consequences

- Every tailored card now addresses the Problem the founder picked, and a
  generation can legitimately return fewer than six. The picker shows what
  passed; nothing is padded.
- Switching angle no longer reuses another angle's tailored set: the Generate
  CTA appears and its click serves the cached set for that angle (free) or
  generates one (ADR 0087 unchanged).
- `hook_templates` gains a nullable `angle_id`; rows written before it are
  filtered by relevance at serve time rather than trusted.
- The relevance floor is lexical. A well-written paraphrase that shares no
  topic word with the Problem or Promise is dropped; the prompt asks for the
  promise's own words precisely so that does not happen.

## Anchors

- `backend/character_policy.py` (`neutralize`, `identity_terms`)
- `backend/template_recommendations.py` (`check_template_relevance`,
  `filter_relevant_templates`, the scorer's `relevance` block)
- `backend/angle_scene.py` (`video_scene`, `opening_shape`, `opening_staging`,
  `opening_development`)
- `backend/ai_service.py` (`_angle_grounding_block`, `generate_brand_templates`,
  `normalize_brand_template`, `_angle_goal_block` Bounded By line, plan/strategy/
  overlay neutralization)
- `backend/server.py` (`_ensure_objective_templates`, `ensure_objective_templates`,
  `recommend_templates`)
- `frontend/src/components/studio/SelectionPanels.jsx` (`shapeLine`, `staging`,
  `development`, `template-development`)
- `frontend/src/hooks/useWizardTemplates.js` (angle-scoped tailor key and request)
- Smoke checks: "a card's shape and in-your-video lines describe one opening from
  the promise", "wizard requests tailored templates for the chosen objective"
  (now asserts the angle id)
