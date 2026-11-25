# ADR 0324: One-word sidebar, HookSnap stands alone

Status: accepted

## Context

The sidebar mixed shapes: Dashboard, History, Assets and
Analytics read in one word, while App Profile and Create
Video took two and Demo + CTA carried a sidebar link the
founder no longer wanted there. The Hook + CTA page —
the fast way to a finished video: the app makes the
hook, the founder adds their demo — had no link of its
own at all (ADR 0248), then rode on the Create entry's
chevron pop-up (ADRs 0251/0259, its Demo + CTA sibling
removed by ADR 0273), where it sat one click deep under
a name that listed its parts instead of its promise.

On the Nov 24 2026 voice call the founder renamed the
list item by item, approving each label and subtitle:
one word everywhere, subtitles at the current
three-beat length (the length of "Research, review,
approve"), and a new name for the fast page — HookSnap,
for how easy and fast it is next to Create and how
short and effective its videos are on TikTok.

## Decision

The sidebar reads, in order: Dashboard ("Your work at
a glance"), Profile ("Your unique facts, audience, and
basics"), Create ("Full plan, script, render"),
HookSnap ("Hook plus demo, done fast"), History
(unchanged), Assets ("Your photos and clips, all
here"), Analytics ("Views, verdicts, lessons").

- **HookSnap stands alone.** The /hook-cta page gets
  its own sidebar entry (testid `hooksnap-nav-link`),
  standing where the Demo + CTA link stood. The Demo +
  CTA sidebar link is removed; the finishing step is
  reached inside the flows, and its page, route and
  the wizard's step names are untouched.
- **The Create pop-up is removed whole.** With its one
  remaining way standing in the list, the pop-up held
  nothing: the `CreateFlowMenu` component, its toggle
  and its menu are deleted, and Create is a plain nav
  link like every other entry. This supersedes ADRs
  0251/0259/0273.
- **Headers follow the labels.** The Profile page's
  header reads "Profile", Create's reads "Create", and
  the HookSnap page's header reads "HookSnap" — a label
  and the page it opens never disagree. The Dashboard's
  destination cards mirror the sidebar's labels and
  hints for the renamed places, as they always have.
- **The page's dressing matches.** The HookSnap page's
  hook card wore a pen (PenLine) beside "The hook" while
  the page title wears Zap; the hook card now wears Zap
  too — the same icon at the top of the page and beside
  its hook, and no pen beside the hook.
- **Routes and testids stay.** /brand, /create,
  /hook-cta and the canonical nav testids are unchanged
  except the new `hooksnap-nav-link`; only the retired
  `demo-cta-nav-link` and the pop-up's testids leave.
  Body copy still says App Profile where it names the
  thing itself — the labels are the short signposts,
  not a new vocabulary.

## Consequences

The sidebar is one flat list of one-word signposts, and
the fast page is one click from everywhere instead of
hidden under Create's chevron. Founders who learned the
pop-up lose that one gesture; the entry it opened is
now visible by name. Marketing and legal copy still use
the long names — copy sync rides in its own commit, as
always.
