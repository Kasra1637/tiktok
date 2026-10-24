# 0023 — One shared text treatment across hook, story and end card

- **Status:** partially superseded by 0024 (text-style catalog trimmed to three)
- **Date:** 2026-10-26
- **Anchors:** `frontend/src/demoCta/constants.js` (`TEXT_STYLES`);
  `frontend/src/demoCta/overlays.js` (`textStylePaint`, `drawHookOverlay`,
  `drawEndCard`); `frontend/src/demoCta/DemoCtaEditor.jsx`
  (`text-style-*` picker, `textStyle` state); `frontend/scripts/check-render-smoke.cjs`
  (finished-looks text-style checks)

## Context

After 0007 the caption had one look: dark pill, accent text, underline bar.
That single treatment never got a picker, so founders could change the face,
motion and size but not the treatment itself — the request was for the five
most viral TikTok caption styles plus the existing one, selectable in one
place.

## Decision

- **One shared `textStyle` state feeds all three painters.** The picker lives
  once in Hook Text; the story inherits it through the hook painter it
  already reuses, and the end card reads the same value. The six styles are
  Signature, Outline, Highlight, Clean, Glow, and Sticker.
- **The default changes nothing.** `signature` reproduces the old pixels
  exactly (dark pill, hook in accent / end card in white, underline on the
  hook's last line); every painter falls back to it for unknown ids, and the
  handle chip stays untouched in every style as a CTA button, not a text
  treatment.
- **Taste follows the existing pipes.** The choice persists in overlay prefs
  beside fonts and motion, joins `lookReviewKey` (changing it resets review
  approval), and is saved/applied with named looks.

## Consequences

- **Gain:** six treatments in one picker; preview and export stay
  frame-identical because the recipe is a pure function of video time.
- **Cost:** no per-overlay treatment — a founder who wants a different
  style on the end card than the hook cannot have it.

## Alternatives considered

- **Per-overlay treatments (three pickers).** Rejected: triples the picker
  surface for a combination nobody asked for, and breaks the story's free
  inheritance of the hook painter.
- **Styling through fonts alone.** Rejected: no face renders an outline,
  highlight block, glow or sticker — those are paint recipes, not typefaces.
