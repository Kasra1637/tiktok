# 0328 — The Audience & template step sits flush, and the wizard's cards carry no hover

Status: accepted. Kasra's orders on the Nov 24 2026 call and in the
Tiktok repo chat the same evening.

## Context

Two of Kasra's rulings land in one pass. From his screenshot of
Create's Audience & template step, he flagged dead space to the right
of the cards and containers — "our pages have a lot of gaps to the
right of most sections" — and set the process: fix ONE section at a
time, to UI/UX best practices, so he can approve the look before more
are touched. He asked whether to reduce the whole section's width and
approved the other approach instead: keep the section width as is,
trim the inside padding so the cards sit flush. The gap is the
wizard's nested gutters stacking: the step card's 20px plus the inset
panel's 16px put 36px of air between the section's edge and its cards
on every side, which reads as dead space beside short content.

Separately, he ordered the mouse hover effect removed from the Create
Video wizard rail, then clarified "the other one" means the content
too — the cards and containers in the sections carry their own hover
effect and lose it as well. Not the sidebar.

He then named the inside of the cards directly: in the four angle
cards, the fit score and the name should sit close to each other —
the full-width row stranded the pill at the far right across a dead
stretch from the title. And he ordered that a rail segment showing
the lock icon must not be clickable: the user can see the locked
step, but not click through it or view its content, which removes a
distraction.

Sequencing was his: this pass comes after the MiniMax removal
(ADR 0327) is pushed.

## Decision

- **The Audience & template step wears a tightened shell.** A new
  `.surface-step-tight` class in index.css takes the step card's
  padding and its inset panels' padding to 12px (from 20px and 16px),
  and CreateVideo.jsx applies it to the `angle` step's section only.
  The section's width is unchanged; the cards gain 24px of reach
  across the section. The class spreads to other steps only as the
  founder approves each one's look.
- **The angle cards stand two-up, and the fit pill annotates the
  title.** From `lg` the four cards stand in a two-up grid
  (`angle-card-grid`, the same grid rule as the step's template
  cards), each keeping its own height, so an open card never
  stretches its row-mate; below `lg` the stack stands. Inside a row
  the title no longer stretches (`flex-1` removed): the fit pill
  follows the title directly, and only the chevron — the expand
  affordance — stands at the row's right edge (`ml-auto`), pulled
  12px off the card's edge by the scoped `.angle-option-row` rule.
- **A locked rail segment cannot be clicked.** The segment button
  renders `disabled` while its step is locked; it still names what
  unlocks it, and no click opens the step. Unlocked segments are
  never disabled.
- **The rail segments carry no hover effect.** The segment button's
  `hover:bg-[color:var(--indigo-8)]` is removed; the segments look
  the same whether the mouse sits on them or not. Labels,
  percentages, check badges and states are untouched.
- **The wizard's cards and containers carry no hover effect.** The
  `.card-pickable:hover` rule is deleted from index.css (the pressed
  state still names the pick), and the hover utilities on the angle
  rows (`hover:bg`), the template cards and the App Profile cards
  (`hover:border`) are removed. Text-level hovers — the substep
  chips' and review tabs' `hover:text-foreground` — are not cards or
  containers and stay.
- **Pinned by render-smoke checks**: the tight shell exists and is
  worn by a step, `.card-pickable:hover` is gone from the CSS, the
  rail's and cards' hover utilities are gone from the sources, the
  angle cards stand in the two-up grid with the fit pill following
  the title and the chevron at the right edge, and a locked rail
  segment renders disabled while an unlocked one never does.

## Not covered

- The other wizard steps keep the standard 20px/16px gutters until
  the founder approves this section's look and names the next one.
- HookSnap's cards are untouched by this pass; the hover order was
  given against the Create wizard's rail and sections.
- The section header toggles below the rail still open a locked
  section to its lock notice — the founder's order named the
  progress bar, and a locked section shows the notice, never its
  content.
