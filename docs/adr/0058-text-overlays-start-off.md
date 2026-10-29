# 0058 — Text overlays start off until the founder turns one on

- **Status:** accepted
- **Date:** 2026-10-29
- **Anchors:** `frontend/src/demoCta/constants.js` (`DEFAULTS.hookEnabled`, `hookText`); `frontend/src/demoCta/DemoCtaEditor.jsx` (`hook-toggle`, `story-toggle`, `cta-toggle`); smoke check "a new clip starts with no text overlay turned on"

## Context

A new clip opened with the hook overlay **on**, carrying default copy ("I built
this so I'd stop journaling in Notes app") painted across the face of whatever
footage the founder added. The founder had not written that line, the clip
usually carries its own opening beat, and the overlay is the loudest element on
the preview. The end card already started off for the same reason, and the story
overlay never started on. Only the hook was on by default, so the one overlay a
founder was most likely to be surprised by was the one that painted first.

## Decision

- `DEFAULTS.hookEnabled` is `false`. All three overlay groups — hook, story,
  end card — now start off, so a freshly added clip shows the footage alone.
- The default hook copy stays in `DEFAULTS.hookText`: turning the overlay on
  immediately paints something the founder can edit, instead of an empty frame
  that looks broken.
- Turning a group on previews it at once (the existing scoped replay), so the
  effect of the choice is visible in the same click.
- Drafts keep the values they stored: this changes the default for a new clip,
  never a saved one.

## Alternatives rejected

- **Hook on with empty text.** Nothing paints, but the toggle reads on, the
  hook window still shapes the story window and the export readback claims a
  hook the clip does not carry. Off is the honest state.
- **Remove the hook overlay.** It is a core capability; the objection is to it
  being chosen for the founder, not to it existing.

## Consequences

- The export card now reads "No hook text — the opening frame carries no
  on-screen line." until the founder turns it on, which is the truth.
- With the hook off, the story window starts at 0 (`resolveStoryWindow` no
  longer reserves the hook run), so story copy can open the clip when the
  founder enables it.
- A saved look applied while both hook and end card are off replays nothing —
  the same no-op the end-card default already had; the founder sees the applied
  look once they turn an overlay on.
- The smoke suite pins the new default across all three groups, and that
  turning the hook on still works, so a future default flip fails the gate.
