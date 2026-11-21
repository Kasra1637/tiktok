# 0251 — The flow choice moves to the sidebar

Status: accepted (partially reverses ADR 0248: only the flow switch's placement moves; every other part of 0248 stands)

## Context

ADR 0248 took Hook + CTA's link out of the sidebar and put the three
ways to make a video — Create Video, Hook + CTA, Demo + CTA — in a
"Make it another way" dropdown at the top of the Create Video page.

Kasra's ruling (Nov 21 2026, reviewing the live page): remove the
dropdown from the page. The Create Video entry in the sidebar
should itself offer the choice — "when they click create video,
plan review, render, that link in the sidebar, should then give the
user selection to choose between hook plus CTA or demo plus CTA."
He judged the pop-up shape good UI and approved it.

## Decision

**The sidebar's Create Video entry is a pop-up trigger.** In the
expanded sidebar (and the mobile drawer, which shares the list),
the entry renders as a button drawn exactly as the nav row it
replaces — same rail, icon, label, hint, and the canonical
`create-nav-link` testid the tours anchor to — and clicking it
opens a small pop-up in the app-drawn menu's language
(`.app-select-menu` surface, `.app-select-option` rows, the current
way check-marked). The pop-up offers the same three ways, with the
dropdown's exact wording, each navigating exactly where ADR 0248's
switch navigated:

- **Create Video — hook + story** → `/create`.
- **Hook + CTA — a short hook, finished with your demo** →
  `/hook-cta`.
- **Demo + CTA — add your demo and closing message** → the open
  draft's finishing step. The switch read the wizard's own open
  project; the sidebar cannot, so the destination is built from the
  shell's remembered draft (the `recentDraft` memory the Continue
  line already reads): `/create?project=<id>&step=finish` when a
  draft is remembered, and plain `/create` when none is — the
  switch's no-draft pick landed on the wizard's first step, which
  is where `/create` opens, so the landing is the same place by the
  same reasoning.

The menu keeps the app-drawn control's contract: Escape closes it,
a press outside closes it, and choosing a way closes the pop-up
(and the mobile drawer). The entry stands active on the Hook + CTA
page as well as Create Video's — the pop-up's ways are one family
under this entry. Collapsed to the icon rail, the sidebar has no
room for a panel, so there the entry stays the plain link it has
always been in the rail; the ADR records that as the rail's
standing limitation, not a second behavior to maintain.

**The Create Video page loses the switcher.** The "Make it another
way" row, its AppSelect, and the `switchFlow` handler are removed;
the page's own top — title, step task line, rail — is unchanged.
The `navigate` binding the switch alone used goes with it. No file
is deleted: the switch's option set and destinations move into
`Sidebar.jsx`'s `CreateFlowMenu`.

**What does not move** (0248's other parts, standing untouched):
the voice-pick tap repair, the gender-neutral labels, the silent
default for new projects, the photo-row Archive/Delete labels, the
hook helper wording — and the Dashboard keeps its Hook + CTA
destination card, the edge choice 0248 made and Kasra did not
revisit. Hook + CTA still has no sidebar link of its own; it is
reached through this entry's pop-up and the Dashboard card.

## Consequences

- The smoke suite's two mounted switcher checks are replaced by a
  mounted check that Create Video renders no switcher (plain and
  with a draft open, the switcher checks' own mounts) and a
  source-level sidebar check pinning the pop-up: its testids, the
  three ways' exact wording, the Hook + CTA link, the
  finishing-step link construction, and the menu trigger/panel
  roles. The sidebar nav check keeps its seven-item order pin and
  its no-own-link rule for Hook + CTA, reworded to name the pop-up.
- Tour anchors are untouched: `create-nav-link` stays on the entry,
  now its trigger button; the tour-targets audit passes.
- A founder whose remembered draft was deleted elsewhere follows
  the Demo + CTA link into Create Video's own deep-link load, which
  already reports a project it cannot load instead of inventing
  one — the recentDraft memory's standing stale-cost, unchanged.
