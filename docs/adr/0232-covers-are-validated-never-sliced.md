# 0232 — Covers are validated, never sliced

Status: accepted

## Context

The second half of the Nov 20 2026 fragment diagnosis (ADR 0231
covers the first). Two places stored a generated cover after a
hard `[:100]` slice and no validation at all:

- The plan's first-draft cover (`generate_creative_plan` in
  `backend/ai_service.py`): the draft was normalized, cut to its
  first 100 characters, and stored — never checked against ADR
  0206's cover rule (3–5 words asked, caps of 6 words and 35
  characters). A 63-character draft was stored sliced; a
  fragment draft was stored whole.
- The post kit's cover (`generate_post_kit`): the same slice sat
  on `(approved_cover or model_cover)`, so it cut BOTH kinds —
  a model draft that should have been validated, and the
  founder's approved cover that ADR 0145 promises ships
  verbatim. An approved cover past 100 characters would have
  shipped missing its tail.

A slice is the one failure shape the cover rules exist to
prevent: the stored words are not the words anyone wrote, and
nothing downstream can tell they were cut.

## Decision

1. **One validation for drafted covers.** `_cover_text_issues`
   in `ai_service.py` collects every failure of the cover rule:
   the ADR 0206 caps (character and word counts named) plus the
   finished-cover gate of ADR 0231. The plan draft and the post
   kit's model cover both answer to it.
2. **The plan draft that fails stores no cover.** The slice is
   removed; the normalized draft is validated whole, and on
   failure the plan stores an empty cover and logs the issues.
   A plan is never refused over post copy — the cover is
   optional by design (ADR 0145), and Review's Suggest flow
   writes one under the suggestion surface's own correction and
   refusal pattern.
3. **The post kit's model cover that fails is loud.** With no
   approved cover on the project, a model cover failing the
   validation raises `RuntimeError` naming the failed rules —
   the kit's existing failure shape, beside its caption and
   hashtag refusals — instead of shipping sliced.
4. **The founder's approved cover ships verbatim, unsliced.**
   The approved branch no longer passes through any slice or
   validation: ADR 0145's promise is the founder's exact words,
   at whatever length they approved them. The draft rules govern
   model drafts only.

## Consequences

No cover is ever stored or shipped as the cut beginning of a
longer line again: a draft either satisfies the cover rule
whole, or it does not become the cover — the plan leaves the
slot empty for the Suggest flow, and the post kit fails loudly
with the rules named. Regression tests pin all four shapes: an
over-length plan draft and a fragment plan draft each store no
cover, a valid draft stores verbatim, an over-length model
cover refuses the kit, and an approved cover past the old
100-character slice ships whole. The post kit's other behavior
— caption guards, hashtag research and selection, the approved
cover's precedence — is unchanged.
