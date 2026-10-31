# 0066 — Review direction fields are profile-matched dropdowns

Status: accepted

## Context

The Review step's direction fields (setting/lighting/wardrobe, voice,
tone) were free-text boxes. A blank box invites inputs the pipeline
cannot honor safely — face and body descriptions (the character reference
photograph is the only authority on appearance) and off-brief wardrobe —
which then had to be detected and refused at save time.

## Decision

Replace the four free-text inputs with dropdowns whose options come from
a deterministic category mapping keyed off the approved profile
(`direction_options_for_profile`): a meditation app is offered calm,
modest options; a fitness app energetic ones. Same six-option discipline
as goal suggestions: the set is fixed per group, pre-vetted by
construction (no option describes a face or body), and picking only
fills the draft — saving still runs the normal claim check, the stale
strategy warning and camera-over-visual-direction precedence are
unchanged. Legacy free-text plans show as a read-only plan default and
preselect whatever they already name.

Alternatives rejected: model-generated options per profile (a call for
what a lookup answers, nondeterministic, untestable); free text plus a
face/body guardrail at save time (detection instead of construction —
the refusal happens after the founder already wrote the words).

## Consequences

- Wardrobe and look always match the app's audience type; nothing
  unvetted can enter these fields from the UI.
- The dropdown is a UX constraint, not a trust boundary: the claim
  check on save stays the guarantee.
- Variant order note: unlike goal suggestions there is no shuffle —
  four curated options per field, group-chosen once per profile.

Anchor: `backend/template_library.py:direction_options_for_profile`.
