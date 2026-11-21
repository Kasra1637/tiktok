# 0248 — Hook + CTA leaves the sidebar for a Create Video flow switch; the voice pick taps, speaks neutrally, and starts silent

Status: accepted (partially supersedes 0244 — the sidebar placement; partially supersedes 0246 — the voice pick's labels and default)

## Context

Four follow-ups from Kasra on Nov 21 2026, from his review of the
live Hook + CTA page (screenshot) and a voice call:

1. "Less fucking link in the sidebar." He approved the shape in the
   same breath: Hook + CTA and Demo + CTA offered as a stylish,
   polished dropdown inside the Create Video page instead.
2. The voice pick (ADR 0246) sat on "She stays silent" and "She
   talks" could not be tapped — clicking it did nothing.
3. The pick's words presume a gender: "we don't know who's customer
   upload face — just a character talks, character stay silent."
4. Two screenshot nits in the same spirit as his earlier dedupe
   order: the presenter-photo row showed a Remove button beside two
   small bin-like icons, and the Hook + CTA hook editor's helper
   text named a "Hook + Story clip" on a page that has no story.

## Decision

**The sidebar link goes; the route and the Dashboard card stay.**
The `NAV_ITEMS` entry for `/hook-cta` is removed from the sidebar
(both the desktop panel and the mobile drawer render the one
model). The `/hook-cta` route is untouched and fully functional,
and the Dashboard's Hook + CTA destination card stays — Kasra's
complaint named sidebar links, so the removal is scoped to the
sidebar and this record says so plainly. The sidebar smoke pin is
inverted: it now pins the order of the seven remaining links and
the ABSENCE of a Hook + CTA link, so the clutter cannot creep
back unnoticed.

**Create Video gains a flow switcher at the top of the page.** An
`AppSelect` — the app's one dropdown (ADRs 0162/0163), wearing the
form-field skin like the direction picks — stands under the page
header, before the step task and the rail, labelled "Make it
another way". Its closed face names this page's flow ("Create
Video — hook + story") and never changes: the control is a set of
actions, not a value the page holds. The menu offers "Hook + CTA —
a short hook, finished with your demo", which navigates to
`/hook-cta`, and "Demo + CTA — add your demo and closing message",
which walks to the current draft's own finishing step — the same
`setStep` the rail's last segment performs. With no project open
there is no finish to walk to, so that pick lands on step 1, where
a project in this flow starts. The four wizard tabs, the rail and
the sticky bar are exactly as they were (ADR 0229 stands).

**The dead voice tap was the Hook + CTA draft reducer, not the
control.** `VoiceModeControl` reported every tap correctly (the
Create Video surface, riding `wizardDraft.js`, switched fine).
The page's own reducer diverged from the wizard's `omitDefault`
semantics: it deleted an edit whose value equalled the pick's
fallback EVEN WHEN the saved row held the other value. With a
draft saved `silent` and the fallback `"talking"`, tapping
"talking" produced no edit at all — no display change, no
autosave, nothing — so the pill read as dead while the gate was
honest about a save that never happened. The same trap sat under
every fallback pick on the page (camera setup, hook shape, tone).
The fix restores the wizard's semantics verbatim: the fallback
stands in for the saved value only when the row carries none. A
new smoke check starts from a saved-silent draft, taps talking,
and pins the pick showing AND the PATCH carrying
`voice_mode: "talking"`; it fails on the shipped reducer and
passes on the fix. A jest pin covers the control half (a tap on
the unselected option reports the choice).

**The pick speaks neutrally, everywhere it speaks.** The options
are "Character talks" and "Character stays silent"; the talking
note, the silent note, the post kit's text-to-speech note
("the character does not speak in it"), the backend's
silent-performance prompt direction, and the migration's
docstring all drop she/her for "the character" / "the presenter".
This is the neutrality ADR 0089 already required of render
directions, extended to the founder-facing copy ADR 0246 wrote
with pronouns. The note's job is unchanged: it still names the
exact text for TikTok's text-to-speech (the hook line on
Hook + CTA; hook + script on Create Video).

**A new project starts silent.** Both create paths (the wizard's
studio create and the Hook + CTA create) now write
`voice_mode: "silent"` explicitly. Migration step 10's column
default stays `'talking'` untouched: it is the historical record
of the backfill existing rows received, and changing it would
rewrite what an existing project carries. Existing projects keep
their saved pick — pinned by a test that sets a project talking,
creates a fresh one beside it (silent), and re-reads the first
(still talking). The frontend's valueless-row fallbacks on both
surfaces now read "silent" to match, and the control resolves an
unknown value to silent rather than talking.

**The two nits.** The asset row's archive and delete actions —
distinct semantics (archive shelves the asset and can be undone;
delete is final) trapped behind two small glyphs that read as
duplicate bins beside Remove — now wear their names as text
("Archive" / "Restore", "Delete"), in the shared `AssetRow`, so
the library page and both embedded photo controls read the same.
Detach stays "Remove", where it always was. And
`HookLineEditor`'s helper names the clip through a `clipLabel`
prop in the caller's words: Create Video keeps the default
"Hook + Story clip"; Hook + CTA passes "short hook clip", so the
helper reads "The opening line spoken in your generated short
hook clip." — this page's clip, with no story in it.

## Consequences

- One fewer sidebar link; Hook + CTA is discovered from the flow
  switcher and the Dashboard card. Deep links and the page's tour
  are unaffected (the tour targets page elements, and ALL TOUR
  TARGETS EXIST still holds).
- The voice pick now works in both directions on both surfaces,
  starts silent on new projects, and never presumes whose face
  was uploaded. Founders with existing talking projects see no
  change until they pick otherwise.
- ADR 0246's remaining substance — the two-choice pick, the
  silent submit and prompt direction, the dedupe, the button
  repair — stands; only its labels and default are superseded.
