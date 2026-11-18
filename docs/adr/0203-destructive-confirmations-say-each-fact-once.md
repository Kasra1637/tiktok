# ADR 0203: Destructive confirmations say each fact once

Status: accepted

Kasra's order on Nov 18 2026: every destructive-confirmation
message in the app is to be concise and punchy — the same facts,
each said exactly once, no repeated warnings. His screenshot of
the History delete-render dialog showed why: its body stated the
loss three ways ("It removes this render from History and
deletes its video file and post copy" / "The clip leaves History
and cannot be played or downloaded here anymore" / "Its post
copy is removed with it") before reaching the two facts that
were new (the plan stays; download first to keep a copy).

## The standard

A destructive confirmation states, in decision order:

1. that it cannot be undone — once;
2. what goes — once, named concretely;
3. what stays — once, where something the reader cares about
   survives;
4. how to keep a copy — last, where a copy can be kept.

Copy only: no behavior, handler, or dialog structure changes,
and each dialog keeps its own facts — a fact from one dialog is
never imported into another.

## Applied

- **History, delete render** (`GenerationHistory.jsx`): the
  description now reads "This cannot be undone. It removes the
  render from History and deletes its video file and post copy,
  so it cannot be played or downloaded here anymore." The
  consequences list keeps the one fact the description does not
  carry ("Your project plan stays untouched."), and the
  conditional download hint stands last, unchanged — it still
  shows only when a download exists. Read top to bottom, the
  dialog is the founder's approved text with each fact once.
  The render-smoke pin that quoted the old phrasing ("removes
  this render from History", "post copy is removed") is updated
  to the new copy.
- **Create, regenerate plan** (`CreateVideo.jsx`): the
  no-edits confirm said its one fact twice ("Replace plan vN
  with a new one? The current plan is discarded."). It now asks
  once: "Discard plan vN and generate a new one?" The
  unsaved-edits variant was already clean — plan replaced and
  edits lost are two distinct facts — and is unchanged.

## Checked and left unchanged

Every other delete / remove / discard / reset / clear
confirmation in the frontend was read against the standard:

- **Delete app profile** (`AppProfileDetail.jsx`): cannot be
  undone, what goes (the app and everything built on it, counted
  in the copy), what stays (the provider call log) — each once.
- **Regenerate angles** (`useWizardAngleStep.js`, ADR 0198):
  what goes (generated angles; affected drafts' stories), what
  stays (hand-written angles; the drafts themselves) — each
  distinct fact once, in both the counted and fallback variants.
- **Strategy rebuild** (`HookContinuityPanel.jsx`, both
  variants): what is replaced and what the render follows —
  each once.
- **Delete asset** (`AssetLibrary.jsx`): what the deletion
  removes from the projects using it, and how it is recovered
  (attach a new one) — each once.
- **Generate another video** (`GenerationPanel.jsx`): not a
  destructive confirm — nothing is deleted; it states the second
  render and that the existing video stays. Out of scope, and
  already concise.
- The Demo + CTA editor's Remove and Reset buttons carry no
  confirmation copy at all (immediate, re-adjustable editor
  actions), so there is nothing to tighten.
