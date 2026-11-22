# 0262 — The Hook + CTA page opens fresh

Status: accepted (supersedes ADR 0246's reopen-newest-draft
behavior; 0246's other fixes stand)

## Context

ADR 0244 built the Hook + CTA page to hold one draft per app, and
ADR 0246 made a plain visit reopen the app's newest draft: the
page had been minting a fresh empty draft on every visit and
opening that instead, so the founder's hooked draft sat unopened
in the list below and the render stayed gated behind "no hook
yet." Reopening the newest draft was the repair for that.

On Nov 21 2026 Kasra asked for the opposite — the page should
start fresh — and cancelled the whole piece later the same day
("Don't worry about that. Ignore that."), so the reopen stayed.
That evening he showed the live page still opening on his
previous draft: its hook line in the editor, its picks set, and
its finished render — an old, fuzzy HeyGen clip — standing in the
Render card. His words: "the fucking shit is still fucking
showing here from before. It didn't clear out." Then: "Also make
sure nothing else is left over." The fresh start was re-ordered.
The drafts section's removal, asked about in the same call, was
not answered, so the section stays.

## Decision

1. **A plain visit opens blank.** With no `?project=` naming a
   draft, the page presents the same empty working state as a
   brand-new draft: no hook line, no pending clearer-hook
   suggestion, no carried-over picks (voice, location, wardrobe,
   focus, tone, shape, hook length), no presenter photo, no render
   preview, and no Demo + CTA editor contents from any earlier
   draft. The six stage cards, their order, the tour, the render
   flow and the post kit are untouched.

2. **The canvas is an untouched row, reused — never a worked
   one.** The drafts read may adopt only a completely untouched
   draft as the visit's canvas (`isUntouchedHookCtaDraft` in
   HookCta.jsx: no hook, script or strategy, script version 0, no
   assets, and every pick at its create-time value — voice silent
   per ADR 0248, length at the create's 5 seconds, shape auto, no
   location, wardrobe, tone or focus). A render cannot hide
   behind those fields: a render needs a hook, and a hook writes
   the line, the strategy and the script version. When no
   untouched row exists, the create effect mints exactly one —
   the same single row a first-ever visit creates (ADR 0244) —
   and every later visit reuses it. Repeated opens with no edits
   never grow the app's draft count, which is ADR 0246's original
   bug kept dead under the new rule.

3. **Nothing is deleted, and explicit open is untouched.**
   Previous drafts stay exactly as they are in the database, in
   the drafts list at the foot of the page (the section stays),
   and in History. Clicking a draft in the list opens it fully —
   hook, picks, render and demo state — exactly as before, and a
   `?project=` link (History's "Reopen this hook", ADR 0253)
   takes the same explicit path. Saved projects reached from the
   Dashboard or History behave as before; only what the page
   itself loads on a plain open changed.

4. **The pins move.** The ADR 0246 reopen check is replaced by
   three render-smoke checks: a fresh visit starts blank over a
   worked draft (its hook and finished render stay in its list
   entry, and its own click restores both); a fresh visit reuses
   the app's untouched draft across two visits with zero creates;
   and beside a worked draft alone, the first visit mints one
   canvas and the next reuses it.

## Alternatives rejected

- **Deferring the row's creation until the founder's first
  edit.** The page's controls are built on the open draft — the
  photo control, the hook editor and the render panel all key on
  the project — so a project-less canvas would rebuild every
  control's empty state to save a row the reuse already avoids
  minting twice.
- **Reopening the newest draft when it has no render yet.**
  Partial carry-over — the picks, the photo, a hook with no
  render — is exactly the "something else left over" the ruling
  names. The line is drawn at untouched, not at unfinished.
- **Removing the drafts section in the same commit.** It was
  asked about in the evening call and not answered; the morning
  cancellation stands until Kasra rules otherwise, and the list
  is now the only door back into a worked draft from this page.

## Consequences

Opening Hook + CTA is starting a new hook, every time; resuming
an old one is one click in the list. A founder who set picks but
wrote no hook and left will find those picks waiting in the list,
not on the canvas — the ruling's plain meaning. ADR 0246 stands
for the voice pick, the hook-length duration validation, the
asset-library guard and the label dedupe; only its reopen
behavior is this record's to retire.
