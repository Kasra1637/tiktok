# ADR 0151: History's record sections stand solid

Status: accepted

Follows ADR 0150 (the summary rides in the record).

## Context

Kasra, live on Nov 15 2026, reviewing the rebalanced History card:
the record's two big sections — Post copy and Plan context — were
native `<details>` disclosures sharing one open slot. Post copy
started expanded, Plan context started collapsed, and opening one
closed the other. He first asked for both expanded by default, then
corrected himself on the same call: not expandable at all. No
chevron, no collapse — solid, always-expanded sections with their
content in full.

The mechanics were also working against ADR 0150's rebalance. The
record column's remaining dead space sat under a collapsed Plan
context header: the content that could fill the column was present
in the row and deliberately hidden. A founder scanning a page of
history had to open each card's second section by hand to see the
audience and demo brief the plan was judged against, and the
one-open-at-a-time slot meant seeing the post copy and the context
together was impossible on any card.

## Decision

- **Post copy and Plan context are solid sections, not
  disclosures.** Each keeps its box — the `rounded-xl` hairline
  border on `bg-secondary/20` — and its header row (glyph, `text-sm`
  semibold muted label), but the header is static: no `<summary>`,
  no chevron, no hover affordance, nothing to click. The content
  renders in full from the first paint.
- **Everything inside survives unchanged:** the frozen kit with its
  Regenerate and Copy all actions, the Plan context read-aloud
  button and its audience / location / demo brief rows, and the
  sections' stacking order (post copy above plan context) in the
  record's single column.
- **The shared open slot is gone.** The `openPanel` state and its
  toggle handler are deleted; the journey line's post-copy item now
  only scrolls to the section, there being nothing to open. The
  kit-less row's generate box already wore the same header as a
  solid box, so a row reads the same whether or not its kit exists.
- **Scope is the History card only.** Disclosures elsewhere in the
  app (the wizard's groups, the Demo + CTA editor's panels, the
  record's own mobile Results & actions toggle) keep their
  mechanics; this decision is about a record the founder reads, not
  about controls he works through.
- **The loading skeleton keeps mirroring the card** (ADR 0143):
  its record placeholders already stand as plain blocks, which is
  now literally the finished shape.

## Consequences

- The record column fills with real content: a full card's record
  now ends near the media column's foot by content, the outcome
  ADR 0150's rebalance wanted, without a single spacer.
- A page of history is scannable end to end — audience, brief and
  copy are visible without touching a card — at the price of
  longer cards. That price is the founder's stated preference:
  the record is the product's memory, and he reads it whole.
- Regression-pinned in the render smoke suite: neither section is
  a `<details>` or carries a `<summary>`, both sections' content
  is present in the initial render, the stacking order holds, and
  on mobile the post copy stands solid outside the Results &
  actions disclosure, which keeps its own toggle.

## Addendum: the polish pass (Nov 15 2026)

The same call asked for the History card to be optimized further —
rearrange, trim or adjust so each card reads polished and cohesive
in the app's design system. The pass made three adjustments and
recorded two proposals it did not take:

- **The sections stack rides the related-blocks gap.** Post copy
  and Plan context stacked at `gap-2` (the 8px list-item token)
  inside a record whose blocks ride a 20px rhythm; the design
  system's spacing table gives related blocks that are not one
  stack 12px, so the stack is now `gap-3`.
- **Plan context carries Post copy's header hairline.** Post copy
  separated its header from its content with a rule; Plan context
  flowed straight from its header to its content. Its content now
  sits under the same `border-t` hairline, so the two solid
  sections are structurally identical: header, rule, content.
- **The kit-less box's header sits at the section's inset.** The
  generate-post-copy box headed its slot 12px down where the solid
  section heads at 10px (the section's `py-1.5` plus its header's
  `py-1`); the box now takes the same top inset and header padding,
  so the Post copy slot reads identically whether or not its kit
  exists. The dashed border stays — it is the honest signal that
  the copy is missing.

Proposals recorded, not taken: the Post copy section repeats its
label inside itself (PostKitSection's own "Caption, hashtags,
cover" group label and explainer line under the section's "Post
copy" header) — removing the duplication needs a prop on a
component three other surfaces share, which is its own change;
and the loading skeleton's record placeholders stay plain bars,
because the mirror rule (ADR 0143) pins the card's geometry,
which this pass did not move.
